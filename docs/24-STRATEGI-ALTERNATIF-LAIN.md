# Strategi Alternatif Selain Momentum_Fib

**Tanggal:** 9 September 2026
**Permintaan:** "Selain momentum_fib, coba lagi apapun itu."

---

## Ringkasan

Dicoba 7 kategori strategi yang **struktural berbeda** dari momentum_fib —
bukan variasi parameter, tapi logika masuk yang sama sekali lain.

| # | Strategi | Logika | Hasil terbaik |
|---|---|---|---|
| 1 | Volatility breakout | Bollinger squeeze → ekspansi | E=-0,0456R |
| 2 | Opening range breakout | Breakout range 1 jam pertama London | E=-0,1185R |
| 3 | Pin bar reversal | Candle rejection (wick besar) | E=-0,0841R |
| 4 | Volume spike | Tick volume 2× rata-rata + arah candle | E=-0,0817R |
| 5 | Time-of-day + trend | Jam terbaik historis + arah HTF | **+0,0333R (tidak stabil)** |
| 6 | Multi-timeframe strict | M5+H1+H4 harus semua searah | E=-0,0576R |
| 7 | Exhaustion reversal | ADX melemah setelah tren kuat | E=-0,0244R |

**6 dari 7 negatif secara langsung.** Strategi #5 sempat terlihat positif,
tapi gagal total saat diverifikasi lebih dalam — dijelaskan di bawah.

---

## Detail Strategi #5 (yang sempat menjanjikan)

Filter: jam [14, 21, 22] UTC + searah tren HTF, SL 400 pip, RR 1:3.

```
Keseluruhan : WR=27,5% E=+0,0333R  <- terlihat positif
```

### Kenapa ditolak setelah diverifikasi

```
In-sample  : E=+0,1210R
Out-of-sample: E=-0,1713R   <- TERBALIK TOTAL
```

Per kuartal:
```
2025Q2: +0,1712   2025Q3: -0,0478   2025Q4: +0,1076
2026Q1: +0,2442   2026Q2: -0,0903   2026Q3: -0,3717  <- kuartal terbaru
```

Tiga kuartal awal (tempat pola ini "ditemukan") positif kuat. Tiga kuartal
setelahnya, termasuk yang **paling baru**, negatif — dan yang terakhir
sangat tajam (−0,37R). Ini pola curve-fitting klasik: filter yang
kebetulan cocok dengan periode tertentu di masa lalu, tapi tidak
mengandung logika yang bertahan ke depan.

**Uji sensitivitas mengonfirmasi kerapuhannya:**
```
jam=[14,21,22] : E=+0,0333R
jam=[13,14,15] : E=-0,0942R   <- geser 1 jam, langsung rugi
jam=[20,21,22,23]: E=-0,0203R
```

Hasil berubah drastis dengan pergeseran kecil — tanda lain dari overfitting,
bukan edge yang nyata.

---

## Kesimpulan

Ditambah dengan seluruh pencarian hari-hari sebelumnya (momentum, mean-
reversion, RR bebas berbagai horizon, model ML, EURUSD), total sekarang
mencakup **250+ kombinasi strategi berbeda** untuk XAUUSDm di broker ini.

**Hanya momentum_fib yang bertahan** dari seluruh pengujian — dan itu pun
dengan expectancy tipis (+0,016R, 4/5 fold walk-forward), belum lolos
gate penuh.

Ini bukan berarti pencarian harus berhenti selamanya. Tapi setiap
kombinasi baru yang diuji pada data historis yang sama meningkatkan
risiko menemukan pola yang kebetulan cocok (seperti Strategi #5) tanpa
benar-benar punya logika yang bertahan. Titik ini adalah batas wajar untuk
pencarian berbasis data historis semata — langkah berikutnya yang lebih
produktif adalah **forward test** momentum_fib yang sudah ada (data live,
bukan historis), atau eksplorasi data non-harga (kalender berita, order
flow) yang belum tersentuh sama sekali di proyek ini.
