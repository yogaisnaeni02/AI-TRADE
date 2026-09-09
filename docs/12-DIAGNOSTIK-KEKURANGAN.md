# Diagnostik: Di Mana Sistem Kurang

**Tanggal:** 9 September 2026
**Metode:** Analisis segmen pada 86.279 sampel berlabel

Dokumen ini menjawab "sistemnya kurang di mana" dengan memecah data per
segmen dan mengukur winrate masing-masing terhadap breakeven 25,41%.

---

## Temuan 1: Filter Arah Tidak Berguna

Selama ini sistem memakai `trend_htf` (H1+H4) untuk menentukan arah. Hasilnya:

| Bias HTF | Sampel | Winrate |
|---|---|---|
| Uptrend | 48.981 | 23,86% |
| Downtrend | 37.298 | 23,39% |
| **Baseline** | 86.279 | **23,65%** |

**Selisihnya hanya 0,47 poin.** Filter arah yang selama ini dianggap fondasi
sistem ternyata tidak menyaring apa pun — mengikuti tren HTF hampir sama saja
dengan menebak.

Ini menjelaskan kegagalan berulang: seluruh setup dibangun di atas filter
arah yang tidak punya daya prediksi.

---

## Temuan 2: Yang Membedakan adalah KAPAN, Bukan Ke Mana

### Per sesi

| Sesi | Sampel | Winrate | vs breakeven |
|---|---|---|---|
| **Rollover** (21-23 UTC) | 7.632 | **25,88%** | +0,47% |
| **NY sore** (16-21 UTC) | 19.062 | **25,22%** | −0,19% |
| Asia | 30.196 | 23,56% | −1,85% |
| Pre-NY | 9.147 | 23,11% | −2,30% |
| London-NY | 8.896 | 22,89% | −2,52% |
| **London open** | 11.346 | **20,84%** | **−4,57%** |

London open — sesi yang dianggap terbaik di semua panduan trading — justru
paling buruk di data ini.

### Per jam (UTC)

| Terbaik | WR | | Terburuk | WR |
|---|---|---|---|---|
| jam 14 | 29,86% | | jam 9 | 18,99% |
| jam 21 | 25,89% | | jam 8 | 21,10% |
| jam 22 | 25,86% | | jam 12 | 21,29% |
| jam 16 | 25,65% | | jam 15 | 21,30% |

Rentang 11 poin persentase antar jam — jauh lebih besar daripada selisih
antar arah (0,47 poin).

---

## Temuan 3: Regime Bulanan Sangat Berayun

| Bulan | Winrate |
|---|---|
| Ags 2025 | **13,32%** |
| Jul 2025 | 16,63% |
| ... | |
| Okt 2025 | **29,71%** |
| Sep 2026 | 27,13% |

Rentang 13% sampai 30%. Strategi yang bekerja di Oktober bisa hancur di
Agustus. Ini menjelaskan mengapa walk-forward selalu tidak konsisten:
**bukan strateginya yang berubah, pasarnya yang berubah.**

---

## Temuan 4: Volatilitas Tidak Monoton

| Persentil ATR | Winrate |
|---|---|
| 0,0–0,2 | 23,12% |
| **0,2–0,4** | **25,34%** |
| 0,4–0,6 | 22,65% |
| 0,6–0,8 | 23,73% |
| 0,8–1,0 | 23,63% |

Tidak ada pola "makin volatil makin baik" atau sebaliknya. Kombinasi dengan
jam-lah yang memberi hasil, bukan ATR sendirian.

---

## Temuan 5: Kantong Edge yang Ditemukan

| Filter | Sampel | WR | OOS | Kuartal > BE |
|---|---|---|---|---|
| **jam 16-22 + ATR>0,6** | 7.602 | **26,47%** | **26,87%** | **5/6** |
| jam 16-22 + ATR>0,8 | 2.851 | 26,59% | 25,38% | 5/6 |
| jam 21-22 saja | 7.632 | 25,88% | 21,18% | 3/6 |

Yang pertama lolos uji stabilitas: out-of-sample **lebih baik** dari
in-sample, dan konsisten di 5 dari 6 kuartal.

---

## Temuan 6: Trailing Stop Merusak RR

Saat kantong edge itu di-backtest, hasilnya justru buruk (−0,165R). Penyebabnya
ditemukan:

```
Dari 24 trade menang:
   8 kena TP penuh
  16 kena trailing SL  <- profit kecil, RR terpotong

RR terealisasi : 1:0,98  (target 1:3)
```

Break-even di 1,5R dan trailing ATR×2,5 **memotong pemenang sebelum mencapai
TP**. Karena strategi ini bergantung pada sedikit pemenang besar (WR 26%),
memotong mereka menghancurkan seluruh ekonominya.

Tanpa trailing, RR kembali ke 2,71 — sesuai desain.

### Perbandingan manajemen posisi

| Kelola | Trade | WR | Expectancy | RR | Fold+ |
|---|---|---|---|---|---|
| Murni SL/TP | 48 | 22,9% | −0,082R | 2,71 | 1/5 |
| **BE 2R saja** | 111 | 35,1% | **+0,055R** | 1,98 | 2/5 |
| BE 2,5R saja | 32 | 25,0% | −0,272R | 1,63 | 1/5 |
| BE 2R + trail ATR×4 | 111 | 35,1% | +0,055R | 1,98 | 2/5 |

Terbaik: BE di 2R tanpa trailing agresif. Tetapi tetap hanya 2/5 fold positif.

---

## Ringkasan: Kekurangan Sistem

| # | Kekurangan | Bukti |
|---|---|---|
| 1 | **Filter arah tidak berfungsi** | uptrend 23,86% vs downtrend 23,39% |
| 2 | **Setup dibangun di atas filter yang salah** | semua setup memakai trend_htf |
| 3 | **Regime pasar berayun ekstrem** | WR bulanan 13%–30% |
| 4 | **Trailing memotong pemenang** | RR 1:3 jadi 1:0,98 |
| 5 | **Sampel per fold terlalu kecil** | 20–60 trade, butuh 200+ |
| 6 | **Risk limit memblokir 86–97% sinyal** | 1 posisi + 6 trade/hari |
| 7 | **Edge yang ada terlalu tipis** | +1,06% di atas BE, mudah tenggelam biaya |

---

## Apa yang Sebenarnya Terjadi

Celah antara acak dan breakeven hanya 1,76 poin persentase. Kantong edge
terbaik yang ditemukan memberi +1,06 poin di atas breakeven — secara teori
cukup, tetapi:

- Terlalu tipis untuk bertahan setelah slippage nyata
- Terlalu sedikit trade per fold untuk dipastikan bukan kebetulan
- Terlalu sensitif terhadap detail eksekusi (trailing mengubah −0,165R
  menjadi +0,055R)

Sistem tidak "salah". Sistem **terlalu presisi untuk edge sekecil itu**.
Analoginya: mencoba menimbang selembar bulu dengan timbangan beras — alatnya
berfungsi, tetapi tidak dirancang untuk skala tersebut.

---

## Yang Bisa Diperbaiki

### Prioritas 1: Buang filter arah, ganti dengan filter waktu

Diagnostik menunjukkan waktu jauh lebih menentukan daripada arah. Setup
berikutnya sebaiknya:
- Tidak memakai `trend_htf` sebagai syarat
- Memakai jam sebagai fitur utama
- Menentukan arah dengan cara lain (misalnya breakout, bukan tren)

### Prioritas 2: Perbaiki manajemen posisi

Trailing agresif terbukti merusak. Untuk strategi WR rendah dengan RR tinggi,
pemenang harus dibiarkan mencapai TP.

### Prioritas 3: Longgarkan risk limit untuk pengujian

Memblokir 97% sinyal membuat sampel terlalu kecil untuk kesimpulan. Untuk
riset, jalankan tanpa batas 1-posisi agar statistiknya bermakna; batas tetap
dipakai saat live.

### Prioritas 4: Terima bahwa XAUUSD M5 mungkin bukan medan yang tepat

Setelah menguji indikator klasik, struktur pasar, Fibonacci, momentum,
sesi, machine learning, dan sekarang diagnostik per segmen — edge terkuat
yang ditemukan hanya +1,06% di atas breakeven, dan itu pun tidak bertahan
saat dieksekusi dengan manajemen posisi apa pun.

Ini bukan alasan untuk berhenti, tetapi data yang layak dipertimbangkan
sebelum menambah waktu di kombinasi instrumen-timeframe yang sama.
