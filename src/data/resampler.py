"""
Resampling M1 -> timeframe lebih tinggi, dan verifikasi urutan intrabar.

Dua kegunaan:

1. Membangun M5/M15 dari M1 agar konsisten dengan sumbernya.

2. Menjawab pertanyaan yang tidak bisa dijawab data M5: kalau dalam satu
   bar M5 harga menyentuh SL DAN TP, mana yang duluan? Data OHLC M5 tidak
   menyimpan urutannya. Dengan M1 di dalam bar itu, urutannya bisa dilihat.

Keterbatasan yang harus disadari: riwayat M1 broker ini hanya ~103 hari,
sedangkan M5 mencapai ~516 hari. Karena itu resampling BUKAN pengganti
data M5 broker untuk training — melainkan alat kalibrasi di periode yang
tertutupi M1.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import pandas as pd

DATA_RAW = Path(__file__).resolve().parents[2] / "data" / "raw"

PANDAS_FREQ = {"M5": "5min", "M15": "15min", "H1": "1h", "H4": "4h"}


def resample_from_m1(df_m1: pd.DataFrame, target_tf: str) -> pd.DataFrame:
    """Agregasi bar M1 menjadi timeframe lebih tinggi."""
    if target_tf not in PANDAS_FREQ:
        raise ValueError(f"Timeframe {target_tf} tidak didukung untuk resampling.")

    df = df_m1.set_index("time_utc").sort_index()

    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "tick_volume": "sum",
        "spread": "mean",
    }
    if "real_volume" in df.columns:
        agg["real_volume"] = "sum"

    out = df.resample(PANDAS_FREQ[target_tf], label="left", closed="left").agg(agg)
    # Periode tanpa tick sama sekali (market tutup) menghasilkan baris kosong
    out = out.dropna(subset=["open"])
    out["spread"] = out["spread"].round().astype(int)

    return out.reset_index()


def compare_with_broker(
    df_resampled: pd.DataFrame, df_broker: pd.DataFrame, tol: float = 0.05
) -> dict:
    """
    Bandingkan M5 hasil resampling dengan M5 dari broker.

    Selisih kecil itu wajar (beda sumber tick). Selisih besar menandakan
    ada yang salah — misalnya offset timezone atau boundary bar berbeda.
    """
    a = df_resampled.set_index("time_utc")[["open", "high", "low", "close"]]
    b = df_broker.set_index("time_utc")[["open", "high", "low", "close"]]
    common = a.index.intersection(b.index)

    if len(common) == 0:
        return {"overlap_bars": 0, "error": "tidak ada timestamp yang beririsan"}

    diff = (a.loc[common] - b.loc[common]).abs()
    return {
        "overlap_bars": len(common),
        "max_diff_usd": float(diff.max().max()),
        "mean_diff_usd": float(diff.mean().mean()),
        "bars_within_tol": int((diff.max(axis=1) <= tol).sum()),
        "pct_within_tol": float((diff.max(axis=1) <= tol).mean() * 100),
    }


def resolve_intrabar_order(
    df_m1: pd.DataFrame,
    bar_start: pd.Timestamp,
    bar_end: pd.Timestamp,
    sl_price: float,
    tp_price: float,
    direction: Literal["buy", "sell"],
) -> Optional[str]:
    """
    Tentukan mana yang tersentuh lebih dulu di dalam satu bar: SL atau TP.

    Mengembalikan "sl", "tp", "none", atau None jika data M1 tidak tersedia
    untuk periode tersebut (di luar cakupan riwayat M1).

    Inilah yang tidak bisa dijawab data M5 saja, dan yang membuat backtest
    harus memakai asumsi pesimis tanpa data M1.
    """
    mask = (df_m1["time_utc"] >= bar_start) & (df_m1["time_utc"] < bar_end)
    sub = df_m1.loc[mask]
    if sub.empty:
        return None

    for row in sub.itertuples():
        if direction == "buy":
            hit_sl = row.low <= sl_price
            hit_tp = row.high >= tp_price
        else:
            hit_sl = row.high >= sl_price
            hit_tp = row.low <= tp_price

        # Kedua level tersentuh di menit yang sama: tetap ambigu bahkan di
        # M1. Pilih pesimis (SL) — konsisten dengan kebijakan backtest.
        if hit_sl and hit_tp:
            return "sl"
        if hit_sl:
            return "sl"
        if hit_tp:
            return "tp"

    return "none"


def m1_coverage(df_m1: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Rentang waktu yang tertutupi data M1 — di luar ini harus pakai asumsi."""
    return df_m1["time_utc"].min(), df_m1["time_utc"].max()


if __name__ == "__main__":
    symbol = "XAUUSDm"
    print("=" * 62)
    print("RESAMPLING M1 -> M5 & VERIFIKASI")
    print("=" * 62)

    m1 = pd.read_parquet(DATA_RAW / f"{symbol}_M1.parquet")
    m5_broker = pd.read_parquet(DATA_RAW / f"{symbol}_M5.parquet")

    lo, hi = m1_coverage(m1)
    print(f"\n  Cakupan M1     : {lo:%Y-%m-%d} s/d {hi:%Y-%m-%d} "
          f"({(hi - lo).days} hari, {len(m1):,} bar)")
    print(f"  Cakupan M5 brk : {m5_broker['time_utc'].min():%Y-%m-%d} s/d "
          f"{m5_broker['time_utc'].max():%Y-%m-%d} "
          f"({(m5_broker['time_utc'].max() - m5_broker['time_utc'].min()).days} hari)")

    m5_resampled = resample_from_m1(m1, "M5")
    print(f"\n  M5 dari resampling: {len(m5_resampled):,} bar")

    stats = compare_with_broker(m5_resampled, m5_broker)
    print("\n  --- Perbandingan dengan M5 broker ---")
    for k, v in stats.items():
        if isinstance(v, float):
            print(f"    {k:<18}: {v:.4f}")
        else:
            print(f"    {k:<18}: {v}")

    out = DATA_RAW / f"{symbol}_M5_from_M1.parquet"
    m5_resampled.to_parquet(out, index=False)
    print(f"\n  Tersimpan: {out.name}")

    pct = stats.get("pct_within_tol", 0)
    print("\n  " + "-" * 58)
    if pct >= 95:
        print(f"  [OK] {pct:.1f}% bar cocok — resampling terverifikasi benar.")
        print("       M1 bisa dipakai untuk resolusi SL/TP intrabar.")
    else:
        print(f"  [PERIKSA] Hanya {pct:.1f}% bar cocok.")
        print("            Cek offset timezone atau boundary bar.")
    print("  " + "-" * 58)
