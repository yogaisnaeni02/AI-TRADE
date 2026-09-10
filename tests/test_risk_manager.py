"""
Tes untuk risk manager — lapisan yang paling menentukan hasil akhir.

Dijalankan tanpa pytest dan tanpa MetaTrader5:

    python tests/test_risk_manager.py

Fokusnya pada perilaku yang audit temukan rusak:
  - counter harian/mingguan yang tidak pernah terisi
  - state yang hilang setiap restart sehingga kill switch tak pernah menyala

Setiap tes memakai file sementara, tidak pernah menyentuh logs/ sungguhan.
"""

from __future__ import annotations

import csv
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.risk.manager import RiskManager  # noqa: E402

# Kamis, 10 September 2026. Senin minggu itu = 7 September.
NOW = datetime(2026, 9, 10, 12, 0, 0)
EQUITY = 5_000_000.0

# Argumen check() yang selalu lolos, agar tes mengisolasi satu batas saja.
BASE = dict(
    equity=EQUITY,
    sl_points=4000,
    tp_points=12000,
    spread_points=260,
    open_positions=0,
)


def write_journal(path: Path, rows: list[tuple[str, float]]) -> None:
    """rows = [(exit_time_iso, net_idr), ...]"""
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ticket", "exit_time", "net_idr"])
        w.writeheader()
        for i, (t, net) in enumerate(rows, start=1):
            w.writerow({"ticket": i, "exit_time": t, "net_idr": net})


def make_manager(tmp: Path, rows: list[tuple[str, float]] | None = None) -> RiskManager:
    journal = tmp / "trades.csv"
    if rows is not None:
        write_journal(journal, rows)
    return RiskManager(journal_path=journal, state_path=tmp / "risk_state.json")


# -- rekonsiliasi counter dari journal -----------------------------------


def test_counters_rebuilt_from_journal(tmp: Path) -> None:
    rm = make_manager(tmp, [
        ("2026-09-08T10:00:00", -50_000),   # Selasa, minggu yang sama
        ("2026-09-10T09:00:00", +80_000),   # hari ini
        ("2026-09-10T10:00:00", -30_000),
        ("2026-09-10T11:00:00", -20_000),
    ])
    rm.refresh_from_journal(NOW)

    assert rm.state.day_trades == 3, rm.state.day_trades
    assert rm.state.day_pnl == 30_000, rm.state.day_pnl
    assert rm.state.week_pnl == -20_000, rm.state.week_pnl
    # Dua loss terakhir berurutan; yang menang di awal hari memutus rentetan.
    assert rm.state.consecutive_losses == 2, rm.state.consecutive_losses


def test_win_resets_consecutive_losses(tmp: Path) -> None:
    rm = make_manager(tmp, [
        ("2026-09-10T09:00:00", -30_000),
        ("2026-09-10T10:00:00", -30_000),
        ("2026-09-10T11:00:00", +10_000),
    ])
    rm.refresh_from_journal(NOW)
    assert rm.state.consecutive_losses == 0, rm.state.consecutive_losses


def test_journal_absent_is_safe(tmp: Path) -> None:
    rm = make_manager(tmp)  # tanpa file journal sama sekali
    rm.refresh_from_journal(NOW)
    assert rm.state.day_trades == 0
    assert rm.state.day_pnl == 0.0


def test_corrupt_rows_are_skipped(tmp: Path) -> None:
    journal = tmp / "trades.csv"
    write_journal(journal, [("2026-09-10T09:00:00", -30_000)])
    # Header terduplikasi + baris rusak — tidak boleh menjatuhkan rekonsiliasi.
    with open(journal, "a", encoding="utf-8", newline="") as f:
        f.write("ticket,exit_time,net_idr\n")
        f.write("99,bukan-tanggal,abc\n")
        f.write("100,2026-09-10T10:00:00,-20000\n")

    rm = RiskManager(journal_path=journal, state_path=tmp / "s.json")
    rm.refresh_from_journal(NOW)
    assert rm.state.day_trades == 2, rm.state.day_trades
    assert rm.state.day_pnl == -50_000, rm.state.day_pnl


# -- batas yang sebelumnya tidak pernah menyala --------------------------


def test_consecutive_losses_blocks_entry(tmp: Path) -> None:
    rm = make_manager(tmp, [
        ("2026-09-10T09:00:00", -30_000),
        ("2026-09-10T10:00:00", -30_000),
        ("2026-09-10T11:00:00", -30_000),
    ])
    d = rm.check(now=NOW, **BASE)
    assert not d.allowed, d.reason
    assert "loss beruntun" in d.reason, d.reason


def test_daily_loss_limit_blocks_entry(tmp: Path) -> None:
    # 4% dari 5.000.000 = 200.000. Dua loss 150.000 menembusnya,
    # tanpa menyentuh batas 3 loss beruntun.
    rm = make_manager(tmp, [
        ("2026-09-10T09:00:00", -150_000),
        ("2026-09-10T10:00:00", -150_000),
    ])
    d = rm.check(now=NOW, **BASE)
    assert not d.allowed, d.reason
    assert "harian" in d.reason, d.reason


def test_daily_trade_count_blocks_entry(tmp: Path) -> None:
    rm = make_manager(tmp, [
        (f"2026-09-10T{9 + i:02d}:00:00", +10_000) for i in range(6)
    ])
    d = rm.check(now=NOW, **BASE)
    assert not d.allowed, d.reason
    assert "trade/hari" in d.reason, d.reason


def test_clean_day_is_allowed(tmp: Path) -> None:
    rm = make_manager(tmp, [("2026-09-10T09:00:00", +10_000)])
    d = rm.check(now=NOW, **BASE)
    assert d.allowed, d.reason
    assert d.lot > 0


# -- state yang bertahan lintas restart ----------------------------------


def test_peak_equity_survives_restart(tmp: Path) -> None:
    """Regresi: sebelumnya peak_equity direset ke equity saat start,
    sehingga drawdown selalu 0% dan kill switch tak pernah menyala."""
    rm = make_manager(tmp, [])
    rm.observe_equity(10_000_000)
    rm.save_state()

    restarted = make_manager(tmp, [])
    restarted.load_state()

    assert restarted.state.peak_equity == 10_000_000, restarted.state.peak_equity
    assert restarted.current_drawdown_pct(8_000_000) == 20.0


def test_drawdown_halt_fires_after_restart(tmp: Path) -> None:
    rm = make_manager(tmp, [])
    rm.observe_equity(10_000_000)
    rm.save_state()

    restarted = make_manager(tmp, [])
    restarted.load_state()
    restarted.state.peak_equity = max(restarted.state.peak_equity, 7_900_000)

    d = restarted.check(now=NOW, **{**BASE, "equity": 7_900_000})
    assert not d.allowed, d.reason
    assert "drawdown" in d.reason, d.reason
    assert restarted.state.halted


def test_halt_state_persists(tmp: Path) -> None:
    rm = make_manager(tmp, [])
    rm.halt("uji coba")

    restarted = make_manager(tmp, [])
    restarted.load_state()
    assert restarted.state.halted
    assert restarted.state.halt_reason == "uji coba"

    d = restarted.check(now=NOW, **BASE)
    assert not d.allowed, d.reason
    assert "dihentikan" in d.reason, d.reason


def test_observe_equity_only_raises_peak(tmp: Path) -> None:
    rm = make_manager(tmp, [])
    rm.observe_equity(10_000_000)
    rm.observe_equity(6_000_000)
    assert rm.state.peak_equity == 10_000_000
    assert rm.observe_equity(6_000_000) == 40.0


# -- perilaku yang DIKETAHUI masih bermasalah ----------------------------


def test_documents_lot_floor_exceeding_configured_risk(tmp: Path) -> None:
    """
    Mendokumentasikan celah yang BELUM diperbaiki (bagian 7 audit).

    Lot minimum 0,01 mengunci risiko di ~Rp 69.934 per trade. Pada equity
    di bawah ~Rp 7 juta itu melebihi `max_risk_percent: 1.0`, tetapi
    check() membandingkannya terhadap `max_lot_percent_equity` (5%)
    sehingga tetap lolos.

    Tes ini sengaja menegaskan perilaku SEKARANG supaya perubahan apa pun
    di sana terlihat, bukan lolos diam-diam.
    """
    rm = make_manager(tmp, [])
    d = rm.check(now=NOW, **BASE)

    assert d.allowed, d.reason
    assert d.risk_pct > rm.max_risk_pct, (d.risk_pct, rm.max_risk_pct)
    assert d.risk_pct <= rm.max_lot_pct, (d.risk_pct, rm.max_lot_pct)


# -- runner --------------------------------------------------------------


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = []

    for fn in tests:
        with tempfile.TemporaryDirectory() as d:
            try:
                fn(Path(d))
            except AssertionError as e:
                failed.append((fn.__name__, f"assert gagal: {e}"))
            except Exception as e:  # noqa: BLE001
                failed.append((fn.__name__, f"{type(e).__name__}: {e}"))
            else:
                print(f"  ok    {fn.__name__}")

    for name, why in failed:
        print(f"  GAGAL {name} -> {why}")

    print(f"\n{len(tests) - len(failed)}/{len(tests)} lolos")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
