# Cara Menjalankan Sistem

Panduan operasional. Untuk latar belakang teknis, lihat folder `docs/`.

---

## Status Singkat

| Bagian | Status |
|---|---|
| Infrastruktur (data, eksekusi, risiko, dashboard) | **Selesai & teruji** |
| Strategi | **Marginal** — belum lolos gate penuh |

Sistem siap dijalankan dan akan trading otomatis. Strategi saat ini
(`momentum_fib`) menunjukkan expectancy positif tipis (+0,016R) dengan
**4 dari 5 fold walk-forward positif** — jauh lebih baik dari versi awal
(−0,300R), tetapi belum memenuhi seluruh kriteria kelulusan.

Jalankan di **akun demo** untuk mengumpulkan data live. Jangan diarahkan ke
akun real sampai forward test menunjukkan hasil konsisten.

### Konfigurasi aktif

| Parameter | Nilai | Dasar |
|---|---|---|
| Setup | `momentum_fib` | Momentum + Fibonacci + tren HTF |
| SL | 400 pip | Uji entry acak: optimal 300-400 pip |
| TP | 1.200 pip | RR 1:3 |
| Break-even | 1,5R | Uji varian manajemen posisi |
| Trailing | ATR x 2,5 | Uji varian |
| Timeout | 48 bar (4 jam) | Timeout cepat terbukti merugikan |
| Sesi | london_ny + ny_afternoon | NY sore terbaik (+0,278R) |
| Risiko | 3% per trade | Peluang bangkrut ~0% |
| Frekuensi | ~2,7 sinyal/hari | Risk limit menyaring jadi ~1-2 trade |

---

## Persiapan (sekali saja)

1. **Buka MetaTrader 5** dan login ke akun demo
2. **Aktifkan algo trading:**
   Tools → Options → Expert Advisors → centang **"Allow algorithmic trading"** → OK
3. Pastikan simbol **XAUUSDm** ada di Market Watch

MT5 harus tetap terbuka selama bot berjalan. Bot berkomunikasi dengan terminal,
bukan langsung ke broker.

---

## Perintah Utama

Jalankan dari folder `D:\Telkom University\PROJECT CUAN`.

### 1. Cek kesiapan sistem

```bash
python run_bot.py --check
```

Menampilkan status koneksi, equity, spread, dan mode. **Selalu jalankan ini
dulu** sebelum menjalankan bot.

Contoh keluaran sehat:
```
Akun          : 463942909 @ Exness-MT5Trial17
Tipe          : DEMO
Equity        : Rp 5,146,662
Simbol        : XAUUSDm (spread 260 pts)
Algo trading  : AKTIF
Mode          : EXECUTOR
Kill switch   : tidak aktif
```

Jika `Algo trading: TIDAK AKTIF` — ulangi langkah 2 di Persiapan.

### 2. Mode sinyal saja (aman, disarankan untuk mulai)

```bash
python run_bot.py --advisor
```

Bot menganalisis dan menampilkan sinyal, **tanpa membuka posisi**. Anda yang
memutuskan eksekusi manual. Cocok untuk melihat kualitas sinyal lebih dulu.

### 3. Mode otomatis penuh

```bash
python run_bot.py
```

Bot membuka dan menutup posisi sendiri, mengelola break-even dan trailing stop.
Biarkan jendela terminal terbuka. Hentikan dengan **Ctrl+C**.

### 4. Dashboard

```bash
streamlit run src/monitoring/dashboard.py
```

Buka di browser (biasanya http://localhost:8501). Menampilkan equity, posisi
terbuka, drawdown, log, dan tombol STOP.

Dashboard bisa dibuka **bersamaan** dengan bot — ia membaca file snapshot,
tidak membuka koneksi MT5 sendiri.

---

## Kill Switch

Cara tercepat menghentikan bot membuka posisi baru:

```bash
echo stop > STOP
```

Bot langsung berhenti entry. **Posisi yang sudah terbuka tetap dikelola**
(break-even & trailing) sampai tertutup — ini disengaja, agar posisi tidak
ditinggalkan tanpa pengawasan.

Mengaktifkan kembali:

```bash
rm STOP
```

Tombol STOP juga tersedia di dashboard.

**Untuk menghentikan total:** tekan Ctrl+C di terminal bot.

---

## Yang Terjadi Saat Bot Berjalan

Setiap 10 detik bot memeriksa apakah ada bar M5 baru yang selesai. Jika ada:

```
1. Ambil data M5 + H1 + H4 dari MT5
2. Hitung indikator, struktur market, sesi
3. Cari sinyal (rule engine)
4. Periksa risk manager  <- gerbang tunggal
5. Kirim order jika lolos
6. Kelola posisi terbuka (break-even, trailing)
```

Semua tercatat di `logs/bot_YYYYMMDD.log`.

### Kapan bot trading

Hanya di sesi **London open** (14:00–17:00 WIB) dan **London–NY overlap**
(19:30–23:00 WIB). Di luar itu bot tetap berjalan tapi tidak mencari sinyal.

Jumat setelah 21:00 WIB tidak ada entry baru (risiko gap akhir pekan).

---

## Pengaman yang Aktif Otomatis

Bot akan **menolak** membuka posisi bila:

| Kondisi | Aksi |
|---|---|
| File STOP ada | Tolak entry |
| Sudah ada 1 posisi terbuka | Tolak (maksimal 1 posisi) |
| Spread > 400 points | Tolak |
| Sudah 6 trade hari ini | Tolak sisa hari |
| 3 loss beruntun | Tolak sisa hari |
| Loss harian ≥ 9% | Tolak sisa hari |
| Loss mingguan ≥ 15% | Tolak sisa minggu |
| RR di bawah minimum | Tolak |
| Di luar sesi trading | Tolak |

Dan menurunkan risiko sendiri saat rugi:

| Drawdown | Risiko per trade |
|---|---|
| 0–15% | 3,0% |
| 15–20% | 1,5% |
| 20–25% | 1,0% |
| ≥ 25% | **SISTEM BERHENTI TOTAL** |

Berhenti total memerlukan restart manual — disengaja, agar ada jeda untuk
mengevaluasi sebelum melanjutkan.

---

## Memeriksa Hasil

```bash
# Log hari ini
type logs\bot_20260909.log

# Status terkini (JSON)
type logs\snapshot.json
```

Atau lewat dashboard, yang menyegarkan otomatis tiap 30 detik.

---

## Menjalankan Ulang Backtest

Untuk menguji perubahan strategi:

```bash
python -m src.data.downloader        # perbarui data dari MT5
python -m src.data.validator         # cek kualitas data
python -m src.features.pipeline      # bangun ulang fitur
```

Lalu jalankan backtest lewat Python. Contoh:

```python
import pandas as pd
from src.strategy.setups import RuleEngine
from backtest.engine import Backtester
from backtest.metrics import compute, print_report

df = pd.read_parquet('data/processed/XAUUSDm_M5_features.parquet')
eng = RuleEngine()
bt = Backtester()

sig = eng.generate(df, min_score=5)
sub = sig[(sig.setup == 'london_sweep') & (sig.score <= 6)]

trades, curve = bt.run(df, sub, initial_equity=3_700_000,
                       breakeven_at_r=1.5, trail_atr_mult=2.5)
print_report(compute(trades, initial_equity=3_700_000))
```

---

## Masalah Umum

| Gejala | Penyebab & solusi |
|---|---|
| `Authorization failed` | MT5 belum login. Buka MT5, login. |
| `Algo trading TIDAK AKTIF` | Tools → Options → Expert Advisors → centang |
| `Simbol tidak tersedia` | Tambahkan XAUUSDm ke Market Watch |
| Bot jalan tapi tidak ada sinyal | Normal. Di luar sesi London/NY memang tidak trading |
| `Spesifikasi broker berubah` | Jalankan `python scripts/phase0_probe.py`, perbarui `config/settings.yaml` |
| Dashboard kosong | Bot belum pernah jalan; snapshot belum dibuat |

---

## Struktur Folder

```
PROJECT CUAN/
├── run_bot.py              <- jalankan bot dari sini
├── STOP                    <- buat file ini untuk kill switch
├── config/
│   ├── settings.yaml       <- parameter sistem & broker
│   └── risk_limits.yaml    <- batasan risiko (terpisah, disengaja)
├── src/
│   ├── data/               gateway, downloader, validator, resampler
│   ├── features/           indikator, pipeline fitur
│   ├── strategy/           struktur market, sesi, rule engine
│   ├── risk/               risk manager & circuit breaker
│   ├── execution/          order manager, trading bot
│   └── monitoring/         dashboard
├── backtest/               engine & metrik
├── data/                   data historis (raw & processed)
├── logs/                   log harian & snapshot
└── docs/                   dokumentasi & analisis
```

---

## Peringatan Penting

Strategi saat ini **belum menguntungkan**. Buktinya ada tiga:

- Out-of-sample: +0,232R (in-sample) menjadi **−0,225R** (data baru)
- Winrate 23,5% — **di bawah entry acak** (24,7%)
- Skor tinggi berkinerja lebih buruk daripada skor rendah

Menjalankan mode EXECUTOR sekarang berarti bot akan trading otomatis dengan
strategi yang rugi. Di akun demo ini berguna untuk memverifikasi sistem
bekerja; di akun real ini akan menghabiskan modal.

Untuk mengubah ke mode aman, edit `config/settings.yaml`:

```yaml
mode: ADVISOR      # sinyal saja, tidak eksekusi
```

Detail lengkap ada di `docs/07-STATUS-SISTEM.md`.
