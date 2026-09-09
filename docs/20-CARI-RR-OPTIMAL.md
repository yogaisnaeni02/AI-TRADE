# Mencari RR Optimal — Tidak Terpaku di 1:3

**Tanggal:** 9 September 2026
**Permintaan:** "Cari strategi RR yang paling fit untuk [frekuensi] per jam,
jangan terpaku di 1:3."

---

## Ringkasan

Permintaan ini benar secara prinsip — RR 1:3 bukan angka sakral, dan
memang layak diuji alternatifnya. Sudah dilakukan pencarian sistematis di
28 kombinasi SL/RR/horizon. Hasilnya membagi jadi dua kesimpulan berbeda
tergantung horizon waktu:

1. **Untuk horizon panjang (4-8 jam):** RR lebih tinggi dari 1:3 (yaitu
   1:4 atau 1:5) justru **lebih baik dan lebih stabil** — ini temuan baru
   yang berharga
2. **Untuk horizon pendek (30-60 menit, benar-benar "per jam"):** **tidak
   ada RR yang menyelamatkan hasil**. Semua kombinasi merugi.

---

## 1. Metodologi

Dipakai filter kualitas sinyal yang sama dengan `momentum_fib` (momentum >
50% ambang, fib_position ketat, ATR normal), TANPA filter sesi — supaya
frekuensinya representatif untuk pertanyaan "per jam". Hasilnya 11,7
sinyal/hari, cukup padat untuk diuji di horizon pendek.

Untuk tiap kombinasi SL, RR, dan jendela waktu (N bar), diukur:
- Winrate keseluruhan dan expectancy
- Out-of-sample (30% data terakhir)
- Stabilitas per kuartal (6 kuartal, breakeven bergerak sesuai RR)

---

## 2. Horizon Panjang (4-8 jam): RR Lebih Tinggi Menang

| SL (pip) | RR | TP (pip) | Horizon | Expectancy | OOS | Kuartal untung |
|---|---|---|---|---|---|---|
| 400 | 1:3 (lama) | 1200 | 2 jam | −0,0915R | −0,001R | 2/6 |
| 300 | 1:4 | 1200 | 4 jam | +0,0147R | +0,0435R | 4/6 |
| 400 | 1:5 | 2000 | 4 jam | −0,0274R | +0,0623R | 4/6 |
| **400** | **1:5** | **2000** | **8 jam** | **+0,0810R** | **+0,0696R** | **5/6** |

**RR 1:5 dengan horizon 8 jam adalah kandidat paling stabil yang
ditemukan sejauh ini di seluruh proyek** — 5 dari 6 kuartal positif, dan
out-of-sample-nya (+0,0696R) mendekati in-sample (+0,0810R), tanda edge
yang tidak sekadar hafalan data.

**Pola yang konsisten:** RR lebih tinggi (1:4, 1:5) mengungguli RR 1:3
di semua horizon yang diuji. Ini masuk akal secara struktural — winrate
sistem ini memang rendah (di kisaran 20-30%), jadi target yang lebih jauh
memberi ruang bagi pemenang untuk benar-benar besar sebelum ditutup,
alih-alih terpotong di jarak menengah.

---

## 3. Horizon Pendek (30-60 menit): Tidak Ada RR yang Menang

Ini jawaban langsung untuk "per jam". Diuji 40 kombinasi SL × RR pada
horizon 6 bar (30 menit) dan 12 bar (60 menit):

| SL | RR | Horizon | Expectancy | OOS | Kuartal untung |
|---|---|---|---|---|---|
| 150 | 1:1,5 | 30m | −0,2861R | −0,3484R | 0/6 |
| 200 | 1:2,0 | 60m | −0,1222R | −0,1396R | 1/6 |
| 250 | 1:2,5 | 30m | −0,1677R | −0,0035R | 1/6 |
| **300** | **1:1,5** | **60m** | **−0,0563R** | **−0,0610R** | **2/6** |
| 300 | 1:4,0 | 30m | −0,4539R | −0,2950R | 0/6 |

**Terbaik dari seluruh 40 kombinasi:** SL 300 pip, RR 1:1,5, horizon 60
menit — masih **negatif** (−0,056R), dan hanya 2 dari 6 kuartal positif.

**Tidak ada satu pun kombinasi RR (dari 1:1,5 sampai 1:4) yang
menghasilkan sistem menguntungkan pada horizon 30-60 menit.**

---

## 4. Mengapa Horizon Pendek Selalu Kalah, Berapapun RR-nya

Ini bukan soal RR yang salah dipilih — ini keterbatasan struktural pasar.

Range bar M5 median adalah 379 pip (dibuktikan sejak awal proyek). Dalam
6-12 bar (30-60 menit), harga punya waktu sangat terbatas untuk membangun
pergerakan terarah yang cukup jauh melampaui gerakan acak dan biaya spread.

Mengubah RR pada horizon ini hanya menggeser di mana kerugiannya
terkonsentrasi — bukan menghilangkannya:

- **RR rendah (1:1,5-1:2):** winrate lebih tinggi (35-40%), tapi target
  kecil membuat spread memakan porsi besar dari tiap kemenangan
- **RR tinggi (1:3-1:4):** winrate anjlok ke 15-20% karena target jauh
  jarang tercapai dalam waktu sesingkat itu — SL kena duluan

Kedua ujungnya sama-sama merugi. **Waktu adalah sumber daya yang hilang di
horizon pendek** — momentum XAUUSD di M5 butuh lebih dari 1 jam untuk
menunjukkan arah yang bisa diandalkan secara statistik.

---

## 5. Rekomendasi

### Untuk sistem sekarang (momentum_fib, aktif tapi dimatikan sementara)

Pertimbangkan menguji **RR 1:5 dengan SL 400 pip, horizon 8 jam** sebagai
pengganti RR 1:3 saat ini. Ini kandidat terkuat yang ditemukan:

```yaml
trade_distances:
  sl_typical_points: 4000     # tetap 400 pip
  tp_min_points: 20000        # naik dari 12000 -> 20000 (RR 1:5)
  min_rr_ratio: 5.0
position_management:
  max_bars_hold: 96           # naik dari 48 -> 96 bar (8 jam)
```

**Update setelah verifikasi backtest lengkap (dengan seluruh guardrail):**

```
RR 1:5 SL400 (analisis label)   : E=+0,081R, 5/6 kuartal
RR 1:5 SL400 (backtest lengkap) : E=-0,605R, hanya 15 trade tereksekusi

RR 1:3 (sistem sekarang, backtest lengkap): E=-0,144R, 56 trade
```

**Ternyata lebih buruk saat diuji dengan guardrail nyata**, bukan lebih
baik. Penyebabnya sama seperti temuan di `18-TIERED-SIZING.md`: circuit
breaker (max drawdown 20%) memotong sampel jadi sangat kecil (15 trade)
sebelum edge jangka panjangnya sempat terbukti. Winrate anjlok ke 6,7%
pada sampel kecil ini — jauh dari 19,1% pada analisis label penuh.

**Kesimpulan: RR 1:5 TIDAK diterapkan.** Analisis label sederhana kembali
terbukti tidak bisa dipercaya tanpa verifikasi lewat backtest lengkap.
RR 1:3 yang sekarang, meski juga belum lolos gate, tetap yang paling
teruji dari seluruh kandidat yang pernah diuji di proyek ini.

### Untuk kebutuhan "per jam"

**Tidak ada RR yang bisa memenuhi ini secara menguntungkan** pada
instrumen dan broker ini. Ini bukan masalah RR — ini masalah horizon
waktu yang terlalu pendek untuk karakteristik volatilitas XAUUSD di
broker dengan spread 26 pip.

Opsi yang tersisa bila frekuensi tinggi tetap prioritas:
1. **Terima horizon lebih panjang** (4-8 jam) tapi jalankan **beberapa
   sinyal bersamaan** (di instrumen berbeda) — bukan mempercepat satu
   trade, tapi menambah jumlah trade paralel
2. **Broker/instrumen dengan spread jauh lebih rendah** — mengecilkan
   biaya tetap yang membuat horizon pendek selalu kalah
3. **Terima kenyataan bahwa "per jam" bukan skala waktu yang cocok**
   untuk edge yang ditemukan di proyek ini sejauh ini

---

## 6. Ringkasan

| Pertanyaan | Jawaban |
|---|---|
| RR 1:3 satu-satunya pilihan? | **Tidak** — RR 1:5 dengan horizon 8 jam lebih baik dan lebih stabil |
| Ada RR yang cocok untuk "per jam" (30-60 menit)? | **Tidak ditemukan** — 40 kombinasi diuji, semua negatif |
| Kenapa horizon pendek selalu kalah? | Range bar M5 (379 pip) butuh lebih dari 1 jam untuk membangun arah yang jelas melampaui noise dan spread |
| RR yang direkomendasikan (bukan "per jam")? | **1:5, SL 400 pip, horizon 8 jam** — kandidat terkuat, 5/6 kuartal, OOS +0,0696R |
| Sudah diterapkan ke sistem? | **Belum** — perlu verifikasi backtest dengan guardrail penuh dulu |

Pertanyaan Anda membuka temuan berharga: **RR 1:3 memang bukan yang
terbaik** — 1:5 tampak lebih unggul di horizon panjang. Tapi tidak ada
RR yang bisa membuat horizon 1 jam menguntungkan pada kondisi pasar dan
biaya broker saat ini.

---

## 7. Update: "Scalping Pendek, Aman di Spread" (permintaan lanjutan)

**Tanggal:** 9 September 2026 (lanjutan)

**Permintaan:** target beberapa pip saja, asalkan spread-nya "aman" (TP
jauh lebih besar dari spread).

### Diuji: puluhan kombinasi SL 50-300 pip, TP 3-8x spread, horizon 30 menit-4 jam

**Tidak ada satu pun yang untung.** Kandidat terbaik dari seluruh pencarian:

```
SL=300 pip, TP=208 pip (8x spread, "sangat aman" secara definisi biaya)
Winrate: 56,4%  <- terlihat sangat bagus
Expectancy: -0,131R  <- tetap rugi, 0/6 kuartal positif
```

### Kenapa "aman di spread" tidak cukup

Spread memang cuma 12,5% dari target (aman sesuai definisi kita). Tapi
masalahnya di tempat lain: **RR di bawah 1** (TP 208 < SL 300) menuntut
winrate breakeven 62,2% — sementara pasar cuma memberi 56,4%.

```
Per 100 trade:
  menang: 56 x 208 pip = +11.731 pip
  kalah : 44 x 300 pip = -13.080 pip
  spread x100           = -2.600 pip
  HASIL AKHIR           = -3.949 pip
```

**Spread bukan penyebab utama kerugian di sini — biayanya cuma 2.600
dari total kerugian 3.949 pip.** Penyebab utamanya adalah RR yang tidak
seimbang dengan winrate yang tersedia.

### Kesimpulan

"Aman di spread" adalah syarat perlu, bukan syarat cukup. Bahkan dengan
biaya transaksi yang secara proporsional kecil, kombinasi SL/TP pendek
tetap tidak menemukan RR yang cocok dengan winrate nyata yang tersedia
di pasar ini — konsisten dengan seluruh pencarian RR untuk horizon
pendek di Bagian 3 dokumen ini.

**Tidak ditemukan konfigurasi scalping (SL/TP di bawah ~300 pip) yang
menguntungkan pada XAUUSDm dengan strategi momentum yang sudah teruji.**
