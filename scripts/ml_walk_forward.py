"""
Uji jujur: mesin memprediksi tiap sinyal, tanpa pernah tahu masa depan.

CARA KERJANYA
-------------
Berjalan maju sepanjang waktu, persis seperti hidup:

    1. Berhenti di satu titik waktu
    2. Latih model HANYA dari trade yang sudah selesai sebelum titik itu
    3. Prediksi trade-trade berikutnya
    4. Maju, ulangi

Model tidak pernah melihat satu pun bar dari masa depannya sendiri. Setiap
prediksi yang dicatat adalah prediksi out-of-sample sesungguhnya - bukan
hasil membagi data lalu mengintip.

Ada jeda `PURGE` antara akhir data latih dan awal prediksi, karena label
sebuah trade baru diketahui setelah posisinya tertutup (bisa 48 bar). Tanpa
jeda itu, trade terakhir di data latih masih "berlangsung" saat prediksi
dibuat - dan itu kebocoran halus yang sulit terlihat.

KENAPA INI BERBEDA DARI HOLDOUT BIASA
--------------------------------------
Holdout tunggal hanya menguji satu titik potong. Kalau kebetulan periode
holdout-nya mudah, hasilnya terlihat bagus tanpa alasan. Walk-forward
menguji puluhan titik potong berurutan, jadi keberuntungan satu periode
tidak bisa menyamar jadi kemampuan.

CATATAN PENTING TENTANG TARGET
-------------------------------
Memprediksi VOLATILITAS ternyata mudah (AUC ~0,82) tetapi TIDAK BERGUNA:
kepentingan fitur tertinggi adalah `hour_utc`, jadi model hanya menghafal
pola volatilitas per jam. Dan arahnya tidak selaras dengan profit - bar
ber-ATR rendah paling sering diikuti volatilitas naik (69%) tetapi justru
menghasilkan E[R] terendah.

Karena itu skrip ini memprediksi yang benar-benar penting: **apakah trade
ini akan kena TP**.

PEMAKAIAN
---------
    python scripts/ml_walk_forward.py
    python scripts/ml_walk_forward.py --min-train 400 --step 50
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.engine import Backtester  # noqa: E402
from src.strategy.setups import RuleEngine  # noqa: E402

FEATURES = ROOT / "data" / "processed" / "XAUUSDm_M5_features.parquet"

# Hanya fitur yang SUDAH diketahui saat bar sinyal ditutup.
KANDIDAT_FITUR = [
    "atr_percentile", "adx", "rsi", "mom_24", "fib_position",
    "h1_adx", "htf_alignment", "atr", "hour_utc",
]

# Jeda antara akhir data latih dan awal prediksi, dalam jumlah trade.
# Label sebuah trade baru pasti diketahui setelah posisinya tertutup
# (maksimal 48 bar M5), jadi beberapa trade terakhir di data latih bisa
# masih berlangsung saat prediksi dibuat.
PURGE = 12


def siapkan() -> tuple[pd.DataFrame, list[str]]:
    """Bangun tabel: satu baris per trade, fitur kausal + label TP."""
    df = pd.read_parquet(FEATURES)
    df["t"] = pd.to_datetime(df["time_utc"])

    sig = RuleEngine().generate(df, min_score=5)
    bt = Backtester()
    bt.max_dd = 999  # halt DD adalah guardrail operasional, bukan alat ukur
    trades, _ = bt.run(df, sig, initial_equity=5_000_000)

    fitur = [c for c in KANDIDAT_FITUR if c in df.columns]
    # Entry terjadi satu bar M5 SETELAH sinyal, jadi fitur diambil dari
    # bar sinyal - bukan bar entry.
    kunci = pd.to_datetime(trades["entry_time"]) - pd.Timedelta(minutes=5)
    peta = df.set_index("t")

    d = pd.concat(
        [
            peta.reindex(kunci)[fitur].reset_index(drop=True),
            trades[["r_multiple", "pnl_idr", "outcome", "entry_time"]].reset_index(drop=True),
        ],
        axis=1,
    ).dropna(subset=fitur).reset_index(drop=True)

    d["label"] = (d["outcome"] == "tp").astype(int)
    d["entry_time"] = pd.to_datetime(d["entry_time"])
    return d.sort_values("entry_time").reset_index(drop=True), fitur


def walk_forward(d: pd.DataFrame, fitur: list[str], min_train: int,
                 step: int, leaves: int, trees: int) -> pd.DataFrame:
    """Prediksi maju; tiap potongan dilatih hanya dari masa lalunya."""
    import lightgbm as lgb

    hasil = []
    mulai = min_train
    while mulai < len(d):
        akhir = min(mulai + step, len(d))
        latih = d.iloc[: mulai - PURGE]
        uji = d.iloc[mulai:akhir]

        # Butuh dua kelas di data latih, kalau tidak model tak bisa belajar.
        if latih["label"].nunique() < 2 or len(latih) < 50:
            mulai = akhir
            continue

        m = lgb.LGBMClassifier(
            num_leaves=leaves, n_estimators=trees, learning_rate=0.05,
            min_child_samples=40, subsample=0.8, colsample_bytree=0.8,
            random_state=42, verbose=-1,
        )
        m.fit(latih[fitur], latih["label"])
        p = m.predict_proba(uji[fitur])[:, 1]

        blok = uji.copy()
        blok["prob"] = p
        blok["n_latih"] = len(latih)
        hasil.append(blok)
        mulai = akhir

    return pd.concat(hasil).reset_index(drop=True) if hasil else pd.DataFrame()


def lapor(h: pd.DataFrame) -> None:
    from sklearn.metrics import roc_auc_score

    n = len(h)
    base = h["label"].mean()
    auc = roc_auc_score(h["label"], h["prob"])

    # SE AUC (Hanley-McNeil) untuk menilai apakah beda dari tebak acak.
    npos = int(h["label"].sum())
    nneg = n - npos
    q1 = auc / (2 - auc)
    q2 = 2 * auc * auc / (1 + auc)
    se = math.sqrt(
        (auc * (1 - auc) + (npos - 1) * (q1 - auc**2) + (nneg - 1) * (q2 - auc**2))
        / (npos * nneg)
    )
    t = (auc - 0.5) / se

    print(f"\nPREDIKSI OUT-OF-SAMPLE : {n:,} trade")
    print(f"  benar-benar TP       : {npos:,} ({base * 100:.1f}%)")
    print(f"  AUC                  : {auc:.4f}  (SE {se:.4f}, t {t:+.2f})")
    print(f"  {'LEBIH BAIK dari acak' if t > 1.96 else 'TIDAK bisa dibedakan dari tebak acak'}")

    # Apakah probabilitas yang lebih tinggi benar-benar lebih sering benar?
    print(f"\n{'kelompok prob':16s} {'n':>5s} {'TP nyata':>9s} {'E[R]':>9s} {'t':>6s}")
    print("-" * 50)
    h = h.copy()
    h["q"] = pd.qcut(h["prob"], 4, labels=["Q1 rendah", "Q2", "Q3", "Q4 tinggi"])
    for q, g in h.groupby("q", observed=True):
        r = g["r_multiple"]
        se_r = r.std(ddof=1) / math.sqrt(len(r))
        print(f"{str(q):16s} {len(g):>5d} {g['label'].mean() * 100:>8.1f}% "
              f"{r.mean():>+9.4f} {r.mean() / se_r:>6.2f}")
    print("-" * 50)

    q1g = h[h["q"] == "Q1 rendah"]["r_multiple"]
    q4g = h[h["q"] == "Q4 tinggi"]["r_multiple"]
    sel = q4g.mean() - q1g.mean()
    se_sel = math.sqrt(q4g.var(ddof=1) / len(q4g) + q1g.var(ddof=1) / len(q1g))
    print(f"selisih Q4 - Q1 = {sel:+.4f}R   t = {sel / se_sel:.2f}")

    # Kalau dipakai sebagai filter: buang sebagian prediksi terendah.
    print("\nKALAU DIPAKAI SEBAGAI FILTER:")
    semua = h["r_multiple"]
    se_a = semua.std(ddof=1) / math.sqrt(len(semua))
    print(f"  tanpa filter         n={len(semua):>5d}  E[R]={semua.mean():>+7.4f}  t={semua.mean() / se_a:>5.2f}")
    for q in (0.25, 0.50):
        amb = h["prob"].quantile(q)
        k = h[h["prob"] >= amb]["r_multiple"]
        se_k = k.std(ddof=1) / math.sqrt(len(k))
        print(f"  buang {q * 100:>3.0f}% terendah  n={len(k):>5d}  E[R]={k.mean():>+7.4f}  t={k.mean() / se_k:>5.2f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-train", type=int, default=400,
                    help="jumlah trade minimum sebelum prediksi pertama")
    ap.add_argument("--step", type=int, default=50,
                    help="berapa trade diprediksi sebelum model dilatih ulang")
    ap.add_argument("--leaves", type=int, default=4)
    ap.add_argument("--trees", type=int, default=60)
    args = ap.parse_args()

    if not FEATURES.exists():
        print(f"Tidak ada {FEATURES}. Jalankan pipeline fitur dulu.")
        return 1

    d, fitur = siapkan()
    print("=" * 62)
    print("WALK-FORWARD: mesin menebak tiap sinyal tanpa tahu masa depan")
    print("=" * 62)
    print(f"Total trade   : {len(d):,}")
    print(f"Fitur kausal  : {len(fitur)} -> {fitur}")
    print(f"Latih minimum : {args.min_train}   dilatih ulang tiap {args.step} trade")
    print(f"Jeda purge    : {PURGE} trade (label belum pasti saat posisi masih terbuka)")
    print(f"Ukuran model  : {args.leaves} leaf, {args.trees} pohon")

    h = walk_forward(d, fitur, args.min_train, args.step, args.leaves, args.trees)
    if h.empty:
        print("\nTidak ada prediksi yang dihasilkan - data latih terlalu sedikit.")
        return 1

    lapor(h)
    print("\nCATATAN: setiap angka di atas out-of-sample. Model tidak pernah")
    print("melihat satu pun trade yang diprediksinya saat dilatih.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
