# Rangkuman Riset Strategi

**Tanggal:** 9 September 2026
**Data:** 100.000 bar M5 XAUUSDm (Apr 2025 – Sep 2026)

---

## Yang Diminta dan Statusnya

| Permintaan | Status |
|---|---|
| RR 1:3 (TP = 3× SL) | **Sudah dipakai** — terpasang di config |
| Sistem cari momentum | **Ada** — `mom_3/6/12/24`, terbukti punya sinyal |
| Sistem hitung lot otomatis | **Ada, teruji** — `RiskManager.calculate_lot()` |
| Sistem open posisi sendiri | **Ada, teruji** — order #2517514924 di demo |
| Teknik bebas (MACD, Fibonacci, dll.) | **Sudah diuji semua** |
| Scalping | **Tidak layak** — lihat `08-SCALPING-VS-SPREAD.md` |
| Target 50%/hari | **Tidak mungkin** — aritmetika, bukan pesimisme |
| Strategi yang stabil profitabel | **Belum tercapai** |

---

## Hasil Pengujian Indikator

Diukur: winrate terhadap target RR 1:3, dibandingkan breakeven 25,4%.

| Indikator | Winrate terbaik | Berguna? |
|---|---|---|
| **mom_24** (momentum 24 bar) | 26,5% | **Ya** |
| **mom_12** | 26,5% | **Ya** |
| **fib_position** | 26,2% | **Ya** |
| fib_range_atr | 26,0% | Ya, lemah |
| Stochastic | 25,9% | Marginal |
| RSI | 27,0% | Ya, lemah |
| plus_di (ADX) | 26,7% | Ya, lemah |
| **MACD** | 25,1% | **Tidak** — di bawah breakeven |
| Bollinger %B | 26,1% | Marginal |
| Candle patterns | 24,8% | Tidak |
| Volume | 25,5% | Marginal |
| ATR percentile | 25,4% | Tidak sendirian |

**Temuan:** momentum dan posisi Fibonacci mengandung informasi nyata. MACD —
meski populer — tidak memberi keunggulan pada instrumen dan timeframe ini.

---

## Evolusi Strategi

| Versi | Expectancy | Walk-forward |
|---|---|---|
| London Sweep (awal) | −0,300R | — |
| + SL diperlebar 650 pip | −0,007R | — |
| + filter setup & arah | +0,083R | OOS −0,225R (gagal) |
| **momentum_fib** (baru) | +0,093R | 2/5 fold |
| **+ filter ATR wajib** | **+0,112R** | **3/5 fold** |

Setiap langkah memperbaiki hasil, tetapi belum ada yang lolos validasi penuh.

### Konfigurasi terbaik saat ini

```
Setup    : momentum_fib
Syarat   : mom_24 > persentil 85 (rolling, anti-lookahead)
           fib_position > 0.75 (uptrend) / < 0.25 (downtrend)
           trend_htf searah
           atr_percentile 0.30-0.85  <- wajib, bukan bonus
SL       : 400 pip
TP       : 1200 pip (RR 1:3)
Kelola   : break-even di 1.5R, trailing ATR x2.5
```

Hasil: 85 trade, winrate 41,2%, expectancy +0,112R, return +4,4%.

---

## Mengapa Belum Lolos

### Walk-forward masih tidak stabil

```
fold 1 (Apr-Jul 2025): +0,419R
fold 2 (Jul-Sep 2025): +0,038R
fold 3 (Sep-Des 2025): +0,143R
fold 4 (Des-Mar 2026): -0,151R
fold 5 (Mar-Sep 2026): -0,405R
```

Tiga fold pertama positif, dua terakhir negatif. Pola ini mengkhawatirkan
karena **kemunduran terjadi di data terbaru** — bisa berarti kondisi pasar
berubah, atau edge-nya memang tidak nyata.

### Sampel terlalu kecil

85 trade terlalu sedikit untuk kesimpulan statistik. Gate menuntut minimal 200.
Filter yang makin ketat menaikkan kualitas tetapi memangkas jumlah trade —
ini pertukaran yang belum menemukan titik seimbang.

### Risk limit memblokir 86% sinyal

Dari 1.004 sinyal, hanya 136 tereksekusi. Sisanya diblokir oleh aturan satu
posisi pada satu waktu dan batas harian. Ini benar dari sisi keamanan, tetapi
berarti sistem tidak memanfaatkan sebagian besar peluang yang ditemukannya.

---

## Yang Sudah Pasti Diketahui

Hasil pengukuran yang tidak berubah lagi:

| Fakta | Nilai |
|---|---|
| Spread XAUUSDm Exness | 260 points = 26 pip, tetap di semua sesi |
| Range bar M5 (median) | 379 pip |
| ATR M5 (median) | 424 pip |
| SL layak | 300–400 pip |
| SL 100 pip | Kena noise 98% dari waktu |
| Winrate entry acak (RR 1:3) | 24,5% |
| Breakeven winrate | 25,4% |
| **Celah yang harus dilampaui** | **0,9 poin persentase** |
| Momentum + Fib + ATR mencapai | 28,7% |
| Scalping 15 menit | −0,331R |
| Menahan 4 jam | −0,038R |
| Modal minimum XAUUSD | Rp 3.700.000 |

---

## Pilihan Berikutnya

### A. Machine learning sebagai penyaring

Celahnya hanya 0,9%. Pola sehalus itu lebih mungkin ditemukan model daripada
aturan manual. Semua prasyarat sudah siap: 88 fitur, labeling triple-barrier,
kerangka walk-forward.

Risikonya: ML sangat mudah overfit pada data finansial. Validasinya harus
ketat — konsisten di 8 dari 10 fold, bukan sekadar rata-rata bagus.

### B. Pindah instrumen

EURUSD memiliki rasio ATR-terhadap-spread jauh lebih baik, sehingga celah yang
harus dilampaui lebih lebar. Seluruh kode sudah instrument-agnostic; yang
berubah hanya konfigurasi dan kalibrasi ulang setup.

Ini juga menyelesaikan masalah modal: EURUSD hanya butuh risiko 0,6% per trade
pada modal Rp 800.000, sementara XAUUSD butuh Rp 3,7 juta.

### C. Akun spread rendah

Exness Raw Spread menawarkan ~10–15 pip efektif dibanding 26 pip sekarang.
Itu memangkas biaya lebih dari separuh dan menggeser seluruh perhitungan —
termasuk membuat scalping mungkin dipertimbangkan ulang.

### D. Terima bahwa edge belum ditemukan

Ini pilihan yang sah. Menemukan edge yang bertahan out-of-sample adalah bagian
tersulit dari algo trading, dan umumnya butuh puluhan iterasi setup.
Infrastruktur yang sudah dibangun membuat setiap iterasi berikutnya jauh lebih
cepat.

---

## Catatan tentang Target Return

Permintaan 50% per hari sudah dijawab dengan angka: modal Rp 3,7 juta akan
menjadi 5× PDB dunia dalam 90 hari. Target itu tidak ada dalam kenyataan.

Hubungan antara agresivitas dan risiko juga terukur (simulasi 2.000 skenario):

| Risiko/trade | Return/bulan | Peluang bangkrut |
|---|---|---|
| 3% | 37% | 0% |
| 10% | 124% | 37% |
| 20% | 248% | 86% |
| 50% | 619% | 99,9% |

"Agresif tetapi risiko minimal" bukan dua tuas terpisah — itu satu tuas.
Menaikkan target berarti menaikkan peluang kehilangan modal, selalu.

Titik yang masuk akal tetap **3% per trade**: agresif (6× standar profesional),
dengan peluang bangkrut mendekati nol — **asalkan strateginya punya edge.**
Tanpa edge, risiko berapa pun hanya mengubah kecepatan kerugian.
