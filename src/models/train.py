"""
Training model meta-labeling dengan walk-forward validation.

Model TIDAK memprediksi harga. Model memprediksi probabilitas bahwa sebuah
setup akan mencapai TP sebelum SL — lalu probabilitas itu dipakai sebagai
confidence untuk menyaring sinyal dan (nanti) mengatur ukuran lot.

Pencegahan overfitting yang diterapkan:
  - Walk-forward, bukan random split
  - Purge gap antara train dan test (mencegah kebocoran lewat label
    yang periodenya tumpang tindih)
  - Kompleksitas model dibatasi (max_depth kecil)
  - Sample weight berdasar tumpang tindih label
  - Evaluasi memakai metrik trading, bukan hanya akurasi
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import lightgbm as lgb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "data" / "models"

# Kolom yang TIDAK boleh jadi fitur: hasil masa depan, harga mentah,
# atau metadata. Harga mentah dibuang karena nilainya bergeser terus
# (gold $1800 -> $4400) sehingga model tak bisa menggeneralisasi.
EXCLUDE = {
    "label", "exit_bars", "outcome", "direction", "weight",
    "time_utc", "time_server", "session_date", "session", "trend", "trend_htf",
    "h1_trend", "h4_trend",
    "open", "high", "low", "close", "real_volume",
    "ema20", "ema50", "ema200", "bb_mid", "bb_upper", "bb_lower",
    "asia_high", "asia_low", "sweep_extreme", "last_swing_high", "last_swing_low",
    "h1_close", "h1_ema50", "h1_swing_high", "h1_swing_low",
    "h4_close", "h4_ema50", "h4_swing_high", "h4_swing_low",
    "macd", "macd_signal", "macd_hist", "vwap",
    "mom_24_q85",
}


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Pilih fitur numerik yang aman, plus encoding beberapa kolom kategorik."""
    out = df.copy()

    # Kategorik -> numerik, dipakai model sebagai konteks
    out["is_uptrend_htf"] = (out["trend_htf"] == "uptrend").astype(int)
    out["is_downtrend_htf"] = (out["trend_htf"] == "downtrend").astype(int)
    out["is_london"] = out["session"].isin(["london_open", "london_ny"]).astype(int)
    out["is_ny"] = (out["session"] == "ny_afternoon").astype(int)
    out["is_asia"] = (out["session"] == "asia").astype(int)
    out["is_buy"] = (out["direction"] == "buy").astype(int)

    feats = [
        c for c in out.columns
        if c not in EXCLUDE and pd.api.types.is_numeric_dtype(out[c])
    ]
    return out, feats


def purged_walk_forward(
    df: pd.DataFrame,
    feats: list[str],
    n_folds: int = 5,
    purge_bars: int = 100,
    params: Optional[dict] = None,
) -> tuple[list[dict], list]:
    """
    Walk-forward dengan purge gap.

    Fold i: train pada semua data sebelum test, dipisahkan purge_bars.
    Purge mencegah label train yang periodenya menyentuh periode test.
    """
    default = {
        "objective": "binary",
        "metric": "auc",
        "learning_rate": 0.03,
        "num_leaves": 15,          # dibatasi — data finansial mudah overfit
        "max_depth": 4,
        "min_child_samples": 200,
        "subsample": 0.8,
        "subsample_freq": 1,
        "colsample_bytree": 0.7,
        "reg_alpha": 1.0,
        "reg_lambda": 1.0,
        "verbose": -1,
        "seed": 42,
    }
    p = {**default, **(params or {})}

    d = df.dropna(subset=["label"]).reset_index(drop=True)
    n = len(d)
    fold_size = n // (n_folds + 1)

    results, models = [], []

    for i in range(n_folds):
        train_end = fold_size * (i + 1)
        test_start = train_end + purge_bars
        test_end = min(test_start + fold_size, n)

        if test_start >= n or test_end - test_start < 200:
            continue

        tr = d.iloc[:train_end]
        te = d.iloc[test_start:test_end]

        X_tr = tr[feats].replace([np.inf, -np.inf], np.nan)
        X_te = te[feats].replace([np.inf, -np.inf], np.nan)

        ds_tr = lgb.Dataset(X_tr, label=tr["label"], weight=tr.get("weight"))
        ds_te = lgb.Dataset(X_te, label=te["label"], reference=ds_tr)

        model = lgb.train(
            p, ds_tr,
            num_boost_round=400,
            valid_sets=[ds_te],
            callbacks=[lgb.early_stopping(40, verbose=False)],
        )

        prob = model.predict(X_te, num_iteration=model.best_iteration)

        results.append({
            "fold": i + 1,
            "train_n": len(tr),
            "test_n": len(te),
            "period": f"{te['time_utc'].min():%Y-%m} -> {te['time_utc'].max():%Y-%m}",
            "base_rate": te["label"].mean(),
            "prob": prob,
            "y": te["label"].values,
            "best_iter": model.best_iteration,
        })
        models.append(model)

    return results, models


def evaluate_thresholds(
    results: list[dict],
    thresholds: tuple[float, ...] = (0.25, 0.30, 0.35, 0.40, 0.45, 0.50),
    sl_points: float = 4000,
    tp_points: float = 12000,
    spread: float = 260,
) -> pd.DataFrame:
    """
    Evaluasi tiap threshold dengan metrik TRADING, bukan akurasi.

    Yang dicari: threshold yang menaikkan winrate cukup jauh di atas
    breakeven, dan konsisten di semua fold.
    """
    rows = []
    for th in thresholds:
        per_fold = []
        for r in results:
            sel = r["prob"] >= th
            if sel.sum() < 30:
                per_fold.append(None)
                continue
            wr = r["y"][sel].mean()
            e = (wr * (tp_points - spread) - (1 - wr) * (sl_points + spread)) / sl_points
            per_fold.append((wr, e, int(sel.sum())))

        valid = [x for x in per_fold if x]
        if not valid:
            continue

        rows.append({
            "threshold": th,
            "avg_winrate": np.mean([v[0] for v in valid]) * 100,
            "avg_expectancy": np.mean([v[1] for v in valid]),
            "folds_positive": sum(1 for v in valid if v[1] > 0),
            "folds_valid": len(valid),
            "total_signals": sum(v[2] for v in valid),
        })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    print("=" * 62)
    print("TRAINING META-LABELING MODEL")
    print("=" * 62)

    df = pd.read_parquet(ROOT / "data/processed/XAUUSDm_M5_labeled.parquet")
    df, feats = build_features(df)

    print(f"\n  Sampel berlabel : {df['label'].notna().sum():,}")
    print(f"  Fitur           : {len(feats)}")
    print(f"  Baseline (TP)   : {df['label'].mean() * 100:.2f}%")

    print("\n  Melatih walk-forward 5 fold...")
    results, models = purged_walk_forward(df, feats, n_folds=5)

    print(f"\n  {'fold':<6} {'periode':<20} {'test n':>7} {'base':>7} {'iter':>6}")
    print("  " + "-" * 52)
    for r in results:
        print(f"  {r['fold']:<6} {r['period']:<20} {r['test_n']:>7,} "
              f"{r['base_rate']*100:>6.1f}% {r['best_iter']:>6}")

    print("\n" + "=" * 62)
    print("EVALUASI THRESHOLD (breakeven WR = 25.4%)")
    print("=" * 62)

    ev = evaluate_thresholds(results)
    print(f"\n  {'thresh':>7} {'WR':>7} {'E(R)':>9} {'fold+':>7} {'sinyal':>8}")
    print("  " + "-" * 44)
    for _, r in ev.iterrows():
        print(f"  {r['threshold']:>7.2f} {r['avg_winrate']:>6.1f}% "
              f"{r['avg_expectancy']:>+9.3f} {int(r['folds_positive'])}/{int(r['folds_valid'])} "
              f"{int(r['total_signals']):>8,}")

    if not ev.empty:
        best = ev.loc[ev["avg_expectancy"].idxmax()]
        print(f"\n  >>> Threshold terbaik: {best['threshold']:.2f}")
        print(f"      WR {best['avg_winrate']:.1f}% | E {best['avg_expectancy']:+.3f}R "
              f"| {int(best['folds_positive'])}/{int(best['folds_valid'])} fold positif")

    # Feature importance dari fold terakhir
    if models:
        imp = pd.DataFrame({
            "feature": models[-1].feature_name(),
            "gain": models[-1].feature_importance("gain"),
        }).sort_values("gain", ascending=False)
        print("\n  15 fitur terpenting:")
        for _, r in imp.head(15).iterrows():
            print(f"    {r['feature']:<24} {r['gain']:>12,.0f}")

        # PERINGATAN — model yang disimpan di sini TIDAK LAYAK PRODUKSI.
        #
        # `models[-1]` adalah fold TERAKHIR walk-forward, yang dilatih pada
        # ~83% data (2025-04-11 s/d 2026-06-08 dari data berakhir 2026-09-09).
        # Artinya model ini tidak punya periode uji yang bersih: mengukurnya
        # pada data proyek ini hampir pasti menghasilkan angka BOCOR.
        #
        # Terbukti 10 Sep 2026 saat dicoba sebagai filter momentum_fib:
        #   periode yang model sudah lihat : +0,1376 -> +0,3651  (terlihat hebat)
        #   periode benar-benar bersih     : +0,1079 -> +0,0294  (MEMPERBURUK)
        #
        # Model disimpan hanya untuk inspeksi/feature importance. JANGAN
        # dimuat oleh bot atau backtest. Bila suatu saat ML benar-benar
        # dipakai, latih ulang pada SELURUH data setelah walk-forward
        # memutuskan modelnya layak - dan model ini TIDAK layak
        # (AUC out-of-sample 0,509 = setara acak).
        #
        # Lihat docs/40-STATUS-MODEL-ML.md.
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        models[-1].save_model(str(MODEL_DIR / "meta_model.txt"))
        imp.to_csv(MODEL_DIR / "feature_importance.csv", index=False)
        print(f"\n  Model tersimpan: {MODEL_DIR / 'meta_model.txt'}")
        print("  PERINGATAN: model ini fold terakhir (dilatih ~83% data),")
        print("  TIDAK punya periode uji bersih. Jangan dipakai produksi.")
        print("  Lihat docs/40-STATUS-MODEL-ML.md")
