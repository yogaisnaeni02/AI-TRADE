"""
Ukur performa momentum_fib per sesi, dengan data yang labelnya sudah benar.

KENAPA SKRIP INI ADA
--------------------
Seluruh ranking sesi yang tercatat di docs/ dan di komentar setups.py
diukur pada data yang kolom `time_utc`-nya meleset 7 jam, sehingga LABEL
sesinya salah sasaran. Yang tercatat sebagai "ny_afternoon +5,45%"
sebenarnya sesi Tokyo, dan sesi London yang sesungguhnya berlabel "asia"
lalu ditolak filter — tidak pernah diuji sekali pun.

Setelah scripts/fix_time_offset.py dijalankan, label sesi jatuh di jam yang
benar. Skrip ini mengukur ulang dari nol: SEMUA sesi dibuka, lalu tiap sesi
dilaporkan terpisah dengan standard error-nya.

CARA BACA HASILNYA
------------------
Kolom `t` adalah expectancy dibagi standard error-nya. Sebagai pegangan:

    |t| < 2   -> tidak bisa dibedakan dari nol. Jangan diambil keputusan.
    |t| >= 2  -> layak dilihat lebih lanjut, TAPI ingat skrip ini menguji
                 6 sesi sekaligus. Menguji 6 hipotesis lalu memilih yang
                 terbaik membuat ambang 2 terlalu longgar; pakai ~2,6
                 (koreksi Bonferroni) sebelum percaya.

Winrate tinggi TIDAK berarti untung. Pada RR 1:3 breakeven ada di ~25,4%,
jadi yang menentukan adalah expectancy, bukan winrate.

PEMAKAIAN
---------
    python scripts/measure_sessions.py
    python scripts/measure_sessions.py --min-score 5 --max-bars 100000
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.engine import Backtester  # noqa: E402
from src.strategy.setups import RuleEngine  # noqa: E402

FEATURES = ROOT / "data" / "processed" / "XAUUSDm_M5_features.parquet"

SESSION_ORDER = [
    "asia", "london_open", "pre_ny", "london_ny", "ny_afternoon", "rollover",
]

# Jam pasar sesungguhnya, untuk mengingatkan label ini kini berarti apa.
SESSION_MEANING = {
    "asia": "Tokyo",
    "london_open": "London buka",
    "pre_ny": "London siang",
    "london_ny": "London-NY overlap",
    "ny_afternoon": "NY sore",
    "rollover": "NY tutup",
}


def summarize(trades: pd.DataFrame) -> dict:
    """Expectancy dengan standard error — bukan sekadar rata-rata."""
    r = trades["r_multiple"].dropna()
    n = len(r)
    if n == 0:
        return {"n": 0}

    mean = float(r.mean())
    sd = float(r.std(ddof=1)) if n > 1 else float("nan")
    se = sd / math.sqrt(n) if n > 1 else float("nan")
    t = mean / se if se == se and se > 0 else float("nan")

    wins = trades["pnl_idr"] > 0
    gross_win = trades.loc[wins, "pnl_idr"].sum()
    gross_loss = abs(trades.loc[~wins, "pnl_idr"].sum())

    return {
        "n": n,
        "expectancy": mean,
        "se": se,
        "t": t,
        "ci_lo": mean - 1.96 * se if se == se else float("nan"),
        "ci_hi": mean + 1.96 * se if se == se else float("nan"),
        "winrate": float(wins.mean() * 100),
        "pf": gross_win / gross_loss if gross_loss else float("inf"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-score", type=int, default=5)
    ap.add_argument("--max-bars", type=int, default=0, help="0 = semua")
    ap.add_argument("--equity", type=float, default=5_000_000.0)
    args = ap.parse_args()

    if not FEATURES.exists():
        print(f"Tidak ada {FEATURES}. Jalankan pipeline fitur dulu.")
        return 1

    df = pd.read_parquet(FEATURES)
    if args.max_bars:
        df = df.tail(args.max_bars).reset_index(drop=True)

    t = pd.to_datetime(df["time_utc"])
    fri = t[t.dt.dayofweek == 4]
    fri_close = (fri.dt.hour + fri.dt.minute / 60).max() if not fri.empty else float("nan")
    if fri_close < 19:
        print(
            f"BERHENTI: bar Jumat terakhir jatuh jam {fri_close:.2f}, "
            "artinya data masih bergeser. Jalankan scripts/fix_time_offset.py dulu."
        )
        return 1

    print("=" * 82)
    print("PERFORMA momentum_fib PER SESI - data berlabel waktu yang sudah benar")
    print("=" * 82)
    print(f"Bar        : {len(df):,}  ({t.min():%Y-%m-%d} s/d {t.max():%Y-%m-%d})")
    print(f"Jumat tutup: {fri_close:.2f} UTC (pasar sesungguhnya ~21:00-22:00) [OK]")
    print(f"min_score  : {args.min_score}   equity awal: Rp {args.equity:,.0f}")

    # Semua sesi dibuka; pemisahan dilakukan SETELAH trade terbentuk.
    engine = RuleEngine(active_setups=["momentum_fib"], momentum_sessions=None)
    signals = engine.generate(df, min_score=args.min_score)

    if signals.empty:
        print("\nTidak ada sinyal sama sekali.")
        return 1

    print(f"\nSinyal 24 jam: {len(signals):,}")

    bt = Backtester()
    trades, _ = bt.run(df, signals, initial_equity=args.equity)

    if trades.empty:
        print("Tidak ada trade tereksekusi.")
        return 1

    print(
        f"Trade tereksekusi: {len(trades):,}"
        "  (dibatasi 1 posisi & batas harian, jadi lebih sedikit dari sinyal)\n"
    )

    # Backtester tidak membawa kolom session ke trades. Sambungkan lewat
    # waktu: entry terjadi di bar SETELAH sinyal, jadi mundurkan 1 bar M5.
    sig_sess = dict(zip(pd.to_datetime(signals["time"]), signals["session"]))
    entry_times = pd.to_datetime(trades["entry_time"])
    trades = trades.assign(
        session=[sig_sess.get(et - pd.Timedelta(minutes=5), "?") for et in entry_times]
    )

    hdr = (
        f"{'sesi':14s} {'jam pasar':19s} {'n':>5s} {'E[R]':>8s} "
        f"{'SE':>7s} {'t':>6s} {'WR%':>6s} {'PF':>6s}  vonis"
    )
    print(hdr)
    print("-" * len(hdr))

    for s in SESSION_ORDER:
        sub = trades[trades["session"] == s]
        st = summarize(sub)
        if st["n"] == 0:
            print(f"{s:14s} {SESSION_MEANING[s]:19s} {0:>5d}  (tidak ada trade)")
            continue
        if abs(st["t"]) < 2:
            verdict = "tidak signifikan"
        elif st["t"] > 0:
            verdict = "layak dilihat"
        else:
            verdict = "negatif signifikan"
        print(
            f"{s:14s} {SESSION_MEANING[s]:19s} {st['n']:>5d} "
            f"{st['expectancy']:>+8.4f} {st['se']:>7.4f} {st['t']:>6.2f} "
            f"{st['winrate']:>6.2f} {st['pf']:>6.2f}  {verdict}"
        )

    unknown = int((trades["session"] == "?").sum())
    if unknown:
        print(f"\n({unknown} trade tidak terpetakan ke sesi - lihat penyambungan waktu)")

    total = summarize(trades)
    print("-" * len(hdr))
    print(
        f"{'SEMUA':14s} {'24 jam':19s} {total['n']:>5d} "
        f"{total['expectancy']:>+8.4f} {total['se']:>7.4f} {total['t']:>6.2f} "
        f"{total['winrate']:>6.2f} {total['pf']:>6.2f}"
    )
    print(f"\nCI 95% keseluruhan: [{total['ci_lo']:+.4f} ; {total['ci_hi']:+.4f}]")

    print("\nCATATAN")
    print("  - Breakeven winrate pada RR 1:3 sekitar 25,4%. Winrate di atas itu")
    print("    belum tentu untung; yang menentukan expectancy.")
    print("  - 6 sesi diuji sekaligus. Ambang |t| >= 2 terlalu longgar untuk")
    print("    memilih yang terbaik dari 6; pakai ~2,6 (Bonferroni) sebelum percaya.")

    if total["expectancy"] > 0 and total["se"] == total["se"]:
        sd = total["se"] * math.sqrt(total["n"])
        n_needed = (1.96 + 0.84) ** 2 * sd**2 / total["expectancy"] ** 2
        print(
            f"  - Untuk membuktikan E[R]={total['expectancy']:+.4f} pada 95%/power 80%"
            f" dibutuhkan ~{n_needed:,.0f} trade."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
