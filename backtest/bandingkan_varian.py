"""
Bandingkan varian dari config/variants.yaml, side-by-side, satu backtest.

UNTUK APA
---------
Sistem ini punya beberapa fitur (filter konfluensi, sisi sell, dst) yang
masing-masing punya flag sendiri. Skrip ini menjawab "yang mana lebih
baik?" dengan mengukur SEMUA varian pada data dan metode yang identik,
dalam satu tabel — bukan menjalankan skrip terpisah tiap kali lalu
membandingkan angka secara manual.

METODE
------
Hanya `global.max_drawdown_percent` (halt) yang dimatikan saat mengukur,
karena itu memotong PERIODE (lihat docs/38 bagian 2) — bukan guardrail
harian yang memang bagian dari strategi. Guardrail lain (batas trade
harian, loss beruntun, rugi harian) TETAP AKTIF, sesuai standar yang
disepakati setelah insiden baseline salah ukur (docs/38).

PEMAKAIAN
---------
    python backtest/bandingkan_varian.py
    python backtest/bandingkan_varian.py --varian baseline konfluensi
    python backtest/bandingkan_varian.py --holdout 0.3
"""

from __future__ import annotations

import argparse
import copy
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.engine import Backtester, load_configs  # noqa: E402
from src.strategy.setups import RuleEngine  # noqa: E402
from src.variants import list_variants, apply_variant  # noqa: E402

FEATURES = ROOT / "data" / "processed" / "XAUUSDm_M5_features.parquet"


def _stat(trades: pd.DataFrame) -> dict | None:
    if trades.empty:
        return None
    r = trades["r_multiple"].dropna()
    n = len(r)
    if n < 2:
        return None
    se = r.std(ddof=1) / math.sqrt(n)
    gw = r[r > 0].sum()
    gl = abs(r[r <= 0].sum())
    return {
        "n": n,
        "E_R": float(r.mean()),
        "t": float(r.mean() / se) if se > 0 else float("nan"),
        "wr": float((r > 0).sum() / n * 100),
        "pf": float(gw / gl) if gl else float("inf"),
    }


def _fmt(s: dict | None) -> str:
    if s is None:
        return "sampel terlalu kecil"
    return (f"n={s['n']:<5} E[R]={s['E_R']:>+8.4f}  t={s['t']:>+6.2f}  "
            f"WR={s['wr']:>5.1f}%  PF={s['pf']:>5.2f}")


def run_variant(df: pd.DataFrame, name: str, settings: dict, risk: dict) -> dict:
    """Backtest satu varian. Hanya halt DD dimatikan (lihat docstring)."""
    merged_settings, magic, meta = apply_variant(settings, name)

    engine = RuleEngine(config=merged_settings)
    signals = engine.generate(df)

    bt = Backtester(config=merged_settings, risk=copy.deepcopy(risk))
    bt.max_dd = 1e5  # matikan HANYA halt DD - lihat docstring modul ini

    trades, curve = bt.run(df, signals)
    return {
        "name": name,
        "magic": magic,
        "meta": meta,
        "signals": len(signals),
        "trades": trades,
        "curve": curve,
        "stat": _stat(trades),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--varian", nargs="+", default=None,
                    help="nama varian yang dibandingkan (default: semua)")
    ap.add_argument("--holdout", type=float, default=0.30,
                    help="pecahan data TERAKHIR yang dilaporkan terpisah (0 = mati)")
    args = ap.parse_args()

    if not FEATURES.exists():
        print(f"File fitur tidak ada: {FEATURES}")
        return 1

    df = pd.read_parquet(FEATURES)
    settings, risk = load_configs()

    all_variants = list_variants()
    if not all_variants:
        print("Tidak ada varian terdaftar di config/variants.yaml")
        return 1

    names = args.varian or list(all_variants)
    unknown = [n for n in names if n not in all_variants]
    if unknown:
        print(f"Varian tidak dikenal: {unknown}")
        print(f"Tersedia: {', '.join(all_variants)}")
        return 1

    tmin, tmax = df["time_utc"].min(), df["time_utc"].max()
    split = tmin + (tmax - tmin) * (1 - args.holdout) if args.holdout > 0 else None

    print("=" * 100)
    print(f"BANDING VARIAN — {df['time_utc'].min().date()} s/d {df['time_utc'].max().date()}"
          f"  ({(tmax - tmin).days} hari)")
    print("=" * 100)
    print("Metode: hanya halt DD dimatikan; batas harian/loss beruntun TETAP AKTIF.\n")

    results = []
    for name in names:
        res = run_variant(df, name, settings, risk)
        results.append(res)
        # Peringatan: varian tanpa override APA PUN adalah janji kosong -
        # hasilnya identik dengan config dasar, bukan fitur yang berdiri
        # sendiri. ml_walkforward contohnya: filternya belum diintegrasikan
        # ke RuleEngine, jadi override-nya {} dan hasilnya = allow_sell
        # apa pun yang ada di settings.yaml saat ini, BUKAN "baseline murni".
        if not (res["meta"].get("override") or {}):
            print(f"  [PERINGATAN] varian '{name}': override kosong — hasil di "
                  f"bawah BUKAN fitur berdiri sendiri, melainkan settings.yaml "
                  f"apa adanya saat ini. Baca 'status' di variants.yaml.")

    header = f"{'VARIAN':<22} {'magic':>7}  {'PERIODE PENUH':<50}"
    if split is not None:
        header += f"  {'HOLDOUT ' + str(int(args.holdout*100)) + '%':<40}"
    print(header)
    print("-" * len(header))

    for res in results:
        line = f"{res['name']:<22} {res['magic']:>7}  {_fmt(res['stat']):<50}"
        if split is not None:
            t = pd.to_datetime(res["trades"]["entry_time"]) if not res["trades"].empty else pd.Series([], dtype="datetime64[ns]")
            ho_trades = res["trades"][t >= split] if len(t) else res["trades"]
            line += f"  {_fmt(_stat(ho_trades)):<40}"
        print(line)

    print()
    print("Status tiap varian (config/variants.yaml):")
    for res in results:
        status = res["meta"].get("status", "-")
        peringatan = res["meta"].get("peringatan", "")
        print(f"  {res['name']:<22} {status}" + (f"  !! {peringatan.strip()}" if peringatan else ""))

    print()
    print("Sinyal mentah (sebelum gerbang risiko) per varian:")
    for res in results:
        print(f"  {res['name']:<22} {res['signals']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
