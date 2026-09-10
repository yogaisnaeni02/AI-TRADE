"""
Sapu pelonggaran filter momentum_fib untuk menaikkan frekuensi sinyal.

MASALAH YANG DISERANG
---------------------
Pada setelan sekarang momentum_fib hanya menghasilkan ~106 trade dalam 1,4
tahun data. Pada laju itu, membuktikan edge +0,10R butuh ~29 tahun. Ini
masalah FREKUENSI, bukan masalah edge: berapa pun bagusnya setup itu, ia
tidak akan pernah mengumpulkan sampel yang cukup untuk dibuktikan.

Penyebabnya bukan pemblokiran guardrail, melainkan sinyal yang menggerombol
(median jarak antar sinyal 1 bar). Yang menentukan jumlah trade adalah
jumlah EPISODE independen, bukan jumlah sinyal mentah.

APA YANG DIUKUR
---------------
Tiap varian melonggarkan satu atau beberapa gate, lalu dilaporkan:

    n        jumlah trade (peluang independen yang benar-benar dieksekusi)
    E[R]     expectancy
    t        E[R] / standard error
    n_2      perkiraan trade yang dibutuhkan agar |t| = 2 pada efek SEKARANG
    tahun    n_2 dibagi laju trade per tahun varian ini

Kolom `tahun` adalah inti laporan ini. Varian yang bagus bukan yang E[R]-nya
tertinggi, melainkan yang membuat pembuktian jadi MUNGKIN dalam waktu wajar.

PERINGATAN MULTIPLE TESTING
---------------------------
Skrip ini menguji banyak varian sekaligus terhadap data yang sama. Memilih
yang terbaik dari N varian lalu mempercayai angkanya adalah persis kesalahan
yang membuat proyek ini nyasar sebelumnya. Perlakukan hasilnya sebagai
PENYARING KANDIDAT, bukan sebagai bukti. Kandidat yang lolos harus diuji
ulang pada data yang belum dipakai memilihnya.

PEMAKAIAN
---------
    python scripts/sweep_frequency.py
    python scripts/sweep_frequency.py --rr 2.78
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

# Rentang data dalam tahun, untuk mengubah "butuh N trade" jadi "butuh X tahun".
def data_years(df: pd.DataFrame) -> float:
    t = pd.to_datetime(df["time_utc"])
    return (t.max() - t.min()).days / 365.25


# Varian pelonggaran. Tiap entri: (nama, dict override gate).
#
# atr_lo/atr_hi  : batas atr_percentile (gate keras di _momentum_fib)
# mom_mult       : pengali ambang momentum; 1.0 = tier penuh, 0.5 = tier kecil
#                  (nilai lebih kecil = lebih longgar)
# fib_hi/fib_lo  : ambang fib_position untuk buy/sell
VARIANTS = [
    ("baseline (sekarang)",        dict()),
    ("ATR 0.20-0.95",              dict(atr_lo=0.20, atr_hi=0.95)),
    ("momentum 0.35x",             dict(mom_mult=0.35)),
    ("momentum 0.25x",             dict(mom_mult=0.25)),
    ("fib 0.65/0.35",              dict(fib_hi=0.65, fib_lo=0.35)),
    ("fib 0.55/0.45",              dict(fib_hi=0.55, fib_lo=0.45)),
    ("ATR longgar + mom 0.35x",    dict(atr_lo=0.20, atr_hi=0.95, mom_mult=0.35)),
    ("ATR longgar + fib 0.65",     dict(atr_lo=0.20, atr_hi=0.95, fib_hi=0.65, fib_lo=0.35)),
    ("mom 0.35x + fib 0.65",       dict(mom_mult=0.35, fib_hi=0.65, fib_lo=0.35)),
    ("semua longgar",              dict(atr_lo=0.20, atr_hi=0.95, mom_mult=0.35,
                                        fib_hi=0.65, fib_lo=0.35)),
    ("semua sangat longgar",       dict(atr_lo=0.15, atr_hi=0.98, mom_mult=0.25,
                                        fib_hi=0.55, fib_lo=0.45)),
]


class LooseEngine(RuleEngine):
    """RuleEngine dengan gate momentum_fib yang bisa dilonggarkan.

    Menimpa _momentum_fib alih-alih mengubah setups.py, supaya eksperimen
    frekuensi tidak menyentuh kode yang dipakai bot live.
    """

    def __init__(self, *a, atr_lo=0.30, atr_hi=0.85, mom_mult=0.5,
                 fib_hi=0.75, fib_lo=0.25, **kw):
        super().__init__(*a, **kw)
        self.atr_lo, self.atr_hi = atr_lo, atr_hi
        self.mom_mult = mom_mult
        self.fib_hi, self.fib_lo = fib_hi, fib_lo

    def _momentum_fib(self, row):
        need = ("mom_24", "fib_position", "mom_24_q85")
        if any(not hasattr(row, f) or pd.isna(getattr(row, f)) for f in need):
            return None

        if self.momentum_sessions is not None and row.session not in self.momentum_sessions:
            return None

        if not (self.atr_lo <= row.atr_percentile <= self.atr_hi):
            return None

        if row.mom_24 > row.mom_24_q85:
            size_tier = "full"
        elif row.mom_24 > row.mom_24_q85 * self.mom_mult:
            size_tier = "reduced"
        else:
            return None

        if row.trend_htf == "uptrend" and row.fib_position > self.fib_hi:
            direction = "buy"
        elif row.trend_htf == "downtrend" and row.fib_position < self.fib_lo:
            direction = "sell"
        else:
            return None

        score = 5 if size_tier == "full" else 3
        return self._build_signal(
            row, "momentum_fib", direction, score,
            [f"momentum ({row.mom_24:.1f})", f"fib {row.fib_position:.2f}"],
            size_tier=size_tier,
        )


def evaluate(df: pd.DataFrame, years: float, overrides: dict, min_score: int,
             equity: float) -> dict:
    engine = LooseEngine(active_setups=["momentum_fib"], momentum_sessions=None,
                         **overrides)
    signals = engine.generate(df, min_score=min_score)
    if signals.empty:
        return {"n": 0, "signals": 0}

    trades, _ = Backtester().run(df, signals, initial_equity=equity)
    if trades.empty or len(trades) < 2:
        return {"n": len(trades), "signals": len(signals)}

    r = trades["r_multiple"].dropna()
    n = len(r)
    mean = float(r.mean())
    sd = float(r.std(ddof=1))
    se = sd / math.sqrt(n)
    t = mean / se if se > 0 else float("nan")

    # Trade yang dibutuhkan agar |t| = 2 pada efek sebesar yang terukur.
    n_for_t2 = (2.0 * sd / mean) ** 2 if mean != 0 else float("inf")
    per_year = n / years
    yrs = n_for_t2 / per_year if per_year > 0 else float("inf")

    return {
        "signals": len(signals),
        "n": n,
        "expectancy": mean,
        "se": se,
        "t": t,
        "winrate": float((trades["pnl_idr"] > 0).mean() * 100),
        "per_year": per_year,
        "n_for_t2": n_for_t2,
        "years": yrs,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-score", type=int, default=3,
                    help="3 agar tier 'reduced' ikut terhitung")
    ap.add_argument("--equity", type=float, default=5_000_000.0)
    ap.add_argument("--rr", type=float, default=None,
                    help="paksa RR nominal (mis. 2.78)")
    args = ap.parse_args()

    if not FEATURES.exists():
        print(f"Tidak ada {FEATURES}. Jalankan pipeline fitur dulu.")
        return 1

    df = pd.read_parquet(FEATURES)
    years = data_years(df)

    t = pd.to_datetime(df["time_utc"])
    fri = t[t.dt.dayofweek == 4]
    fri_close = (fri.dt.hour + fri.dt.minute / 60).max()
    if fri_close < 19:
        print(f"BERHENTI: data masih bergeser (Jumat tutup {fri_close:.2f}). "
              "Jalankan scripts/fix_time_offset.py dulu.")
        return 1

    print("=" * 96)
    print("SAPUAN FREKUENSI momentum_fib")
    print("=" * 96)
    print(f"Bar: {len(df):,}  rentang {years:.2f} tahun  "
          f"({t.min():%Y-%m-%d} s/d {t.max():%Y-%m-%d})")
    print(f"min_score: {args.min_score}")

    if args.rr is not None:
        import src.strategy.setups as S
        cfg = S.load_config()
        cfg["trade_distances"]["min_rr_ratio"] = args.rr
        S.load_config = lambda: cfg  # noqa: E731
        print(f"RR nominal dipaksa: 1:{args.rr}")

    print()
    hdr = (f"{'varian':28s} {'sinyal':>7s} {'n':>5s} {'E[R]':>8s} {'t':>6s} "
           f"{'WR%':>6s} {'n/thn':>6s} {'n utk t=2':>10s} {'tahun':>7s}")
    print(hdr)
    print("-" * len(hdr))

    for name, ov in VARIANTS:
        res = evaluate(df, years, ov, args.min_score, args.equity)
        if res["n"] < 2:
            print(f"{name:28s} {res.get('signals', 0):>7,} {res['n']:>5d}  (terlalu sedikit)")
            continue
        yrs = res["years"]
        yrs_s = f"{yrs:>7.0f}" if yrs < 1e4 else "   >9999"
        print(
            f"{name:28s} {res['signals']:>7,} {res['n']:>5d} "
            f"{res['expectancy']:>+8.4f} {res['t']:>6.2f} {res['winrate']:>6.2f} "
            f"{res['per_year']:>6.0f} {res['n_for_t2']:>10,.0f} {yrs_s}"
        )

    print("-" * len(hdr))
    print("\nCARA MEMILIH")
    print("  - Lihat kolom 'tahun', bukan 'E[R]'. Varian dengan E[R] tinggi tapi")
    print("    butuh 50 tahun untuk dibuktikan tidak berguna.")
    print("  - 'n utk t=2' dihitung pada efek yang TERUKUR di varian itu. Kalau")
    print("    efeknya kebetulan besar karena noise, angkanya terlalu optimis.")
    print("  - Banyak varian diuji pada data yang sama. Ini penyaring kandidat,")
    print("    bukan bukti. Kandidat harus diuji ulang di data yang belum dipakai.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
