"""
Tes simulasi live (backtest/simulasi_live.py).

Fitur bar yang sedang terbentuk dihitung inkremental supaya simulasi
berbulan-bulan tetap cepat. Tes ini menjaga hasilnya IDENTIK dengan
pipeline indikator asli (add_all + add_extended) - kalau rumus indikator
berubah, tes ini yang pertama gagal.

    python tests/test_simulasi_live.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.simulasi_live import FiturBarBerjalan  # noqa: E402
from src.features.indicators import add_all, add_extended  # noqa: E402
from src.strategy.setups import hitung_skor100  # noqa: E402


def _data(n: int = 900, seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    close = 4000 + np.cumsum(rng.normal(0, 1.2, n))
    open_ = np.r_[close[0], close[:-1]] + rng.normal(0, 0.2, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.8, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.8, n))
    df = pd.DataFrame({
        "time_utc": pd.date_range("2026-08-03", periods=n, freq="5min"),
        "open": open_, "high": high, "low": low, "close": close,
        "tick_volume": 100, "spread": 260,
    })
    feat = add_extended(add_all(df))
    feat["trend_htf"] = "uptrend"
    feat["mom_24_q85"] = 1.0
    return df, feat


def test_fitur_bar_berjalan_identik_dengan_pipeline():
    df, feat = _data()
    fitur = FiturBarBerjalan(feat)
    rng = np.random.default_rng(1)
    kolom = ("atr", "mom_24", "adx", "fib_position", "atr_percentile", "stoch_k")

    for _ in range(60):
        k = int(rng.integers(650, len(df)))
        o = float(df.at[k, "open"])
        ph = o + abs(rng.normal(0, 2))
        pl = o - abs(rng.normal(0, 2))
        pc = float(rng.uniform(pl, ph))

        cepat = fitur.hitung(k, ph, pl, pc)

        parsial = {"time_utc": df.at[k, "time_utc"], "open": o, "high": max(o, ph),
                   "low": min(o, pl), "close": pc, "tick_volume": 100, "spread": 260}
        tail = pd.concat([df.iloc[k - 600:k], pd.DataFrame([parsial])], ignore_index=True)
        acuan = add_extended(add_all(tail)).iloc[-1].copy()
        acuan["trend_htf"], acuan["mom_24_q85"] = "uptrend", 1.0

        for c in kolom:
            selisih = abs(getattr(cepat, c) - acuan[c])
            assert selisih < 1e-8, (k, c, getattr(cepat, c), acuan[c])
        for arah in ("buy", "sell"):
            assert hitung_skor100(cepat, arah) == hitung_skor100(acuan, arah), (k, arah)


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = []
    for fn in tests:
        try:
            fn()
        except AssertionError as e:
            failed.append((fn.__name__, f"assert gagal: {e}"))
        except Exception as e:  # noqa: BLE001
            failed.append((fn.__name__, f"{type(e).__name__}: {e}"))
        else:
            print(f"  ok    {fn.__name__}")
    for name, why in failed:
        print(f"  GAGAL {name} -> {why}")
    print(f"\n{len(tests) - len(failed)}/{len(tests)} lolos")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
