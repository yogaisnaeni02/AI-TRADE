# Cara Menjalankan Bot di PC Lain

**Untuk siapa:** siapa pun yang menyiapkan bot ini di komputer baru.
Dokumen ini lengkap dari nol — tidak mengasumsikan sudah ada apa pun.

Ada dua cara:

| | **A. PC worker** (disarankan) | **B. Manual dengan git** |
|---|---|---|
| Di PC yang menjalankan bot | klik dua kali satu file `.bat` | `git clone`, `pip install`, `git pull` tiap update |
| Git di PC itu | tidak perlu | wajib |
| Update kode | otomatis, saat tidak ada posisi terbuka | manual, bot harus dimatikan dulu |
| Varian yang dijalankan | diatur dari PC utama | diketik di PC itu |
| Log & journal | terkirim otomatis ke PC utama | `6-KIRIM-LOG.bat` manual |

Cara A dibuat setelah kejadian 16 Sep 2026: sebuah PC ternyata masih
menjalankan kode lama tanpa ada yang tahu, `git pull` di tengah bot berjalan
menimpa journal-nya, dan rem harian terbaca nol setelah restart. Di cara A
kode dan data berjalan di dua jalur terpisah, sehingga hal itu tidak bisa
terjadi lagi.

---

## PERINGATAN UTAMA — baca dulu

**Jalankan bot hanya di SATU PC untuk satu akun MT5.**

File kunci (`logs/bot.lock`) yang mencegah bot berjalan dobel itu
**tersimpan lokal di tiap PC**. Kalau dua PC login ke akun MT5 yang sama,
kunci itu tidak pernah saling melihat — keduanya akan mengirim order ke
akun yang sama.

Ini **sudah pernah terjadi** (14 Sep 2026): 5 pasang posisi terbuka dobel
dalam selisih 4–7 detik, kerugian tiap sinyal jadi 2x lipat.

Setiap PC worker harus login ke **akun demonya sendiri**.

---

# A. PC Worker

## A1. Konsepnya

```
PC UTAMA (kode, config, analisis)              PC WORKER (hanya menjalankan)
repo git ── UTAMA-2-TERBITKAN ──> AI-TRADE-rilis\ ══ Syncthing ══> rilis\
                                                                     │ disalin saat bot mati
                                                                     ▼
laporan\<nama-pc>\  <═══════════ Syncthing ═══════════  bot\logs\  (bot jalan di bot\)
```

- **PC utama** adalah satu-satunya tempat kode dan config diubah, dites,
  dan di-review (tetap lewat git bersama tim). Hasil dari semua worker
  dikumpulkan dan dianalisis di sini.
- **PC worker** hanya menerima paket rilis, menjalankan bot dengan varian
  yang ditugaskan, lalu mengirim log dan journal kembali ke PC utama.
- Pengiriman memakai **Syncthing**: gratis, tanpa akun, file dikirim
  langsung antar-PC lewat internet. Arahnya dikunci: rilis hanya mengalir
  ke worker, laporan hanya mengalir ke PC utama.

Yang dikirim ke worker **hanya** yang dibutuhkan bot: `run_bot.py`,
`requirements.txt`, `src/`, `config/`, dan `scripts/pc_worker/`. Data,
backtest, dokumen, dan log PC utama tidak ikut.

## A2. Sekali di PC utama

Yang harus ada: Windows, Python 3.10+ di PATH, Git, dan repo ini.

1. Klik dua kali **`UTAMA-1-SIAPKAN.bat`**. Yang dikerjakan:
   - membuat `.venv` dan memasang paket, kalau belum ada;
   - mengunduh Syncthing (portable, tanpa admin) ke
     `%LOCALAPPDATA%\AI-TRADE-Syncthing\` dan menyalakannya otomatis saat
     Windows login;
   - membuat folder rilis `..\AI-TRADE-rilis\` (di sebelah folder repo)
     dan folder laporan `laporan\` di dalam repo;
   - membuat **`PASANG-WORKER.bat`** di folder repo.
2. Klik dua kali **`UTAMA-2-TERBITKAN.bat`** untuk mengisi folder rilis
   pertama kali (lihat A5).

> Kalau muncul dialog **Windows Firewall** untuk `syncthing.exe`, klik
> **Allow / Izinkan**. Kalau dibatalkan tetap jalan lewat relay, hanya
> lebih lambat.

Empat file di PC utama:

| File | Kapan dipakai |
|---|---|
| `UTAMA-1-SIAPKAN.bat` | sekali saja |
| `UTAMA-2-TERBITKAN.bat` | setiap ada perubahan kode atau config untuk worker |
| `UTAMA-3-STATUS-WORKER.bat` | menerima worker baru dan memantau semua worker |
| `UTAMA-4-ATUR-VARIAN-WORKER.bat` | memilih varian tiap worker dengan nomor |

`PASANG-WORKER.bat` berisi ID Syncthing PC utama ini, jadi file itu tidak
ikut Git. Kalau hilang, buat ulang dengan:

```
.venv\Scripts\python.exe scripts\pc_worker\siapkan_utama.py --bat-saja
```

## A3. Pasang PC worker — klik dua kali

**Siapkan dulu di PC worker:**

1. **MetaTrader 5** terpasang dan **login ke akun demo PC itu**.
2. **Algo Trading menyala** (tombol di toolbar MT5 berwarna hijau).
3. Simbol **`XAUUSDm`** tampil di Market Watch (klik kanan → *Symbols* →
   cari `XAUUSDm` → *Show*).
4. PC **tidak sleep**: Settings → Power → Screen and sleep → Sleep: *Never*.

**Lalu:**

1. Kirim `PASANG-WORKER.bat` ke PC worker (Telegram, Google Drive,
   flashdisk). Kalau aplikasi chat menolak file `.bat`, kirim dalam `.zip`.
2. Di PC worker, klik dua kali `PASANG-WORKER.bat`.
   - Kalau muncul **"Windows protected your PC"**: klik *More info* →
     *Run anyway*.
   - Kalau muncul dialog **Windows Firewall**: klik *Allow / Izinkan*.
3. Jawab pertanyaan **nama PC**, misalnya `PC Kantor`. Pemasang
   menampilkan **kunci penugasan** PC itu, misalnya `pc-kantor`. Catat.
4. Pemasang memasang Python (lewat `winget`, kalau belum ada) dan
   Syncthing, lalu menunggu dengan pesan *"menunggu PC utama menerima PC
   ini"*.
5. **Di PC utama:** klik dua kali **`UTAMA-3-STATUS-WORKER.bat`**, lalu
   jawab `y` saat ditanya menerima worker baru. Pastikan namanya sesuai.
6. Kembali ke PC worker: pemasang menerima kode, memasang paket Python
   (beberapa menit, sekali saja), lalu membuat shortcut **"AI-TRADE
   Worker"** di desktop.
7. Pemasang bertanya apakah bot dijalankan otomatis setiap Windows
   menyala. Jawab `y` kalau PC itu memang khusus untuk bot.
8. **Di PC utama:** pilih varian untuk worker baru ini (A4). Sebelum itu
   worker hanya menunggu dan tidak menjalankan bot.

Semua file worker ada di `%USERPROFILE%\AI-TRADE-WORKER\`:

| Folder / file | Isi |
|---|---|
| `AI-TRADE-WORKER.bat` | peluncur — yang dibuka shortcut desktop |
| `rilis\` | kiriman PC utama. **Jangan diubah** — perubahan di sini dibuang |
| `bot\` | salinan rilis tempat bot berjalan |
| `bot\logs\` | journal, log, status — dikirim otomatis ke PC utama |
| `syncthing\`, `venv\` | Syncthing dan paket Python |
| `worker.json` | nama PC dan lokasi Syncthing |

Kalau pemasangan terputus (internet mati, jendela tertutup), klik dua kali
`PASANG-WORKER.bat` lagi. Langkah yang sudah selesai dilewati.

**Python tidak bisa dipasang otomatis** (PC kantor kadang memblokir
`winget`): unduh dari <https://www.python.org/downloads/windows/>, centang
*"Add python.exe to PATH"* saat memasang, lalu klik dua kali pemasangnya
lagi.

## A4. Menentukan varian tiap worker — pilih nomor

Di PC utama, klik dua kali **`UTAMA-4-ATUR-VARIAN-WORKER.bat`**. Tidak ada
nama yang perlu diketik:

```
  no  PC                      penugasan               sedang berjalan
  ----------------------------------------------------------------------
  1   PC Kantor               dua_arah_konfluensi     dua_arah_konfluensi
  2   PC3                     -                       -

Nomor PC yang mau diubah (Enter = selesai): 2

0  berhenti  - worker hidup, bot TIDAK dijalankan
h  hapus     - hapus dari penugasan (sama-sama tidak menjalankan bot)

no varian               magic     status   ...
1  baseline             20260909  ...
2  konfluensi           20260910  ...
...
5  pyramid5             20260914  ...

Nomor varian (Enter = batal): 5
-> PC3: pyramid5
```

Tekan Enter kosong untuk selesai. Perubahan ditampilkan, disimpan ke
`config/penugasan.yaml`, lalu ada tawaran **terbitkan sekarang** (A5).

- Yang muncul di daftar hanya worker yang **sudah diterima** lewat
  `UTAMA-3-STATUS-WORKER.bat`.
- Nomor varian sama dengan nomor di `5-JALANKAN-VARIAN.bat`: urutan di
  `config/variants.yaml`.
- Varian berstatus riset (misalnya `ml_walkforward`) meminta konfirmasi
  `ya` lebih dulu.
- **PC tanpa penugasan tidak menjalankan bot** — ia menunggu dengan
  keadaan `belum_ditugaskan`. Ini disengaja: worker baru tidak langsung
  berdagang sebelum diputuskan varian apa yang dijalankan.

`config/penugasan.yaml` juga boleh diedit langsung, dengan format satu
baris `kunci-pc: nama_varian` per worker. Komentar di bagian atas file
dipertahankan, tapi komentar di ujung baris penugasan hilang setelah
alat nomor dipakai.

## A5. Menerbitkan perubahan

Klik dua kali **`UTAMA-2-TERBITKAN.bat`**. Urutannya:

1. **Kode harus sudah di-commit.** Perubahan yang belum di-commit ditolak,
   supaya versi di worker selalu bisa dilacak ke satu commit. Pengecualian:
   `config/penugasan.yaml` boleh diterbitkan tanpa commit — isinya tetap
   tercatat di `VERSI.json` setiap rilis.
2. **Bukan branch `main`?** Diminta mengetik `ya`, karena semua worker akan
   menjalankan kode branch itu.
3. `config/penugasan.yaml` diperiksa: format dan nama varian.
4. **Tes dijalankan.** Kalau gagal, rilis dibatalkan dan worker tetap di
   versi lama.
5. File disalin ke folder rilis. Kalau isinya sama persis dengan rilis
   sebelumnya, tidak ada yang diterbitkan.

**Yang terjadi di worker setelah itu:**

- Worker mengecek rilis setiap 30 detik, dan hanya memakai rilis yang
  **seluruh filenya sudah tiba** (dicocokkan dengan sidik jari di
  `VERSI.json`). Rilis yang baru separuh terkirim tidak pernah dipakai.
- Kalau kodenya berubah, atau **penugasan PC itu** berubah, bot diminta
  berhenti **begitu tidak ada posisi terbuka**. Selama masih ada posisi,
  bot tetap mengelolanya (trailing, break-even) dan update menunggu.
  Keadaan worker: `menunggu_posisi_tutup`.
- Setelah bot berhenti, rilis disalin ke `bot\`, paket Python dipasang
  ulang bila `requirements.txt` berubah, lalu bot dinyalakan lagi.
- Kalau rilis juga mengubah peluncur worker itu sendiri
  (`scripts/pc_worker/`), peluncur memulai ulang dirinya — juga hanya saat
  bot sedang mati.
- Mengubah penugasan PC lain **tidak** membuat worker ini restart.

Hasil uji di satu PC (dua Syncthing lewat 127.0.0.1, 17 Sep 2026):
pemasangan worker sampai kode lengkap tiba 72 detik; laporan pertama tiba di
PC utama sekitar 2 menit; setelah penugasan diganti dan diterbitkan, bot
di worker pindah varian dalam 74 detik. Lewat internet angkanya bisa lebih
lama.

Header log bot selalu mencatat versinya:

```
BOT START — mode EXECUTOR — VARIAN: dua_arah_konfluensi
Versi kode: rilis 20260917-1530-abc1234 (commit abc1234)
```

## A6. Memantau dari PC utama

Klik dua kali **`UTAMA-3-STATUS-WORKER.bat`** kapan saja. Contoh:

```
Rilis terbaru: 20260917-1530-abc1234

----------------------------------------------------------
PC Kantor  [pc-kantor]  TERHUBUNG | kabar 1 menit lalu
  keadaan : berjalan - varian dua_arah_konfluensi, versi 20260917-1530-abc1234
  versi   : 20260917-1530-abc1234
  varian  : dua_arah_konfluensi
  akun    : equity Rp 5,208,252 | posisi 0 | hari ini 0 trade, P/L Rp 0
  trade   : 4 tercatat | minggu ini 4, P/L Rp -291,748
  status  : [2026-09-17 13:35:03] [status] 13:35 WIB | sesi asia AKTIF — belum: ...
```

Tanda yang perlu diperhatikan:

| Tanda | Artinya |
|---|---|
| `!! BASI` | tidak ada kabar lebih dari 5 menit — PC mati, internet putus, atau worker ditutup |
| `TIDAK TERHUBUNG` | Syncthing di PC itu tidak tersambung ke PC utama |
| `!! belum versi terbaru` | wajar sesaat setelah menerbitkan; kalau lama, cek keadaannya |
| `varian: X (penugasan: Y)` | worker belum pindah varian — biasanya masih menunggu posisi tutup |

Arti **keadaan**:

| Keadaan | Artinya |
|---|---|
| `berjalan` | bot hidup dengan varian yang ditugaskan |
| `menunggu_posisi_tutup` | ada update, bot berhenti setelah posisinya tertutup |
| `belum_ditugaskan` | PC ini belum ada di `config/penugasan.yaml` |
| `dihentikan_pc_utama` | penugasannya `berhenti` |
| `menunggu_kode` | kiriman pertama belum lengkap |
| `bot_gagal` | bot keluar dengan kode 1: MT5 belum login, akun REAL, atau varian salah. Dicoba lagi tiap 2 menit |
| `bot_berhenti` | bot berhenti tak terduga; dinyalakan ulang dalam 30 detik |
| `bot_lama_masih_jalan` | peluncur sempat mati tapi bot-nya masih hidup; bot itu diminta berhenti begitu tidak ada posisi terbuka, lalu diambil alih |
| `memperbarui` | sedang memasang rilis baru |
| `dimatikan` | jendela worker ditutup / Ctrl+C di PC worker |

Semua kiriman worker ada di **`laporan\<kunci-pc>\`**: `trades__*.csv`,
`bot_*.log`, `worker_*.log`, `snapshot.json`, `risk_state.json`,
`status_worker.json`. Journal semua worker digabung ke
**`laporan\trades_gabungan.csv`** setiap kali status dibuka.

> Laporan dikirim sekitar tiap 1 menit. Kalau PC utama sedang mati,
> laporan tertahan di worker dan terkirim begitu PC utama menyala lagi —
> tidak ada yang hilang. Selama PC utama mati, rilis baru juga tidak bisa
> dikirim, tapi bot di worker tetap berjalan.

## A7. Rutinitas di PC worker

```
1. MT5 terbuka, login ke akun demo, Algo Trading hijau
2. Klik dua kali "AI-TRADE Worker" di desktop  (atau otomatis saat Windows menyala)
3. Biarkan jendelanya terbuka
```

Tidak ada lagi yang perlu diketik atau di-pull. Baris `[status]` muncul
tiap ~1 jam selama bot hidup; baris `[worker]` berasal dari peluncur.

Notifikasi Telegram (opsional) diatur sekali per PC worker lewat Command
Prompt, lalu tutup dan buka lagi jendela worker:

```
setx AI_TRADE_TG_TOKEN   "123456:ABC..."
setx AI_TRADE_TG_CHAT_ID "987654321"
```

Tiap pesan diawali **nama PC + varian**, jadi notifikasi dari beberapa
worker tidak tertukar. Yang dikirim:

| Kejadian | Isi |
|---|---|
| Posisi dibuka | arah, lot, harga, SL/TP, RR, skor, risiko (% dan rupiah), tiket |
| Posisi tertutup | sebab (TP, SL, trailing/BE, ditutup bot, ditutup manual), harga masuk → keluar, durasi, P/L dan R, trade + P/L hari ini, equity |
| Kabar berkala | equity dan drawdown, posisi terbuka + floating, trade dan P/L hari ini, status rem, sesi |
| Order gagal, HALT, bot start/stop | alasannya |

Kabar berkala default tiap **1 jam**; ubah di `config/settings.yaml`
(`telegram.heartbeat_jam`, `0` untuk mematikan). Gunanya bukan kenyamanan:
kalau pesannya berhenti datang, berarti bot atau PC-nya mati.

## A8. Menghentikan

| Cara | Efek |
|---|---|
| `UTAMA-4-ATUR-VARIAN-WORKER.bat` → nomor PC → `0` (berhenti) → terbitkan | bot berhenti **setelah posisinya tertutup**, worker tetap hidup dan menunggu |
| File **`STOP`** di `AI-TRADE-WORKER\bot\` (di PC worker) | berhenti buka posisi baru; posisi terbuka tetap dikelola. Hapus file itu untuk aktif lagi. Tidak terhapus oleh update |
| Tutup jendela worker / Ctrl+C | bot mati total; posisi terbuka **tidak lagi dikelola**, hanya SL/TP di server |

## A9. Memindahkan PC yang sudah memakai cara B

PC yang sebelumnya menjalankan bot lewat git punya journal dan puncak
equity di folder lamanya. Kalau tidak dibawa, **rem harian, mingguan, dan
halt drawdown mulai dari nol** — persis masalah 16 Sep.

1. Hentikan bot lama (tutup jendelanya).
2. Pasang worker (A3), **tetapi jangan jalankan dulu**.
3. Salin dari `logs\` folder lama ke `AI-TRADE-WORKER\bot\logs\`:
   - `trades__<nama>.csv` — **ganti namanya** menjadi
     `trades__<kunci-penugasan>.csv` bila berbeda;
   - `risk_state.json`.
4. Pilih variannya lewat `UTAMA-4-ATUR-VARIAN-WORKER.bat`, terbitkan,
   lalu jalankan worker.

Jangan menjalankan folder lama dan worker bersamaan (lihat peringatan utama).

## A10. Kalau ada masalah

| Gejala | Penyebab & solusi |
|---|---|
| Pemasang terus *"menunggu PC utama menerima PC ini"* | Jalankan `UTAMA-3-STATUS-WORKER.bat` di PC utama dan jawab `y`. Pastikan PC utama menyala dan Syncthing-nya berjalan |
| Worker baru tidak muncul di PC utama | Tunggu 1–2 menit lalu buka status lagi. Periksa internet kedua PC |
| Keadaan `belum_ditugaskan` | Pilih variannya lewat `UTAMA-4-ATUR-VARIAN-WORKER.bat`, lalu terbitkan |
| PC tidak muncul di `UTAMA-4-ATUR-VARIAN-WORKER.bat` | Worker belum diterima. Jalankan `UTAMA-3-STATUS-WORKER.bat` dulu |
| `varian '...' tidak ada` saat terbitkan | Salah ketik nama varian di `penugasan.yaml` (hanya terjadi bila diedit manual) |
| Keadaan `bot_gagal` | Buka jendela worker dan baca pesan bot. Biasanya MT5 belum login |
| Terbitkan ditolak *"Commit dulu"* | Commit perubahan kode, atau `UTAMA-2-TERBITKAN.bat --paksa` untuk uji coba |
| Terbitkan ditolak karena tes gagal | Perbaiki dulu. Worker tetap di versi lama, jadi aman |
| Syncthing mati setelah restart Windows | Buka `shell:startup` (Win+R) dan pastikan shortcut *AI-TRADE Syncthing* ada. Peluncur worker juga menyalakannya sendiri |
| Ingin melihat detail Syncthing | Buka <http://127.0.0.1:18384> di browser PC itu |
| Pesan lain dari bot | Sama dengan cara B — lihat B10 |

**Jangan mengganti nama PC** setelah worker berjalan: nama itu menentukan
kunci penugasan dan nama file journal. Kalau terpaksa, pasang ulang di
folder baru dan pindahkan journal seperti A9.

**Menghapus worker:** tutup jendela worker, hapus shortcut *AI-TRADE* di
`shell:startup` dan desktop, lalu hapus folder `AI-TRADE-WORKER`.

---

# B. Manual dengan git

Cara lama, tetap berlaku untuk PC pengembang atau bila Syncthing tidak bisa
dipakai.

## B1. Yang Harus Ada Dulu

| Kebutuhan | Keterangan |
|---|---|
| **Windows** | Wajib. Modul `MetaTrader5` hanya jalan di Windows |
| **Python 3.11+** | Diuji pada 3.13.4. Saat install, centang **"Add Python to PATH"** |
| **MetaTrader 5** | Terpasang dan sudah login ke akun |
| **Git** | Untuk mengambil kode |

## B2. Ambil Kode

```
git clone https://github.com/yogaisnaeni02/AI-TRADE.git
cd AI-TRADE
```

Kalau folder sudah ada dan hanya ingin memperbarui:

```
cd "lokasi\folder\AI-TRADE"
git pull
```

### Aturan sebelum pull atau push

**Matikan bot dulu sebelum `git pull`.** Bot yang sedang berjalan tidak
memuat kode baru, dan pull bisa menimpa journal yang sedang ditulisnya.

Jangan langsung menjalankan `git pull` atau `git push` saat bot sedang
menulis hasil. Jalankan dulu:

```
6-KIRIM-LOG.bat
```

Skrip ini membuat laporan Markdown baru di `docs/AnalisaLog/` sebelum
sinkronisasi. Nama file memakai nama PC dan waktu, misalnya
`LOG-PC-RUMAH-20260916-143000.md`, sehingga laporan lama tidak ditimpa
dan dua PC tidak menulis file yang sama.

Urutannya:

1. Periksa status bot, snapshot, dan jumlah trade lokal.
2. Buat laporan baru di `docs/AnalisaLog/`.
3. Pull perubahan dari PC lain.
4. Push journal PC ini dan laporan barunya.
5. Buat hasil gabungan trade di `docs/AnalisaLog/trades_gabungan.csv`.

Data runtime bot tetap berada di `logs/`. Folder `docs/AnalisaLog/` adalah
arsip hasil dan analisis, bukan sumber data yang dibaca bot. Gunakan satu
laporan baru untuk setiap sesi pull/push; jangan memakai satu file Markdown
yang terus ditimpa.

## B3. Siapkan Python

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

## B4. Siapkan MetaTrader 5

Tiga hal ini wajib, bot tidak akan jalan tanpanya:

1. **MT5 terbuka dan sudah login** ke akun yang dituju
2. **Algo Trading menyala** — tombol di toolbar MT5, harus berwarna hijau
3. **Simbol `XAUUSDm` tersedia** di Market Watch

> Kalau simbolnya tidak terlihat: klik kanan di Market Watch → *Symbols* →
> cari `XAUUSDm` → *Show*.

## B5. Cek Kesiapan Sebelum Menjalankan

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

## B6. Menjalankan Bot

### Cara 1 — pilih varian (disarankan)

Dobel-klik:

```
5-JALANKAN-VARIAN.bat
```

Akan menanyakan dua hal berurutan:

1. **Nama PC** — label yang ditempel di notifikasi Telegram, mis.
   `PC Rumah`. Ditanya **sekali saja**, lalu diingat di
   `logs/nama_pc.txt`. Hapus file itu bila ingin menggantinya.
   Kosongkan lalu Enter untuk memakai nama Windows apa adanya.

2. **Nomor varian** — ketik nomor dari kolom `no` di daftar, misalnya
   `4` untuk `dua_arah_konfluensi`. Nama lengkap juga masih diterima.
   Nomor yang tidak ada di daftar ditolak dan ditanyakan ulang.
   Kosongkan lalu Enter kalau ingin memakai `settings.yaml` apa adanya.

Nama PC berguna saat menjalankan bot di lebih dari satu komputer: tanpa
label itu, notifikasi Telegram dari PC berbeda tidak bisa dibedakan.

> Nama PC juga menentukan nama file journal (`logs/trades__<nama>.csv`),
> dan rem harian/mingguan dibaca dari file itu. **Jangan mengganti nama PC
> di tengah minggu** — rem akan mulai dari nol.

### Cara 2 — langsung, tanpa memilih

Dobel-klik:

```
3-JALANKAN-OTOMATIS.bat
```

Memakai `config/settings.yaml` apa adanya.

### Cara 3 — lewat terminal

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

## B7. Selama Bot Berjalan

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

## B8. Menghentikan Bot

| Cara | Efek |
|---|---|
| **`STOP-BOT.bat`** | Berhenti buka posisi baru; posisi terbuka **tetap dikelola** sampai tutup. Untuk aktif lagi: hapus file `STOP` |
| **Tutup jendela** / Ctrl+C | Bot mati total, posisi terbuka **tidak lagi dikelola** |

Cara yang lebih aman adalah `STOP-BOT.bat`, karena trailing stop dan
proteksi lain tetap berjalan untuk posisi yang masih terbuka.

## B9. Memantau

Dobel-klik:

```
4-DASHBOARD.bat
```

Membuka dashboard di browser: equity, posisi terbuka, riwayat trade, dan
statistik per varian.

File yang bisa dilihat langsung:

| File | Isi |
|---|---|
| `logs/trades__<nama-pc>.csv` | Riwayat trade PC ini (ada kolom `varian` dan `magic`) |
| `logs/snapshot.json` | Kondisi terkini; `timestamp` diperbarui tiap siklus |
| `logs/bot_YYYYMMDD.log` | Log harian bot |
| `logs/risk_state.json` | Puncak equity dan status halt |
| `docs/AnalisaLog/LOG-*.md` | Laporan bot dan trade sebelum pull/push |
| `docs/AnalisaLog/trades_gabungan.csv` | Hasil gabungan semua PC, turunan dari journal |

## B10. Kalau Ada Masalah

| Gejala | Penyebab & solusi |
|---|---|
| `Bot lain sudah berjalan (PID ...)` | Ada bot lain aktif di PC ini. Hentikan dulu, atau hapus `logs\bot.lock` bila yakin sudah mati |
| `Lock dipegang mesin lain` | Bot berjalan di PC lain. **Jangan** hapus lock-nya kecuali PC itu benar-benar mati |
| `GAGAL connect MT5` | MT5 belum terbuka / belum login |
| `Algo trading TIDAK AKTIF` | Nyalakan tombol **Algo Trading** di toolbar MT5 |
| Bot menolak jalan, kode 1 | Akun terdeteksi REAL. Disengaja. Tambahkan `--allow-real` **hanya bila memang disengaja** |
| `ModuleNotFoundError` | venv belum aktif atau `pip install -r requirements.txt` belum dijalankan |
| Bot berhenti, `halted: true` | Circuit breaker drawdown 20% menyala. Evaluasi dulu, baru reset `logs/risk_state.json` secara manual |
| Varian salah ketik | Ketik nomornya saja. Daftar bernomor: `python -m src.variants` |
| `Versi kode:` di header log bukan commit terbaru | Bot masih memakai kode lama. Matikan bot, `git pull`, jalankan lagi |

## B11. Ringkasan Cepat

Setelah semuanya terpasang, rutinitas hariannya:

```
1. Buka MT5, login, pastikan Algo Trading hijau
2. Dobel-klik 1-CEK.bat             -> pastikan DEMO & semua OK
3. Dobel-klik 5-JALANKAN-VARIAN.bat -> isi nama PC (sekali saja),
                                       lalu ketik nomor varian
4. Biarkan jendela terbuka
5. Pantau lewat 4-DASHBOARD.bat
```

Untuk berhenti: `STOP-BOT.bat`.
