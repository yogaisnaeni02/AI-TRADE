# Trailing Stop: Menggeser TP Mengikuti Profit

**Tanggal:** 9 September 2026
**Pertanyaan:** "Bisa tidak TP-nya digeser terus ke arah profit? Misal sudah
profit 30% dari target, kalau turun jadi 5% penurunan profit."

---

## Jawaban Singkat

**Bisa, dan sistem sudah punya mekanismenya.** Tetapi pengujian menunjukkan
trailing justru **menurunkan** hasil pada strategi ini.

Yang Anda gambarkan adalah **trailing stop**: SL digeser mengikuti profit
sehingga keuntungan terkunci. Sudah terpasang di `backtest/engine.py` dan
`src/execution/bot.py` sejak awal, dan sudah diuji dalam banyak varian.

---

## 1. Bug yang Ditemukan Saat Pengujian

Uji pertama memberi hasil yang tampak luar biasa:

```
kunci 0,3R, mundur 20% -> winrate 76,1%, expectancy +0,4401R
```

Angka itu terlalu bagus, jadi diperiksa lagi. Hasil pemeriksaan:

```
Trade dengan profit > 3R : 204   <- MUSTAHIL, TP dibatasi 3R
Profit terbesar          : +22,199R
```

**Penyebabnya lookahead bias.** Kode memperbarui trailing SL memakai `high`/
`low` bar yang sama dengan bar yang sedang diperiksa — artinya SL naik lebih
dulu, baru diperiksa apakah tersentuh. Itu memakai informasi yang belum
tersedia pada saat keputusan dibuat.

### Perbaikan

```python
for j in bar_berikutnya:
    # 1. CEK dulu dengan SL yang berlaku SEBELUM bar ini
    if kena_sl: keluar
    if kena_tp: keluar
    # 2. BARU perbarui trailing, memakai CLOSE bar yang sudah selesai
    peak = max(peak, profit_dari_close)
    sl = geser(peak)
```

Setelah diperbaiki: tidak ada lagi profit di atas 3R, dan hasilnya berubah
total.

> Ini contoh mengapa hasil backtest yang terlihat hebat wajib dicurigai.
> Winrate 76% dengan expectancy +0,44R akan sangat meyakinkan bila tidak
> diperiksa — dan akan gagal total di live.

---

## 2. Hasil Sebenarnya (setelah bug diperbaiki)

Diuji pada 8.971 entry di jendela NY (jam 16–22 UTC, ATR > persentil 60):

| Konfigurasi | Winrate | Expectancy |
|---|---|---|
| **Tanpa trailing** | 42,0% | **+0,0634R** |
| Kunci 2R, mundur 30% | 28,7% | +0,0113R |
| Kunci 1,5R, mundur 30% | 32,2% | −0,0064R |
| Kunci 1R, mundur 30% | 37,1% | −0,0254R |
| Kunci 0,5R, mundur 30% | 45,1% | −0,0255R |
| Kunci 0,3R, mundur 20% | 49,3% | −0,0346R |

**Polanya konsisten: makin agresif trailing, makin buruk hasilnya.**

Perhatikan kolom winrate — trailing memang menaikkannya (42% → 49%). Tetapi
expectancy justru turun. Ini persis mekanisme yang dibahas di
`02-KENAPA-WINRATE-TINGGI-TIDAK-BISA.md`: menang lebih sering dengan profit
lebih kecil bukan perbaikan.

---

## 3. Mengapa Trailing Merugikan di Sini

Strategi ini punya winrate rendah (26–42%) dengan RR tinggi (1:3). Ekonominya
bergantung pada **sedikit pemenang besar** yang menutup banyak kekalahan kecil.

Distribusi hasilnya timpang: sebagian kecil trade menyumbang mayoritas
keuntungan. Trailing memotong justru trade-trade itu.

Bukti dari backtest sebelumnya:

```
Dari 24 trade menang:
   8 mencapai TP penuh
  16 kena trailing SL dengan profit kecil

RR terealisasi: 1:0,98   (target 1:3)
```

Trailing mengubah strategi RR 1:3 menjadi RR 1:1 secara efektif — dan pada
winrate 26%, RR 1:1 pasti merugi.

---

## 4. Uji Stabilitas

| Konfigurasi | Expectancy | In-sample | Out-of-sample | Kuartal positif |
|---|---|---|---|---|
| **Tanpa trailing** | +0,0329R | +0,0063 | **+0,0947** | **4/6** |
| Kunci 2R, mundur 30% | +0,0113R | −0,0117 | +0,0652 | 3/6 |

Tanpa trailing unggul di semua metrik, termasuk out-of-sample.

---

## 5. Kapan Trailing Justru Berguna

Trailing bukan teknik yang buruk — ia cocok untuk profil strategi yang
berbeda:

| Cocok untuk | Tidak cocok untuk |
|---|---|
| Winrate tinggi, RR rendah | **Winrate rendah, RR tinggi** (kasus kita) |
| Strategi trend-following jangka panjang | Strategi dengan TP tetap |
| Posisi ditahan berhari-hari | Posisi ditahan beberapa jam |
| Tujuan: menangkap tren besar | Tujuan: mencapai target tetap |

Pada strategi trend-following H4/D1 yang menahan posisi berminggu-minggu,
trailing sangat masuk akal — tidak ada TP tetap, dan tujuannya memang
mengikuti tren sejauh mungkin.

Pada strategi intraday dengan TP tetap 1.200 pip, trailing hanya memotong
perjalanan menuju target.

---

## 6. Varian yang Layak Dipertimbangkan

Bila tetap ingin mengunci sebagian profit, opsi paling tidak merusak:

### Break-even jauh, tanpa trailing lanjutan

```yaml
breakeven_at_r: 2.0     # SL ke titik impas setelah profit 2R
trail_atr_mult: null    # tidak ada trailing setelahnya
```

Setelah profit 2R (dua pertiga jalan menuju TP), SL digeser ke titik impas.
Trade tidak bisa rugi lagi, tetapi masih bebas mencapai TP penuh.

Hasilnya (+0,0113R) masih di bawah tanpa trailing (+0,0329R), tetapi jauh
lebih baik daripada trailing agresif (−0,0346R). Ini kompromi bila
kenyamanan psikologis lebih diutamakan daripada expectancy maksimum.

### Partial close

Tutup 50% posisi di 1,5R, sisanya dibiarkan mencapai TP. Belum diuji pada
sistem ini; memerlukan dukungan partial close di backtester.

---

## 7. Kesimpulan

| Pertanyaan | Jawaban |
|---|---|
| Bisa TP digeser mengikuti profit? | **Ya**, sudah ada mekanismenya |
| Membantu strategi ini? | **Tidak** — expectancy turun |
| Menaikkan winrate? | Ya (42% → 49%), tetapi profit per trade turun lebih besar |
| Konfigurasi terbaik? | **Tanpa trailing**, biarkan TP tercapai |
| Kompromi bila tetap ingin? | BE di 2R, tanpa trailing lanjutan |
| Ada temuan lain? | **Bug lookahead ditemukan dan diperbaiki** |

Pertanyaan ini bernilai lebih dari jawabannya sendiri: pengujiannya
mengungkap bug lookahead yang membuat backtest melaporkan hasil 13× lebih
baik daripada kenyataan. Bug itu kini diperbaiki, sehingga seluruh angka
lain di sistem ini lebih bisa dipercaya.
