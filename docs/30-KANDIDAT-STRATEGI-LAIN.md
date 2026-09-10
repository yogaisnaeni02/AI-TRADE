# Kandidat Strategi Lain — Satu Aman, Satu Berisiko

**Tanggal:** 10 September 2026
**Pertanyaan:** adakah strategi lain yang aman, dan satu yang lebih berisiko
tapi masih layak dijalankan?
**Data:** semua pengukuran memakai data yang sudah dikoreksi waktunya
(`docs/27` bagian 1) dan **tanpa halt drawdown** di dalam backtest.

---

## 0. Temuan yang mengubah angka sebelumnya

Sebelum mencari strategi baru, dua hal ditemukan yang mengoreksi angka lama.

### 0.1 Backtest sebelumnya terpotong

`backtest/engine.py` menghentikan simulasi begitu drawdown menyentuh
`global.max_drawdown_percent` (20%). Semua angka di `docs/28` revisi 1 diukur
dengan halt itu aktif — backtest berhenti **25 Maret 2026, 168 hari sebelum
akhir data**.

| | terpotong (docs/28 rev 1) | periode penuh |
|---|---|---|
| trade | 513 | **721** |
| E[R] | +0,1749 | **+0,1557** |
| t | 2,25 | **2,38** |
| max drawdown | 20,1% | **32,1%** |
| trade/tahun | 363 | **510** |

Pilihan kalibrasi (ATR 0,20–0,95, RR 1:2,78) **tetap terbaik** pada periode
penuh, jadi config tidak berubah. Yang berubah adalah pemahaman risikonya:
drawdown alami strategi ini 32%, sehingga kill switch 20% **diharapkan
menyala** kira-kira sekali per 1,4 tahun. Itu rem bekerja, bukan kerusakan.

### 0.2 Tujuh strategi yang pernah ditolak, ditolak pada jam yang salah

`docs/24` mencatat 7 strategi alternatif yang semuanya negatif. Ketujuhnya
lewat `_passes_gates(require_session=True)` — difilter ke jam yang meleset
7 jam. "Opening range breakout London" yang tercatat −0,1185R sebenarnya
menguji pagi New York. Sebagian diukur ulang di bawah.

### 0.3 Data H1/H4 sebelum 2017 rusak

| tahun | close median | ATR H1 (pts) | ATR/close | bar/tahun |
|---|---|---|---|---|
| 2014–2016 | 1.168–1.279 | **13.400–14.700** | **~1,1%** | **~300** |
| 2017–2019 | 1.261–1.406 | 2.200–2.400 | 0,17% | ~5.900 |

ATR per jam 1,1% dari harga pada emas $1.250 itu mustahil, dan 300 bar per
tahun bukan H1. Tiga tahun pertama file H1 (dan kemungkinan H4) adalah
timeframe lain yang salah label. Klaim `docs/broker-specs.md` "H1 ~5 tahun,
H4 ~9 tahun" harus dibaca sebagai **9,7 tahun H1 yang sahih (2017+)**.
Semua uji H1 di bawah membuang pre-2017.

---

## 1. Kandidat AMAN — hasilnya: tidak ada yang baru di M5

Empat ide "aman" diuji. **Semuanya negatif.** Ini ditulis lengkap justru
supaya tidak diulang.

### 1.1 Asia-range breakout di London open (sesungguhnya)

Sesi London asli (07:00–10:00 UTC) tidak pernah diuji sebelumnya karena
salah label. Sekarang diuji: break pertama Asia high/low, SL di dalam range
(cap 4.500 pts), satu trade per hari.

| varian | n | E[R] | t | WR% | PF | DD |
|---|---|---|---|---|---|---|
| RR 1:2, filter trend HTF | 142 | −0,103 | −0,89 | 30,3 | 0,85 | 34% |
| RR 1:2, tanpa filter | 225 | −0,080 | −0,87 | 31,6 | 0,88 | 44% |
| RR 1:2,78, filter trend | 142 | −0,047 | −0,34 | 26,1 | 0,94 | 29% |
| SL cap 3.000 | 142 | −0,120 | −1,03 | 29,6 | 0,83 | 28% |

Asia range median **43.648 pts ($43,6)** — jauh lebih lebar dari SL 4.500.
Jadi ini bukan "breakout dengan SL di sisi lain range", melainkan breakout
dengan SL kecil di dalam range lebar → mudah tersapu.

### 1.2 Setup lama, diukur ulang pada jam yang benar

| setup | n | E[R] | t | WR% | PF | DD |
|---|---|---|---|---|---|---|
| london_sweep | 205 | −0,155 | −1,44 | 24,4 | 0,80 | 64% |
| ny_momentum | 75 | +0,026 | 0,13 | 26,7 | 1,07 | 14% |
| ny_vol_window | 507 | −0,136 | **−1,95** | 24,1 | 0,82 | 100% |

`ny_vol_window` — setup yang angkanya (8.971 trade) dulu dipakai untuk
mengalibrasi trailing — hampir signifikan **negatif**.

### 1.3 Mean reversion sesi Tokyo (23:00–07:00 UTC)

Fade deviasi dari EMA50 (dalam satuan ATR), target kembali ke mean.

| varian | n | E[R] | t | WR% |
|---|---|---|---|---|
| dev ≥ 2,0 ATR, RR 1:1 | 504 | −0,209 | **−4,76** | 39,9 |
| dev ≥ 2,0, RR 1:0,75 | 563 | −0,176 | −4,74 | 47,4 |
| dev ≥ 1,5, RR 1:1 | 756 | −0,131 | −3,59 | 43,8 |

**Ini hasil paling signifikan di seluruh proyek — t = −4,76 — hanya arahnya
salah.** Menahan pergerakan Tokyo secara konsisten rugi.

### 1.4 Sinyal Tokyo dibalik (ikut arah deviasi)

Kalau fade rugi signifikan, apakah ikut arah untung?

| varian | n | E[R] | t | paruh-1 | paruh-2 |
|---|---|---|---|---|---|
| Tokyo, dev ≥ 2, RR 1:2 | 1.394 | −0,025 | −0,65 | −0,026 | −0,024 |
| 24 jam, dev ≥ 2, RR 1:2,78 | 1.689 | −0,011 | −0,28 | −0,037 | +0,015 |

**Tidak.** Fade rugi −0,21R, ikut arah rugi −0,02R. Selisihnya bukan edge
momentum — itu **spread memakan kedua arah**, dengan fade lebih parah karena
RR 1:1 memberi TP yang terlalu dekat dengan spread. Tokyo tidak punya edge
yang bisa diambil di salah satu arah pun.

### 1.5 Kesimpulan kandidat aman

Tidak ada strategi M5 lain yang mengalahkan `momentum_fib`. Kalau "aman"
diartikan **variansnya lebih kecil**, jawabannya bukan strategi baru
melainkan **ukuran posisi**: strategi yang sama pada risiko 0,5–0,75% per
trade memangkas drawdown 32% menjadi ~12–18%, dengan expectancy per trade
tidak berubah. Itu satu-satunya "versi aman" yang terbukti ada.

Saudara yang layak dipantau (bukan diganti): ATR 0,20–0,85 memberi DD 23%
dengan E[R] serupa (+0,137, t 1,99). Tidak dipakai karena mengganti lagi
berarti menambah percobaan pada data yang sama.

---

## 2. Kandidat BERISIKO — trend-following H1, 9,7 tahun data

Satu-satunya kandidat yang lolos dengan bukti lintas-tahun.

### 2.1 Kenapa H1 menyerang akar masalah

Dua masalah struktural XAUUSD di broker ini adalah spread 26 pip dan sampel
kecil. H1 menyerang keduanya sekaligus:

- **Spread relatif mengecil.** ATR H1 pada rezim 2025–2026 = 10.000–20.000
  pts. Dengan SL 3×ATR, spread 260 pts hanya **0,4–0,9% dari risiko**, versus
  6,5% di M5. Handicap yang membuat "celah 0,7pp" mustahil dilampaui di M5
  praktis hilang.
- **Sampel 7x lebih panjang.** 9,7 tahun H1 sahih vs 1,41 tahun M5 — melewati
  rezim $1.200, $1.800, $2.400, $3.300, $4.500.

### 2.2 Hasil (Donchian breakout, spread + slippage dibayar, 2017–2026)

| varian | n | n/thn | E[R] | t | WR% | tahun positif | loss beruntun | DD (R) |
|---|---|---|---|---|---|---|---|---|
| D20/10, SL 2×ATR | 1.752 | 181 | +0,045 | 0,98 | 30,5 | 6/10 | 16 | 68 |
| D55/20, SL 2×ATR | 875 | 90 | +0,123 | 1,48 | 29,3 | 6/10 | 17 | 50 |
| **D20/10, SL 3×ATR** | **1.576** | **163** | **+0,062** | **1,76** | **35,3** | **8/10** | **13** | **32** |
| D40/15, SL 2,5×ATR | 1.039 | 107 | +0,103 | 1,77 | 33,7 | 7/10 | 14 | 45 |
| D10/5, SL 2×ATR | 2.876 | 297 | +0,008 | 0,30 | 32,8 | 5/10 | 13 | 87 |

Per tahun untuk D20/10 SL 2×ATR: 2017 +0,11 · 2018 −0,17 · 2019 −0,05 ·
2020 +0,39 · 2021 −0,14 · 2022 −0,04 · 2023 +0,10 · 2024 +0,00 · 2025 +0,17 ·
2026 +0,28.

**Semua lima varian positif**, dan yang terbaik positif di 8 dari 10 tahun.
Tidak satu pun mencapai t ≥ 2 — tetapi konsistensi lintas 10 tahun dan lima
rezim harga jauh lebih berbobot daripada t 2,38 dari 1,4 tahun. Ini bukan
klaim edge besar; ini klaim edge **kecil yang bertahan lama**, yang memang
ciri trend-following.

### 2.3 Kenapa ini "berisiko" — dan risikonya nyata

**Drawdown dalam satuan R: 32–68R.** Itu angka yang menentukan segalanya:

| risiko/trade | DD varian terbaik (32R) | DD varian D20/10 2×ATR (68R) |
|---|---|---|
| 1,35% | **43%** | **91%** |
| 0,75% | 24% | 51% |
| 0,50% | 16% | 34% |

Trend-following H1 **hanya hidup pada risiko kecil per trade**. Dan di sini
lot minimum menggigit:

| SL | risiko 0,01 lot | % dari Rp 5,2 jt | butuh untuk 1,35% | butuh untuk 0,5% |
|---|---|---|---|---|
| 1,5×ATR (6.500 pts) | Rp 114.000 | 2,2% | Rp 8,4 jt | Rp 22,8 jt |
| 2×ATR (8.700 pts) | Rp 152.000 | 2,9% | Rp 11,3 jt | Rp 30,4 jt |
| 3×ATR (13.000 pts) | Rp 228.000 | 4,4% | Rp 16,9 jt | Rp 45,6 jt |

Pada equity sekarang, varian terbaik (3×ATR) memaksa risiko **4,4% per
trade** → drawdown yang diharapkan **~140%**. Akun habis. **Strategi ini
membutuhkan modal Rp 17–45 juta**, bukan Rp 5 juta.

Risiko lain yang belum masuk hitungan:

- **Swap.** `swap_long: -526.4`, satuannya tidak tercatat probe. Bila itu
  points per lot per malam (lazim di MT5), biayanya ≈ Rp 8.700/malam pada
  0,01 lot. Rata-rata posisi H1 menginap ~1,5 malam → ~Rp 13.000 per trade
  long ≈ **0,09R** — hampir separuh edge D20/10 3×ATR untuk sisi long. Bila
  satuannya mata uang deposit, biayanya Rp 5/malam dan bisa diabaikan.
  **Wajib diukur** (tambahkan `swap_mode` ke probe) sebelum melangkah.
- **Loss beruntun 13–17** adalah normal, bukan anomali. Secara psikologis
  ini yang membunuh trend-follower, bukan matematikanya.
- Diuji dengan simulator sendiri, bukan `backtest/engine.py` — perlu
  di-port supaya memakai model biaya yang sama.

### 2.4 Kapan layak dijalankan

1. Equity ≥ Rp 17 juta (untuk risiko ≤ 1,35% pada SL 3×ATR), idealnya
   ≥ Rp 30 juta.
2. `swap_mode` terukur dan biayanya masuk backtest.
3. Di-port ke `backtest/engine.py` dan hasilnya tidak berubah material.
4. Berjalan **berdampingan** dengan momentum_fib, bukan menggantikannya —
   dua edge yang tidak berkorelasi (intraday momentum vs multi-day trend)
   saling melunakkan drawdown.

---

## 3. Ringkasan keputusan

| | Aman | Berisiko |
|---|---|---|
| Strategi | momentum_fib (yang ada) pada risiko 0,5–0,75% | Donchian 20/10 SL 3×ATR di H1 |
| Bukti | +0,156R, t 2,38, 1,4 tahun, kedua paruh positif | +0,062R, t 1,76, 9,7 tahun, 8/10 tahun positif |
| Drawdown yang diharapkan | 12–18% | 16% @0,5% · 43% @1,35% |
| Modal minimum | Rp 5 jt (sudah) | **Rp 17–45 jt** |
| Blocker | forward test belum selesai | modal, swap belum terukur, belum di-port |
| Tindakan | jalan terus | tunggu modal; ukur swap dulu |

**Yang paling penting dari dokumen ini:** semua strategi "aman" baru di M5
gagal, dan gagalnya bersih — bukan karena kurang data, tapi karena spread
26 pip tidak menyisakan ruang di timeframe itu untuk apa pun selain
momentum yang sudah ada. Kalau ingin edge kedua, jalannya **naik
timeframe**, dan itu berarti **modal**, bukan ide baru.

### Hitungan percobaan

Sesi ini menambah ~25 varian pada data M5 yang sama (ORB 4, setup lama 4,
Tokyo MR 5, Tokyo dibalik 5, sapuan ATR 6) dan 5 varian H1. Total percobaan
pada M5 kini melampaui 50. Ambang t yang jujur untuk klaim apa pun dari data
M5 ini sekarang sekitar **3,0**. Tidak ada yang mencapainya — termasuk
momentum_fib (2,38). Forward test tetap satu-satunya bukti yang tidak
terkontaminasi.

---

## 4. Cara mengulang

```bash
python scripts/fix_time_offset.py --check     # data harus lolos dulu
python scripts/sweep_frequency.py --rr 2.78   # sapuan ATR (matikan halt: bt.max_dd=999)
```

Uji ORB, Tokyo, dan H1 di dokumen ini dijalankan sebagai skrip sekali pakai;
logikanya tercatat di bagian masing-masing. Bila salah satu akan dilanjutkan,
langkah pertamanya adalah menjadikannya detektor di `setups.py` supaya diukur
oleh engine yang sama dengan momentum_fib.
