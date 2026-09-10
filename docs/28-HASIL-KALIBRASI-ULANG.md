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

> **KOREKSI (revisi 3, 10 Sep 2026):** `scripts/fix_time_offset.py` hanya
> menggeser kolom `time_utc`, TIDAK menghitung ulang kolom turunannya. File
> di `data/processed` karena itu punya `time_utc` benar tetapi `session`,
> `is_trading_session`, `hour_utc`, `friday_cutoff`, `asia_high/low`, dan
> `sweep_*` masih nilai lama yang salah 7 jam (terverifikasi: label tersimpan
> cocok 100% dengan `time_utc` dikurangi 7 jam). Akibatnya backtest memblokir
> 7 jam penuh termasuk seluruh sesi London, sementara bot live menghitung
> sesi dengan benar — backtest dan live menguji jam berbeda lagi.
>
> Setelah `python -m src.features.pipeline` dijalankan ulang, terungkap bahwa
> `is_trading_session` (dari daftar SESSIONS hardcode) memblokir `asia` dan
> `pre_ny`, dan justru jam-jam itulah yang menguntungkan:
>
> | | n | E[R] | t | DD |
> |---|---|---|---|---|
> | patuhi `is_trading_session` | 457 | **−0,1254** | −1,65 | 89% |
> | 24 jam penuh | **897** | **+0,1254** | **+2,14** | 32,1% |
>
> `momentum_fib.require_trading_session: false` ditambahkan ke config.
> **Angka final yang berlaku: E[R] +0,1254, t 2,14, WR 29,9%, PF 1,22,
> DD 32,1%, 635 trade/tahun, stabil di kedua paruh (+0,108 / +0,143).**
> Angka di seluruh sisa dokumen ini dan di `docs/30` diukur sebelum rebuild
> dan harus dibaca dengan itu di pikiran; arah kesimpulannya tidak berubah,
> besarannya berubah.
>
> **KOREKSI (revisi 2, 10 Sep 2026 malam):** angka di revisi pertama dokumen
> ini diukur dengan `global.max_drawdown_percent: 20` AKTIF di dalam backtest.
> Engine menghentikan simulasi begitu drawdown 20% tersentuh — pada
> 25 Maret 2026, **168 hari sebelum akhir data**. Jadi "513 trade" adalah
> jumlah sebelum terpotong, bukan jumlah sesungguhnya. Halt itu adalah
> guardrail operasional, bukan alat ukur; untuk pengukuran ia dimatikan.
> Angka di bawah adalah periode penuh.

Hasil dari config apa adanya, M5, 1,41 tahun, **periode penuh**:

```
sinyal 4.743 -> trade 721
E[R]  = +0,1557R    SE = 0,0654    t = 2,38
winrate 31,1%       (breakeven RR 1:2,78 = 28,17%)
profit factor 1,28  trade/tahun 510
max drawdown 32,1%  loss beruntun maks 11
paruh-1 +0,177R     paruh-2 +0,134R
```

Implikasi operasional yang penting: **drawdown alami strategi ini 32%**,
sehingga kill switch 20% di `risk_limits.yaml` DIHARAPKAN menyala kira-kira
sekali per 1,4 tahun. Itu bukan tanda ada yang rusak — itu rem bekerja
sesuai desain. Setelah menyala, perlu reset manual `logs/risk_state.json`
setelah dievaluasi.

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

> Tabel di bawah diukur dengan halt DD 20% aktif (terpotong). Verifikasi
> ulang periode penuh tanpa halt **mengonfirmasi pilihannya**:
>
> | varian | n | E[R] | t | DD | paruh-1 | paruh-2 |
> |---|---|---|---|---|---|---|
> | baseline ATR 0,30-0,85 | 602 | +0,1002 | 1,42 | 30,2% | +0,146 | +0,055 |
> | **ATR 0,20-0,95 (dipakai)** | **721** | **+0,1557** | **2,38** | 32,1% | +0,177 | +0,134 |
> | ATR 0,20-0,95 + mom 0,35x | 774 | +0,1385 | 2,20 | 37,1% | +0,140 | +0,137 |
> | ATR 0,20-0,85 | 645 | +0,1371 | 1,99 | **23,4%** | +0,134 | +0,140 |
>
> Baseline ternyata juga positif pada periode penuh (+0,10R) — angka
> −0,01R sebelumnya sebagian artefak pemotongan. Pelonggaran ATR tetap
> menambah ~120 trade dan menaikkan t dari 1,42 ke 2,38. Varian
> ATR 0,20–0,85 menarik sebagai saudara ber-DD lebih rendah (23% vs 32%)
> dengan E[R] serupa, tetapi TIDAK dipakai — mengganti lagi berarti
> menambah percobaan pada data yang sama.

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
   positif. Pada 510 trade/tahun itu sekitar 5 bulan.
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
