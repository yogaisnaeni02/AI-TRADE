# Arsitektur: Bot (Backend) vs Dashboard (Monitoring)

**Tanggal:** 9 September 2026
**Pertanyaan:** "Streamlit kan tidak realtime. Itu untuk dashboard monitoring
saja ya? Yang auto open/close trade itu di backend?"

**Jawaban: benar sepenuhnya.**

---

## 1. Dua Proses Terpisah

```
┌──────────────────────────────────────────────────────────┐
│  MetaTrader 5 Terminal                                   │
│  - koneksi broker, harga live, eksekusi order            │
└────────────────────────┬─────────────────────────────────┘
                         │ API MetaTrader5 (Python)
                         │ SATU koneksi saja
┌────────────────────────▼─────────────────────────────────┐
│  BOT — run_bot.py                    [YANG TRADING]      │
│                                                          │
│  Loop tiap 10 detik:                                     │
│    1. Ambil data M5/H1/H4 dari MT5                       │
│    2. Hitung indikator & sinyal                          │
│    3. Cek risk manager                                   │
│    4. KIRIM ORDER  <- di sini trading terjadi            │
│    5. Kelola posisi (break-even, timeout)                │
│    6. Tulis snapshot.json                                │
└────────────────────────┬─────────────────────────────────┘
                         │ tulis file
                         ▼
              logs/snapshot.json
              logs/trades.csv
              logs/bot_YYYYMMDD.log
                         │ baca file
┌────────────────────────▼─────────────────────────────────┐
│  DASHBOARD — streamlit                [HANYA MELIHAT]    │
│                                                          │
│  - Baca snapshot.json tiap 30 detik                      │
│  - Tampilkan equity, posisi, drawdown, log               │
│  - Tombol STOP (membuat file STOP)                       │
│                                                          │
│  TIDAK menyentuh MT5. TIDAK bisa membuka posisi.         │
└──────────────────────────────────────────────────────────┘
```

---

## 2. Pembagian Peran

| | Bot (`run_bot.py`) | Dashboard (Streamlit) |
|---|---|---|
| Koneksi ke MT5 | **Ya** | Tidak |
| Membuka posisi | **Ya** | Tidak |
| Menutup posisi | **Ya** | Tidak |
| Mengelola SL/TP | **Ya** | Tidak |
| Menampilkan status | Log teks | Grafik & tabel |
| Kalau ditutup | **Trading berhenti** | Trading tetap jalan |
| Wajib berjalan | **Ya** | Tidak |

**Dashboard opsional.** Bot bekerja penuh tanpanya.

---

## 3. Mengapa Dipisah

Bukan pilihan gaya — ini keharusan teknis.

Paket `MetaTrader5` hanya mengizinkan **satu koneksi per terminal**. Bila
dashboard ikut memanggil `mt5.initialize()`, keduanya berebut koneksi dan
salah satu gagal dengan cara yang sulit didiagnosis: order bisa tidak
terkirim, atau data yang terbaca tidak lengkap.

Karena itu dashboard sengaja dibuat **hanya membaca file**:

```python
# src/monitoring/dashboard.py
def read_snapshot() -> dict:
    with open(SNAPSHOT, encoding="utf-8") as f:
        return json.load(f)
```

Tidak ada satu pun panggilan MT5 di dalamnya.

Masalah ini sudah terbukti nyata: sebelumnya terdeteksi dua bot berjalan
bersamaan (mode ADVISOR dan EXECUTOR). Kini dicegah oleh lock file
(`logs/bot.lock`).

---

## 4. Soal "Tidak Realtime"

Benar, dashboard menyegarkan tiap **30 detik**. Tetapi itu tidak menghambat
apa pun:

| Komponen | Kecepatan | Alasan |
|---|---|---|
| Bot memeriksa pasar | tiap 10 detik | Cukup — bar M5 baru muncul tiap 5 menit |
| Bot menulis snapshot | tiap siklus | ~10 detik |
| Dashboard membaca | tiap 30 detik | Cukup untuk mata manusia |

Keputusan trading terjadi di bot, dan bot bekerja pada resolusi bar M5.
Menyegarkan dashboard lebih cepat tidak mengubah kecepatan trading sama
sekali — hanya menambah beban baca file.

---

## 5. Cara Menjalankan

### Bot saja (cukup untuk trading)

```
3-JALANKAN-OTOMATIS.bat
```

Jendela hitam harus **tetap terbuka**. Menutupnya menghentikan trading.

### Bot + Dashboard

```
Jendela 1:  3-JALANKAN-OTOMATIS.bat    <- biarkan terbuka
Jendela 2:  4-DASHBOARD.bat            <- boleh ditutup kapan saja
```

Keduanya aman berjalan bersamaan karena dashboard tidak menyentuh MT5.

---

## 6. Cara Memastikan Bot Hidup

### A. Jendela bot

Ada baris log baru muncul, termasuk heartbeat tiap jam:

```
[status] 12:30 WIB | sesi asia — di luar jam trading, menunggu
```

### B. Umur snapshot

```bash
python -c "import json;from datetime import datetime;s=json.load(open('logs/snapshot.json'));print((datetime.now()-datetime.fromisoformat(s['timestamp'])).total_seconds(),'detik lalu')"
```

Di bawah 60 detik berarti bot aktif. Di atas beberapa menit berarti bot
berhenti.

### C. Dashboard

Indikator di pojok kiri atas:

| Tampilan | Arti |
|---|---|
| **Bot aktif** (hijau) | Snapshot < 2 menit |
| **Diam N mnt** (kuning) | Snapshot basi — bot kemungkinan berhenti |
| **KILL SWITCH AKTIF** (merah) | File STOP ada |

### D. Daftar proses

```bash
wmic process where "name='python.exe'" get ProcessId,CommandLine
```

Harus ada **satu** `run_bot.py`. Bila ada dua, itu masalah — hentikan salah
satu.

---

## 7. Alur Saat Ada Sinyal

```
19:32:05  Bot: bar M5 baru selesai
19:32:05  Bot: hitung indikator -> sinyal BUY ditemukan
19:32:05  Bot: risk manager -> IZIN, lot 0.01, risiko 1%
19:32:06  Bot: kirim order ke MT5
19:32:06  MT5: order tereksekusi, ticket 2517890123
19:32:06  Bot: tulis snapshot.json
19:32:30  Dashboard: baca snapshot -> tampilkan posisi baru
```

Dashboard mengetahui posisi baru sekitar 24 detik setelah order terkirim.
Keterlambatan itu tidak berpengaruh pada trading — order sudah tereksekusi
sejak detik pertama.

---

## 8. Ringkasan

| Pertanyaan | Jawaban |
|---|---|
| Streamlit untuk monitoring saja? | **Ya** |
| Yang trading itu backend? | **Ya** — `run_bot.py` |
| Dashboard bisa buka posisi? | **Tidak** — hanya membaca file |
| Dashboard wajib dijalankan? | **Tidak** — opsional |
| Kalau dashboard ditutup? | Trading tetap jalan |
| Kalau jendela bot ditutup? | **Trading berhenti** |
| Refresh 30 detik menghambat? | Tidak — keputusan ada di bot |
| Kenapa dipisah? | API MT5 hanya izinkan satu koneksi |
