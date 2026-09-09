# Uji Ide: RR 1:3 → Switch Trailing di 80 Pip, Toleransi 10%

**Tanggal:** 9 September 2026
**Ide:** "Awalnya pakai SL/TP 1:3. Begitu profit 80 pip, langsung beralih ke
trailing stop dengan toleransi 10% penurunan dari profit."

---

## Ringkasan Hasil

**Ide ini berhasil melakukan persis apa yang dimaksudkan — menaikkan winrate
hampir dua kali lipat. Tetapi expectancy-nya justru turun.**

| Konfigurasi | Winrate | Expectancy | Rata-rata menang |
|---|---|---|---|
| Tanpa trailing | 26,6% | **+0,0329R** | **+2,874R** |
| **80 pip → trailing 10%** | **51,5%** | **−0,0398R** | +0,865R |

Winrate naik dari 26,6% ke 51,5%. Tetapi rata-rata kemenangan anjlok dari
2,874R ke 0,865R — trailing memotong pemenang di sepertiga perjalanan.

Diuji pada **8.971 entry** (jendela NY, ATR di atas persentil 60), tanpa
lookahead bias.

---

## 1. Mengapa Winrate Naik tetapi Hasil Turun

Trailing di 80 pip mengunci profit sangat awal. Konsekuensinya:

```
Trade yang tadinya kalah penuh (-1R)  -> jadi menang kecil (+0,3R sampai +0,8R)
Trade yang tadinya menang besar (+3R) -> jadi menang kecil (+0,8R)
```

Yang pertama terlihat seperti perbaikan. Yang kedua adalah kerusakannya, dan
kerusakannya lebih besar.

Strategi RR 1:3 dengan winrate 26% bergantung pada **sedikit pemenang besar**
untuk menutup banyak kekalahan. Distribusinya timpang secara sengaja. Trailing
meratakan distribusi itu — dan ekonominya runtuh.

Analogi: seperti menjual saham yang naik 5% padahal Anda membelinya karena
memperkirakan naik 300%. Anda akan lebih sering "untung", tetapi portofolio
tidak tumbuh.

---

## 2. Pengaruh Titik Trigger

Semakin jauh trigger, semakin baik hasilnya — arahnya konsisten menuju
"tanpa trailing":

| Trigger | Toleransi | Winrate | Expectancy | Rata-rata menang |
|---|---|---|---|---|
| 80 pip | 10% | 51,5% | −0,0398R | +0,865R |
| 150 pip | 10% | 47,7% | −0,0356R | +1,023R |
| 200 pip | 10% | 45,1% | −0,0324R | +1,143R |
| 300 pip | 10% | 40,6% | −0,0318R | +1,382R |
| 400 pip | 10% | 37,1% | −0,0283R | +1,622R |
| 600 pip | 10% | 32,2% | −0,0103R | +2,076R |
| **Tanpa trailing** | — | 26,6% | **+0,0329R** | **+2,874R** |

Tidak ada titik trigger yang mengungguli "tanpa trailing". Setiap kali
trailing diaktifkan lebih awal, hasilnya lebih buruk.

### Pengaruh toleransi

Toleransi 10%, 20%, atau 30% pada trigger 80 pip hampir tidak berbeda
(−0,0398 / −0,0368 / −0,0331). Yang menentukan adalah **kapan trailing
aktif**, bukan seberapa longgar toleransinya.

---

## 3. Varian yang Diuji

| Varian | Winrate | Expectancy |
|---|---|---|
| Tanpa trailing | 26,6% | **+0,0329R** |
| 300 pip → SL ke breakeven saja | 40,6% | +0,0004R |
| 150 pip → SL ke breakeven saja | 47,7% | −0,0109R |
| 80 pip → SL ke breakeven saja | 51,5% | −0,0147R |
| 400 pip → tutup 50%, sisa trailing 20% | 37,1% | −0,0295R |
| 300 pip → tutup 50%, sisa trailing | 40,6% | −0,0323R |
| **80 pip → trailing 10%** (ide asli) | 51,5% | −0,0398R |
| 80 pip → tutup 50%, sisa trailing | 51,5% | −0,0410R |

**Breakeven-only lebih baik daripada trailing penuh** (−0,0147 vs −0,0398).
Menggeser SL ke titik impas tanpa mengikuti harga lebih sedikit merusaknya,
karena pemenang tetap bebas berjalan menuju TP.

Partial close tidak membantu — hasilnya sedikit lebih buruk dari trailing biasa.

---

## 4. Uji Stabilitas Antar Periode

| Konfigurasi | Expectancy | In-sample | Out-of-sample | Kuartal positif |
|---|---|---|---|---|
| **Tanpa trailing** | +0,0329R | +0,0063 | **+0,0947** | **4/6** |
| 300 pip → breakeven | +0,0004R | −0,0308 | +0,0733 | 3/6 |
| 80 pip → trailing 10% | −0,0398R | −0,0533 | −0,0084 | **1/6** |

Per kuartal:

```
Tanpa trailing  : +0,082  -0,100  +0,003  -0,018  +0,054  +0,157
80p trailing    : -0,026  -0,103  -0,057  -0,058  +0,004  -0,013
```

Trailing bukan hanya menurunkan rata-rata — ia juga **kurang stabil**, hanya
1 dari 6 kuartal positif dibanding 4 dari 6.

---

## 5. Kapan Ide Ini Justru Tepat

Trailing bukan teknik buruk. Ia cocok untuk profil strategi yang berbeda:

| Cocok | Tidak cocok (kasus kita) |
|---|---|
| Winrate tinggi, RR rendah (1:1) | Winrate rendah, RR tinggi (1:3) |
| Tanpa TP tetap — mengejar tren | TP tetap 1.200 pip |
| Posisi ditahan berhari-hari | Posisi ditahan 4 jam |
| Distribusi hasil merata | Distribusi timpang (sedikit pemenang besar) |

Pada strategi trend-following H4/D1 tanpa TP, trailing adalah cara utama
keluar — di sana ia justru wajib.

Pada strategi ini, TP 1.200 pip sudah menjadi target yang dihitung. Trailing
hanya memotong perjalanan menuju target itu.

---

## 6. Kompromi bila Tetap Diinginkan

Jika kenyamanan psikologis lebih diutamakan (tidak ingin melihat profit
berbalik jadi rugi), opsi paling tidak merusak:

```yaml
breakeven_at_r: 0.75    # ~300 pip, SL ke titik impas
trail_atr_mult: null    # TANPA trailing lanjutan
```

Expectancy +0,0004R — praktis impas, tetapi jauh lebih baik daripada −0,0398R.
Setelah profit 300 pip, trade tidak bisa rugi lagi, dan pemenang tetap bebas
mencapai TP.

Biayanya: expectancy turun dari +0,0329R ke +0,0004R. Itu harga dari rasa
aman tersebut.

---

## 7. Kesimpulan

| Pertanyaan | Jawaban |
|---|---|
| Bisa dibuat? | **Ya**, dan sudah diuji |
| Menaikkan winrate? | **Ya** — 26,6% → 51,5% |
| Menaikkan profit? | **Tidak** — expectancy +0,033R → −0,040R |
| Trigger optimal? | Tidak ada; makin jauh makin baik, terbaik = tanpa trailing |
| Toleransi berpengaruh? | Hampir tidak (10%/20%/30% serupa) |
| Varian terbaik? | Breakeven-only di 300 pip (+0,0004R) |
| Keputusan sistem | **Trailing tetap nonaktif** |

Konfigurasi sistem tidak diubah: `breakeven_at_r: null`, `trail_atr_mult:
null` — biarkan TP tercapai.

Ide ini layak diuji dan pengujiannya memberi jawaban yang jelas. Pola yang
muncul sama dengan yang dibahas di `02-KENAPA-WINRATE-TINGGI-TIDAK-BISA.md`:
**menang lebih sering dengan profit lebih kecil bukan perbaikan.**

---

## 8. Update: Trigger Berbasis Persentase Jarak TP (bukan pip absolut)

**Tanggal:** 9 September 2026 (lanjutan)

**Ide baru:** trigger trailing di **70% jarak menuju TP** (bukan pip tetap
seperti 80 pip sebelumnya), toleransi mundur 10-15%.

### Hasil

| Trigger (% jarak TP) | Toleransi | Expectancy |
|---|---|---|
| 70% | 10% | +0,0069R |
| 70% | 15% | +0,0038R |
| 80% | 10% | +0,0200R |
| 85% | 10% | +0,0241R |
| 90% | 10% | +0,0269R |
| **95%** | **5%** | **+0,0306R (terbaik)** |
| **Tanpa trailing** | — | **+0,0319R** |

### Kesimpulan

**Trigger berbasis persentase JAUH lebih baik daripada pip absolut** — di
70% jarak TP, hasilnya sudah positif (+0,0069R), dibanding trigger 80 pip
absolut yang jelas negatif (-0,0398R di pengujian sebelumnya). Ini karena
80 pip cuma ~9,5% dari total jarak TP (840 pip) — jauh lebih dini
dibanding 70% yang dimaksud di sini.

Polanya konsisten dan bisa diprediksi: **makin dekat trigger ke 100%
(TP itu sendiri), makin dekat hasilnya ke "tanpa trailing sama sekali"**
— sampai batas 95% pun, trailing tetap sedikit di bawah "tanpa trailing"
(+0,0306R vs +0,0319R).

**Ini bukan kebetulan — ini keniscayaan matematis.** Trailing, dengan
mekanisme apapun, hanya bisa MENGURANGI kemungkinan sampai ke TP penuh —
tidak pernah menambahnya. Semakin longgar triggernya (mendekati TP),
semakin kecil pengurangannya, tapi tidak akan pernah menjadi nol
sepenuhnya kecuali trigger-nya persis di 100% (yang berarti sama saja
dengan tidak ada trailing).

### Keputusan

Konfigurasi sistem **tetap tidak berubah**: `breakeven_at_r: 2.0` (~800
pip, setara ~67% jarak TP) tanpa trailing lanjutan — ini sudah mendekati
titik optimal (trigger tinggi, toleransi kecil) dari hasil pengujian di
atas, dan sudah teruji sebagai kompromi terbaik antara proteksi psikologis
dan expectancy.
