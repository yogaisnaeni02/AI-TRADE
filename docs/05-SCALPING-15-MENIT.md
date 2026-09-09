# Analisis: Scalping M5 dengan Target Profit 15 Menit

**Tanggal:** 9 September 2026
**Pertanyaan:** "Bisa tidak scalping di M5 dengan target profit besar per 15 menit?"

---

## Jawaban Singkat

**Pergerakannya ada. Yang tidak ada adalah edge untuk menangkapnya.**

Gold bergerak median **461 pip dalam 15 menit** (3 bar M5). Spread 26 pip
hanya memakan 6% dari pergerakan itu. Jadi secara ukuran gerakan, target
besar dalam 15 menit sepenuhnya realistis.

Masalahnya ada di tempat lain, dan diuraikan di bawah.

---

## 1. Pergerakan Aktual dalam 15 Menit

Diukur dari 100.000 bar M5 (April 2025 – September 2026):

| Statistik | Pergerakan terbaik dalam 3 bar M5 |
|---|---|
| Median | 4.605 points = **461 pip** |
| Persentil 75 | 7.408 points = 741 pip |
| Persentil 90 | 11.743 points = 1.174 pip |

Spread 260 points hanya **6% dari pergerakan median**. Ini kabar bagus:
biaya bukan penghalang utama di jangka waktu ini.

---

## 2. Masalah Sebenarnya: Asimetri TP dan SL

SL tidak bisa lebih sempit dari sekitar 650 pip (ATR × 1,5). Jika lebih
sempit, SL berada di dalam rentang gerak normal satu bar dan akan tersentuh
oleh noise — sudah dibuktikan di backtest sebelumnya (winrate anjlok ke 23,8%).

Konsekuensinya, target kecil menghasilkan RR terbalik:

| Target TP | Spread sbg % TP | RR (SL 650 pip) | Winrate agar impas |
|---|---|---|---|
| 30 pip | 87% | 1 : 0,05 | **99%** |
| 50 pip | 52% | 1 : 0,08 | **96%** |
| 80 pip | 32% | 1 : 0,12 | 92% |
| 120 pip | 22% | 1 : 0,18 | 87% |
| 200 pip | 13% | 1 : 0,31 | 79% |
| 300 pip | 9% | 1 : 0,46 | **70%** |

Baris terakhir: untuk target 300 pip, Anda mempertaruhkan 650 pip demi 300 pip.
Sistem baru impas bila menang 70% dari waktu.

Ini pola yang sama dengan yang dibahas di `02-KENAPA-WINRATE-TINGGI-TIDAK-BISA.md`:
**target kecil memaksa winrate tinggi, dan winrate tinggi tidak tersedia.**

---

## 3. Uji Empiris: Timeout Cepat

Diuji langsung pada strategi London Sweep — posisi ditutup paksa setelah N bar:

| Timeout | Setara | Trade | Winrate | Expectancy | PF |
|---|---|---|---|---|---|
| 3 bar | **15 menit** | 339 | 48,1% | **−0,003R** | 0,99 |
| 6 bar | 30 menit | 339 | 48,7% | +0,003R | 1,01 |
| 12 bar | 60 menit | 339 | 46,6% | −0,022R | 0,95 |
| 24 bar | 2 jam | 339 | 45,4% | −0,015R | 0,96 |
| 48 bar | 4 jam | 339 | 44,8% | +0,038R | 1,03 |
| 120 bar | 10 jam | 339 | 44,8% | +0,048R | 1,03 |

**Temuan:** timeout 15 menit menghasilkan expectancy −0,003R — praktis nol,
dan tidak berbeda bermakna dari varian lain. Semuanya berkisar di breakeven.

**Artinya:** durasi tahan posisi bukan variabel yang menentukan di sini.
Mengubahnya tidak memperbaiki apa pun, karena masalahnya ada di hulu.

---

## 4. Akar Masalahnya: Strategi Belum Punya Edge

Uji out-of-sample pada strategi yang sama:

```
IN-SAMPLE  (Apr 2025 - Mar 2026) : +0,232R, PF 1,36
OUT-SAMPLE (Mar 2026 - Aug 2026) : -0,225R, PF 0,65
```

Strategi yang tampak bagus di periode tempat parameter dituning, justru rugi
di data yang belum pernah disentuh. Ini **curve fitting** — pola yang
ditemukan adalah noise, bukan keunggulan yang berulang.

Uji sensitivitas mengonfirmasi kerapuhannya: menggeser parameter 20% memotong
expectancy separuh (+0,108R → +0,048R). Edge yang nyata tidak serapuh itu.

**Konsekuensinya untuk pertanyaan ini:** timing entry dan durasi exit hanya
bisa mengoptimalkan sinyal yang sudah punya keunggulan. Bila sinyalnya sendiri
belum unggul, mengubah target 15 menit, 30 menit, atau 4 jam sama saja —
seperti mengatur ulang jadwal keberangkatan kendaraan yang mesinnya belum
menyala.

---

## 5. Yang Bisa Dikerjakan

### Untuk membuat scalping cepat masuk akal

Prasyaratnya berurutan, dan tidak bisa dilompati:

1. **Temukan setup dengan edge yang lolos out-of-sample.** Ini pekerjaan
   Tahap 2 yang belum tuntas — gerbangnya belum lulus.
2. **Setelah itu**, optimalkan timing exit. Data timeout di atas menunjukkan
   perbedaan antar durasi kecil, jadi ini optimasi tahap akhir, bukan awal.
3. **Target minimum tetap 300 pip.** Di bawah itu, RR terbalik dan sistem
   menuntut winrate yang tidak tersedia.

### Arah yang lebih menjanjikan daripada mempercepat exit

| Arah | Alasan |
|---|---|
| **Cari setup baru** | Masalahnya di kualitas sinyal, bukan timing |
| **Kurangi SL lewat entry presisi (M1)** | SL 650 pip berasal dari entry yang kasar. Entry lebih presisi memungkinkan SL lebih sempit tanpa kena noise — ini melonggarkan seluruh persamaan |
| **Uji instrumen lain** | EURUSD punya rasio ATR-terhadap-spread jauh lebih baik |
| **Terima horizon lebih panjang** | Data menunjukkan 4-10 jam sedikit lebih baik daripada 15 menit |

Poin kedua layak diperhatikan: **entry yang lebih presisi adalah pengungkit
terbesar yang belum dipakai.** SL 650 pip diperlukan karena entry ditentukan
di close bar M5. Bila entry ditentukan di M1 pada level yang lebih tepat, SL
bisa turun ke 300–400 pip — dan itu langsung memperbaiki RR untuk semua target,
termasuk target 15 menit.

---

## 6. Kesimpulan

| Pertanyaan | Jawaban |
|---|---|
| Gold bergerak cukup dalam 15 menit? | **Ya** — median 461 pip |
| Spread menghalangi? | **Tidak** — hanya 6% dari gerakan |
| Target besar per 15 menit mungkin? | **Ya**, bila target ≥ 300 pip |
| Bisa dijalankan sekarang? | **Belum** — strategi belum punya edge |
| Apa yang menghalangi? | Kualitas sinyal, bukan timing exit |

Pertanyaan ini bagus dan arahnya benar. Yang perlu digeser hanya urutannya:
**edge dulu, timing kemudian.** Mempercepat exit pada sinyal yang belum unggul
tidak mengubah hasil — sudah dibuktikan secara empiris di Bagian 3.
