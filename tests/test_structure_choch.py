"""
Tes regresi CHoCH — kolom yang dulu diam-diam selalu nol.

Dijalankan tanpa pytest dan tanpa MetaTrader5:

    python tests/test_structure_choch.py

BUG YANG DIJAGA (10 Sep 2026)
-----------------------------
`add_structure` dulu menuntut pergantian LANGSUNG uptrend <-> downtrend
dalam satu bar untuk menandai CHoCH. classify_trend selalu melewati
"ranging" di antaranya, jadi kedua cabang itu kode mati: `choch` bernilai 0
di seluruh 100.000 bar dan `bars_since_choch` bernilai -1.

Kolom yang selalu konstan tidak pernah melempar error - ia hanya membuat
setiap pemakainya diam-diam tidak berfungsi. Tes ini memastikan kolomnya
benar-benar hidup.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.strategy.structure import add_structure  # noqa: E402


def _trending_series(n: int = 900) -> pd.DataFrame:
    """Harga yang naik lalu turun lalu naik lagi - wajib memicu CHoCH."""
    seg = n // 3
    up = np.linspace(2000, 2100, seg)
    down = np.linspace(2100, 1980, seg)
    up2 = np.linspace(1980, 2120, n - 2 * seg)
    close = np.concatenate([up, down, up2])

    # Riak kecil supaya swing point terbentuk, bukan garis lurus sempurna
    close = close + np.sin(np.arange(n) * 0.7) * 3.0

    return pd.DataFrame({
        "time_utc": pd.date_range("2026-01-01", periods=n, freq="5min"),
        "open": close - 0.2,
        "high": close + 1.5,
        "low": close - 1.5,
        "close": close,
    })


def test_choch_fires_on_trend_reversal() -> None:
    out = add_structure(_trending_series())
    fired = int((out["choch"] != 0).sum())

    assert fired > 0, (
        "CHoCH tidak pernah menyala pada data yang jelas berbalik arah — "
        "ini bug lama yang kembali: pergantian tren selalu lewat 'ranging', "
        "jadi syarat uptrend->downtrend langsung tidak pernah terpenuhi."
    )

    assert set(out["choch"].unique()) <= {-1, 0, 1}
    print(f"  CHoCH menyala {fired}x — OK")


def test_bars_since_choch_is_alive() -> None:
    out = add_structure(_trending_series())
    bsc = out["bars_since_choch"]

    assert bsc.nunique() > 1, (
        "bars_since_choch konstan — pertanda choch tidak pernah menyala."
    )
    assert (bsc[bsc >= 0] >= 0).all()
    print(f"  bars_since_choch punya {bsc.nunique()} nilai berbeda — OK")


def test_choch_direction_follows_reversal() -> None:
    """CHoCH bullish hanya muncul saat tren berarah terakhir adalah down."""
    out = add_structure(_trending_series())

    last_dir = None
    for t, c in zip(out["trend"], out["choch"]):
        if c == 1:
            assert last_dir == "downtrend", (
                "CHoCH bullish muncul tanpa didahului downtrend"
            )
        elif c == -1:
            assert last_dir == "uptrend", (
                "CHoCH bearish muncul tanpa didahului uptrend"
            )
        if t in ("uptrend", "downtrend"):
            last_dir = t
    print("  arah CHoCH konsisten dengan tren sebelumnya — OK")


def test_ranging_between_trends_still_counts() -> None:
    """Perjalanan uptrend -> ranging -> downtrend tetap dihitung CHoCH.

    Ini inti perbaikannya: versi lama melewatkan kasus ini, dan kasus ini
    adalah SATU-SATUNYA cara tren berbalik pada data nyata.
    """
    out = add_structure(_trending_series())

    seen_ranging_between = False
    last_dir = None
    saw_ranging = False
    for t, c in zip(out["trend"], out["choch"]):
        if t == "ranging":
            saw_ranging = True
        elif t in ("uptrend", "downtrend"):
            if last_dir and t != last_dir and saw_ranging:
                assert c != 0, (
                    "pergantian tren yang melewati 'ranging' tidak ditandai "
                    "CHoCH — persis bug yang diperbaiki 10 Sep 2026"
                )
                seen_ranging_between = True
            if t != last_dir:
                saw_ranging = False
            last_dir = t

    assert seen_ranging_between, (
        "data uji tidak menghasilkan pergantian tren lewat ranging"
    )
    print("  pergantian lewat 'ranging' tertangkap — OK")


if __name__ == "__main__":
    tests = [
        test_choch_fires_on_trend_reversal,
        test_bars_since_choch_is_alive,
        test_choch_direction_follows_reversal,
        test_ranging_between_trends_still_counts,
    ]
    for fn in tests:
        print(f"{fn.__name__}:")
        fn()
    print(f"\n{len(tests)} tes CHoCH lulus.")
