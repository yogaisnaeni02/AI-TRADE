"""
Trade journal — mencatat setiap posisi yang tertutup.

Sumber kebenarannya adalah riwayat deal MT5, bukan catatan internal bot.
Bot bisa restart, crash, atau kehilangan state; riwayat broker tidak.

Dipakai dashboard untuk menampilkan statistik, dan untuk membandingkan
performa live dengan ekspektasi backtest (Tahap 8).
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

import MetaTrader5 as mt5

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "logs"
TRADES_CSV = LOG_DIR / "trades.csv"

MAGIC = 20260909

FIELDS = [
    "ticket", "symbol", "direction", "lot",
    "entry_time", "entry_price", "exit_time", "exit_price",
    "pnl_idr", "commission", "swap", "net_idr",
    "r_multiple", "duration_min", "comment",
]


def _load_existing_tickets() -> set[int]:
    if not TRADES_CSV.exists():
        return set()
    try:
        with open(TRADES_CSV, encoding="utf-8", newline="") as f:
            return {int(row["ticket"]) for row in csv.DictReader(f) if row.get("ticket")}
    except (OSError, ValueError, KeyError):
        return set()


def sync_closed_trades(days_back: int = 30, risk_per_trade_idr: float = 0.0) -> int:
    """
    Ambil posisi yang sudah tertutup dari MT5 dan catat yang belum ada.

    Mengembalikan jumlah trade baru yang dicatat. Aman dipanggil berulang —
    trade yang sudah tercatat dilewati.
    """
    LOG_DIR.mkdir(exist_ok=True)

    to_time = datetime.now() + timedelta(days=1)
    from_time = datetime.now() - timedelta(days=days_back)

    deals = mt5.history_deals_get(from_time, to_time)
    if deals is None:
        return 0

    # Kelompokkan SEMUA deal per posisi dulu (tanpa filter magic).
    #
    # BUG YANG DIPERBAIKI (9 Sep 2026): posisi yang ditutup MANUAL (bukan
    # oleh bot) kadang diberi magic=0 oleh broker pada deal EXIT-nya, meski
    # deal ENTRY-nya magic=20260909. Filter magic per-deal sebelumnya
    # membuang deal exit itu, menyisakan cuma 1 deal (entry) per posisi -
    # sehingga trade yang sudah selesai tidak pernah tercatat di journal.
    #
    # Perbaikan: kelompokkan dulu per position_id tanpa filter, baru saring
    # posisi mana yang MILIK BOT berdasarkan apakah SALAH SATU deal-nya
    # (biasanya entry) bermagic milik sistem ini.
    all_positions: dict[int, list] = {}
    for d in deals:
        all_positions.setdefault(d.position_id, []).append(d)

    positions = {
        pos_id: dl for pos_id, dl in all_positions.items()
        if any(d.magic == MAGIC for d in dl)
    }

    existing = _load_existing_tickets()
    new_rows = []

    for pos_id, dl in positions.items():
        if pos_id in existing or len(dl) < 2:
            continue

        dl.sort(key=lambda x: x.time)
        entry, exit_ = dl[0], dl[-1]

        pnl = sum(d.profit for d in dl)
        comm = sum(d.commission for d in dl)
        swap = sum(d.swap for d in dl)
        net = pnl + comm + swap

        duration = (exit_.time - entry.time) / 60.0

        new_rows.append({
            "ticket": pos_id,
            "symbol": entry.symbol,
            "direction": "buy" if entry.type == mt5.DEAL_TYPE_BUY else "sell",
            "lot": entry.volume,
            "entry_time": datetime.fromtimestamp(entry.time).isoformat(),
            "entry_price": entry.price,
            "exit_time": datetime.fromtimestamp(exit_.time).isoformat(),
            "exit_price": exit_.price,
            "pnl_idr": round(pnl, 2),
            "commission": round(comm, 2),
            "swap": round(swap, 2),
            "net_idr": round(net, 2),
            "r_multiple": round(net / risk_per_trade_idr, 3) if risk_per_trade_idr else "",
            "duration_min": round(duration, 1),
            "comment": entry.comment,
        })

    if not new_rows:
        return 0

    new_rows.sort(key=lambda r: r["entry_time"])
    write_header = not TRADES_CSV.exists()

    with open(TRADES_CSV, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            w.writeheader()
        w.writerows(new_rows)

    return len(new_rows)


def summary() -> dict:
    """Statistik ringkas dari journal."""
    if not TRADES_CSV.exists():
        return {"total": 0}

    with open(TRADES_CSV, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return {"total": 0}

    nets = [float(r["net_idr"]) for r in rows if r.get("net_idr")]
    wins = [n for n in nets if n > 0]
    losses = [n for n in nets if n <= 0]

    gross_win = sum(wins)
    gross_loss = abs(sum(losses))

    return {
        "total": len(nets),
        "wins": len(wins),
        "losses": len(losses),
        "winrate_pct": len(wins) / len(nets) * 100 if nets else 0,
        "total_pnl": sum(nets),
        "avg_win": gross_win / len(wins) if wins else 0,
        "avg_loss": -gross_loss / len(losses) if losses else 0,
        "profit_factor": gross_win / gross_loss if gross_loss else float("inf"),
    }


if __name__ == "__main__":
    if not mt5.initialize():
        raise SystemExit(f"Gagal connect MT5: {mt5.last_error()}")

    n = sync_closed_trades()
    print(f"Trade baru dicatat: {n}")

    s = summary()
    if s["total"]:
        print(f"\n  Total trade   : {s['total']}")
        print(f"  Winrate       : {s['winrate_pct']:.1f}%")
        print(f"  P/L total     : Rp {s['total_pnl']:,.0f}")
        print(f"  Profit Factor : {s['profit_factor']:.2f}")
        print(f"  Rata2 menang  : Rp {s['avg_win']:,.0f}")
        print(f"  Rata2 kalah   : Rp {s['avg_loss']:,.0f}")
    else:
        print("Belum ada trade tercatat.")

    mt5.shutdown()
