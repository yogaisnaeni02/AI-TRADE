"""
Metrik evaluasi backtest.

Metrik UTAMA adalah expectancy (R per trade), bukan winrate. Winrate tinggi
mudah dicapai dengan TP kecil dan SL besar, dan itu justru merugikan.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute(trades: pd.DataFrame, initial_equity: float = 800_000) -> dict:
    if trades.empty:
        return {"total_trades": 0, "note": "tidak ada trade"}

    wins = trades[trades["pnl_idr"] > 0]
    losses = trades[trades["pnl_idr"] <= 0]

    gross_profit = wins["pnl_idr"].sum()
    gross_loss = abs(losses["pnl_idr"].sum())

    equity_curve = initial_equity + trades["pnl_idr"].cumsum()
    running_peak = equity_curve.cummax()
    drawdown = (running_peak - equity_curve) / running_peak * 100

    # Sharpe per-trade dianualisasi dengan asumsi ~250 hari trading.
    # Ini pendekatan kasar; frekuensi trade sebenarnya dipakai sebagai skala.
    r = trades["r_multiple"]
    if len(trades) > 1 and r.std() > 0:
        span_days = max(
            (trades["exit_time"].max() - trades["entry_time"].min()).days, 1
        )
        trades_per_year = len(trades) / span_days * 365
        sharpe = r.mean() / r.std() * np.sqrt(trades_per_year)
    else:
        sharpe = 0.0

    # Rentetan kalah terpanjang
    is_loss = (trades["pnl_idr"] <= 0).astype(int)
    streak = max_streak = 0
    for v in is_loss:
        streak = streak + 1 if v else 0
        max_streak = max(max_streak, streak)

    final_equity = initial_equity + trades["pnl_idr"].sum()

    return {
        "total_trades": len(trades),
        "winrate_pct": len(wins) / len(trades) * 100,
        "expectancy_r": r.mean(),
        "profit_factor": gross_profit / gross_loss if gross_loss > 0 else np.inf,
        "total_pnl_idr": trades["pnl_idr"].sum(),
        "final_equity_idr": final_equity,
        "return_pct": (final_equity - initial_equity) / initial_equity * 100,
        "max_drawdown_pct": drawdown.max(),
        "sharpe": sharpe,
        "avg_win_idr": wins["pnl_idr"].mean() if len(wins) else 0.0,
        "avg_loss_idr": losses["pnl_idr"].mean() if len(losses) else 0.0,
        "avg_rr_realized": (
            abs(wins["pnl_idr"].mean() / losses["pnl_idr"].mean())
            if len(wins) and len(losses) and losses["pnl_idr"].mean() != 0
            else 0.0
        ),
        "max_consecutive_losses": max_streak,
        "avg_bars_held": trades["bars_held"].mean(),
        "tp_hits": int((trades["outcome"] == "tp").sum()),
        "sl_hits": int((trades["outcome"] == "sl").sum()),
        "timeouts": int((trades["outcome"] == "timeout").sum()),
    }


def print_report(m: dict, title: str = "HASIL BACKTEST") -> None:
    print("\n" + "=" * 62)
    print(title)
    print("=" * 62)

    if m.get("total_trades", 0) == 0:
        print("  Tidak ada trade.")
        return

    print(f"  Total trade        : {m['total_trades']:,}")
    print(f"  Winrate            : {m['winrate_pct']:.1f}%")
    print(f"  Expectancy         : {m['expectancy_r']:+.3f} R   <- METRIK UTAMA")
    print(f"  Profit Factor      : {m['profit_factor']:.2f}")
    print(f"  Sharpe             : {m['sharpe']:.2f}")
    print()
    print(f"  P/L total          : Rp {m['total_pnl_idr']:>14,.0f}")
    print(f"  Equity akhir       : Rp {m['final_equity_idr']:>14,.0f}")
    print(f"  Return             : {m['return_pct']:+.1f}%")
    print(f"  Max Drawdown       : {m['max_drawdown_pct']:.1f}%")
    print()
    print(f"  Rata-rata menang   : Rp {m['avg_win_idr']:>14,.0f}")
    print(f"  Rata-rata kalah    : Rp {m['avg_loss_idr']:>14,.0f}")
    print(f"  RR terealisasi     : 1:{m['avg_rr_realized']:.2f}")
    print(f"  Loss beruntun maks : {m['max_consecutive_losses']}")
    print()
    print(f"  TP / SL / timeout  : {m['tp_hits']} / {m['sl_hits']} / {m['timeouts']}")
    print(f"  Rata-rata bar hold : {m['avg_bars_held']:.0f}")


def check_gate(m: dict) -> tuple[bool, list[str]]:
    """Kriteria kelulusan Tahap 3 sesuai roadmap."""
    checks = [
        ("Expectancy positif", m.get("expectancy_r", 0) > 0),
        ("Profit Factor > 1.2", m.get("profit_factor", 0) > 1.2),
        ("Minimal 200 trade", m.get("total_trades", 0) >= 200),
        ("Max DD < 25%", m.get("max_drawdown_pct", 100) < 25),
    ]
    failed = [name for name, ok in checks if not ok]
    return len(failed) == 0, failed
