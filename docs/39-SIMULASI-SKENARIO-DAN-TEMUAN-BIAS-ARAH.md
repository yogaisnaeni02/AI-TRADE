# Simulasi Skenario BUY/SELL + Temuan: Sistem Ini Praktis Hanya BUY

**Tanggal:** 10 September 2026
**Permintaan:** "buat skenario buy atau sell biar aku yakin sistemnya sudah
berjalan dengan baik" — sebelum bot dijalankan di PC lain.

---

## Ringkasan

Simulasi dibuat (`scripts/simulasi_skenario.py`) dan **sistem terbukti
berjalan benar**: sinyal terbentuk, SL/TP di sisi yang tepat, gerbang risiko
memblokir yang harus diblokir, payload order tersusun lengkap.

Tetapi simulasi itu **menemukan dua hal yang tidak terlihat sebelumnya**:

1. **Bot hanya melapor salah** soal ambang ATR di heartbeat (sudah diperbaiki)
2. **Sistem ini praktis hanya BUY** — 4.180 sinyal buy vs **9** sell

Temuan kedua penting dan perlu keputusan pemilik. Diselidiki tuntas di bawah.

---

## 1. Hasil Simulasi — Sistem Berjalan Benar

Dijalankan dengan kode produksi yang sama persis; `mt5.order_send()` tidak
pernah dipanggil.

### Skenario BUY (8 Sep 2026, sesi Asia)

```
entry  4436.139
SL     4432.328   (3811 pts = 381 pip)   di BAWAH entry  OK
TP     4447.259   (11120 pts = 1112 pip) di ATAS entry   OK

RR efektif 1:2,67 (setelah spread 260 pts)  -> breakeven WR 27,3%
Gerbang risiko: IZIN, lot 0,01, risiko Rp 66.623 (1,67%)
SL kena -> -Rp 66.623   TP kena -> +Rp 194.418
```

### Skenario SELL (9 Jun 2026, sesi NY sore)

```
entry  4266.045
SL     4270.545   (4500 pts = 450 pip)   di ATAS entry   OK
TP     4253.535   (12510 pts = 1251 pip) di BAWAH entry  OK

RR efektif 1:2,57  -> breakeven WR 28,0%
Gerbang risiko: IZIN, lot 0,01, risiko Rp 78.676 (1,97%)
SL kena -> -Rp 78.676   TP kena -> +Rp 218.720
```

### Uji gerbang risiko

| Skenario | Hasil |
|---|---|
| Equity Rp 1 juta (di bawah minimum) | **TOLAK** — "di bawah minimum Rp 4.000.000" |
| Sudah ada 1 posisi terbuka | **TOLAK** — "sudah ada 1 posisi terbuka" |
| Spread melebar 500 pts | **TOLAK** — "spread 500 > batas 400" |
| Kondisi normal | **IZIN** — "lolos semua pemeriksaan" |

SL dan TP dikirim **bersamaan** dengan entry dalam satu request — posisi
tidak pernah ada tanpa proteksi.

---

## 2. Bug Diperbaiki: Heartbeat Melapor Ambang ATR yang Salah

`src/execution/bot.py` menulis ulang ambang ATR sebagai angka mati:

```python
if not (0.30 <= row["atr_percentile"] <= 0.85):
    kurang.append(f"ATR {row['atr_percentile']:.2f}")
```

Padahal gate sesungguhnya sudah dilonggarkan ke **0,20–0,95**. Akibatnya
heartbeat melaporkan `belum: ATR 0.25` untuk bar yang sebenarnya **LOLOS**.

Ini **tidak memblokir trade** — hanya salah lapor. Tetapi persis jenis
kebohongan yang membuat pemilik ragu apakah botnya bekerja, dan itu justru
yang sedang dijawab oleh simulasi ini. Sekarang ambang dibaca dari
`RuleEngine`, tidak ditulis ulang.

---

## 3. TEMUAN UTAMA: 4.180 BUY vs 9 SELL

Simulasi meminta satu contoh tiap arah. Saat mencari, ketahuan:

```
total sinyal : 4.189
BUY          : 4.180
SELL         :     9      <-- 0,2%
```

### Penyebabnya: `mom_24` bertanda, gatenya tidak

`mom_24` adalah perubahan harga ternormalisasi ATR — **bertanda**:
positif saat harga naik, negatif saat turun.

```
mom_24 keseluruhan:  min -11,40   median +0,13   max +15,66
```

Gate momentum berlaku sama untuk kedua arah:

```python
if row.mom_24 > row.mom_24_q85:          # ambang = kuantil 85 (positif)
    size_tier = "full"
elif row.mom_24 > row.mom_24_q85 * 0.5:
    size_tier = "reduced"
```

Untuk **sell**, syarat itu berarti: *"harga harus sedang NAIK kuat"* —
padahal arah tradenya jual, dan `trend_htf` wajib `downtrend`. Dua syarat
yang saling meniadakan.

Yang tersisa cuma 9 sinyal — bar yang kebetulan HTF-nya downtrend tetapi
momentum M5-nya sedang naik tajam.

| | Kandidat lolos gate |
|---|---|
| BUY | 8.030 |
| SELL (gate sekarang) | **124** |
| SELL (gate simetris) | 5.258 |

---

## 4. Diperbaiki? TIDAK — dan ini alasannya

Perbaikan yang "jelas" adalah memakai `-mom_24` untuk sell. Diuji:

| | Sekarang | Simetris |
|---|---|---|
| Sinyal | 4.189 (buy 4180 / sell 9) | 6.747 (buy 4180 / **sell 2567**) |
| Trade | 675 | 1.140 |
| **E[R]** | **+0,1327** | **+0,0725** |
| **t** | **+1,95** | **+1,41** |
| Winrate | 29,8% | 28,2% |
| Holdout | +0,0748 | +0,0477 |

Dipecah per arah — ini kuncinya:

```
BUY  saja : n=673  E=+0,1411  t=+2,07  WR=30,0%
SELL saja : n=520  E=-0,0151  t=-0,20  WR=26,0%   <- gate simetris
```

**Sisi sell tidak punya edge.** Menambahkannya bukan memperbaiki sistem —
hanya mengencerkan edge sisi buy dengan 520 trade yang expectancy-nya nol.

Jadi: gate asimetris itu **memang bug secara logika**, tetapi memperbaikinya
**merugikan**. Sistem ini tidak "kebetulan cuma buy" — ia **memang hanya
punya edge di sisi buy**, dan bug itu tanpa sengaja menyaringnya.

### Kenapa masuk akal

Data ini mencakup Apr 2025 – Sep 2026, periode emas naik dari ~$3.200 ke
~$4.400. Setup ini adalah **kelanjutan tren**; di pasar yang naik terus,
sisi buy punya angin belakang dan sisi sell melawan arus.

Artinya ada **risiko rezim** yang harus disadari: kalau emas masuk bear
market panjang, sistem ini akan jarang memberi sinyal, dan sedikit yang
diberikan kualitasnya belum teruji. Ini bukan sistem dua arah.

---

## 5. Konsekuensi untuk Pemilik

**Yang tidak berubah:** sistem berjalan benar, forward test lanjut apa
adanya. Tidak ada kode strategi yang diubah.

**Yang perlu diketahui:**

1. **Bot ini praktis hanya membeli.** Kalau melihat berhari-hari tanpa
   sinyal saat harga turun, itu perilaku normal — bukan kerusakan.
2. **Buktinya bias ke satu rezim pasar.** Angka +0,1411R / t=2,07 untuk
   sisi buy diukur pada periode emas naik. Belum ada bukti untuk rezim turun.
3. **Gate asimetris dibiarkan** karena memperbaikinya menurunkan hasil.
   Tetapi sekarang tercatat sebagai keputusan sadar, bukan kecelakaan yang
   tidak diketahui.

### Yang layak diuji kelak (bukan sekarang)

Sisi sell mungkin butuh **setup berbeda**, bukan cerminan setup buy. Pasar
turun berperilaku lain: lebih cepat, lebih tajam, volatilitas lebih tinggi.
Menyalin gate buy lalu membalik tandanya jelas tidak cukup — itu sudah
dibuktikan di bagian 4.

Ini masuk daftar riset, dengan syarat yang sama seperti semua kandidat:
holdout tersegel, stabilitas belah dua, dan ambang t ~3,0.

---

## 6. Cara Menjalankan Simulasi

```bash
python scripts/simulasi_skenario.py           # data historis, tanpa MT5
python scripts/simulasi_skenario.py --live    # harga live, butuh MT5 terbuka
python scripts/simulasi_skenario.py --equity 4336460
```

Skrip ini **tidak pernah** memanggil `mt5.order_send()`. Aman dijalankan
kapan saja, termasuk saat bot sedang aktif.
