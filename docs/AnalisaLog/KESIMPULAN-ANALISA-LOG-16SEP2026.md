# Kesimpulan Analisa Log Trading Bot XAUUSD (15 - 16 September 2026)

**Dokumen**: Evaluasi Kinerja & Root Cause Analysis  
**Tanggal Update**: 16 September 2026 (Pukul 13:50 WIB)  
**Folder**: `docs/AnalisaLog/`  
**Varian Bot**: `pyramid5` | **Setup**: `momentum_fib`  
**Sumber Data**: `logs/trades.csv`, `logs/trades__pc3.csv`, `logs/snapshot.json`

---

## 1. Executive Summary & Status Akun

| Metrik | Pagi (10:56 WIB) | Terkini (13:50 WIB) | Dampak / Status |
|---|---|---|---|
| **Modal Awal** | Rp 5.396.751 | Rp 5.396.751 | Akun Demo Exness |
| **Equity Terkini** | Rp 4.709.063 | **Rp 4.234.604** | Tergerus Rp 1.162.147 (-21.53%) |
| **Balance** | Rp 4.685.305 | **Rp 4.016.351** | Realized Loss membesar |
| **Current Drawdown** | -12.74% | **-21.53%** | ⚠️ Zona bahaya |
| **Consecutive Losses** | 6x beruntun | **14x beruntun** | Rekor kerugian berturut-turut |
| **Day PnL** | -Rp 303.016 | **-Rp 971.971** | Rugi harian mendekati Rp 1 Juta |
| **Open Positions** | 3x BUY (0.01 lot) | 3x BUY (0.01 lot) | Floating profit ~Rp +218.000 |

### Inti Permasalahan Kritis:
1. **Posisi SELL Hancur di Tengah Uptrend Makro (15–16 Sep)**:  
   Pasar emas (XAUUSD) sedang rally kencang di timeframe besar (D1/H4). Namun bot berkali-kali membuka posisi SELL di lembah koreksi intraday (4262–4283), berujung **9x SL berturut-turut** (total rugi SELL **-Rp 695.558**).
2. **Posisi BUY Kena Sapu Bersih Akibat Pyramiding Tanpa Jeda Jarak (16 Sep)**:  
   Meskipun tren makro naik, bot mengalami **14x SL beruntun** dari pagi hingga siang. Antara jam 11:00–11:30, bot membuka 7 posisi BUY berdekatan di harga 4325–4327. Saat harga emas koreksi wajar 6 poin ke 4321, seluruh 7 posisi tersebut disapu SL serentak dalam 5 menit.

---

## 2. Rekapitulasi Data Transaksi Nyata

### A. Rekap Posisi SELL (15 & 16 September) — 100% Loss
Bot mengeksekusi SELL di area bawah karena indikator mendeteksi "momentum turun minor", padahal itu hanyalah pullback di tren naik besar:

| Waktu Entry | Posisi | Entry Price | Exit Price | Net IDR | Durasi | Keterangan |
|---|---|---|---|---|---|---|
| 15-Sep 15:43 | SELL 0.01 | 4268.73 | 4275.46 | **-Rp 119.440** | 85 min | SL kena rally |
| 15-Sep 15:45 | SELL 0.01 | 4267.64 | 4272.19 | **-Rp 80.650** | 58 min | SL kena rally |
| 15-Sep 15:50 | SELL 0.01 | 4266.70 | 4270.93 | **-Rp 75.149** | 51 min | SL kena rally |
| 15-Sep 15:55 | SELL 0.01 | 4267.33 | 4271.70 | **-Rp 77.453** | 47 min | SL kena rally |
| 15-Sep 16:00 | SELL 0.01 | 4262.59 | 4267.07 | **-Rp 79.401** | 5 min | SL kena rally |
| 15-Sep 16:10 | SELL 0.01 | 4265.71 | 4270.19 | **-Rp 79.580** | 31 min | SL kena rally |
| 16-Sep 07:45 | SELL 0.01 | 4283.59 | 4287.03 | **-Rp 61.021** | 29 min | SL kena rally |
| 16-Sep 07:55 | SELL 0.01 | 4278.27 | 4281.64 | **-Rp 59.399** | 5 min | SL kena rally |
| 16-Sep 08:00 | SELL 0.01 | 4277.26 | 4280.86 | **-Rp 63.465** | 0.1 min | SL kena spike |
| **Total Rugi SELL** | | | | **-Rp 695.558** | | **9x SL berturut-turut** |

---

### B. Rekap Posisi BUY (16 September) — Late Entry & Pyramid Flushing
Tren makro BUY, tapi eksekusi M5 bermasalah di pemilihan timing entry & manajemen penumpukan posisi:

| Waktu Entry | Posisi | Entry Price | Exit Price | Net IDR | Status | Catatan Analisis |
|---|---|---|---|---|---|---|
| 16-Sep 10:05 | BUY 0.01 | 4328.09 | 4340.58 | **+Rp 220.495** | **TP** ✅ | Awal momentum berhasil |
| 16-Sep 10:10 | BUY 0.01 | 4328.85 | 4339.63 | **+Rp 190.406** | **TP** ✅ | Follow through sukses |
| 16-Sep 10:15 | BUY 0.01 | 4337.62 | 4332.48 | **-Rp 91.344** | **SL** ❌ | Beli di puncak lokal |
| 16-Sep 10:20 | BUY 0.01 | 4336.43 | 4331.27 | **-Rp 91.344** | **SL** ❌ | Beli di pucuk lokal |
| 16-Sep 10:25 | BUY 0.01 | 4337.45 | 4332.00 | **-Rp 96.665** | **SL** ❌ | Beli di pucuk lokal |
| 16-Sep 10:30 | BUY 0.01 | 4331.82 | 4327.46 | **-Rp 77.530** | **SL** ❌ | Koreksi gelombang 1 |
| 16-Sep 10:35 | BUY 0.01 | 4330.00 | 4325.11 | **-Rp 86.929** | **SL** ❌ | Koreksi gelombang 1 |
| 16-Sep 10:40 | BUY 0.01 | 4328.01 | 4323.16 | **-Rp 86.219** | **SL** ❌ | Koreksi gelombang 1 |
| 16-Sep 10:45 | BUY 0.01 | 4327.28 | 4322.59 | **-Rp 83.033** | **SL** ❌ | Disapu di 4322 (11:45) |
| 16-Sep 10:55 | BUY 0.01 | 4326.80 | 4322.38 | **-Rp 78.242** | **SL** ❌ | Disapu di 4322 (11:45) |
| 16-Sep 11:00 | BUY 0.01 | 4327.53 | 4322.48 | **-Rp 89.775** | **SL** ❌ | Disapu di 4322 (11:45) |
| 16-Sep 11:05 | BUY 0.01 | 4327.89 | 4323.10 | **-Rp 85.176** | **SL** ❌ | Disapu di 4323 (11:43) |
| 16-Sep 11:10 | BUY 0.01 | 4326.46 | 4321.69 | **-Rp 84.650** | **SL** ❌ | Disapu di 4321 (11:48) |
| 16-Sep 11:15 | BUY 0.01 | 4327.31 | 4322.22 | **-Rp 90.319** | **SL** ❌ | Disapu di 4322 (11:47) |
| 16-Sep 11:25 | BUY 0.01 | 4326.89 | 4322.22 | **-Rp 82.689** | **SL** ❌ | Disapu di 4322 (11:47) |
| 16-Sep 11:30 | BUY 0.01 | 4325.62 | 4321.38 | **-Rp 75.067** | **SL** ❌ | Disapu di 4321 (11:48) |
| **Total Sesi BUY** | | | | **-Rp 878.002** | | **2 TP (+410K) vs 14 SL (-1.28jt)** |

---

### C. Posisi Masih Aktif Saat Ini (Floating Profit ~Rp +218.000)
- Ticket `4717628586`: BUY 0.01 @ **4323.58** (SL: 4319.22, TP: 4336.23) ➔ Floating `+Rp 73.987`
- Ticket `4717730007`: BUY 0.01 @ **4324.12** (SL: 4319.34, TP: 4336.35) ➔ Floating `+Rp 64.452`
- Ticket `4717810192`: BUY 0.01 @ **4323.26** (SL: 4318.83, TP: 4334.33) ➔ Floating `+Rp 79.814`

---

## 3. Root Cause Analysis (Bedah Kode & Algoritma)

### 🔴 Kenapa SELL Selalu Rugi?
1. **Bias Trend HTF Tidak Memperhitungkan D1/H4**  
   - Di [`src/features/pipeline.py` baris 85-98](file:///c:/Users/HAN/Dev/APPAI/PROJECT/AI/AI-TRADE/src/features/pipeline.py#L85-L98), `trend_htf` ditentukan dari H1. Timeframe D1 sama sekali tidak dimasukkan ke dalam pipeline.
   - Koreksi wajar 1–2 jam di H1 langsung didiagnosa sebagai `downtrend`, memicu bot mengambil posisi SELL di tengah mega-uptrend D1.
2. **Fibonacci Hanya Mengukur 8 Jam Terakhir (100 Bar M5)**  
   - Di [`src/features/indicators.py` baris 160-162](file:///c:/Users/HAN/Dev/APPAI/PROJECT/AI/AI-TRADE/src/features/indicators.py#L160-L162), lookback Fib hanya 100 bar M5 (~8 jam).
   - Kondisi `fib_position < 0.25` diartikan sebagai level murah untuk SELL, padahal dalam struktur D1/H4 itu adalah **Demand Zone / Support Kuat**.
3. **Logika SELL Sudah Terbukti Gagal di Backtest**  
   - Riset [`src/strategy/setups.py` baris 223-231](file:///c:/Users/HAN/Dev/APPAI/PROJECT/AI/AI-TRADE/src/strategy/setups.py#L223-L231) mencatat varian sell menghasilkan expected return negatif di holdout (`-0.5333`).

---

### 🔴 Kenapa BUY Mengalami 14x Stop Loss Beruntun?
1. **Late Entry / Beli di Pucuk Tanpa Filter Overextension**  
   - Setelah harga terbang 57 poin dari 4280 ke 4337, bot tetap memaksakan BUY di puncak 4336–4337 karena momentum M5 masih hijau.
2. **Kelemahan Fatal Pyramiding (Penumpukan Posisi Tanpa Spacing)**  
   - Bot membuka posisi baru setiap bar M5 memberikan sinyal, tanpa mengecek apakah posisi sebelumnya berada di harga yang sama.
   - Posisi BUY dibuka berturut-turut di 4325, 4326, 4327. Saat harga koreksi tipis 6 poin ke 4321, seluruh posisi tersapu serentak.
3. **SL Terlalu Ketat terhadap Volatilitas Emas (~4.5 Poin / 45 Pip)**  
   - SL dihitung dari ATR lokal M5. Fluktuasi normal emas dengan mudah menyentuh SL sebelum harga berbalik naik sesuai tren utama.

---

## 4. Rekomendasi Solusi & Rencana Aksi

| No | Langkah Solusi | Tingkat Kesulitan | Status | Efek / Manfaat |
|:---:|---|:---:|:---:|---|
| **1** | **Matikan `allow_sell: false` di `settings.yaml`** | 1 Baris Config | ⚡ Segera | Menghentikan loss SELL konyol beruntun. |
| **2** | **Aktifkan `confluence_filter: true`** | 1 Baris Config | ⚡ Segera | Filter statistik teruji (t-stat 3.14, 5/5 fold) untuk menyaring fake signal M5. |
| **3** | **Beri Jarak Minimal Antar Entry Pyramiding** | Ringan (~15 baris) | 🛠️ Kode | Melarang penumpukan entry jika harga belum bergerak minimal 1x ATR dari posisi sebelumnya. |
| **4** | **Filter Overextension Entry BUY** | Sedang (~20 baris) | 🛠️ Kode | Melarang BUY jika harga sudah naik >2x ATR dari swing low terdekat. |
| **5** | **Integrasikan Tren D1/H4 ke Pipeline** | Sedang (~35 baris) | 🛠️ Kode | Mencegah bot salah mendeteksi arah tren makro pasar. |

---

## 5. Kesimpulan & Keputusan Operasional

> **Keputusan Terbaik Saat Ini**: **STOP BOT SEMENTARA & TERAPKAN PERBAIKAN.**
> Jangan biarkan bot berjalan dengan konfigurasi saat ini karena resiko drawdown membengkak sangat tinggi akibat spamming pyramiding di M5 dan ketiadaan filter konfluensi.
