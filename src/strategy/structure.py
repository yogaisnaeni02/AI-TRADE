"""
Deteksi struktur market: swing point, BOS, CHoCH, klasifikasi tren.

Ini fondasi seluruh sistem. Tanpa filter struktur, indikator hanya noise
dan sistem akan melawan arah dominan — penyebab terbesar kerugian ritel.

CATATAN LOOKAHEAD: swing point baru terkonfirmasi setelah N bar ke kanan
terbentuk. Modul ini menandai swing pada posisi aslinya, tetapi menyediakan
kolom `confirmed_at_idx` sehingga pemakai bisa memastikan hanya swing yang
sudah terkonfirmasi pada bar t yang dipakai untuk keputusan di bar t.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


@dataclass
class SwingPoint:
    idx: int
    time: pd.Timestamp
    price: float
    kind: Literal["high", "low"]
    confirmed_at_idx: int  # bar saat swing ini baru bisa diketahui


def find_swings(df: pd.DataFrame, left: int = 2, right: int = 2) -> list[SwingPoint]:
    """
    Deteksi swing high/low dengan metode fractal.

    Swing high pada bar i: high[i] adalah tertinggi di antara `left` bar
    sebelumnya dan `right` bar sesudahnya. Karena butuh `right` bar ke depan,
    swing ini baru terkonfirmasi di bar i + right.
    """
    highs, lows = df["high"].values, df["low"].values
    n = len(df)
    swings: list[SwingPoint] = []

    for i in range(left, n - right):
        window_h = highs[i - left : i + right + 1]
        window_l = lows[i - left : i + right + 1]

        if highs[i] == window_h.max() and (window_h.argmax() == left):
            swings.append(
                SwingPoint(i, df["time_utc"].iloc[i], highs[i], "high", i + right)
            )
        elif lows[i] == window_l.min() and (window_l.argmin() == left):
            swings.append(
                SwingPoint(i, df["time_utc"].iloc[i], lows[i], "low", i + right)
            )

    return swings


def classify_trend(swings: list[SwingPoint], lookback: int = 4) -> str:
    """
    Klasifikasi tren dari urutan swing terakhir.

    HH + HL -> uptrend, LH + LL -> downtrend, selain itu ranging.
    """
    if len(swings) < lookback:
        return "ranging"

    recent = swings[-lookback:]
    hi = [s.price for s in recent if s.kind == "high"]
    lo = [s.price for s in recent if s.kind == "low"]

    if len(hi) < 2 or len(lo) < 2:
        return "ranging"

    higher_highs = hi[-1] > hi[-2]
    higher_lows = lo[-1] > lo[-2]
    lower_highs = hi[-1] < hi[-2]
    lower_lows = lo[-1] < lo[-2]

    if higher_highs and higher_lows:
        return "uptrend"
    if lower_highs and lower_lows:
        return "downtrend"
    return "ranging"


def add_structure(
    df: pd.DataFrame, left: int = 2, right: int = 2, lookback: int = 4
) -> pd.DataFrame:
    """
    Tambahkan kolom struktur ke dataframe, bebas lookahead.

    Kolom yang dihasilkan:
      last_swing_high / last_swing_low : level swing terakhir YANG SUDAH
                                          terkonfirmasi pada bar tersebut
      trend        : uptrend / downtrend / ranging
      bos          : 1 bullish BOS, -1 bearish BOS, 0 tidak ada
      choch        : 1 bullish CHoCH, -1 bearish CHoCH, 0 tidak ada
      bars_since_bos / bars_since_choch
    """
    out = df.copy()
    n = len(out)
    swings = find_swings(out, left, right)

    last_sh = np.full(n, np.nan)
    last_sl = np.full(n, np.nan)
    trend = np.array(["ranging"] * n, dtype=object)
    bos = np.zeros(n, dtype=int)
    choch = np.zeros(n, dtype=int)

    # Iterasi maju: pada tiap bar, hanya pakai swing yang sudah terkonfirmasi.
    confirmed: list[SwingPoint] = []
    swing_ptr = 0
    cur_trend = "ranging"
    # Tren BERARAH terakhir (uptrend/downtrend), mengabaikan periode ranging
    # di antaranya. Dipakai deteksi CHoCH - lihat catatan di bawah.
    last_directional: str | None = None

    for i in range(n):
        while swing_ptr < len(swings) and swings[swing_ptr].confirmed_at_idx <= i:
            confirmed.append(swings[swing_ptr])
            swing_ptr += 1

        highs = [s for s in confirmed if s.kind == "high"]
        lows = [s for s in confirmed if s.kind == "low"]

        if highs:
            last_sh[i] = highs[-1].price
        if lows:
            last_sl[i] = lows[-1].price

        cur_trend = classify_trend(confirmed, lookback)
        trend[i] = cur_trend

        # BOS: harga menembus swing terakhir searah tren yang sedang berjalan
        close_i = out["close"].iloc[i]
        if highs and close_i > highs[-1].price and cur_trend == "uptrend":
            bos[i] = 1
        elif lows and close_i < lows[-1].price and cur_trend == "downtrend":
            bos[i] = -1

        # CHoCH: pergantian karakter tren — sinyal awal pembalikan
        #
        # DIPERBAIKI 10 Sep 2026 — versi lama KODE MATI, tidak pernah menyala
        # sekali pun dalam 100.000 bar.
        #
        # Versi lama membandingkan tren bar ini dengan tren bar SEBELUMNYA,
        # dan menuntut lompatan LANGSUNG uptrend <-> downtrend. Padahal
        # classify_trend selalu melewati "ranging" di antaranya:
        #
        #     downtrend -> ranging    3.411x
        #     ranging   -> uptrend    3.667x
        #     uptrend   -> downtrend      0x   <- yang dicari kode lama
        #     downtrend -> uptrend        0x   <- yang dicari kode lama
        #
        # Akibatnya `choch` selalu 0 dan `bars_since_choch` selalu -1, dan
        # bonus skor "CHoCH konfirmasi" di setups.py::_london_sweep tidak
        # pernah diberikan. Tidak berdampak pada sistem yang berjalan
        # (london_sweep nonaktif, momentum_fib tidak memakai CHoCH), tetapi
        # kolom yang selalu nol adalah jebakan untuk pengembangan berikutnya.
        #
        # Perbaikan: bandingkan dengan tren BERARAH TERAKHIR, bukan tren bar
        # sebelumnya - sehingga perjalanan lewat "ranging" tetap terhitung
        # sebagai pergantian karakter. Setelah diperbaiki: menyala 4.230x.
        #
        # CATATAN PEMAKAIAN: diuji sebagai filter untuk momentum_fib dan
        # HASILNYA NEGATIF (-0,135R, negatif di kedua paruh). CHoCH mencari
        # PEMBALIKAN sementara momentum_fib mencari KELANJUTAN - bertentangan
        # secara desain. Lihat docs/33-UJI-BOS-CHOCH.md.
        if cur_trend == "uptrend":
            if last_directional == "downtrend":
                choch[i] = 1
            last_directional = "uptrend"
        elif cur_trend == "downtrend":
            if last_directional == "uptrend":
                choch[i] = -1
            last_directional = "downtrend"

    out["last_swing_high"] = last_sh
    out["last_swing_low"] = last_sl
    out["trend"] = trend
    out["bos"] = bos
    out["choch"] = choch

    out["bars_since_bos"] = _bars_since(out["bos"] != 0)
    out["bars_since_choch"] = _bars_since(out["choch"] != 0)

    return out


def _bars_since(flag: pd.Series) -> pd.Series:
    """Jumlah bar sejak kondisi terakhir bernilai True."""
    idx = np.arange(len(flag))
    last_true = np.where(flag.values, idx, np.nan)
    last_true = pd.Series(last_true).ffill().values
    return pd.Series(idx - last_true, index=flag.index).fillna(-1).astype(int)
