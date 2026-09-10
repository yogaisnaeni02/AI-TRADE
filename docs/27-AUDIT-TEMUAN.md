# Audit Independen — Temuan

**Tanggal:** 10 September 2026 (revisi 2 — menggantikan seluruh versi sebelumnya)
**Metode:** Analisis statis kode + verifikasi aritmetika + pemeriksaan empiris
langsung ke file `.parquet`. Setiap temuan menyebut file dan baris.
**Cakupan:** dua gelombang audit dengan refutasi adversarial per temuan.
Bagian 12 mencatat klaim yang ditarik beserta alasannya.

---

## Ringkasan eksekutif

Enam hal yang menentukan, urut kepentingan:

1. **Data historis salah label waktu 7 jam.** Kolom `time_utc` di seluruh
   `data/*.parquet` adalah UTC dikurangi 7 jam. Dibuktikan dari data, bukan dari
   pembacaan kode. Bot live memakai waktu yang benar, sehingga backtest dan live
   memperdagangkan jam yang berbeda.
2. **Tidak ada satu pun batas kerugian yang berfungsi.** `record_trade()` tidak
   pernah dipanggil dari mana pun, sehingga batas harian, mingguan, dan loss
   beruntun tidak pernah terisi — bahkan tanpa restart.
3. **Basis bukti setup aktif hanya 136 trade,** bukan 8.971. Angka 8.971 milik
   setup lain yang sudah dinonaktifkan.
4. **Setup aktif dibajak setup nonaktif** sebelum sempat dievaluasi.
5. **Batas risiko 1% tidak berlaku;** risiko nyata 1,35–1,89%.
6. **Blok config dibaca sebagai kebijakan padahal mati:** `sessions`,
   `forbidden`, sebagian `circuit_breaker`, `news_filter`, `live_ramp`.

Nomor 1–4 mengarah ke satu kesimpulan: **angka-angka di `docs/` tidak mengukur
sistem yang sedang berjalan.** Itu harus dibereskan sebelum ada pertanyaan apa
pun tentang edge.

---

## 1. Data historis meleset 7 jam — dibuktikan dari data

`src/data/downloader.py:85-88` mengurangi konstanta config dari waktu server:

```python
offset_hours = cfg["broker"].get("server_utc_offset", 7)   # settings.yaml -> 7
df["time_server"] = df["time"]
df["time"] = df["time"] - pd.Timedelta(hours=offset_hours)
df = df.rename(columns={"time": "time_utc"})
```

### Bukti empiris (menentukan)

Dijalankan langsung atas `data/raw/XAUUSDm_M5.parquet`, n=100.000:

```
selisih time_server - time_utc : tepat 7:00:00

                Jumat tutup   Minggu buka
  time_utc        14:55         15:00
  time_server     21:55         22:00
```

Pasar forex tutup Jumat ~21:00–22:00 UTC dan buka lagi Minggu ~21:00–22:00 UTC
(17:00 New York). Kolom yang cocok dengan kenyataan adalah **`time_server`**,
bukan `time_utc`.

**Kesimpulan: `time_server` sudah UTC yang benar; `time_utc` = UTC − 7 jam.**
Artinya `server_utc_offset: 7` salah — server broker ini UTC+0, dan downloader
mengurangi 7 jam dari nilai yang sudah UTC.

Ini konsisten dengan insiden yang dicatat developer sendiri di
`src/data/mt5_gateway.py:136-138`: *"bot mengira jam 12:35 WIB padahal
sebenarnya 19:37 WIB, selisih 7 jam sesuai offset lama."* Jalur live sudah
diperbaiki; downloader dan seluruh data tidak.

### Akibatnya pada klasifikasi sesi backtest

| Label di backtest | Jendela `time_utc` | Jam UTC sebenarnya | Jam WIB sebenarnya | trade |
|---|---|---|---|---|
| `asia` | 23:00–07:00 | 06:00–14:00 | 13:00–21:00 | **false** |
| `london_open` | 07:00–10:00 | 14:00–17:00 | 21:00–00:00 | true |
| `pre_ny` | 10:00–12:30 | 17:00–19:30 | 00:00–02:30 | false |
| `london_ny` | 12:30–16:00 | 19:30–23:00 | 02:30–06:00 | true |
| `ny_afternoon` | 16:00–21:00 | 23:00–04:00 | 06:00–11:00 | true |
| `rollover` | 21:00–23:00 | 04:00–06:00 | 11:00–13:00 | true |

Sesi London yang sesungguhnya (06:00–14:00 UTC) justru berlabel `asia` dengan
`trade=false` — **tidak pernah diuji sama sekali.** Yang diuji sebagai
`ny_afternoon` sebenarnya sesi Tokyo.

### Backtest dan live memperdagangkan jam berbeda

- Offline (`downloader.py:85`): offset **statis 7** dari config.
- Live (`bot.py:159-160`): `offset = detect_server_offset_hours()` → **0**.

Bot live memakai UTC yang benar dan berdagang di jam yang benar, sementara
setiap kalibrasi berasal dari jam yang salah. Forward test yang berjalan bukan
verifikasi backtest — ia menguji populasi jam yang berbeda.

**Yang TIDAK terpengaruh:** data harga (OHLC) benar. Kalibrasi yang tidak
bergantung jam — ATR median, range bar, SL optimal — tetap sahih. Yang batal
adalah semua yang dikondisikan pada sesi: filter sesi, Asia range,
`friday_cutoff`, dan seluruh label ML.

**Perbaikan (murah):** `time_server` sudah ada di setiap parquet dan sudah
benar. Setel `server_utc_offset: 0` setelah verifikasi, bangun ulang `time_utc`
dari `time_server`, jalankan ulang pipeline. Tidak perlu unduh ulang.

**Verifikasi yang harus dijalankan saat MT5 hidup** (metode di kode mencampur
zona waktu laptop):

```python
from datetime import datetime, timezone
import MetaTrader5 as mt5
mt5.initialize()
t = mt5.symbol_info_tick("XAUUSDm").time
print("server:", datetime.fromtimestamp(t, tz=timezone.utc))
print("UTC   :", datetime.now(timezone.utc))
# selisihnya = offset server sebenarnya
```

---

## 2. Tidak ada satu pun batas kerugian yang berfungsi

`grep -rn "record_trade" .` di seluruh repo menghasilkan **satu baris:
definisinya sendiri.** Nol pemanggil.

```
src/risk/manager.py:268:    def record_trade(self, pnl: float) -> None:
```

Fungsi itu satu-satunya yang mengisi state:

```python
def record_trade(self, pnl: float) -> None:
    self.state.day_pnl += pnl
    self.state.week_pnl += pnl
    self.state.day_trades += 1
    self.state.consecutive_losses = (
        self.state.consecutive_losses + 1 if pnl < 0 else 0
    )
```

Karena tidak pernah dipanggil, keempat batas ini **permanen bernilai nol**:

| Batas | Nilai config | Status nyata |
|---|---|---|
| `daily.max_loss_percent` | 4,0% | tidak pernah menyala |
| `daily.max_trades` | 6 | tidak pernah menyala |
| `daily.max_consecutive_losses` | 3 | tidak pernah menyala |
| `weekly.max_loss_percent` | 8,0% | tidak pernah menyala |

Bot bisa rugi sepuluh kali beruntun dalam satu hari tanpa satu pun rem aktif.
(`record_order_failure` memang dipanggil di `bot.py:395` — hanya itu.)

### Diperparah: state tidak persisten

`SessionState` (`manager.py:42-54`) dataclass biasa tanpa persistensi.
`logs/snapshot.json` hanya **ditulis** (`bot.py:142`) dan dibaca hanya oleh
dashboard — tidak pernah dimuat kembali. Ditambah `bot.py:470`:

```python
self.risk.state.peak_equity = acc.equity    # setiap START
```

Sehingga `peak_equity` selalu direset ke equity saat ini, drawdown selalu
terbaca 0%, dan **kill switch 20% beserta tangga derisking 10/15/20% tidak
pernah menyala setelah restart.**

Yang benar-benar tersisa sebagai pengaman hanyalah `max_open_positions: 1`
(dievaluasi terhadap state broker langsung, jadi andal) dan SL per posisi.

**Perbaikan:** rekonsiliasi posisi tertutup tiap siklus lewat
`mt5.history_deals_get` — infrastrukturnya sudah ada di `journal.py`, yang sudah
mengelompokkan deal per `position_id` dan menyaring magic — lalu panggil
`record_trade(net_pnl)`. Persistkan `SessionState` ke disk dan muat saat start;
`peak_equity` harus `max(tersimpan, equity)`.

**Ini prioritas nomor satu sebelum akun real disentuh.**

---

## 3. Basis bukti setup aktif: 136 trade, bukan 8.971

Dibaca langsung dari artefak yang ter-commit:

| File | n | setup | E[R] | SE | t | winrate |
|---|---|---|---|---|---|---|
| `trades_momentum_fib.parquet` | **136** | momentum_fib | +0,0932 | 0,1385 | **0,67** | 39,71% |
| `trades_final.parquet` | 29 | **ny_vol_window** | −0,0429 | 0,3118 | −0,14 | 31,03% |
| `trades_baseline.parquet` | 21 | london_sweep, ny_momentum | −0,3000 | 0,2875 | −1,04 | 23,81% |
| `signals_final.parquet` | 1.412 | momentum_fib | — | — | — | — |

Yang harus digarisbawahi:

- Artefak bernama **`trades_final`** berisi **`ny_vol_window`** — setup yang
  dinonaktifkan — dan hanya mencakup **9 hari** (15–24 Apr 2025).
- Angka **8.971** yang dipakai di `settings.yaml:60` ("Semua pada 8.971 entry")
  dan di seluruh perbandingan varian trailing merujuk jendela NY milik
  `ny_vol_window`, **bukan `momentum_fib`.** Tidak ada artefak di repo yang
  memuat 8.971 baris.
- Karena itu tabel keputusan trailing di `settings.yaml` mengalibrasi setup yang
  **tidak dipakai**, lalu menerapkan hasilnya ke setup yang dipakai.

### Statistik yang benar untuk setup aktif

Pada n=136, E[R]=+0,0932, sd=1,6153:

```
SE = 1,6153 / sqrt(136) = 0,1385
t  = 0,0932 / 0,1385 = 0,67          -> tidak signifikan
CI 95% = [-0,179 ; +0,365]           -> memuat nol dengan longgar
```

Jumlah trade untuk membuktikan edge sebesar +0,0932R (95%, power 80%):

```
N = (1,96 + 0,84)^2 x 1,6153^2 / 0,0932^2 = 2.355 trade
```

Pada laju artefak (136 trade dalam 9 bulan ≈ 181/tahun) → **sekitar 13 tahun.**

### Seleksi dari 11 konfigurasi

Kriteria "4 dari 5 fold walk-forward positif":

```
P(X >= 4 | n=5, p=0,5) = 6/32 = 0,1875 per konfigurasi
P(minimal satu dari 11 lolos | semua edge nol) = 1 - (1-0,1875)^11 = 89,8%
```

Kriteria itu tidak menyaring apa pun. Untuk 6 varian trailing yang dibandingkan
pada trade yang sama, angkanya 71,2%.

**Kesimpulan:** tidak ada bukti edge, dan sampelnya jauh lebih kecil dari yang
diyakini. Ditambah bagian 1, sampel kecil itu pun diukur pada jam yang salah.

---

## 4. Setup nonaktif membajak setup aktif

`src/strategy/setups.py:476-490` memakai first-match-wins:

```python
for detector in (
    self._ny_vol_window,      # <-- dievaluasi PERTAMA, padahal nonaktif
    self._momentum_fib,       # <-- satu-satunya yang aktif di config
    self._london_sweep,
    self._ny_momentum,
):
    sig = detector(row)
    if sig and sig.score >= min_score:
        signals.append(sig)
        found = True
        break                 # momentum_fib tak pernah dievaluasi di bar ini
```

Skor minimum `ny_vol_window` (5) sama persis dengan `min_score` default bot (5),
jadi `break` selalu terjadi lebih dulu. Setiap bar di `ny_afternoon`/`rollover`
dengan `atr_percentile` di (0,60 ; 0,85] diklaim setup nonaktif, lalu sinyalnya
**dibuang senyap** oleh `bot.py:323` karena setup-nya tidak ada di
`active_setups`. Tidak ada log penolakan.

Akibatnya `momentum_fib` tidak pernah dievaluasi di sebagian bar yang justru
paling relevan baginya — tanpa jejak apa pun bahwa itu terjadi.

**Perbaikan:** saring setup di HULU — susun tuple detektor dari `active_setups`
sehingga setup nonaktif tidak pernah dipanggil. Minimal: hapus `break`,
kumpulkan semua sinyal per bar, pilih skor tertinggi di antara yang diizinkan.
Ganti `return` senyap di `bot.py:323` dengan log.

---

## 5. Backtest tidak mencerminkan bot live

Selain perbedaan waktu (bagian 1):

| Aspek | Backtest | Live |
|---|---|---|
| Holding period | `engine.py:151` hardcode `max_bars=120` (10 jam); `run()` tak pernah mengoper config | `bot.py:250` pakai `max_bars_hold: 48` (4 jam) |
| Batas risiko | `engine.py` pakai `max_risk_percent` | `manager.py:258` pakai `max_lot_percent` (bagian 7) |
| `initial_equity` | default `800_000` (`engine.py:287`, `metrics.py:14`) | 5,2 juta |
| Break-even | mengunci ~1,65R | `bot.py:229` mengunci 0,065R — mekanisme berbeda |
| ATR saat manajemen | bar sudah selesai | `bot.py:206` memakai bar BELUM selesai; ATR ~7% lebih kecil |
| Ambang momentum | `rolling(2000)` | `bot.py:197-198` `rolling(2000)` di atas frame 1500 bar — **mustahil terisi** |
| `max_bars_hold` | indeks bar | `bot.py:248` menghitung iterasi loop di memori; restart → nol |
| `deviation` | `slippage_assume_points: 30` | `order_manager.py:32` hardcode 50 |

Pada equity 800.000 dengan lot terkunci 0,01, risiko per trade = 8,7%. Setiap
kurva equity, max drawdown, dan logika `halted` yang dihitung dengan default itu
tidak valid. R-multiple tetap sahih (skala-invariant); metrik berbasis equity
tidak.

### Yang sudah BENAR di engine (jangan diubah)

- Entry di bar berikutnya (`entry_idx = sig["idx"] + 1`)
- Spread + slippage dibayar di entry, slippage tambahan saat SL kena
- Ambiguitas SL/TP dalam satu bar → pesimis (SL duluan), dengan opsi resolusi M1
- Trailing di-update SETELAH pengecekan SL/TP, memakai close bar yang sudah
  selesai. Komentar `engine.py:190` mencatat versi lama punya lookahead yang
  melaporkan hasil 13x lebih baik — perbaikan itu benar dan penting.
- `resampler.py:48` `label="left", closed="left"` — konvensi kausal yang benar

Engine-nya jujur. Masalahnya di parameter dan di data yang dimasukkan.

---

## 6. Guardrail dan blok config yang mati

| Diyakini aktif | Kenyataan |
|---|---|
| News filter `fail_closed: true` | `bot.py:341` tidak pernah mengoper `news_blackout`; default `False` di `manager.py:194`. **Fail OPEN.** Tidak ada sumber kalender sama sekali. |
| `forbidden:` "dikunci di kode" | **0 referensi** ke martingale/averaging_down/widening. Murni komentar. |
| `circuit_breaker` | Hanya `consecutive_order_failures` dibaca. `mt5_disconnect_seconds`, `spread_abnormal_multiplier`, `price_anomaly_atr_multiple` → 0 referensi. |
| Blok `sessions:` | **`cfg["sessions"]` 0 referensi.** Kebijakan sesi hardcode di `sessions.py:24-33` dan `setups.py`. Config terbaca terbalik: `ny_afternoon` tertulis `trade: false` tapi ditradingkan; `london_open` tertulis `true` tapi `momentum_fib` tidak memakainya. |
| Tangga OBSERVER→ADVISOR→EXECUTOR | Tidak diimplementasikan. `bot.py:372` hanya mengecek `!= "EXECUTOR"`. |

Dead config lain (0 referensi): `live_ramp`, `withdrawal`, `at_equity_multiple`,
`minutes_before`, `fail_closed`, `swap_long`, `frequent_micro_max_daily_trades`.

Ini pola sistemik, bukan lima bug terpisah: **config diperlakukan sebagai
dokumentasi kebijakan, sementara kode berjalan sendiri.** Perbaikan yang benar
bukan menambal satu per satu, melainkan uji start-up yang gagal keras bila ada
kunci config yang tidak dikonsumsi kode mana pun.

### Proteksi akun real hanya peringatan

`src/execution/bot.py:462`

```python
if self.mode == "EXECUTOR" and not is_demo:
    self.log("!! AKUN REAL terdeteksi di mode EXECUTOR.")
    self.log("!! Hentikan sekarang bila ini tidak disengaja (Ctrl+C).")
    time.sleep(10)              # lalu LANJUT trading
```

`time.sleep(10)`, bukan `sys.exit(1)`.

---

## 7. Batas risiko 1% tidak berlaku

`src/risk/manager.py:258` membandingkan risiko aktual terhadap
`max_lot_percent_equity` (**5,0%**), bukan `max_risk_percent` (**1,0%**).

Lot minimum 0,01 mengunci risiko pada nilai tetap:

```
4000 points x Rp 1.748,36/point x 0,01 lot = Rp 69.934 per trade
```

| Equity | Risiko nyata |
|---|---|
| Rp 5.198.659 (live) | **1,35%** |
| Rp 3.700.000 (`min_equity_idr`) | **1,89%** |
| Rp 6.993.440 | 1,00% |

Penolakan baru terjadi di equity < Rp 1.398.688 — padahal `min_equity_idr` sudah
memblokir di Rp 3,7 juta. Jadi tidak pernah ditolak.

Efek samping: **`size_tier: "reduced"` tidak berefek apa pun** — lantai lot
minimum membuat kedua tier memakai risiko identik (`manager.py:177`). Seluruh
skema tiered sizing di `risk_limits.yaml` adalah no-op.

---

## 8. Eksekusi order dan ketahanan

**Posisi telanjang tanpa SL dilaporkan "ORDER OK"** (`order_manager.py:115-121`):
kegagalan memasang SL diabaikan total, tidak ada penutupan darurat. Penanganan
retcode biner — hanya `DONE` diterima, `DONE_PARTIAL` dilaporkan gagal padahal
posisi terbuka.

**Gangguan koneksi beberapa detik mematikan bot dengan posisi terbuka**
(`bot.py:497-499`): `ensure_connected()` dipanggil di dalam blok `except` tanpa
pelindung, dan melempar ulang bila percobaan terakhir gagal. MT5 tersendat ~5
detik → proses mati permanen, posisi ditinggalkan tanpa trailing, tanpa
break-even, tanpa `max_bars_hold`. Baris log terakhir keliru melaporkan
"0 posisi".

**Log break-even ditulis SEBELUM order dikirim** (`bot.py:232`); kegagalan
modify dan kegagalan close sepenuhnya senyap.

Yang sudah benar: SL/TP dikirim menyatu dalam satu `TRADE_ACTION_DEAL`;
monotonisitas SL dijaga berlapis dua (`order_manager.py:147-151` + `bot.py:239`)
dan tidak ada jalur yang bisa melebarkan SL; `_filling_mode()` memetakan bitmask
dengan benar; idempotensi per-bar dijaga `_last_bar_time`; bot tidak bisa
menyentuh posisi milik orang lain.

---

## 9. Machine learning

Yang **sudah benar** (hipotesis umum yang terbantah): split BUKAN KFold acak —
`train.py:101-110` memakai expanding walk-forward terurut waktu tanpa shuffle;
`purge_bars=100` > span label 48 bar sehingga purging memadai; tidak ada scaler
yang di-fit ke seluruh dataset; fitur di `src/features/` kausal (nol
`center=True`, nol `shift(-n)`, nol `bfill`; merge HTF memakai
`available_at = time + durasi TF`).

Yang **bocor**:

- **Fold test dipakai sekaligus sebagai validation set early stopping**
  (`train.py:116-125`): `best_iteration` adalah argmax metrik atas maksimum 400
  snapshot, dievaluasi pada fold yang dilaporkan sebagai out-of-sample.
- **Barrier triple-barrier dihitung pada harga mid tanpa spread**, padahal
  backtester membayar spread. Base rate 23,65% yang jadi fondasi tabel keputusan
  di `docs/11` optimistis ~1,6pp — lebih besar dari celah yang dikejar proyek.
- Threshold dipilih dengan `idxmax` di atas fold test (`train.py:159`).
- `meta_model.txt` adalah model fold terakhir: dilatih pada 83% data tertua,
  iterasinya di-fit ke fold test-nya sendiri, tak pernah dilatih ulang di data
  penuh.
- Bobot uniqueness memakai konkurensi di bar awal saja; jumlah sinyal yang
  dilaporkan melebih-lebihkan bukti independen ~8–17x.

Arah bias semuanya **optimistis**. Artinya kesimpulan negatif `docs/11`
("AUC ~0,50, tidak ada edge") kemungkinan masih terlalu murah hati.

Model ini tidak dipakai runtime: 0 referensi `meta_model`/`predict` di
`src/execution/` maupun `src/strategy/`.

---

## 10. Reproduktibilitas dan higiene repo

- **`scripts/` hanya berisi `phase0_probe.py`.** Semua script kalibrasi,
  backtest, dan training yang menghasilkan angka di `docs/` tidak ada di repo.
  Tidak satu pun hasil bisa direproduksi — ini juga sebabnya angka 8.971 tidak
  bisa dilacak ke artefak mana pun.
- `phase0_probe.py` **tidak pernah mengukur offset server sama sekali**,
  sehingga klaim "server = WIB, terverifikasi Tahap 0" tidak berdasar.
- **229 MB parquet ter-commit** (`data/` 180M, `data_eurusd/` 45M,
  `data_corr/` 4,3M). `.git` sudah 91 MB.
- `config/settings.yaml` ter-track berisi nomor akun 463942909 dan server. Field
  `telegram.bot_token` akan ikut ter-commit begitu diisi.
- `logs/snapshot.json` dan `logs/trades.csv` ter-track (equity, nomor tiket).
  `.gitignore` hanya mengecualikan `logs/*.log`.
- **Tidak ada** `requirements.txt`, `pyproject.toml`, lockfile, atau pin versi
  Python.
- **Tidak ada satu pun tes.** Modul paling berbahaya untuk tidak diuji:
  `src/risk/manager.py` dan `src/execution/order_manager.py`.
- `logs/trades.csv` punya kolom `r_multiple` yang selalu kosong — tanpa itu
  tidak ada cara membandingkan performa live terhadap backtest.

---

## 11. Rekomendasi, urut dampak

**Sistem tidak boleh menyentuh akun real** sampai butir 1–3 selesai. Di demo,
biarkan jalan bila ingin mengamati perilaku.

1. **Pulihkan batas kerugian** (bagian 2). Panggil `record_trade()` dari
   rekonsiliasi `history_deals_get`; persistkan `SessionState`;
   `peak_equity = max(tersimpan, equity)`. Tanpa ini tidak ada rem sama
   sekali. — *jam*
2. **Betulkan waktu** (bagian 1). Verifikasi offset dengan cara yang benar,
   setel `server_utc_offset`, bangun ulang `time_utc` dari `time_server`,
   jalankan ulang pipeline. Satukan sumber waktu offline dan live jadi satu
   fungsi. Tambahkan pengaman start-up: bila offset terdeteksi ≠ offset metadata
   dataset, ABORT. — *jam*
3. **Abort pada akun real** (`bot.py:462`), dan saring setup di hulu
   (bagian 4). — *jam*
4. **Jalankan ulang seluruh kalibrasi** setelah 1–3. Semua angka di `docs/`
   harus dianggap batal sampai diproduksi ulang dari data berlabel benar oleh
   script yang ter-commit. Perlakukan sebagai pengukuran pertama, bukan
   pengulangan. — *hari*
5. **Tetapkan ambang statistik sebelum menguji apa pun lagi.** Tolak klaim
   dengan |t| < 2; laporkan CI, bukan titik estimasi; catat jumlah hipotesis
   yang diuji. Ini membatalkan sebagian besar keputusan trailing/tiering yang
   sudah diambil, dan mencegah iterasi berikutnya mengulang kesalahan yang
   sama. — *jam*
6. **Commit script penghasil angka.** Tanpa itu angka apa pun adalah anekdot. — *jam*
7. **Uji start-up untuk config yang tidak dikonsumsi** (bagian 6) — gagal keras
   bila ada kunci yang tidak dibaca kode mana pun. Ini mencegah kelas bug yang
   sudah muncul lima kali. — *jam*
8. **Pertimbangkan pindah instrumen.** Spread 26 pip di XAUUSD adalah sumber
   kesulitan struktural, bukan kualitas setup. Data EURUSD sudah ada dan kode
   instrument-agnostic. **Tapi kerjakan setelah 1–4** — memindahkan instrumen
   dengan pipeline waktu yang rusak hanya memindahkan masalahnya. — *minggu*

### Penilaian jujur

Infrastrukturnya solid dan backtest engine-nya lebih jujur dari kebanyakan —
lookahead 13x yang ditemukan dan diperbaiki sendiri adalah pekerjaan bagus.
Tetapi audit ini menemukan bahwa sistem belum pernah benar-benar diukur:
datanya salah label waktu, sampelnya jauh lebih kecil dari yang diyakini, setup
aktifnya dibajak sebelum sempat jalan, dan tidak ada batas kerugian yang
berfungsi.

Kabar baiknya, tidak satu pun dari empat hal itu sulit diperbaiki — semuanya
hitungan jam, bukan minggu, dan `time_server` yang benar sudah tersimpan di
setiap file. Pertanyaan "apakah ada edge" belum bisa dijawab sekarang, karena
belum pernah diajukan pada data yang benar. Itu kabar yang jauh lebih baik
daripada "sudah diukur dengan benar dan hasilnya nol".

---

## 12. Klaim yang ditarik

Dicatat agar revisi ini tidak perlu diaudit ulang.

**Ditarik — "klasifikasi sesi meleset 1 jam karena DST."** Salah. Pergeseran
sebenarnya 7 jam dan berasal dari `server_utc_offset` yang keliru, bukan DST.
DST tetap relevan sebagai isu kecil (ambang UTC tetap tidak mengikuti
London/NY), tapi tertelan masalah 7 jam.

**Ditarik — "`time_utc` sudah benar UTC, kekhawatiran 7 jam tidak berdasar."**
Ini kesimpulan revisi 1 dan **salah**. Ia bersandar pada asumsi bahwa
`server_utc_offset: 7` benar. Bukti empiris di bagian 1 (batas akhir pekan
21:55/22:00 pada `time_server` vs 14:55/15:00 pada `time_utc`) menunjukkan
asumsi itu keliru.

**Ditarik — "`friday_cutoff` hardcode 14.0 tidak cocok dengan config 21:00."**
Salah sebagai bug: 14:00 UTC = 21:00 WIB, dan komentar `sessions.py:80`
menyatakannya. Tetap benar sebagai catatan pemeliharaan (nilainya hardcode
sehingga config tidak diikuti), dan dalam kerangka bagian 1 jendela itu tetap
salah sasaran karena datanya sendiri salah label.

**Dikoreksi — N=8.971.** Revisi 1 memakai angka ini untuk seluruh aritmetika
signifikansi. Angka itu milik `ny_vol_window`. N sebenarnya untuk setup aktif
adalah 136 (bagian 3). Arah koreksinya membuat bukti **lebih lemah**, bukan
lebih kuat.
