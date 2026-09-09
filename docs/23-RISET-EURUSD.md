# Riset EURUSD — Hasil Pencarian Sistem Terpisah

**Tanggal:** 9 September 2026
**Tujuan:** Sistem trading terpisah untuk EURUSD, mencari alternatif karena
XAUUSD tidak menemukan edge untuk horizon pendek.

---

## Ringkasan

Broker: `EURUSDm`, spread median **0,8 pip** (32× lebih murah dari XAUUSD
26 pip). Data terunduh: M5 489 hari, M1 97 hari.

**Diuji 150+ kombinasi** (SL 3-80 pip, RR 1:1 sampai 1:4, horizon 1-48 jam,
filter momentum dan mean-reversion). Hasilnya:

- **Strategi momentum** (sama seperti XAUUSDm): **semua rugi**, konsisten
  di semua horizon dan ukuran SL
- **Strategi mean-reversion** (RSI oversold/overbought): satu kandidat
  tipis positif, tapi **tidak lolos uji stabilitas**

**Kesimpulan: belum ditemukan edge yang bisa dipercaya di EURUSDm.**

---

## 1. Spesifikasi Broker

| | XAUUSDm | EURUSDm |
|---|---|---|
| Spread | 26 pip (fixed) | 0,8 pip median (spike ke 5,5+ pip P99) |
| ATR M5 median | 424 pip | 3,2 pip |
| Range bar M5 median | 379 pip | 2,9 pip |
| **Rasio ATR/spread** | **16,3×** | **4,0×** |

**Temuan yang mengoreksi asumsi awal:** rasio ATR-terhadap-spread EURUSD
ternyata **lebih buruk** dari XAUUSD, bukan lebih baik. Meski spread
absolut EURUSD jauh lebih kecil, pergerakan hariannya juga jauh lebih
kecil secara proporsional — jadi keunggulan spread rendah sebagian
tergerus oleh volatilitas yang juga rendah.

---

## 2. Strategi Momentum (pola sama dengan momentum_fib XAUUSD)

96 kombinasi diuji: SL 3-80 pip, RR 1,5-4, horizon 1-48 jam.

**Semua negatif.** Kandidat terbaik:

```
SL=20 pip, RR=1:1,5, horizon=24 jam
WR=37,7% | E=-0,0970R | 8/17 bulan positif
```

Pola menurun konsisten: makin besar RR yang dicoba, makin jelek hasilnya
(sama seperti temuan di XAUUSD). Momentum tidak bekerja di EURUSD pada
horizon manapun yang diuji.

---

## 3. Strategi Mean-Reversion (RSI oversold/overbought)

Karena momentum gagal, dicoba pendekatan berlawanan: beli saat RSI < 30,
jual saat RSI > 70.

### Kandidat yang tampak menjanjikan

```
SL=30 pip, RR=1:1, horizon=24 jam
WR=51,5% | E=+0,0026R | 8/17 bulan positif
```

Expectancy positif tipis, muncul konsisten di rentang SL 20-36 pip.

### Kenapa TIDAK direkomendasikan meski positif

**Uji stabilitas mengungkap masalah serius:**

```
In-sample (70% data)   : WR=48,8% E=-0,0513R
Out-of-sample (30% data): WR=57,7% E=+0,1283R
```

**OOS jauh lebih baik dari IS** — ini pola terbalik dari yang seharusnya
meyakinkan (biasanya IS lebih baik, OOS mengonfirmasi atau sedikit turun).
Selisih sebesar ini antara IS dan OOS adalah tanda peringatan: kemungkinan
besar hasil OOS yang bagus berasal dari satu periode kebetulan yang
menguntungkan, bukan edge yang konsisten.

**Sensitivitas parameter juga rapuh:**

```
SL=24p: E=-0,0140R
SL=27p: E=-0,0082R
SL=30p: E=+0,0026R  <- kandidat
SL=33p: E=+0,0065R
SL=36p: E=-0,0017R
```

Expectancy berayun di sekitar nol dengan pergeseran SL kecil (3 pip).
Edge yang nyata biasanya lebih tahan terhadap perubahan parameter kecil —
ini persis pola yang berulang kali kita temukan sebagai tanda curve
fitting, bukan edge sungguhan (lihat `18-TIERED-SIZING.md`,
`20-CARI-RR-OPTIMAL.md`).

---

## 4. Kesimpulan

| Pertanyaan | Jawaban |
|---|---|
| EURUSD punya edge momentum? | **Tidak** — semua kombinasi rugi |
| EURUSD punya edge mean-reversion? | **Belum terbukti** — kandidat ada tapi tidak stabil |
| Layak dijadikan sistem terpisah sekarang? | **Belum** |
| Kenapa spread rendah tidak otomatis membantu? | Volatilitas EURUSD juga rendah — rasio ATR/spread malah lebih buruk dari gold |

**Tidak ada sistem EURUSD yang dibangun dari hasil riset ini.**
Membangun sistem dari kandidat yang gagal uji stabilitas akan mengulang
kesalahan yang sudah dihindari sepanjang proyek — mengoperasikan sesuatu
yang terlihat untung di satu sudut pandang tapi terbukti rapuh saat
diperiksa lebih jauh.

---

## 5. Arah Selanjutnya (belum dikerjakan)

Bila riset EURUSD ingin dilanjutkan:

1. **Verifikasi kandidat mean-reversion dengan backtest lengkap** (risk
   manager, circuit breaker) — pola sebelumnya menunjukkan analisis label
   sederhana sering menyesatkan dibanding backtest penuh
2. **Perpanjang data historis** — 489 hari M5 mungkin belum cukup untuk
   menguji strategi mean-reversion yang butuh banyak siklus pasar berbeda
3. **Coba pasangan mata uang lain** dengan karakteristik volatilitas
   berbeda (GBPUSD, USDJPY) — EURUSD sendiri mungkin bukan yang optimal
4. **Uji filter tambahan** pada mean-reversion (misalnya kombinasi dengan
   Bollinger Bands atau ADX untuk memastikan kondisi ranging, bukan
   trending) — RSI ekstrem saja terbukti belum cukup selektif

Data dan fitur EURUSD (`data_eurusd/`) sudah tersimpan dan siap dipakai
untuk pengembangan lanjutan, terpisah dari sistem XAUUSD yang sedang
berjalan.
