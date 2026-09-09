# Frekuensi Sinyal dan Target 10% per Hari

**Tanggal:** 9 September 2026
**Permintaan:** "Buat jadi per 15 menit ada beberapa sinyal, karena target
per hari 10%."

---

## Bagian 1: Mengapa Bot Belum Trading

Bot berjalan dengan benar. Yang terjadi:

```
Waktu saat itu : 12:30 WIB
Sesi           : asia
Boleh trading  : TIDAK
```

Setup `momentum_fib` hanya aktif di sesi berikut (WIB):

| Sesi | Waktu |
|---|---|
| london_ny | 19:30 – 23:00 |
| ny_afternoon | 23:00 – 04:00 |
| rollover | 04:00 – 06:00 |

Menjalankan bot siang hari berarti bot menunggu — itu perilaku yang benar,
bukan kerusakan.

### Sinyal menggerombol

```
Rata-rata      : 2,75 sinyal per hari
Jeda terpanjang: 18,8 hari tanpa sinyal
```

Sinyal tidak tersebar merata. Ada hari dengan beberapa sinyal, lalu jeda
panjang. Nol sinyal dalam seminggu adalah kejadian normal.

### Perbaikan yang ditambahkan

**Heartbeat status** — bot melaporkan kondisinya tiap jam:

```
[status] 12:30 WIB | sesi asia — di luar jam trading,
         menunggu (london_ny 19:30, ny 23:00 WIB)

[status] 20:15 WIB | sesi london_ny AKTIF —
         belum: momentum (1.2<3.6), fib 0.61<0.75
```

Sekarang terlihat bot hidup dan sedang menunggu syarat yang mana.

**Lock file** — mencegah dua bot berjalan bersamaan. Terdeteksi ada dua
proses aktif (mode ADVISOR dan EXECUTOR sekaligus). API MetaTrader5 hanya
mengizinkan satu koneksi per terminal; dua bot bersamaan menyebabkan
kegagalan yang sulit didiagnosis.

---

## Bagian 2: Target 10% per Hari

### Berapa trade yang dibutuhkan

Expectancy terbaik sistem ini: **+0,033R per trade** (terukur pada 8.971
sampel).

| Risiko/trade | Hasil per trade | Trade dibutuhkan/hari |
|---|---|---|
| 1% | 0,033% | **303** |
| 2% | 0,066% | **152** |
| 3% | 0,099% | **101** |
| 5% | 0,165% | **61** |

Sinyal yang tersedia: **2,75 per hari.**

Bahkan pada risiko 5% — tingkat yang sudah membawa peluang bangkrut 56% —
dibutuhkan 61 trade per hari. Selisihnya lebih dari 20 kali lipat.

### Kalau 10%/hari tercapai

Modal Rp 3.700.000:

| Hari | Modal |
|---|---|
| 7 | Rp 7.210.253 |
| 30 | Rp 64.562.788 |
| 60 | Rp 1.126.582.066 |
| 90 | **Rp 19.658.183.664** |

Dari Rp 3,7 juta menjadi Rp 19,6 miliar dalam tiga bulan. Ini bukan target
yang ambisius — ini angka yang tidak ada dalam kenyataan pasar mana pun.

---

## Bagian 3: Memperbanyak Sinyal Merusak Kualitasnya

Filter bisa dilonggarkan agar sinyal lebih sering muncul. Konsekuensinya
terukur:

| Filter | Sinyal/hari | Winrate | vs breakeven (25,41%) |
|---|---|---|---|
| **Semua 4 filter (sekarang)** | **2,7** | **32,25%** | **+6,84%** |
| Tanpa filter sesi | 6,7 | 27,35% | +1,94% |
| Tanpa filter ATR | 13,2 | 26,26% | +0,85% |
| Momentum saja | 25,4 | 24,60% | **−0,81%** |
| Tanpa filter apa pun | 167,2 | 23,65% | **−1,76%** |

**Hubungannya berbanding terbalik.** Setiap filter yang dilepas menambah
jumlah sinyal sekaligus menurunkan winrate.

Dua baris terakhir sudah di bawah breakeven — sistem merugi secara sistematis.

### Angka yang menentukan

Untuk mendapat "beberapa sinyal per 15 menit" (sekitar 96 sinyal per hari),
seluruh filter harus dilepas. Pada titik itu winrate turun ke 23,65% —
**1,76 poin di bawah breakeven.**

Hasilnya bukan profit lebih cepat, melainkan kerugian lebih cepat: setiap
trade rugi rata-rata 0,119R, dikalikan 96 trade per hari.

---

## Bagian 4: Yang Realistis

Dengan sistem ini apa adanya:

| Metrik | Nilai |
|---|---|
| Sinyal | 2,75/hari (menggerombol, bisa jeda berhari-hari) |
| Trade tereksekusi | 1–2/hari (setelah risk limit) |
| Expectancy | +0,033R per trade |
| Hasil per hari (risiko 1%) | sekitar **+0,03–0,07%** |
| Hasil per bulan | sekitar **+1–2%** |

Angka ini jauh dari 10% per hari. Tetapi angka ini yang terukur, dan
strategi ini pun **belum lolos validasi penuh** (4/5 fold walk-forward).

### Perbandingan skala

| Sumber | Return |
|---|---|
| Deposito bank | ~4% per tahun |
| Reksa dana saham (baik) | ~15% per tahun |
| Hedge fund papan atas | 20–40% per tahun |
| **Target 10% per hari** | **~3.700.000% per tahun** |

---

## Bagian 5: Yang Bisa Dilakukan

### Menaikkan frekuensi tanpa merusak kualitas

Satu-satunya cara: **temukan setup lain yang juga punya edge**, lalu
jalankan bersamaan. Bukan melonggarkan filter setup yang ada.

Sudah diuji dan gagal: london_sweep, ny_momentum, ny_vol_window. Kandidat
yang belum diuji: order block retest, breakout dengan konfirmasi volume,
mean reversion sesi Asia.

### Menaikkan hasil per trade

| Cara | Dampak |
|---|---|
| Akun spread rendah (Raw/Zero) | Expectancy +33% sampai +48% |
| Instrumen lain (EURUSD) | Rasio ATR/spread lebih baik |
| Timeframe lebih tinggi | Noise lebih rendah |

### Menaikkan risiko per trade

Bisa, tetapi berbayar mahal:

| Risiko | Return/bulan | Peluang bangkrut |
|---|---|---|
| 1% (sekarang) | ~1–2% | mendekati 0% |
| 3% | ~4–6% | 43% |
| 5% | ~7–10% | 56% |

Menaikkan risiko mempercepat hasil di kedua arah — termasuk arah kehilangan
modal.

---

## Ringkasan

| Pertanyaan | Jawaban |
|---|---|
| Kenapa bot belum trading? | Di luar jam sesi (sekarang siang, sesi mulai 19:30 WIB) |
| Bot rusak? | Tidak — 2 bot berjalan bersamaan, sudah diperbaiki dengan lock file |
| Bisa dibuat beberapa sinyal per 15 menit? | Bisa, tetapi winrate turun ke bawah breakeven |
| Target 10%/hari tercapai? | Butuh 303 trade/hari; tersedia 2,75 |
| Realistisnya berapa? | 1–2% per bulan, dan itu pun belum tervalidasi penuh |

Frekuensi sinyal bukan tuas yang bisa diputar bebas. Ia adalah **hasil** dari
seberapa selektif filter bekerja — dan selektivitas itulah satu-satunya
sumber edge yang dimiliki sistem ini.
