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

import copy
import csv
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.risk.manager import RiskManager, load_risk_config  # noqa: E402

# Kamis, 10 September 2026. Senin minggu itu = 7 September.
NOW = datetime(2026, 9, 10, 12, 0, 0)
EQUITY = 5_000_000.0

# Argumen check() yang selalu lolos, agar tes mengisolasi satu batas saja.
#
# SEMUA angka diturunkan dari config, tidak ada yang di-hardcode. Tes ini
# sempat pecah saat daily.max_trades dinaikkan 6 -> 12 karena angkanya
# dikunci di sini. Suite tes harus ikut berubah saat config berubah,
# bukan menghalangi perubahannya.
_probe = RiskManager()
_d = _probe.cfg["trade_distances"]
SL_POINTS = float(_d["sl_typical_points"])
TP_POINTS = SL_POINTS * float(_d["min_rr_ratio"])
SPREAD = float(_probe.cfg["costs"]["spread_points"])

BASE = dict(
    equity=EQUITY,
    sl_points=SL_POINTS,
    tp_points=TP_POINTS,
    spread_points=SPREAD,
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
    """Jumlah loss beruntun diambil dari config."""
    batas = make_manager(tmp, []).max_consec_losses
    rm = make_manager(tmp, [
        (f"2026-09-10T{9 + i // 4:02d}:{(i % 4) * 15:02d}:00", -30_000)
        for i in range(batas)
    ])
    d = rm.check(now=NOW, **BASE)
    assert not d.allowed, f"{batas} loss beruntun seharusnya memblokir: {d.reason}"
    assert "loss beruntun" in d.reason, d.reason


def test_daily_loss_limit_blocks_entry(tmp: Path) -> None:
    """Batas rugi harian dari config, dan jumlah trade dijaga tetap di
    bawah batas loss beruntun agar yang diuji benar-benar batas rugi."""
    rm0 = make_manager(tmp, [])
    ambang = EQUITY * rm0.max_daily_loss_pct / 100.0
    n = max(1, rm0.max_consec_losses - 1)          # jangan picu loss beruntun
    per_trade = -(ambang / n) * 1.1                # 10% menembus ambang
    rm = make_manager(tmp, [
        (f"2026-09-10T{9 + i:02d}:00:00", per_trade) for i in range(n)
    ])
    d = rm.check(now=NOW, **BASE)
    assert not d.allowed, f"rugi {ambang:,.0f} seharusnya memblokir: {d.reason}"
    assert "harian" in d.reason, d.reason


def test_daily_trade_count_blocks_entry(tmp: Path) -> None:
    """Jumlah trade diambil dari config, bukan di-hardcode.

    Tes ini sempat gagal saat daily.max_trades dinaikkan 6 -> 12 karena
    angkanya dikunci di tes. Sekarang ia membaca batas yang berlaku,
    sehingga tetap sahih berapa pun nilainya."""
    probe = make_manager(tmp, [])
    batas = probe.max_daily_trades
    rm = make_manager(tmp, [
        (f"2026-09-10T{9 + i // 4:02d}:{(i % 4) * 15:02d}:00", +10_000)
        for i in range(batas)
    ])
    d = rm.check(now=NOW, **BASE)
    assert not d.allowed, f"batas {batas} trade/hari seharusnya memblokir: {d.reason}"
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


# -- rem per varian dan sumber riwayat MT5 -------------------------------


def write_journal_varian(path: Path, rows: list[tuple[str, str, float, int]]) -> None:
    """rows = [(entry_time_iso, exit_time_iso, net_idr, magic), ...]"""
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ticket", "entry_time", "exit_time",
                                          "net_idr", "magic", "varian"])
        w.writeheader()
        for i, (t_in, t_out, net, magic) in enumerate(rows, start=1):
            w.writerow({"ticket": i, "entry_time": t_in, "exit_time": t_out,
                        "net_idr": net, "magic": magic, "varian": ""})


def test_rem_per_varian_tidak_tercampur(tmp: Path) -> None:
    """Regresi: SL varian lain di akun yang sama dulu ikut dihitung sebagai
    loss beruntun varian ini - pyramid5 bisa menghentikan baseline."""
    batas = make_manager(tmp, []).max_consec_losses
    journal = tmp / "trades.csv"
    write_journal_varian(journal, [
        ("2026-09-10T08:00:00", "2026-09-10T08:30:00", +10_000, 20260909),
    ] + [
        (f"2026-09-10T09:{i:02d}:00", f"2026-09-10T09:{i + 1:02d}:30", -30_000, 20260914)
        for i in range(batas)
    ])

    baseline = RiskManager(journal_path=journal, state_path=tmp / "a.json", magic=20260909)
    d = baseline.check(now=NOW, **BASE)
    assert d.allowed, d.reason
    assert baseline.state.day_trades == 1, baseline.state.day_trades

    pyramid = RiskManager(journal_path=journal, state_path=tmp / "b.json", magic=20260914)
    pyramid.refresh_from_journal(NOW)
    assert pyramid.state.consecutive_losses == batas, pyramid.state.consecutive_losses

    semua = RiskManager(journal_path=journal, state_path=tmp / "c.json")
    semua.refresh_from_journal(NOW)
    assert semua.state.day_trades == batas + 1, semua.state.day_trades


def test_baris_tanpa_magic_milik_baseline(tmp: Path) -> None:
    journal = tmp / "trades.csv"
    write_journal(journal, [("2026-09-10T09:00:00", -30_000)])   # skema lama
    baseline = RiskManager(journal_path=journal, state_path=tmp / "a.json", magic=20260909)
    baseline.refresh_from_journal(NOW)
    assert baseline.state.day_trades == 1, baseline.state.day_trades
    lain = RiskManager(journal_path=journal, state_path=tmp / "b.json", magic=20260911)
    lain.refresh_from_journal(NOW)
    assert lain.state.day_trades == 0, lain.state.day_trades


def test_refresh_dari_riwayat_tanpa_csv(tmp: Path) -> None:
    """Bot mengoper baris riwayat MT5 langsung; CSV tidak diperlukan."""
    rm = RiskManager(journal_path=tmp / "tidak_ada.csv", state_path=tmp / "s.json", magic=20260909)
    trades = [
        {"entry_time": f"2026-09-10T09:0{i}:00", "exit_time": f"2026-09-10T09:1{i}:00",
         "net_idr": -30_000, "magic": 20260909}
        for i in range(2)
    ]
    assert rm.refresh_from_journal(NOW, trades=trades)
    assert rm.state.consecutive_losses == 2, rm.state.consecutive_losses

    # Pergantian hari memakai sumber terakhir itu, bukan CSV yang tidak ada.
    rm.state.day = None
    rm.check(now=NOW, **BASE)
    assert rm.state.consecutive_losses == 2, rm.state.consecutive_losses


def test_journal_gagal_dibaca_rem_tidak_direset(tmp: Path) -> None:
    """Regresi: gagal baca dulu = [] = semua counter nol = rem terbuka."""
    rm = make_manager(tmp, [("2026-09-10T09:00:00", -30_000), ("2026-09-10T10:00:00", -30_000)])
    assert rm.refresh_from_journal(NOW)
    assert rm.state.consecutive_losses == 2

    rm.journal_path = tmp   # ada, tetapi direktori -> open() gagal
    assert rm.refresh_from_journal(NOW) is False
    assert rm.state.consecutive_losses == 2, rm.state.consecutive_losses
    assert rm.journal_error


def test_mode_batch_per_varian(tmp: Path) -> None:
    risk = copy.deepcopy(load_risk_config())
    risk["daily"]["loss_mode"] = "batch"
    rm = RiskManager(risk=risk, journal_path=tmp / "x.csv", state_path=tmp / "s.json", magic=20260914)
    trades = [
        # batch 1: dua posisi bertumpuk, keduanya rugi
        {"entry_time": "2026-09-10T09:00:00", "exit_time": "2026-09-10T09:20:00", "net_idr": -1, "magic": 20260914},
        {"entry_time": "2026-09-10T09:05:00", "exit_time": "2026-09-10T09:25:00", "net_idr": -1, "magic": 20260914},
        # trade varian lain di sela-sela: tidak boleh memutus rentetan
        {"entry_time": "2026-09-10T09:30:00", "exit_time": "2026-09-10T09:35:00", "net_idr": +5, "magic": 20260909},
        # batch 2: satu posisi rugi
        {"entry_time": "2026-09-10T10:00:00", "exit_time": "2026-09-10T10:10:00", "net_idr": -1, "magic": 20260914},
    ]
    rm.refresh_from_journal(NOW, trades=trades)
    assert rm.state.consecutive_loss_batches == 2, rm.state.consecutive_loss_batches


# -- jarak antar entry (pyramiding) --------------------------------------


def _manager_jarak(tmp: Path, jarak: float) -> RiskManager:
    risk = copy.deepcopy(load_risk_config())
    risk["global"]["min_jarak_entry_atr"] = jarak
    return RiskManager(risk=risk, journal_path=tmp / "j.csv", state_path=tmp / "s.json")


def test_jarak_entry_memblokir_posisi_menumpuk(tmp: Path) -> None:
    """Regresi kejadian live 16 Sep 2026: tujuh posisi BUY dibuka di
    4325-4327, lalu koreksi 6 poin menyapu semuanya sekaligus."""
    rm = _manager_jarak(tmp, 1.0)
    arg = {**BASE, "open_positions": 1, "atr": 4.0, "harga": 4325.0}

    d = rm.check(now=NOW, **{**arg, "harga_posisi": [4326.5]})     # jarak 1,5 < 4,0
    assert not d.allowed, "entry menumpuk harus ditolak"
    assert "jarak" in d.reason, d.reason

    d = rm.check(now=NOW, **{**arg, "harga_posisi": [4335.0]})     # jarak 10 > 4,0
    assert d.allowed, d.reason

    # Yang dipakai adalah posisi TERDEKAT, bukan yang pertama.
    d = rm.check(now=NOW, **{**arg, "harga_posisi": [4335.0, 4326.0]})
    assert not d.allowed, d.reason


def test_jarak_entry_mati_secara_default(tmp: Path) -> None:
    rm = make_manager(tmp, [])
    assert rm.min_jarak_entry_atr == 0.0, rm.min_jarak_entry_atr
    d = rm.check(now=NOW, **{**BASE, "open_positions": 1, "atr": 4.0,
                             "harga": 4325.0, "harga_posisi": [4325.1]})
    assert d.allowed, d.reason


def test_jarak_entry_dilewati_bila_data_harga_tidak_dioper(tmp: Path) -> None:
    """Pemanggil lama (tanpa atr/harga) tidak boleh berubah perilakunya."""
    rm = _manager_jarak(tmp, 1.0)
    assert rm.check(now=NOW, **{**BASE, "open_positions": 1}).allowed


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
