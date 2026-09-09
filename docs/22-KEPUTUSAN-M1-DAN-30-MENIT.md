# Keputusan: M1 dan "Open Posisi dalam 30 Menit"

**Tanggal:** 9 September 2026
**Permintaan:** "Sistem yang benar-benar bisa open posisi dalam 30 menit,
berapapun untungnya tidak masalah, pisahkan dari sistem sekarang." Lanjut:
"main di M1 aja kalau M5 tidak bisa."

Ini dokumen keputusan — saya pikirkan sungguh-sungguh, uji sampai tuntas,
dan sekarang beri jawaban jujur plus jalan terbaik yang sebenarnya ada.

---

## 1. Yang Sudah Diuji Hari Ini — Rekap Lengkap

| # | Yang diuji | Kombinasi | Hasil |
|---|---|---|---|
| 1 | Scalping SL/TP kecil (M5) | ~20 kombinasi | Semua rugi |
| 2 | RR bebas, horizon fix 30 menit (M5) | 42 kombinasi | **Semua rugi** |
| 3 | Horizon digeser 30 menit → 12 jam (RR 1:1,5 M5) | 9 titik | **Semua rugi**, expectancy stuck di ~−0,04R |
| 4 | Model ML confidence M1 sebagai exit | 3 framing | AUC ~0,50-0,54, tidak membantu sebagai exit |
| 5 | Pola momentum_fib diterapkan langsung di M1 | 60 kombinasi (setelah bug pip diperbaiki) | **Semua rugi**, 0/5 bulan positif |

**Total: 130+ kombinasi berbeda diuji hari ini.** Tidak satupun
menghasilkan sistem yang untung dengan horizon keputusan di bawah ~2 jam.

---

## 2. Kesimpulan yang Harus Saya Sampaikan Jujur

**Tidak ada bukti bahwa XAUUSDm di broker ini bisa ditradingkan
menguntungkan dengan horizon 30 menit — baik di M5 maupun M1, berapapun
ukuran target yang dicoba.**

Ini bukan karena kurang mencoba. Alasannya struktural:

1. **Spread 26 pip (fixed) adalah biaya tetap** yang harus dilampaui setiap
   trade, di timeframe manapun
2. **Range harga acak dalam 30 menit** (baik di M1 maupun M5) sudah cukup
   besar untuk membuat SL manapun—kecil atau besar—punya peluang tersentuh
   signifikan sebelum arah sebenarnya terbentuk
3. Pola momentum yang **terbukti punya sedikit edge di M5 dengan horizon
   4-8 jam** kehilangan edge itu sepenuhnya saat diterapkan di skala waktu
   lebih pendek — momentum jangka pendek di pasar ini lebih dekat ke
   random walk daripada momentum jangka menengah

Poin 3 ini konsisten dengan penelitian pasar finansial secara umum:
**mean-reversion mendominasi di sangat-jangka-pendek, momentum baru
terlihat di jangka menengah.** Itu bukan kebetulan hasil pengujian kita —
itu pola yang dikenal luas di literatur finansial, dan data kita
menegaskannya lagi.

### Soal "berapapun untungnya tidak masalah"

Ini poin penting yang perlu diluruskan: masalahnya bukan **untungnya
terlalu kecil**. Masalahnya **expectancy-nya negatif** — sistem ini akan
rugi secara sistematis, bukan untung sedikit. "Berapapun untungnya oke"
tidak bisa menyelamatkan sistem yang expectancy-nya di bawah nol; itu
tetap kehilangan uang, hanya kecepatannya yang bervariasi tergantung
seberapa sering ditradingkan.

---

## 3. Kenapa Saya Tidak Membangun Sistem M1 "Berapapun Untungnya"

Saya bisa saja membangun sistem yang **terlihat** aktif tiap 30 menit —
tinggal ambil kombinasi manapun dari 130+ yang diuji, deploy sebagai
"sistem terpisah". Secara teknis mudah, satu jam kerja.

Tapi itu berarti menyerahkan sistem yang **terbukti dari datanya sendiri
akan menghabiskan modal** — hanya karena permintaannya "berapapun
untungnya", bukan karena datanya mendukung. Saya tidak melakukan itu,
karena:

- Itu sama saja menyembunyikan hasil pengujian yang sudah jelas
- Sistem yang "sering aktif tapi rugi" justru lebih berbahaya daripada
  sistem yang jarang tapi untung — ia menghabiskan modal lebih cepat sambil
  terasa lebih "produktif"
- Ini persis pola yang sudah berkali-kali kita bahas: winrate/frekuensi
  tinggi yang terlihat meyakinkan, tapi expectancy negatif di baliknya

---

## 4. Yang Saya Bangun Sebagai Gantinya — Jalan yang Benar-Benar Bisa Dipertanggungjawabkan

Karena permintaan intinya adalah **frekuensi lebih tinggi dan lebih
terprediksi**, bukan sekadar angka "30 menit", ada dua jalan nyata yang
belum sepenuhnya dieksplorasi:

### A. Instrumen dengan spread jauh lebih rendah (paling menjanjikan)

Seluruh kegagalan hari ini bermuara ke satu angka: spread 26 pip. Kita
sudah ukur EURUSD sebelumnya di awal proyek:

```
XAUUSDm : risiko 14,3% di lot minimum, perlu modal Rp 3,7 juta
EURUSD  : risiko 0,6% di modal yang sama — 24x lebih presisi
```

Rasio ATR-terhadap-spread EURUSD jauh lebih baik. Kombinasi SL/TP kecil
yang mustahil di gold berpeluang nyata di sana — belum diuji secara
khusus untuk horizon pendek, tapi ini jalur paling masuk akal untuk
"buka posisi lebih sering" yang sungguhan.

**Ini yang saya rekomendasikan dicoba lebih dulu**, bukan memaksakan
M1 gold.

### B. Terima frekuensi momentum_fib apa adanya, maksimalkan pemantauannya

Sistem sekarang (momentum_fib, M5, horizon 4-8 jam) adalah **satu-satunya
yang terbukti punya edge positif** dari seluruh yang diuji hari ini —
meski tipis (+0,016R, 4/5 fold). Solusi untuk "tidak mau nunggu lama" itu
sudah dibangun: notifikasi Telegram, supaya menunggu tidak berarti
memelototi layar.

### Yang TIDAK saya rekomendasikan

- Sistem terpisah trading M1 gold dengan target manapun — 60+ kombinasi
  sudah dicoba, semua rugi
- Melonggarkan filter momentum_fib untuk menambah frekuensi — sudah
  dicoba (`frequent_micro`), rugi
- Memaksakan horizon 30 menit dengan RR manapun — sudah dicoba, semua rugi

---

## 5. Keputusan yang Saya Ambil

**Saya tidak membangun sistem M1/30-menit terpisah**, karena:
1. Data menunjukkan jelas ini akan merugi, bukan sekadar untung kecil
2. "Terpisah dari sistem sekarang" tidak menghilangkan risiko — uang yang
   hilang di sistem kedua tetap uang yang sama
3. Membangunnya tanpa mengatakan ini akan bertentangan dengan cara saya
   bekerja sepanjang proyek ini: jujur dengan hasil pengujian, bukan
   menyenangkan permintaan dengan mengorbankan kebenaran datanya

**Yang saya tawarkan sebagai gantinya:**
1. Uji EURUSD atau instrumen spread-rendah lain untuk kebutuhan frekuensi
   tinggi — ini jalur yang datanya mendukung, belum kita coba
2. Sistem sekarang (momentum_fib) tetap jalan sebagaimana adanya —
   terbukti (tipis) positif, dan notifikasinya sudah siap dipakai

Kalau Anda tetap ingin saya membangun sistem M1 murni terlepas dari hasil
pengujian ini — silakan sampaikan secara eksplisit, dan saya akan
bangunkan dengan peringatan tertulis yang jelas di setiap bagian sistemnya
bahwa ini beroperasi di luar bukti yang tersedia. Tapi saya tidak akan
melakukannya sebagai langkah default tanpa Anda menyatakan itu sadar akan
risikonya.

---

## 6. Update: Pencarian Lanjutan (sesi berikutnya, tetap fokus XAUUSD)

**Tanggal:** 9 September 2026 (lanjutan setelah eksplorasi EURUSD)

Setelah kembali fokus XAUUSD, dicoba dua pendekatan tambahan yang belum
dijajal sebelumnya:

### A. Filter arah alternatif untuk horizon 30 menit

36 kombinasi: mean-reversion (RSI, Bollinger %B, Stochastic ekstrem) dan
trend-strength (ADX tinggi + EMA cross). **Semua negatif.** Terbaik:
ADX+EMA, SL 400 pip, E=-0,0981R.

### B. Batas teoritis prediktabilitas (upper bound test)

Diuji dengan LightGBM memakai **52 fitur sekaligus** untuk mengukur
seberapa jauh horizon 30 menit BISA diprediksi sama sekali — bukan mencari
strategi tertentu, tapi mengukur informasi yang tersedia secara matematis.

Percobaan pertama sempat menunjukkan AUC 0,58 (terlihat menjanjikan),
tetapi ditemukan **kebocoran framing**: target itu "memilih arah terbaik
setelah tahu hasil" — bukan cara kerja trading sungguhan (arah harus
ditentukan SEBELUM tahu hasil).

Setelah diperbaiki ke framing yang benar (prediksi arah murni: naik/turun
dalam 30 menit):

```
AUC rata-rata (6 fold): 0,5081
```

**Kembali ke wilayah acak** — identik dengan semua temuan lain sepanjang
hari untuk horizon pendek.

### Kesimpulan akhir yang bisa dipertanggungjawabkan

Total sepanjang hari ini, mencakup sesi sebelum dan sesudah eksplorasi
EURUSD: **200+ kombinasi strategi dan 2 pengujian batas teoritis** untuk
horizon 30 menit di XAUUSDm. Tidak satupun menunjukkan edge yang bertahan.

Ini bukan kegagalan mencari — ini bukti yang cukup kuat bahwa **XAUUSDm
di broker ini, pada horizon keputusan 30 menit, tidak mengandung
informasi yang bisa diprediksi melampaui gerak acak**, terlepas dari
filter, model, atau kombinasi SL/TP yang dicoba.

Keputusan tetap seperti sebelumnya: **sistem 30-menit terpisah tidak
dibangun**, karena membangunnya berarti menjalankan sesuatu yang sudah
terbukti dari datanya sendiri akan merugi secara sistematis.
