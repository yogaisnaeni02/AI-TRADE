# Analisis: Scalping di XAUUSDm Exness

**Tanggal:** 9 September 2026
**Pertanyaan:** "Bagaimana kalau pakai teknik scalping saja?"

---

## Jawaban Singkat

**Scalping tidak layak di broker ini.** Bukan karena tekniknya salah, tetapi
karena spread 26 pip terlalu besar relatif terhadap target scalping.

Semakin kecil targetnya, semakin besar kerugiannya. Diukur langsung dari
100.000 bar M5.

---

## 1. Uji Semua Kombinasi SL/TP (entry acak)

| SL (pip) | TP (pip) | RR | Winrate | Breakeven WR | Expectancy |
|---|---|---|---|---|---|
| **50** | **100** | 2,0 | 17,0% | 40,3% | **−1,011R** |
| 50 | 150 | 3,0 | 15,7% | 28,7% | −0,891R |
| 100 | 200 | 2,0 | 26,1% | 36,5% | −0,478R |
| 100 | 300 | 3,0 | 21,3% | 26,7% | −0,407R |
| 150 | 450 | 3,0 | 23,9% | 26,1% | −0,219R |
| 200 | 600 | 3,0 | 24,3% | 25,8% | −0,159R |
| **300** | **600** | 2,0 | 32,3% | 34,3% | **−0,117R** |

**Polanya konsisten: target kecil = rugi besar.**

Scalping ketat (SL 50 / TP 100 pip) adalah yang paling menghancurkan —
kehilangan satu R penuh setiap trade.

### Mengapa

Dua sebab yang bekerja bersamaan:

1. **Spread memakan target.** Untuk TP 100 pip, spread 26 pip = **26% dari
   target**. Trade harus bergerak 126 pip untuk menghasilkan 100 pip.

2. **SL kecil kena noise.** Range bar M5 median 379 pip. SL 50 pip berada
   jauh di dalam gerakan satu bar — tersentuh oleh fluktuasi biasa, bukan
   oleh arah pasar yang salah.

---

## 2. Apakah Filter Momentum Menyelamatkan Scalping?

Diuji dengan filter yang ditemukan sebelumnya (momentum tinggi + Fibonacci
+ tren HTF searah):

| SL/TP (pip) | Trade | Winrate | Expectancy | Perbaikan vs acak |
|---|---|---|---|---|
| 100/300 | 7.176 | 23,4% | −0,324R | **+0,058** |
| 150/450 | 7.158 | 25,6% | −0,151R | **+0,070** |
| 200/600 | 7.094 | 27,2% | −0,043R | **+0,118** |
| **300/900** | 6.775 | 27,0% | **−0,008R** | **+0,131** |
| 400/1200 | 6.289 | 25,2% | −0,057R | +0,115 |

**Filter momentum bekerja** — konsisten menaikkan expectancy +0,058 hingga
+0,131R di semua kombinasi. Ini konfirmasi bahwa fitur momentum dan Fibonacci
memang mengandung informasi.

Tetapi perbaikannya belum cukup menutup kerugian struktural dari spread.
Yang terbaik (300/900) mendekati impas di −0,008R.

---

## 3. Berapa Lama Posisi Sebaiknya Ditahan?

Ini menjawab langsung inti dari scalping — keluar cepat:

| Timeout | Trade | Winrate | Expectancy |
|---|---|---|---|
| **15 menit** | 5.244 | 20,0% | **−0,331R** |
| 30 menit | 6.213 | 23,9% | −0,172R |
| 1 jam | 6.816 | 26,0% | −0,090R |
| 2 jam | 7.094 | 27,2% | −0,043R |
| **4 jam** | 7.163 | 27,3% | **−0,038R** |

**Semakin lama ditahan, semakin baik hasilnya.** Ini kebalikan langsung dari
prinsip scalping.

Alasannya: spread adalah biaya **tetap per trade**. Menahan posisi lebih lama
memberi ruang bagi pergerakan untuk melampaui biaya itu. Keluar cepat berarti
membayar biaya penuh untuk pergerakan yang belum sempat berkembang.

---

## 4. Apa yang Sudah Dimiliki Sistem

Tiga hal yang ditanyakan sudah ada dan berfungsi:

| Kemampuan | Status | Lokasi |
|---|---|---|
| **Cari momentum** | Ada | `mom_3/6/12/24`, `mom_accel` di `indicators.py` |
| **Hitung lot otomatis** | Ada, teruji | `RiskManager.calculate_lot()` |
| **Open posisi sendiri** | Ada, teruji | `OrderManager.open_position()` |

Lot dihitung dari risiko dan jarak SL:

```python
risk_amount = equity * (risk_pct / 100)
lot = risk_amount / (sl_points * value_per_point)
lot = pembulatan ke volume_step, dibatasi volume_min/max
```

Terverifikasi di akun demo: order #2517514924, lot 0,02, risiko 2,72%.

Yang **tidak** dimiliki adalah alasan untuk memakainya dalam mode scalping —
karena scalping di broker ini merugi secara struktural.

---

## 5. Rekomendasi

### Jangan scalping di XAUUSDm Exness

Spread 26 pip membuat target kecil tidak layak secara matematis. Ini bukan
soal strategi yang lebih baik; ini biaya tetap yang melebihi ukuran target.

### Yang layak dikejar

| Parameter | Nilai |
|---|---|
| SL | 300–400 pip |
| TP | 900–1.200 pip (RR 1:3) |
| Timeout | 2–4 jam (bukan 15 menit) |
| Filter | Momentum + Fibonacci + tren HTF |

Ini bukan scalping — ini **intraday momentum**, dan itulah yang cocok dengan
karakteristik biaya broker ini.

### Bila tetap ingin scalping

Dua syarat harus dipenuhi lebih dulu:

1. **Broker dengan spread lebih rendah.** Akun Raw Spread / Zero Exness
   menawarkan ~10–15 pip efektif. Itu memangkas biaya lebih dari separuh dan
   mengubah seluruh perhitungan di Bagian 1.

2. **Instrumen dengan rasio ATR/spread lebih baik.** EURUSD sudah diukur
   memiliki karakteristik yang jauh lebih ramah untuk target kecil.

---

## 6. Catatan tentang Status Strategi

Perlu disampaikan bersamaan: setup momentum yang dipakai di analisis ini
belum lolos validasi walk-forward.

```
Walk-forward 5 fold: 2/5 positif, rata-rata -0,124R
```

Filter momentum terbukti **menaikkan** expectancy secara konsisten (Bagian 2),
tetapi belum cukup untuk menghasilkan sistem yang profitabel di semua periode.

Artinya: pertanyaan "scalping atau tidak" sudah terjawab (tidak), tetapi
pertanyaan yang lebih mendasar — "strategi apa yang punya edge stabil" —
masih terbuka.
