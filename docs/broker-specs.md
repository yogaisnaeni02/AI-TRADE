# Spesifikasi Broker — Hasil Verifikasi Tahap 0

**Tanggal probe:** 9 September 2026
**Broker:** Exness
**Server:** Exness-MT5Trial17
**Akun:** 463942909 (DEMO)
**Balance:** Rp 800.000 (IDR)
**Leverage:** 1:2000

---

## 1. Simbol yang Dipakai

**`XAUUSDm`** — bukan `XAUUSD`. Akhiran `m` adalah konvensi Exness.

Simbol lain yang muncul saat probe dan **tidak boleh** dipakai:

| Simbol | Kenapa tidak dipakai |
|---|---|
| `BTCXAUm` | Bitcoin/Gold — instrumen berbeda total |
| `XAUEURm`, `XAUGBPm`, `XAUAUDm` | Gold vs mata uang lain, bukan USD |
| `XAUUSD247m` | Varian 24/7, spread & likuiditas berbeda |

> **Catatan:** probe versi pertama keliru memilih `BTCXAUm` karena urutan
> alfabet. Sudah diperbaiki di `scripts/phase0_probe.py`. Setiap kode yang
> menyebut simbol harus memakai `XAUUSDm` secara eksplisit.

---

## 2. Spesifikasi Kontrak

| Field | Nilai | Catatan |
|---|---|---|
| `digits` | 3 | Harga 4 desimal-ish: 4407.687 |
| `point` | 0.001 | **Bukan 0.01** — skala 10x lebih halus |
| `contract_size` | 100.0 | 100 oz per lot |
| `tick_value` | 1747.96 IDR | Per tick, akun IDR |
| `tick_size` | 0.001 | |
| `volume_min` | 0.01 | |
| `volume_step` | 0.01 | |
| `volume_max` | 200.0 | |
| `stops_level` | 0 | Tidak ada jarak SL/TP minimum |
| `filling_mode` | 3 | IOC + FOK didukung |
| `trade_exemode` | 2 | Market execution |
| `swap_long` | −526.4 | **Mahal** — hindari posisi menginap |
| `swap_short` | 0.0 | Gratis |

**Nilai per point per lot: 1.748,36 IDR**

---

## 3. KRITIS: Konvensi "Point" vs "Pip"

Ini sumber kebingungan yang harus dikunci sekarang agar tidak salah hitung
di seluruh sistem.

Broker ini memakai `point = 0.001`, sedangkan konvensi umum gold adalah
1 pip = 0.01. **Artinya 1 pip = 10 points di broker ini.**

| Ukuran | Dalam point (broker) | Dalam pip gold | Dalam USD |
|---|---|---|---|
| 1 point | 1 | 0,1 | $0,001 |
| 1 pip | 10 | 1 | $0,01 |
| Spread saat probe | 260 | **26** | $0,26 |
| SL 200 points | 200 | 20 | $0,20 |

**Aturan untuk seluruh kode:** simpan semua jarak dalam **point broker**
(satuan asli MT5), dan konversi ke pip hanya saat menampilkan ke manusia.
Mencampur dua satuan ini menghasilkan kesalahan 10x lipat.

---

## 4. Spread

**Median: 260 points = 26 pip = $0,26**

Hasil per sesi (5 hari, jam server):

| Sesi | Median | p90 | Max |
|---|---|---|---|
| Asia | 260 | 260 | 480 |
| London open | 260 | 260 | 260 |
| London–NY | 260 | 260 | 260 |
| NY sore | 260 | 260 | 340 |
| Rollover | 260 | 260 | 260 |

**Temuan penting:** spread nyaris **tetap di 260** sepanjang sesi. Ini
karakteristik akun Standard Exness — spread fixed markup, bukan floating
mengikuti likuiditas interbank.

**Implikasi untuk strategi:**
- Rencana awal "trading hanya di sesi spread terendah" **tidak berlaku** di
  akun ini — tidak ada sesi yang spread-nya lebih murah
- Pemilihan sesi tetap penting, tapi alasannya bergeser: bukan demi spread
  murah, melainkan demi **volatilitas dan kualitas pergerakan**
- Optimasi Tahap 4A (filter spread per jam) perlu disesuaikan; potensi
  perbaikannya lebih kecil dari estimasi awal

**Konsekuensi biaya:**

| Item | Nilai |
|---|---|
| Spread per trade | 26 pip = $0,26 |
| TP minimum layak (8x spread) | 2.080 points = 208 pip = $2,08 |
| Biaya spread dalam Rupiah (lot 0,07) | ~Rp 32.000 per trade |

> Angka terakhir perlu diperhatikan: dengan risiko per trade Rp 24.500,
> biaya spread (Rp 32.000) **lebih besar dari risiko yang direncanakan**.
> Ini bukan kesalahan hitung — ini menunjukkan SL 200 points terlalu sempit
> untuk broker ini. Lihat Bagian 6.

---

## 5. Position Sizing — Hasil Verifikasi

```
Equity            : Rp 800.000
Risiko target     : 3%
Asumsi SL         : 200 points (20 pip)
Nilai/point/lot   : 1.748,36 IDR

Lot ideal         : 0,06864
Lot minimum       : 0,01
Lot dipakai       : 0,07
Risiko sebenarnya : Rp 24.477 = 3,06% dari equity   [OK]

Margin untuk 0,07 lot : Rp 270.765 (33,8% equity)
```

**Status: `[OK]` — akun ini LAYAK untuk sistem.**

Ini temuan yang mengubah kesimpulan sebelumnya. Meski bertipe **Standard**
(bukan Cent), denominasi **IDR** membuat granularitas sizing menjadi halus:
lot 0,01 hanya bernilai Rp 17.484 per 10 pip, sehingga risiko 3% bisa
dicapai dengan presisi tinggi.

**Akun cent tidak diperlukan.** Kekhawatiran di dokumen 01 Bagian 1.1
(risiko terpaksa 41% per trade) tidak berlaku untuk akun IDR ini.

---

## 6. Konsekuensi: SL Harus Lebih Lebar

Spread 26 pip mengubah perhitungan RR secara signifikan.

| SL | Spread sebagai % SL | Layak? |
|---|---|---|
| 20 pip (200 pts) | **130%** | Tidak — biaya melebihi risiko |
| 50 pip (500 pts) | 52% | Tidak |
| 100 pip (1.000 pts) | 26% | Marginal |
| 200 pip (2.000 pts) | 13% | Ya |
| 300 pip (3.000 pts) | **8,7%** | Ya — target sistem |

**Revisi parameter untuk broker ini:**

```yaml
sl_minimum: 1500      # points = 150 pip
sl_typical: 2000-3000 # points = 200-300 pip
tp_minimum: 3000      # points = 300 pip (RR 1:2 dari SL 150 pip)
```

Dengan SL 2.000 points (200 pip), sizing menjadi:
```
Lot = (800.000 x 0,03) / (2.000 x 1.748,36) = 0,00686 -> dibulatkan 0,01
Risiko aktual = 0,01 x 2.000 x 1.748,36 = Rp 34.967 = 4,4% equity
```

Sedikit di atas target 3%, karena lot minimum 0,01 mulai membatasi. Ini
dapat diterima, tetapi berarti **presisi sizing menurun saat SL diperlebar**.

**Trade-off yang harus diputuskan di Tahap 2–4:**
- SL sempit (20–50 pip): sizing presisi, tapi spread memakan terlalu besar
- SL lebar (200–300 pip): spread proporsional wajar, tapi sizing terpaksa
  4–5% per trade

Keputusan final menunggu data expectancy dari backtest.

---

## 7. Kedalaman Riwayat

| TF | Bar tersedia | Rentang | Status |
|---|---|---|---|
| M1 | ~50.000 | 21 Jul 2026 – 9 Sep 2026 (~7 minggu) | **KURANG** |
| M5 | ~50.000 | 24 Des 2025 – 9 Sep 2026 (~8,5 bulan) | Cukup untuk awal |
| M15 | ~50.000 | 29 Jul 2024 – 9 Sep 2026 (~2 tahun) | Cukup |
| H1 | 31.000 | 14 Jun 2021 – 9 Sep 2026 (5 tahun) | Cukup |
| H4 | 15.000 | 11 Apr 2017 – 9 Sep 2026 (9 tahun) | Cukup |

**Batas teknis:** `copy_rates_from_pos` gagal di atas ~50.000 bar sekali
minta (`Invalid params`). `copy_rates_range` juga gagal untuk rentang
panjang. **Solusi: download bertahap per blok** — diimplementasikan di
Tahap 1.

**Masalah M1:** hanya 7 minggu. Terlalu sedikit untuk training ML.

Opsi:
1. **Scroll manual di MT5** — buka chart M1 XAUUSDm, tekan Home berulang
   agar terminal mengunduh riwayat lebih dalam, lalu ulangi probe
2. **Pakai M5 sebagai timeframe utama** — 8,5 bulan sudah memadai untuk
   memulai; M1 hanya untuk timing entry (sesuai rencana awal)
3. **Sumber eksternal** (Dukascopy) bila M1 dalam benar-benar dibutuhkan

**Rekomendasi: opsi 2 + coba opsi 1.** Rencana awal memang menempatkan M5
sebagai timeframe eksekusi, jadi keterbatasan M1 tidak memblokir.

---

## 8. Waktu Server

```
Waktu server : 2026-09-09 14:29:33
Waktu lokal  : 2026-09-09 14:29:33 (WIB)
Selisih      : 0,0 jam
```

**Server berjalan di waktu yang sama dengan WIB (UTC+7).**

Ini memudahkan: jam sesi di dokumen master plan (yang ditulis dalam WIB)
bisa dipakai langsung. Tetap disarankan menormalisasi ke UTC di dalam kode
agar tidak rapuh terhadap perubahan DST broker.

---

## 9. Status Tahap 0

- [x] **Algo trading aktif** — diverifikasi 9 Sep 2026:
      `trade_allowed=True`, `trade_expert=True`
- [x] **Tipe akun diputuskan: Standard** — klien memilih tetap memakai
      akun ini. Alternatif Raw Spread/Zero (spread ~10–15 pip efektif)
      ditawarkan dan tidak diambil. Konsekuensinya diterima: biaya per
      trade 26 pip, sehingga SL/TP harus lebar (lihat Bagian 6).
- [x] Simbol dikunci: `XAUUSDm`
- [x] Sizing terverifikasi: 3,06% pada SL 200 points
- [ ] Perdalam riwayat M1 dengan scroll manual di chart (opsional,
      tidak memblokir — M5 dipakai sebagai timeframe utama)
- [ ] Kumpulkan sampel spread beberapa hari untuk konfirmasi pola fixed
      (dikerjakan di Tahap 1)

**Server ini hanya menyediakan `XAUUSDm` dan `XAUUSD247m`, keduanya
spread 26 pip.** Tidak ada varian simbol yang lebih murah di akun Standard.

### Konsekuensi yang harus dipegang seluruh sistem

Spread 26 pip adalah **biaya tetap per trade** yang tidak bisa dikurangi
dengan memilih jam atau simbol. Satu-satunya cara menekan porsinya adalah
memperbesar jarak SL/TP. Karena itu:

- SL minimum 150 pip (1.500 points) — bukan 20 pip seperti rencana awal
- TP minimum 300 pip (3.000 points)
- Frekuensi trade akan **lebih rendah** dari perkiraan awal: target
  1–3 trade/hari, bukan 5–15
- Setup scalping cepat tidak layak di broker ini — sudah dibuktikan
  secara aritmetika di Bagian 6

**TAHAP 0 SELESAI — lanjut ke Tahap 1 (Data).**

---

## 10. Ringkasan Keputusan

| Aspek | Temuan | Keputusan |
|---|---|---|
| Simbol | `XAUUSDm` | Kunci di config, jangan hardcode `XAUUSD` |
| Tipe akun | Standard IDR | **Layak** — cent tidak diperlukan |
| Sizing | 3,06% tercapai | Sesuai target |
| Spread | 26 pip, fixed | **Lebih tinggi dari asumsi awal (15–25 pip)** |
| SL | Harus 150–300 pip | Revisi dari rencana 20 pip |
| Filter sesi | Spread rata | Alasan bergeser ke volatilitas |
| Data M1 | 7 minggu | Pakai M5 sebagai TF utama |
| Data M5 | 8,5 bulan | Memadai untuk memulai |
| Swap long | −526,4 | Tutup posisi sebelum rollover |
| Point | 0,001 | 1 pip = 10 points — kunci konvensi ini |

---

## 11. Hasil Tahap 1 — Data (9 Sep 2026)

### Data berhasil diunduh (download bertahap menembus batas 50k bar)

| TF | Bar | Rentang | Hari |
|---|---|---|---|
| M1 | 100.000 | 28 Mei 2026 – 9 Sep 2026 | 103 |
| M5 | 100.000 | 10 Apr 2025 – 9 Sep 2026 | **516** |
| M15 | 100.000 | 15 Jun 2022 – 9 Sep 2026 | 1.546 |
| H1 | 57.154 | 13 Jan 2014 – 9 Sep 2026 | 4.621 |
| H4 | 16.162 | 13 Jan 2014 – 8 Sep 2026 | 4.621 |

Jauh lebih baik dari perkiraan probe awal (M5: 8,5 bulan -> 17 bulan).
**M5 516 hari memadai untuk training ML.**

### Validasi kualitas

Temuan yang awalnya ditandai bermasalah, setelah diperiksa ternyata normal:

| Temuan | Kesimpulan |
|---|---|
| "7.738 bar akhir pekan" (M5) | Semua hari **Minggu 15:00–22:00 UTC** = pembukaan sesi Asia Senin waktu lokal. Normal. Nol bar Sabtu. |
| "14 spike harga" (M5) | Reaksi berita asli (NFP, FOMC). Harga bergerak **dan bertahan** — bukan error feed. Bar paling berharga untuk sistem. |
| "Kelengkapan 72%" (H1) | Kesalahan rumus validator (memakai rasio 5/7 hari, seharusnya 120/168 jam). |
| 161 bar Sabtu (H1/H4) | Jam 17:00 UTC, tahun 2014–2017. Sisa konvensi lama broker. Tidak relevan — kita pakai M1/M5. |

**Kelengkapan aktual M1/M5/M15: ~94%** — sisanya libur bank dan jeda
likuiditas, wajar untuk data broker ritel.

### Verifikasi resampling M1 -> M5

Diuji apakah M5 broker konsisten dengan agregasi M1:

```
Bar beririsan   : 20.034
Cocok (tol 0,05): 20.033  = 99,995%
Selisih rata2   : 0,0000 USD
Selisih maks    : 2,4080 USD (1 bar, kemungkinan bar berita)
```

**Kesimpulan: data broker konsisten.** M1 dapat dipakai untuk menentukan
urutan sentuhan SL/TP di dalam bar M5.

### Keputusan: peran M1 dan M5

Riwayat M1 (103 hari) jauh lebih pendek dari M5 (516 hari), sehingga
resampling tidak dipakai menggantikan data M5 broker.

| Data | Peran |
|---|---|
| **M5 broker** (516 hari) | Training model & backtest utama — sampel besar |
| **M1** (103 hari) | Resolusi SL/TP intrabar & timing entry |
| **M5 dari M1** | Kalibrasi: mengukur bias asumsi pesimis |

**Cara kerja kalibrasi:** backtest utama memakai asumsi pesimis (SL kena
duluan saat ambigu). Di 103 hari yang punya M1, urutan sebenarnya dapat
diperiksa. Selisih keduanya = besar bias asumsi tersebut. Jika kecil,
asumsi pesimis aman diterapkan ke seluruh 516 hari.

Tanpa M1, bias ini tidak akan pernah terukur — hanya bisa diasumsikan.

**TAHAP 1 SELESAI — lanjut Tahap 2 (Rule Engine).**
