"""
Triple-barrier labeling (López de Prado).

Untuk tiap kandidat entry, pasang tiga barrier:
  - Upper : entry + TP   -> label 1 bila tersentuh duluan
  - Lower : entry - SL   -> label 0 bila tersentuh duluan
  - Vertical: entry + N bar -> label 0 (timeout = trade tidak layak)

Label dibuat HANYA dari data setelah titik entry. Ini yang membedakan
meta-labeling dari prediksi harga: model tidak menebak harga, melainkan
menjawab "apakah setup ini akan berhasil?".

Arah trade mengikuti sinyal rule engine, bukan ditentukan model.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def triple_barrier(
    df: pd.DataFrame,
    sl_points: float = 4000,
    tp_points: float = 12000,
    max_bars: int = 48,
    point: float = 0.001,
    direction_col: str | None = None,
) -> pd.DataFrame:
    """
    Beri label tiap bar sebagai kandidat entry.

    direction_col: nama kolom berisi 'buy'/'sell'. Bila None, arah diambil
    dari trend_htf (uptrend -> buy, downtrend -> sell).

    Mengembalikan DataFrame dengan kolom:
      label      : 1 (TP duluan) / 0 (SL duluan atau timeout)
      exit_bars  : berapa bar sampai keluar
      outcome    : 'tp' / 'sl' / 'timeout'
    """
    n = len(df)
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values

    if direction_col and direction_col in df.columns:
        dirs = df[direction_col].values
    else:
        dirs = np.where(
            df["trend_htf"].values == "uptrend", "buy",
            np.where(df["trend_htf"].values == "downtrend", "sell", "none"),
        )

    sl_d = sl_points * point
    tp_d = tp_points * point

    labels = np.full(n, np.nan)
    exit_bars = np.full(n, np.nan)
    outcomes = np.array(["none"] * n, dtype=object)

    for i in range(n - max_bars - 1):
        d = dirs[i]
        if d not in ("buy", "sell"):
            continue

        # Entry di open bar berikutnya — konsisten dengan backtester
        entry = close[i]
        fut_h = high[i + 1 : i + 1 + max_bars]
        fut_l = low[i + 1 : i + 1 + max_bars]

        if d == "buy":
            tp_hit = fut_h >= entry + tp_d
            sl_hit = fut_l <= entry - sl_d
        else:
            tp_hit = fut_l <= entry - tp_d
            sl_hit = fut_h >= entry + sl_d

        i_tp = int(np.argmax(tp_hit)) if tp_hit.any() else 10**9
        i_sl = int(np.argmax(sl_hit)) if sl_hit.any() else 10**9

        if i_tp == 10**9 and i_sl == 10**9:
            labels[i] = 0.0
            exit_bars[i] = max_bars
            outcomes[i] = "timeout"
        elif i_tp < i_sl:
            labels[i] = 1.0
            exit_bars[i] = i_tp + 1
            outcomes[i] = "tp"
        else:
            # Sentuh keduanya di bar sama -> asumsi pesimis: SL duluan
            labels[i] = 0.0
            exit_bars[i] = i_sl + 1
            outcomes[i] = "sl"

    out = df.copy()
    out["label"] = labels
    out["exit_bars"] = exit_bars
    out["outcome"] = outcomes
    out["direction"] = dirs
    return out


def sample_weights(df: pd.DataFrame, max_bars: int = 48) -> np.ndarray:
    """
    Bobot sampel berdasar tumpang tindih label.

    Label yang periodenya bertumpang tindih membawa informasi yang sama,
    sehingga tidak boleh dihitung penuh — kalau tidak, model menganggap
    dirinya punya lebih banyak bukti independen daripada kenyataannya.

    Bobot = 1 / jumlah label yang tumpang tindih di periode itu.
    """
    n = len(df)
    exit_bars = df["exit_bars"].fillna(max_bars).values.astype(int)
    overlap = np.zeros(n)

    for i in range(n):
        if np.isnan(df["label"].values[i]):
            continue
        end = min(i + exit_bars[i], n)
        overlap[i:end] += 1

    w = np.ones(n)
    nz = overlap > 0
    w[nz] = 1.0 / overlap[nz]
    return w


if __name__ == "__main__":
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[2]
    df = pd.read_parquet(ROOT / "data/processed/XAUUSDm_M5_features.parquet")

    print("=" * 58)
    print("TRIPLE BARRIER LABELING")
    print("=" * 58)

    out = triple_barrier(df, sl_points=4000, tp_points=12000, max_bars=48)
    labeled = out.dropna(subset=["label"])

    print(f"\n  Total bar    : {len(out):,}")
    print(f"  Berlabel     : {len(labeled):,}")
    print(f"  Label 1 (TP) : {int(labeled['label'].sum()):,} "
          f"({labeled['label'].mean() * 100:.2f}%)")
    print(f"  Label 0      : {int((1 - labeled['label']).sum()):,}")

    print("\n  Distribusi outcome:")
    for k, v in labeled["outcome"].value_counts().items():
        print(f"    {k:<9}: {v:>7,} ({v / len(labeled) * 100:.1f}%)")

    out["weight"] = sample_weights(out)
    path = ROOT / "data/processed/XAUUSDm_M5_labeled.parquet"
    out.to_parquet(path, index=False)
    print(f"\n  Tersimpan: {path.name}")
