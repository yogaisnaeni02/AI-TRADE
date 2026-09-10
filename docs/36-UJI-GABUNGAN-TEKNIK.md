# Uji Gabungan Teknik: Candle, MACD, Bollinger, ADX, RSI, Stochastic

**Tanggal:** 10 September 2026
**Permintaan:** "implementasikan gabungan teknik — pattern candle, MACD,
Bollinger Bands, dll — yang bisa mendongkrak peluang dan bikin sistem lebih
konsisten tanpa merusak yang lainnya."

---

## Ringkasan

22 filter diuji di atas sinyal `momentum_fib` yang sudah ada. Satu kandidat
lolos seluruh pemeriksaan termasuk **holdout yang disegel**:

```
Candle searah + ADX > 25
```

| | Baseline | + Filter |
|---|---|---|
| Holdout E[R] | +0,0260 | **+0,1282** |
| Holdout winrate | 27,2% | **29,9%** |
| Holdout PF | 1,04 | **1,18** |
| Trade tersisa | — | **71%** |

**Belum diterapkan ke produksi.** Alasannya di bagian 6.

---

## 1. Desain yang Menjamin "Tanpa Merusak yang Lain"

Filter hanya boleh **membuang** sinyal. Tidak membuat sinyal baru, tidak
mengubah SL/TP/lot, tidak menyentuh logika arah. Sinyal yang lolos identik
dengan yang sekarang.

Konsekuensinya: risiko terburuk sebuah filter adalah **membuang trade bagus**
— bukan menciptakan perilaku baru yang belum teruji. Ini sengaja dipilih
supaya sistem yang sedang forward test tidak berubah karakternya.

---

## 2. Hasil Seluruh Filter (516 hari, 909 trade baseline)

Circuit breaker dimatikan saat mengukur — pelajaran dari `docs/31`, supaya
semua varian memperdagangkan rentang yang sama.

| Filter | n | E[R] | WR% | PF | dE |
|---|---|---|---|---|---|
| **BASELINE momentum_fib** | 909 | +0,0733 | 28,2 | 1,10 | — |
| Engulfing searah | 234 | +0,1993 | 31,2 | 1,29 | +0,126 |
| BB squeeze (width rendah) | 284 | +0,1494 | 30,3 | 1,21 | +0,076 |
| H4 selaras | 308 | +0,1011 | 28,9 | 1,14 | +0,028 |
| Candle searah | 831 | +0,0895 | 28,6 | 1,12 | +0,016 |
| ADX > 25 | 717 | +0,0863 | 28,6 | 1,12 | +0,013 |
| Bukan doji | 879 | +0,0831 | 28,4 | 1,12 | +0,010 |
| ADX > 20 | 828 | +0,0813 | 28,5 | 1,11 | +0,008 |
| BB belum ekstrem | 726 | +0,0814 | 28,7 | 1,11 | +0,008 |
| RSI searah | 905 | +0,0735 | 28,2 | 1,10 | +0,000 |
| Searah EMA200 | 906 | +0,0727 | 28,1 | 1,10 | −0,001 |
| Candle badan kuat | 579 | +0,0450 | 27,3 | 1,06 | −0,028 |
| RSI belum jenuh | 652 | +0,0442 | 27,8 | 1,06 | −0,029 |
| **MACD (3 varian)** | 732 | +0,0338 | 26,9 | 1,05 | **−0,040** |
| BB ekspansi | 784 | +0,0271 | 27,0 | 1,04 | −0,046 |
| Stoch belum jenuh | 517 | +0,0084 | 26,7 | 1,01 | −0,065 |

### Yang gagal, dan kenapa itu masuk akal

**MACD justru merugikan (−0,040R).** Ketiga varian MACD memberi hasil
identik — pertanda ketiganya menyaring sinyal yang sama. Penyebabnya: MACD
adalah indikator *lagging* berbasis crossover EMA, sedangkan `momentum_fib`
sudah memakai momentum(24) yang mengukur hal serupa lebih awal. MACD hanya
mengulang informasi yang sudah dipakai, sambil menunda entry.

**Stochastic paling buruk (−0,065R).** Stochastic dirancang untuk pasar
ranging; dipakai sebagai filter pada setup yang justru mencari kelanjutan
tren, ia membuang trade terbaik.

Pelajarannya: menumpuk indikator yang mengukur hal yang sama tidak menambah
informasi — hanya menambah keterlambatan.

---

## 3. Verifikasi Kandidat

Kandidat teratas WAJIB lewat pemeriksaan yang menggugurkan kandidat kemarin.

### Stabilitas belah dua

| Filter | Paruh-1 | Paruh-2 | Vonis |
|---|---|---|---|
| BASELINE | +0,081 | +0,066 | stabil |
| Engulfing searah | +0,297 | +0,079 | stabil |
| **BB squeeze** | +0,234 | **−0,059** | **BERLAWANAN — gugur** |
| H4 selaras | +0,025 | +0,197 | stabil |
| Candle searah | +0,066 | +0,113 | stabil |
| ADX > 25 | +0,043 | +0,127 | stabil |

**BB squeeze gugur di sini** — persis pola yang menggugurkan varian pullback
di `docs/31`. Angka +0,149R-nya adalah rata-rata dua paruh berlawanan.

### Walk-forward 5 fold

```
BASELINE          +0.24  -0.05  +0.22  -0.07  -0.02   -> 2/5
Engulfing searah  +0.44  +0.00  +0.40  -0.21  +0.23   -> 4/5   (n cuma 38-65/fold)
Candle searah     +0.27  -0.10  +0.30  -0.10  +0.01   -> 3/5
ADX > 25          +0.13  -0.10  +0.26  +0.08  -0.04   -> 3/5
```

### Kombinasi

| Kombinasi | n | E[R] | WR% | t |
|---|---|---|---|---|
| **Candle + ADX25** | **640** | **+0,1389** | 29,8 | **+1,99** |
| BBsqueeze + ADX25 | 179 | +0,2692 | 33,5 | +1,95 |
| Engulf + BBsqueeze | 69 | +0,2298 | 31,9 | +1,05 |
| Candle + BBsqueeze | 266 | +0,1296 | 30,1 | +1,19 |
| Engulf + H4 | 85 | +0,0129 | 25,9 | +0,07 |

`Candle + ADX25` menonjol bukan karena E[R] tertinggi, melainkan karena
**mempertahankan 640 dari 909 trade** sambil menaikkan expectancy hampir dua
kali lipat. Kombinasi ber-E[R] lebih tinggi menyisakan terlalu sedikit
sampel untuk dipercaya.

Engulfing sendiri menarik (4/5 fold) tetapi hanya menyisakan 234 trade —
38-65 per fold. Terlalu tipis untuk jadi filter utama.

---

## 4. Uji Holdout — Pemeriksaan Terpenting

22 filter diuji pada data yang sama lalu yang terbaik dipilih. Itu multiple
testing, dan angkanya pasti optimistis. Obatnya: data yang belum pernah
dipakai memilih.

Data dibelah **70% seleksi / 30% holdout disegel**.

| | Seleksi (70%) | HOLDOUT (30%) |
|---|---|---|
| Baseline E[R] | +0,0896 | +0,0260 |
| + Filter E[R] | +0,1426 | **+0,1282** |
| **Selisih** | **+0,0530** | **+0,1022** |
| Trade tersisa | 70% | 71% |

**Perbaikan di holdout (+0,102R) lebih besar daripada di periode seleksi
(+0,053R).** Ini pola yang meyakinkan — kebalikan dari artefak overfitting,
yang selalu menyusut di data baru.

### Kedua komponen menyumbang sendiri-sendiri

Di holdout, tanpa guardrail:

```
baseline      n=232  E=+0.0260  WR=27.2%
candle saja   n=212  E=+0.0519  WR=27.8%
adx saja      n=181  E=+0.1053  WR=29.3%
gabungan      n=164  E=+0.1282  WR=29.9%
```

Efeknya menumpuk, bukan satu komponen menyeret yang lain. Keduanya mengukur
hal berbeda: ADX = kekuatan tren, candle = konfirmasi arah pada bar entry.

---

## 5. Angka yang TIDAK Boleh Dipercaya dari Uji Ini

Pengukuran dengan guardrail produksi aktif menghasilkan baris ini:

```
[HOLDOUT] BASELINE  n=11  E=-1.0067  WR=0.0%  maxDD=21.7%
[HOLDOUT] + filter  n=125 E=+0.2702  WR=33.6% maxDD=15.7%
```

Terlihat seolah filter menyelamatkan sistem dari kehancuran. **Jangan pakai
angka ini.** Baseline kebetulan mengawali holdout dengan 11 SL beruntun
(7-16 April), circuit breaker tersentuh, lalu berhenti total untuk sisa 5
bulan. Itu artefak titik mulai, bukan properti filter.

Dicatat di sini supaya tidak dikutip belakangan sebagai bukti.

---

## 6. Kenapa Belum Diterapkan

Filter ini menjanjikan, tetapi **tidak diaktifkan sekarang**:

1. **`docs/29` melarang mengubah logika sinyal selama forward test.** Aturan
   itu dibuat justru untuk situasi seperti ini — temuan menarik di tengah
   jalan. Mengubah sekarang berarti forward test yang berjalan kehilangan
   arti, dan kita kembali ke nol sampel.

2. **t = 1,99, ambang Bonferroni untuk 22 uji adalah 2,69.** Holdout
   menguatkan, tetapi belum mencapai ambang yang jujur.

3. Forward test yang sedang berjalan baru mengumpulkan sedikit trade.
   Menumpuk perubahan di atas basis bukti yang belum matang adalah pola yang
   sudah beberapa kali menyesatkan proyek ini.

### Rencana

Terapkan **setelah forward test sekarang selesai** (~200 trade), sebagai
perubahan tunggal yang terisolasi, lalu ukur ulang. Sampai saat itu, filter
ini tercatat sebagai kandidat terkuat yang pernah lolos holdout.

Bila pemilik ingin lebih cepat: jalankan sebagai **bot kedua di akun demo
terpisah** dengan filter aktif, paralel dengan yang sekarang. Dua-duanya
mengumpulkan sampel, tidak ada yang dikorbankan.

---

## 7. Catatan Metode

Kesalahan yang dihindari di uji ini, semuanya pernah terjadi sebelumnya:

- **Circuit breaker dimatikan saat mengukur** (`docs/31`) — kalau tidak,
  varian dibandingkan pada rentang waktu berbeda
- **Stabilitas belah dua diperiksa** — menggugurkan BB squeeze
- **Holdout disegel** — satu-satunya obat untuk multiple testing
- **n diperhatikan, bukan cuma E[R]** — filter ber-E[R] tinggi yang
  menyisakan 69 trade tidak berguna
- **Artefak titik-mulai diidentifikasi dan dibuang** (bagian 5)
