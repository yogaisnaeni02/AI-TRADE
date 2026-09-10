# Uji: Menambah M1 sebagai Konfirmasi Entry

**Tanggal:** 10 September 2026
**Permintaan:** "membaca pasar bisa gak ditambah lagi dari M1 biar lebih valid?"

---

## Jawaban Singkat

**Tidak terbukti membantu.** Enam varian filter M1 diuji pada periode yang
sama; lima memperburuk hasil, satu tampak membaik tetapi terbukti tidak
stabil saat dibelah dua.

Namun M1 **sudah dipakai** di sistem ini — untuk resolusi exit, bukan entry.
Lihat bagian 4.

---

## 1. Kondisi Sekarang

Bot membaca **M5 (utama) + H1 + H4 (filter tren)** — `src/execution/bot.py`
baris 170-194. M1 tidak dibaca bot live.

Kendala data: M1 hanya tersedia **103 hari**, sedangkan M5 **516 hari**.
Batas 100.000 bar dari MT5 berlaku untuk semua timeframe, jadi makin kecil
timeframe makin pendek jangkauan sejarahnya. Setiap uji yang melibatkan M1
otomatis kehilangan 80% periode pengujian.

---

## 2. Kesalahan pada Pengukuran Pertama

Pengukuran pertama melaporkan filter M1 menaikkan expectancy dari −0,15R ke
+0,11R. **Angka itu salah** dan perlu dicatat supaya tidak terulang.

Baseline hanya menghasilkan **31 trade dari 697 sinyal**. Sebabnya: circuit
breaker 20% drawdown tersentuh 17 Juni, lalu `Backtester.run()` berhenti
total (`halted = True`). Baseline hanya memperdagangkan **19 hari dari 103**.

Varian berfilter kebetulan menghindari rentetan rugi awal, tidak kena halt,
dan terus jalan sampai September. Jadi yang dibandingkan bukan kualitas
filter, melainkan **rentang waktu yang berbeda**.

Tanda bahaya yang seharusnya langsung terlihat: filter yang MEMBUANG sinyal
justru menghasilkan trade LEBIH BANYAK (31 -> 99). Itu mustahil bila
periodenya sama.

**Perbaikan:** circuit breaker dan batas harian dimatikan khusus untuk
pengukuran, supaya semua varian memperdagangkan 103 hari yang sama.
Guardrail tetap aktif di produksi — di konteks pengukuran ia mengaburkan,
bukan melindungi.

---

## 3. Hasil Setelah Diperbaiki

Periode 29 Mei - 9 Sep 2026 (103 hari), 697 sinyal mentah, semua varian
memperdagangkan rentang yang sama:

| Varian | n | E[R] | WR% | PF | t |
|---|---|---|---|---|---|
| **BASELINE (M5+H1+H4)** | 162 | **+0,0044** | 26,5 | 1,01 | 0,03 |
| + M1 EMA9>EMA21 searah | 146 | −0,0664 | 24,7 | 0,91 | −0,49 |
| + M1 momentum(5) searah | 145 | −0,0601 | 24,8 | 0,92 | −0,44 |
| + M1 momentum(15) searah | 142 | −0,1202 | 23,2 | 0,84 | −0,88 |
| + M1 bar terakhir searah | 134 | −0,0107 | 26,1 | 0,99 | −0,07 |
| + M1 momentum LAWAN (pullback) | 101 | +0,1234 | 29,7 | 1,17 | 0,71 |
| + M1 EMA & momentum searah | 130 | −0,0965 | 23,8 | 0,87 | −0,67 |

### Temuan utama

**Konfirmasi searah justru merugikan.** Semua varian yang menuntut M1
bergerak searah sinyal menghasilkan expectancy lebih rendah dari baseline.

Ini konsisten dengan temuan lama di `docs/22`: di skala sangat pendek pasar
lebih dekat ke mean-reversion. Menunggu M1 "mengonfirmasi" arah berarti
masuk setelah dorongan pendek sudah habis — entry jadi lebih buruk, bukan
lebih valid.

### Varian pullback tidak lolos verifikasi

Satu-satunya varian positif adalah kebalikannya: masuk saat M1 bergerak
BERLAWANAN (pullback). Terlihat menarik, tetapi gagal dua pemeriksaan:

**Signifikansi.** t = 0,71 pada n = 101; p mentah 0,479. Setelah koreksi
Bonferroni untuk 6 varian yang diuji, ambang t yang jujur adalah **2,69**.
Terukur 0,71 — tidak mendekati.

**Stabilitas belah-dua.**

```
PARUH-1 (Mei-Jul) : n=40  E=-0,3415R  WR=17,5%  t=-1,48
PARUH-2 (Jul-Sep) : n=61  E=+0,4282R  WR=37,7%  t=+1,80
```

Dua paruh berlawanan arah. Angka +0,12R adalah rata-rata dari periode sangat
rugi dan periode sangat untung — bukan edge yang stabil. Memakainya berarti
bertaruh bahwa paruh kedua yang mewakili masa depan, tanpa dasar.

---

## 4. M1 Sudah Dipakai — untuk Exit, Bukan Entry

`backtest/engine.py::_resolve_m1` (baris 132) sudah memakai M1 untuk hal
yang memang membutuhkannya: **urutan sentuhan SL/TP dalam satu bar M5**.

Bila dalam satu bar M5 harga menyentuh SL dan TP sekaligus, data M5 tidak
menyimpan mana yang duluan. M1 membuka urutan sebenarnya. Di luar jangkauan
M1, backtester memakai asumsi pesimis (anggap SL duluan).

Ini pemakaian M1 yang tepat: **menambah resolusi pada fakta yang sudah
terjadi**, bukan menebak arah yang belum terjadi.

---

## 5. Kesimpulan

Menambah M1 ke pembacaan pasar untuk entry **tidak dilakukan**, karena:

1. Semua varian konfirmasi searah memperburuk expectancy
2. Varian pullback tidak lolos uji signifikansi maupun stabilitas
3. Data M1 hanya 103 hari — sampel apa pun yang melibatkannya jauh lebih
   lemah daripada 516 hari M5
4. Menambahnya berarti mengubah logika sinyal saat forward test berjalan,
   yang dilarang di `docs/29` bagian "Yang TIDAK boleh dikerjakan sekarang"

"Lebih banyak timeframe" tidak sama dengan "lebih valid". Setiap filter
tambahan memotong jumlah sampel, dan filter yang tidak punya daya prediksi
hanya membuang trade yang baik bersama yang buruk.

Ide M1 yang masih layak diuji kelak ada di `docs/29` bagian 10c: memakai M1
untuk **presisi harga entry** (bukan sebagai filter ya/tidak), sehingga SL
bisa lebih rapat dari 400 pip. Itu menaikkan RR, mekanisme yang berbeda dari
yang diuji di sini, dan baru relevan setelah forward test selesai.
