# Diagnosis: Data, Model, atau Fitur — Apa Kendala ML-nya?

**Tanggal:** 12 September 2026
**Pertanyaan pemilik:** "kalau upgrade ML, kendalanya di data yang kurang,
modelnya tidak cocok, atau gimana?"

---

## Jawaban Singkat

**Bukan ketiganya secara terpisah — kendalanya adalah plafon informasi
di sumbernya: harga OHLCV itu sendiri.** Tiga eksperimen terkontrol di
bawah membuktikan menambah data, mengganti model, dan menambah fitur
semuanya nyaris tidak menggerakkan hasil. AUC menempel di 0,52–0,56
(0,50 = tebak acak) apa pun yang diubah.

Ini bukan tebakan — tiga variabel diuji **satu per satu**, sambil dua
lainnya dikunci tetap, persis metode kendali eksperimen.

---

## Eksperimen 1: Apakah Datanya Kurang?

Sama fitur (9 kandidat kausal), sama model (LightGBM), sama metode
(walk-forward dengan purge) — **hanya timeframe yang diganti**, sehingga
jumlah data historis berubah 3x lipat:

| Timeframe | Trade | Cakupan waktu | AUC | t |
|---|---|---|---|---|
| M5 | 1.751 | 1,4 tahun | 0,5618 | +3,54 |
| **M15** | **3.416** | **4,2 tahun** | **0,5487** | **+3,95** |

**2x lipat jumlah trade dan 3x lipat rentang waktu, AUC-nya malah sedikit
turun.** Kalau kendalanya kekurangan data, menambah data historis 3x
lipat seharusnya menaikkan AUC secara jelas — yang terjadi kebalikannya.

### Diperiksa lebih lanjut: apakah hasil M15 stabil?

```
Stabilitas seed (5 seed)     : AUC 0,5452-0,5491, semua stabil
Belah dua periode prediksi   : paruh awal AUC 0,5162 (t=+0,90, TIDAK signifikan)
                                paruh akhir AUC 0,5330 (t=+1,97)
```

Stabil terhadap seed (bukan kebetulan angka acak), tapi **tidak stabil
antar periode** — separuh data historisnya bahkan tidak menunjukkan
sinyal yang signifikan secara statistik. Ini tanda edge yang sangat
tipis dan bergantung rezim, bukan pola struktural yang kuat.

**Kesimpulan: bukan kekurangan data.**

---

## Eksperimen 2: Apakah Modelnya Tidak Cocok?

Sama data (1.751 trade M5), sama fitur — **hanya algoritma yang diganti**:

| Algoritma | AUC | t |
|---|---|---|
| LightGBM | 0,5618 | +3,54 |
| XGBoost | 0,5499 | +2,86 |
| Random Forest | 0,5167 | +0,96 |

Ditambah hasil sebelumnya (`docs/42`) yang menguji 7 algoritma termasuk
CatBoost, Extra Trees, Regresi Logistik, dan Neural Network — semuanya
berkumpul di kisaran 0,46–0,56, rata-rata 0,50 tepat.

Kalau kendalanya model yang salah pilih, satu algoritma akan menonjol
jauh dari yang lain. Yang terjadi: semua algoritma — linear, tree-based,
boosting, neural network — mendarat di kisaran yang sama.

**Kesimpulan: bukan pilihan model.**

---

## Eksperimen 3: Apakah Fiturnya Kurang?

Sama data, sama model — **jumlah fitur diperluas 4x lipat**, dari 9
fitur kausal pilihan manual menjadi 37 fitur (semua indikator numerik
yang tersedia: RSI, MACD, Bollinger, Stochastic, ADX/DI, momentum
multi-horizon, struktur candle, volume ratio, BOS):

| Set fitur | Jumlah | AUC | t |
|---|---|---|---|
| 9 fitur kausal | 9 | 0,5618 | +3,54 |
| **37 fitur diperluas** | **37** | **0,5639** | **+3,67** |

**Menambah fitur 4x lipat menaikkan AUC sebesar 0,002** — secara
praktis nol. Kalau kendalanya fitur yang kurang kaya, menambah 28 fitur
baru (termasuk semua indikator populer: MACD, Bollinger, Stochastic,
struktur BOS) akan menaikkan AUC secara jelas. Tidak terjadi.

**Kesimpulan: bukan kekurangan fitur.**

*(Catatan teknis: percobaan pertama sempat menunjukkan AUC 0,36 —
di bawah acak — karena tiga fitur `asia_range`/`dist_to_asia_high/low`
punya 71% NaN by design [anti-lookahead, hanya terisi setelah sesi Asia
selesai], yang membuang 71% baris data secara diam-diam. Setelah tiga
fitur itu dikeluarkan, hasilnya 0,5639 seperti tabel di atas. Dicatat
di sini supaya tidak terulang: hati-hati fitur ber-NaN tinggi saat
menggabungkan ke satu tabel latih.)*

---

## Jadi Apa Kendalanya?

**Plafon informasi.** Ketiga sumbu yang biasanya jadi penyebab masalah
ML (data, model, fitur) sudah diperiksa dan bukan penyebabnya. Yang
tersisa: **harga OHLCV historis di broker ini, pada horizon trade yang
dipakai (jam-an), memang hanya mengandung sedikit informasi arah** —
sekitar AUC 0,52–0,56, bukan nol (jadi bukan "tidak ada apa-apa"), tapi
jauh dari cukup untuk jadi basis keputusan trading sendirian.

Ini konsisten dengan temuan struktural dari awal proyek: celah antara
entry acak dan breakeven cuma **0,7 poin persentase** (`docs/06`).
Ruang untuk edge apa pun — aturan atau ML — memang sempit di pasar ini.

### Kenapa AUC 0,55 "kecil" tapi tetap berguna sebagai filter

AUC 0,55 terdengar dekat dengan 0,50, tapi di atas cukup trade, angka itu
signifikan secara statistik (t=3,5–4,0) dan **bisa dipakai sebagai
filter tambahan** — bukan generator sinyal berdiri sendiri. Itu sebabnya
`docs/46` menunjukkan filter walk-forward menaikkan E[R] dari +0,148 ke
+0,220 saat dipakai untuk membuang 25% probabilitas terendah dari sinyal
yang **sudah ada** dari rule engine.

Pola inilah yang terbukti bekerja di proyek ini: ML sebagai **penyaring**
di atas aturan yang sudah punya edge, bukan ML sebagai **penentu arah**
yang berdiri sendiri.

---

## Upgrade yang Sudah Terbukti — dan yang Terbukti Tidak Menolong

| Upgrade | Hasil |
|---|---|
| Ganti algoritma (7 dicoba) | Tidak menolong — semua di kisaran acak |
| Tambah data historis (3x) | Tidak menolong — AUC malah sedikit turun |
| Tambah fitur (4x lipat) | Tidak menolong — AUC nyaris tidak bergerak |
| **Ganti target: TP/SL bukan volatilitas** | **Menolong** — AUC 0,50→0,56 |
| **Ganti populasi: trade tereksekusi, bukan semua bar** | **Menolong** — jadi melatih pertanyaan yang benar |
| **Ganti validasi: walk-forward, bukan holdout tunggal** | **Menolong** — membuktikan sinyalnya bukan kebetulan satu periode |

Tiga baris terakhir itulah yang benar-benar mengubah hasil dari "tidak
ada apa-apa" (`docs/41`, `docs/42`) menjadi "ada sinyal lemah tapi nyata"
(`docs/46`). Bukan data/model/fitur — melainkan **apa yang diprediksi
dan bagaimana divalidasi**.

---

## Rekomendasi Konkret

1. **Jangan cari algoritma "lebih canggih".** Sudah dibuktikan dua kali
   (`docs/42`, dan eksperimen 2 di sini) tidak ada bedanya.
2. **Jangan kejar lebih banyak data historis** dari broker/timeframe
   yang sama. Sudah dibuktikan (eksperimen 1) tidak menaikkan AUC.
3. **Kalau mau upgrade fitur, arahnya bukan "lebih banyak"** — sudah
   terbukti sia-sia (eksperimen 3) — melainkan **informasi yang benar-
   benar baru**: order flow, kalender berita, data lintas-aset (DXY),
   bukan turunan lain dari OHLCV yang sama.
4. **Pakai AUC 0,55-0,56 sebagai filter**, bukan generator sinyal —
   pola yang sudah terbukti menaikkan expectancy (`docs/46`).
5. Prioritas riset berikutnya tetap seperti `docs/31`: entry presisi M1
   (menyerang eksekusi, bukan prediksi) dan lintas-sesi Tokyo→London
   (informasi temporal yang belum pernah diuji) — dua-duanya menyerang
   sumber informasi BARU, bukan mengolah ulang OHLCV yang sama dengan
   cara berbeda.
