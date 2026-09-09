# Status Sistem — Ringkasan Akhir

**Tanggal:** 9 September 2026
**Akun demo:** 463942909 @ Exness-MT5Trial17
**Equity demo:** Rp 5.146.662
**Mode:** EXECUTOR (auto-trading)

---

## 1. Apa yang Sudah Jadi

Seluruh infrastruktur teknis selesai dan terverifikasi berjalan.

| Komponen | File | Status |
|---|---|---|
| Gateway MT5 | `src/data/mt5_gateway.py` | Terverifikasi |
| Downloader bertahap | `src/data/downloader.py` | Terverifikasi |
| Validator data | `src/data/validator.py` | Terverifikasi |
| Resampler M1→M5 | `src/data/resampler.py` | 99,995% cocok |
| Indikator | `src/features/indicators.py` | Selesai |
| Pipeline fitur | `src/features/pipeline.py` | Selesai |
| Struktur market | `src/strategy/structure.py` | Selesai |
| Sesi + Asia range | `src/strategy/sessions.py` | Selesai |
| Rule engine | `src/strategy/setups.py` | Selesai |
| Backtester | `backtest/engine.py` | Selesai |
| Metrik | `backtest/metrics.py` | Selesai |
| **Risk manager** | `src/risk/manager.py` | **Semua guardrail teruji** |
| **Order manager** | `src/execution/order_manager.py` | **Order terverifikasi** |
| **Trading bot** | `src/execution/bot.py` | Terhubung, siap |
| Dashboard | `src/monitoring/dashboard.py` | Selesai |
| Runner | `run_bot.py` | Terverifikasi |

### Hasil uji eksekusi nyata (demo)

```
Order BUY 0,02 lot        -> BERHASIL, ticket 2517490337
SL & TP terpasang otomatis -> [OK] terverifikasi
Geser SL searah profit     -> OK
Coba lebarkan SL           -> DITOLAK (proteksi bekerja)
Tutup posisi               -> OK
```

### Hasil uji guardrail

| Skenario | Hasil |
|---|---|
| Kondisi normal | IZIN, lot 0,01, risiko 3,07% |
| File STOP ada | TOLAK |
| Sudah ada posisi terbuka | TOLAK |
| Spread melebihi batas | TOLAK |
| Blackout berita | TOLAK |
| RR di bawah minimum | TOLAK |
| 3 loss beruntun | TOLAK — stop sisa hari |
| Drawdown 16% | Risiko turun otomatis 3% → 1,5% |
| Drawdown 21% | Risiko turun otomatis → 1,0% |
| Drawdown 26% | SISTEM DIHENTIKAN |
| 3 order gagal beruntun | SISTEM DIHENTIKAN |

---

## 2. Apa yang Belum Selesai

**Strateginya belum punya edge.** Ini satu-satunya hal yang menghalangi
sistem menghasilkan uang, dan ia dibuktikan tiga cara berbeda:

### Bukti 1 — Uji out-of-sample

```
In-sample  (Apr 2025 - Mar 2026) : +0,232R, PF 1,36
Out-sample (Mar 2026 - Aug 2026) : -0,225R, PF 0,65
```

Yang bagus di periode tuning justru rugi di data baru. Ini curve fitting.

### Bukti 2 — Perbandingan dengan entry acak

Pada RR 1:3 dengan SL 400 pip:

```
Entry acak            : winrate 24,7%
Setup terbaik kita    : winrate 23,5%
```

Rule engine berkinerja **di bawah** entry acak.

### Bukti 3 — Skor tinggi berkinerja lebih buruk

```
Skor 6 : +0,361R
Skor 7 : -0,121R
Skor 8 : -0,219R
```

Sistem skoring bekerja terbalik — filter "kualitas" justru membuang peluang
yang layak. Ini tanda kriteria yang dipakai tidak berkorelasi dengan hasil.

**Gate Tahap 2 tidak lulus.** Sesuai roadmap, ML tidak boleh ditambahkan
sebelum rule engine punya edge — ML menyaring keunggulan yang ada, tidak
menciptakannya.

---

## 3. Temuan Terpenting: Ukuran Celah

Diukur dengan entry acak pada berbagai kombinasi SL/TP:

```
RR 1:3, SL 400 pip
  Winrate entry acak  : 24,7%
  Breakeven winrate   : 25,4%
  Selisih             : 0,7 poin persentase
```

**Pasar XAUUSD hampir efisien.** Spread 26 pip yang mendorongnya ke sisi rugi.

Ini pengukuran paling berguna dari seluruh proyek, karena mengubah target
abstrak menjadi angka konkret:

> **Strategi hanya perlu menaikkan winrate 1–2% di atas acak untuk profitabel.**

Bukan 20%. Bukan 10%. Satu sampai dua persen.

Itu target yang jelas, terukur, dan tidak mustahil — tetapi juga tidak
memberi ruang untuk sinyal yang asal-asalan.

---

## 4. Parameter yang Sudah Terkalibrasi

Ditemukan lewat pengukuran, bukan asumsi:

| Parameter | Nilai | Dasar |
|---|---|---|
| Simbol | `XAUUSDm` | Probe broker |
| Spread | 260 points = 26 pip | FIXED semua sesi |
| 1 pip | 10 points | `point` = 0,001 |
| Range bar M5 (median) | 379 pip | 100.000 bar |
| ATR M5 (median) | 424 pip | 100.000 bar |
| **SL optimal** | **300–500 pip** | Uji entry acak |
| SL 100 pip | Kena noise 98% | Terukur |
| SL 650 pip | Terlalu lebar | Terukur |
| Modal minimum XAUUSD | Rp 3.700.000 | Lot min 0,01 |
| Gerakan 15 menit (median) | 461 pip | Terukur |
| Manajemen posisi terbaik | BE 1,5R + trail ATR×2,5 | Uji varian |

---

## 5. Cara Menjalankan

### Persiapan
```bash
# MT5 harus terbuka dan login
# Tools > Options > Expert Advisors > "Allow algorithmic trading"
```

### Perintah

```bash
python run_bot.py --check      # cek koneksi & konfigurasi
python run_bot.py --advisor    # mode sinyal saja (tidak eksekusi)
python run_bot.py              # mode sesuai config (saat ini EXECUTOR)

streamlit run src/monitoring/dashboard.py    # dashboard
```

### Kill switch

```bash
# Hentikan entry baru (posisi terbuka tetap dikelola)
echo stop > STOP

# Aktifkan kembali
rm STOP
```

Tombol STOP juga tersedia di dashboard.

### Peringatan

Menjalankan `python run_bot.py` sekarang akan membuka posisi otomatis dengan
strategi yang **terbukti tidak punya edge** (−0,145R). Di akun demo ini aman
untuk mengamati perilaku sistem, tetapi jangan diarahkan ke akun real sebelum
Bagian 6 diselesaikan.

---

## 6. Langkah Berikutnya

Diurutkan berdasar potensi dampak:

### A. Entry presisi lewat M1 — pengungkit terbesar yang belum dipakai

SL 400–650 pip diperlukan karena entry ditentukan di **close bar M5** — titik
yang kasar. Bila entry ditentukan di M1 pada level yang lebih tepat (retest
FVG, order block, atau level sweep), SL bisa turun ke 200–300 pip tanpa
terkena noise.

Dampaknya berlipat: SL lebih sempit menaikkan RR untuk semua target, sekaligus
memungkinkan sizing lebih presisi. Data M1 sudah tersedia dan resampler sudah
terverifikasi.

### B. Setup alternatif

London Sweep terbukti tidak bekerja pada data ini. Kandidat lain yang belum
diuji:
- Order block retest dengan konfirmasi M1
- Breakout dengan konfirmasi volume
- Mean reversion di sesi Asia (range-bound)
- Momentum continuation setelah BOS

### C. Machine learning — pertimbangkan lebih awal dari rencana

Roadmap menempatkan ML setelah rule engine punya edge. Tetapi mengingat
celahnya hanya 0,7%, pola yang dibutuhkan mungkin terlalu halus untuk
ditangkap aturan manual. ML sebagai penyaring (meta-labeling) berpotensi
menemukannya.

Prasyaratnya tetap: validasi walk-forward yang ketat, dan hasilnya harus
konsisten di 8 dari 10 fold — bukan sekadar rata-rata bagus.

### D. Instrumen lain

EURUSD memiliki rasio ATR-terhadap-spread jauh lebih baik, sehingga celah
yang harus dilampaui lebih lebar. Seluruh kode sudah instrument-agnostic;
yang berubah hanya config dan kalibrasi setup.

---

## 7. Penilaian Jujur

**Yang berhasil:** infrastruktur lengkap, teruji, dan berjalan. Setiap
komponen dari pengambilan data sampai eksekusi order sudah diverifikasi
bekerja di akun nyata (demo). Guardrail terbukti memblokir setiap pelanggaran
yang diuji.

**Yang belum:** strategi yang menghasilkan uang.

Ini bukan kegagalan proyek — ini hasil yang wajar untuk tahap ini. Menemukan
edge yang bertahan out-of-sample adalah bagian tersulit dari algo trading, dan
umumnya butuh puluhan iterasi setup. Yang penting, sistem gerbang bertahap
bekerja sebagaimana dirancang: kelemahan strategi terungkap di backtest, bukan
setelah modal hilang di akun nyata.

Infrastruktur yang sudah ada membuat iterasi berikutnya jauh lebih cepat —
menguji setup baru sekarang hanya perlu menulis satu fungsi detektor, bukan
membangun ulang seluruh pipeline.
