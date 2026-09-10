# ML Dilatih Ulang dengan Benar — Hasilnya Tetap Tidak Ada Edge

**Tanggal:** 10 September 2026
**Pertanyaan pemilik:** "harusnya modelnya digunakan untuk membantu prediksi,
karena itu dasar yang digunakannya."

---

## Kenapa Pertanyaan Ini Wajar

Proyek ini memang dimulai sebagai proyek ML. Menolak memakai model hanya
karena "hasil lamanya jelek" tidak cukup — model lama itu **memang dilatih
dengan cara yang salah**, jadi kesimpulannya belum sah.

Maka model dilatih ULANG di sini dengan seluruh kesalahan diperbaiki, lalu
diuji jujur. Hasilnya baru bisa dipakai untuk memutuskan.

---

## 1. Tiga Kesalahan Model Lama

| # | Kesalahan | Akibat |
|---|---|---|
| 1 | Dilatih pada **semua 86.279 bar**, seolah tiap bar kandidat entry | Model menjawab pertanyaan yang salah — yang ditradingkan cuma 4.189 sinyal |
| 2 | Data latihnya **basi**: kolom sesi meleset 7 jam (cocok hanya **4,4%**) | Model belajar konteks sesi yang salah |
| 3 | Yang disimpan `models[-1]` — fold terakhir, dilatih **83% data** | Tidak punya periode uji bersih; semua pengukuran bocor |

Ditambah kebocoran yang sudah tercatat di `docs/27` bagian 9: fold test
dipakai sebagai validation early stopping, dan barrier dihitung tanpa spread.

---

## 2. Yang Diperbaiki di Pelatihan Ulang

- **Sampel = hanya sinyal momentum_fib** (4.189), bukan semua bar
- **Label dihitung ulang** dari data fitur yang sudah benar (100% cocok)
- **SL/TP mengikuti sinyal masing-masing**, bukan angka tetap 4000/12000
- **Spread 260 pts dibayar di entry** saat menghitung barrier
- **Tiga bagian terpisah:** 55% train / 15% valid / **30% HOLDOUT disegel**
- **Early stopping memakai valid**, bukan holdout
- **Purge 48 bar** antar bagian (label bisa menjangkau 48 bar ke depan)

```
Train   : 2025-04-15 .. 2025-12-15   n=2.255
Valid   : 2025-12-22 .. 2026-02-09   n=  581
HOLDOUT : 2026-02-18 .. 2026-09-08   n=1.257   <- disegel
Base rate TP: 27,62%
```

---

## 3. Hasil: AUC Holdout 0,51 — Setara Acak

```
AUC train   : 0,8109   <- masih bisa menghafal
AUC valid   : 0,5614
AUC HOLDOUT : 0,5123   <- 0,50 = lempar koin
```

Pohon terpakai: **2**. Early stopping menghentikannya dari 600 ronde.

### Enam varian hiperparameter dicoba

| Varian | Pohon | AUC valid | **AUC HOLDOUT** |
|---|---|---|---|
| default (depth4, leaf15) | 2 | 0,5614 | 0,5123 |
| lebih dangkal (depth2, leaf4) | 9 | 0,6383 | 0,5108 |
| stump (depth1) | 1 | 0,5301 | **0,4817** |
| lr kecil (0,01) | 3 | 0,6609 | 0,5045 |
| **regularisasi kuat** | 23 | 0,6321 | **0,5539** |
| dalam (depth8, leaf63) | 3 | 0,5648 | 0,4940 |

Semuanya berkerumun di sekitar 0,50. Dua varian bahkan **di bawah** acak.

---

## 4. Varian Terbaik Diuji Lebih Jauh — dan Gugur

Varian regularisasi kuat (AUC 0,5539) dipakai sebagai filter trading:

```
baseline              n=190  E=+0,0151
buang 30% terendah    n=176  E=+0,3117  t=+2,28   <- terlihat hebat
buang 50% terendah    n=141  E=+0,0453
buang 70% terendah    n= 82  E=-0,0316
```

Terlihat menjanjikan di satu titik. Dua pemeriksaan menggugurkannya.

### a. Tidak monoton

Edge asli **menguat** saat disaring makin ketat. Ini tidak:

```
buang  0% : E=+0,0151
buang 10% : E=+0,0592
buang 20% : E=+0,2741
buang 30% : E=+0,3117   <- puncak
buang 40% : E=+0,1504
buang 50% : E=+0,0453
buang 60% : E=+0,0948
buang 70% : E=-0,0316   <- negatif
buang 80% : E=-0,0198
```

Naik lalu jatuh lalu negatif. Kalau model benar-benar bisa mengurutkan
kualitas sinyal, membuang yang terburuk selalu memperbaiki hasil. Pola ini
bentuk bukit acak.

### b. Berubah total hanya karena ganti seed

Varian "buang 30%" yang sama, hanya `seed` berbeda:

| seed | n | E[R] | t |
|---|---|---|---|
| 1 | 179 | +0,1413 | +1,08 |
| 7 | 187 | +0,2139 | +1,64 |
| **42** | 176 | **+0,3117** | +2,28 |
| 123 | 159 | **+0,0467** | +0,34 |
| 999 | 189 | +0,2411 | +1,85 |

Rentang **+0,047 sampai +0,312** — 6,7x lipat, hanya dari angka acak awal.
Seed 42 yang dilaporkan pertama kebetulan yang paling bagus.

Model yang menemukan pola nyata tidak berubah sebesar ini karena seed.

---

## 5. Perbandingan Langsung pada Holdout yang Sama

| | n | E[R] | t | WR |
|---|---|---|---|---|
| Baseline (semua sinyal) | 190 | +0,0151 | +0,12 | 26,8% |
| Filter ML (buang 30%) | 176 | +0,3117 | +2,28 | 34,7% |
| **Filter konfluensi (aturan)** | 165 | +0,0516 | +0,39 | 27,9% |

Angka ML memang lebih tinggi — tetapi angka itulah yang barusan terbukti
berubah 6,7x karena seed. Filter aturan tidak punya seed, tidak punya
hiperparameter, dan hasilnya sama setiap kali dijalankan.

---

## 6. Kenapa ML Gagal di Sini — Bukan Salah Modelnya

Tiga alasan struktural, semuanya sudah terukur di dokumen lain:

**a. Celahnya terlalu sempit.** `docs/06`: jarak entry acak (24,7%) ke
breakeven (25,4%) cuma **0,7 poin persentase**. Model harus akurat luar
biasa untuk melampaui itu — sementara AUC 0,51 berarti hampir tidak bisa
membedakan apa pun.

**b. Sampelnya terlalu sedikit.** 4.189 sinyal, dan yang benar-benar
dieksekusi 675 trade dalam 1,4 tahun. LightGBM dengan 58 fitur butuh jauh
lebih banyak untuk memisahkan pola dari noise. Bukti langsungnya: model
berhenti di 2 pohon.

**c. Fitur teratasnya volatilitas, bukan arah.** `h4_atr`, `h1_adx`,
`h4_adx`, `asia_range` — semua mengukur *seberapa besar gerakan*, bukan
*ke mana*. Itu konsisten dengan seluruh temuan proyek ini: yang bisa
diprediksi dari data ini adalah volatilitas, bukan arah.

---

## 7. Jawaban untuk Pemilik

**Modelnya sudah dipakai — untuk menjawab pertanyaan, bukan untuk trading.**

Yang dikerjakan ML di proyek ini bukan nol. Ia menjawab satu pertanyaan
penting dengan tegas: *apakah ada pola tersembunyi di data M5 yang belum
ditangkap aturan?* Jawabannya **tidak ada**, dan jawaban itu menghemat
waktu yang akan terbuang mengejar model yang lebih rumit.

Memakai model ber-AUC 0,51 untuk keputusan uang bukan "memanfaatkan ML" —
itu memasang generator angka acak di jalur order, dengan risiko nyata:

- Membuang sinyal bagus berdasarkan skor yang tidak bermakna
- Menambah satu titik kegagalan (model gagal dimuat = bot berhenti)
- Membuat hasil live tidak bisa ditelusuri (kenapa sinyal ini ditolak?)

### Kapan ML layak dicoba lagi

Urutan di `docs/29` tetap berlaku, dan pengujian hari ini menguatkannya:

1. **Forward test selesai** (~200 trade live)
2. **Filter konfluensi terbukti** di data live, bukan cuma backtest
3. **Sampel bertambah** — 675 trade terlalu sedikit; 2.000+ baru masuk akal
4. Baru setelah itu, ML sebagai penyaring di atas rule engine yang sudah
   terbukti punya edge

Sampai saat itu, yang menggantikan peran "prediksi" adalah **filter aturan
yang lolos holdout**: candle searah + ADX>25 + tren M5, t=3,14 (`docs/36`).
Bedanya, filter itu bisa dijelaskan, hasilnya sama setiap dijalankan, dan
tidak berubah karena seed.

---

## 8. Cara Mengulang

Skrip pelatihan ulang: `scripts/ml_uji_ulang.py`

```bash
python scripts/ml_uji_ulang.py            # latih + evaluasi holdout
python scripts/ml_uji_ulang.py --sweep    # sapuan hiperparameter
python scripts/ml_uji_ulang.py --seeds    # uji stabilitas seed
```

Skrip ini **tidak menyimpan model** dan tidak menyentuh jalur produksi.
