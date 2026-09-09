"""
Validasi kualitas data historis.

Data buruk menghasilkan model buruk, dan masalahnya tidak memunculkan
error — hanya hasil yang salah. Modul ini memeriksa sebelum data dipakai.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

DATA_RAW = Path(__file__).resolve().parents[2] / "data" / "raw"

# Menit per bar, untuk mendeteksi gap
TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240}


@dataclass
class ValidationReport:
    timeframe: str
    total_bars: int
    date_from: pd.Timestamp
    date_to: pd.Timestamp
    duplicates: int = 0
    invalid_ohlc: int = 0
    zero_volume: int = 0
    price_spikes: int = 0
    large_moves: int = 0
    saturday_bars: int = 0
    gaps_weekday: list = field(default_factory=list)
    completeness_pct: float = 0.0

    @property
    def is_usable(self) -> bool:
        return (
            self.duplicates == 0
            and self.invalid_ohlc == 0
            and self.price_spikes == 0
            and self.saturday_bars == 0
            and self.completeness_pct >= 85.0
        )

    def print_report(self) -> None:
        status = "LULUS" if self.is_usable else "PERLU PERBAIKAN"
        print(f"\n  --- {self.timeframe} [{status}] ---")
        print(f"    Bar          : {self.total_bars:,}")
        print(f"    Rentang      : {self.date_from:%Y-%m-%d} s/d {self.date_to:%Y-%m-%d}")
        print(f"    Kelengkapan  : {self.completeness_pct:.1f}%")
        if self.duplicates:
            print(f"    [!] Duplikat timestamp : {self.duplicates}")
        if self.invalid_ohlc:
            print(f"    [!] OHLC tidak valid   : {self.invalid_ohlc}")
        if self.price_spikes:
            print(f"    [!] Spike harga        : {self.price_spikes}")
        if self.zero_volume:
            print(f"    [i] Volume nol         : {self.zero_volume}")
        if self.saturday_bars:
            print(f"    [!] Bar hari Sabtu     : {self.saturday_bars}")
        if self.large_moves:
            print(f"    [i] Pergerakan besar   : {self.large_moves} "
                  f"(reaksi berita — normal, bar penting)")
        if self.gaps_weekday:
            print(f"    [i] Gap hari kerja     : {len(self.gaps_weekday)} "
                  f"(terbesar: {max(self.gaps_weekday)} menit)")


def validate(df: pd.DataFrame, timeframe: str) -> ValidationReport:
    df = df.sort_values("time_utc").reset_index(drop=True)

    rep = ValidationReport(
        timeframe=timeframe,
        total_bars=len(df),
        date_from=df["time_utc"].min(),
        date_to=df["time_utc"].max(),
    )

    rep.duplicates = int(df["time_utc"].duplicated().sum())

    # OHLC harus konsisten: high >= max(open,close), low <= min(open,close)
    invalid = (
        (df["high"] < df["low"])
        | (df["high"] < df[["open", "close"]].max(axis=1))
        | (df["low"] > df[["open", "close"]].min(axis=1))
    )
    rep.invalid_ohlc = int(invalid.sum())

    rep.zero_volume = int((df["tick_volume"] == 0).sum())

    # Anomali feed vs reaksi berita: keduanya menghasilkan bar besar.
    # Pembedanya adalah kelanjutan harga — reaksi berita menggeser harga
    # dan bertahan, error feed melompat lalu langsung kembali.
    # Yang dicari: bar ekstrem yang close-nya kembali ke level sebelumnya.
    rng = df["high"] - df["low"]
    atr = rng.rolling(100, min_periods=20).mean()
    extreme = rng > atr * 10
    reverted = (df["close"] - df["open"]).abs() < rng * 0.2
    rep.price_spikes = int((extreme & reverted).sum())
    rep.large_moves = int(extreme.sum())

    # Gap: hanya dihitung di hari kerja. Gap akhir pekan itu normal.
    # Catatan: market forex tutup dari Jumat ~21:00 UTC sampai Minggu
    # ~21:00 UTC, jadi bar hari Minggu sore adalah pembukaan sesi Asia
    # hari Senin waktu lokal — bukan anomali.
    expected_min = TF_MINUTES[timeframe]
    delta_min = df["time_utc"].diff().dt.total_seconds() / 60
    is_weekday_gap = (delta_min > expected_min * 1.5) & (
        df["time_utc"].dt.dayofweek < 5
    )
    rep.gaps_weekday = delta_min[is_weekday_gap].dropna().astype(int).tolist()

    # Sabtu adalah satu-satunya hari yang benar-benar tidak boleh ada bar.
    rep.saturday_bars = int((df["time_utc"].dt.dayofweek == 5).sum())

    # Kelengkapan: market forex buka ~5 hari 22 jam per minggu
    # (Minggu 21:00 UTC s/d Jumat 21:00 UTC), bukan 5/7 hari penuh.
    span_min = (rep.date_to - rep.date_from).total_seconds() / 60
    open_ratio = 120 / 168  # 120 jam buka dari 168 jam seminggu
    expected_bars = (span_min / expected_min) * open_ratio
    rep.completeness_pct = min(100.0, len(df) / expected_bars * 100) if expected_bars else 0.0

    return rep


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Bersihkan masalah yang bisa diperbaiki tanpa mengarang data."""
    df = df.drop_duplicates(subset="time_utc", keep="first")
    invalid = (
        (df["high"] < df["low"])
        | (df["high"] < df[["open", "close"]].max(axis=1))
        | (df["low"] > df[["open", "close"]].min(axis=1))
    )
    df = df[~invalid]
    return df.sort_values("time_utc").reset_index(drop=True)


def validate_all(symbol: str = "XAUUSDm") -> dict[str, ValidationReport]:
    print("=" * 62)
    print("VALIDASI KUALITAS DATA")
    print("=" * 62)

    reports = {}
    for tf in ["M1", "M5", "M15", "H1", "H4"]:
        path = DATA_RAW / f"{symbol}_{tf}.parquet"
        if not path.exists():
            print(f"\n  {tf}: file tidak ada — jalankan downloader dulu.")
            continue
        df = pd.read_parquet(path)
        rep = validate(df, tf)
        rep.print_report()
        reports[tf] = rep

    print("\n" + "=" * 62)
    usable = [tf for tf, r in reports.items() if r.is_usable]
    print(f"Timeframe siap pakai: {', '.join(usable) if usable else 'TIDAK ADA'}")
    print("=" * 62)
    return reports


if __name__ == "__main__":
    validate_all()
