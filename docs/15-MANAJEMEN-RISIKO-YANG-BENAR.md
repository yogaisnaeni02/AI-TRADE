# Manajemen Risiko: "Sudah Profit Lalu Jadi Rugi"

**Tanggal:** 9 September 2026
**Pertanyaan:** "Aku mau manajemen risiko, jadi kalau sudah profit terus
malah loss gitu, baiknya gimana?"

---

## Klarifikasi Awal

**Tanpa trailing, TP tidak berubah.** TP tetap terpasang di 1.200 pip sejak
entry sampai posisi tertutup. Yang bergerak hanya harga — mendekati atau
menjauhi TP.

Yang Anda khawatirkan berbeda dan valid: posisi sudah menunjukkan profit,
lalu berbalik dan kena SL.

---

## 1. Seberapa Sering Ini Terjadi?

Diukur pada 8.971 trade:

| Kondisi | Jumlah | Porsi |
|---|---|---|
| Total trade | 8.971 | 100% |
| Trade kalah | 6.581 | 73,4% |
| **Kalah setelah sempat profit ≥ 80 pip** | **4.874** | **54,3% dari semua trade** |

Puncak profit sebelum akhirnya kalah:

```
median : 235 pip
p75    : 518 pip
p90    : 841 pip
```

**Kekhawatiran Anda terbukti sangat nyata.** Lebih dari separuh trade sempat
menunjukkan profit sebelum berbalik jadi rugi penuh.

---

## 2. Solusi yang Terlihat Jelas: Breakeven

Pasang SL ke titik impas setelah profit tertentu. Trade tidak bisa rugi lagi.

Hasil pengujian:

| BE di | Winrate | Expectancy | Loss penuh | Impas | Menang penuh (3R) |
|---|---|---|---|---|---|
| **Tanpa BE** | 26,6% | **+0,0329R** | 6.571 | — | **2.236** |
| 80 pip | 51,5% | −0,0147R | 4.353 | 3.270 | 1.328 |
| 250 pip | 42,8% | −0,0030R | 5.131 | 2.157 | 1.635 |
| 400 pip | 37,1% | +0,0065R | 5.643 | 1.421 | 1.846 |
| 600 pip | 32,2% | +0,0205R | 6.081 | 759 | 2.040 |
| 800 pip | 28,7% | +0,0299R | 6.384 | 291 | 2.170 |

### Perhitungan trade-off pada BE 80 pip

```
Loss penuh dihindari : 6.571 - 4.353 = 2.218 trade  ->  hemat +2.218R
Pemenang TP hilang   : 2.236 - 1.328 =   908 trade  ->  hilang -2.724R
                                                        ------------
Selisih bersih                                          -506R
```

Setiap satu pemenang yang terpotong (bernilai 3R) menghapus keuntungan dari
tiga loss yang diselamatkan (bernilai 1R masing-masing). Karena 908 pemenang
hilang sementara hanya 2.218 loss diselamatkan, rasionya merugikan.

---

## 3. Temuan Terpenting: Breakeven Tidak Mengurangi Risiko

Ini yang mengubah kesimpulan. Diukur dengan metrik risiko, bukan expectancy —
simulasi 500 skenario, 300 trade, risiko 3% per trade:

| Konfigurasi | Expectancy | **Max Drawdown** | Loss beruntun | **Peluang rugi** |
|---|---|---|---|---|
| Tanpa BE | +0,0329R | **62,7%** | 15 | **54%** |
| BE 250 pip | −0,0030R | 61,1% | 9 | 67% |
| BE 400 pip | +0,0065R | 63,8% | 10 | 65% |
| BE 600 pip | +0,0205R | 63,2% | 12 | 57% |
| BE 800 pip | +0,0299R | 64,4% | 14 | 60% |

**Drawdown praktis sama di semua konfigurasi (61–64%).** Breakeven tidak
melindungi modal.

Yang berubah:
- Loss beruntun berkurang (15 → 9) — ini manfaat **psikologis**, nyata tetapi
  bukan proteksi modal
- Peluang rugi justru **naik** (54% → 67%)

Breakeven membuat perjalanan terasa lebih nyaman sambil membuat hasil akhir
lebih buruk.

---

## 4. Sumber Risiko yang Sebenarnya

Drawdown 62% itu bukan berasal dari "profit yang berbalik". Berasal dari
**ukuran risiko per trade**.

Simulasi winrate 26,6%, RR 1:3, 300 trade:

| Risiko/trade | Max Drawdown | Peluang rugi | Peluang DD > 30% | Hasil akhir (median) |
|---|---|---|---|---|
| **0,5%** | **12,8%** | 28% | **1%** | 1,07× |
| **1,0%** | **25,0%** | 34% | 28% | **1,17×** |
| 1,5% | 34,3% | 34% | 68% | 1,22× |
| 2,0% | 43,4% | 40% | 89% | 1,24× |
| **3,0%** (sekarang) | **58,5%** | 43% | **99%** | 1,08× |
| 5,0% | 81,4% | 56% | 100% | 0,74× |

### Aritmetikanya sederhana

Dengan winrate 26%, rentetan **10–15 kekalahan beruntun adalah kejadian
normal** — bukan nasib buruk.

```
Risiko 3% x 15 loss beruntun  =  -36% equity
Risiko 1% x 15 loss beruntun  =  -14% equity
```

Perhatikan juga kolom terakhir: risiko 3% menghasilkan 1,08× sementara
risiko 1% menghasilkan **1,17×** — lebih besar dengan drawdown kurang dari
separuhnya. Pada winrate rendah, risiko besar justru menurunkan hasil akhir
karena kerugian beruntun menggerus basis compounding.

---

## 5. Rekomendasi

### Manajemen risiko yang benar untuk kekhawatiran Anda

| Langkah | Alasan |
|---|---|
| **Turunkan risiko ke 1% per trade** | DD turun 62% → 25%, hasil akhir justru naik |
| **Biarkan TP tercapai** (tanpa BE/trailing) | Expectancy tertinggi, pemenang tidak terpotong |
| Pertahankan batas harian & de-risking | Sudah aktif di risk manager |

Risiko 1% masih **dua kali lipat** standar profesional (0,5%), jadi tetap
tergolong agresif — tetapi tanpa drawdown yang merusak.

### Bila kenyamanan psikologis tetap diprioritaskan

```yaml
breakeven_at_r: 2.0     # ~800 pip, SL ke titik impas
trail_atr_mult: null    # tanpa trailing lanjutan
```

BE di 800 pip hampir tidak menurunkan expectancy (+0,0299R vs +0,0329R)
tetapi menghilangkan 291 trade dari zona rugi. Ini kompromi paling murah.

**Jangan pasang BE di 80–250 pip.** Di rentang itu, biayanya paling mahal:
expectancy negatif tanpa perbaikan drawdown.

---

## 6. Ringkasan

| Pertanyaan | Jawaban |
|---|---|
| Tanpa trailing, TP berubah? | **Tidak** — TP tetap sejak entry |
| Sering profit lalu rugi? | **Ya** — 54,3% dari semua trade |
| Breakeven menyelesaikannya? | **Tidak** — DD tetap ~62%, peluang rugi naik |
| Apa yang benar-benar menurunkan risiko? | **Risiko per trade**: 3% → 1% memangkas DD dari 62% ke 25% |
| Kompromi paling murah? | BE di 800 pip (biaya hanya −0,003R) |

Pertanyaan Anda mengarah ke tempat yang tepat — hanya tuasnya berbeda dari
yang diperkirakan. Yang melindungi modal bukan **kapan keluar dari satu
trade**, melainkan **seberapa besar taruhan di setiap trade**.

---

## 7. Catatan Implementasi: Batas Lot Minimum

Risiko 1% tidak sepenuhnya tercapai pada equity Rp 3,7 juta, karena lot
minimum broker (0,01) tidak bisa dibagi lebih kecil.

```
Risiko pada lot 0,01 dengan SL 400 pip = Rp 69.934 (nilai tetap)
```

| Equity | Risiko aktual di lot minimum |
|---|---|
| Rp 3.700.000 | **1,89%** |
| Rp 5.000.000 | 1,40% |
| **Rp 7.000.000** | **1,00%** |
| Rp 10.000.000 | 0,70% |

**Untuk risiko 1% presisi dibutuhkan equity sekitar Rp 7 juta.**

Pada equity Rp 3,7 juta, risiko terkecil yang bisa dicapai adalah 1,89% —
sudah jauh lebih baik daripada 3%, tetapi belum optimal.

### Konsekuensinya

Konfigurasi `max_risk_percent: 1.0` tetap dipakai karena:
- Pada equity di bawah Rp 7 juta, sistem otomatis memakai lot minimum
  (risiko efektif 1,4–1,9%)
- Saat equity tumbuh melewati Rp 7 juta, risiko 1% tercapai dengan
  sendirinya tanpa perubahan konfigurasi

Ini juga alasan tambahan mengapa XAUUSD menuntut modal lebih besar: bukan
hanya untuk membuka posisi, tetapi untuk mengendalikan risiko dengan presisi.
