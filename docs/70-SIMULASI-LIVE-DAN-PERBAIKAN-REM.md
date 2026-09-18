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

**Catatan:** aturan ini memang akan mencegah kejadian 16 Sep
(tujuh entry dalam 30 menit di rentang 2 dolar). Tetapi pada data yang
lebih panjang ia juga memotong kelompok entry yang menguntungkan, sehingga
tidak menyelesaikan sebab kerugian - hanya memperkecil ukuran taruhannya.
Penyebab yang belum disentuh: sisi sell tanpa edge, tidak ada filter
konfluensi, dan tidak ada filter overextension (rekomendasi 1, 2, 4, 5
dokumen analisa).

---

## 9. Walk-forward: apakah "varian yang sedang bagus" bertahan?

Permintaan pemilik: latih di beberapa bulan, uji di bulan berikutnya, ambil
hasilnya, lalu ulangi siklusnya.

**Alat:** `backtest/walk_forward.py`. Di tiap lipatan, semua kandidat
dijalankan pada periode LATIH, satu dipilih menurut kriteria yang dinyatakan
di muka, lalu HANYA pilihan itu dijalankan pada periode UJI yang belum
pernah dilihat. Equity dibawa maju antar lipatan. Pembandingnya: tiap varian
TETAP dijalankan pada periode uji yang sama persis.

Periode uji tidak pernah memuat satu bar pun dari periode latihnya - itu
dikunci tes (`tests/test_walk_forward.py`).

```bash
python backtest/walk_forward.py --dari 2026-06-01 --sampai 2026-09-09 \
    --latih 30 --uji 14 --tanpa-halt-dd
```

### Hasil pada data Exness asli 1 Jun - 9 Sep 2026 (M1 penuh)

Total R di periode UJI saja, halt DD dimatikan, equity awal Rp 5,5 jt:

```
                            latih 30 / uji 14      latih 30 / uji 14   latih 45 / uji 21
strategi                    pilih totR (5 lipatan)  pilih E[R]          pilih totR (2 lipatan)
pemilih walk-forward              +15,06R               +16,97R               +3,99R
tetap baseline                    +30,31R               +30,31R              +45,78R
tetap konfluensi                  +19,38R               +19,38R               +9,49R
tetap dua_arah                    +38,53R               +38,53R              +58,10R
tetap dua_arah_konfluensi         +32,81R               +32,81R              +29,36R
tetap autoclose                   +18,82R               +18,82R              +41,76R
tetap pyramid5                    -18,59R               -18,59R              -24,40R
tetap autoclose_agresif           -17,77R               -17,77R              -22,16R
```

Varian yang terpilih tiap lipatan berganti-ganti: dengan kriteria total R
dua_arah 2x, dua_arah_konfluensi 2x, autoclose 1x; dengan kriteria E[R]
konfluensi 2x, lalu dua_arah, baseline, dua_arah_konfluensi masing-masing 1x.

Korelasi nilai latih terhadap hasil uji pada lipatan 30/14: **+0,11**
(kriteria E[R]) dan +0,61 (kriteria total R), dari 5 lipatan. Run 45/21
tidak dilaporkan korelasinya - hanya 2 lipatan, dan korelasi dua titik
selalu +-1,00.

### Hasil pada 1,4 tahun (1 Mei 2025 - 9 Sep 2026), latih 60 -> uji 30

14 lipatan, total R di periode UJI saja:

```
strategi                    entry   TP    SL    WR     E[R]      t      totR   equity akhir
pemilih walk-forward         1670  393  1120   32%   +0.066  +1.67   +109.36    Rp 13,97 jt
tetap konfluensi              748  225   480   36%   +0.213  +3.48   +159.36    Rp 23,36 jt
tetap dua_arah_konfluensi    1133  305   767   32%   +0.098  +1.99   +110.81    Rp 14,21 jt
tetap baseline                959  256   645   33%   +0.092  +1.76    +88.33    Rp 14,46 jt
tetap dua_arah                178   23   127   29%   -0.130  -1.18    -23.15     Rp 3,99 jt
tetap autoclose               178   21   113   35%   -0.133  -1.31    -23.71     Rp 4,00 jt
tetap pyramid5                648   85   438   32%   -0.052  -0.90    -33.72     Rp 3,99 jt
```

Terpilih: konfluensi 5x, dua_arah_konfluensi 3x, pyramid5 2x, dua_arah 2x,
autoclose 1x, baseline 1x. Lipatan dengan hasil uji positif: 8 dari 14.
**Korelasi nilai latih vs hasil uji: -0,07.**

Dua hal yang WAJIB dibaca bersama tabel itu:
- Periode ini memakai resolusi M5 saja (data M1 baru ada sejak 29 Mei 2026),
  jadi eksekusi di dalam bar lebih kasar daripada run 3,5 bulan di atas.
- dua_arah, autoclose, dan pyramid5 BERHENTI di tengah periode karena equity
  menembus `min_equity_idr` (equity akhir ~Rp 4 jt, entry-nya ikut terpotong
  jadi 178). Angka mereka bukan hasil periode penuh.

### Kesimpulan

1. **Pemilih otomatis kalah dari varian tetap terbaik di keempat
   konfigurasi yang diuji**, dengan dua kriteria pemilihan dan tiga panjang
   jendela:

   ```
   konfigurasi                       pemilih     varian tetap terbaik
   latih 30 / uji 14, pilih totR     +15,06R     dua_arah      +38,53R
   latih 30 / uji 14, pilih E[R]     +16,97R     dua_arah      +38,53R
   latih 45 / uji 21, pilih totR      +3,99R     dua_arah      +58,10R
   latih 60 / uji 30, pilih totR    +109,36R     konfluensi   +159,36R
   ```

2. **Nilai periode latih tidak meramalkan periode uji.** Korelasinya -0,07
   pada sampel terbesar (14 lipatan). Pemilihnya bukan "salah pilih" - tidak
   ada yang bisa dipilih: yang diukur di periode latih sebagian besar
   kebisingan.

3. **Kriteria total R berbahaya.** Dua kali ia memilih pyramid5 karena total
   R latihnya paling besar (+106,46 dan +108,48) - padahal itu datang dari
   452 dan 306 entry, bukan dari keunggulan per trade. Hasil ujinya +54,11R
   lalu -13,17R. Memilih menurut total R berarti memilih varian yang paling
   banyak bertaruh.

4. **Pemilih tidak buruk secara absolut** (+109,36R, mengalahkan baseline
   tetap +88,33R) - ia hanya tidak lebih baik daripada memilih satu varian
   bagus lalu mendiamkannya. Ongkos gonta-gantinya nyata: 1.670 entry untuk
   hasil yang di bawah konfluensi dengan 748 entry.

5. **Untuk ide "kepala bot yang memilih varian otomatis": tidak ada
   dasarnya.** Yang terukur justru kebalikannya - pilih SATU varian,
   diamkan. Di 14 periode uji berturut-turut, konfluensi tetap memberi
   +159,36R dengan t +3,48; itu satu-satunya angka di seluruh pengukuran
   dokumen ini yang melewati ambang ~3,0 (docs/30).

6. Ini **memperkuat rekomendasi 2 dokumen analisa** (`confluence_filter:
   true`) dari arah yang berbeda: bukan dari satu periode penuh yang dipakai
   memilih, melainkan dari 14 periode uji yang tidak pernah dilihat saat
   memilih.

**Batasnya:** satu instrumen, satu rezim panjang (emas naik kuat sepanjang
periode), dan tiga varian pembanding berhenti di tengah jalan karena equity.
Angka ini bukan janji hasil ke depan - ia hanya menutup satu pertanyaan:
memilih varian dari performa terakhir tidak terbukti berguna.

---

## 10. Rem mana yang boleh dibuka untuk testing di demo

Pertanyaan pemilik: untuk menguji baseline, konfluensi, dua_arah, dan
dua_arah_konfluensi, bisakah trade dibuat tanpa batas - "kalau market lagi
oke dan banyak kena TP, biarkan mengalir"?

### Empat skenario (total R, equity awal Rp 5,5 jt, maxpos 2 di semuanya)

- **S0** seperti live: 12 trade/hari, 3 loss beruntun, rugi harian 4%,
  mingguan 8%, halt drawdown 20% permanen
- **S1** batas jumlah trade dibuka, rem lain tetap
- **S2** S1 + halt drawdown dimatikan
- **S3** tanpa batas sama sekali

100 hari data Exness (1 Jun - 9 Sep 2026):
```
varian               S0 (live)          S1            S2          S3
baseline             +0,0  HALT 23 e.   = S0          +26,70R     +17,34R
konfluensi           +5,5  HALT 77 e.   = S0          +25,61R     +20,05R
dua_arah             +0,1  HALT 52 e.   = S0          +51,76R     -19,42R modal habis
dua_arah_konfluensi  -0,6  HALT 41 e.   = S0          +43,11R     -19,22R modal habis
```

30 hari (16 Agu - 15 Sep 2026): S3 paling buruk di keempat varian
(baseline dan dua_arah kehabisan modal); S1 menurunkan konfluensi
+9,94 -> +5,94R dan dua_arah_konfluensi +21,01 -> +16,01R.

Pembanding yang menentukan - **halt DD dimatikan tetapi batas 12
trade/hari DIPERTAHANKAN** (bagian 4): 100 hari baseline +33,70R,
konfluensi +32,61R, dua_arah +60,61R, dua_arah_konfluensi +50,11R. Lebih
baik dari S2 di keempat varian (sekitar 7-9R), juga di 30 hari.

### Hipotesis "let it flow" diuji langsung

Diambil trade yang HANYA terjadi karena batas 12/hari dibuka, dipecah
menurut kondisi hari tepat saat entry (`scratchpad` analisa, halt DD mati):

```
varian               100 hari                      30 hari
baseline             8 trade, 8 SL, -8,00R         tidak ada
konfluensi           7 trade, 7 SL, -7,00R         4 trade, 4 SL, -4,00R
dua_arah             21 trade, 3 menang, -9,87R    5 trade, 5 SL, -5,00R
dua_arah_konfluensi  7 trade, 7 SL, -7,00R         5 trade, 5 SL, -5,00R
```

**Seluruh 57 trade tambahan masuk di hari yang sudah untung dan sudah
"panas" (>=3 TP).** Hanya 3 yang menang, total -45,9R.

Mekanismenya: hari yang sampai menutup 12 trade adalah hari dengan gerakan
besar yang SUDAH berjalan jauh. Trade ke-13 dan seterusnya masuk di ujung
gerakan, saat momentum habis. Pola yang sama tercatat live 16 Sep
(`docs/AnalisaLog`): sesi BUY dibuka 2 TP, lalu 14 SL beruntun karena bot
terus membeli di pucuk. Batas harian di sini memotong entry kesiangan,
bukan profit.

Batasnya jujur: batas 12 hanya kena di 1-4 hari per varian, dan hari-hari
itu sebagian sama antar varian - bukan 57 bukti independen. Tetapi polanya
seragam di dua periode dan empat varian, dan cocok dengan kejadian live.

### Kesimpulan dan yang dipasang

1. Yang menghentikan testing adalah **halt drawdown permanen**, bukan batas
   jumlah trade.
2. **Batas 12 trade/hari dan rem rugi dipertahankan.**
3. Empat varian uji dengan magic sendiri di `config/variants.yaml` -
   `uji_baseline`, `uji_konfluensi`, `uji_dua_arah`,
   `uji_dua_arah_konfluensi` - identik dengan induknya kecuali
   `max_drawdown_percent: 100`. Khusus demo, hapus setelah testing.
4. Arah yang layak diuji berikutnya untuk "hari panas" adalah kebalikan
   dari membuka batas: filter overextension (rekomendasi 4 dokumen
   AnalisaLog) - menahan entry saat gerakan sudah terlalu jauh.

---

## 11. Setelah merge revisi SL/TP varian agresif (61c19ef)

Rekan kerja merombak SL/TP `pyramid5` dan `autoclose_agresif` (SL
3000-6000, RR 3,0, TP min 9000, timeout 96 bar, konfluensi ADX 35) dan
menurunkan `min_equity_idr` 4 jt -> 2 jt untuk SEMUA varian. Diukurnya
dengan `simulasi_live.py` dari branch ini, 100 hari Exness, modal Rp 3 jt.

### Reproduksi

Setelan sama (1 Jun - 9 Sep 2026, modal Rp 3 jt, halt DD mati):

```
varian              angka rekan kerja            hasil di sini (config merge)
konfluensi          +36,61R  maxDD 28,3%          +36,61R  maxDD 28,3%   identik
autoclose_agresif   +17,79R  452 entry  55,7%     +17,79R  452 entry  55,7%   identik
pyramid5            -17,27R   62 entry  79,0%     -10,27R   55 entry  69,7%   BEDA
```

Dua dari tiga identik, jadi data dan kodenya sama. **Angka +17,79R itu
ternyata sudah memakai `autoclose_bar: tutup`** - catatan di commit merge
`fe3cf54` yang menyebut "diukur dengan bar berjalan" SALAH, dikoreksi di
sini dan di `variants.yaml`.

`pyramid5` tidak bisa direproduksi. Bukan karena titik mulai (`--hari
100` memberi hasil identik) dan bukan karena auto-close (varian ini tidak
memakainya). Kemungkinan setelan run di sisi rekan kerja berbeda untuk
varian itu saja; tidak bisa dipastikan dari sini. Kesimpulannya tidak
berubah: kedua angka sangat negatif, modal habis di pertengahan Juni.

### Bar berjalan vs bar tutup, di SL/TP baru

```
autoclose_agresif     bar berjalan                  bar tutup (dipakai)
100 hari Exness       +30,15R  456 e.  maxDD 41,6%   +17,79R  452 e.  maxDD 55,7%
30 hari               -12,13R   94 e.  maxDD 58,5%   -10,02R   93 e.  maxDD 56,0%
                      modal habis sejak 21 Agu       modal habis sejak 15 Sep
```

Di SL/TP lama (bagian 4) bar tutup menang di kedua periode. Di SL/TP baru
hasilnya **tidak konsisten**: periode panjang memilih bar berjalan (+12,4R,
drawdown juga lebih kecil), periode pendek memilih bar tutup (+2,1R) -
tetapi perbandingan 30 hari itu tercemar efek jalur, karena versi bar
berjalan kehabisan modal 25 hari lebih awal.

Dibiarkan `tutup` (setelan yang diukur dan dilaporkan rekan kerja) karena
tidak ada dasar kuat untuk membalik. **Keputusan terbuka.** Yang tidak
berubah di kedua mode: di modal Rp 3 jt varian ini kehabisan modal dalam
30 hari terakhir, dan drawdown 41-58%.

### Temuan: rem persentase jauh lebih ketat di modal kecil

`konfluensi`, 30 hari, config tidak berubah:

```
modal       entry  WR    totR     penolakan terbanyak
Rp 5,5 jt     51   33%  +9,94R   41x sudah 2 posisi; 11x batas trade/hari
Rp 3 jt       24   17%  -9,89R   44x batas RUGI HARIAN; 34x batas RUGI MINGGUAN
```

Penyebabnya aritmetika, bukan strategi. Lot terkunci 0,01, jadi satu SL
(4500 poin) selalu Rp 78.676:

```
modal       1 SL     rem harian 4%        rem mingguan 8%
Rp 5,5 jt   1,43%    setelah ~3 SL        setelah ~6 SL
Rp 3 jt     2,62%    berhenti di SL ke-2  berhenti di SL ke-4
Rp 2 jt     3,93%    berhenti di SL ke-2  berhenti di SL ke-3
```

Di modal Rp 2-3 jt, rem rugi harian 4% praktis berarti **"berhenti setelah
2 SL dalam sehari"** - lebih ketat dari rem "3 loss beruntun" yang sengaja
dipilih. Untuk varian agresif dengan SL sampai 6000 poin, satu SL sudah
Rp 104.902 (3,5% dari Rp 3 jt).

Dampaknya ke hasil TIDAK selalu negatif - di 100 hari `konfluensi` modal
Rp 3 jt justru +36,61R (vs +32,61R di Rp 5,5 jt). Yang pasti hanya
mekanismenya. **Keputusan terbuka untuk pemilik** yang berencana mulai
dari modal kecil: apakah rem harian/mingguan sebaiknya dinyatakan dalam
jumlah SL (tetap berapa pun modalnya), bukan persen. Belum diubah -
`daily`/`weekly` di `risk_limits.yaml` terkunci docs/45 bagian 7.
