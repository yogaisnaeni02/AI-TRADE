"""
Downloader data historis dari MT5 ke Parquet.

Probe Tahap 0 menemukan copy_rates_from_pos gagal ("Invalid params") di
atas ~50.000 bar sekali minta, dan copy_rates_range gagal untuk rentang
panjang. Modul ini mengunduh bertahap per blok lalu menyambungnya.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import MetaTrader5 as mt5
import pandas as pd

from .mt5_gateway import MT5Gateway, load_config

TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
}

DATA_RAW = Path(__file__).resolve().parents[2] / "data" / "raw"


def _bars_to_frame(bars) -> pd.DataFrame:
    df = pd.DataFrame(bars)
    # MT5 mengembalikan epoch detik dalam waktu SERVER. Broker ini berjalan
    # di UTC+7 (terverifikasi di probe), jadi kita simpan sebagai naive
    # server-time dan konversi ke UTC secara eksplisit di bawah.
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def download_timeframe(
    gateway: MT5Gateway,
    timeframe: str,
    max_bars: int = 500_000,
    block_size: Optional[int] = None,
) -> pd.DataFrame:
    """
    Unduh bar sebanyak mungkin untuk satu timeframe, bertahap per blok.

    Berjalan mundur dari bar terbaru sampai broker berhenti memberi data
    atau max_bars tercapai.
    """
    cfg = gateway.config
    tf_const = TIMEFRAMES[timeframe]
    block = block_size or cfg["data"]["max_bars_per_request"]

    frames: list[pd.DataFrame] = []
    collected = 0
    pos = 0

    while collected < max_bars:
        want = min(block, max_bars - collected)
        bars = mt5.copy_rates_from_pos(gateway.symbol, tf_const, pos, want)

        if bars is None or len(bars) == 0:
            break

        frames.append(_bars_to_frame(bars))
        collected += len(bars)
        pos += len(bars)

        # Broker memberi lebih sedikit dari yang diminta -> riwayat habis
        if len(bars) < want:
            break

    if not frames:
        raise RuntimeError(
            f"Tidak ada data {timeframe} untuk {gateway.symbol}: {mt5.last_error()}"
        )

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)

    # Normalisasi ke UTC. Semua logika sesi bekerja di UTC agar tidak rapuh
    # terhadap perubahan DST atau offset server.
    offset_hours = cfg["broker"].get("server_utc_offset", 7)
    df["time_server"] = df["time"]
    df["time"] = df["time"] - pd.Timedelta(hours=offset_hours)
    df = df.rename(columns={"time": "time_utc"})

    return df


def save_parquet(df: pd.DataFrame, timeframe: str, symbol: str) -> Path:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    path = DATA_RAW / f"{symbol}_{timeframe}.parquet"
    df.to_parquet(path, index=False)
    return path


def download_all(timeframes: Optional[list[str]] = None) -> dict[str, Path]:
    """Unduh semua timeframe dan simpan ke Parquet."""
    cfg = load_config()
    tfs = timeframes or ["M1", "M5", "M15", "H1", "H4"]
    results: dict[str, Path] = {}

    with MT5Gateway(cfg) as gw:
        print(f"Simbol: {gw.symbol} @ {cfg['broker']['server']}\n")
        for tf in tfs:
            print(f"  {tf:4s} ... ", end="", flush=True)
            try:
                df = download_timeframe(gw, tf)
                path = save_parquet(df, tf, gw.symbol)
                results[tf] = path
                span = (df["time_utc"].max() - df["time_utc"].min()).days
                print(
                    f"{len(df):>7,} bar | "
                    f"{df['time_utc'].min():%Y-%m-%d} s/d {df['time_utc'].max():%Y-%m-%d} "
                    f"({span} hari)"
                )
            except RuntimeError as e:
                print(f"GAGAL: {e}")

    return results


if __name__ == "__main__":
    print("=" * 62)
    print("DOWNLOAD DATA HISTORIS")
    print("=" * 62)
    paths = download_all()
    print(f"\nTersimpan di: {DATA_RAW}")
    for tf, p in paths.items():
        print(f"  {tf:4s} -> {p.name}")
