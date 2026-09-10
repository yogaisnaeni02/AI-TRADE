# Rencana Riset Berikutnya — Siap Eksekusi

**Tanggal:** 10 September 2026
**Untuk siapa:** sesi/agen mana pun yang akan mengeksekusi. Dokumen ini
dirancang agar bisa dikerjakan tanpa konteks percakapan sebelumnya.

**Baca dulu, berurutan:**
1. `docs/27-AUDIT-TEMUAN.md` — kenapa semua angka lama batal (data meleset 7 jam)
2. `docs/28-HASIL-KALIBRASI-ULANG.md` — setelan sekarang dan batas kepercayaannya
3. `docs/30-KANDIDAT-STRATEGI-LAIN.md` — apa yang sudah diuji dan gagal (jangan diulang)
4. `docs/29-RENCANA-LANJUTAN.md` — pekerjaan keselamatan/infrastruktur yang masih terbuka

**Status saat dokumen ini ditulis:** bot jalan di demo, mode EXECUTOR,
momentum_fib, ATR 0,20–0,95, RR 1:2,78, 24 jam. Forward test sedang
mengumpulkan trade. **Jangan ubah jalur sinyal selama forward test berjalan**
kecuali lewat prosedur di bagian 5.

---

## 1. Prinsip yang mengikat semua ide di bawah

Di M5 dengan spread 26 pip, **menambah indikator tidak menambah edge**.
50+ kombinasi diuji pada data M5 yang sama; ambang t jujur sekarang ≈ 3,0
dan tidak ada yang mencapainya. Setiap ide di sini disaring lewat satu
pertanyaan: *apakah ia membawa informasi yang belum ada di deret harga M5,
memperbaiki eksekusi, atau naik ke timeframe di mana spread tidak menggigit?*

Yang **dilarang** tanpa alasan baru yang kuat: oscillator tambahan (RSI,
MACD, Stoch), MA berlapis, Ichimoku, kebun binatang pola candle, ML
sebelum rule engine punya edge terbukti, confidence score untuk keputusan
apa pun (terbukti terbalik: skor 6 = +0,361R, skor 8 = −0,219R).

---

## 2. Daftar prioritas

| # | ide | jenis | nilai | biaya | informasi baru? | status |
|---|---|---|---|---|---|---|
| 1 | Entry presisi M1 | eksekusi | **tertinggi** | sedang | ya (resolusi) | belum |
| 2 | Blackout berita | risiko | tinggi | rendah | ya (kalender) | direncanakan docs/29 #6 |
| 3 | Lintas-sesi Tokyo→London | filter hari | sedang-tinggi | rendah | ya (temporal) | belum pernah disentuh |
| 4 | BOS/CHoCH sebagai filter arah | filter | sedang | sangat rendah | tidak | belum |
| 5 | DXY H4 sebagai bias arah | filter arah | sedang | rendah | ya (cross-asset) | belum |
| 6 | Profil volatilitas per jam | sizing/veto | sedang | rendah | ya (baru sahih) | belum |
| 7 | Panel insight makro di dashboard | insight | — | rendah | untuk manusia | belum |
| 8 | Ukur ulang docs/25 (berita) & docs/26 (korelasi) | koreksi | sedang | rendah | — | keduanya diukur pada jam yang salah |
| 9 | COT + yield riil | rezim | — | data luar | ya | hanya untuk H1 (docs/30 §2) |

Nomor 1 dan 3 adalah yang paling layak dikerjakan pertama: #1 menyerang RR
secara mekanis tanpa perlu edge baru, #3 satu-satunya ide yang informasinya
belum pernah dilihat siapa pun di proyek ini.

---

## 3. Spesifikasi per ide — hipotesis dipra-daftarkan

Format tiap ide: **hipotesis** (ditulis sebelum lihat data) → **metrik** →
**ambang lolos** → **file yang disentuh** → **jebakan**.

Kalau hasil tidak memenuhi ambang, ide itu **gagal**. Bukan "coba parameter
lain". Mengubah parameter setelah melihat hasil adalah persis cara proyek ini
nyasar sebelumnya.

### 3.1 Entry presisi M1

**Hipotesis.** Sinyal momentum_fib tetap ditentukan di close bar M5, tetapi
entry dieksekusi di M1 pada retest level yang lebih tepat, sehingga jarak SL
turun dari ~400 pip ke 200–300 pip **tanpa** menaikkan frekuensi SL kena
lebih dari proporsional. Efek bersihnya RR naik ≥ 1,4x dan E[R] naik.

**Metrik.** E[R] dan t pada trade yang sama (paired: sinyal M5 identik,
hanya entry/SL yang beda), median SL points, % trade yang gagal mendapat
retest (sinyal hangus).

**Ambang lolos.**
- E[R] naik minimal +0,05R terhadap baseline pada sinyal yang sama, DAN
- t tidak turun, DAN
- sinyal hangus (tidak dapat retest dalam N bar M1) ≤ 30%.
Bila hangus > 30% tapi E[R] naik besar, laporkan dua-duanya — itu trade-off
frekuensi vs kualitas, keputusan pemilik.

**File.** `src/strategy/setups.py` (definisi retest), `backtest/engine.py`
(mode entry M1 — engine sudah punya `df_m1` dan `_resolve_m1`, perluas ke
entry), `src/execution/bot.py` (loop harus membaca M1 setelah sinyal M5).

**Jebakan.**
- Data M1 hanya 0,28 tahun (`data/raw/XAUUSDm_M1.parquet`, Mei–Sep 2026).
  Cukup untuk uji awal, TIDAK cukup untuk klaim. Bandingkan hanya pada
  periode yang sama dengan baseline M5.
- Definisi "retest" harus ditetapkan SEBELUM uji (misal: harga kembali ke
  50% jarak close-sinyal ke EMA20 M1, dalam maksimal 12 bar M1). Satu
  definisi. Bukan lima.
- `resampler.py` sudah terverifikasi kausal (`label="left", closed="left"`);
  jangan ubah.

### 3.2 Blackout berita

Spesifikasi lengkap sudah di `docs/29` bagian 6. Tambahan yang relevan di
sini: ini **filter risiko**, bukan sumber sinyal. Ambang lolosnya bukan
"E[R] naik" melainkan "DD dan loss beruntun turun tanpa E[R] turun lebih
dari 0,02R". Kalau E[R] naik pun, itu bonus, bukan tujuan.

Keuntungan khusus broker ini: spread fixed, jadi biaya berita hanya slippage
dan whipsaw — bukan spread yang melebar 10x seperti di broker lain.

### 3.3 Lintas-sesi: Tokyo memprediksi London?

**Hipotesis.** Karakter sesi Tokyo (23:00–07:00 UTC) — lebar range relatif
ATR, dan arah bersih vs berisik (|close−open| / range) — memprediksi apakah
momentum_fib menguntungkan di sesi London/NY hari itu. Secara spesifik:
hari dengan Tokyo **sempit dan berisik** (kompresi) diikuti momentum yang
lebih menguntungkan; Tokyo **lebar dan searah** (ekspansi sudah terjadi)
diikuti momentum yang lebih buruk.

**Metrik.** E[R] momentum_fib per kuartil "skor Tokyo", pada trade yang
terjadi setelah 07:00 UTC hari yang sama.

**Ambang lolos.** Selisih E[R] kuartil terbaik vs terburuk ≥ 0,15R, DAN
monotonik (kuartil 1 < 2 < 3 < 4 atau sebaliknya), DAN bertahan di kedua
paruh M5. Kalau hanya kuartil ekstrem yang beda tapi tidak monotonik,
itu noise.

**File.** Baru: fitur harian di `src/features/pipeline.py` (`tokyo_range_atr`,
`tokyo_directional`), lalu dipakai `setups.py` sebagai gate opsional
`momentum_fib.tokyo_filter`. Uji lewat skrip seperti
`scripts/measure_sessions.py`.

**Jebakan.**
- Ini lead-lag *temporal*, bukan antar-instrumen — docs/26 yang bilang
  "tidak ada lead-lag" mengukur hal yang berbeda (DXY/silver di M5).
- Hanya 364 hari Tokyo di data M5. Kuartil = ~90 hari tiap kelompok.
  Cukup untuk melihat pola, tipis untuk klaim. Validasi di M15 (4,23 thn)
  wajib.
- Jangan uji 10 definisi "skor Tokyo". Dua fitur di atas, satu kombinasi.

### 3.4 BOS/CHoCH sebagai filter arah

**Hipotesis.** Entry momentum_fib yang **searah** BOS terakhir di M5 punya
E[R] lebih tinggi daripada yang berlawanan; membuang yang berlawanan
menaikkan E[R] tanpa memotong n lebih dari 25%.

**Metrik.** E[R] dan n untuk dua kelompok (searah / berlawanan BOS), lalu
gabungan setelah filter.

**Ambang lolos.** E[R] kelompok searah − berlawanan ≥ 0,10R, DAN n setelah
filter ≥ 75% dari sebelumnya, DAN bertahan di kedua paruh.

**File.** `structure.py` sudah menghitung `bos`/`choch` (audit
mengonfirmasi swing dikonfirmasi ke depan dengan benar, `confirmed_at_idx`).
Cukup tambah satu `if` di `_momentum_fib`. Ini uji termurah di daftar.

**Jebakan.** Kalau n terpotong > 25%, edge per trade naik tapi bukti per
tahun turun — kembali ke masalah frekuensi docs/28 §2. Laporkan "tahun
yang dibutuhkan untuk t=2" sebelum dan sesudah.

### 3.5 DXY H4 sebagai bias arah

**Hipotesis.** Long emas hanya saat DXY H4 downtrend (dan sebaliknya)
menaikkan E[R] momentum_fib, karena makro bekerja di horizon H4–D1 dan
docs/26 (yang tidak menemukan lead-lag) mengukur di M5.

**Metrik.** E[R] per kelompok (DXY searah / berlawanan / ranging), lalu
gabungan.

**Ambang lolos.** Sama dengan 3.4: selisih ≥ 0,10R, n ≥ 75%, kedua paruh.

**File.** `data_corr/raw/DXYm_M5.parquet` (sudah benar waktunya — audit
mengonfirmasi tutup Jumat 21:55). Resample ke H4, hitung tren dengan cara
yang sama seperti `build_htf_context`, merge dengan `merge_asof` dan
`available_at` seperti H1/H4 emas — **jangan** merge langsung, itu lookahead.

**Jebakan.** DXYm adalah CFD sintetis broker, bukan indeks asli. docs/26
sudah curiga korelasinya lemah karena itu. Kalau hasilnya nol, coba
sumber DXY luar sebelum menyimpulkan.

### 3.6 Profil volatilitas per jam

**Hipotesis.** Sekarang label jam sudah benar, ada jam-jam yang E[R]
momentum_fib-nya konsisten negatif (kemungkinan 21:00–23:00 UTC rollover
dan 04:00–06:00 UTC). Membuang jam itu sebagai *veto* menaikkan E[R].

**Metrik.** E[R] per jam UTC (24 kelompok), kedua paruh terpisah.

**Ambang lolos.** Jam yang dibuang harus negatif di **kedua** paruh DAN
total jam yang dibuang ≤ 4. Kalau harus buang 8 jam untuk dapat efek, itu
overfitting terhadap 1,4 tahun.

**File.** `sessions.py` sudah punya `hour_utc`. Gate opsional di
`_momentum_fib`. Ini pengganti yang jujur untuk ranking sesi lama yang
diukur pada label salah.

**Jebakan.** 24 kelompok = 24 percobaan. Ambang "negatif di kedua paruh"
ada justru untuk itu.

### 3.7 Panel insight makro di dashboard

Bukan riset — ini untuk pemilik, bukan bot. Tambah ke
`src/monitoring/dashboard.py`: tren DXY H4, event kalender 24 jam ke depan
(setelah 3.2 ada), rezim volatilitas hari ini (ATR percentile), posisi harga
terhadap Asia range hari ini, skor Tokyo (setelah 3.3). **Tidak masuk jalur
sinyal.** Tujuannya mengumpulkan intuisi tanpa mengontaminasi forward test.

### 3.8 Ukur ulang docs/25 dan docs/26

Keduanya diukur pada data yang `time_utc`-nya meleset 7 jam. Untuk docs/25
itu fatal: jendela NFP/CPI dicocokkan ke jam yang salah, jadi "reaksi
berita" yang diuji bukan bar berita. Kesimpulan "berita tidak bisa
dipercaya" sendiri belum bisa dipercaya. Jalankan ulang dengan kalender
sesungguhnya setelah 3.2 tersedia. Untuk docs/26, uji lead-lag DXY/silver
di M5 kemungkinan tetap nol (itu memang horizon yang salah), tetapi ukur
ulang tetap wajib sebelum mengutip angkanya.

### 3.9 COT + yield riil (hanya untuk H1)

Relevan hanya bila kandidat H1 di `docs/30` §2 dijalankan (butuh modal
Rp 17–45 jt). Positioning COT (mingguan, CFTC gratis) dan yield riil 10 thn
(FRED, harian) sebagai filter rezim untuk trend-following — kombinasi klasik.
Tidak ada gunanya di M5. Jangan kerjakan sebelum H1 di-port ke
`backtest/engine.py`.

---

## 4. Yang sengaja TIDAK ada di daftar

| ide | kenapa tidak |
|---|---|
| Pola candle (engulfing, doji, hammer, dst) | pin bar −0,084R; 30+ pola = jebakan multiple testing. Satu-satunya pemakaian sah: **veto** wick berlawanan > 60% range, satu aturan, satu uji |
| Mean reversion di M5 | Tokyo MR t = −4,76. Spread memakan kedua arah |
| Breakout Asia range | 4 varian negatif di London open sesungguhnya (docs/30 §1.1) |
| Multi-posisi / hedging | eksposur nol dengan spread ganda; tunda sampai forward test lolos (docs/29 §10e) |
| ML meta-labeling | AUC ~0,50 dan bocor optimis (docs/27 §9). Baru masuk akal setelah rule engine punya edge terbukti |
| Ganti ke EURUSD | pemilik memutuskan fokus XAUUSD |

---

## 5. Prosedur eksekusi — wajib

1. **Satu ide per jendela forward test.** Uji di backtest → kalau lolos,
   pasang di demo → kumpulkan ~100 trade → baru ide berikutnya. Tiga ide
   sekaligus = tidak akan pernah tahu mana yang bekerja.
2. **Tulis hipotesis dan ambang di dokumen ini SEBELUM menjalankan uji.**
   Bagian 3 sudah mengisinya untuk 6 ide pertama. Ide baru harus mengikuti
   format yang sama.
3. **Matikan halt DD saat mengukur** (`bt.max_dd = 999`). Halt 20% adalah
   guardrail operasional, bukan alat ukur — docs/30 §0.1 menunjukkan ia
   memotong backtest 168 hari.
4. **Laporkan selalu:** n, E[R], SE, t, kedua paruh, DD, dan "tahun yang
   dibutuhkan untuk t=2". Bukan cuma E[R].
5. **Validasi di data yang tidak dipakai memilih:** M15 (4,23 thn) untuk
   ide yang tidak bergantung timeframe; paruh kedua M5 untuk yang bergantung.
6. **Ambang t ≥ 3** untuk klaim apa pun dari data M5 yang sama. Di bawah
   itu, statusnya "menarik, belum terbukti" — boleh dipasang di demo,
   tidak boleh jadi dasar akun real.
7. **Jangan ubah setelan yang sedang forward test** (ATR 0,20–0,95,
   RR 1:2,78) untuk mengakomodasi ide baru. Ide baru diuji sebagai
   *tambahan* pada setelan itu, bukan pengganti.
8. Setiap uji yang dijalankan **di-commit sebagai skrip** di `scripts/`.
   Angka tanpa skrip yang menghasilkannya adalah anekdot (pelajaran
   docs/27 §10).

---

## 6. Alat yang sudah tersedia

```bash
python scripts/fix_time_offset.py --check        # data harus lolos ini dulu
python scripts/measure_sessions.py               # E[R] per sesi, dengan SE
python scripts/sweep_frequency.py --rr 2.78      # sapuan gate (LooseEngine)
python scripts/compare_live_vs_backtest.py       # forward test vs backtest
python tests/test_risk_manager.py                # 13 tes
python tests/test_order_safety.py                # 7 tes, tanpa MT5
```

`scripts/sweep_frequency.py::LooseEngine` adalah pola yang disarankan untuk
menguji varian: subclass `RuleEngine`, timpa satu detektor, jangan sentuh
`setups.py` sampai varian lolos ambang.

Lingkungan: `MetaTrader5` hanya ada di Windows dengan terminal terpasang.
Backtest dan tes tidak membutuhkannya (`tests/test_order_safety.py`
memalsukan modulnya). Dependensi di `requirements.txt`.
