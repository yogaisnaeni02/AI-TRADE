# Sistem Siap — Panduan Memulai

**Status:** Sistem lengkap, teruji, menunggu deposit akun demo.

---

## Langkah 1: Siapkan Akun Demo

Akun demo lama (463942909) habis kena stop out — bukan dari sistem ini,
melainkan dari 5 posisi manual tanpa stop loss.

Pilih salah satu:

**A. Reset saldo akun lama**
Dashboard Exness → akun 463942909 → tombol **"Tetapkan Saldo"** → isi nominal

**B. Buat akun demo baru**
Dashboard Exness → buat akun demo baru → login di MT5
(File → Login to Trade Account)

### Berapa yang perlu didepositkan

| Deposit | Risiko per trade | Catatan |
|---|---|---|
| Rp 3.700.000 | 1,89% | **Minimum** — bot menolak di bawah ini |
| Rp 5.000.000 | 1,40% | Lebih baik |
| **Rp 7.000.000** | **1,00%** | **Optimal** — target risiko tercapai presisi |
| Rp 10.000.000 | 0,70% | Konservatif |

Batasannya berasal dari lot minimum broker (0,01) yang tidak bisa dibagi
lebih kecil. Detail di `docs/15-MANAJEMEN-RISIKO-YANG-BENAR.md`.

**Saran: deposit Rp 7 juta** agar risiko 1% tercapai tepat.

---

## Langkah 2: Aktifkan Algo Trading

Di MetaTrader 5:

```
Tools → Options → Expert Advisors → centang "Allow algorithmic trading" → OK
```

Pastikan simbol **XAUUSDm** ada di Market Watch.

---

## Langkah 3: Cek Kesiapan

```bash
python run_bot.py --check
```

Yang harus terlihat:

```
Tipe          : DEMO
Equity        : Rp 7,000,000        <- di atas minimum
Algo trading  : AKTIF
Kill switch   : tidak aktif
```

Jika `Algo trading: TIDAK AKTIF`, ulangi Langkah 2.

---

## Langkah 4: Jalankan

### Mode aman (disarankan untuk minggu pertama)

```bash
python run_bot.py --advisor
```

Bot menganalisis dan menampilkan sinyal, **tanpa membuka posisi**. Anda bisa
melihat kualitas sinyalnya dulu sebelum membiarkannya eksekusi sendiri.

### Mode otomatis penuh

```bash
python run_bot.py
```

Bot membuka dan menutup posisi sendiri.

### Dashboard (jendela terpisah)

```bash
streamlit run src/monitoring/dashboard.py
```

Buka http://localhost:8501 — menampilkan equity, posisi, drawdown, log, dan
tombol STOP.

---

## Kill Switch

```bash
echo stop > STOP      # hentikan entry baru
rm STOP               # aktifkan lagi
```

Posisi yang sudah terbuka tetap dikelola sampai tertutup. Untuk berhenti
total: **Ctrl+C** di terminal bot.

---

## Konfigurasi Aktif

| Parameter | Nilai | Dasar |
|---|---|---|
| Setup | `momentum_fib` | Momentum + Fibonacci + tren HTF |
| SL / TP | 400 / 1.200 pip | **RR 1:3** |
| Break-even | 2,0R (~800 pip) | Proteksi termurah (biaya −0,003R) |
| Trailing | nonaktif | Terbukti memotong pemenang |
| Timeout | 4 jam | Timeout cepat merugikan |
| Risiko | 1% per trade | DD 25% vs 62% pada risiko 3% |
| Sesi | london_ny, ny_afternoon, rollover | Berdasar uji per sesi |
| Mode | EXECUTOR | Auto-trading |

### Batas otomatis

| Kondisi | Aksi |
|---|---|
| Equity < Rp 3,7 juta | Tolak semua entry |
| Loss harian ≥ 4% | Stop sisa hari |
| Loss mingguan ≥ 8% | Stop sisa minggu |
| 3 loss beruntun | Stop sisa hari |
| 6 trade/hari | Stop sisa hari |
| Spread > 400 pts | Tolak entry |
| Drawdown 10% | Risiko turun ke 0,75% |
| Drawdown 15% | Risiko turun ke 0,50% |
| **Drawdown 20%** | **SISTEM BERHENTI TOTAL** |

---

## Yang Perlu Diketahui Sebelum Menjalankan

### Strategi belum lolos validasi penuh

Dari 11 konfigurasi yang diuji, yang terbaik mencapai **4 dari 5 fold
walk-forward positif** dengan expectancy tipis (+0,016R). Belum memenuhi
seluruh kriteria kelulusan (butuh 200+ trade, PF > 1,2).

**Karena itu: jalankan di demo dulu.** Tujuannya mengumpulkan data live,
bukan menghasilkan uang.

### Ekspektasi realistis

| Metrik | Perkiraan |
|---|---|
| Frekuensi | 1–3 trade per hari |
| Winrate | 26–40% |
| Loss beruntun | 10–15 kali (normal pada winrate ini) |
| Drawdown | Bisa mencapai 25% |

Rentetan 10 kekalahan beruntun akan terjadi dan itu **normal** untuk strategi
RR 1:3. Yang penting bukan menghindarinya, melainkan memastikan ukuran risiko
cukup kecil untuk menahannya.

### Kapan naik ke akun real

Setelah forward test demo menunjukkan:
- Minimal 60 trade tercatat
- Profit Factor > 1,3
- Deviasi dari backtest < 30%
- Tidak ada pelanggaran risk limit

Detail di `docs/03-ROADMAP-DETAIL.md` Tahap 8.

---

## Setelah Berjalan

### Memeriksa hasil

```bash
type logs\bot_20260909.log       # log hari ini
type logs\snapshot.json          # status terkini
type logs\trades.csv             # riwayat trade
```

Atau lewat dashboard yang menyegarkan otomatis tiap 30 detik.

### Evaluasi mingguan

```bash
python -m src.monitoring.journal
```

Menampilkan winrate, profit factor, dan P/L kumulatif dari riwayat MT5.

---

## Dokumentasi

| Dokumen | Isi |
|---|---|
| `CARA-PAKAI.md` | Panduan operasional lengkap |
| `docs/07-STATUS-SISTEM.md` | Status seluruh komponen |
| `docs/12-DIAGNOSTIK-KEKURANGAN.md` | Kelemahan sistem yang ditemukan |
| `docs/15-MANAJEMEN-RISIKO-YANG-BENAR.md` | Mengapa risiko 1%, bukan 3% |
| `docs/broker-specs.md` | Spesifikasi broker terverifikasi |

---

## Ringkasan Komponen

| Komponen | Status |
|---|---|
| Gateway MT5 (koneksi tunggal, auto-reconnect) | Terverifikasi |
| Downloader bertahap (tembus batas 50k bar) | Terverifikasi |
| Validator kualitas data | Terverifikasi |
| Resampler M1→M5 (99,995% cocok) | Terverifikasi |
| 88 fitur (MACD, Fibonacci, momentum, dll.) | Selesai |
| Rule engine (4 setup) | Selesai |
| Backtester (biaya realistis, anti-lookahead) | Terverifikasi |
| Risk manager (semua guardrail) | **Teruji satu per satu** |
| Order manager | **Order terkirim di akun nyata** |
| Trading bot (loop EXECUTOR) | Terverifikasi |
| Dashboard + journal + kill switch | Selesai |
| Kerangka ML (labeling + walk-forward) | Selesai |

Kabari saya setelah deposit — saya bantu verifikasi dan jalankan.
