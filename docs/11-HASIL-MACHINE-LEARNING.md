# Hasil Machine Learning: Meta-Labeling

**Tanggal:** 9 September 2026
**Model:** LightGBM, 58 fitur, 86.279 sampel berlabel
**Kesimpulan:** Model tidak menemukan pola yang bertahan di luar sampel

---

## 1. Ringkasan

ML dikerjakan sebagai jalan terakhir untuk melampaui celah 0,9% antara
entry acak (24,5%) dan breakeven (25,4%). Hasilnya: **model tidak menemukan
sinyal apa pun yang berulang.**

```
AUC in-sample     : 0,9829   <- model BISA menghafal data
AUC out-of-sample : 0,5089   <- setara tebakan acak
```

Kesenjangan ini adalah diagnosis yang jelas. Model punya kapasitas belajar
yang cukup (terbukti bisa menghafal hingga AUC 0,98), tetapi tidak ada pola
yang berulang untuk dipelajari. Yang dihafalnya adalah noise.

---

## 2. Persiapan Data

### Triple-barrier labeling

```
SL       : 400 pip
TP       : 1.200 pip (RR 1:3)
Timeout  : 48 bar (4 jam)
Arah     : mengikuti trend_htf
```

Hasil pada 100.000 bar M5:

| Outcome | Jumlah | Persentase |
|---|---|---|
| TP duluan (label 1) | 20.409 | 23,7% |
| SL duluan (label 0) | 62.143 | 72,0% |
| Timeout (label 0) | 3.727 | 4,3% |

Baseline: **23,65%**. Model harus melampaui ini secara konsisten.

### Fitur

58 fitur numerik. Yang **dikeluarkan** dan alasannya:

| Dikeluarkan | Alasan |
|---|---|
| Harga mentah (OHLC, EMA, BB) | Nilainya bergeser terus ($1.800 → $4.400); model tak bisa menggeneralisasi |
| Label, outcome, exit_bars | Informasi masa depan |
| MACD mentah | Berskala harga, sudah diwakili `macd_hist_atr` |
| `mom_24_q85` | Ambang, bukan sinyal |

Yang **dipertahankan**: semua yang dinormalisasi ATR (momentum, jarak),
rasio (fib_position, body_ratio, bb_pct_b), osilator (RSI, ADX, Stochastic),
konteks waktu dan sesi.

---

## 3. Hasil Walk-Forward

Lima fold dengan purge gap 100 bar:

| Fold | Periode uji | Baseline | AUC | Winrate top-10% |
|---|---|---|---|---|
| 1 | Jul–Sep 2025 | 17,2% | 0,5102 | 12,9% |
| 2 | Sep–Des 2025 | 26,4% | 0,5376 | 25,9% |
| 3 | Des–Mar 2026 | 25,5% | 0,4981 | 28,6% |
| 4 | Mar–Jun 2026 | 23,9% | 0,5032 | 23,5% |
| 5 | Jun–Sep 2026 | 25,2% | 0,4954 | 23,3% |

**AUC rata-rata: 0,5089.**

Kolom terakhir paling menentukan: bahkan pada 10% sinyal dengan probabilitas
tertinggi menurut model, winrate tidak lebih baik dari baseline. Di fold 1
bahkan jauh lebih buruk (12,9% vs 17,2%).

### Evaluasi threshold

| Threshold | Winrate | Expectancy | Fold positif |
|---|---|---|---|
| 0,25 | 21,0% | −0,227R | 0/4 |
| 0,30 | 22,5% | −0,167R | 1/2 |

Tidak ada threshold yang menghasilkan winrate di atas breakeven 25,4%.

---

## 4. Masalah Teknis yang Ditemukan dan Diperbaiki

### Sample weight menghentikan training

Bobot berdasar tumpang tindih label (López de Prado) membuat model berhenti
di iterasi **1**. Tanpa bobot, training berjalan normal hingga 94 iterasi.

| Konfigurasi | AUC | Iterasi |
|---|---|---|
| Dengan sample weight | 0,4988 | **1** |
| Tanpa sample weight | 0,5064 | 94 |

Penyebabnya: bobot rata-rata sangat kecil (1/overlap, dengan overlap hingga
48), sehingga sinyal gradien tenggelam. Bobot dinonaktifkan untuk pengujian
berikutnya.

Perbaikan ini menaikkan AUC dari 0,4988 ke 0,5089 — tetap tidak bermakna.

---

## 5. Pendekatan Alternatif yang Dicoba

Semua diuji untuk memastikan hasil nol bukan karena framing yang keliru:

| Pendekatan | Baseline | AUC | Hasil |
|---|---|---|---|
| Semua bar, RR 1:3, 48 bar | 23,7% | 0,5089 | Tidak ada sinyal |
| **Hanya sinyal rule engine** (meta-labeling sejati) | 32,2% | **0,4313** | Lebih buruk dari acak |
| Horizon 96 bar (8 jam) | 25,2% | 0,4840 | Tidak ada sinyal |
| Horizon 192 bar (16 jam) | 25,6% | 0,4988 | Tidak ada sinyal |
| Target lebih mudah (RR 1:1) | 48,8% | 0,5072 | Tidak ada sinyal |

**Lima framing berbeda, semuanya AUC ~0,50.** Ini bukan kebetulan atau
kesalahan konfigurasi — ini kesimpulan yang konsisten.

---

## 6. Fitur Terpenting (dan Mengapa Itu Menjelaskan Kegagalan)

| Peringkat | Fitur | Gain |
|---|---|---|
| 1 | h4_atr | 221 |
| 2 | atr_pct | 108 |
| 3 | mom_3 | 70 |
| 4 | bb_width | 67 |
| 5 | fib_dist_618 | 64 |

Empat dari lima fitur teratas adalah **ukuran volatilitas** (ATR, bandwidth),
bukan penunjuk arah.

Ini masuk akal sekaligus mengungkap masalahnya: volatilitas memang
memengaruhi apakah TP 1.200 pip tercapai dalam 4 jam — tetapi itu memprediksi
**apakah harga bergerak jauh**, bukan **ke arah mana**. Untuk trading
berarah, informasi itu tidak cukup.

Model pada dasarnya belajar "kapan pasar sedang bergerak besar", yang tidak
sama dengan "kapan trade akan menang".

---

## 7. Apa Artinya

### Yang terbukti

Setelah menguji indikator klasik (MACD, RSI, Stochastic, Bollinger),
konsep struktur (BOS, CHoCH, liquidity sweep), Fibonacci, momentum
multi-horizon, analisis sesi, dan sekarang machine learning dengan lima
framing berbeda:

> **Tidak ditemukan edge yang bertahan out-of-sample pada XAUUSDm M5 di
> broker ini.**

Ini bukan kegagalan implementasi. Setiap komponen diverifikasi bekerja:
data bersih 99,995%, backtester memodelkan biaya realistis, eksekusi order
terbukti di akun nyata. Yang tidak ditemukan adalah polanya.

### Mengapa masuk akal

Celahnya memang sangat sempit:

```
Winrate entry acak  : 24,5%
Breakeven winrate   : 25,4%
Selisih             :  0,9 poin persentase
```

Spread 26 pip menempatkan sistem 0,9% di bawah impas sebelum strategi apa pun
diterapkan. Melampauinya menuntut prediksi yang lebih baik daripada yang
tersedia dari data OHLCV M5.

Pasar XAUUSD di timeframe ini praktis efisien terhadap informasi yang bisa
diekstrak dari harga historis saja.

---

## 8. Pilihan yang Tersisa

### A. Kurangi biaya — membantu, tetapi tidak menyelesaikan

Perhitungan ulang dengan angka terukur (winrate entry acak 23,65%):

| Akun | Spread | Breakeven WR | Expectancy | Celah |
|---|---|---|---|---|
| Standard (sekarang) | 26 pip | 25,41% | −0,119R | 1,76% |
| Raw Spread | 15 pip | 25,24% | −0,091R | 1,58% |
| Zero | 10 pip | 25,16% | −0,079R | 1,50% |
| Teoretis tanpa spread | 0 pip | 25,00% | −0,054R | 1,35% |

**Spread bukan penyebab utamanya.** Bahkan tanpa spread sama sekali, entry
acak tetap merugi — karena barrier SL 400 pip lebih sering tersentuh lebih
dulu daripada TP 1.200 pip.

Menurunkan spread hanya memangkas celah dari 1,76% ke 1,50%. Membantu, tetapi
edge tetap harus datang dari kualitas sinyal.

**Namun** — dan ini yang penting — bila edge sudah ada, spread rendah
memperbesarnya secara nyata:

| Akun | Expectancy dengan edge momentum (WR 28,7%) |
|---|---|
| Standard 26 pip | **+0,083R** |
| Raw Spread 15 pip | **+0,110R** (+33%) |
| Zero 10 pip | **+0,123R** (+48%) |

Jadi urutannya: temukan edge dulu, lalu pindah ke akun spread rendah untuk
memperbesarnya. Bukan sebaliknya.

### B. Ganti instrumen

EURUSD memiliki rasio ATR-terhadap-spread jauh lebih baik. Sudah diukur:
risiko 0,6% per trade pada modal Rp 800.000, dibanding 14,3% untuk XAUUSD.

Ini juga menyelesaikan masalah modal minimum Rp 3,7 juta.

### C. Timeframe lebih tinggi

Rasio sinyal terhadap noise meningkat di H1/H4, dan spread menjadi porsi
yang jauh lebih kecil dari target. Data H1 tersedia 12,6 tahun dan H4 9 tahun
— jauh lebih banyak dari M5.

### D. Data di luar OHLCV

Order book, tick data, kalender ekonomi terstruktur, sentimen. Semua di luar
jangkauan API MT5 standar, tetapi inilah yang dipakai institusi untuk
menemukan edge yang tidak terlihat di chart.

---

## 9. Yang Tetap Bernilai

Seluruh infrastruktur tetap terpakai apa pun arah berikutnya:

| Komponen | Status |
|---|---|
| Pipeline data (download, validasi, resample) | Terverifikasi |
| 88 fitur, termasuk MACD/Fibonacci/momentum | Selesai |
| Backtester dengan biaya realistis | Terverifikasi |
| Risk manager + circuit breaker | Semua guardrail teruji |
| Order manager | Order terkirim di akun nyata |
| Kerangka labeling & walk-forward ML | Selesai |
| Dashboard, journal, kill switch | Selesai |

Menguji instrumen atau broker baru sekarang hanya perlu mengubah konfigurasi
dan menjalankan ulang pipeline — bukan membangun ulang apa pun.

Temuan negatif ini juga bernilai: ia diperoleh di backtest dan demo, bukan
setelah modal hilang di akun nyata. Itulah fungsi gerbang bertahap yang
dipakai sejak awal.
