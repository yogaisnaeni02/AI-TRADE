# Hasil Kalibrasi Ulang Setelah Perbaikan Waktu

**Tanggal:** 10 September 2026
**Prasyarat:** `docs/27-AUDIT-TEMUAN.md` — data historis meleset 7 jam,
sudah diperbaiki oleh `scripts/fix_time_offset.py`.

Seluruh angka di dokumen `docs/` sebelum ini **batal**. Angka di sini adalah
pengukuran pertama yang dilakukan pada data berlabel waktu yang benar.

---

## 1. Setelan yang dipakai sekarang

| Parameter | Nilai | Sebelumnya |
|---|---|---|
| `momentum_fib.atr_percentile_min/max` | **0,20 / 0,95** | 0,30 / 0,85 |
| `trade_distances.min_rr_ratio` | **2,78** | 3,0 |
| `trade_distances.tp_min_points` | **11120** | 12000 |
| Sesi | **semua (24 jam)** | ny_afternoon, london_ny, rollover |
| `per_trade.max_risk_percent` | **1,35** | 1,0 (tidak pernah berlaku) |
| `max_bars_hold` backtest | **48** (ikut config) | 120 (hardcode) |

Hasil dari config apa adanya, M5, 1,41 tahun:

```
sinyal 4.743 -> trade 513
E[R]  = +0,1749R    SE = 0,0779    t = 2,25
winrate 31,77%      (breakeven RR 1:2,78 = 28,17%)
profit factor 1,31  trade/tahun 363
```

---

## 2. Kenapa gate ATR dilonggarkan

Masalah utamanya bukan edge, melainkan **frekuensi**. Pada setelan lama
momentum_fib hanya menghasilkan 106 trade dalam 1,41 tahun. Pada laju itu:

| kalau edge sebenarnya | butuh | setara |
|---|---|---|
| +0,05R | 8.595 trade | ~115 tahun |
| +0,10R | 2.149 trade | ~29 tahun |
| +0,15R | 955 trade | ~13 tahun |

Setup sebagus apa pun tidak berguna kalau tidak pernah bisa dibuktikan.

Penyebab jumlah trade kecil BUKAN guardrail dan BUKAN holding period —
keduanya sudah diuji dan tidak berpengaruh. Penyebabnya sinyal yang
**menggerombol**: median jarak antar sinyal 1 bar, dan 3.123 dari 3.381
sinyal muncul dalam 48 bar setelah sinyal sebelumnya. momentum_fib
menghasilkan ~259 episode momentum, bukan 3.382 peluang independen.

### Sapuan pelonggaran (M5, RR 1:2,78)

| varian | n | E[R] | t | WR% |
|---|---|---|---|---|
| baseline (ATR 0,30-0,85) | 107 | −0,0104 | −0,07 | 29,91 |
| **ATR 0,20-0,95** | **512** | **+0,1618** | **2,05** | 30,86 |
| momentum 0,35x | 265 | +0,1074 | 0,99 | 30,19 |
| ATR longgar + mom 0,35x | 542 | +0,1478 | 1,93 | 30,26 |
| fib 0,65/0,35 | 107 | −0,0401 | −0,25 | 28,04 |
| semua sangat longgar | 31 | −0,3735 | −1,41 | 16,13 |

Dua hal penting dari tabel ini:

1. Melonggarkan gate ATR menaikkan trade **5x** dan expectancy **ikut naik**.
   Itu menandakan rentang lama membuang peluang bagus, bukan menyaring yang
   jelek.
2. Melonggarkan gate LAIN tidak menambah apa pun, dan melonggarkan semuanya
   sekaligus justru hancur (WR 15,6%). Jadi spesifik gate ATR yang salah
   kalibrasi — bukan "makin longgar makin bagus".

### Kenapa RR 1:2,78 dan bukan 1:3

RR efektif setelah spread 260 points, pada SL 4000:

| RR nominal | RR efektif | breakeven WR |
|---|---|---|
| 1:3,00 | 2,756 | 26,62% |
| 1:2,78 | 2,549 | 28,17% |

Breakeven WR naik 1,55pp, tapi TP yang lebih dekat lebih sering tercapai
dan efek bersihnya positif: t naik dari 1,81 ke 2,05 pada varian terpilih.

---

## 3. Batas kepercayaan — WAJIB dibaca sebelum menaikkan risiko

Dua hal yang membuat angka di atas **belum** layak disebut bukti.

### 3.1 Multiple testing

`t = 2,25` diperoleh setelah menguji **22 kombinasi** (11 varian × 2 RR)
pada data yang sama, lalu mengambil yang terbaik. Dengan 22 percobaan,
mendapat t ≈ 2 secara kebetulan itu **wajar**. Ambang jujurnya sekitar
**t ≥ 2,9** (koreksi Bonferroni).

Ini pola yang sama yang membuat proyek ini nyasar sebelumnya: kriteria
"4 dari 5 fold positif" atas 11 konfigurasi punya 89,8% peluang lolos
secara kebetulan.

### 3.2 GAGAL di M15

Diuji pada M15 (4,23 tahun, 2022–2026 — data yang **tidak** dipakai memilih
varian ini):

| SL | baseline | ATR 0,20-0,95 |
|---|---|---|
| 3500-4500 (warisan M5) | −0,331 | −0,452 |
| 2500-3200 (proporsional ATR M15) | −0,203 | **−0,141** |
| 2000-2600 | −0,272 | −0,242 |

Negatif di semua kalibrasi SL. Jadi kegagalannya bukan soal SL yang salah.

Sementara di M5 varian ini stabil positif di kedua paruh waktu:

| periode | baseline | ATR 0,20-0,95 |
|---|---|---|
| Apr 2025 – Des 2025 | −0,010 | **+0,138** |
| Des 2025 – Sep 2026 | +0,069 | **+0,156** |

**Dua tafsir, keduanya masih terbuka:**

- Edge-nya memang khas M5. Momentum 24 bar di M5 = 2 jam; di M15 = 6 jam —
  fenomena yang berbeda. Masuk akal, tapi belum dibuktikan sendiri.
- Yang terlihat di M5 adalah artefak dari 1,41 tahun data tertentu
  (2025–2026) yang tidak berlaku di periode 2022–2026.

Belum ada cara memisahkan keduanya dengan data yang ada.

---

## 4. Status dan langkah berikutnya

**Setelan ini dipasang untuk DEMO.** Layak dijalankan karena expectancy
positif dan stabil di M5, frekuensinya cukup untuk mengumpulkan bukti
(363 trade/tahun, bukan 75), dan seluruh guardrail sudah berfungsi.

**Belum layak untuk akun real** sampai salah satu terpenuhi:

1. Forward test demo mengumpulkan ~200 trade dengan expectancy tetap
   positif. Pada 363 trade/tahun itu sekitar 7 bulan.
2. Edge M5 terkonfirmasi di data M5 yang lebih panjang (butuh unduh ulang
   di luar batas 100.000 bar), atau di M1 sebagai timeframe tetangga.

**Yang TIDAK boleh dilakukan:** menaikkan risiko, mengaktifkan multi-posisi,
atau memakai confidence score untuk memilih arah. Skor terbukti tidak
memprediksi hasil (korelasi −0,006; skor 6 = +0,361R, skor 8 = −0,219R).

---

## 5. Cara mengulang pengukuran ini

```bash
python scripts/fix_time_offset.py --check    # pastikan data tidak bergeser
python scripts/measure_sessions.py           # performa per sesi
python scripts/sweep_frequency.py --rr 2.78  # sapuan pelonggaran gate
```

Untuk kembali ke setelan lama, ubah di `config/settings.yaml`:
`atr_percentile_min: 0.30`, `atr_percentile_max: 0.85`, `min_rr_ratio: 3.0`,
`tp_min_points: 12000`.
