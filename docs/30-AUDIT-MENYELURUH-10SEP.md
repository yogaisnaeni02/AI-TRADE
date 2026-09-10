# Audit Menyeluruh — 10 September 2026

**Pemicu:** curiga ada bug setelah merge, dan bot tidak membuka posisi
selama berjam-jam.

---

## Ringkasan Eksekutif

Ditemukan **satu bug kritis** yang membuat sistem memperdagangkan jam yang
salah selama ini, dan **dua masalah operasional** yang menjelaskan kenapa
bot tampak diam.

Setelah bug diperbaiki, backtest berubah dari **−0,150R (49 trade)** menjadi
**+0,160R (632 trade, 5/5 fold positif)**.

---

## BUG KRITIS: Label sesi meleset 7 jam

### Apa yang terjadi

`config/settings.yaml` sudah dikoreksi ke `server_utc_offset: 0` (benar,
sudah diverifikasi dua cara). Tetapi batas jam di `src/strategy/sessions.py`
**tidak ikut dikoreksi** — nilainya masih dihitung dengan asumsi lama
"WIB dikurangi 7".

Akibatnya setiap bar mendapat label sesi yang meleset 7 jam:

| Jam UTC | Sesi sesungguhnya | Label lama | Status lama |
|---|---|---|---|
| 00–03 | Tokyo/Asia | `ny_afternoon` | **ditradingkan** |
| 07–13 | **London (paling likuid)** | `asia` | **DIBLOKIR** |
| 14–16 | Overlap London-NY | `london_open` | ditradingkan |
| 17–19 | NY sore | `pre_ny` | DIBLOKIR |

**Sesi London — jam paling likuid dalam sehari — tidak pernah
ditradingkan sama sekali.**

### Bukti independen

Volatilitas median per jam UTC (dari 100.000 bar M5):

```
13:00 UTC  608 pip   <- puncak
14:00 UTC  624 pip   <- puncak
15:00 UTC  507 pip
01:00 UTC  530 pip   <- tinggi, tapi dilabeli "asia" dan diblokir
```

Puncak volatilitas di 13:00–15:00 UTC persis cocok dengan overlap
London-NY yang sesungguhnya — konfirmasi bahwa kolom `time_utc` memang
sudah UTC murni, dan batas jam lama yang salah.

### Perbaikan

`src/strategy/sessions.py` — batas jam disetel ke jam pasar sesungguhnya
(UTC), dan seluruh sesi dibuka:

```python
SESSIONS = [
    ("asia",         23.0,  7.0, True),
    ("london_open",   7.0, 12.0, True),
    ("london_ny",    12.0, 16.0, True),   # paling likuid
    ("ny_afternoon", 16.0, 21.0, True),
    ("rollover",     21.0, 23.0, True),
]
```

Semua sesi dibuka karena ranking sesi lama diukur pada label yang salah —
tidak bisa dipakai. Seleksi sekarang diserahkan ke filter kualitas
(momentum/ATR/fib).

### Dampak terukur

| | Sebelum | Sesudah |
|---|---|---|
| Sinyal | 8,77/hari | **14,12/hari** |
| Trade tereksekusi | 49 | **632** |
| Winrate | 22,4% | **31,5%** |
| Expectancy | **−0,150R** | **+0,160R** |
| Profit Factor | 0,80 | **1,25** |
| Walk-forward | — | **5/5 fold positif** |
| In-sample / Out-of-sample | — | +0,164R / **+0,153R** |
| Max Drawdown | 20,1% | 20,2% |

Selisih IS dan OOS hanya 0,011R — tanda edge yang stabil, bukan hasil
tuning.

---

## Verifikasi Kewajaran Hasil

Hasil sebaik itu wajib dicurigai. Empat pemeriksaan dilakukan:

| Pemeriksaan | Hasil |
|---|---|
| Trade tumpang tindih (harus 1 posisi/waktu) | **0 dari 631** — bersih |
| Distribusi outcome | 446 SL / 171 TP / 15 timeout — wajar |
| Sebaran per jam | merata di 23 jam, tidak menumpuk 1-2 jam |
| Out-of-sample | +0,153R vs IS +0,164R — konsisten |

### Anomali yang diperiksa: R-multiple 3,177 > RR 2,78

Awalnya tampak seperti bug (profit melebihi TP). Setelah ditelusuri:
**bukan bug**.

`tp_min_points: 11120` adalah **lantai tetap**, bukan hasil `SL × RR`.
SL sendiri berbasis ATR dan bervariasi 3500–4500 points. Ketika SL turun
ke 3500, rasio TP/SL naik ke 3,177. Perilaku ini sesuai desain dan
`r_multiple` konsisten dengan risiko nominal tiap trade.

---

## MASALAH OPERASIONAL

### 1. Bot tidak berjalan sama sekali di PC ini

Snapshot terakhir dari **9 Sep 21:40** (20 jam sebelum audit), dan tidak
ada proses `run_bot.py` yang hidup. Log terakhir:

```
[21:37:16] File STOP ada — bot idle, tidak membuka posisi baru.
[21:40:31] ERROR siklus: RuntimeError: gagal ambil M5: (-10001, 'IPC send failed')
```

Bot dihentikan oleh file STOP, lalu kehilangan koneksi MT5.

Catatan: bot dijalankan di PC lain, jadi log di PC ini bukan gambaran
kondisi bot yang sebenarnya.

### 2. Bot di PC lain belum membuka posisi apapun

Diperiksa langsung ke akun MT5 (sumber kebenaran yang sama untuk semua
PC):

```
Deal dari bot (magic 20260909) dalam 24 jam: 1
  09-09 20:15:01 BUY 0.01 @ 4413.544  <- ini dari PC ini, bukan PC lain
```

Bot di PC lain **belum menghasilkan satu order pun**. Ini konsisten
dengan bug sesi: sesi London (jam 07–13 UTC = 14:00–20:00 WIB) diblokir,
padahal itu jam kerja utama.

### 3. Lock file yatim

`logs/bot.lock` berisi PID 24928 yang sudah mati. Kode `_acquire_lock()`
sebenarnya sudah bisa mendeteksi PID mati dan mengambil alih lock, jadi
ini tidak memblokir start — tetapi tetap perlu dibersihkan.

---

## Temuan Minor

### `config['sessions']` tidak dipakai kode

Blok `sessions:` di `settings.yaml` (dengan jam WIB) **tidak pernah dibaca
oleh kode manapun** — diverifikasi dengan grep di seluruh `src/` dan
`backtest/`. Isinya juga sudah usang (menyebut UTC+7).

Blok ini menyesatkan: pembaca config bisa mengira jam trading diatur di
sana, padahal yang berlaku adalah `SESSIONS` di `sessions.py`.

### Parameter backtest dan live sudah konsisten

Diperiksa dan cocok:

```
breakeven_at_r : 2.4  (backtest = live)
trail_atr_mult : 2.0  (backtest = live)
max_bars_hold  : 48   (backtest = live)
```

Ini penting — perbedaan di sini pernah jadi bug sebelumnya (backtest
menahan 10 jam, live 4 jam) dan sekarang sudah beres.

---

## Yang Perlu Dilakukan

1. **Restart bot di PC yang menjalankannya** — perbaikan sesi baru berlaku
   setelah proses di-restart (Python tidak me-reload modul yang sudah
   dimuat)
2. **Pastikan `git pull`** di PC itu supaya dapat `sessions.py` yang sudah
   diperbaiki
3. Hapus `logs/bot.lock` bila bot menolak start

---

## Catatan Kehati-hatian

Expectancy +0,160R dengan 632 trade jauh lebih kuat daripada basis bukti
sebelumnya (49 trade). Tetapi:

- Ini tetap **backtest**, bukan hasil live
- Max drawdown 20,2% masih menyentuh ambang circuit breaker (20%) —
  sistem bisa berhenti sendiri saat periode buruk
- Sesi dibuka semua tanpa seleksi; setelah forward test mengumpulkan
  cukup sampel, sesi layak diukur ulang dengan label yang sekarang sudah
  benar
