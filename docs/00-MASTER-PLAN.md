# XAUUSD Intraday Trading Assistant — Master Plan

**Versi:** 1.0
**Tanggal:** 9 September 2026
**Instrumen:** XAUUSD (Gold vs US Dollar) — eksklusif
**Timeframe:** M1 & M5
**Deployment:** Lokal (Windows 11), terhubung ke MetaTrader 5 desktop
**Status:** Dokumen perencanaan — belum ada kode yang ditulis

---

## 0. Baca Ini Dulu: Koreksi Ekspektasi

Permintaan awal menyebut "winrate 100 persen". Saya perlu menyatakan ini dengan jelas di depan, karena seluruh desain sistem bergantung padanya:

**Winrate 100% tidak ada, tidak pernah ada, dan tidak akan ada.**

Ini bukan soal kurang pintar atau kurang canggih modelnya. Ini konsekuensi struktural dari cara market bekerja:

1. **Spread & slippage** — XAUUSD punya spread 15–35 points. Setiap posisi dibuka dalam keadaan rugi. Trade dengan target kecil bisa kalah hanya karena biaya, tanpa market bergerak melawan sama sekali.
2. **Ketidakpastian ireduksibel** — harga dipengaruhi arus order yang tidak terlihat di chart (institusi, bank sentral, algo HFT). Data OHLCV M1 hanyalah bayangan dari proses itu.
3. **Berita & gap** — rilis NFP, CPI, FOMC menggerakkan gold 300–800 points dalam hitungan detik. Tidak ada model yang bisa memprediksi isi angka yang belum dirilis.
4. **Bukti empiris** — dana kuantitatif terbaik dunia (Renaissance Medallion) beroperasi di winrate sekitar 50,75%. Mereka menang dari volume transaksi besar dengan edge tipis, bukan dari akurasi tinggi.

**Jika ada sistem yang mengklaim winrate 100%, penyebabnya selalu salah satu dari ini** — dan semuanya akan kita hindari secara eksplisit di dokumen ini:

| Klaim | Penyebab Sebenarnya |
|---|---|
| "Backtest saya 100% profit" | Lookahead bias — model melihat data masa depan |
| "Live 3 bulan tanpa loss" | Martingale / grid tanpa stop loss — floating loss disembunyikan, akun meledak di trend kuat |
| "Winrate 95%+" | TP 5 pips, SL 500 pips — menang sering, sekali kalah menghapus 100 kemenangan |
| "EA ini tidak pernah salah" | Curve fitting — dioptimasi ke noise data historis |

### Target yang Realistis dan Profesional

Ini yang akan kita jadikan definisi sukses:

| Metrik | Target Minimum | Target Baik |
|---|---|---|
| Winrate | 45% | 52–58% |
| Risk-Reward rata-rata | 1:1,5 | 1:2 atau lebih |
| Profit Factor | > 1,25 | > 1,5 |
| Max Drawdown | < 15% | < 10% |
| Sharpe Ratio (annualized) | > 1,0 | > 1,5 |
| Expectancy per trade | > 0,1R | > 0,25R |

> **Matematika yang perlu dipahami klien:** Dengan winrate 45% dan RR 1:2, dari 100 trade: 45 menang × 2R = +90R, 55 kalah × 1R = −55R. **Net +35R.** Sistem ini profitabel meskipun *lebih sering kalah daripada menang.* Inilah cara trader profesional sungguhan menghasilkan uang — bukan dari akurasi, tapi dari **asimetri antara ukuran menang dan kalah.**

**Rekomendasi untuk komunikasi ke klien:** Jangan jual "winrate tinggi". Jual **konsistensi, kontrol risiko, dan transparansi**. Sistem yang jujur menghasilkan 8%/bulan dengan DD 10% jauh lebih bernilai — dan jauh lebih bisa dipertahankan — daripada sistem yang menjanjikan 100% lalu menghapus akun di bulan ketiga. Klien yang kehilangan modal tidak akan kembali.

---

## 1. Ruang Lingkup & Filosofi Sistem

### 1.1 Ini Assistant, Bukan Autotrader (Awalnya)

Sistem dirancang bertahap dalam 3 mode operasi:

```
Mode 1: OBSERVER    -> Analisa + logging, tanpa sinyal.   (Validasi data)
Mode 2: ADVISOR     -> Kirim sinyal ke user, eksekusi manual. (Validasi edge)
Mode 3: EXECUTOR    -> Eksekusi otomatis dengan guardrail. (Hanya setelah Mode 2 terbukti)
```

**Jangan pernah lompat ke Mode 3.** Setiap mode harus lulus kriteria kelulusan (Bagian 9) sebelum naik tingkat. Ini bukan birokrasi — ini yang membedakan proyek yang menghasilkan uang dari proyek yang membakar modal klien.

### 1.2 Mengapa Fokus XAUUSD Saja — Ini Keputusan yang Benar

Fokus tunggal adalah kekuatan, bukan keterbatasan:
- Karakteristik volatilitas gold sangat khas (ATR M5 biasanya 15–40 points)
- Punya pola sesi yang konsisten dan bisa dieksploitasi (Bagian 3.2)
- Model tidak perlu belajar generalisasi lintas instrumen sehingga data lebih efisien
- Satu set parameter risiko, satu spesifikasi kontrak, satu perilaku spread

### 1.3 Realita Timeframe M1 & M5

Anda memilih M1 dan M5. Ini bisa dikerjakan, tapi klien harus tahu trade-off-nya:

**Tantangan pada timeframe rendah:**
- Rasio noise terhadap sinyal sangat tinggi
- Biaya transaksi jadi porsi besar dari target profit
- Spread 20 points terhadap target 40 points = **50% biaya di depan**
- Butuh eksekusi cepat; latency 200ms bisa berarti slippage 5–15 points

**Keputusan desain sebagai respons:**
- **M5 sebagai timeframe eksekusi utama** (sinyal & entry)
- **M1 hanya untuk timing entry presisi** (refinement, bukan generator sinyal)
- **M15/H1/H4 sebagai konteks bias** (filter arah — wajib, tidak opsional)
- Target minimum per trade: **lebih dari 3x spread** — kalau tidak, jangan entry

> Trading M1 murni tanpa konteks HTF adalah cara tercepat membakar akun. Sistem ini akan selalu menggunakan pendekatan multi-timeframe.

---

## 2. Arsitektur Sistem

### 2.1 Diagram Alur

```
+--------------------------------------------------------------+
|  MetaTrader 5 Terminal (jendela terpisah, tetap terbuka)     |
|  - Koneksi broker, feed harga live, eksekusi order           |
+------------------------+-------------------------------------+
                         | Python API (MetaTrader5 package)
                         | IPC lokal - bukan network
+------------------------v-------------------------------------+
|  LAYER 1 - DATA                                              |
|  - Historical loader (M1/M5/M15/H1/H4)                       |
|  - Live tick & bar streaming                                 |
|  - Penyimpanan Parquet + validasi kualitas data              |
|  - Deteksi gap, bar hilang, harga anomali                    |
+------------------------+-------------------------------------+
+------------------------v-------------------------------------+
|  LAYER 2 - FEATURE ENGINEERING                               |
|  - Indikator teknikal (ATR, RSI, EMA, ADX, Bollinger)        |
|  - Struktur market (swing high/low, BOS, CHoCH)              |
|  - Fitur sesi & waktu (Asia/London/NY, jam ke-N)             |
|  - Fitur volatilitas & regime                                |
|  - Konteks multi-timeframe (bias HTF)                        |
+------------------------+-------------------------------------+
+------------------------v-------------------------------------+
|  LAYER 3 - MODEL / DECISION                                  |
|  - Rule engine (baseline strategi, wajib ada duluan)         |
|  - ML classifier (filter kualitas sinyal)                    |
|  - Regime detector (trending / ranging / high-vol)           |
|  - Confidence scoring                                        |
+------------------------+-------------------------------------+
+------------------------v-------------------------------------+
|  LAYER 4 - RISK MANAGEMENT  <- LAYER PALING KRITIS           |
|  - Position sizing (fixed fractional, ATR-based)             |
|  - Batas harian / mingguan (loss limit, max trades)          |
|  - Filter berita (blackout window)                           |
|  - Circuit breaker (kill switch otomatis)                    |
|  - Validasi spread & likuiditas pre-trade                    |
+------------------------+-------------------------------------+
+------------------------v-------------------------------------+
|  LAYER 5 - EXECUTION & MONITORING                            |
|  - Order manager (market/limit, SL/TP, trailing)             |
|  - Dashboard lokal (Streamlit)                               |
|  - Notifikasi (Telegram opsional)                            |
|  - Trade journal & analytics                                 |
+--------------------------------------------------------------+
```

### 2.2 Kritis: MT5 Python API Bersifat Single-Process

Ini detail teknis yang sering menjebak dan harus jadi keputusan arsitektur sejak awal:

- Paket `MetaTrader5` **hanya Windows** dan **tidak thread-safe**
- Hanya boleh **satu proses Python** yang `initialize()` ke satu terminal
- **Solusi:** satu proses `mt5_gateway.py` memegang koneksi tunggal; komponen lain berkomunikasi via file queue / SQLite / ZeroMQ lokal
- Jangan `initialize()` di dashboard Streamlit dan bot secara bersamaan — ini akan menyebabkan kegagalan koneksi yang sulit didiagnosis

### 2.3 Struktur Direktori

```
PROJECT CUAN/
├── docs/                    # Dokumentasi (dokumen ini + turunannya)
├── config/
│   ├── settings.yaml        # Parameter sistem
│   ├── risk_limits.yaml     # Batasan risiko - terpisah & disengaja
│   └── credentials.env      # Login MT5 (JANGAN commit ke git)
├── data/
│   ├── raw/                 # Data mentah dari MT5 (Parquet)
│   ├── processed/           # Dataset dengan fitur
│   └── models/              # Model terlatih (.pkl / .onnx)
├── src/
│   ├── data/                # Loader, validator, streamer
│   ├── features/            # Feature engineering
│   ├── strategy/            # Rule engine & sinyal
│   ├── models/              # Training & inference ML
│   ├── risk/                # Risk manager & circuit breaker
│   ├── execution/           # Order manager & MT5 gateway
│   └── monitoring/          # Dashboard & alerting
├── backtest/
│   ├── engine.py            # Backtester event-driven
│   └── reports/             # Hasil backtest
├── logs/                    # Log terstruktur (JSON)
├── tests/                   # Unit & integration tests
└── notebooks/               # Riset & eksplorasi
```

---

## 3. Ilmu Trading yang Digunakan

Ini bagian inti. Sistem tidak akan menebak-nebak — setiap keputusan berdasar konsep yang punya alasan struktural, bukan sekadar "indikator yang populer".

### 3.1 Fondasi: Market Structure (Prioritas Tertinggi)

Struktur market adalah dasar segalanya. Tanpa ini, indikator hanya noise.

**Konsep yang diimplementasikan:**

| Konsep | Definisi | Cara Deteksi |
|---|---|---|
| **Swing High/Low** | Titik pivot lokal | Fractal: high tertinggi dari N bar kiri-kanan |
| **BOS** (Break of Structure) | Harga menembus swing terakhir searah tren | Close > swing high sebelumnya (uptrend) |
| **CHoCH** (Change of Character) | Sinyal pertama pembalikan tren | Uptrend gagal buat HH lalu tembus LL |
| **HH/HL/LH/LL** | Klasifikasi tren via urutan swing | Perbandingan swing berurutan |

**Aturan bias:**
```
HH + HL berurutan     -> Uptrend    -> HANYA cari BUY
LH + LL berurutan     -> Downtrend  -> HANYA cari SELL
Campuran/tidak jelas  -> Ranging    -> Stand aside atau mean-reversion
```

**Mengapa ini penting:** sebagian besar kerugian trader ritel berasal dari melawan struktur — buy di downtrend karena "sudah murah". Filter ini saja sudah menghilangkan sebagian besar trade buruk.

### 3.2 Analisis Sesi — Edge Terbesar untuk Gold

XAUUSD punya perilaku yang **sangat berbeda per sesi**. Ini salah satu edge paling andal dan paling sering diabaikan.

| Sesi | Waktu (WIB) | Karakteristik | Strategi |
|---|---|---|---|
| **Asia** | 06:00–14:00 | Volatilitas rendah, range-bound, likuiditas tipis | Range trading / **hindari**. Catat high-low Asia sebagai level kunci |
| **London** | 14:00–17:00 | Volatilitas melonjak, sering sweep Asia range | **Sesi terbaik.** Breakout & liquidity sweep reversal |
| **London-NY Overlap** | 19:30–23:00 | Volume & volatilitas tertinggi | **Sesi terbaik #2.** Momentum & trend continuation |
| **NY sore** | 23:00–04:00 | Volatilitas menurun, sering retrace | Kurangi ukuran, hati-hati |

> Jam WIB di atas mengasumsikan periode non-DST. Saat AS/Eropa masuk DST, geser sekitar 1 jam. Sistem harus menghitung sesi dari UTC, bukan hardcode jam WIB.

**Aturan sistem:**
- Trading utama **hanya di London open + NY overlap**
- Sesi Asia: default **tidak trading** (rasio biaya-terhadap-pergerakan buruk)
- Jumat setelah 21:00 WIB: **tidak ada entry baru** (risiko gap weekend)
- **Asia range high/low adalah level likuiditas** — sering di-sweep saat London open

### 3.3 Konsep Likuiditas & Order Flow

Konsep modern yang bekerja baik di gold, karena gold sangat "algoritmik":

- **Liquidity Pool** — kumpulan stop order di atas equal highs / bawah equal lows
- **Liquidity Sweep / Stop Hunt** — harga menembus level, memicu stop, lalu berbalik tajam. **Ini setup dengan RR terbaik di gold.**
- **Fair Value Gap (FVG)** — imbalance 3-bar; sering jadi area retracement
- **Order Block** — candle terakhir sebelum pergerakan impulsif

**Setup unggulan (paling andal untuk XAUUSD M5):**
```
1. Identifikasi Asia range high/low
2. London open: tunggu sweep menembus level tersebut
3. Konfirmasi: CHoCH di M1 + rejection wick + volume spike
4. Entry: retest FVG/order block yang terbentuk
5. SL: di luar wick sweep + buffer ATR
6. TP: liquidity pool sisi berlawanan (biasanya RR 1:2 - 1:4)
```

> Catatan jujur: istilah ICT/SMC di atas populer tapi definisinya bervariasi antar praktisi. Nilainya bukan pada namanya, melainkan pada aturan deteksi yang eksplisit dan bisa diuji. Semua konsep di sini harus diterjemahkan jadi kode deterministik lalu **divalidasi statistik di Fase 2** — kalau tidak terbukti punya edge di data, kita buang, tidak dipertahankan karena populer.

### 3.4 Volatilitas — ATR sebagai Fondasi Manajemen Risiko

**ATR bukan indikator sinyal — ATR adalah alat ukur risiko.** Semua jarak dalam sistem ini dinormalisasi ke ATR, tidak pernah ke pips tetap.

```python
SL_distance = ATR(14) * 1.5      # adaptif terhadap volatilitas
TP_distance = SL_distance * RR   # RR minimal 1.5
position_size = (equity * risk_pct) / (SL_distance * tick_value)
```

**Mengapa jarak tetap berbahaya:** SL 200 points wajar saat ATR 40, tapi jadi bunuh diri saat ATR 15 (kena noise) atau terlalu sempit saat ATR 90 (saat NFP). Normalisasi ATR membuat sistem beradaptasi otomatis.

**Filter volatilitas:**
- ATR terlalu rendah (di bawah persentil 20) → market mati, spread dominan → skip
- ATR terlalu tinggi (di atas persentil 95) → biasanya berita → skip atau kurangi size

### 3.5 Indikator Teknikal — Sebagai Konfirmasi, Bukan Trigger

Digunakan **secukupnya**. Menumpuk 15 indikator adalah tanda sistem tanpa arah.

| Indikator | Fungsi | Parameter |
|---|---|---|
| **ATR(14)** | Ukuran risiko & sizing | Fondasi |
| **EMA(20/50/200)** | Bias tren, dynamic S/R | Multi-TF |
| **RSI(14)** | Divergensi & ekstrem | Bukan overbought/oversold naif |
| **ADX(14)** | Kekuatan tren (>25 = trending) | Regime filter |
| **Bollinger(20,2)** | Ekspansi/kontraksi volatilitas | Squeeze detection |
| **VWAP** | Harga acuan institusional | Intraday, reset harian |
| **Volume (tick)** | Konfirmasi partisipasi | Relatif terhadap MA volume |

**Catatan:** volume di MT5 forex adalah **tick volume**, bukan volume riil. Tetap berguna sebagai proksi aktivitas, tapi jangan diperlakukan seperti volume saham.

### 3.6 Fundamental & Berita — Wajib, Bukan Opsional

Gold sangat sensitif terhadap makro. Mengabaikan kalender ekonomi = bunuh diri.

**Event berdampak tinggi untuk XAUUSD:**
- FOMC, suku bunga Fed, notulen rapat
- NFP (Jumat pertama tiap bulan)
- CPI / PCE (inflasi)
- Yield obligasi AS & DXY (korelasi negatif kuat dengan gold)
- Ketegangan geopolitik (safe haven flow)

**Aturan blackout:**
```
15 menit SEBELUM rilis high-impact  -> tutup posisi, tidak ada entry baru
30 menit SETELAH rilis              -> tunggu spread & volatilitas normal
```
Sumber kalender: Forex Factory (scraping — perlu cek ToS), atau API berbayar. Verifikasi keandalan sumber di Fase 5; sumber yang sering down lebih berbahaya daripada tidak ada filter, karena menciptakan rasa aman palsu.

---

## 4. Pipeline Data

### 4.1 Kebutuhan Data Historis

| Timeframe | Kedalaman Riwayat | Estimasi Jumlah Bar |
|---|---|---|
| M1 | 2 tahun | sekitar 750.000 bar |
| M5 | 3 tahun | sekitar 225.000 bar |
| M15 | 5 tahun | sekitar 125.000 bar |
| H1 | 5 tahun | sekitar 31.000 bar |
| H4 | 10 tahun | sekitar 15.000 bar |

**Catatan penting:** MT5 membatasi riwayat berdasarkan broker. Beberapa broker hanya menyimpan 3–6 bulan data M1. Perlu diverifikasi di Fase 0. Jika kurang, opsi: Dukascopy (tick data gratis) atau vendor data berbayar.

### 4.2 Validasi Kualitas Data — Jangan Dilewati

Data buruk menghasilkan model buruk. Cek wajib:

- Bar hilang (gap di luar jam tutup market normal)
- Harga anomali (spike lebih dari 10 ATR, high < low)
- Duplikasi timestamp
- Konsistensi zona waktu (server broker biasanya GMT+2/+3, **bukan** WIB)
- Gap weekend (Sabtu–Minggu — normal, harus ditandai bukan dihapus)

> **Perangkap zona waktu:** salah handle timezone adalah bug nomor satu di trading bot. Waktu server broker tidak sama dengan waktu lokal maupun UTC. Semua logika sesi **harus** dinormalisasi ke UTC dulu, baru dikonversi.

---

## 5. Feature Engineering

### 5.1 Kategori Fitur

**A. Price Action (sekitar 15 fitur)**
- Body/wick ratio, arah candle, ukuran range relatif ATR
- Jarak ke swing high/low terdekat (dalam ATR)
- Posisi close dalam range bar (0–1)

**B. Trend & Struktur (sekitar 12 fitur)**
- Jarak harga ke EMA20/50/200 (dinormalisasi ATR)
- Susunan EMA (bullish/bearish stack)
- Hitungan HH/HL/LH/LL dalam N bar terakhir
- Bar sejak BOS/CHoCH terakhir

**C. Volatilitas & Regime (sekitar 10 fitur)**
- ATR, persentil ATR (rolling 200 bar)
- Bollinger bandwidth & posisi %B
- Rasio realized volatility (jangka pendek/panjang)
- Nilai ADX & kemiringannya

**D. Sesi & Waktu (sekitar 10 fitur)**
- One-hot sesi (Asia/London/NY/overlap)
- Jam ke-N dalam sesi, menit dalam jam
- Hari dalam minggu
- Jarak ke Asia range high/low
- Menit sampai/sejak rilis berita berdampak tinggi

**E. Multi-Timeframe (sekitar 15 fitur)**
- Bias M15/H1/H4 (bullish/bearish/netral)
- Jarak ke level kunci HTF
- Keselarasan antar timeframe (skor 0–1)

**F. Mikrostruktur (sekitar 8 fitur)**
- Spread saat ini vs rata-rata
- Tick volume relatif terhadap MA
- Kecepatan harga (tick per detik)

**Total sekitar 70 fitur.** Akan direduksi lewat feature importance jadi 25–35 yang benar-benar berkontribusi.

### 5.2 Aturan Anti-Lookahead — MUTLAK

> **Ini penyebab nomor satu backtest yang terlihat sempurna tapi gagal di live.**

Aturan yang tidak boleh dilanggar:
1. Fitur pada bar `t` **hanya** boleh menggunakan data sampai `t-1` close
2. Jangan pakai `high`/`low` bar berjalan untuk keputusan di bar itu
3. Semua rolling window harus di-`shift(1)` setelah kalkulasi
4. Normalisasi (scaling) di-fit **hanya** pada data training, lalu diterapkan ke test — bukan di-fit pada seluruh dataset
5. Label harus dibuat dengan informasi **masa depan saja** dari titik entry

---

## 6. Pendekatan Machine Learning

### 6.1 Framing Masalah — Ini Keputusan Paling Menentukan

**JANGAN prediksi harga.** Regresi harga pada M1/M5 hampir selalu menghasilkan model yang sekadar meniru harga terakhir (naive persistence) — terlihat akurat di metrik R kuadrat, tapi tidak punya nilai trading sama sekali.

**Framing yang benar — Triple Barrier Method (López de Prado):**

Untuk setiap sinyal kandidat dari rule engine, beri label hasilnya:
```
Pasang 3 barrier dari titik entry:
  - Upper barrier    : entry + (ATR * RR)    -> TP
  - Lower barrier    : entry - (ATR * 1.0)   -> SL
  - Vertical barrier : entry + N bar         -> timeout

Label = barrier mana yang tersentuh lebih dulu
  -> 1  (TP kena duluan)  = trade bagus
  -> 0  (SL kena duluan)  = trade jelek
  -> 0  (timeout)         = trade tidak layak
```

**Peran ML = meta-labeling:** Rule engine menghasilkan sinyal, lalu ML memprediksi probabilitas sinyal itu berhasil, lalu ambil hanya yang probabilitasnya tinggi.

Ini jauh lebih kuat daripada membiarkan ML mencari sinyal dari nol, karena:
- Rule engine memastikan sinyal punya logika ekonomi
- ML hanya perlu belajar tugas yang lebih mudah: "apakah setup ini bagus?"
- Dataset lebih seimbang & bisa diinterpretasi
- Kegagalan bisa didiagnosis — bukan black box

### 6.2 Pilihan Model

| Tahap | Model | Alasan |
|---|---|---|
| **Baseline** | Rule-based (tanpa ML) | Wajib. Benchmark. Jika rule tidak profit, ML tidak akan menyelamatkan |
| **Utama** | **LightGBM / XGBoost** | Terbaik untuk tabular, cepat, feature importance jelas |
| **Sekunder** | Random Forest | Pembanding, kurang rentan overfit |
| **Regime** | HMM / KMeans | Deteksi kondisi market unsupervised |
| **Eksperimental** | LSTM / TCN | Hanya jika GBDT sudah maksimal — sering tidak sepadan |

**Rekomendasi tegas: LightGBM.** Untuk data tabular finansial, GBDT secara konsisten mengungguli deep learning. Deep learning masuk akal untuk raw tick sequence, tapi butuh data dan compute jauh lebih besar dengan hasil marginal.

### 6.3 Validasi — Time Series, Bukan Random Split

**JANGAN pakai `train_test_split` acak.** Itu membocorkan masa depan ke masa lalu.

```
Walk-Forward Analysis:
+------------+-----+----------------------------
| Train 6bln | Gap | Test 1bln
+------------+-----+----------------------------
     |__ geser 1 bulan __> ulangi

Gap (purging) = 1-3 hari, mencegah kebocoran via
                label yang periodenya tumpang tindih
```

**Metrik evaluasi — utamakan metrik trading, bukan metrik ML:**
- Precision pada kelas 1 (dari sinyal yang diambil, berapa yang profit)
- Expectancy per trade (dalam R)
- Profit Factor, Sharpe, Max DD
- **Stabilitas antar fold** — paling penting. Model yang bagus di satu fold dan hancur di fold lain adalah model yang overfit, bukan model bagus.

### 6.4 Mencegah Overfitting

Ini musuh utama proyek ML trading:

1. **Batasi kompleksitas** — max_depth maksimal 6, min_samples_leaf tinggi
2. **Batasi jumlah fitur** — sekitar 30 fitur untuk puluhan ribu sampel
3. **Hindari over-optimasi hyperparameter** — setiap percobaan "membakar" sedikit data test
4. **Out-of-sample terkunci** — sisihkan 6 bulan terakhir, **hanya sentuh sekali** di akhir. Jika Anda melihatnya dua kali, itu bukan OOS lagi
5. **Uji Deflated Sharpe Ratio** — koreksi Sharpe terhadap jumlah percobaan
6. **Monte Carlo permutation** — acak urutan trade, cek distribusi hasil

---

## 7. Manajemen Risiko — Bagian Terpenting Seluruh Sistem

> Sistem dengan edge biasa-biasa ditambah risk management ketat = **profitabel.**
> Sistem dengan edge hebat ditambah risk management buruk = **akun habis.**
> Layer ini lebih menentukan hasil akhir daripada kecanggihan modelnya.

### 7.1 Position Sizing

**Fixed Fractional Risk — standar industri:**
```python
risk_per_trade = 0.005                  # 0.5% dari equity
risk_amount    = equity * risk_per_trade
sl_distance    = ATR * 1.5              # dalam points
lot_size       = risk_amount / (sl_distance * tick_value_per_lot)
lot_size       = clamp(lot_size, volume_min, max_allowed)
lot_size       = round_to_step(lot_size, volume_step)
```

**Mengapa 0,5% dan bukan 2%:** Pada M1/M5 frekuensi trade tinggi (5–15 per hari). Risiko 2% dikali 10 trade sama dengan eksposur 20% per hari. Frekuensi tinggi menuntut risiko per trade yang lebih kecil.

### 7.2 Batasan Berlapis (Hard Limits)

```yaml
per_trade:
  max_risk_percent: 0.5
  max_lot_size: 0.50
  min_rr_ratio: 1.5           # tolak setup dengan RR di bawah ini

harian:
  max_loss_percent: 2.0       # STOP TRADING sisa hari
  max_trades: 10
  max_consecutive_losses: 3   # jeda 1 jam setelah tercapai

mingguan:
  max_loss_percent: 5.0       # STOP TRADING sisa minggu

global:
  max_drawdown_percent: 10.0  # MATIKAN SISTEM, perlu review manual
  max_open_positions: 1       # satu posisi saja - tanpa kompleksitas korelasi
  max_spread_points: 35       # tolak entry jika spread melebihi ini
```

Angka-angka ini adalah titik awal yang konservatif, bukan hasil optimasi. Nilai final ditentukan setelah backtest dan disepakati tertulis dengan klien.

### 7.3 Circuit Breaker — Kill Switch Otomatis

Sistem **harus** berhenti otomatis saat:

| Pemicu | Aksi |
|---|---|
| Loss harian tercapai | Stop sampai hari berikutnya |
| Drawdown maksimum tercapai | Matikan total, butuh reset manual |
| Koneksi MT5 putus lebih dari 30 detik | Batalkan pending, alert user |
| Spread lebih dari 3x normal | Jeda trading sampai normal |
| 3 order gagal berturut-turut | Matikan, ada masalah teknis |
| Anomali harga (spike lebih dari 10 ATR) | Jeda, verifikasi feed |
| Window blackout berita | Tidak ada entry baru |
| Equity menyimpang dari ekspektasi melebihi toleransi | Matikan — kemungkinan bug |

**Kill switch manual wajib ada:** file `STOP` di root direktori. Jika file ada, sistem menolak membuka posisi baru. Sederhana, tidak bisa gagal, tidak bergantung pada UI atau jaringan.

### 7.4 Manajemen Stop Loss

- **SL wajib di setiap order** — dikirim bersamaan dengan entry, bukan setelah
- Jangan pernah melebarkan SL. Melebarkan SL adalah cara akun mati.
- Break-even setelah profit 1R (opsional, uji dampaknya di backtest)
- Trailing stop berbasis ATR untuk trade runner
- Partial close di 1,5R, sisanya trailing (uji apakah ini meningkatkan expectancy)

### 7.5 Hal-Hal yang Dilarang Keras

Praktik yang **tidak akan** diimplementasikan, apa pun permintaannya:

| Larangan | Alasan |
|---|---|
| **Martingale** | Menggandakan lot setelah loss. Menghasilkan winrate semu tinggi, lalu menghapus akun. Kebangkrutan matematis pasti dalam waktu cukup lama |
| **Grid tanpa SL** | Floating loss tak terbatas saat trend kuat |
| **Averaging down** | Menambah posisi rugi sama dengan memperbesar kesalahan |
| **Trading tanpa SL** | Satu event ekor bisa menghapus akun |
| **Revenge trading** | Menaikkan size setelah loss untuk balas dendam |
| **Menonaktifkan risk limit** untuk "mengejar peluang" | Limit ada justru untuk momen ini |

---

## 8. Backtesting & Validasi

### 8.1 Backtester Wajib Realistis

Backtest optimistis adalah **penipuan diri sendiri yang mahal**. Harus memodelkan:

- **Spread realistis** — variabel per sesi, melebar saat berita (bukan konstan)
- **Slippage** — 2–8 points untuk market order XAUUSD; lebih besar saat volatil
- **Komisi & swap** — sesuai spesifikasi broker
- **Latency eksekusi** — 100–300ms antara sinyal dan fill
- **Requote / order ditolak** — probabilitas kecil tapi bukan nol
- **Eksekusi bar berikutnya** — sinyal di close bar `t` menghasilkan fill di open bar `t+1`

### 8.2 Ambiguitas SL/TP dalam Satu Bar — Jangan Diabaikan

Jika dalam satu bar M5 harga menyentuh SL **dan** TP, mana yang duluan? Data OHLC tidak memberi tahu urutannya.

**Solusi (pilih salah satu, dan konsisten):**
- **Konservatif (rekomendasi):** asumsikan SL kena duluan — pesimistis, aman
- **Presisi:** turunkan ke data M1 atau tick untuk menentukan urutan sebenarnya

Menggunakan asumsi optimistis (TP duluan) akan membuat backtest tampak jauh lebih bagus daripada realita. Ini sumber kekecewaan yang sangat umum.

### 8.3 Uji Robustness

Model yang baik harus bertahan di semua uji ini:

1. **Walk-forward** — konsisten profit di berbagai periode
2. **Monte Carlo** — acak urutan trade 1000 kali, lihat distribusi DD
3. **Sensitivitas parameter** — ubah parameter plus-minus 20%; jika hasil hancur, itu curve-fit, bukan edge
4. **Uji per regime** — performa di trending vs ranging vs high-vol
5. **Uji per periode** — 2020 (COVID), 2022 (inflasi), 2023–2025 (variasi)
6. **Out-of-sample** — 6 bulan terkunci, satu kali evaluasi

### 8.4 Forward Test — Tidak Bisa Dilewati

**Minimum 4–8 minggu di akun DEMO** dengan kondisi live sebelum menyentuh uang sungguhan. Bandingkan metrik demo vs backtest:
- Jika demo jauh lebih buruk, berarti ada lookahead bias atau asumsi biaya keliru
- Deviasi wajar 10–20%. Deviasi di atas 40% berarti ada yang salah mendasar

---

## 9. Roadmap Implementasi

### Fase 0 — Setup & Verifikasi Lingkungan (2–3 hari)

**Status lingkungan saat ini (sudah diperiksa):**
- MT5 terinstall di `C:\Program Files\MetaTrader 5`
- Python 3.13.4 (64-bit) dengan paket `MetaTrader5` 5.0.5735 sudah terpasang
- **MT5 belum login ke akun broker** — probe koneksi gagal dengan `(-6, 'Authorization failed')`. **Ini blocker pertama yang harus diselesaikan.**

**Tugas:**
- [ ] Buka MT5, login ke **akun demo** broker (jangan real dulu)
- [ ] Aktifkan: Tools → Options → Expert Advisors → "Allow algorithmic trading"
- [ ] Verifikasi koneksi Python ke MT5
- [ ] **Dokumentasikan spesifikasi simbol XAUUSD broker Anda:** nama simbol persis (bisa `XAUUSD`, `GOLD`, `XAUUSD.m`, `XAUUSDm`), digits, point, contract size, tick value, volume_min/step, stops_level, spread rata-rata per sesi
- [ ] Cek kedalaman riwayat M1 yang tersedia dari broker
- [ ] Setup virtual environment & dependencies
- [ ] Inisialisasi git repository (`.gitignore` wajib mengecualikan credentials)

> **Catatan penting soal broker:** spesifikasi kontrak berbeda antar broker. Ada yang tick value 1 USD per lot, ada yang 10 USD per lot. Salah asumsi di sini membuat position sizing meleset sepuluh kali lipat. **Harus diverifikasi, tidak boleh diasumsikan.**

### Fase 1 — Data Foundation (1 minggu)
- [ ] `mt5_gateway.py` — koneksi tunggal, auto-reconnect
- [ ] Historical downloader multi-timeframe ke Parquet
- [ ] Data validator (gap, anomali, timezone)
- [ ] Live bar streamer dengan callback
- [ ] Notebook EDA: distribusi ATR per sesi, pola volatilitas jam-an, perilaku spread, karakteristik sweep Asia range
- [ ] **Deliverable:** dataset bersih & tervalidasi plus laporan EDA

### Fase 2 — Rule Engine Baseline (1–2 minggu)
- [ ] Deteksi market structure (swing, BOS, CHoCH)
- [ ] Klasifikasi sesi & Asia range tracker
- [ ] Implementasi 2–3 strategi:
      (a) London liquidity sweep reversal
      (b) NY momentum continuation
      (c) Asia range breakout (opsional)
- [ ] Modul indikator (ATR, EMA, RSI, ADX, BB, VWAP)
- [ ] **Deliverable:** rule engine menghasilkan sinyal plus statistik dasar

> **Gate kelulusan Fase 2:** Rule engine harus menunjukkan expectancy positif pada data historis **sebelum** ML disentuh. Jika rule tidak profit, ML tidak akan memperbaikinya — ML hanya memfilter sinyal yang sudah punya edge. Jika gagal di sini: kembali ke riset strategi, jangan lanjut ke Fase 3.

### Fase 3 — Backtesting Engine (1–2 minggu)
- [ ] Backtester event-driven dengan biaya realistis
- [ ] Model spread & slippage per sesi
- [ ] Penanganan ambiguitas SL/TP intra-bar
- [ ] Modul metrik lengkap (Sharpe, PF, DD, expectancy, dll.)
- [ ] Generator laporan HTML (equity curve, distribusi, per-sesi)
- [ ] Walk-forward framework
- [ ] **Deliverable:** backtest baseline yang bisa dipercaya

### Fase 4 — Machine Learning Layer (2–3 minggu)
- [ ] Pipeline feature engineering (sekitar 70 fitur)
- [ ] Labeling triple-barrier
- [ ] Training LightGBM dengan walk-forward
- [ ] Analisis feature importance & seleksi fitur
- [ ] Kalibrasi probabilitas plus tuning threshold
- [ ] Perbandingan: rule-only vs rule+ML
- [ ] Uji robustness (Monte Carlo, sensitivitas)
- [ ] **Deliverable:** model terlatih plus laporan validasi jujur

> **Gate kelulusan Fase 4:** rule+ML harus mengungguli rule-only secara **konsisten di semua fold walk-forward** — bukan hanya rata-rata bagus. Jika ML tidak memberi perbaikan nyata, **pakai rule engine saja.** Sistem sederhana yang profitabel mengalahkan sistem kompleks yang rapuh.

### Fase 5 — Risk & Execution (1–2 minggu)
- [ ] Risk manager dengan seluruh limit berlapis
- [ ] Circuit breaker & kill switch (termasuk file `STOP`)
- [ ] Order manager (entry, SL/TP, trailing, partial)
- [ ] Filter berita (integrasi kalender ekonomi)
- [ ] Rekonsiliasi state (posisi sistem vs posisi MT5 aktual)
- [ ] Logging & audit trail terstruktur
- [ ] **Deliverable:** layer eksekusi lengkap dengan proteksi berlapis

### Fase 6 — Monitoring & Dashboard (1 minggu)
- [ ] Dashboard Streamlit: posisi, equity, sinyal, log
- [ ] Trade journal dengan analitik
- [ ] Notifikasi Telegram (opsional)
- [ ] Health check & heartbeat
- [ ] **Deliverable:** UI operasional untuk klien

### Fase 7 — Demo Forward Test (4–8 minggu) — WAJIB, JANGAN DIPOTONG
- [ ] Jalankan Mode ADVISOR di akun demo
- [ ] Catat setiap sinyal & hasilnya
- [ ] Bandingkan performa live vs backtest
- [ ] Perbaiki gap yang ditemukan
- [ ] **Deliverable:** bukti bahwa sistem bekerja di kondisi nyata

> Fase ini paling sering dipangkas karena tekanan waktu, dan justru paling sering jadi penyebab kegagalan proyek. Fase ini yang membedakan "demo yang mengesankan" dari "sistem yang layak dipercaya uang klien".

### Fase 8 — Live Deployment Bertahap (berkelanjutan)
- [ ] Live dengan modal minimal (uang yang siap hilang)
- [ ] Risiko 0,25% per trade selama bulan pertama
- [ ] Naikkan bertahap **hanya jika** metrik sesuai ekspektasi
- [ ] Review mingguan, retraining bulanan
- [ ] Monitoring model drift

**Total estimasi: 12–20 minggu** sampai live dengan modal nyata. Angka ini realistis. Timeline yang lebih cepat berarti ada fase yang dipotong — dan fase yang dipotong biasanya risk management atau forward test.

---

## 10. Tech Stack

```yaml
Bahasa: Python 3.11+ (3.13.4 terdeteksi - verifikasi kompatibilitas paket)

Terhubung MT5:
  - MetaTrader5      # API resmi (Windows-only)

Data:
  - pandas, numpy
  - pyarrow          # Parquet
  - polars           # opsional, cepat untuk dataset besar

Indikator:
  - pandas-ta        # atau implementasi manual (lebih terkontrol)
  - TA-Lib           # opsional, butuh binary Windows

Machine Learning:
  - scikit-learn
  - lightgbm         # model utama
  - xgboost          # pembanding
  - optuna           # tuning hyperparameter (gunakan hemat)

Backtesting:
  - Engine custom    # rekomendasi - kontrol penuh atas asumsi biaya
  - vectorbt         # opsional untuk screening cepat

Visualisasi & UI:
  - plotly
  - streamlit

Utilitas:
  - pydantic         # validasi konfigurasi
  - loguru           # logging terstruktur
  - APScheduler      # penjadwalan
  - python-dotenv
```

**Catatan Python 3.13:** beberapa paket ML (TA-Lib, versi lama LightGBM) mungkin belum punya wheel untuk 3.13. Jika muncul masalah instalasi, **Python 3.11 adalah pilihan paling aman** untuk ekosistem ini. Ini perlu diverifikasi di Fase 0.

---

## 11. Risiko Proyek & Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Riwayat M1 broker tidak cukup | Tinggi | Verifikasi di Fase 0; siapkan sumber eksternal (Dukascopy) |
| Overfitting model | Tinggi | Walk-forward, OOS terkunci, uji sensitivitas |
| Rule engine tidak punya edge | Tinggi | Gate Fase 2; siap iterasi strategi |
| Perbedaan backtest vs live | Tinggi | Model biaya realistis plus forward test wajib |
| MT5 disconnect saat posisi terbuka | Sedang | Auto-reconnect, SL selalu di server (bukan virtual) |
| Perubahan regime market | Sedang | Regime detector, retraining berkala, monitoring drift |
| Broker requote/slippage tinggi | Sedang | Uji broker di demo; pilih broker ECN spread rendah |
| Paket tidak kompatibel Python 3.13 | Rendah | Fallback ke Python 3.11 |
| **Ekspektasi klien tidak realistis** | **Tinggi** | **Dokumen ini, Bagian 0. Selaraskan sejak awal — sebelum kontrak** |

Risiko terakhir itu bukan basa-basi. Proyek trading paling sering gagal bukan karena teknis, tapi karena ekspektasi yang tidak pernah diluruskan di awal.

---

## 12. Kriteria Sukses

Sistem dinyatakan berhasil jika, setelah 3 bulan live:

- [ ] Profit Factor di atas 1,3
- [ ] Max Drawdown di bawah 12%
- [ ] Sharpe Ratio di atas 1,0
- [ ] Deviasi performa live vs backtest di bawah 25%
- [ ] Tidak ada pelanggaran risk limit
- [ ] Uptime sistem di atas 95% saat jam trading
- [ ] Semua trade terlogging & dapat diaudit

**Bukan** kriteria sukses: winrate tinggi, profit besar dalam satu bulan, nol loss.

---

## 13. Catatan Legal & Etis

- Trading forex/CFD berisiko tinggi; mayoritas trader ritel merugi (broker teregulasi wajib mengungkapkan angka ini — umumnya 70–80%)
- Sistem ini alat bantu, bukan jaminan profit
- Klien harus memahami risiko dan hanya menggunakan modal yang siap hilang
- Performa masa lalu tidak menjamin hasil masa depan
- **Jangan menjanjikan angka return spesifik kepada klien**
- Pertimbangkan disclaimer tertulis dalam kontrak kerja
- Jika mengelola dana pihak ketiga, periksa persyaratan regulasi yang berlaku di Indonesia (OJK/Bappebti) — pengelolaan dana orang lain punya konsekuensi hukum tersendiri

---

## 14. Langkah Selanjutnya

**Segera (blocker):**
1. Login MT5 ke akun demo broker — koneksi Python saat ini gagal
2. Jalankan probe spesifikasi simbol XAUUSD
3. Verifikasi kedalaman riwayat M1 yang tersedia

**Setelah itu:**
4. Review dokumen ini bersama klien — terutama **Bagian 0**
5. Sepakati target realistis secara tertulis
6. Mulai Fase 0

**Keputusan yang perlu diambil sebelum coding:**
- Broker mana yang dipakai? (mempengaruhi spread, riwayat, spesifikasi)
- Ukuran modal target? (mempengaruhi position sizing minimum)
- Klien ingin advisory (sinyal) atau full otomatis?
- Apakah ada preferensi jam trading spesifik dari klien?

---

*Dokumen ini adalah perencanaan, bukan janji hasil. Setiap angka target bersifat estimasi berdasarkan standar industri dan harus divalidasi dengan data aktual selama implementasi.*
