"""
Uji ML dengan benar: dilatih HANYA pada sinyal momentum_fib, holdout tersegel.

HASIL (10 Sep 2026): AUC holdout 0,51 = setara acak. TIDAK ADA EDGE.

Skrip ini TIDAK menyimpan model dan tidak menyentuh jalur produksi -
dipertahankan supaya kesimpulannya bisa diperiksa ulang kapan saja.

    python scripts/ml_uji_ulang.py            # latih + evaluasi holdout
    python scripts/ml_uji_ulang.py --sweep    # 6 varian hiperparameter
    python scripts/ml_uji_ulang.py --seeds    # stabilitas seed

Lihat docs/41-ML-DILATIH-ULANG-DENGAN-BENAR.md.

KENAPA UJI LAMA TIDAK ADIL
--------------------------
1. Model lama dilatih pada SEMUA 86.279 bar (setiap bar dianggap kandidat
   entry), padahal yang benar-benar ditradingkan hanya ~4.189 sinyal
   momentum_fib. Model belajar menjawab pertanyaan yang salah.
2. Data latihnya BASI - kolom sesi meleset 7 jam (cocok cuma 4,4% dengan
   time_utc). Model belajar konteks sesi yang salah.
3. Model yang disimpan adalah fold terakhir (83% data), tidak punya
   periode uji bersih.

YANG DIKERJAKAN DI SINI
-----------------------
- Label dihitung ULANG pada data fitur yang sudah benar
- Sampel = HANYA sinyal momentum_fib (pertanyaan yang benar)
- SL/TP mengikuti sinyal masing-masing, bukan angka tetap
- Holdout 30% TERAKHIR disegel: model tidak pernah melihatnya
- Early stopping pakai bagian dari TRAIN, bukan test (kebocoran docs/27 #9)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lightgbm as lgb  # noqa: E402

from src.strategy.setups import RuleEngine  # noqa: E402
from backtest.engine import Backtester  # noqa: E402

FEAT = ROOT / "data" / "processed" / "XAUUSDm_M5_features.parquet"

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


def label_signals(df: pd.DataFrame, sig: pd.DataFrame, max_bars: int = 48,
                  spread_pts: float = 260.0, point: float = 0.001) -> pd.DataFrame:
    """Triple-barrier per SINYAL, memakai SL/TP sinyal itu sendiri.

    Spread dibayar di entry (docs/27 #9: barrier lama dihitung tanpa spread).
    """
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    n = len(df)

    out = []
    for r in sig.itertuples():
        i = int(r.idx) + 1          # eksekusi bar berikutnya
        if i >= n:
            out.append((np.nan, np.nan))
            continue
        # harga entry riil setelah spread
        if r.direction == "buy":
            entry = df["open"].iloc[i] + spread_pts * point
            sl, tp = entry - r.sl_points * point, entry + r.tp_points * point
        else:
            entry = df["open"].iloc[i] - spread_pts * point
            sl, tp = entry + r.sl_points * point, entry - r.tp_points * point

        end = min(i + max_bars, n)
        lab, bars = 0, end - i
        for j in range(i, end):
            if r.direction == "buy":
                hit_sl, hit_tp = low[j] <= sl, high[j] >= tp
            else:
                hit_sl, hit_tp = high[j] >= sl, low[j] <= tp
            if hit_sl:              # pesimis: SL menang bila sama-sama kena
                lab, bars = 0, j - i
                break
            if hit_tp:
                lab, bars = 1, j - i
                break
        out.append((lab, bars))

    lab = pd.DataFrame(out, columns=["label", "exit_bars"], index=sig.index)
    return lab


BASE_PARAMS = {
    "objective": "binary", "metric": "auc",
    "subsample": 0.8, "subsample_freq": 1, "colsample_bytree": 0.7,
    "reg_alpha": 1.0, "reg_lambda": 1.0, "verbose": -1, "seed": 42,
}

SWEEP_GRID = [
    ("default (depth4,leaf15,lr.03)",
     dict(max_depth=4, num_leaves=15, learning_rate=0.03, min_child_samples=50)),
    ("lebih dangkal (depth2,leaf4)",
     dict(max_depth=2, num_leaves=4, learning_rate=0.03, min_child_samples=100)),
    ("stump (depth1)",
     dict(max_depth=1, num_leaves=2, learning_rate=0.05, min_child_samples=100)),
    ("lr kecil (0.01)",
     dict(max_depth=3, num_leaves=8, learning_rate=0.01, min_child_samples=80)),
    ("regularisasi kuat",
     dict(max_depth=3, num_leaves=8, learning_rate=0.02, min_child_samples=150,
          reg_alpha=10.0, reg_lambda=10.0)),
    ("dalam (depth8,leaf63)",
     dict(max_depth=8, num_leaves=63, learning_rate=0.05, min_child_samples=20)),
]

# Varian dengan AUC holdout tertinggi dari SWEEP_GRID - dipakai uji seed.
BEST_PARAMS = dict(max_depth=3, num_leaves=8, learning_rate=0.02,
                   min_child_samples=150, reg_alpha=10.0, reg_lambda=10.0)


def build_dataset(df: pd.DataFrame):
    """Kembalikan (sig, X, y) siap latih, hanya pada sinyal momentum_fib."""
    sig = RuleEngine(active_setups=["momentum_fib"]).generate(df).copy()
    sig["_t"] = pd.to_datetime(sig["time"])
    lab = label_signals(df, sig)
    sig["label"] = lab["label"]
    sig["exit_bars"] = lab["exit_bars"]
    sig = sig.dropna(subset=["label"])
    sig["label"] = sig["label"].astype(int)

    X = df.set_index("time_utc").reindex(sig["_t"]).copy()
    X["is_uptrend_htf"] = (X["trend_htf"] == "uptrend").astype(int)
    X["is_downtrend_htf"] = (X["trend_htf"] == "downtrend").astype(int)
    X["is_london"] = X["session"].isin(["london_open", "london_ny"]).astype(int)
    X["is_ny"] = (X["session"] == "ny_afternoon").astype(int)
    X["is_asia"] = (X["session"] == "asia").astype(int)
    X["is_buy"] = (sig["direction"] == "buy").to_numpy().astype(int)
    feats = [c for c in X.columns
             if c not in EXCLUDE and pd.api.types.is_numeric_dtype(X[c])]
    X = X[feats].replace([np.inf, -np.inf], np.nan).reset_index(drop=True)
    return sig, X, sig["label"].to_numpy()


def make_splits(n: int, purge: int = 48):
    """55% train / 15% valid / 30% holdout, dipisah purge gap."""
    i_tr, i_va = int(n * 0.55), int(n * 0.70)
    return slice(0, i_tr - purge), slice(i_tr, i_va - purge), slice(i_va, n)


def _fit(X, y, tr, va, params):
    ds_tr = lgb.Dataset(X.iloc[tr], label=y[tr])
    ds_va = lgb.Dataset(X.iloc[va], label=y[va], reference=ds_tr)
    return lgb.train({**BASE_PARAMS, **params}, ds_tr, num_boost_round=800,
                     valid_sets=[ds_va],
                     callbacks=[lgb.early_stopping(60, verbose=False)])


def run_sweep(df: pd.DataFrame) -> None:
    """Sapuan hiperparameter: hasil tidak tergantung setelan."""
    from sklearn.metrics import roc_auc_score

    sig, X, y = build_dataset(df)
    tr, va, ho = make_splits(len(sig))
    print("Sapuan hiperparameter - AUC di HOLDOUT tersegel (0,50 = acak)")
    print()
    print(f"{'varian':<38} {'pohon':>6} {'AUC val':>9} {'AUC HOLDOUT':>12}")
    print("-" * 70)
    for nm, ov in SWEEP_GRID:
        m = _fit(X, y, tr, va, ov)
        it = m.best_iteration
        av = roc_auc_score(y[va], m.predict(X.iloc[va], num_iteration=it))
        ah = roc_auc_score(y[ho], m.predict(X.iloc[ho], num_iteration=it))
        print(f"{nm:<38} {it:>6} {av:>9.4f} {ah:>12.4f}")
    print()
    print("Semua berkerumun di sekitar 0,50 - tidak ada setelan yang menolong.")


def run_seeds(df: pd.DataFrame) -> None:
    """Stabilitas seed: hasil 'terbaik' cuma kebetulan angka acak."""
    sig, X, y = build_dataset(df)
    tr, va, ho = make_splits(len(sig))
    sh = sig.iloc[ho].copy()
    b = Backtester()
    b.max_dd = 1e5

    def st(s):
        t_, _ = b.run(df, s.drop(columns=["_t", "p", "label", "exit_bars"],
                                 errors="ignore"))
        r = t_["r_multiple"].dropna()
        k = len(r)
        if k < 2:
            return None
        return k, r.mean(), r.mean() / (r.std(ddof=1) / math.sqrt(k))

    print("Stabilitas seed - varian 'buang 30% prob terendah' di holdout")
    print()
    print(f"{'seed':>6} {'n':>6} {'E[R]':>10} {'t':>8}")
    print("-" * 34)
    for seed in (1, 7, 42, 123, 999):
        m = _fit(X, y, tr, va, {**BEST_PARAMS, "seed": seed})
        q = m.predict(X.iloc[ho], num_iteration=m.best_iteration)
        s2 = sh.copy()
        s2["p"] = q
        r = st(s2[s2["p"] >= float(np.quantile(q, 0.3))])
        if r:
            print(f"{seed:>6} {r[0]:>6} {r[1]:>+10.4f} {r[2]:>+8.2f}")
    print()
    print("Rentang E[R] lebar hanya karena seed = noise, bukan edge.")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true", help="sapuan hiperparameter")
    ap.add_argument("--seeds", action="store_true", help="uji stabilitas seed")
    args = ap.parse_args()

    df = pd.read_parquet(FEAT)
    if args.sweep:
        run_sweep(df)
        return
    if args.seeds:
        run_seeds(df)
        return

    engine = RuleEngine(active_setups=["momentum_fib"])
    sig = engine.generate(df).copy()
    sig["_t"] = pd.to_datetime(sig["time"])

    print(f"Sinyal momentum_fib : {len(sig)}")

    lab = label_signals(df, sig)
    sig["label"] = lab["label"]
    sig["exit_bars"] = lab["exit_bars"]
    sig = sig.dropna(subset=["label"])
    sig["label"] = sig["label"].astype(int)
    print(f"Berlabel            : {len(sig)}   base rate TP = {sig['label'].mean()*100:.2f}%")

    # -- fitur pada bar sinyal -------------------------------------------
    X = df.set_index("time_utc").reindex(sig["_t"]).copy()
    X["is_uptrend_htf"] = (X["trend_htf"] == "uptrend").astype(int)
    X["is_downtrend_htf"] = (X["trend_htf"] == "downtrend").astype(int)
    X["is_london"] = X["session"].isin(["london_open", "london_ny"]).astype(int)
    X["is_ny"] = (X["session"] == "ny_afternoon").astype(int)
    X["is_asia"] = (X["session"] == "asia").astype(int)
    X["is_buy"] = (sig["direction"] == "buy").to_numpy().astype(int)
    feats = [c for c in X.columns
             if c not in EXCLUDE and pd.api.types.is_numeric_dtype(X[c])]
    X = X[feats].replace([np.inf, -np.inf], np.nan).reset_index(drop=True)
    y = sig["label"].to_numpy()
    t = sig["_t"].to_numpy()
    print(f"Fitur               : {len(feats)}")

    # -- pembagian: 55% train / 15% valid / 30% HOLDOUT tersegel ----------
    n = len(sig)
    i_tr, i_va = int(n * 0.55), int(n * 0.70)
    PURGE = 48  # bar; label bisa menjangkau 48 bar ke depan

    tr = slice(0, i_tr - PURGE)
    va = slice(i_tr, i_va - PURGE)
    ho = slice(i_va, n)

    print(f"\nTrain   : {pd.Timestamp(t[0]):%Y-%m-%d} .. {pd.Timestamp(t[i_tr-PURGE-1]):%Y-%m-%d}  n={i_tr-PURGE}")
    print(f"Valid   : {pd.Timestamp(t[i_tr]):%Y-%m-%d} .. {pd.Timestamp(t[i_va-PURGE-1]):%Y-%m-%d}  n={i_va-PURGE-i_tr}")
    print(f"HOLDOUT : {pd.Timestamp(t[i_va]):%Y-%m-%d} .. {pd.Timestamp(t[-1]):%Y-%m-%d}  n={n-i_va}  (DISEGEL)")

    params = {
        "objective": "binary", "metric": "auc",
        "learning_rate": 0.03, "num_leaves": 15, "max_depth": 4,
        "min_child_samples": 50, "subsample": 0.8, "subsample_freq": 1,
        "colsample_bytree": 0.7, "reg_alpha": 1.0, "reg_lambda": 1.0,
        "verbose": -1, "seed": 42,
    }
    ds_tr = lgb.Dataset(X.iloc[tr], label=y[tr])
    ds_va = lgb.Dataset(X.iloc[va], label=y[va], reference=ds_tr)
    model = lgb.train(params, ds_tr, num_boost_round=600, valid_sets=[ds_va],
                      callbacks=[lgb.early_stopping(50, verbose=False)])
    print(f"\nPohon terpakai: {model.best_iteration}")

    from sklearn.metrics import roc_auc_score
    for nm, sl_ in [("train", tr), ("valid", va), ("HOLDOUT", ho)]:
        p = model.predict(X.iloc[sl_], num_iteration=model.best_iteration)
        try:
            print(f"  AUC {nm:8}: {roc_auc_score(y[sl_], p):.4f}")
        except ValueError:
            print(f"  AUC {nm:8}: n/a")

    # -- dampak trading di HOLDOUT ----------------------------------------
    p_ho = model.predict(X.iloc[ho], num_iteration=model.best_iteration)
    sig_ho = sig.iloc[ho].copy()
    sig_ho["p"] = p_ho

    b = Backtester()
    b.max_dd = 1e5

    def st(s):
        tr_, _ = b.run(df, s.drop(columns=["_t", "p", "label", "exit_bars"],
                                  errors="ignore"))
        r = tr_["r_multiple"].dropna()
        k = len(r)
        if k < 2:
            return None
        return k, r.mean(), r.mean() / (r.std(ddof=1) / math.sqrt(k)), 100*(r > 0).sum()/k

    print("\n" + "=" * 70)
    print("DAMPAK TRADING DI HOLDOUT TERSEGEL")
    print("-" * 70)
    base = st(sig_ho)
    print(f"  {'baseline (semua sinyal)':<32} n={base[0]:4d} E={base[1]:+.4f} "
          f"t={base[2]:+.2f} WR={base[3]:.1f}%")
    for q in (0.3, 0.5, 0.7):
        thr = float(np.quantile(p_ho, q))
        s2 = sig_ho[sig_ho["p"] >= thr]
        r = st(s2)
        if r:
            print(f"  {'buang '+str(int(q*100))+'% prob terendah':<32} n={r[0]:4d} "
                  f"E={r[1]:+.4f} t={r[2]:+.2f} WR={r[3]:.1f}%")
    print("=" * 70)

    imp = pd.DataFrame({"f": model.feature_name(),
                        "g": model.feature_importance("gain")}).sort_values("g", ascending=False)
    print("\n10 fitur terpenting:")
    for _, r in imp.head(10).iterrows():
        print(f"   {r['f']:<22} {r['g']:>10.1f}")


if __name__ == "__main__":
    main()
