# Simulasi Seperti Bot Live, dan Perbaikan Rem, Auto-close, Offset

**Tanggal:** 15 September 2026
**Branch:** `perbaikan/rem-autoclose-simulasi`
**Permintaan pemilik:** sampling 48 jam lalu 30 hari terakhir untuk semua
varian ("hit sinyal, momentum, TP, SL, trailing, dan apakah ada kondisi
kalau TP tidak tercapai lalu harga balik"), lalu "buat branch, kerjakan,
tes ulang".

---

## 1. Kenapa ada

Sampling 48 jam dan 30 hari dijalankan dengan simulator yang meniru bot
live per menit (bukan `backtest/engine.py`). Hasilnya menemukan masalah
yang tidak terlihat di backtest biasa:

| # | Temuan | Dampak |
|---|---|---|
| 1 | Rem harian/beruntun/mingguan menghitung trade SEMUA varian di journal | varian di akun yang sama saling menghentikan |
| 2 | Rem hanya diperbarui setelah `trades.csv` berhasil ditulis, error ditelan | rem bisa buta tanpa jejak |
| 3 | Gagal baca journal -> semua counter rem jadi nol | rem terbuka justru saat data tak terbaca |
| 4 | Posisi yang melewati restart kehilangan `score100` | auto-close diam-diam mati |
| 5 | Offset jam dihitung dari tick terakhir, termasuk tick basi | jam bergeser -1 jam saat jeda harian, -49 jam di akhir pekan |
| 6 | Heartbeat menulis mati fib 0,75/0,25 dan momentum sisi buy | log salah untuk varian fib 0,70/0,30 dan sisi sell |
| 7 | Auto-close dinilai di bar BERJALAN | memotong trade yang akan TP; ukuran lama tidak berlaku |
| 8 | Auto-close + mode batch | untung Rp 700 dari auto-close mematikan rem 3 batch rugi |
| 9 | `r_multiple` di journal selalu kosong | E[R] live tidak bisa dihitung |
| 10 | `engine.py` tidak memodelkan auto-close, batch, dan langkah titik impas | varian autoclose tampil identik dengan induknya |

Terkait #2: 14 Sep 2026 bot live tetap entry setelah 4 SL beruntun
(05:30 x2, 11:05 x2 WIB), padahal rem 3-loss sudah ada sejak commit
`34cdd88` (10 Sep). Penyebab pastinya tidak bisa dipastikan tanpa log PC
tersebut (`logs/*.log` tidak di-commit). #2 adalah salah satu jalur yang cocok.

---

## 2. Yang diubah

### Aturan posisi: satu sumber untuk bot dan simulasi
`src/execution/manajemen_posisi.py` (baru, murni tanpa MT5) berisi
`putuskan()`: BE -> trailing, auto-close, timeout. `TradingBot.manage_positions()`
sekarang hanya menerapkan keputusannya. `backtest/simulasi_live.py` memanggil
fungsi yang sama.

### Rem risiko (`src/risk/manager.py`)
- `RiskManager(..., magic=)` - counter hanya dari trade magic varian itu.
  Baris journal lama tanpa kolom magic dianggap baseline (sama dengan migrasi
  skema). `magic=None` = perilaku lama (dipakai skrip analisis).
- `refresh_from_journal(now, trades=)` - bot mengoper baris riwayat MT5
  langsung. Sumber gagal dibaca -> `False`, counter lama DIPERTAHANKAN.
- Pergantian hari memakai sumber terakhir yang dioper, bukan kembali ke CSV.

### Bot (`src/execution/bot.py`)
- `_sinkron_rem_dan_journal()`: riwayat MT5 dibaca tiap siklus -> rem ->
  baru tulis CSV. Kegagalan dilaporkan ke log dan Telegram (maks sekali per
  jam per sumber), tidak lagi `except Exception: pass`.
- `_rekonstruksi_posisi()`: skor awal dihitung ulang dari bar sinyal;
  `be_done` dikenali dari SL yang sudah melewati entry; offset server
  dikurangkan dari waktu buka broker.
- Heartbeat membaca `fib_buy_min`/`fib_sell_max`/`allow_sell` dari RuleEngine
  dan menguji momentum sesuai arah.

### Journal (`src/monitoring/journal.py`)
- `posisi_tertutup()` (baru): baris posisi tertutup dari riwayat MT5;
  `None` bila riwayat tak terbaca (beda dengan `[]`).
- `sync_closed_trades(rows=)` memakai baris yang sama.
- `r_multiple` membagi dengan `risk_idr` yang memang dihitung (perbaikan
  10 Sep membagi dengan argumen yang selalu 0). Catatan: bila SL tidak
  diketahui, risikonya memakai `sl_typical_points` - R perkiraan.

### Offset server (`src/data/offset_server.py`, `mt5_gateway.py`)
- `PelacakOffset`: nilai awal dari `broker.server_utc_offset`; nilai baru
  dipakai hanya bila tick segar (dekat bilangan bulat jam, rentang wajar) dan
  konsisten 30 menit. Perbedaan dilog.
- `detect_server_offset_hours(strict=True)` untuk downloader: pengukuran
  mentah, menolak tick basi.

### Config
- `position_management.autoclose_bar: berjalan | tutup` - default kode
  `berjalan` (perilaku lama). `autoclose` dan `autoclose_agresif` di
  `variants.yaml` memakai `tutup` (bagian 4).
- Sidik jari config memuat `autoclose_score_drop` dan `autoclose_bar`
  HANYA bila auto-close aktif.

### Simulator (`backtest/simulasi_live.py`, baru)
```bash
python backtest/simulasi_live.py --dari 2026-06-01 --sampai 2026-09-09 --tanpa-halt-dd
python backtest/simulasi_live.py --varian dua_arah autoclose --autoclose-bar tutup
python backtest/simulasi_live.py --feat fitur.parquet --m1 m1.parquet --hari 30 --mingguan
```
Butuh data M1 (bar M5 tanpa M1 disimulasikan satu langkah). Default
equity Rp 5,5 jt - bukan `simulated_equity_idr` (Rp 4 jt), karena itu sama
dengan `min_equity_idr` sehingga rugi pertama langsung memblokir.

---

## 3. Tes ulang

### Suite tes (semua lolos)
```
test_risk_manager.py      18/18   (5 baru: per magic, tanpa magic, dari riwayat, gagal baca, batch)
test_order_safety.py       8/8    (1 baru: posisi_tertutup + r_multiple)
test_structure_choch.py    4/4
test_manajemen_posisi.py  11/11   (baru)
test_offset_server.py      7/7    (baru)
test_simulasi_live.py      1/1    (fitur bar berjalan == pipeline asli)
test_bot_manage.py         8/8    (baru: kabel bot dengan MT5 palsu)
```

### Paritas simulator
`backtest/simulasi_live.py` (memakai `putuskan()` + `RiskManager` baru) pada
data 30 hari yang sama dengan simulasi awal: **652 dari 652 trade identik**
(waktu entry, waktu keluar, alasan, R) di ketujuh varian.

### Sidik jari config
```
konfigurasi            main   branch
settings.yaml          f97a   f97a      <- forward test tidak terputus
baseline               96d6   96d6
konfluensi             ec53   ec53
dua_arah               62ca   62ca
dua_arah_konfluensi    4f92   4f92
pyramid5               2d44   2d44
autoclose              62ca   berubah   <- dulu SAMA dengan dua_arah
autoclose_agresif      2d44   berubah   <- dulu SAMA dengan pyramid5
```
Dulu trade autoclose tidak bisa dibedakan dari induknya lewat hash.

---

## 4. Pengukuran auto-close: bar berjalan vs bar tutup

Metode: `simulasi_live.py`, halt DD dimatikan (standar docs/38), guardrail
harian aktif, equity awal Rp 5,5 jt, tiap varian akun sendiri.

### 100 hari data Exness asli (1 Jun - 9 Sep 2026, 100% bar punya M1)
```
varian              entry  TP   SL  trail autoC  E[R]    t     total R
dua_arah             352  103  227   21     -   +0.173 +1.93   +60.61
autoclose (berjalan) 347   80  206   10    51   +0.128 +1.54   +44.38
autoclose (tutup)    344   87  213   13    31   +0.137 +1.60   +47.17
pyramid5             171   40  124    7     -   -0.072 -0.60   -12.23
agresif (berjalan)   467   90  288    7    82   -0.035 -0.52   -16.27
agresif (tutup)      170   34  113    6    17   -0.078 -0.69   -13.29
```

### 30 hari (16 Agu - 15 Sep 2026; 9-15 Sep proxy GC=F tergeser ke level Exness)
```
varian              entry  TP   SL  autoC  total R
dua_arah             106   26   73    -     -0.53
autoclose (berjalan)  94   16   63   13    -15.66
autoclose (tutup)    100   19   68   10    -11.61
pyramid5              81   16   63    -    -21.09
agresif (berjalan)   162   27  104   30    -22.85
agresif (tutup)       87   16   64    6    -19.86
```

### Entry identik, beda cara keluar (100 hari)
```
dua_arah -> autoclose (berjalan): 299 entry  +59.00R -> +42.80R
   20x TP -> autoclose   -38.57R
   16x SL -> autoclose   +20.31R
dua_arah -> autoclose (tutup):    310 entry  +56.56R -> +36.21R
   15x TP -> autoclose   -30.07R
    6x SL -> autoclose    +8.37R
```

**Kesimpulan:**
- Bar tutup lebih baik dari bar berjalan di keempat perbandingan (+2,8R
  sampai +4,1R). Dipasang di kedua varian autoclose.
- Auto-close tetap KALAH dari tanpa auto-close di kedua periode. Ia memotong
  lebih banyak trade yang akan TP daripada menyelamatkan yang akan SL.
  Klaim +0,018R per trade di `variants.yaml` tidak berlaku untuk bot live.
  **Keputusan pemilik:** hentikan varian autoclose atau lanjutkan sebagai
  pembanding.

---

## 5. Temuan lain dari sampling (tidak diubah)

**Kasus "TP nyaris lalu balik" jarang.** SL penuh dikelompokkan menurut
jarak terjauh ke TP sebelum balik, 100 hari dua_arah (227 SL):
`<25%: 142 | 25-50%: 41 | 50-75%: 37 | 75-90%: 7 | >=90%: 0`.
Pemicu BE 2,4R setara ~85-94% jarak TP (ditetapkan saat RR masih 1:3),
tetapi menurunkannya hanya menyentuh segelintir trade. Prioritas rendah.

**Pyramid kehabisan modal.** pyramid5 dan autoclose_agresif menembus
`min_equity_idr` dalam 2-3 minggu di kedua periode (100 hari: sejak 16 Jun).

**Rem DD 20% memotong periode.** Dengan semua rem aktif, 30 hari:
baseline, dua_arah, dan autoclose berhenti permanen di tengah bulan.

**Konfluensi paling stabil di 30 hari** (drawdown 11-12% vs 22-42%), tetapi
di 100 hari dua_arah tanpa konfluensi lebih tinggi totalnya (+60,6R vs
+50,1R). Tidak ada perubahan config - `momentum_fib` terkunci docs/45 §7.

---

## 6. Yang sengaja TIDAK diubah (butuh keputusan pemilik)

- Definisi batch rugi ("SEMUA posisi rugi") - permintaan pemilik.
- Pyramid tanpa syarat jarak harga.
- `breakeven_at_r`, `momentum_fib`, `trade_distances`, `daily`, `global`.
- Status varian konfluensi.

---

## 7. Batasan

- Bot mengecek tiap ~3 detik, simulasi tiap menit; pemicu BE/trailing
  memakai high/low menit itu. SL dan TP dalam satu menit -> SL duluan.
- Tiap varian dianggap punya akun sendiri. Di akun bersama, equity (untuk
  halt DD dan `min_equity_idr`) tetap milik bersama - rem per magic hanya
  memisahkan counter trade.
- 100 hari = satu rezim pasar (emas naik ke ~4.700 lalu turun). Nilai t
  semua varian di bawah ambang ~3,0 proyek ini.

---

## 8. Jarak antar entry pyramiding — DIUKUR, TIDAK MENAIKKAN HASIL

Rekomendasi nomor 3 `docs/AnalisaLog/KESIMPULAN-ANALISA-LOG-16SEP2026.md`:
larang entry baru bila harga belum bergerak minimal 1x ATR dari posisi
sebelumnya. Latarnya kejadian live 16 Sep: tujuh posisi BUY dibuka di
4325-4327 dalam setengah jam, lalu koreksi 6 poin ke 4321 menyapu semuanya.

**Implementasi:** `global.min_jarak_entry_atr` di `config/risk_limits.yaml`,
default `0.0` (MATI, perilaku lama). Gerbangnya di `RiskManager.check()` -
gerbang tunggal yang sama dipakai bot live dan `simulasi_live.py`, memakai
harga sinyal, ATR sinyal, dan harga buka posisi yang sedang terbuka.

### Hasil (halt DD dimatikan, equity awal Rp 5,5 jt)

100 hari data Exness asli (1 Jun - 9 Sep 2026):
```
varian              jarak  entry   TP   SL     E[R]      t     totR    maxDD
dua_arah                0    351  103  227   +0.173  +1.93   +60.61    22.6%
dua_arah              0,5    348   97  230   +0.125  +1.41   +43.60    25.2%
dua_arah              1,0    335   89  225   +0.080  +0.89   +26.76    27.0%
dua_arah              1,5    299   78  207   +0.032  +0.34    +9.60    25.9%
pyramid5                0    171   40  124   -0.072  -0.60   -12.23    61.7%
pyramid5              0,5    100   19   76   -0.202  -1.35   -20.20    42.0%
pyramid5              1,0     83   15   64   -0.235  -1.44   -19.52    37.6%
pyramid5              1,5     59    9   47   -0.352  -1.98   -20.77    33.7%
autoclose_agresif       0    170   34  113   -0.078  -0.69   -13.29    57.6%
autoclose_agresif     0,5     98   17   70   -0.184  -1.26   -18.05    37.4%
autoclose_agresif     1,0     87   14   63   -0.213  -1.40   -18.56    35.0%
autoclose_agresif     1,5     65    9   48   -0.306  -1.87   -19.90    31.9%
```

30 hari (16 Agu - 15 Sep 2026):
```
varian              jarak  entry   TP   SL     E[R]      t     totR    maxDD
dua_arah                0    106   26   73   -0.005  -0.03    -0.53    22.6%
dua_arah              0,5    101   24   73   -0.067  -0.43    -6.73    29.5%
dua_arah              1,0     86   17   64   -0.163  -1.00   -13.98    27.6%
dua_arah              1,5     88   19   65   -0.152  -0.94   -13.33    25.8%
pyramid5                0     81   16   63   -0.260  -1.64   -21.09    42.0%
pyramid5              0,5     64   11   51   -0.327  -1.88   -20.93    35.1%
pyramid5              1,0    171   41  121   -0.036  -0.30    -6.23    32.2%
pyramid5              1,5    153   36  109   -0.071  -0.56   -10.85    25.6%
autoclose_agresif       0     87   16   64   -0.228  -1.52   -19.86    40.3%
autoclose_agresif     0,5     62   10   48   -0.325  -1.89   -20.13    34.2%
autoclose_agresif     1,0     91   15   65   -0.236  -1.63   -21.46    33.5%
autoclose_agresif     1,5    109   19   76   -0.193  -1.44   -21.02    33.2%
```

### Kesimpulan

1. **Hasilnya tidak naik.** Di 100 hari ketiga varian MEMBURUK dan monoton
   seiring jarak diperbesar. Yang paling telak: dua_arah +60,61R -> +9,60R.
   Aturan ini membuang entry yang berdekatan - dan di periode ini, kelompok
   entry berdekatan itu termasuk yang berujung TP, bukan hanya yang disapu.
2. **Yang konsisten membaik adalah drawdown varian pyramid:** 61,7% ->
   33,7% (pyramid5) dan 57,6% -> 31,9% (agresif) di 100 hari; 42,0% ->
   25,6% di 30 hari. Jadi ini alat KONTROL RISIKO, bukan perbaikan profit.
3. **Angka pyramid5 di 30 hari (1,0 dan 1,5) tidak boleh dibaca sebagai
   bukti.** Tanpa jarak, equity menembus `min_equity_idr` pada 26 Agu dan
   bot terblokir sisa periode; dengan jarak ia tidak pernah terblokir,
   sehingga yang dibandingkan bukan periode yang sama. Efek jalur, bukan
   efek aturan.
4. Karena itu flag **DIBIARKAN MATI** dan tidak dipasang di varian mana pun.
   Kodenya siap dipakai bila pemilik memilih menukar return dengan drawdown.

**Yang perlu disadari:** aturan ini memang akan mencegah kejadian 16 Sep
(tujuh entry dalam 30 menit di rentang 2 dolar). Tetapi pada data yang
lebih panjang ia juga memotong kelompok entry yang menguntungkan, sehingga
tidak menyelesaikan sebab kerugian - hanya memperkecil ukuran taruhannya.
Penyebab yang belum disentuh: sisi sell tanpa edge, tidak ada filter
konfluensi, dan tidak ada filter overextension (rekomendasi 1, 2, 4, 5
dokumen analisa).
