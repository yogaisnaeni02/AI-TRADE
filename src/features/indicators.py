"""
Indikator teknikal.

ATURAN MUTLAK: setiap indikator di sini menghasilkan nilai yang HANYA
memakai data sampai bar t-1. Pemanggil bertanggung jawab melakukan
shift(1) sebelum memakainya sebagai fitur keputusan di bar t.

Fungsi di modul ini TIDAK melakukan shift sendiri — supaya bisa dipakai
juga untuk perhitungan yang memang butuh nilai bar berjalan (misalnya
menghitung ATR untuk menentukan SL saat entry sudah diputuskan).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range — fondasi seluruh perhitungan risiko."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)

    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    # Wilder smoothing (bukan SMA biasa) — standar untuk ATR
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """ADX + DI. ADX > 25 umumnya menandakan pasar trending."""
    high, low = df["high"], df["low"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index
    )

    atr_val = atr(df, period)
    alpha = 1 / period

    plus_di = 100 * plus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_val
    minus_di = 100 * minus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_val

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val = dx.ewm(alpha=alpha, adjust=False, min_periods=period).mean()

    return pd.DataFrame({"adx": adx_val, "plus_di": plus_di, "minus_di": minus_di})


def bollinger(close: pd.Series, period: int = 20, std_mult: float = 2.0) -> pd.DataFrame:
    mid = close.rolling(period, min_periods=period).mean()
    std = close.rolling(period, min_periods=period).std()

    upper = mid + std * std_mult
    lower = mid - std * std_mult
    width = (upper - lower) / mid.replace(0, np.nan)
    pct_b = (close - lower) / (upper - lower).replace(0, np.nan)

    return pd.DataFrame(
        {"bb_mid": mid, "bb_upper": upper, "bb_lower": lower,
         "bb_width": width, "bb_pct_b": pct_b}
    )


def vwap_session(df: pd.DataFrame, session_col: str = "session_date") -> pd.Series:
    """
    VWAP yang di-reset tiap hari trading.

    Butuh kolom penanda hari sesi; forex tidak reset di tengah malam kalender,
    jadi pengelompokan disediakan pemanggil (lihat sessions.py).
    """
    typical = (df["high"] + df["low"] + df["close"]) / 3
    pv = typical * df["tick_volume"]

    cum_pv = pv.groupby(df[session_col]).cumsum()
    cum_vol = df["tick_volume"].groupby(df[session_col]).cumsum()

    return cum_pv / cum_vol.replace(0, np.nan)


def add_all(df: pd.DataFrame, config: dict | None = None) -> pd.DataFrame:
    """Tambahkan seluruh indikator standar ke dataframe."""
    out = df.copy()

    out["atr"] = atr(out, 14)
    out["atr_pct"] = out["atr"] / out["close"]

    for p in (20, 50, 200):
        out[f"ema{p}"] = ema(out["close"], p)

    out["rsi"] = rsi(out["close"], 14)

    adx_df = adx(out, 14)
    out[["adx", "plus_di", "minus_di"]] = adx_df

    bb = bollinger(out["close"], 20, 2.0)
    out[bb.columns.tolist()] = bb

    # Persentil ATR dalam 200 bar terakhir — dipakai untuk filter regime.
    # Volatilitas terlalu rendah: spread mendominasi. Terlalu tinggi:
    # biasanya berita.
    out["atr_percentile"] = out["atr"].rolling(200, min_periods=50).rank(pct=True)

    return out


# ---------------------------------------------------------------------------
# Indikator tambahan — diuji untuk mencari daya prediksi
# ---------------------------------------------------------------------------

def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD: selisih dua EMA, plus garis sinyal dan histogram."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    line = ema_fast - ema_slow
    sig = line.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame({"macd": line, "macd_signal": sig, "macd_hist": line - sig})


def stochastic(df: pd.DataFrame, k: int = 14, d: int = 3) -> pd.DataFrame:
    """Stochastic oscillator — posisi close dalam range N bar."""
    low_n = df["low"].rolling(k, min_periods=k).min()
    high_n = df["high"].rolling(k, min_periods=k).max()
    pct_k = 100 * (df["close"] - low_n) / (high_n - low_n).replace(0, np.nan)
    return pd.DataFrame({"stoch_k": pct_k, "stoch_d": pct_k.rolling(d).mean()})


def fibonacci_levels(df: pd.DataFrame, lookback: int = 100) -> pd.DataFrame:
    """
    Posisi harga relatif terhadap retracement Fibonacci swing terakhir.

    fib_position 0 = di swing low, 1 = di swing high. Zona 0.382-0.618
    adalah area retracement klasik tempat harga sering berbalik.
    """
    hi = df["high"].rolling(lookback, min_periods=20).max()
    lo = df["low"].rolling(lookback, min_periods=20).min()
    rng = (hi - lo).replace(0, np.nan)
    pos = (df["close"] - lo) / rng

    return pd.DataFrame({
        "fib_position": pos,
        "fib_range_atr": rng / atr(df, 14).replace(0, np.nan),
        # Jarak ke level-level kunci; kecil = harga sedang di level itu
        "fib_dist_382": (pos - 0.382).abs(),
        "fib_dist_500": (pos - 0.500).abs(),
        "fib_dist_618": (pos - 0.618).abs(),
        "fib_in_golden": ((pos >= 0.382) & (pos <= 0.618)).astype(int),
    })


def momentum_features(df: pd.DataFrame) -> pd.DataFrame:
    """Momentum multi-horizon, dinormalisasi ATR agar sebanding antar waktu."""
    a = atr(df, 14).replace(0, np.nan)
    out = {}
    for n in (3, 6, 12, 24):
        out[f"mom_{n}"] = (df["close"] - df["close"].shift(n)) / a
    # Percepatan: momentum yang sedang menguat atau melemah
    out["mom_accel"] = out["mom_3"] - out["mom_6"]
    return pd.DataFrame(out)


def candle_features(df: pd.DataFrame) -> pd.DataFrame:
    """Bentuk candle — body, wick, dan posisi close dalam range."""
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    body = (df["close"] - df["open"]).abs()
    upper = df["high"] - df[["open", "close"]].max(axis=1)
    lower = df[["open", "close"]].min(axis=1) - df["low"]

    return pd.DataFrame({
        "body_ratio": body / rng,
        "upper_wick_ratio": upper / rng,
        "lower_wick_ratio": lower / rng,
        "close_position": (df["close"] - df["low"]) / rng,
        "is_bullish": (df["close"] > df["open"]).astype(int),
    })


def volume_features(df: pd.DataFrame) -> pd.DataFrame:
    """Tick volume relatif — proksi partisipasi pasar."""
    v = df["tick_volume"]
    ma = v.rolling(20, min_periods=10).mean().replace(0, np.nan)
    return pd.DataFrame({
        "vol_ratio": v / ma,
        "vol_trend": v.rolling(5).mean() / ma,
    })


def add_extended(df: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan seluruh indikator lanjutan di atas indikator dasar."""
    out = df.copy()
    for frame in (
        macd(out["close"]),
        stochastic(out),
        fibonacci_levels(out),
        momentum_features(out),
        candle_features(out),
        volume_features(out),
    ):
        out[frame.columns.tolist()] = frame

    # Turunan MACD yang lebih informatif daripada nilai mentahnya
    a = out["atr"].replace(0, np.nan) if "atr" in out.columns else atr(out, 14)
    out["macd_hist_atr"] = out["macd_hist"] / a
    out["macd_cross_up"] = (
        (out["macd"] > out["macd_signal"])
        & (out["macd"].shift(1) <= out["macd_signal"].shift(1))
    ).astype(int)
    out["macd_cross_dn"] = (
        (out["macd"] < out["macd_signal"])
        & (out["macd"].shift(1) >= out["macd_signal"].shift(1))
    ).astype(int)

    return out
