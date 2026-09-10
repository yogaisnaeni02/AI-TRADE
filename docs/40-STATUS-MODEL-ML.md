# Status Model Machine Learning: Ada, Tapi Sengaja Tidak Dipakai

**Tanggal:** 10 September 2026
**Pertanyaan pemilik:** "model yang dilatih udah kepanggil belum? harusnya
model machine learning-nya dipakai."

---

## Jawaban Singkat

**Belum dipakai, dan itu memang keputusan yang benar.**

File modelnya ada (`data/models/meta_model.txt`, LightGBM, 58 fitur) dan
bisa dimuat. Tetapi **tidak ada satu baris pun kode produksi yang
membacanya** — hanya `src/models/train.py` yang menyentuhnya, dan itu untuk
MENULIS, bukan membaca.

Alasannya: model itu **tidak punya edge**. Saat diuji ulang hari ini pada
data yang benar-benar belum pernah dilihatnya, ia justru **memperburuk**
hasil.

---

## 1. Bukti Model Tidak Dipanggil

```
$ grep -rn "meta_model|lgb.Booster|load_model|lightgbm" --include=*.py .
src/models/train.py:22:  import lightgbm as lgb
src/models/train.py:233: models[-1].save_model(... "meta_model.txt")
```

Tiga kemunculan, semuanya di `train.py`. `bot.py`, `setups.py`, dan
`manager.py` tidak pernah mengimpor lightgbm.

### Yang mungkin disangka ML padahal bukan

`bot.py` baris 355:

```python
confidence = min(1.0, sig["score"] / 10.0)
```

Ini **bukan** output model — hanya skor rule-based dibagi 10. Dipakai untuk
`adaptive_sizing`, yang pun `enabled: false` di config.

---

## 2. Kenapa Tidak Dipakai: Model Ini Tidak Menemukan Pola

Dari `docs/11`, saat model dilatih:

```
AUC in-sample     : 0,9829   <- model BISA menghafal
AUC out-of-sample : 0,5089   <- setara lempar koin
```

Model punya kapasitas belajar (terbukti hafal sampai AUC 0,98), tetapi tidak
ada pola berulang untuk dipelajari. Yang dihafalnya noise.

Bukti tambahan dari file modelnya sendiri: **hanya 11 pohon**. Early
stopping menghentikannya hampir seketika dari 400 ronde yang dijadwalkan —
tanda model berhenti belajar karena tidak ada lagi yang bisa dipelajari.

Sebaran prediksinya juga nyaris datar:

```
min 0,205   median 0,245   max 0,254
```

Rentangnya cuma 0,05 di sekitar base rate 23,7%. Model pada dasarnya
menebak angka yang sama untuk semua bar.

---

## 3. Diuji Ulang Hari Ini — dan Sempat Terlihat Menjanjikan

Model dicoba sebagai filter di atas sinyal `momentum_fib`:

| Filter | n | E[R] | t | WR |
|---|---|---|---|---|
| Baseline | 675 | +0,1327 | +1,95 | 29,8% |
| Buang 30% prob terendah | 559 | +0,1517 | +2,02 | 29,9% |
| Buang 50% prob terendah | 487 | +0,2176 | +2,66 | 31,6% |
| **Buang 70% prob terendah** | 339 | **+0,3067** | **+3,07** | 33,9% |

Terlihat sangat bagus — bahkan melampaui filter konfluensi. **Angka ini
palsu.**

---

## 4. Kenapa Palsu: Model Melihat Data Ujinya Sendiri

`train.py` baris 233 menyimpan `models[-1]` — model dari **fold terakhir**
walk-forward. Fold terakhir dilatih pada **83% data**:

```
model tersimpan dilatih pada : 2025-04-11 -> 2026-06-08  (71.895 dari 86.279 baris)
akhir data                   : 2026-09-09
holdout 30% saya mulai       : 2026-04-07   <- TUMPANG TINDIH
```

Jadi "holdout" saya bukan holdout untuk model ini — ia sudah melihat dua
bulan pertamanya saat latihan.

### Uji pada periode yang BENAR-BENAR bersih

Hanya data setelah 8 Juni 2026 yang tidak pernah dilihat model:

| Periode | Baseline | + Filter ML |
|---|---|---|
| **Bersih** (setelah 8 Jun 2026) | n=96, **+0,1079** | n=59, **+0,0294** |
| Bocor (model sudah lihat) | n=572, +0,1376 | n=280, **+0,3651** |

**Di data yang benar-benar baru, filter ML MEMPERBURUK hasil**
(+0,108 → +0,029). Yang "hebat" (+0,365) hanya muncul di periode yang model
sudah hafal.

Ini contoh tekstbook kebocoran data. Kalau dipakai live, hasilnya akan
seperti kolom kiri — lebih buruk daripada tanpa model.

---

## 5. Bug yang Ditemukan Sekalian

### `train.py` menyimpan model yang salah

Menyimpan `models[-1]` (fold terakhir, dilatih 83% data) berarti model yang
tersimpan **tidak punya periode uji yang bersih sama sekali**. Siapa pun yang
memuatnya lalu mengukur pada data proyek ini akan mendapat angka bocor.

Yang benar untuk dipakai produksi: latih ulang pada SELURUH data setelah
walk-forward memutuskan modelnya layak — dan hanya kalau layak. Model ini
tidak layak (AUC OOS 0,509), jadi tidak ada yang perlu disimpan.

### Enam fitur harus dibangun ulang manual

Model menuntut `is_uptrend_htf`, `is_downtrend_htf`, `is_london`, `is_ny`,
`is_asia`, `is_buy` — tidak ada di file fitur, dibuat on-the-fly di
`train.py::build_features`. Siapa pun yang memuat model tanpa mereplikasi
persis enam baris itu akan mendapat prediksi diam-diam salah.

---

## 6. Kesimpulan

| Pertanyaan | Jawaban |
|---|---|
| Model ada? | Ya, `data/models/meta_model.txt` |
| Dipanggil kode produksi? | **Tidak** |
| Seharusnya dipanggil? | **Tidak** |
| Kenapa? | AUC OOS 0,509 (acak); di data bersih memperburuk +0,108 → +0,029 |

Yang terbukti bekerja bukan ML, melainkan **filter aturan sederhana**:
candle searah + ADX>25 + tren M5 (`docs/36`), t=3,14 dengan holdout tersegel
yang benar-benar bersih.

`docs/29` sudah menetapkan urutannya, dan urutan itu terbukti benar:

> **ML sebagai penyaring baru masuk akal SETELAH rule engine punya edge
> yang terbukti.**

Rule engine baru mencapai t~3,14 hari ini, dan itu pun belum lulus forward
test. ML adalah langkah setelah itu, bukan sekarang.

### Kalau nanti ML dicoba lagi

Prasyarat yang wajib dipenuhi:

1. Perbaiki `train.py` — jangan simpan `models[-1]`
2. Sisihkan periode holdout yang tidak pernah disentuh siapa pun
3. Perbaiki kebocoran yang tercatat di `docs/27` bagian 9: fold test dipakai
   sebagai validation early stopping, dan barrier dihitung tanpa spread
4. Bangun fitur turunan di pipeline, bukan on-the-fly di train.py
5. Ambang lolos ditetapkan SEBELUM melihat hasil
