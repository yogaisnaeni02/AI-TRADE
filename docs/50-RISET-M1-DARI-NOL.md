# Riset M1 dari Nol — Hasil: Tetap Rugi, Sebabnya Sekarang Terukur

**Tanggal:** 13 September 2026
**Permintaan pemilik:** "coba tetep buatkan dengan M1 itu ya" — riset baru
dari nol, bukan menyalin gate `momentum_fib` M5 (yang sudah terbukti
gagal di M1 pada `docs/22`).

---

## Ringkasan

**Tetap rugi di semua 13 kombinasi yang diuji.** Tapi kali ini alasannya
terukur presisi, bukan cuma "sudah dicoba dan gagal": **rasio spread
terhadap SL di M1 dua kali lebih mahal dibanding M5**, dan realisasi
winrate jatuh lebih jauh dari breakeven-nya sendiri dibanding di M5.

Satu perbaikan penting dari riset sebelumnya: asumsi lama soal ukuran
gerakan M1 ("40-80 pip") **sudah usang** — harga emas sekarang jauh lebih
tinggi dari saat asumsi itu dibuat. ATR M1 median sekarang **198 pip**.
Diagnosis di dokumen ini memakai angka yang baru diukur, bukan asumsi
lama yang sudah tidak berlaku.

---

## 1. Kenapa Ini Bukan Sekadar Mengulang docs/22

`docs/22` menerapkan gate `momentum_fib` M5 **langsung** di M1 —
SL/TP-nya (400–4.500 points) dikalibrasi untuk skala gerakan M5, dipaksa
ke M1 tanpa penyesuaian. Itu cacat desain sejak awal.

Di sini SL/TP dibangun dari **ATR M1 yang benar-benar diukur** pada bar
itu sendiri (adaptif, bukan angka tetap), dan gate momentum/tren/fib
dibangun ulang dengan parameter M1 (`mom_12`, bukan `mom_24` M5).

---

## 2. Temuan Pertama: Skala Gerakan M1 Sudah Berubah

```
ATR(14) M1 median SEKARANG : 198 pip
Asumsi lama (docs/22)      : 40-80 pip
```

Penyebabnya jelas: harga emas saat data lama dipakai (~$1.800–3.200) jauh
lebih rendah dari sekarang (~$4.400). Pergerakan dalam satuan pip naik
sebanding dengan level harga. Ini bukan berarti kesimpulan lama salah,
tapi angka SL/TP yang dipakai di eksperimen lama sudah tidak relevan
untuk kondisi sekarang — makanya riset ini dimulai ulang dari pengukuran
segar, bukan mewarisi angka lama.

---

## 3. Uji Sinyal Baru: Momentum M1 + Tren HTF + Fibonacci

Gate dibangun dari nol: `mom_12` (momentum 12 menit) melewati kuantil-80
rolling, searah `trend_htf`, posisi harga sesuai `fib_position`. Hasil:
**6.001 kandidat sinyal dalam 103 hari** — frekuensi tinggi seperti yang
diharapkan dari M1.

### Delapan kombinasi SL/TP (berbasis ATR aktual), semua rugi

| SL(×ATR) | TP(×ATR) | RR | E[R] penuh | t | E[R] holdout |
|---|---|---|---|---|---|
| 1,0 | 2,0 | 2,0 | −0,1416 | −8,09 | −0,0223 |
| 1,0 | 3,0 | 3,0 | −0,1961 | −9,48 | −0,0774 |
| 1,5 | 3,0 | 2,0 | −0,2076 | −12,16 | −0,1443 |
| 2,0 | 4,0 | 2,0 | −0,1561 | −8,97 | −0,0655 |
| 1,0 | 1,5 | 1,5 | −0,1822 | −12,03 | −0,0910 |

Ditambah lima varian RR lebih tinggi (4,0–8,0×) untuk mengompensasi
spread yang proporsinya lebih besar — **semua tetap negatif**, satu
varian (RR 5,0) mendekati nol di holdout (+0,0030, t=+0,06) tapi
winrate-nya cuma 14,0% — terlalu jarang menang untuk dipercaya di luar
sampel kecil.

---

## 4. Diagnosis: Kenapa Tepatnya M1 Kalah — Bukan Cuma "Terbukti Gagal Lagi"

### Bukan karena harga M1 lebih acak dari M5

Diuji entry **acak murni** (tanpa strategi apa pun), RR sama (1:2),
horizon sebanding:

```
M1 entry acak : WR 28,6%
M5 entry acak : WR 30,2%
```

Selisih cuma 1,6 poin persentase — karakter dasar pergerakan harga M1
dan M5 **mirip**. Ini penting: kalau M1 secara struktur jauh lebih acak,
itu akan jadi penyebab utama. Tapi tidak.

### Penyebab sesungguhnya: rasio spread/SL dua kali lebih mahal

```
                    M1              M5
Spread              260 pts         260 pts (SAMA, broker fixed)
SL median (1×ATR)   2.004 pts       ~4.240 pts
Spread/SL           13,0%           6,1%
```

Spread broker **tetap** (260 points) di semua timeframe. Tapi SL yang
proporsional di M1 jauh lebih kecil (ATR-nya lebih kecil), sehingga
spread yang sama memakan porsi risiko dua kali lebih besar.

### Dampaknya ke breakeven

```
                          M1        M5 (docs/06)
Breakeven WR (RR 1:2)     37,7%     26,6%
Realisasi WR (acak)       28,6%     30,2%
Selisih ke breakeven      -9,1pp    +3,6pp (UNTUNG)
```

Di M5, entry acak sudah **di atas** breakeven-nya sendiri (itu dasar
kenapa `momentum_fib` bisa profit dengan filter tambahan yang cuma perlu
menaikkan winrate sedikit). Di M1, entry acak **9,1 poin di bawah**
breakeven-nya — gate manapun harus menutup jarak sebesar itu, jauh lebih
berat daripada menutup 0,7 poin di M5.

Ini yang membuat M1 secara struktural jauh lebih sulit, terlepas dari
seberapa bagus sinyalnya: **spread yang sama memakan porsi risiko dua
kali lebih besar setiap trade**, dan gate momentum/tren/fib yang sudah
diuji tidak cukup kuat menutup jarak itu.

---

## 5. Kesimpulan

| Pertanyaan | Jawaban |
|---|---|
| M1 dari nol (bukan salinan M5) sudah dicoba? | Ya, gate baru + SL/TP adaptif ATR aktual |
| Hasilnya? | Rugi di 13/13 kombinasi, satu mendekati nol di holdout tapi WR terlalu rendah |
| Kenapa, tepatnya? | Bukan harga M1 lebih acak — tapi spread memakan 2x porsi risiko dibanding M5 |
| Bisakah membaik dengan gate lebih ketat? | Mungkin, tapi harus menutup jarak breakeven 9,1pp — jauh lebih berat dari 0,7pp di M5 yang sudah butuh 100+ percobaan |

**Rekomendasi: tidak dilanjutkan sebagai jalur trading M1 mandiri.**
Bukan karena "sudah dicoba dan menyerah", tapi karena sekarang ada angka
konkret yang menunjukkan berapa besar keunggulan yang dibutuhkan (>9pp di
atas acak) sebelum M1 bisa layak — jauh di luar jangkauan gate momentum
sederhana, dan kemungkinan di luar jangkauan filter tambahan apa pun
tanpa mengubah struktur biaya (spread) itu sendiri.

### Yang tetap berharga dari riset ini

1. **Data M1 lengkap dengan konteks HTF sudah tersimpan**
   (`data/processed/XAUUSDm_M1_features.parquet`) — siap dipakai kalau
   nanti ada ide baru yang genuinely berbeda (bukan varian gate serupa).
2. **Angka breakeven M1 (37,7%) tercatat presisi** — patokan yang jelas
   untuk menilai ide M1 apa pun di masa depan tanpa perlu mengukur ulang
   dari nol.
3. Konfirmasi bahwa M1 **tetap** cocok untuk perannya yang sudah ada:
   resolusi presisi eksekusi (urutan SL/TP dalam satu bar M5), bukan
   basis sinyal independen.

---

## 6. Cara Mengulang

```bash
python -c "from src.features.pipeline import build_dataset, save_processed; \
save_processed(build_dataset(base_tf='M1'), 'XAUUSDm', 'M1')"
```

Skrip eksperimen (`riset_m1.py`) ada di scratchpad sesi ini, tidak
disalin ke `scripts/` karena hasilnya negatif dan tidak menghasilkan
kandidat yang layak dipakai ulang — konsisten dengan pola proyek ini:
hasil negatif dicatat sebagai dokumen, bukan sebagai skrip permanen,
kecuali skrip itu sendiri berguna untuk verifikasi ulang metodologi
(seperti `scripts/ml_uji_ulang.py`).
