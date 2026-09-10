# Ganti Algoritma ML: XGBoost, CatBoost, Neural Net — Semua Sama Saja

**Tanggal:** 10 September 2026
**Pertanyaan pemilik:** "kalau kita perbaiki modelnya dulu gimana? kayak
ganti model misal pakai XGBoost dll supaya lebih valid lagi."

---

## Ringkasan

Tujuh algoritma diuji pada holdout tersegel yang sama. **Rata-rata AUC
0,5029** — tepat di tengah acak.

Lalu satu uji kendali menjawab pertanyaan yang sebenarnya: pipeline yang
sama, fitur yang sama, model yang sama berhasil memprediksi **volatilitas
dengan AUC 0,72**. Jadi kodenya sehat — yang tidak bisa diprediksi hanya
**arah**.

Masalahnya bukan algoritma. Masalahnya data.

---

## 1. Kenapa Pertanyaan Ini Harus Diuji

Menyimpulkan "ML tidak bisa" dari satu algoritma tidak sah. LightGBM bisa
saja kebetulan tidak cocok untuk struktur data ini. Jadi diuji: **kalau
algoritmanya diganti, apakah hasilnya berubah?**

Logikanya sederhana:

- Kalau masalahnya di **algoritma** → algoritma lain akan lebih baik
- Kalau masalahnya di **data** → semua algoritma berkumpul di AUC ~0,50

---

## 2. Hasil: Tujuh Algoritma, Semua di Sekitar Acak

Split identik untuk semua: 55% train / 15% valid / **30% holdout tersegel**.
Holdout tidak pernah disentuh saat melatih maupun memilih.

```
Sampel: 4.189   fitur: 58   base rate TP: 27,62%
train n=2.255   valid n=581   HOLDOUT n=1.257
```

| Algoritma | AUC valid | **AUC HOLDOUT** | Catatan |
|---|---|---|---|
| **LightGBM** (pembanding) | 0,6321 | **0,5539** | 23 pohon |
| **XGBoost** | 0,6353 | **0,5348** | 51 pohon |
| **CatBoost** | 0,4901 | **0,5181** | 9 pohon |
| Random Forest | 0,5166 | **0,5064** | 500 pohon |
| Extra Trees | 0,4017 | **0,4835** | 500 pohon |
| Regresi Logistik | 0,5178 | **0,4639** | linear |
| MLP (neural net 32-16) | 0,4773 | **0,4597** | |
| **Ensemble** (rata-rata rank) | — | **0,4998** | gabungan 7 model |

```
Rentang : 0,4597 - 0,5539
Rata-rata: 0,5029
```

**Tiga dari tujuh di BAWAH acak.** Ensemble — yang biasanya menolong kalau
tiap model menangkap sepotong sinyal — mendarat di 0,4998. Persis acak.
Itu tanda tidak ada potongan sinyal untuk digabungkan.

XGBoost, yang secara khusus ditanyakan, mendapat **0,5348** — lebih rendah
dari LightGBM.

---

## 3. Uji Kendali: Apakah Pipeline-nya yang Rusak?

Tiga model dilatih dengan pipeline, fitur, dan split yang **persis sama**.
Hanya targetnya berbeda.

| # | Target | AUC holdout | Arti |
|---|---|---|---|
| 1 | **Label diacak** | **0,4638** | Pipeline bersih — tidak ada kebocoran |
| 2 | **Volatilitas** (ATR naik 1 jam ke depan) | **0,7204** | Pipeline SEHAT dan mampu belajar |
| 3 | **Arah** (TP sebelum SL) | **0,5539** | Tidak ada yang bisa dipelajari |

Baris 1 membuktikan tidak ada kebocoran: dengan label acak, model tidak
menemukan apa pun (seperti seharusnya).

**Baris 2 adalah kuncinya.** Fitur, kode, dan model yang sama mencapai
**AUC 0,72** untuk memprediksi volatilitas. Jadi tidak mungkin beralasan
"fiturnya kurang bagus" atau "modelnya salah setelan" — perangkat yang
sama bekerja dengan baik ketika ada pola yang nyata.

Baris 3 memakai perangkat identik, dan mentok di 0,55.

**Kesimpulannya tegas: volatilitas bisa diprediksi dari data ini, arah
tidak.** Itu bukan kegagalan implementasi, itu sifat pasarnya.

---

## 4. Kenapa Ganti Algoritma Tidak Menolong

Semua algoritma yang diuji — boosting, bagging, linear, neural network —
mencari hal yang sama: **fungsi dari fitur ke label**. Kalau fungsi itu
tidak ada dalam data, tidak ada algoritma yang bisa menemukannya.

Analoginya: mengganti teleskop tidak membuat bintang muncul di langit yang
memang kosong.

Ini konsisten dengan seluruh temuan proyek:

| Temuan | Dokumen |
|---|---|
| Celah entry acak ke breakeven cuma 0,7pp | `docs/06` |
| 130+ kombinasi horizon pendek, semua rugi | `docs/22` |
| MACD, Stochastic, BOS, CHoCH — semua memperburuk | `docs/36`, `docs/37` |
| Fitur ML teratas: `h4_atr`, `h1_adx`, `asia_range` (volatilitas) | `docs/41` |

Pola yang sama muncul berulang dari arah berbeda: **yang bisa diukur dari
data ini adalah seberapa besar gerakan, bukan ke mana**.

---

## 5. Apa yang Sebenarnya Bisa Dilakukan dengan Temuan AUC 0,72

Kemampuan memprediksi volatilitas **bukan tidak berguna** — hanya tidak
bisa dipakai memilih arah. Dua pemakaian yang masuk akal, dan keduanya
sudah ada versinya di sistem:

1. **Gate ATR** (`atr_percentile` 0,20–0,95) — sudah dipakai. Ini persis
   "menghindari trading saat volatilitas salah", dikerjakan lewat aturan.
2. **SL adaptif ATR** (3500–4500 points) — sudah dipakai. SL menyesuaikan
   volatilitas, dan itu memakai informasi yang memang bisa diprediksi.

Jadi informasi yang bisa ditangkap ML dari data ini **sudah dipakai
sistem**, lewat aturan yang lebih sederhana dan tidak butuh model.

Kalau nanti mau lebih jauh: ukuran lot yang menyesuaikan prediksi
volatilitas (bukan arah) adalah satu-satunya jalur ML yang punya dasar
bukti di proyek ini. Tetapi itu memperbaiki manajemen risiko, bukan
menambah edge.

---

## 6. Jawaban untuk Pemilik

Pertanyaannya benar dan wajib diuji — dan sekarang sudah diuji dengan
tuntas: **7 algoritma + 1 ensemble, semua pada holdout tersegel yang sama**.

| Pertanyaan | Jawaban |
|---|---|
| XGBoost lebih baik? | Tidak — 0,5348 vs LightGBM 0,5539 |
| CatBoost? | Tidak — 0,5181 |
| Neural network? | Tidak — 0,4597 (di bawah acak) |
| Digabung semua (ensemble)? | Tidak — 0,4998 |
| Jadi modelnya yang salah? | **Bukan.** Pipeline yang sama dapat AUC 0,72 untuk volatilitas |

Yang membuat sistem ini layak dijalankan bukan model, melainkan:

- **Rule engine** dengan expectancy +0,1327R
- **Filter konfluensi** yang lolos holdout tersegel, t=3,14 (`docs/36`)
- **Manajemen risiko** yang membatasi kerugian per trade dan per hari

Menambahkan model ber-AUC 0,50 ke atas itu tidak membuatnya "lebih valid" —
justru menambah komponen yang keputusannya tidak bisa dijelaskan.

### Kapan ML layak dicoba lagi

Prasyaratnya bukan algoritma yang lebih canggih, melainkan **data yang
lebih banyak atau informasi yang belum ada di harga M5**:

1. Sampel jauh lebih besar (675 trade → 2.000+)
2. Informasi dari luar deret harga M5 — order flow, kalender berita,
   posisi COT — hal yang belum pernah dilihat model
3. Rule engine terbukti punya edge di data LIVE, bukan cuma backtest

Menambah algoritma pada data yang sama sudah terbukti tidak menolong.

---

## 7. Cara Mengulang

```bash
python scripts/ml_banding_algoritma.py           # 7 algoritma + ensemble
python scripts/ml_banding_algoritma.py --kendali # uji kendali 3 target
```

Skrip tidak menyimpan model dan tidak menyentuh jalur produksi.
