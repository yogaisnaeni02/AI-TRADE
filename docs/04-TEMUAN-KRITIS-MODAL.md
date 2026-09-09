# Temuan Kritis: Modal Rp 800.000 Tidak Cukup untuk XAUUSD

**Tanggal:** 9 September 2026
**Ditemukan di:** Tahap 3 (backtest pertama)
**Status:** BLOCKER — perlu keputusan sebelum melanjutkan

---

## Ringkasan

Backtest pertama mengungkap batasan aritmetika yang tidak bisa diatasi oleh
strategi, model, atau optimasi apa pun:

**Volatilitas XAUUSD saat ini menuntut SL sekitar 636 pip. Pada lot minimum
broker (0,01), SL sebesar itu memberi risiko 13,9% per trade — bukan 3%.**

Ini bukan kegagalan strategi. Ini ketidakcocokan antara ukuran modal dan
instrumen yang dipilih.

---

## Bagaimana Ini Ditemukan

Backtest pertama menghasilkan angka yang jelas salah: hanya 21 trade
tereksekusi dari 882 sinyal, dan rata-rata bar hold = 0. Penelusuran
mengungkap urutan sebab berikut.

### 1. Gejala awal: SL 300 pip memaksa risiko 6,6%

```
SL 3.000 points x lot 0,01 x Rp 1.748,36 = Rp 52.451 = 6,6% dari Rp 800.000
Lot ideal untuk risiko 3% = 0,00458  ->  di bawah lot minimum 0,01
```

Empat loss beruntun langsung menyentuh batas drawdown 25%, sehingga sistem
berhenti. Itu sebabnya hanya 4 trade yang tereksekusi pada percobaan pertama.

### 2. Perbaikan yang tampak masuk akal: perkecil SL ke 150 pip

Pada SL 1.500 points, risiko turun ke 3,3% — target tercapai. Tetapi hasilnya
justru lebih buruk: winrate 23,8%, expectancy −0,300R.

### 3. Akar masalah sebenarnya

```
Range bar M5 (median)  : 3.793 points = 379 pip
ATR M5 (median)        : 4.243 points = 424 pip
SL yang dipakai        : 1.500 points = 150 pip
```

**Satu bar M5 rata-rata bergerak 2,5 kali lebih besar dari SL.**

Trade kena SL bukan karena arahnya salah, melainkan karena SL berada di dalam
rentang gerak normal satu bar. Ini setara memasang stop 3 pip di EURUSD —
kekalahan yang dijamin oleh noise, bukan oleh arah pasar.

---

## Aritmetika yang Mengunci

Dua batasan bergerak berlawanan dan tidak ada nilai yang memuaskan keduanya:

| Jarak SL | Risiko di lot 0,01 | Spread sbg % SL | Bertahan dari noise? |
|---|---|---|---|
| 150 pip | 3,3% | 17,3% | **Tidak** — di bawah range 1 bar |
| 212 pip | 4,6% | 12,3% | Tidak |
| 318 pip | 7,0% | 8,2% | Marginal |
| 424 pip (ATR x1) | 9,3% | 6,1% | Ya |
| **636 pip (ATR x1,5)** | **13,9%** | 4,1% | **Ya** |

Baris terakhir adalah jarak SL yang benar secara teknis. Risikonya 13,9% per
trade — lebih dari 4 kali target agresif kita, dan **7 loss beruntun akan
menghabiskan akun**.

Penyebabnya tunggal: **lot minimum 0,01 tidak bisa dibagi lebih kecil.**
Dengan modal Rp 800.000, satu unit terkecil yang bisa diperdagangkan sudah
mewakili risiko yang terlalu besar.

---

## Kenapa Ini Tidak Terdeteksi di Probe Tahap 0

Probe memakai asumsi SL 200 points (20 pip) dan melaporkan `[OK]` dengan
risiko 3,06%. Asumsi itu keliru: 20 pip sama sekali tidak realistis untuk
XAUUSD — lebih kecil dari spread-nya sendiri (26 pip).

Angka SL yang realistis baru diketahui setelah ATR aktual dihitung dari data
historis di Tahap 1–2. Inilah gunanya gerbang bertahap: kesalahan asumsi
terungkap oleh data, sebelum uang nyata dipertaruhkan.

Script probe sudah diperbarui agar memakai SL berbasis ATR, bukan angka tetap.

---

## Faktor Tambahan: Harga Gold Saat Ini

XAUUSD diperdagangkan di sekitar **$4.400** (September 2026). Volatilitas
absolutnya jauh lebih besar dibanding era $1.800–2.000:

| Periode | Harga | ATR M5 tipikal | SL wajar |
|---|---|---|---|
| 2020 | ~$1.800 | ~$1,50 | ~150 pip |
| 2023 | ~$2.000 | ~$2,00 | ~200 pip |
| **2026** | **~$4.400** | **~$4,20** | **~636 pip** |

Panduan trading yang beredar di internet umumnya ditulis untuk era harga
lama. Angka SL dari sumber tersebut tidak berlaku lagi.

---

## Modal Minimum yang Sebenarnya Dibutuhkan

Dengan SL 636 pip (ATR x 1,5) pada lot minimum 0,01:

| Target risiko/trade | Modal minimum | Karakter |
|---|---|---|
| 1% (standar profesional) | Rp 11.126.000 | Aman |
| 2% (moderat) | Rp 5.563.000 | Wajar |
| **3% (agresif, target kita)** | **Rp 3.709.000** | Batas bawah yang layak |
| 5% (sangat agresif) | Rp 2.225.000 | Risk of ruin tinggi |
| 13,9% (kondisi sekarang) | Rp 800.000 | **Kehancuran matematis** |

**Kesimpulan: proyek ini membutuhkan modal minimum sekitar Rp 3.700.000
untuk XAUUSD.** Di bawah itu, lot minimum memaksa risiko yang tidak bisa
diselamatkan strategi apa pun.

---

## Opsi yang Tersedia

### Opsi 1 — Tambah modal ke Rp 3.700.000+ (paling langsung)

Seluruh sistem yang sudah dibangun langsung berlaku tanpa perubahan.

| Aspek | Nilai |
|---|---|
| Modal | Rp 3.700.000 |
| Risiko/trade | 3% = Rp 111.000 |
| SL | 636 pip pada lot 0,01 |
| Yang perlu diubah | Tidak ada — hanya nilai equity |

### Opsi 2 — Ganti instrumen (modal tetap Rp 800.000)

Instrumen dengan volatilitas absolut lebih kecil memungkinkan sizing presisi
pada modal kecil:

| Instrumen | Nilai/pip di lot 0,01 | SL wajar | Risiko di modal Rp 800rb |
|---|---|---|---|
| **EURUSD** | ~Rp 1.660 | ~15 pip | **~3,1%** |
| **GBPUSD** | ~Rp 1.660 | ~20 pip | ~4,2% |
| XAUUSD | ~Rp 17.484 | 636 pip | 13,9% |

EURUSD cocok secara aritmetika dengan modal ini. Konsekuensinya: seluruh
riset sesi dan setup harus dikalibrasi ulang — perilaku sweep Asia range
pada EURUSD berbeda dari gold. Kode struktur, sesi, backtester, dan risk
manager tetap terpakai; yang berubah adalah parameter dan validasi setup.

### Opsi 3 — Cari broker dengan lot minimum lebih kecil

Sebagian broker menyediakan lot minimum 0,001 (sepersepuluh). Itu menurunkan
risiko dari 13,9% menjadi 1,39% — masalah selesai sepenuhnya.

Yang perlu diverifikasi:
- Apakah tersedia untuk XAUUSD (bukan hanya forex pair)
- Apakah akun demo-nya bisa diuji dulu
- Spread pada tipe akun tersebut

Exness memiliki akun Cent yang berpotensi memenuhi ini. Sebelumnya opsi ini
ditawarkan dan tidak diambil karena akun Standard sudah dinyatakan `[OK]` —
penilaian yang ternyata berdasar asumsi SL yang keliru.

### Opsi 4 — Lanjutkan di demo untuk validasi strategi

Modal Rp 800.000 tidak dipakai untuk trading nyata, melainkan sistem
divalidasi di demo dengan equity simulasi Rp 3.700.000. Setelah strategi
terbukti punya edge, keputusan modal diambil berdasar bukti, bukan harapan.

Ini tidak menghasilkan uang dalam waktu dekat, tetapi juga tidak
menghilangkan modal, dan seluruh pekerjaan tetap bernilai.

---

## Rekomendasi

**Opsi 3 (broker lot 0,001) sebagai pilihan pertama**, karena menyelesaikan
masalah tanpa menambah modal maupun mengganti instrumen. Perlu diverifikasi
ketersediaannya untuk XAUUSD.

**Jika Opsi 3 tidak tersedia: Opsi 4 sekarang, Opsi 1 saat modal siap.**
Sistem tetap dibangun dan divalidasi; keputusan modal menyusul berdasar bukti
performa.

Yang **tidak** saya rekomendasikan: menjalankan XAUUSD dengan modal
Rp 800.000 pada risiko 13,9% per trade. Tujuh kekalahan beruntun — kejadian
yang normal dalam ratusan trade — akan menghabiskan modal sepenuhnya.
Itu bukan risiko yang dikelola, melainkan kepastian yang ditunda.

---

## Yang Tetap Bernilai dari Pekerjaan Ini

Seluruh komponen yang dibangun tetap terpakai apa pun opsi yang dipilih:

| Komponen | Status |
|---|---|
| Gateway MT5 + verifikasi spesifikasi | Selesai, terpakai |
| Downloader bertahap (tembus batas 50k bar) | Selesai, terpakai |
| Validator kualitas data | Selesai, terpakai |
| Resampler M1 + resolusi SL/TP intrabar | Selesai, terpakai |
| Deteksi struktur (swing, BOS, CHoCH) | Selesai, terpakai |
| Klasifikasi sesi + Asia range + sweep | Selesai, terpakai |
| Indikator (ATR, EMA, RSI, ADX, BB) | Selesai, terpakai |
| Rule engine + skoring konfluensi | Selesai, perlu kalibrasi |
| Backtester dengan biaya realistis | Selesai, terpakai |
| Modul metrik | Selesai, terpakai |

Yang berubah hanya **parameter**, bukan arsitektur.

Temuan ini justru bukti sistem gerbang bertahap bekerja: kesalahan asumsi
terungkap di backtest, bukan setelah modal habis di akun nyata.
