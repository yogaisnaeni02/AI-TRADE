# Cara Menjalankan Sistem

Panduan langkah demi langkah. Tidak perlu paham coding.

---

## Alur Singkat

```
1. Buka MetaTrader 5, login          <- aplikasi MT5
2. Aktifkan algo trading             <- sekali saja
3. Klik 1-CEK.bat                    <- pastikan siap
4. Klik 3-JALANKAN-OTOMATIS.bat      <- bot mulai bekerja
5. Klik 4-DASHBOARD.bat              <- pantau (opsional)
```

MT5 harus **tetap terbuka** selama bot berjalan. Bot berbicara dengan
terminal MT5, bukan langsung ke broker.

---

## Langkah 1: Buka MetaTrader 5

Buka aplikasi MT5 seperti biasa, pastikan sudah login ke akun demo.

Cek pojok kanan bawah MT5 — harus ada angka kecepatan koneksi
(misalnya `25 ms`), bukan tulisan "No connection".

---

## Langkah 2: Aktifkan Algo Trading

**Cukup sekali saja**, pengaturan ini tersimpan.

```
Menu Tools  →  Options  →  tab Expert Advisors
    → centang "Allow algorithmic trading"
    → OK
```

Pastikan juga **XAUUSDm** ada di panel Market Watch. Jika belum:
klik kanan di Market Watch → Symbols → cari XAUUSDm → Show.

---

## Langkah 3: Jalankan File Batch

Buka folder `D:\Telkom University\PROJECT CUAN` di File Explorer.
Ada 5 file yang bisa diklik dua kali:

| File | Fungsi |
|---|---|
| **1-CEK.bat** | Cek kesiapan sistem — **jalankan ini dulu** |
| **2-JALANKAN-SINYAL.bat** | Mode aman: tampilkan sinyal, tidak buka posisi |
| **3-JALANKAN-OTOMATIS.bat** | Mode penuh: bot buka & tutup posisi sendiri |
| **4-DASHBOARD.bat** | Buka dashboard di browser |
| **STOP-BOT.bat** | Kill switch — hentikan entry baru |

### Klik dua kali `1-CEK.bat` dulu

Akan muncul jendela hitam (Command Prompt) berisi:

```
==========================================================
  Akun          : 463942909 @ Exness-MT5Trial17
  Tipe          : DEMO
  Equity        : Rp 7,000,000
  Simbol        : XAUUSDm (spread 260 pts)
  Algo trading  : AKTIF
  Mode          : EXECUTOR
  Kill switch   : tidak aktif
  Data          : 1500 bar, terakhir 2026-09-09 05:25:00
  Sesi saat ini : asia
  Posisi terbuka: 0
==========================================================
```

**Yang harus dipastikan:**

| Baris | Nilai yang benar |
|---|---|
| Tipe | **DEMO** |
| Equity | **minimal Rp 3.700.000** |
| Algo trading | **AKTIF** |
| Kill switch | tidak aktif |

Kalau `Equity: Rp 0` — belum deposit, lihat bagian bawah.
Kalau `Algo trading: TIDAK AKTIF` — ulangi Langkah 2.

---

## Langkah 4: Jalankan Bot

### Pilihan A — Mode Sinyal (disarankan minggu pertama)

Klik dua kali **`2-JALANKAN-SINYAL.bat`**

Bot menganalisis pasar dan menampilkan sinyal di layar, tetapi **tidak
membuka posisi**. Anda bisa melihat kualitas sinyalnya dulu.

### Pilihan B — Mode Otomatis Penuh

Klik dua kali **`3-JALANKAN-OTOMATIS.bat`**

Ada jeda 5 detik untuk membatalkan (Ctrl+C) jika ternyata bukan akun demo.
Setelah itu bot membuka dan menutup posisi sendiri.

**Jendela hitamnya harus dibiarkan terbuka.** Kalau ditutup, bot berhenti.

Tampilan saat berjalan:

```
[2026-09-09 15:20:35] ==========================================
[2026-09-09 15:20:35] BOT START - mode EXECUTOR
[2026-09-09 15:20:35] Akun 463942909 @ Exness-MT5Trial17 (DEMO)
[2026-09-09 15:20:35] Equity Rp 7,000,000 | simbol XAUUSDm
[2026-09-09 15:20:35] Setup: ('momentum_fib',) skor 5-99
[2026-09-09 15:20:35] ==========================================
```

Lalu diam menunggu sinyal. **Diam itu normal** — bot hanya trading di sesi
tertentu dan hanya saat kondisi terpenuhi (sekitar 1–3 kali per hari).

Saat ada sinyal:

```
[15:32:10] SINYAL BUY momentum_fib skor=7 | lot=0.01 risiko=1.00% | SL=4380.5 TP=4450.5
[15:32:11]   ORDER OK ticket=2517890123 @ 4400.285
```

---

## Langkah 5: Dashboard (Opsional)

Klik dua kali **`4-DASHBOARD.bat`**, lalu buka browser ke:

```
http://localhost:8501
```

Menampilkan equity, posisi terbuka, drawdown, log, riwayat trade, dan tombol
STOP. Menyegarkan otomatis tiap 30 detik.

Dashboard bisa dibuka **bersamaan** dengan bot — keduanya tidak bentrok.

---

## Menghentikan Bot

| Cara | Efek |
|---|---|
| Klik **`STOP-BOT.bat`** | Bot berhenti buka posisi baru, posisi terbuka tetap dikelola |
| Tekan **Ctrl+C** di jendela bot | Bot berhenti total |
| Tutup jendela bot | Bot berhenti total |
| Tombol STOP di dashboard | Sama dengan `STOP-BOT.bat` |

**Untuk mengaktifkan lagi setelah STOP-BOT:** hapus file bernama `STOP` di
folder project.

> Kill switch sengaja tidak menutup posisi yang sudah terbuka — agar posisi
> tidak ditinggalkan tanpa pengawasan. Break-even dan timeout tetap berjalan.

---

## Kapan Bot Trading

Bot hanya mencari sinyal di sesi tertentu (waktu WIB):

| Sesi | Waktu WIB |
|---|---|
| London–NY overlap | 19:30 – 23:00 |
| NY sore | 23:00 – 04:00 |
| Rollover | 04:00 – 06:00 |

Di luar jam itu bot tetap berjalan tetapi tidak membuka posisi. Jumat setelah
21:00 WIB tidak ada entry baru (risiko gap akhir pekan).

**Jadi kalau menjalankan bot siang hari, wajar tidak ada aktivitas apa pun.**

---

## Kalau Equity Masih Rp 0

Akun demo perlu diisi dulu. Di dashboard Exness (web/aplikasi):

**Opsi A — Reset saldo akun lama**
Cari akun 463942909 → tombol **"Tetapkan Saldo"** → isi nominal

**Opsi B — Buat akun demo baru**
Buat akun demo → catat login, password, server → di MT5:
`File → Login to Trade Account` → isi kredensial

### Berapa nominalnya

| Deposit | Risiko per trade |
|---|---|
| Rp 3.700.000 | 1,89% — minimum, di bawah ini bot menolak |
| **Rp 7.000.000** | **1,00% — disarankan** |
| Rp 10.000.000 | 0,70% |

Batasan ini karena lot minimum broker (0,01) tidak bisa dibagi lebih kecil.

---

## Kalau Ada Masalah

| Gejala | Solusi |
|---|---|
| Jendela hitam langsung tertutup | Buka lewat Command Prompt agar pesan errornya terbaca |
| `Authorization failed` | MT5 belum login — buka MT5, login dulu |
| `Algo trading TIDAK AKTIF` | Tools → Options → Expert Advisors → centang |
| `equity di bawah minimum` | Deposit akun demo (lihat bagian atas) |
| Bot jalan tapi diam terus | Normal di luar jam sesi trading |
| `python is not recognized` | Python tidak ada di PATH — jalankan lewat terminal biasa |

### Menjalankan lewat terminal (alternatif)

Jika file `.bat` bermasalah, buka Command Prompt lalu:

```
cd "D:\Telkom University\PROJECT CUAN"
python run_bot.py --check
python run_bot.py
```

---

## Ringkasan Sekali Lihat

```
BUKA MT5  →  1-CEK.bat  →  3-JALANKAN-OTOMATIS.bat
                                     ↓
                          biarkan jendela terbuka
                                     ↓
                          4-DASHBOARD.bat (pantau)
                                     ↓
                          STOP-BOT.bat (hentikan)
```
