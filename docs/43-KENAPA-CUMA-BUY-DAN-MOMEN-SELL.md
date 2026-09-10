# Kenapa Cuma BUY, dan Bagaimana Kalau Ada Momen SELL

**Tanggal:** 10 September 2026
**Pertanyaan pemilik:** "loh gak bisa ya sell-nya, cuma buy doang? kalau ada
momen di bagian sell gimana?"

---

## Ringkasan

Pertanyaannya tepat sasaran, dan jawabannya **bukan** "momen sell tidak ada".

- Pasar **downtrend 37,3%** dari waktu — momen sell banyak
- Saat pasar benar-benar turun (2026Q2, −14,7%), **sell menang: +0,119R
  sementara buy −0,071R**
- Tetapi **rata-rata sepanjang 1,4 tahun, sell = nol** (+0,007R, t=0,09)

Jadi sell **bisa** bekerja, tapi hanya di rezim tertentu — dan kita belum
punya cara andal menebak kapan rezim itu datang. Menyalakannya sekarang
menurunkan hasil keseluruhan.

---

## 1. Momen Sell Bukannya Tidak Ada

```
Distribusi tren HTF (100.000 bar):
  uptrend    49,0%
  downtrend  37,3%     <- momen sell
  ranging    13,7%
```

Lebih dari sepertiga waktu pasar dalam downtrend. Yang membuat bot hampir
tidak pernah sell bukan kelangkaan momen, melainkan **gate momentum yang
asimetris** (lihat `docs/39`).

---

## 2. Empat Definisi Sell Diuji — Tidak Ada yang Bekerja

Bukan sekadar mencerminkan gate buy; empat cara berbeda dicoba:

| Definisi sell | n | E[R] | t | WR | paruh-1 | paruh-2 |
|---|---|---|---|---|---|---|
| **simetris** (fib < 0,25, momentum turun) | 520 | −0,0151 | −0,20 | 26,0% | −0,053 | −0,003 |
| **fib_atas** (jual dari puncak retracement) | 3 | +0,6142 | +0,55 | 66,7% | — | — |
| **fib_bebas** (tanpa syarat fib) | 563 | −0,0681 | −0,98 | 24,9% | −0,100 | −0,032 |
| **breakout** (tembus bawah, fib < 0,15) | 471 | +0,0122 | +0,16 | 26,8% | +0,012 | +0,028 |
| *pembanding:* **BUY produksi** | 673 | **+0,1411** | **+2,07** | 30,0% | | |

`fib_atas` menghasilkan **3 sinyal** — terlalu sedikit untuk dipercaya,
angka +0,61 itu kebetulan tiga trade.

Yang terbaik (`breakout`) pun cuma +0,012R — praktis nol.

---

## 3. Kenapa? Sebagian Karena Periodenya

Data ini mencakup emas **naik 37,4%** ($3.207 → $4.409). Wajar curiga sisi
buy diuntungkan.

Diuji netral — **entry acak**, tanpa strategi apa pun, hanya mengukur
pasarnya:

```
BUY  acak : n=6000  E=-0,0747R  WR=23,5%
SELL acak : n=6000  E=-0,1052R  WR=22,7%
```

Keduanya rugi (spread 26 pip), tapi **sell lebih rugi**. Jadi memang ada
angin belakang untuk buy di periode ini — bukan cuma setup kita yang bias.

---

## 4. Bukti Terkuat: Saat Pasar Benar-Benar Turun, Sell Menang

Per kuartal, dengan gate simetris:

| Kuartal | Pasar | BUY (n / E[R]) | SELL (n / E[R]) |
|---|---|---|---|
| 2025Q2 | +3,3% | 84 / +0,1794 | 83 / +0,1338 |
| 2025Q3 | +16,6% | 113 / +0,1157 | 58 / **−0,3314** |
| 2025Q4 | +11,8% | 157 / +0,1881 | 71 / −0,0371 |
| 2026Q1 | +8,4% | 139 / +0,1481 | 90 / +0,0030 |
| **2026Q2** | **−14,7%** | 81 / **−0,0712** | 129 / **+0,1191** |
| 2026Q3 | +10,0% | 74 / +0,2346 | 80 / **−0,1927** |

**Di satu-satunya kuartal pasar turun, posisinya terbalik**: sell +0,119
sementara buy justru rugi −0,071.

Ini membuktikan sisi sell **tidak rusak** — ia bekerja persis saat
seharusnya bekerja. Masalahnya: dari 6 kuartal, hanya 1 yang turun.

---

## 5. Dicoba dengan Filter Terbaik — Tetap Nol

Filter konfluensi (satu-satunya yang lolos holdout tersegel, `docs/36`)
diterapkan ke dua arah:

| Varian | n | E[R] | t | paruh-1 | paruh-2 |
|---|---|---|---|---|---|
| **BUY saja (produksi sekarang)** | 675 | **+0,1327** | +1,95 | +0,133 | +0,132 |
| dua arah, tanpa filter | 1.140 | +0,0725 | +1,41 | +0,070 | +0,075 |
| dua arah + filter konfluensi | 889 | +0,1287 | **+2,18** | +0,155 | +0,106 |

Dipecah per arah pada varian terakhir:

```
BUY  saja : n=518  E=+0,2534  t=+3,17   <- seluruh edge ada di sini
SELL saja : n=412  E=+0,0072  t=+0,09   <- nol
HOLDOUT   : n=278  E=+0,0479  t=+0,47
```

Menambahkan 412 trade ber-expectancy nol **mengencerkan** edge sisi buy:
E turun dari +0,2534 (buy saja + filter) ke +0,1287 (dua arah + filter).

t memang naik tipis (2,18 vs 1,95) karena sampel bertambah, tetapi
**expectancy per trade turun** — dan itu yang menentukan uang.

---

## 6. Jadi Kalau Ada Momen Sell, Bagaimana?

Jawaban jujurnya: **bot akan melewatkannya, dan itu pilihan yang disengaja.**

Alasannya bukan "sell tidak bisa untung", melainkan:

1. **Kita belum bisa menebak kapan rezim turun datang.** Sell menang di
   2026Q2 dan kalah telak di 2025Q3 (−0,331) serta 2026Q3 (−0,193).
   Menyalakannya berarti ikut kalah di kuartal-kuartal itu juga.
2. **Melewatkan peluang tidak merugikan; ikut trade nol-expectancy
   merugikan.** Tidak buka posisi = biaya nol. Buka 412 posisi
   ber-expectancy nol = membayar spread 412 kali untuk hasil rata-rata nol.
3. **Modal terbatas.** Lot minimum mengunci risiko 1,35–1,97% per trade.
   Setiap slot posisi (max 1 bersamaan) lebih baik dipakai sinyal
   ber-expectancy +0,25R daripada 0,00R.

### Yang benar-benar hilang

Selama forward test, kalau pasar masuk tren turun panjang, bot akan
**jarang membuka posisi**. Itu bukan kerusakan — itu sistem menolak
bertaruh pada sesuatu yang belum terbukti.

---

## 7. Yang Akan Membuat Sell Layak Dinyalakan

Bukan definisi sell yang lebih pintar — empat sudah dicoba. Yang dibutuhkan
**deteksi rezim**: cara mengetahui bahwa pasar sedang dalam fase turun
sebelum faktanya lewat.

Kandidat yang punya dasar bukti, belum diuji:

| Ide | Kenapa masuk akal | Sumber |
|---|---|---|
| **DXY H4 sebagai bias arah** | Makro bekerja di horizon H4–D1; emas & dolar berlawanan | `docs/31` #3.5 |
| **Tren H4/D1 emas sendiri** | Aktifkan sell hanya saat H4 downtrend berkelanjutan | belum diuji |
| **Data lebih panjang** | 1,4 tahun cuma memuat 1 kuartal turun. Butuh periode bear panjang | M5 terbatas 100.000 bar |

Syaratnya sama seperti semua kandidat: **holdout tersegel, stabilitas belah
dua, ambang t ~3,0**. Dan tidak boleh diubah selama forward test berjalan
(`docs/29`).

---

## 8. Ringkasnya untuk Pemilik

| Pertanyaan | Jawaban |
|---|---|
| Momen sell ada? | **Ada** — pasar downtrend 37,3% waktu |
| Sell bisa untung? | **Bisa** — di 2026Q2 (pasar −14,7%): +0,119R vs buy −0,071R |
| Kenapa dimatikan? | Rata-rata 1,4 tahun = **nol** (+0,007R, t=0,09) |
| Kalau dinyalakan? | Expectancy turun +0,2534 → +0,1287 per trade |
| Kapan bisa nyala? | Setelah ada **deteksi rezim** yang terbukti (DXY/H4) |

Sistem ini bukan "cuma bisa buy" — ia **memilih hanya mengambil taruhan
yang terbukti**. Sisi sell tetap ada di kode dan akan otomatis ikut aktif
begitu deteksi rezim terbukti layak.

---

## 9. Pelengkap: Seberapa Besar Handicap Short Sebenarnya? (sesi lain)

Bagian 1–8 menjawab *"apakah sell bekerja"*. Bagian ini menjawab pertanyaan
yang berbeda: *"apakah short dirugikan secara struktural, atau hanya setup
ini yang tidak cocok?"* — diukur dengan **entry acak**, tanpa setup sama
sekali.

### Arus dasar tiap arah

Entry acak, RR 1:2,78, SL 4000 pts, maks 48 bar, spread + slippage dibayar,
seed tetap (4.000 sampel per arah):

| data | arah | E[R] | t | WR% |
|---|---|---|---|---|
| M5 (2025–2026, +37%) | buy | −0,0548 | −2,15 | 26,5 |
| M5 | **sell** | **−0,0749** | −2,96 | 25,8 |
| M15 (2022–2026, +140%) | buy | −0,0747 | −3,05 | 27,7 |
| M15 | **sell** | **−0,1209** | −5,00 | 26,2 |

Dua hal terbaca:

1. **Entry acak rugi di KEDUA arah.** Itu spread 26 pip — tembok yang sama
   tinggi untuk buy maupun sell. Musuh utamanya biaya transaksi, bukan arah.
2. **Handicap short kecil:** selisih buy−sell hanya **+0,020R (M5)** sampai
   **+0,046R (M15)**. Itu drift naik emas. Short tidak dihukum berat secara
   struktural.

### Setup diukur sebagai nilai tambah di atas acak

Ini cara yang lebih adil menilai sisi sell — bukan "positif atau negatif",
melainkan "apakah setup menambah sesuatu di atas lempar koin":

| | acak | setup (gate simetris) | **nilai tambah** |
|---|---|---|---|
| M5 buy | −0,055 | +0,131 | **+0,186R** |
| M5 sell | −0,075 | −0,038 | **+0,037R** |
| M15 buy | −0,075 | +0,038 | +0,113R |
| M15 sell | −0,121 | −0,158 | **−0,037R** |

Di M5, sisi sell sebenarnya **menambah nilai** (+0,037R) — konsisten dengan
temuan bagian 4 bahwa ia bekerja saat rezimnya cocok. Ia hanya tidak cukup
untuk melewati tembok spread −0,075R.

Di M15 justru **lebih buruk dari lempar koin** (−0,037R).

### Angka target yang konkret

Dari tabel di atas, sebuah setup sell harus memberi **≥ +0,075R (M5)** atau
**≥ +0,121R (M15)** di atas entry acak hanya untuk mencapai breakeven —
plus margin di atasnya agar layak dijalankan.

Sebagai pembanding: setup buy yang sekarang memberi **+0,186R** di atas acak.
Jadi targetnya bukan mustahil — tetapi butuh sesuatu yang sekelas itu,
dirancang khusus untuk sisi turun.

### Catatan atas uji lintas-tahun M15

M15 memberi 4,2 tahun (3x M5), dengan gate simetris `min_score=5`:

| tahun | pasar | buy E[R] | sell E[R] |
|---|---|---|---|
| 2022 | −1% | −0,2447 | −0,2168 |
| 2023 | +13% | +0,0395 | +0,0065 |
| 2024 | +27% | +0,0232 | −0,0878 |
| 2025 | +65% | +0,0654 | −0,1174 |
| 2026 | +2% | +0,1607 | −0,5539 |
| **total** | +140% | +0,0379 (t 0,65) | **−0,1580 (t −2,52)** |

Sekilas ini tampak membantah bagian 4 — sell rugi bahkan di 2022 yang
"datar". Tetapi **datar ≠ turun**: setahun −1% bisa berisi naik dan turun
yang saling meniadakan, dan setup kelanjutan-tren rugi di kedua fase itu.
Bagian 4 mengukur satu kuartal yang benar-benar turun **−14,7%** — itu
kondisi yang berbeda, dan di sana sell menang.

Jadi kedua temuan konsisten: **sell butuh tren turun yang jelas dan
berkelanjutan, bukan sekadar pasar yang tidak naik.** Itu justru
mempersempit syarat deteksi rezim di bagian 7 — bukan "deteksi bukan-bull",
melainkan "deteksi bear yang sedang berlangsung".

Perhatikan juga kolom buy: **+0,0379 (t 0,65) di M15**, jauh di bawah M5
(+0,131). Edge sisi buy pun menyusut pada data lebih panjang — konsisten
dengan `docs/28` §3.2. Pertanyaan itu lebih mendesak daripada soal sell:
bila edge buy sendiri artefak periode, menambah sell tidak menyelamatkan
apa pun.
