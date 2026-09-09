# Analisis: Risk-Reward 1:3 (SL 100 pip / TP 300 pip)

**Tanggal:** 9 September 2026
**Pertanyaan:** "Kenapa tidak pakai SL 100 pip dan TP 300 pip saja (RR 1:3)?"

---

## Jawaban Singkat

**Prinsip 1:3 benar. Angka 100 pip yang bermasalah.**

SL 100 pip tersentuh dalam satu bar M5 pada **98% dari waktu**, karena range
bar M5 median adalah 379 pip. SL itu berada jauh di dalam gerakan normal satu
bar — ia kena oleh noise, bukan oleh arah pasar yang salah.

Pengujian juga mengungkap sesuatu yang lebih mendasar tentang seluruh proyek
ini, diuraikan di Bagian 3.

---

## 1. Mengapa SL 100 Pip Gagal

```
Range bar M5 (median)              : 3.793 points = 379 pip
Bar dengan range >= 100 pip        : 97,6%
```

SL 100 pip lebih kecil dari gerakan satu bar tunggal. Ini setara memasang
stop 5 pip di EURUSD — dijamin tersentuh oleh fluktuasi biasa.

### Hasil simulasi (SL 100 pip / TP 300 pip, 3.992 sampel)

| Hasil | Jumlah | Persentase |
|---|---|---|
| TP tersentuh duluan | 870 | **21,8%** |
| SL tersentuh duluan | 3.121 | 78,2% |

```
Breakeven winrate (setelah spread) : 26,7%
Winrate aktual                     : 21,8%
Expectancy                         : -0,39 R per trade
```

Rugi, meski RR-nya 1:3.

---

## 2. Mencari SL yang Benar untuk RR 1:3

Diuji dengan **entry acak** (tanpa strategi apa pun), untuk mengukur
karakteristik pasar itu sendiri:

| SL (pip) | TP (pip) | Winrate | Breakeven WR | Expectancy |
|---|---|---|---|---|
| 100 | 300 | 21,5% | 26,7% | −0,401R |
| 200 | 600 | 24,9% | 25,8% | −0,136R |
| 300 | 900 | 25,0% | 25,6% | −0,085R |
| **400** | **1.200** | **24,7%** | **25,4%** | **−0,076R** |
| 500 | 1.500 | 24,0% | 25,3% | −0,093R |
| 650 | 1.950 | 22,4% | 25,3% | −0,145R |
| 800 | 2.400 | 21,1% | 25,2% | −0,187R |

**SL optimal untuk RR 1:3 adalah sekitar 400 pip** — jauh dari 100 pip, tetapi
juga lebih sempit dari 650 pip yang dipakai sebelumnya.

---

## 3. Temuan Terpenting: Pasar Nyaris Efisien

Perhatikan baris SL 400 pip:

```
Winrate aktual (entry acak) : 24,7%
Breakeven winrate           : 25,4%
Selisih                     : 0,7%
```

**Jarak antara acak dan impas hanya 0,7 poin persentase.** Yang mendorong ke
sisi rugi adalah spread 26 pip.

Ini pengukuran paling berharga dari seluruh proyek, dan maknanya dua sisi:

**Sisi baik:** celahnya sempit. Strategi hanya perlu menaikkan winrate sekitar
1–2% di atas acak untuk menjadi profitabel. Bukan 20%, bukan 10%.

**Sisi berat:** tidak ada ruang untuk kesalahan. Setiap sinyal yang tidak
lebih baik dari acak langsung menghasilkan kerugian, karena spread tidak
memberi margin toleransi.

Ini juga penjelasan kuantitatif mengapa mayoritas sistem trading ritel gagal:
mereka harus mengalahkan pasar yang hampir efisien sambil membayar biaya di
setiap transaksi.

---

## 4. Uji Strategi pada RR 1:3

Rule engine dijalankan dengan SL 400 pip / TP 1.200 pip:

| Filter | Trade | Winrate | Expectancy | PF |
|---|---|---|---|---|
| Semua sinyal | 22 | 13,6% | −0,460R | 0,46 |
| london_sweep | 26 | 15,4% | −0,390R | 0,53 |
| sweep + buy | 23 | 17,4% | −0,310R | 0,55 |
| sweep skor ≤ 6 | 34 | **23,5%** | −0,145R | 0,69 |
| **Entry acak (pembanding)** | — | **24,7%** | −0,076R | — |

**Setup terbaik kita menghasilkan winrate 23,5% — di bawah entry acak 24,7%.**

Rule engine ini tidak sekadar belum punya edge; ia sedikit lebih buruk
daripada masuk pasar secara acak. Filter yang dirancang untuk meningkatkan
kualitas justru membuang peluang yang layak.

Ini konsisten dengan uji out-of-sample sebelumnya (+0,232R in-sample menjadi
−0,225R out-of-sample) dan dengan temuan bahwa skor tinggi berkinerja lebih
buruk daripada skor rendah. Ketiganya menunjuk ke satu kesimpulan yang sama:
**sinyal yang dihasilkan belum mengandung informasi prediktif.**

---

## 5. Apa Artinya untuk Proyek Ini

### Yang sudah pasti

| Temuan | Status |
|---|---|
| SL harus 300–500 pip (bukan 100, bukan 650) | Terukur |
| RR 1:3 adalah arah yang benar | Terkonfirmasi |
| Pasar hampir efisien — celah 0,7% | Terukur |
| Rule engine saat ini tidak punya edge | Terbukti tiga cara |

### Yang perlu dikerjakan

Masalahnya bukan pada parameter SL/TP, timeout, atau ukuran target. Semua itu
sudah diuji dan tidak mengubah kesimpulan. Masalahnya ada pada **kualitas
sinyal**.

Arah yang masih terbuka, diurutkan dari yang paling menjanjikan:

1. **Entry presisi lewat M1.** Saat ini entry ditentukan di close bar M5 —
   kasar. Entry di level yang lebih tepat (dengan M1) memungkinkan SL lebih
   sempit tanpa terkena noise, dan itu memperbaiki seluruh persamaan RR.

2. **Setup yang berbeda.** London Sweep sudah terbukti tidak bekerja pada
   data ini. Kandidat lain: order block retest, breakout dengan konfirmasi
   volume, mean reversion di sesi Asia.

3. **Machine learning sebagai penyaring.** Roadmap menempatkan ML setelah
   rule engine punya edge — tetapi mengingat celahnya hanya 0,7%, ML mungkin
   justru alat yang tepat untuk menemukan pola yang tidak terlihat oleh
   aturan manual. Ini penyimpangan dari rencana awal yang layak
   dipertimbangkan.

4. **Instrumen lain.** EURUSD memiliki rasio ATR-terhadap-spread yang jauh
   lebih baik, sehingga celahnya lebih lebar dan lebih mudah dilampaui.

---

## 6. Kesimpulan

| Pertanyaan | Jawaban |
|---|---|
| RR 1:3 ide yang bagus? | **Ya** — arah yang benar |
| SL 100 pip bisa dipakai? | **Tidak** — kena noise 98% dari waktu |
| SL yang benar berapa? | **300–500 pip** untuk XAUUSD M5 |
| Dengan SL benar, 1:3 profitabel? | **Belum** — masih −0,076R karena spread |
| Apa yang kurang? | **Edge pada sinyal**, bukan parameter |
| Seberapa besar edge yang dibutuhkan? | **Winrate +1-2% di atas acak** |

Angka terakhir adalah target yang konkret dan terukur — dan itu jauh lebih
berguna daripada mengejar "winrate tinggi" yang abstrak.
