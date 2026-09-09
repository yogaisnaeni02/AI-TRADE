"""
Pipeline penyusunan dataset: gabungkan M5 dengan konteks timeframe tinggi.

TITIK RAWAN LOOKAHEAD: menggabungkan H1 ke M5 mudah membocorkan masa depan.
Bar H1 jam 10:00 baru SELESAI jam 11:00, jadi bar M5 jam 10:05 tidak boleh
melihatnya. Modul ini memakai merge_asof dengan timestamp H1 yang sudah
digeser ke waktu penutupannya.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..features.indicators import add_all
from ..strategy import sessions, structure

DATA_RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
DATA_PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"

TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240}


def load_raw(symbol: str, tf: str) -> pd.DataFrame:
    path = DATA_RAW / f"{symbol}_{tf}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} tidak ada — jalankan downloader dulu.")
    return pd.read_parquet(path).sort_values("time_utc").reset_index(drop=True)


def build_htf_context(df_htf: pd.DataFrame, tf: str, prefix: str) -> pd.DataFrame:
    """
    Siapkan konteks timeframe tinggi dengan timestamp penutupan bar.

    Kolom `available_at` = waktu bar SELESAI. Inilah momen paling awal
    informasi tersebut boleh dipakai oleh timeframe rendah.
    """
    out = add_all(df_htf)
    out = structure.add_structure(out)

    ctx = pd.DataFrame(
        {
            "available_at": out["time_utc"] + pd.Timedelta(minutes=TF_MINUTES[tf]),
            f"{prefix}_trend": out["trend"],
            f"{prefix}_close": out["close"],
            f"{prefix}_ema50": out["ema50"],
            f"{prefix}_atr": out["atr"],
            f"{prefix}_adx": out["adx"],
            f"{prefix}_swing_high": out["last_swing_high"],
            f"{prefix}_swing_low": out["last_swing_low"],
        }
    )
    return ctx.dropna(subset=["available_at"]).sort_values("available_at")


def build_dataset(symbol: str = "XAUUSDm", base_tf: str = "M5") -> pd.DataFrame:
    """Susun dataset lengkap: base timeframe + indikator + sesi + konteks HTF."""
    base = load_raw(symbol, base_tf)

    base = add_all(base)
    base = sessions.prepare(base)
    base = structure.add_structure(base)

    for tf, prefix in [("H1", "h1"), ("H4", "h4")]:
        ctx = build_htf_context(load_raw(symbol, tf), tf, prefix)
        base = pd.merge_asof(
            base.sort_values("time_utc"),
            ctx,
            left_on="time_utc",
            right_on="available_at",
            direction="backward",
        ).drop(columns=["available_at"])

    # Bias HTF gabungan.
    #
    # Menuntut H1 DAN H4 sepakat terlalu ketat: keduanya hanya sepakat 42,6%
    # dari waktu, dan itu membuang 91% peluang sweep. Klasifikasi swing-based
    # memang sering menghasilkan "ranging" di timeframe tinggi.
    #
    # Pendekatan yang dipakai: H1 sebagai bias utama (lebih responsif),
    # H4 sebagai VETO — hanya membatalkan bila arahnya berlawanan tegas.
    # Saat H1 ranging, posisi harga terhadap EMA50 H1 dipakai sebagai
    # bias lemah.
    base["trend_htf"] = base["h1_trend"]

    h4_opposes = (
        ((base["h1_trend"] == "uptrend") & (base["h4_trend"] == "downtrend"))
        | ((base["h1_trend"] == "downtrend") & (base["h4_trend"] == "uptrend"))
    )
    base.loc[h4_opposes, "trend_htf"] = "ranging"

    # H1 ranging -> pakai posisi harga terhadap EMA50 H1 sebagai bias lemah
    h1_flat = base["h1_trend"] == "ranging"
    above = h1_flat & (base["h1_close"] > base["h1_ema50"]) & (base["h4_trend"] != "downtrend")
    below = h1_flat & (base["h1_close"] < base["h1_ema50"]) & (base["h4_trend"] != "uptrend")
    base.loc[above, "trend_htf"] = "uptrend"
    base.loc[below, "trend_htf"] = "downtrend"

    # Indikator lanjutan (MACD, Fibonacci, Stochastic, momentum, dll.)
    from .indicators import add_extended
    base = add_extended(base)

    # Ambang momentum sebagai rolling quantile — dihitung dari data MASA LALU
    # saja agar tidak membocorkan informasi masa depan ke keputusan entry.
    base['mom_24_q85'] = (
        base['mom_24'].rolling(2000, min_periods=500).quantile(0.85).shift(1)
    )

    # Keselarasan multi-timeframe sebagai skor 0-1
    base["htf_alignment"] = (
        (base["h1_trend"] == base["h4_trend"]).astype(int)
        + (base["trend"] == base["h1_trend"]).astype(int)
    ) / 2

    return base


def save_processed(df: pd.DataFrame, symbol: str, tf: str) -> Path:
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    path = DATA_PROCESSED / f"{symbol}_{tf}_features.parquet"
    df.to_parquet(path, index=False)
    return path


if __name__ == "__main__":
    print("=" * 62)
    print("BUILD DATASET")
    print("=" * 62)

    symbol = "XAUUSDm"
    df = build_dataset(symbol, "M5")
    path = save_processed(df, symbol, "M5")

    print(f"\n  Bar        : {len(df):,}")
    print(f"  Rentang    : {df['time_utc'].min():%Y-%m-%d} s/d {df['time_utc'].max():%Y-%m-%d}")
    print(f"  Kolom      : {len(df.columns)}")
    print(f"  Tersimpan  : {path.name}")

    print("\n  --- Distribusi sesi ---")
    for name, cnt in df["session"].value_counts().items():
        mark = " (trading)" if name in sessions.TRADING_SESSIONS else ""
        print(f"    {name:<15}: {cnt:>7,}{mark}")

    print("\n  --- Distribusi tren M5 ---")
    for name, cnt in df["trend"].value_counts().items():
        print(f"    {name:<15}: {cnt:>7,}")

    print("\n  --- Bias HTF (H1+H4 sepakat) ---")
    for name, cnt in df["trend_htf"].value_counts().items():
        print(f"    {name:<15}: {cnt:>7,}")

    sweeps = int(df["sweep_high"].sum() + df["sweep_low"].sum())
    print(f"\n  Bar dengan sweep Asia range: {sweeps:,}")
