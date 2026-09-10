"""
Klasifikasi sesi trading dan pelacakan Asia range.

Waktu server broker = UTC+0 (diverifikasi 10 Sep 2026, lihat
config/settings.yaml::broker.server_utc_offset). Kolom time_utc pada data
sudah UTC murni, jadi modul ini membandingkan langsung dengan jam UTC.

DIPERBAIKI 10 Sep 2026 — batas jam di bawah ini SEBELUMNYA salah 7 jam.

Nilai lama dihitung dengan asumsi server UTC+7 ("WIB dikurangi 7"). Setelah
offset dikoreksi ke 0, batas itu tidak ikut dikoreksi, sehingga setiap bar
mendapat label sesi yang meleset 7 jam:

    jam 00-03 UTC (Asia sesungguhnya)   -> berlabel "ny_afternoon", DITRADINGKAN
    jam 07-13 UTC (London sesungguhnya) -> berlabel "asia",         DIBLOKIR
    jam 14-16 UTC (overlap London-NY)   -> berlabel "london_open"

Akibatnya sesi paling likuid dalam sehari tidak pernah ditradingkan sama
sekali. Bukti: volatilitas median per jam UTC memuncak di 13:00-15:00
(608/624/507 pip) — itu overlap London-NY yang sebenarnya.

Batas baru mengikuti jam pasar yang sesungguhnya (UTC):
  Tokyo/Asia        23:00-07:00
  London open       07:00-12:00
  London-NY overlap 12:00-16:00   <- paling likuid
  NY sore           16:00-21:00
  Rollover          21:00-23:00

`trade=True` untuk semua sesi: ranking sesi lama diukur pada label yang
salah, jadi tidak bisa dipakai. Pemilihan sesi sekarang diserahkan ke
filter kualitas (momentum/ATR/fib) dan ke `momentum_sessions` di config
bila nanti diukur ulang dengan data yang benar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# (nama, jam_mulai_utc, jam_selesai_utc, boleh_trading)
SESSIONS = [
    ("asia", 23.0, 7.0, True),
    ("london_open", 7.0, 12.0, True),
    ("london_ny", 12.0, 16.0, True),
    ("ny_afternoon", 16.0, 21.0, True),
    ("rollover", 21.0, 23.0, True),
]

TRADING_SESSIONS = {name for name, _, _, ok in SESSIONS if ok}


def _hour_float(ts: pd.Series) -> pd.Series:
    return ts.dt.hour + ts.dt.minute / 60.0


def classify_session(ts: pd.Series) -> pd.Series:
    """Beri label sesi untuk tiap timestamp UTC."""
    h = _hour_float(ts)
    out = pd.Series("unknown", index=ts.index, dtype=object)

    for name, start, end, _ in SESSIONS:
        if start < end:
            mask = (h >= start) & (h < end)
        else:  # sesi melewati tengah malam (Asia)
            mask = (h >= start) | (h < end)
        out[mask] = name

    return out


def trading_day(ts: pd.Series) -> pd.Series:
    """
    Hari trading, bukan hari kalender.

    Sesi Asia dimulai 23:00 UTC hari sebelumnya, sehingga bar jam 23:00-24:00
    UTC termasuk hari trading berikutnya. Tanpa ini, Asia range akan terpotong
    di tengah malam.
    """
    h = _hour_float(ts)
    shifted = ts + pd.to_timedelta((h >= 23.0).astype(int), unit="D")
    return shifted.dt.date


def add_sessions(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["session"] = classify_session(out["time_utc"])
    out["session_date"] = trading_day(out["time_utc"])
    out["is_trading_session"] = out["session"].isin(TRADING_SESSIONS)

    out["hour_utc"] = out["time_utc"].dt.hour
    out["dayofweek"] = out["time_utc"].dt.dayofweek

    # Jumat setelah 14:00 UTC (21:00 WIB): tidak ada entry baru — risiko gap
    out["friday_cutoff"] = (out["dayofweek"] == 4) & (_hour_float(out["time_utc"]) >= 14.0)

    return out


def add_asia_range(df: pd.DataFrame) -> pd.DataFrame:
    """
    Hitung high/low sesi Asia per hari trading.

    Level ini adalah kolam likuiditas: stop order menumpuk di atas Asia high
    dan di bawah Asia low. London open sering menyapunya sebelum bergerak ke
    arah sebenarnya — inilah dasar setup unggulan sistem.

    ANTI-LOOKAHEAD: nilai range hanya tersedia SETELAH sesi Asia berakhir.
    Bar di dalam sesi Asia mendapat NaN.
    """
    out = df.copy()

    asia = out[out["session"] == "asia"]
    rng = asia.groupby("session_date").agg(
        asia_high=("high", "max"),
        asia_low=("low", "min"),
        asia_end_time=("time_utc", "max"),
    )

    out = out.merge(rng, left_on="session_date", right_index=True, how="left")

    # Kosongkan nilai untuk bar yang terjadi sebelum sesi Asia selesai
    not_yet = out["time_utc"] <= out["asia_end_time"].fillna(pd.Timestamp.max)
    out.loc[not_yet, ["asia_high", "asia_low"]] = np.nan

    out["asia_range"] = out["asia_high"] - out["asia_low"]
    out["dist_to_asia_high"] = out["asia_high"] - out["close"]
    out["dist_to_asia_low"] = out["close"] - out["asia_low"]

    return out.drop(columns=["asia_end_time"])


def detect_sweep(df: pd.DataFrame, lookback: int = 12) -> pd.DataFrame:
    """
    Deteksi liquidity sweep terhadap Asia range.

    Sweep = harga menembus level, lalu KEMBALI masuk ke dalam range.
    Penembusan yang berlanjut adalah breakout, bukan sweep — keduanya
    dibedakan oleh apakah harga kembali.

      sweep_high : harga menyapu Asia high lalu kembali turun -> bias SELL
      sweep_low  : harga menyapu Asia low lalu kembali naik  -> bias BUY
    """
    out = df.copy()
    n = len(out)

    sweep_high = np.zeros(n, dtype=bool)
    sweep_low = np.zeros(n, dtype=bool)
    sweep_extreme = np.full(n, np.nan)

    highs = out["high"].values
    lows = out["low"].values
    closes = out["close"].values
    a_high = out["asia_high"].values
    a_low = out["asia_low"].values
    in_session = out["session"].isin(TRADING_SESSIONS).values

    for i in range(1, n):
        if not in_session[i] or np.isnan(a_high[i]):
            continue

        start = max(0, i - lookback)

        # Sweep high: ada bar yang menembus ke atas, harga kini kembali di bawah
        window_high = highs[start : i + 1]
        if window_high.max() > a_high[i] and closes[i] < a_high[i]:
            sweep_high[i] = True
            sweep_extreme[i] = window_high.max()

        # Sweep low: ada bar menembus ke bawah, harga kini kembali di atas
        window_low = lows[start : i + 1]
        if window_low.min() < a_low[i] and closes[i] > a_low[i]:
            sweep_low[i] = True
            sweep_extreme[i] = window_low.min()

    out["sweep_high"] = sweep_high
    out["sweep_low"] = sweep_low
    out["sweep_extreme"] = sweep_extreme

    return out


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Pipeline lengkap sesi: klasifikasi -> Asia range -> deteksi sweep."""
    return detect_sweep(add_asia_range(add_sessions(df)))
