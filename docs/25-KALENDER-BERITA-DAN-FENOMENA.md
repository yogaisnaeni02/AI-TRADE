# Eksplorasi Kalender Berita & Fenomena Pasar

**Tanggal:** 9 September 2026
**Permintaan:** "Coba dari kalender berita, fenomena yang ada di dunia, dll."

---

## Ringkasan

Dieksplorasi tiga pendekatan berbasis kalender ekonomi/berita, dengan
keterbatasan akses data yang perlu disampaikan jujur di depan.

**Kesimpulan: belum ditemukan edge yang bisa dipercaya**, dan satu temuan
awal yang tampak menjanjikan ternyata gagal uji signifikansi statistik.

---

## 1. Keterbatasan Akses Data

| Sumber | Status |
|---|---|
| MT5 Python API kalender ekonomi | **Tidak tersedia** — fitur ini ada di terminal desktop, tidak diekspos ke Python |
| ForexFactory feed publik | **Bisa diakses gratis**, tapi hanya minggu berjalan (this/last/next week saja) — 404 untuk periode lain |
| Arsip historis kalender berbulan-bulan | **Tidak tersedia gratis** — butuh API berbayar (Trading Economics, dll.) |

Karena arsip historis kalender tidak tersedia gratis, dipakai dua
pendekatan pengganti:
1. **Proxy jadwal terhitung** (NFP: selalu Jumat pertama tiap bulan —
   aturan tetap yang bisa dihitung mundur)
2. **Proxy dari data harga sendiri** (lonjakan volatilitas ekstrem sebagai
   penanda "kemungkinan ada berita")

---

## 2. NFP: Pre-Release Drift dan Post-Release Momentum

### Pre-NFP drift

Diukur pergerakan 4 jam sebelum tiap rilis NFP (17 event, Apr 2025–Sep
2026). **Tidak ada pola arah konsisten** — pergerakan bervariasi liar dari
−4.307 pip sampai +1.389 pip tanpa bias jelas ke satu arah.

### Post-NFP momentum follow-through

Hipotesis: arah candle reaksi pertama (15 menit) memprediksi arah 2 jam
berikutnya.

```
Sampel: 17 event
Winrate: 52,9%
Expectancy: +0,50R
Breakeven WR: 34,3%
```

**Angka ini terlihat sangat menjanjikan** — jauh di atas breakeven.

### Kenapa TIDAK bisa dipercaya

Uji signifikansi statistik (binomial test terhadap hipotesis winrate
netral 40%):

```
Peluang hasil ini terjadi karena KEBETULAN: ~19,9%
```

Standar umum untuk "signifikan secara statistik" adalah di bawah 5%.
Angka 19,9% jauh melampaui itu — dengan kata lain, **1 dari 5 kali
kemungkinan hasil sebagus ini murni kebetulan**, bukan edge nyata.

Detail per event menunjukkan hasilnya nyaris 50-50 (9 menang, 8 kalah)
dengan pembayaran timpang (menang +2R, kalah −1R) — persis jenis pola
yang bisa muncul dari koin yang dilempar 17 kali.

**Akar masalahnya: NFP cuma terjadi sebulan sekali.** Untuk mendapat
sampel yang cukup meyakinkan secara statistik (butuh minimal 50-100
event), diperlukan 4-8 tahun data — tidak realistis untuk divalidasi
sekarang.

---

## 3. Proxy Berita dari Lonjakan Volatilitas (Sampel Lebih Besar)

Untuk mengatasi masalah sampel kecil, dicoba mendeteksi "momen seperti
berita" langsung dari data harga: bar dengan range jauh melebihi ATR
normal (>3× ATR, saat ATR sendiri sudah di atas median).

```
Sampel: 336 kejadian (jauh lebih besar dari 17 NFP)
```

### Momentum (ikuti arah reaksi)

```
WR=24,1% | E=-1,1435R | IS=-1,13R OOS=-1,18R (konsisten rugi)
```

### Fade (lawan arah reaksi)

```
WR=26,8% | E=-1,0631R | konsisten rugi di semua variasi SL/TP dicoba
```

**Kedua arah gagal telak, dengan kerugian sangat besar (~-1R).** Ini
mengindikasikan lonjakan volatilitas mendadak di XAUUSD **tidak
terprediksi arahnya sama sekali** — baik mengikuti momentum awal maupun
melawannya (menunggu reversal) sama-sama merugikan secara signifikan.

Sampel besar ini (336 vs 17) memberi gambaran yang jauh lebih bisa
dipercaya, dan hasilnya justru mengonfirmasi bahwa angka NFP yang tadi
tampak bagus kemungkinan besar memang kebetulan.

---

## 4. Kesimpulan

| Pendekatan | Sampel | Hasil |
|---|---|---|
| NFP pre-release drift | 17 | Tidak ada pola arah |
| NFP post-release momentum | 17 | +0,50R, **tapi p=19,9% (tidak signifikan)** |
| Volatility-spike momentum | 336 | -1,14R (rugi jelas) |
| Volatility-spike fade | 336 | -1,06R (rugi jelas) |

**Tidak ditemukan edge yang bisa dipercaya** dari kalender berita atau
proxy-nya. Sampel yang cukup besar untuk diuji secara statistik (336)
justru menunjukkan hasil yang jelas negatif di kedua arah, sementara
sampel yang tampak menjanjikan (17 event NFP) gagal lolos uji
signifikansi paling dasar.

---

## 5. Kenapa Ini Berbeda dari Klaim "Trading Berita" yang Umum

Klaim populer bahwa "trading di sekitar berita besar itu profitable"
biasanya berasal dari:
- Backtest dengan sampel sangat kecil (seperti temuan NFP palsu di atas)
- Survivorship bias (hanya kasus sukses yang diceritakan)
- Eksekusi manual oleh trader berpengalaman yang membaca **konteks**
  berita (angka aktual vs forecast, bukan cuma waktu rilis) — informasi
  yang tidak tersedia di data OHLCV historis

Poin terakhir penting: sistem otomatis berbasis data harga saja tidak
bisa membaca **isi** berita (apakah NFP di atas atau di bawah ekspektasi)
— hanya **waktu** rilisnya. Itu sebabnya proxy ini secara struktural
terbatas, terlepas dari seberapa banyak data yang tersedia.

---

## 6. Arah yang Masih Terbuka (Belum Dikerjakan)

Bila eksplorasi ini ingin dilanjutkan dengan sumber daya lebih:

1. **API kalender berbayar** (Trading Economics, ForexFactory Premium)
   untuk arsip historis + **angka aktual vs forecast** — komponen yang
   hilang di eksplorasi ini
2. **Data sentimen berita real-time** (NewsAPI, GDELT) untuk mengukur
   nada pemberitaan, bukan sekadar jadwal
3. **Korelasi antar-aset** — DXY (indeks dolar), yield obligasi AS,
   yang secara historis berkorelasi kuat dengan gold — belum diuji sama
   sekali di proyek ini, dan berpotensi lebih menjanjikan daripada
   kalender berita murni

Poin 3 adalah arah yang paling realistis untuk dieksekusi tanpa API
berbayar, karena DXY dan yield obligasi AS umumnya tersedia sebagai
simbol tradeable di broker yang sama.
