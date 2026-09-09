# Roadmap Detail — Tahap demi Tahap

**Versi:** 1.0
**Tanggal:** 9 September 2026
**Status:** Rencana kerja operasional
**Prasyarat baca:** `00-MASTER-PLAN.md`, `01-SMALL-CAPITAL-AGGRESSIVE.md`

---

## Cara Membaca Dokumen Ini

Setiap tahap punya struktur yang sama:

| Bagian | Isinya |
|---|---|
| **Tujuan** | Apa yang ingin dicapai, dalam satu kalimat |
| **Kenapa tahap ini ada** | Alasannya — supaya tidak dikerjakan asal jadi |
| **Tugas** | Checklist konkret |
| **Deliverable** | Hasil nyata yang bisa dilihat |
| **Kriteria lulus** | Syarat untuk boleh lanjut ke tahap berikutnya |
| **Jika gagal** | Apa yang dilakukan kalau kriteria tidak tercapai |

**Aturan utama:** jangan lanjut ke tahap berikutnya sebelum kriteria lulus
terpenuhi. Melewati tahap adalah cara paling umum proyek seperti ini gagal —
bukan karena kurang pintar, tapi karena kesalahan di tahap awal baru terlihat
saat uang sudah hilang.

---

## Peta Keseluruhan

```
TAHAP 0  Persiapan               2-3 hari    -> Broker & lingkungan siap
TAHAP 1  Data                    1 minggu    -> Data bersih & tervalidasi
TAHAP 2  Strategi Dasar          2 minggu    -> Rule engine punya edge
TAHAP 3  Backtest Jujur          2 minggu    -> Angka yang bisa dipercaya
TAHAP 4  Optimasi Profit         2 minggu    -> Expectancy dimaksimalkan
TAHAP 5  Machine Learning        3 minggu    -> Winrate naik, TP tetap besar
TAHAP 6  Risk & Eksekusi         2 minggu    -> Sistem tidak bisa bunuh diri
TAHAP 7  Dashboard               1 minggu    -> Bisa dipantau & diaudit
TAHAP 8  Demo Forward Test       6 minggu    -> Bukti bekerja di kondisi nyata
TAHAP 9  Live Bertahap           3 bulan+    -> Uang nyata, naik pelan-pelan
                                 ---------
                            Total ~5-6 bulan sampai live penuh
```

**Catatan tentang durasi:** angka ini asumsi pengerjaan konsisten beberapa
jam per hari. Yang tidak boleh dipotong adalah Tahap 8 — enam minggu itu
kebutuhan statistik untuk mengumpulkan cukup trade, bukan buffer waktu.

---

## TAHAP 0 — Persiapan (2–3 hari)

### Tujuan
Memastikan lingkungan kerja dan broker benar-benar layak sebelum menulis
kode apa pun.

### Kenapa tahap ini ada
Salah pilih broker di awal berarti semua pekerjaan setelahnya dibangun di
atas fondasi yang salah. Contoh konkret: jika `tick_value` broker berbeda
dari asumsi, position sizing bisa meleset 100x lipat — cukup untuk
menghabiskan modal dalam satu trade.

### Tugas

**A. Pilih broker** (blocker utama — belum ditentukan)

Kriteria wajib:

| Kriteria | Syarat | Cara cek |
|---|---|---|
| Akun cent | Tersedia | Website broker / tanya support |
| XAUUSD di akun cent | Tersedia | **Wajib dikonfirmasi** — banyak broker hanya sediakan forex pair |
| Spread XAUUSD | < 25 points | Buka demo, lihat Market Watch saat London |
| Regulasi | ASIC/FCA/CySEC | Cek nomor lisensi di situs regulator |
| Riwayat M1 | Min. 1 tahun | Script probe akan cek |
| API MT5 | Aktif | Script probe akan cek |
| Leverage | 1:200–1:500 | Cukup; tidak perlu lebih |

- [ ] Bandingkan minimal 3 broker
- [ ] Buka **akun demo** di broker terpilih (jangan real dulu)
- [ ] Catat hasilnya di `docs/broker-comparison.md`

**B. Setup MT5**
- [ ] Login MT5 ke akun demo
- [ ] Tools → Options → Expert Advisors → centang "Allow algorithmic trading"
- [ ] Tambahkan XAUUSD ke Market Watch

**C. Setup Python**
- [ ] Buat virtual environment
- [ ] Install dependencies
- [ ] Jalankan `python scripts/phase0_probe.py`
- [ ] **Simpan seluruh output ke `docs/broker-specs.md`**

**D. Setup project**
- [ ] `git init` + `.gitignore` (wajib exclude credentials & data)
- [ ] Buat struktur folder sesuai master plan

### Deliverable
- Akun demo aktif dengan koneksi Python terverifikasi
- `docs/broker-specs.md` berisi spesifikasi lengkap
- Repository siap

### Kriteria lulus
- [ ] Script probe jalan tanpa error
- [ ] Bagian sizing menampilkan **[OK]** — bukan [BAHAYA]
- [ ] Riwayat M1 minimal 1 tahun tersedia
- [ ] Median spread London/NY di bawah 25 points

### Jika gagal
| Masalah | Solusi |
|---|---|
| Sizing [BAHAYA] | Broker tidak punya akun cent yang layak → **ganti broker** |
| Riwayat M1 < 1 tahun | Ganti broker, atau siapkan data Dukascopy |
| Spread > 30 points | Ganti broker — spread setinggi ini membunuh sistem |

> Jangan kompromi di tahap ini. Mengganti broker sekarang butuh 1 hari;
> menyadarinya di Tahap 8 berarti mengulang berminggu-minggu pekerjaan.

---

## TAHAP 1 — Data (1 minggu)

### Tujuan
Mengumpulkan data historis yang bersih dan tervalidasi.

### Kenapa tahap ini ada
Model dan backtest hanya sebaik datanya. Data dengan bar hilang, timestamp
salah, atau timezone kacau menghasilkan sistem yang tampak bagus di layar
tapi gagal di pasar. Ini kesalahan yang sulit dideteksi belakangan karena
tidak memunculkan error — hanya hasil yang salah.

### Tugas

**A. Gateway MT5** (`src/data/mt5_gateway.py`)
- [ ] Koneksi tunggal (ingat: API MT5 tidak thread-safe)
- [ ] Auto-reconnect saat putus
- [ ] Health check

**B. Downloader** (`src/data/downloader.py`)
- [ ] Ambil M1, M5, M15, H1, H4
- [ ] Simpan ke Parquet
- [ ] Download bertahap (MT5 batasi jumlah bar per request)

**C. Validator** (`src/data/validator.py`)

Cek wajib:
- [ ] Bar hilang di luar jam tutup normal
- [ ] Duplikasi timestamp
- [ ] Harga tidak masuk akal (high < low, spike > 10 ATR)
- [ ] **Konversi timezone ke UTC** — semua logika sesi pakai UTC
- [ ] Tandai (bukan hapus) gap weekend

**D. Analisis awal** (`notebooks/01_eda.ipynb`)
- [ ] Distribusi ATR per jam & per sesi
- [ ] Pola spread per sesi (konfirmasi hasil probe)
- [ ] Seberapa sering London menyapu (sweep) range Asia?
- [ ] Berapa pergerakan rata-rata setelah sweep terjadi?

### Deliverable
- Dataset Parquet bersih untuk 5 timeframe
- Laporan validasi (berapa bar hilang, anomali ditemukan)
- Notebook EDA dengan grafik

### Kriteria lulus
- [ ] Data M1 minimal 1 tahun, kelengkapan > 95%
- [ ] Tidak ada anomali harga tersisa
- [ ] Timezone terverifikasi benar (cek manual beberapa titik waktu)
- [ ] EDA menunjukkan pola sesi yang jelas

### Jika gagal
Data tidak lengkap → cari sumber tambahan (Dukascopy gratis) sebelum lanjut.
Melanjutkan dengan data buruk hanya memindahkan masalah ke tahap berikutnya.

---

## TAHAP 2 — Strategi Dasar (2 minggu)

### Tujuan
Membuat rule engine yang menghasilkan sinyal dengan expectancy positif —
**tanpa ML sama sekali**.

### Kenapa tahap ini ada
Ini gerbang terpenting seluruh proyek. **ML tidak menciptakan edge, ML hanya
menyaring edge yang sudah ada.** Kalau aturan dasarnya tidak profitabel,
menambahkan machine learning hanya menghasilkan sistem rumit yang tetap rugi
— dan jauh lebih sulit didiagnosis.

Banyak proyek gagal karena langsung lompat ke ML, berharap model menemukan
sesuatu yang tidak ada.

### Tugas

**A. Deteksi struktur market** (`src/strategy/structure.py`)
- [ ] Swing high/low (metode fractal)
- [ ] BOS — Break of Structure
- [ ] CHoCH — Change of Character
- [ ] Klasifikasi tren: uptrend / downtrend / ranging

**B. Sesi & level** (`src/strategy/sessions.py`)
- [ ] Klasifikasi sesi dari UTC
- [ ] Tracker Asia range (high/low)
- [ ] Deteksi liquidity sweep

**C. Indikator** (`src/features/indicators.py`)
- [ ] ATR, EMA (20/50/200), RSI, ADX, Bollinger, VWAP
- [ ] **Wajib: semua di-`shift(1)`** agar tidak melihat masa depan

**D. Strategi** (`src/strategy/setups.py`)

Prioritas 1 — **London Sweep Reversal** (setup unggulan):
```
1. Catat Asia range (high & low)
2. Sesi London: tunggu harga menembus salah satu batas
3. Konfirmasi: harga kembali masuk ke dalam range + CHoCH di M1
4. Entry: saat retest area sweep
5. SL: di luar wick sweep + buffer 0,3 ATR
6. TP: sisi berlawanan Asia range (biasanya RR 1:2 - 1:4)
```

Prioritas 2 — **NY Momentum Continuation**:
```
1. Bias searah struktur H1
2. Sesi NY overlap: tunggu pullback ke EMA20 M5
3. Konfirmasi: rejection candle + ADX > 25
4. Entry: saat konfirmasi muncul
5. SL: di bawah swing low terakhir
6. TP: 2x jarak SL
```

**E. Statistik awal** (`notebooks/02_strategy_stats.ipynb`)
- [ ] Berapa sinyal per hari?
- [ ] Winrate mentah tiap setup
- [ ] Distribusi RR yang tercapai
- [ ] Performa per sesi dan per hari

### Deliverable
- Rule engine berfungsi
- Statistik tiap setup
- Visualisasi contoh sinyal di chart

### Kriteria lulus (GERBANG PENTING)
- [ ] Minimal 1 setup dengan **expectancy positif** (belum perlu bagus)
- [ ] Frekuensi sinyal masuk akal: 1–5 per hari
- [ ] Sinyal terlihat logis saat diperiksa manual di chart
- [ ] Winrate 35–55% dengan RR rata-rata di atas 1,5

### Jika gagal
**Jangan lanjut ke Tahap 3.** Yang dilakukan:
1. Periksa apakah ada bug di deteksi struktur (paling sering)
2. Uji variasi parameter (panjang swing, buffer ATR)
3. Coba setup alternatif
4. Jika setelah iterasi tetap tidak ada edge → sampaikan ke klien secara
   jujur bahwa pendekatan ini perlu dievaluasi ulang

> Tahap ini boleh memakan waktu lebih lama dari rencana. Lebih baik 4 minggu
> di sini dengan hasil yang benar, daripada 2 minggu lalu membangun 4 tahap
> berikutnya di atas strategi yang tidak punya edge.

---

## TAHAP 3 — Backtest Jujur (2 minggu)

### Tujuan
Mengukur performa strategi dengan biaya realistis, sehingga angkanya bisa
dipercaya.

### Kenapa tahap ini ada
Backtest optimistis adalah penipuan diri sendiri yang mahal. Selisih antara
backtest dan live hampir selalu berasal dari biaya yang tidak dimodelkan.
Lebih baik melihat angka yang mengecewakan sekarang daripada kehilangan uang
nanti.

### Tugas

**A. Engine backtest** (`backtest/engine.py`)
- [ ] Event-driven, bar per bar
- [ ] **Eksekusi di bar berikutnya** — sinyal di close bar t, entry di open t+1
- [ ] Tracking posisi, equity, drawdown

**B. Model biaya realistis** — ini bagian kritisnya

| Komponen | Cara model |
|---|---|
| Spread | **Variabel per sesi**, dari data aktual Tahap 1 |
| Slippage entry | 2–8 points acak, lebih besar saat ATR tinggi |
| Slippage SL | 3–15 points (SL sering kena lebih buruk) |
| Komisi | Sesuai spesifikasi broker |
| Latency | Asumsi 200ms |

- [ ] **Ambiguitas SL/TP dalam 1 bar:** pakai asumsi konservatif (SL kena duluan)

**C. Metrik** (`backtest/metrics.py`)
- [ ] Winrate, RR rata-rata, **expectancy (metrik utama)**
- [ ] Profit Factor, Sharpe, Max Drawdown
- [ ] Rentetan loss terpanjang
- [ ] Breakdown per sesi, per hari, per bulan

**D. Laporan** (`backtest/report.py`)
- [ ] Equity curve
- [ ] Grafik drawdown
- [ ] Distribusi hasil trade
- [ ] Output HTML

### Deliverable
- Backtester yang bisa dipercaya
- Laporan lengkap strategi Tahap 2

### Kriteria lulus
- [ ] Expectancy tetap positif **setelah semua biaya**
- [ ] Profit Factor > 1,2
- [ ] Minimal 200 trade dalam sampel
- [ ] Hasil konsisten di berbagai periode (tidak hanya menang di satu tahun)

### Jika gagal
Expectansi jadi negatif setelah biaya → ini informasi berharga, bukan
kegagalan. Artinya target TP terlalu kecil relatif terhadap spread.
Solusinya: perbesar target, perketat seleksi setup, atau keduanya. Lalu
ulangi.

---

## TAHAP 4 — Optimasi Profit (2 minggu)

### Tujuan
Memaksimalkan expectancy dari edge yang sudah terbukti ada.

### Kenapa tahap ini ada
Inilah tahap yang menjawab pertanyaan "bagaimana memaksimalkan profit". Edge
sudah ada dari Tahap 2–3; sekarang kita perbesar tanpa menambah risiko.

Setiap optimasi di sini punya dampak terukur. Ini pekerjaan nyata dengan
hasil nyata.

### Tugas

**A. Optimasi biaya** (dampak terbesar, usaha terkecil)
- [ ] Uji filter spread: berapa batas optimal? (20/25/30 points)
- [ ] Uji jam trading: jam mana yang expectancy-nya tertinggi?
- [ ] Buang jam dengan expectancy negatif
- [ ] **Dampak estimasi: +15–25% expectancy**

**B. Optimasi manajemen posisi**
- [ ] Uji break-even di 1R: membantu atau merugikan?
- [ ] Uji partial close di 1,5R
- [ ] Uji trailing stop ATR (multiplier 1,5 / 2,0 / 2,5)
- [ ] Uji timeout: berapa bar maksimal posisi dibiarkan?
- [ ] **Dampak estimasi: RR rata-rata 2,0 → 2,5**

**C. Optimasi seleksi setup**
- [ ] Bangun sistem skoring konfluensi (lihat dokumen 01, Bagian 2.3)
- [ ] Uji threshold skor: 5 / 6 / 7 / 8
- [ ] Trade-off: skor tinggi = lebih sedikit trade tapi kualitas lebih baik
- [ ] **Dampak estimasi: winrate +5–10% tanpa mengecilkan TP**

**D. Filter regime**
- [ ] Deteksi trending vs ranging (pakai ADX)
- [ ] Cek: setup mana bekerja di regime mana?
- [ ] Matikan setup di regime yang tidak cocok

**E. Uji ketahanan** — jangan dilewati
- [ ] Ubah tiap parameter ±20%: apakah hasil hancur?
- [ ] Jika ya → itu curve fitting, bukan edge
- [ ] Monte Carlo: acak urutan trade 1000x, lihat sebaran drawdown

### Deliverable
- Parameter optimal terdokumentasi
- Perbandingan sebelum vs sesudah optimasi
- Laporan uji ketahanan

### Kriteria lulus
- [ ] Expectancy naik minimal 30% dari baseline Tahap 3
- [ ] Profit Factor > 1,4
- [ ] **Hasil tetap stabil saat parameter diubah ±20%**
- [ ] Monte Carlo: drawdown persentil-95 masih di bawah 35%

### Jika gagal
Hasil hancur saat parameter digeser sedikit → itu tanda over-optimasi.
Kembali ke parameter yang lebih sederhana dan lebih longgar. Sistem yang
sedikit kurang optimal tapi stabil jauh lebih berharga daripada sistem
"optimal" yang rapuh.

> **Peringatan:** semakin banyak kombinasi parameter yang dicoba, semakin
> besar risiko menemukan hasil bagus karena kebetulan. Batasi jumlah
> percobaan, dan selalu verifikasi dengan uji sensitivitas.

---

## TAHAP 5 — Machine Learning (3 minggu)

### Tujuan
Menaikkan winrate dari sekitar 45% ke 50–55% **tanpa mengecilkan TP**.

### Kenapa tahap ini ada
Inilah satu-satunya jalur sah untuk menaikkan winrate. ML tidak mencari
sinyal baru — ML menyaring sinyal dari rule engine, membuang yang
berkualitas rendah.

Naik dari 45% ke 55% dengan RR tetap 1:2 adalah peningkatan expectancy yang
besar: dari +0,35R menjadi +0,65R. Hampir dua kali lipat.

### Tugas

**A. Feature engineering** (`src/features/`)
- [ ] Bangun ~70 fitur sesuai master plan Bagian 5
- [ ] **Audit anti-lookahead ketat** — setiap fitur diperiksa satu per satu
- [ ] Simpan dataset ke Parquet

**B. Pelabelan** (`src/models/labeling.py`)
- [ ] Triple barrier: TP / SL / timeout
- [ ] Label dibuat hanya dari data setelah titik entry
- [ ] Cek keseimbangan kelas

**C. Training** (`src/models/train.py`)
- [ ] LightGBM sebagai model utama
- [ ] **Walk-forward validation** (train 6 bulan → gap 3 hari → test 1 bulan)
- [ ] Batasi kompleksitas: max_depth ≤ 6
- [ ] Kalibrasi probabilitas

**D. Seleksi fitur**
- [ ] Feature importance
- [ ] Buang fitur yang tidak berkontribusi
- [ ] Target akhir: 25–35 fitur

**E. Penentuan threshold**
- [ ] Uji threshold probabilitas: 0,55 / 0,60 / 0,65 / 0,70
- [ ] Trade-off: threshold tinggi = trade lebih sedikit, winrate lebih tinggi
- [ ] Pilih yang memaksimalkan **expectancy total**, bukan winrate

**F. Perbandingan jujur**
- [ ] Rule-only vs Rule+ML
- [ ] Bandingkan di **setiap fold**, bukan hanya rata-rata

### Deliverable
- Model terlatih
- Laporan feature importance
- Perbandingan rule-only vs rule+ML per fold

### Kriteria lulus (GERBANG PENTING)
- [ ] Rule+ML mengungguli rule-only di **minimal 8 dari 10 fold**
- [ ] Peningkatan expectancy minimal +20%
- [ ] Winrate naik **tanpa** mengecilkan TP
- [ ] Model tidak menunjukkan tanda overfitting (performa train ≈ test)

### Jika gagal
**Pakai rule engine saja, lewati ML.** Ini keputusan yang sah dan tidak
memalukan. Sistem sederhana yang profitabel jauh lebih baik daripada sistem
kompleks yang rapuh.

ML yang tidak memberi perbaikan konsisten hanya menambah titik kegagalan
tanpa menambah nilai.

---

## TAHAP 6 — Risk & Eksekusi (2 minggu)

### Tujuan
Membuat sistem yang secara struktural tidak bisa menghancurkan akun.

### Kenapa tahap ini ada
Ini layer yang paling menentukan hasil akhir. Sistem dengan edge biasa +
risk management ketat akan bertahan; sistem dengan edge hebat + risk
management buruk akan kehilangan modal.

Semua aturan risiko **dikunci di level kode**, bukan sekadar dicatat di
dokumen — supaya tidak bisa dilanggar saat emosi sedang tinggi.

### Tugas

**A. Position sizing** (`src/risk/sizing.py`)
- [ ] Hitung lot dari risiko % dan jarak SL
- [ ] **Pakai `tick_value` aktual dari probe Tahap 0**
- [ ] Bulatkan ke `volume_step`, hormati `volume_min`
- [ ] Hard cap maksimum

**B. Risk manager** (`src/risk/manager.py`)

Semua limit dari `risk_limits.yaml`:
- [ ] Maksimum risiko per trade (3%)
- [ ] Batas loss harian (9%) → stop sisa hari
- [ ] Batas loss mingguan (15%) → stop sisa minggu
- [ ] Maksimum 6 trade/hari
- [ ] 3 loss beruntun → stop
- [ ] Maksimum 1 posisi terbuka
- [ ] **De-risking otomatis:** DD > 15% → risiko turun ke 1,5%

**C. Circuit breaker** (`src/risk/circuit_breaker.py`)
- [ ] File `STOP` di root → tolak semua entry baru
- [ ] MT5 disconnect > 30 detik → alert
- [ ] Spread abnormal → jeda
- [ ] 3 order gagal beruntun → matikan
- [ ] DD 25% → matikan total, perlu reset manual

**D. Filter berita** (`src/risk/news_filter.py`)
- [ ] Ambil kalender ekonomi
- [ ] Blackout 15 menit sebelum, 30 menit sesudah event high-impact
- [ ] **Jika sumber kalender gagal → default ke tidak trading** (fail-safe)

**E. Order manager** (`src/execution/order_manager.py`)
- [ ] Kirim order **beserta SL/TP sekaligus** (bukan dua langkah)
- [ ] Verifikasi order benar-benar tereksekusi
- [ ] Trailing stop, partial close
- [ ] **Rekonsiliasi:** bandingkan posisi sistem vs posisi aktual di MT5

**F. Logging** (`src/monitoring/logger.py`)
- [ ] Log terstruktur (JSON)
- [ ] Catat setiap keputusan **beserta alasannya**
- [ ] Audit trail lengkap

### Deliverable
- Risk manager dengan semua limit aktif
- Order manager teruji
- Sistem logging lengkap

### Kriteria lulus
- [ ] Unit test untuk setiap limit — pastikan benar-benar memblokir
- [ ] Uji simulasi: coba langgar tiap limit, pastikan ditolak
- [ ] File `STOP` terbukti menghentikan entry
- [ ] Rekonsiliasi mendeteksi ketidakcocokan posisi
- [ ] Order terkirim lengkap dengan SL/TP

### Jika gagal
Jangan lanjut. Bug di layer ini yang menghabiskan akun, bukan strategi yang
kurang bagus.

---

## TAHAP 7 — Dashboard (1 minggu)

### Tujuan
Membuat sistem bisa dipantau dan diaudit.

### Kenapa tahap ini ada
Sistem yang tidak bisa dipantau tidak bisa dipercaya. Klien perlu melihat
apa yang terjadi, dan Anda perlu bisa mendiagnosis saat ada yang aneh.

### Tugas

**A. Dashboard** (`src/monitoring/dashboard.py` — Streamlit)
- [ ] Status: koneksi, mode, kill switch
- [ ] Equity curve real-time
- [ ] Posisi terbuka
- [ ] Riwayat trade + statistik
- [ ] Sinyal terakhir + alasan diambil/ditolak
- [ ] **Penting: dashboard TIDAK memanggil `mt5.initialize()`** — baca dari
      file/database yang ditulis gateway

**B. Trade journal** (`src/monitoring/journal.py`)
- [ ] Simpan setiap trade ke database
- [ ] Screenshot chart saat entry (opsional, sangat membantu evaluasi)
- [ ] Analitik: performa per setup, per sesi, per jam

**C. Notifikasi** (opsional)
- [ ] Telegram bot: sinyal, eksekusi, alert
- [ ] Ringkasan harian

### Deliverable
- Dashboard berjalan
- Trade journal otomatis

### Kriteria lulus
- [ ] Dashboard menampilkan data akurat
- [ ] Tidak ada konflik koneksi MT5
- [ ] Semua trade tercatat lengkap

---

## TAHAP 8 — Demo Forward Test (6 minggu) — WAJIB

### Tujuan
Membuktikan sistem bekerja di kondisi pasar nyata, bukan hanya di data
historis.

### Kenapa tahap ini ada
Ini tahap yang paling sering dipangkas karena tidak sabar — dan paling
sering menjadi penyebab kegagalan.

Backtest tidak bisa mereproduksi: slippage nyata, perilaku broker, requote,
koneksi terputus, spread saat kondisi ekstrem. Enam minggu bukan buffer
waktu — itu kebutuhan statistik untuk mengumpulkan cukup trade agar hasilnya
bermakna.

### Tugas
- [ ] Jalankan sistem di akun **demo** dengan kondisi live penuh
- [ ] Mode ADVISOR dulu 2 minggu (sinyal saja, eksekusi manual)
- [ ] Mode EXECUTOR 4 minggu (otomatis penuh)
- [ ] Catat **setiap** sinyal, termasuk yang ditolak dan alasannya
- [ ] Bandingkan mingguan: hasil live vs ekspektasi backtest

**Yang dipantau khusus:**

| Aspek | Yang dicari |
|---|---|
| Slippage aktual | Sesuai asumsi backtest? |
| Spread aktual | Sesuai data historis? |
| Order gagal | Berapa sering? Kenapa? |
| Uptime | Ada disconnect? Berapa lama? |
| Perbedaan performa | Deviasi dari backtest berapa persen? |

### Deliverable
- Log lengkap 6 minggu
- Laporan perbandingan live vs backtest
- Daftar bug/masalah yang ditemukan

### Kriteria lulus (GERBANG TERAKHIR SEBELUM UANG NYATA)
- [ ] Minimal 60 trade tercatat
- [ ] Profit Factor > 1,3 di kondisi live
- [ ] **Deviasi dari backtest < 30%**
- [ ] Tidak ada pelanggaran risk limit
- [ ] Uptime > 95% saat jam trading
- [ ] Tidak ada bug kritis di 2 minggu terakhir

### Jika gagal

| Gejala | Kemungkinan penyebab | Tindakan |
|---|---|---|
| Live jauh lebih buruk dari backtest | Lookahead bias | Audit ulang seluruh fitur |
| Slippage lebih besar dari asumsi | Model biaya terlalu optimis | Perbarui backtest, evaluasi ulang |
| Banyak order gagal | Masalah teknis/broker | Perbaiki sebelum lanjut |
| Sering kena limit harian | Sistem terlalu agresif | Turunkan risiko |

**Deviasi > 40% berarti ada yang salah mendasar.** Kembali ke Tahap 3–5,
jangan lanjut ke live.

---

## TAHAP 9 — Live Bertahap (3 bulan+)

### Tujuan
Menjalankan sistem dengan uang nyata, dinaikkan bertahap sesuai bukti.

### Kenapa bertahap
Bulan pertama adalah kesempatan terakhir mendeteksi masalah selagi biayanya
masih murah. Langsung masuk risiko 3% berarti membuang kesempatan itu.

### Tugas

**Bulan 1 — Verifikasi (risiko 1%)**
- [ ] Deposit Rp 800.000 ke akun cent **real**
- [ ] Risiko **1%** per trade — bukan 3%
- [ ] Tujuan: verifikasi eksekusi nyata, bukan profit
- [ ] Bandingkan dengan hasil demo

**Bulan 2 — Peningkatan (risiko 2%)**
- [ ] Naikkan hanya jika bulan 1 sesuai ekspektasi
- [ ] Terus pantau deviasi

**Bulan 3+ — Penuh (risiko 3%)**
- [ ] Risiko penuh jika 2 bulan sebelumnya konsisten
- [ ] Compounding aktif

**Rutinitas berkelanjutan:**

| Frekuensi | Kegiatan |
|---|---|
| Harian | Cek log, pastikan sistem sehat |
| Mingguan | Review performa, bandingkan dengan ekspektasi |
| Bulanan | Evaluasi menyeluruh, pertimbangkan retraining |
| Saat DD > 15% | De-risking otomatis aktif, evaluasi manual |
| Saat modal 2x | **Tarik modal awal** (lihat dokumen 01, Bagian 2.5) |

### Kriteria sukses (setelah 3 bulan)
- [ ] Profit Factor > 1,3
- [ ] Max Drawdown < 25%
- [ ] Deviasi dari backtest < 30%
- [ ] Tidak ada pelanggaran risk limit
- [ ] Sistem berjalan tanpa intervensi manual

---

## Ringkasan Gerbang Penting

Empat titik di mana proyek boleh dihentikan atau diubah arah:

| Gerbang | Di tahap | Syarat lulus | Jika gagal |
|---|---|---|---|
| **1. Broker layak** | 0 | Sizing [OK], spread < 25 | Ganti broker |
| **2. Rule punya edge** | 2 | Expectancy positif | Iterasi strategi, jangan ke ML |
| **3. ML memberi nilai** | 5 | Unggul di 8/10 fold | Pakai rule saja |
| **4. Live sesuai demo** | 8 | Deviasi < 30% | Kembali ke Tahap 3–5 |

Gerbang ini bukan formalitas. Melewatinya tanpa lulus berarti membangun
tahap berikutnya di atas fondasi yang belum terbukti — dan biaya
memperbaikinya naik berlipat di setiap tahap.

---

## Estimasi Dampak Optimasi

Menjawab "berapa besar profit bisa dimaksimalkan" — perkiraan kumulatif:

| Tahap | Optimasi | Expectancy |
|---|---|---|
| 3 | Baseline (rule + biaya realistis) | +0,15R |
| 4A | Filter spread & jam optimal | +0,20R |
| 4B | Manajemen posisi (trailing, partial) | +0,26R |
| 4C | Seleksi setup ketat | +0,31R |
| 5 | ML meta-labeling | **+0,40R** |

**Total peningkatan: sekitar 2,5x lipat dari baseline.**

Angka-angka ini estimasi berdasar rentang yang wajar, bukan janji. Nilai
sebenarnya baru diketahui setelah Tahap 3–4 dijalankan dengan data aktual.

Yang ingin ditunjukkan di sini: **memaksimalkan profit itu pekerjaan yang
konkret dan terukur.** Bukan mencari sistem ajaib, melainkan memperbaiki
banyak hal kecil yang efeknya berlipat.

---

## Langkah Pertama Anda

Satu hal yang memblokir semuanya:

**Pilih broker dengan akun cent untuk XAUUSD.**

Setelah itu:
1. Buka akun demo di broker tersebut
2. Login MT5, aktifkan algo trading
3. Jalankan `python scripts/phase0_probe.py`
4. Simpan outputnya

Script akan langsung memberi tahu apakah broker tersebut layak — bagian
sizing menampilkan [OK] atau [BAHAYA]. Kalau [BAHAYA], ganti broker sebelum
menulis satu baris kode pun.
