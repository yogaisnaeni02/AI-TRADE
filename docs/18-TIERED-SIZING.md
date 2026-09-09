# "Realtime Terus, Ambil Peluang Kecil dan Besar Sekaligus"

**Tanggal:** 9 September 2026
**Permintaan:** "Buat realtime terus, peluang kecil tetap diambil biar
progress terus, peluang besar juga jangan sampai terlewat."

---

## Ringkasan

Ide Anda diterjemahkan menjadi **tiered position sizing**: dua tingkat
kualitas sinyal, keduanya diambil, ukuran risiko beda sesuai kualitas. Ini
konsep yang valid dan sudah dibangun.

Tetapi pengujian mengungkap tiga hal yang perlu dipahami sebelum
dijalankan:

1. Tidak semua "peluang kecil" boleh diambil — ada titik di mana kecil
   berubah jadi rugi
2. Bahkan tier yang menguntungkan secara statistik, saat diuji lewat
   backtest lengkap (dengan seluruh guardrail), hasilnya negatif
3. Penyebabnya bukan sinyalnya — melainkan **batas keamanan sendiri**
   yang mematikan sistem sebelum expectancy jangka panjang sempat terwujud

---

## 1. Sejauh Mana "Peluang Kecil" Boleh Dilonggarkan

Syarat momentum dilonggarkan bertahap, diukur terhadap breakeven 25,41%:

| Tier | Sinyal/hari | Winrate | vs breakeven | Status |
|---|---|---|---|---|
| **Besar** (skor penuh) | 2,7 | 32,25% | **+6,84%** | Untung |
| **+ momentum longgar 50%** | 4,2 | 30,77% | **+5,36%** | Untung |
| + tanpa filter ATR | 8,5 | 27,75% | +2,34% | Untung |
| + tanpa filter sesi | 23,6 | 25,33% | **−0,08%** | **Rugi** |
| + momentum sangat longgar | 87,2 | 23,97% | −1,44% | Rugi |
| Tanpa filter sama sekali | 167,2 | 23,65% | −1,76% | Rugi |

**Dua tier teratas menguntungkan. Selebihnya merugi.** Ada garis nyata di
mana "peluang kecil" berhenti menjadi peluang.

Sistem dibangun memakai dua tier yang terbukti untung:

```
Tier FULL    : mom_24 > 100% ambang  -> risiko 1x (1%)
Tier REDUCED : mom_24 > 50% ambang   -> risiko 0,5x (0,5%)
Di bawah 50% : TIDAK diambil sama sekali
```

---

## 2. Implementasi

### Rule engine (`src/strategy/setups.py`)

```python
if row.mom_24 > row.mom_24_q85:
    size_tier = "full"
elif row.mom_24 > row.mom_24_q85 * 0.5:
    size_tier = "reduced"
else:
    return None  # di bawah ini tidak diambil
```

### Risk manager (`src/risk/manager.py`)

```python
if size_tier == "reduced":
    risk_pct *= reduced_risk_multiplier  # 0.5
```

### Konfigurasi (`config/risk_limits.yaml`)

```yaml
tiered_sizing:
  reduced_risk_multiplier: 0.5
```

Dengan ini, sinyal tier kecil tetap diambil (progress terus) dengan risiko
setengah dari sinyal tier besar (tidak melewatkan yang besar, tidak
gegabah di yang kecil).

---

## 3. Analisis Sederhana vs Backtest Lengkap

Ini bagian yang mengubah kesimpulan.

### Analisis sederhana (label saja, tanpa guardrail)

```
Tier full     : n=1.417  E=+0,225R
Tier reduced  : n=764    E=+0,166R
Gabungan/hari : 0,618% -> 0,700% (naik)
```

Terlihat menjanjikan.

### Backtest lengkap (dengan risk manager penuh)

```
Hanya tier full        : n=31   E=-0,345R
Tiered (full+reduced)  : n=46   E=-0,199R
```

**Keduanya negatif** — meski tiered lebih baik daripada full-only.

### Mengapa selisihnya sebesar ini

Dari 1.306 sinyal yang dihasilkan, hanya **46 (3,5%) yang benar-benar
tereksekusi**. Sisanya diblokir oleh:

| Batasan | Nilai |
|---|---|
| Maksimal 1 posisi terbuka | Sinyal baru ditolak selama posisi lama masih jalan |
| Maksimal 6 trade/hari | Sinyal ke-7 dst hari itu ditolak |
| 3 loss beruntun | Stop sisa hari |
| **Max drawdown 20%** | **Sistem berhenti total** |

Baris terakhir adalah penyebab utamanya.

---

## 4. Penemuan Inti: Circuit Breaker Mematikan Sistem Sebelum Pulih

Diuji dengan menaikkan batas `max_drawdown_percent`:

| Batas DD | Trade tereksekusi | Winrate | Expectancy |
|---|---|---|---|
| **20% (sekarang)** | 46 | 21,7% | **−0,199R** |
| 30% | 52 | 19,2% | −0,292R |
| **50%** | **286** | **29,4%** | **+0,040R** |
| 80% | 286 | 29,4% | +0,040R |

Pada batas 20%, sistem terkena rentetan rugi di awal periode, **berhenti
total**, dan tidak pernah sampai ke periode yang lebih baik. Sampelnya
terlalu kecil (46 trade) untuk expectancy jangka panjang terwujud.

Pada batas 50%, sistem bertahan melewati periode buruk dan sampai ke 286
trade — expectancy positif tipis (+0,040R) mulai terlihat.

**Ini bukan berarti circuit breaker di 20% salah.** Batas itu dipasang
untuk melindungi modal riil — dan itu bekerja persis seperti dirancang:
menghentikan sistem sebelum kerugian membesar. Yang terungkap adalah
**strategi ini butuh lebih banyak sampel daripada yang bisa diberikan
circuit breaker konservatif** sebelum edge-nya (yang tipis) sempat
terbukti secara statistik.

---

## 5. Apa Artinya untuk "Realtime Terus"

### Yang bisa dijalankan sekarang

Mekanisme tiered sizing sudah aktif di kode. Bot akan:
- Mengambil sinyal tier "full" dengan risiko 1%
- Mengambil sinyal tier "reduced" dengan risiko 0,5%
- Menolak apa pun di bawah tier reduced

Ini menaikkan frekuensi dari 2,7 ke sekitar **4,2 sinyal/hari** — tanpa
masuk ke zona yang terbukti rugi.

### Yang belum bisa dijamin

Backtest dengan guardrail penuh menunjukkan hasil masih negatif pada
sampel kecil (46 trade, dibatasi circuit breaker 20% DD). Ini konsisten
dengan status sistem secara keseluruhan: **strategi belum lolos validasi
penuh** (dokumen 07, 09, 12).

Tiered sizing memperbaiki *arah* (dari −0,345R ke −0,199R), tetapi tidak
mengubah kesimpulan bahwa edge sistem ini masih terlalu tipis untuk
diandalkan pada sampel kecil.

---

## 6. Trade-off yang Perlu Diputuskan

| Pilihan | Konsekuensi |
|---|---|
| **Pertahankan max DD 20%** | Modal lebih terlindungi, tetapi sistem bisa berhenti sebelum edge terbukti (seperti temuan di atas) |
| **Naikkan max DD ke 30-35%** | Sistem bertahan lebih lama untuk kumpulkan sampel, tetapi risiko kerugian lebih dalam bila edge ternyata tidak nyata |

**Rekomendasi: pertahankan 20%.** Modal Rp 3,7 juta ini untuk *validasi*,
bukan untuk dipertaruhkan lebih dalam demi mengumpulkan data. Bila circuit
breaker terpicu, itu sinyal untuk berhenti dan mengevaluasi — bukan
menaikkan toleransi risiko agar bisa terus jalan.

Forward test jangka panjang (mingguan/bulanan, bukan sekali jalan) akan
mengumpulkan sampel yang cukup tanpa perlu melonggarkan batas keamanan.

---

## 7. Ringkasan

| Pertanyaan | Jawaban |
|---|---|
| Bisa ambil peluang kecil dan besar sekaligus? | **Ya** — tiered sizing sudah dibangun |
| Semua peluang kecil aman diambil? | **Tidak** — ada garis tegas di WR 25,33% |
| Tiered sizing memperbaiki hasil? | **Ya**, dari −0,345R ke −0,199R |
| Sudah profitable? | **Belum** — masih negatif pada sampel kecil |
| Kenapa? | Circuit breaker (DD 20%) membatasi sampel sebelum edge terbukti |
| Apa yang harus dilakukan? | Forward test jangka panjang, bukan naikkan toleransi risiko |

Ide Anda benar secara konsep dan sudah diimplementasikan. Yang membatasi
bukan idenya — melainkan kenyataan bahwa strategi dasarnya sendiri masih
perlu dibuktikan dengan sampel yang lebih besar daripada yang bisa
diberikan satu sesi backtest dengan guardrail ketat.

---

## 8. Update: Setup Frequent-Micro (permintaan "1 sinyal/jam")

**Tanggal:** 9 September 2026 (lanjutan)

Dibangun sebagai setup **terpisah** (`frequent_micro`, di `run_bot_frequent.py`),
tidak mengubah sistem utama (`momentum_fib`) yang tetap berjalan.

### Batas frekuensi yang sungguh-sungguh masih untung

| Kelonggaran | Sinyal/hari | Winrate | vs breakeven |
|---|---|---|---|
| Sekarang (semua sesi, momentum 100%) | 6,70 | 27,35% | +1,94% |
| **momentum 50%, fib ketat, ATR normal** | **11,65** | **25,62%** | **+0,21%** |
| momentum 30% | 13,72 | 25,33% | −0,08% (rugi) |

**"1 sinyal per jam" (~24/hari) tidak pernah tercapai sambil tetap
untung** — semua kombinasi di atas 12–14 sinyal/hari sudah di bawah
breakeven. Titik paling longgar yang masih untung adalah **~1 sinyal per
2 jam** (11,65/hari), dengan marjin sangat tipis (+0,21%).

### Backtest dengan guardrail penuh

```
Sampel kecil (max DD 20%, sesuai limit sekarang) : n=44   E=-0,241R
Sampel penuh (max DD 50%)                        : n=329  E=-0,031R
Sampel penuh (max DD 80%)                        : n=404  E=-0,075R
```

**Berbeda dari kasus tiered sizing (momentum_fib) sebelumnya** — di sana
melonggarkan circuit breaker membalik hasil jadi positif. Di sini, bahkan
dengan sampel penuh (404 trade), hasilnya **tetap negatif** di semua
skenario.

### Kesimpulan

Marjin +0,21% di atas breakeven pada analisis label sederhana **tidak
bertahan** setelah dimasukkan gesekan eksekusi nyata: entry di bar
berikutnya (bukan instan), slippage, dan interaksi dengan risk manager.
Analisis label mengasumsikan eksekusi sempurna; kenyataannya tidak.

**Setup ini TIDAK diaktifkan default.** Kode dan runner-nya (`run_bot_frequent.py`)
tersedia untuk pengamatan lebih lanjut, tetapi backtest dengan guardrail
penuh menunjukkan ini merugi secara konsisten pada sampel besar sekalipun —
bukan sekadar dibatasi circuit breaker seperti kasus sebelumnya.

**Rekomendasi: jangan dijalankan dengan uang, termasuk demo dengan tujuan
mengumpulkan profit.** Berguna hanya sebagai observasi lebih lanjut apakah
marjinnya bisa diperbaiki (misalnya via ML atau instrumen lain), bukan
sebagai sistem yang siap pakai.
