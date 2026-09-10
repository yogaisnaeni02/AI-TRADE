# Rencana Pengembangan Lanjutan

**Tanggal:** 10 September 2026
**Konteks:** forward test demo sedang berjalan (mode EXECUTOR, momentum_fib,
ATR 0,20–0,95, RR 1:2,78). Dokumen ini menutup kekurangan yang masih
terbuka dari `docs/27-AUDIT-TEMUAN.md`, disusun agar bisa dikerjakan
**tanpa mengganggu** bot yang sedang mengumpulkan trade.

Prinsip urutan: **keselamatan dulu, alat ukur kedua, riset terakhir.**
Selama forward test berjalan, jangan sentuh logika sinyal — mengubahnya di
tengah jalan membuat trade yang terkumpul tidak bisa dibandingkan.

---

## Ringkasan prioritas

| # | Pekerjaan | Kenapa sekarang | Sentuh sinyal? | Perkiraan |
|---|---|---|---|---|
| 1 | SL gagal pasang = posisi telanjang | bisa rugi tak terbatas | tidak | jam |
| 2 | Bot mati saat koneksi putus | posisi ditinggalkan tanpa trailing | tidak | jam |
| 3 | `r_multiple` kosong di journal | tanpa ini forward test tak terukur | tidak | jam |
| 4 | Notifikasi kegagalan | bot mati diam-diam tak ketahuan | tidak | jam |
| 5 | Circuit breaker yang belum ada | 3 dari 4 tidak diimplementasi | tidak | hari |
| 6 | Kalender berita | filter fail-OPEN saat ini | tidak | hari |
| 7 | Uji config mati | cegah kelas bug berulang | tidak | jam |
| 8 | Tes untuk backtest engine | tak ada tes sama sekali | tidak | hari |
| 9 | Evaluasi forward test | keputusan real/tidak | ya, setelah | — |
| 10 | Riset lanjutan | kalau nomor 9 lolos | ya | minggu |

Nomor 1–8 aman dikerjakan sambil forward test jalan.

---

## 1. SL gagal pasang → posisi telanjang (KRITIS)

**Kondisi sekarang** — `src/execution/order_manager.py:121-127`:

```python
positions = mt5.positions_get(symbol=self.symbol)
if positions:
    for p in positions:
        if p.ticket == result.order or p.magic == MAGIC:
            if p.sl == 0.0:
                self.modify_position(p.ticket, sl, tp)   # <- hasil TIDAK dicek
            break
```

Tiga celah, berurutan dari yang paling berbahaya:

1. `modify_position()` mengembalikan hasil, tapi **nilainya dibuang**. Kalau
   gagal, posisi tetap terbuka tanpa SL dan bot melaporkan "ORDER OK".
2. Kalau `positions_get()` mengembalikan `None` atau list kosong (lag
   broker), blok ini dilewati sepenuhnya — tidak ada verifikasi sama sekali.
3. Tidak ada penutupan darurat. Posisi tanpa SL pada XAUUSD dengan leverage
   2000 bisa menghabiskan akun dalam satu pergerakan.

**Rencana:**

- Ambil nilai balik `modify_position`, dan bila gagal ulangi sampai 3x
  dengan jeda pendek.
- Bila setelah 3x SL masih `0.0`, **tutup posisi segera** dan `halt()`
  sistem. Rugi kecil yang disengaja jauh lebih baik daripada posisi tanpa
  batas.
- Perlakukan `positions_get()` kosong sebagai KEGAGALAN, bukan sukses diam.
- Kirim notifikasi Telegram pada tiap kejadian.

**Cara uji tanpa broker:** buat `FakeOrderManager` yang mensimulasikan
`modify_position` gagal, lalu pastikan posisi ditutup dan sistem halt.

---

## 2. Bot mati saat koneksi terputus (KRITIS)

**Kondisi sekarang** — `src/execution/bot.py`:

```python
except Exception as e:  # noqa: BLE001
    self.log(f"ERROR siklus: {type(e).__name__}: {e}")
    self.gw.ensure_connected()      # <- ini sendiri bisa melempar
```

`ensure_connected()` melempar ulang `ConnectionError` bila percobaan
terakhir gagal. Karena dipanggil **di dalam** blok `except` tanpa pelindung,
lemparan itu keluar dari `try` dan mematikan proses.

Akibatnya MT5 tersendat ~5 detik (restart terminal, Wi-Fi putus, update
broker) → bot mati permanen, posisi terbuka ditinggalkan tanpa trailing,
tanpa break-even, tanpa `max_bars_hold`. Yang tersisa hanya SL/TP di server.

**Rencana:**

- Bungkus `ensure_connected()` dalam `try/except` sendiri.
- Backoff bertingkat (5s → 15s → 60s), loop **terus mencoba**, tidak pernah
  menyerah selama masih ada posisi terbuka.
- Hitung durasi putus; bila melewati `circuit_breaker.mt5_disconnect_seconds`
  (30), kirim notifikasi — jangan matikan bot, justru posisi terbuka
  membutuhkan bot tetap hidup.
- Perbaiki baris log terakhir yang keliru melaporkan "0 posisi" saat
  koneksi sedang mati.

---

## 3. `r_multiple` kosong di journal

`src/monitoring/journal.py:109` mengisi `r_multiple` hanya bila
`risk_per_trade_idr` diberikan, dan `bot.py` memanggil
`sync_closed_trades(days_back=7)` **tanpa argumen itu**. Jadi kolomnya
selalu kosong.

Dampaknya langsung ke forward test: tanpa `r_multiple`, hasil live tidak
bisa dibandingkan dengan backtest (E[R] +0,1749R). Yang bisa dibandingkan
cuma winrate — padahal winrate bukan penentu profitabilitas.

**Rencana:**

- Simpan `risk_amount` per ticket saat order dibuka (sudah ada di
  `_entry_info`), lalu oper ke `sync_closed_trades`.
- Untuk trade lama yang sudah tercatat, hitung mundur dari `lot` dan jarak
  SL saat entry.
- Tambah `scripts/compare_live_vs_backtest.py`: baca `logs/trades.csv`,
  hitung E[R] live dengan standard error, bandingkan terhadap +0,1749R,
  dan laporkan apakah selisihnya di dalam noise.

**Ini yang paling mendesak untuk forward test** — tanpa alat ukur, 7 bulan
data tidak akan menjawab apa pun.

---

## 4. Notifikasi kegagalan

`notifier.py` memberi tahu hasil order, tetapi tidak ada yang memberi tahu
kalau **bot mati**. Bot yang berhenti diam-diam terlihat sama persis dengan
bot yang sedang menunggu sinyal.

**Rencana:**

- Kirim notifikasi saat: bot start, bot berhenti (termasuk karena exception),
  halt karena guardrail, koneksi putus melewati ambang, dan SL gagal pasang.
- Heartbeat harian: ringkasan trade, P/L, drawdown, status.
- Isi `telegram.bot_token` dan `chat_id` lewat **variabel lingkungan**, bukan
  di `settings.yaml` — file itu ter-commit ke repo publik.

---

## 5. Circuit breaker yang belum diimplementasi

Dari empat yang tercatat di `risk_limits.yaml`, hanya satu yang benar-benar
ada:

| Breaker | Status |
|---|---|
| `consecutive_order_failures` | ada (`manager.py:279`) |
| `mt5_disconnect_seconds` | **0 referensi** |
| `spread_abnormal_multiplier` | **0 referensi** |
| `price_anomaly_atr_multiple` | **0 referensi** |

**Rencana:** implementasikan tiga sisanya. `spread_abnormal_multiplier`
paling bernilai — spread Exness memang fixed 260 points, jadi lonjakan
mendadak adalah sinyal kuat ada yang tidak beres (berita besar, masalah
likuiditas, atau feed rusak).

Blok `forbidden:` (martingale, averaging_down, widening_sl) punya **0
referensi** di seluruh kode, padahal komentarnya mengklaim "dikunci di
kode". Sebagian sudah dijamin struktur (bot hanya 1 posisi, SL monotonik
berlapis dua). **Rencana:** jadikan tes yang membuktikan klaim itu, lalu
perbaiki komentar config agar tidak menjanjikan yang tidak ada.

---

## 6. Kalender berita

`bot.py` tidak pernah mengoper `news_blackout`, sehingga default `False` —
filter **fail-OPEN**, kebalikan dari `fail_closed: true` di config. Tidak
ada sumber kalender sama sekali.

XAUUSD sangat sensitif terhadap NFP, CPI, dan FOMC. Spread bisa melebar
berkali-kali lipat dan slippage jauh melampaui asumsi 30 points.

**Rencana:**

- Ambil kalender dari sumber gratis (ForexFactory JSON / Finnhub), cache ke
  disk harian.
- Oper `news_blackout` ke `risk.check()`.
- Hormati `fail_closed: true` — bila sumber gagal dan cache basi, **jangan
  trading**.
- Backtest ulang dengan filter berita aktif untuk mengukur dampaknya.

---

## 7. Uji config yang tidak dikonsumsi

Sudah lima kali ditemukan blok config yang dibaca sebagai kebijakan padahal
kodenya berjalan sendiri: `sessions`, `forbidden`, sebagian
`circuit_breaker`, `news_filter`, `live_ramp`. Ini pola sistemik, bukan lima
bug terpisah.

**Rencana:** tes yang membaca semua kunci di kedua file YAML, mencocokkan
dengan grep ke seluruh `src/` + `backtest/`, lalu **gagal** bila ada kunci
yang tidak pernah dibaca. Kunci yang memang sengaja dokumentatif didaftarkan
dalam allowlist eksplisit.

Ini mencegah seluruh kelas bug, bukan menambal satu per satu.

---

## 8. Tes untuk backtest engine

`tests/test_risk_manager.py` sudah ada (13 tes). Backtest engine — sumber
setiap angka keputusan — belum punya tes sama sekali.

**Rencana:** tes dengan data sintetis yang hasilnya bisa dihitung tangan:

- entry di bar berikutnya, bukan bar sinyal
- spread + slippage benar-benar terpotong
- SL dan TP kena di bar yang sama → pesimis (SL menang)
- trailing tidak pernah melebarkan SL
- `max_bars_hold` benar-benar memotong
- R-multiple sesuai definisi
- **regresi lookahead**: pastikan bug 13x yang dulu ditemukan tidak kembali

---

## 9. Evaluasi forward test (gerbang keputusan)

**Jangan ubah apa pun di jalur sinyal sampai tahap ini selesai.**

Target: ~200 trade (≈4 bulan pada 635 trade/tahun). Evaluasi di 50, 100,
dan 200 trade.

Acuan pembanding:

| Metrik | Backtest | Ambang bahaya |
|---|---|---|
| E[R] | +0,1254R | negatif di n ≥ 100 |
| Winrate | 29,9% | di bawah 28,17% (breakeven) |
| Trade/hari kalender | 1,74 | jauh lebih kecil = ada yang salah |
| Profit factor | 1,22 | di bawah 1,0 |

**Aturan yang ditetapkan SEKARANG, sebelum ada uang di meja:**

- E[R] live positif dan CI 95%-nya tidak memuat nol pada n ≥ 200 → boleh
  bicara akun real, mulai dari risiko 0,5%.
- E[R] live negatif pada n ≥ 100 → hentikan, kembali ke riset.
- Winrate live jauh di bawah 28,17% pada n ≥ 50 → hentikan lebih awal.

Menetapkan ambang sebelum data masuk adalah satu-satunya cara mencegah
rasionalisasi setelah melihat hasilnya.

---

## 10. Riset lanjutan (hanya bila nomor 9 lolos)

Diurutkan berdasarkan potensi, bukan kemudahan.

**a. Jawab pertanyaan M5 vs M15.** Setelan sekarang positif di kedua paruh
M5 tetapi negatif di M15 (−0,141R atas 4,23 tahun). Dua tafsir belum
terpisahkan: edge khas M5, atau artefak 1,41 tahun data. Uji di M1 sebagai
timeframe tetangga, dan unduh M5 lebih panjang di luar batas 100.000 bar.

**b. Kurangi multiple testing.** `t = 2,25` berasal dari 22 kombinasi pada
data yang sama; ambang jujurnya ~2,9. Sisihkan periode holdout yang tidak
pernah disentuh sampai keputusan akhir.

**c. Entry presisi lewat M1.** SL 400 pip diperlukan karena entry di close
bar M5. Entry di M1 pada level lebih tepat bisa menurunkan SL ke 200–300
pip — menaikkan RR untuk semua target sekaligus.

**d. Reversal pada sinyal berlawanan.** Menggantikan ide "pilih arah pakai
confidence score" yang dibatalkan karena skor terbukti tidak memprediksi
(korelasi −0,006; skor 6 = +0,361R, skor 8 = −0,219R). Yang benar: bila
sinyal berlawanan muncul, **tutup posisi lama lalu buka yang baru** — satu
posisi, satu arah, sekali bayar spread. Dua posisi berlawanan di simbol yang
sama adalah eksposur nol dengan biaya spread ganda.

**e. Multi-posisi searah.** Hanya setelah (d) terbukti dan forward test
lolos. `max_open_positions: 1` adalah guardrail paling andal yang ada;
menaikkannya melipatgandakan eksposur.

**f. EURUSD.** Rasio ATR terhadap spread jauh lebih longgar daripada XAUUSD
(spread 26 pip adalah handicap struktural). Kode sudah instrument-agnostic;
data sudah ada di `data_eurusd/`. Tetap relevan bila XAUUSD mentok.

**g. ML sebagai penyaring.** Baru masuk akal setelah rule engine punya edge
yang terbukti. Perbaiki dulu kebocoran yang tercatat di `docs/27` bagian 9:
fold test dipakai sebagai validation early stopping, dan barrier dihitung
tanpa spread.

---

## Yang TIDAK boleh dikerjakan sekarang

- Mengubah logika sinyal selama forward test berjalan
- Menaikkan risiko di atas 1,35%
- Menaikkan `max_open_positions`
- Memakai confidence score untuk keputusan apa pun
- Mengarahkan ke akun real sebelum gerbang nomor 9 terlampaui
