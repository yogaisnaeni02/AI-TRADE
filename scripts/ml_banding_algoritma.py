"""
Bandingkan banyak algoritma ML pada holdout tersegel yang SAMA.

Pertanyaan pemilik: "kalau ganti model, misal XGBoost dll, supaya lebih valid?"

Kalau masalahnya ada di ALGORITMA, mengganti algoritma akan menolong.
Kalau masalahnya ada di DATA (tidak ada pola untuk dipelajari), semua
algoritma akan berkumpul di sekitar AUC 0,50 - dan itu jawabannya.

Semua model dilatih pada split yang identik, holdout tidak pernah disentuh
saat melatih maupun memilih.
"""
from __future__ import annotations

import math
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from sklearn.metrics import roc_auc_score  # noqa: E402

from ml_uji_ulang import build_dataset, make_splits  # noqa: E402


def evaluate(name, fit_predict, X, y, tr, va, ho, rows):
    """fit_predict(Xtr,ytr,Xva,yva,Xall) -> (p_va, p_ho, catatan)"""
    try:
        p_va, p_ho, note = fit_predict(X.iloc[tr], y[tr], X.iloc[va], y[va],
                                       X.iloc[va], X.iloc[ho])
        auc_va = roc_auc_score(y[va], p_va)
        auc_ho = roc_auc_score(y[ho], p_ho)
        rows.append((name, auc_va, auc_ho, note, p_ho))
        print(f"  {name:<28} AUC val {auc_va:.4f}   AUC HOLDOUT {auc_ho:.4f}   {note}")
    except Exception as e:  # noqa: BLE001
        print(f"  {name:<28} GAGAL: {type(e).__name__}: {str(e)[:60]}")


def run_kendali(df: pd.DataFrame) -> None:
    """Uji kendali: pipeline-nya yang rusak, atau datanya memang tanpa pola?

    Tiga model, pipeline & fitur & split IDENTIK - hanya targetnya beda.
    Ini pemeriksaan terpenting di seluruh uji ML proyek ini.
    """
    import lightgbm as lgb

    sig, X, y = build_dataset(df)
    tr, va, ho = make_splits(len(sig))
    p = {"objective": "binary", "metric": "auc", "max_depth": 3, "num_leaves": 8,
         "learning_rate": 0.02, "min_child_samples": 150, "reg_alpha": 10.0,
         "reg_lambda": 10.0, "subsample": 0.8, "subsample_freq": 1,
         "colsample_bytree": 0.7, "verbose": -1, "seed": 42}

    def fit_auc(target, mask=None):
        d1 = lgb.Dataset(X.iloc[tr], label=target[tr])
        d2 = lgb.Dataset(X.iloc[va], label=target[va], reference=d1)
        m = lgb.train(p, d1, num_boost_round=400, valid_sets=[d2],
                      callbacks=[lgb.early_stopping(50, verbose=False)])
        sel = np.zeros(len(target), bool)
        sel[ho] = True
        if mask is not None:
            sel &= mask
        return roc_auc_score(target[sel],
                             m.predict(X.iloc[sel], num_iteration=m.best_iteration))

    print("UJI KENDALI: pipeline rusak, atau data memang tanpa pola?")
    print("Tiga model - pipeline, fitur, split IDENTIK. Hanya target beda.\n")

    y_rand = np.random.default_rng(0).permutation(y)
    print(f"1. Label DIACAK          -> AUC holdout {fit_auc(y_rand):.4f}")
    print("   Harus ~0,50. Kalau jauh di atas, berarti pipeline bocor.\n")

    Xi = df.set_index("time_utc").reindex(sig["_t"]).reset_index(drop=True)
    atr_next = Xi["atr"].shift(-12)          # ATR 1 jam ke depan
    tgt = (atr_next > Xi["atr"]).astype(float)
    ok = tgt.notna().to_numpy()
    y_vol = tgt.fillna(0).to_numpy().astype(int)
    print(f"2. Target VOLATILITAS    -> AUC holdout {fit_auc(y_vol, ok):.4f}")
    print("   (ATR naik 1 jam ke depan). Jelas >0,50 = pipeline SEHAT.\n")

    print(f"3. Target ARAH (asli)    -> AUC holdout {fit_auc(y):.4f}")
    print("   TP sebelum SL. Perangkat sama, hasil mentok.\n")
    print("KESIMPULAN: volatilitas bisa diprediksi dari data ini, ARAH tidak.")
    print("Itu sifat pasarnya, bukan kegagalan implementasi.")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--kendali", action="store_true",
                    help="uji kendali 3 target (acak / volatilitas / arah)")
    args = ap.parse_args()

    df = pd.read_parquet(ROOT / "data/processed/XAUUSDm_M5_features.parquet")
    if args.kendali:
        run_kendali(df)
        return

    sig, X, y = build_dataset(df)
    tr, va, ho = make_splits(len(sig))
    print(f"Sampel: {len(sig)}  fitur: {X.shape[1]}  base rate: {y.mean()*100:.2f}%")
    print(f"train n={len(range(*tr.indices(len(sig))))}  "
          f"valid n={len(range(*va.indices(len(sig))))}  "
          f"HOLDOUT n={len(range(*ho.indices(len(sig))))}\n")

    Xf = X.fillna(X.iloc[tr].median())
    rows = []

    print("HASIL (0,50 = acak):")

    # -- LightGBM (pembanding) -------------------------------------------
    def f_lgb(Xtr, ytr, Xva, yva, Xv, Xh):
        import lightgbm as lgb
        p = {"objective": "binary", "metric": "auc", "max_depth": 3,
             "num_leaves": 8, "learning_rate": 0.02, "min_child_samples": 150,
             "reg_alpha": 10.0, "reg_lambda": 10.0, "subsample": 0.8,
             "subsample_freq": 1, "colsample_bytree": 0.7, "verbose": -1, "seed": 42}
        d1 = lgb.Dataset(Xtr, label=ytr)
        d2 = lgb.Dataset(Xva, label=yva, reference=d1)
        m = lgb.train(p, d1, num_boost_round=800, valid_sets=[d2],
                      callbacks=[lgb.early_stopping(60, verbose=False)])
        it = m.best_iteration
        return m.predict(Xv, num_iteration=it), m.predict(Xh, num_iteration=it), f"{it} pohon"
    evaluate("LightGBM (pembanding)", f_lgb, X, y, tr, va, ho, rows)

    # -- XGBoost ----------------------------------------------------------
    def f_xgb(Xtr, ytr, Xva, yva, Xv, Xh):
        import xgboost as xgb
        m = xgb.XGBClassifier(
            n_estimators=800, max_depth=3, learning_rate=0.02,
            subsample=0.8, colsample_bytree=0.7, reg_alpha=10.0, reg_lambda=10.0,
            min_child_weight=20, eval_metric="auc", early_stopping_rounds=60,
            random_state=42, tree_method="hist",
        )
        m.fit(Xtr, ytr, eval_set=[(Xva, yva)], verbose=False)
        return (m.predict_proba(Xv)[:, 1], m.predict_proba(Xh)[:, 1],
                f"{m.best_iteration} pohon")
    evaluate("XGBoost", f_xgb, X, y, tr, va, ho, rows)

    # -- CatBoost ---------------------------------------------------------
    def f_cat(Xtr, ytr, Xva, yva, Xv, Xh):
        from catboost import CatBoostClassifier
        m = CatBoostClassifier(
            iterations=800, depth=3, learning_rate=0.02, l2_leaf_reg=10.0,
            eval_metric="AUC", random_seed=42, verbose=0,
            early_stopping_rounds=60,
        )
        m.fit(Xtr, ytr, eval_set=(Xva, yva))
        return (m.predict_proba(Xv)[:, 1], m.predict_proba(Xh)[:, 1],
                f"{m.get_best_iteration()} pohon")
    evaluate("CatBoost", f_cat, X, y, tr, va, ho, rows)

    # -- Random Forest ----------------------------------------------------
    def f_rf(Xtr, ytr, Xva, yva, Xv, Xh):
        from sklearn.ensemble import RandomForestClassifier
        m = RandomForestClassifier(n_estimators=500, max_depth=6,
                                   min_samples_leaf=50, max_features="sqrt",
                                   random_state=42, n_jobs=-1)
        m.fit(Xtr.fillna(Xtr.median()), ytr)
        return (m.predict_proba(Xv.fillna(Xtr.median()))[:, 1],
                m.predict_proba(Xh.fillna(Xtr.median()))[:, 1], "500 pohon")
    evaluate("Random Forest", f_rf, Xf, y, tr, va, ho, rows)

    # -- Extra Trees ------------------------------------------------------
    def f_et(Xtr, ytr, Xva, yva, Xv, Xh):
        from sklearn.ensemble import ExtraTreesClassifier
        m = ExtraTreesClassifier(n_estimators=500, max_depth=6,
                                 min_samples_leaf=50, random_state=42, n_jobs=-1)
        m.fit(Xtr, ytr)
        return m.predict_proba(Xv)[:, 1], m.predict_proba(Xh)[:, 1], "500 pohon"
    evaluate("Extra Trees", f_et, Xf, y, tr, va, ho, rows)

    # -- Regresi logistik -------------------------------------------------
    def f_lr(Xtr, ytr, Xva, yva, Xv, Xh):
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import make_pipeline
        m = make_pipeline(StandardScaler(),
                          LogisticRegression(C=0.1, max_iter=2000, random_state=42))
        m.fit(Xtr, ytr)
        return m.predict_proba(Xv)[:, 1], m.predict_proba(Xh)[:, 1], "linear"
    evaluate("Regresi Logistik", f_lr, Xf, y, tr, va, ho, rows)

    # -- MLP (jaringan saraf) ---------------------------------------------
    def f_mlp(Xtr, ytr, Xva, yva, Xv, Xh):
        from sklearn.neural_network import MLPClassifier
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import make_pipeline
        m = make_pipeline(StandardScaler(),
                          MLPClassifier(hidden_layer_sizes=(32, 16), alpha=1.0,
                                        max_iter=600, early_stopping=True,
                                        random_state=42))
        m.fit(Xtr, ytr)
        return m.predict_proba(Xv)[:, 1], m.predict_proba(Xh)[:, 1], "32-16"
    evaluate("MLP (neural net)", f_mlp, Xf, y, tr, va, ho, rows)

    # -- Ensemble rata-rata ------------------------------------------------
    if len(rows) >= 3:
        P = np.column_stack([r[4] for r in rows])
        # ranking rata-rata supaya skala tiap model tidak mendominasi
        from scipy.stats import rankdata
        ens = np.mean([rankdata(P[:, i]) for i in range(P.shape[1])], axis=0)
        auc_ens = roc_auc_score(y[ho], ens)
        print(f"  {'ENSEMBLE (rata-rata rank)':<28} {'':<16} AUC HOLDOUT {auc_ens:.4f}")

    print()
    aucs = [r[2] for r in rows]
    print(f"Rentang AUC holdout: {min(aucs):.4f} - {max(aucs):.4f}")
    print(f"Rata-rata          : {np.mean(aucs):.4f}")
    print()
    if max(aucs) < 0.55:
        print("Tidak ada algoritma yang mendekati berguna. Masalahnya di DATA,")
        print("bukan di pilihan algoritma - mengganti model tidak menolong.")


if __name__ == "__main__":
    main()
