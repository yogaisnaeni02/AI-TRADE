# Cara Menjalankan Bot di PC Lain

**Untuk siapa:** siapa pun yang menyiapkan bot ini di komputer baru.
Dokumen ini lengkap dari nol — tidak mengasumsikan sudah ada apa pun.

---

## PERINGATAN UTAMA — baca dulu

**Jalankan bot hanya di SATU PC untuk satu akun MT5.**

File kunci (`logs/bot.lock`) yang mencegah bot berjalan dobel itu
**tersimpan lokal di tiap PC**. Kalau dua PC punya folder `logs/`
masing-masing, kunci itu tidak pernah saling melihat — keduanya akan
mengirim order ke akun yang sama.

Ini **sudah pernah terjadi** (14 Sep 2026): 5 pasang posisi terbuka dobel
dalam selisih 4–7 detik, kerugian tiap sinyal jadi 2x lipat.

Kalau ingin menjalankan beberapa strategi sekaligus, gunakan **varian**
(bagian 6) di **PC yang sama** — bukan di PC berbeda.

---

## 1. Yang Harus Ada Dulu

| Kebutuhan | Keterangan |
|---|---|
| **Windows** | Wajib. Modul `MetaTrader5` hanya jalan di Windows |
| **Python 3.11+** | Diuji pada 3.13.4. Saat install, centang **"Add Python to PATH"** |
| **MetaTrader 5** | Terpasang dan sudah login ke akun |
| **Git** | Untuk mengambil kode |

---

## 2. Ambil Kode

```
git clone https://github.com/yogaisnaeni02/AI-TRADE.git
cd AI-TRADE
```

Kalau folder sudah ada dan hanya ingin memperbarui:

```
cd "lokasi\folder\AI-TRADE"
git pull
```

---

## 3. Siapkan Python

Sekali saja per PC:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Kalau berhasil, akan muncul `(.venv)` di awal baris terminal.

> Semua file `.bat` di proyek ini **otomatis mengaktifkan venv**, jadi
> langkah `activate` di atas hanya diperlukan saat instalasi atau saat
> menjalankan perintah manual.

---

## 4. Siapkan MetaTrader 5

Tiga hal ini wajib, bot tidak akan jalan tanpanya:

1. **MT5 terbuka dan sudah login** ke akun yang dituju
2. **Algo Trading menyala** — tombol di toolbar MT5, harus berwarna hijau
3. **Simbol `XAUUSDm` tersedia** di Market Watch

> Kalau simbolnya tidak terlihat: klik kanan di Market Watch → *Symbols* →
> cari `XAUUSDm` → *Show*.

---

## 5. Cek Kesiapan Sebelum Menjalankan

Dobel-klik:

```
1-CEK.bat
```

Ini **tidak mengirim order apa pun** — hanya memeriksa. Yang akan
ditampilkan: nomor akun, tipe akun (DEMO/REAL), equity, spread, status
Algo Trading, dan varian yang terpilih.

**Pastikan tipe akunnya DEMO** sebelum lanjut.

Kalau muncul peringatan akun REAL, bot akan **menolak jalan** — itu
pengaman yang disengaja, bukan kerusakan.

---

## 6. Menjalankan Bot

### Cara A — pilih varian (disarankan)

Dobel-klik:

```
5-JALANKAN-VARIAN.bat
```

Akan menanyakan dua hal berurutan:

1. **Nama PC** — label yang ditempel di notifikasi Telegram, mis.
   `PC Rumah`. Ditanya **sekali saja**, lalu diingat di
   `logs/nama_pc.txt`. Hapus file itu bila ingin menggantinya.
   Kosongkan lalu Enter untuk memakai nama Windows apa adanya.

2. **Nama varian** — kosongkan lalu Enter kalau ingin memakai
   `settings.yaml` apa adanya.

Nama PC berguna saat menjalankan bot di lebih dari satu komputer: tanpa
label itu, notifikasi Telegram dari PC berbeda tidak bisa dibedakan.

### Cara B — langsung, tanpa memilih

Dobel-klik:

```
3-JALANKAN-OTOMATIS.bat
```

Memakai `config/settings.yaml` apa adanya.

### Cara C — lewat terminal

```
.venv\Scripts\activate
python run_bot.py --daftar-varian      lihat varian yang ada
python run_bot.py --varian pyramid5    jalankan varian tertentu
python run_bot.py                      config apa adanya
```

### Varian yang tersedia

| Varian | Magic | Isi singkat |
|---|---|---|
| `baseline` | 20260909 | BUY saja, maks 2 posisi |
| `konfluensi` | 20260910 | + filter candle/ADX (backtest terbaik) |
| `dua_arah` | 20260911 | BUY + SELL, maks 2 posisi |
| `dua_arah_konfluensi` | 20260912 | gabungan keduanya |
| `pyramid5` | 20260914 | BUY + SELL, maks **5** posisi searah |
| `ml_walkforward` | 20260913 | riset, belum aktif |

Penjelasan tiap varian ada di `config/variants.yaml` — termasuk status,
hasil backtest, dan peringatannya. Baca dulu sebelum memilih.

### Menjalankan beberapa varian sekaligus

Tiap varian punya **magic number sendiri**, jadi posisinya tidak
bercampur. Buka dua jendela di **PC yang sama**:

```
Jendela 1:  python run_bot.py                    (forward test utama)
Jendela 2:  python run_bot.py --varian pyramid5  (eksperimen)
```

Bot `pyramid5` hanya melihat posisi bermagic 20260914; bot utama hanya
melihat 20260909. Journal juga memisahkannya lewat kolom `varian`.

---

## 7. Selama Bot Berjalan

- **Jendela harus tetap terbuka.** Ganti virtual desktop (Win+Tab) aman.
- **MT5 harus tetap terbuka dan login.**
- **PC jangan sleep** — Settings → Power → Screen and sleep → Sleep: *Never*.
- Bot **menyalakan ulang dirinya sendiri** kalau berhenti tak terduga
  (jeda 30 detik). Berhenti yang disengaja tidak di-restart.

### Yang wajar terjadi — jangan panik

- **Berjam-jam tanpa posisi itu normal.** Rata-rata 3,4 trade/hari, dan
  28,5% hari tidak ada trade sama sekali.
- **Sabtu–Minggu market tutup.** Bot tetap hidup tapi tidak ada bar baru,
  jadi tidak akan buka posisi. Ini normal.
- Baris `[status]` muncul tiap ~1 jam. Selama itu muncul, bot hidup.

---

## 8. Menghentikan Bot

| Cara | Efek |
|---|---|
| **`STOP-BOT.bat`** | Berhenti buka posisi baru; posisi terbuka **tetap dikelola** sampai tutup. Untuk aktif lagi: hapus file `STOP` |
| **Tutup jendela** / Ctrl+C | Bot mati total, posisi terbuka **tidak lagi dikelola** |

Cara yang lebih aman adalah `STOP-BOT.bat`, karena trailing stop dan
proteksi lain tetap berjalan untuk posisi yang masih terbuka.

---

## 9. Memantau

Dobel-klik:

```
4-DASHBOARD.bat
```

Membuka dashboard di browser: equity, posisi terbuka, riwayat trade, dan
statistik per varian.

File yang bisa dilihat langsung:

| File | Isi |
|---|---|
| `logs/trades.csv` | Riwayat trade (ada kolom `varian` dan `magic`) |
| `logs/snapshot.json` | Kondisi terkini; `timestamp` diperbarui tiap siklus |
| `logs/bot_YYYYMMDD.log` | Log harian bot |
| `logs/risk_state.json` | Puncak equity dan status halt |

---

## 10. Kalau Ada Masalah

| Gejala | Penyebab & solusi |
|---|---|
| `Bot lain sudah berjalan (PID ...)` | Ada bot lain aktif di PC ini. Hentikan dulu, atau hapus `logs\bot.lock` bila yakin sudah mati |
| `Lock dipegang mesin lain` | Bot berjalan di PC lain. **Jangan** hapus lock-nya kecuali PC itu benar-benar mati |
| `GAGAL connect MT5` | MT5 belum terbuka / belum login |
| `Algo trading TIDAK AKTIF` | Nyalakan tombol **Algo Trading** di toolbar MT5 |
| Bot menolak jalan, kode 1 | Akun terdeteksi REAL. Disengaja. Tambahkan `--allow-real` **hanya bila memang disengaja** |
| `ModuleNotFoundError` | venv belum aktif atau `pip install -r requirements.txt` belum dijalankan |
| Bot berhenti, `halted: true` | Circuit breaker drawdown 20% menyala. Evaluasi dulu, baru reset `logs/risk_state.json` secara manual |
| Varian salah ketik | Jalankan `python run_bot.py --daftar-varian` untuk melihat nama yang benar |

---

## 11. Ringkasan Cepat

Setelah semuanya terpasang, rutinitas hariannya:

```
1. Buka MT5, login, pastikan Algo Trading hijau
2. Dobel-klik 1-CEK.bat             -> pastikan DEMO & semua OK
3. Dobel-klik 5-JALANKAN-VARIAN.bat -> isi nama PC (sekali saja),
                                       lalu pilih varian
4. Biarkan jendela terbuka
5. Pantau lewat 4-DASHBOARD.bat
```

Untuk berhenti: `STOP-BOT.bat`.
