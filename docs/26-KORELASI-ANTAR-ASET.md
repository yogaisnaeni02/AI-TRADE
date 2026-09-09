# Eksplorasi Korelasi Antar-Aset: DXY dan Silver

**Tanggal:** 9 September 2026
**Permintaan:** Lanjutan eksplorasi — korelasi gold dengan DXY (indeks
dolar) dan Silver, arah yang belum disentuh sama sekali sebelumnya.

---

## Ringkasan

Diunduh data DXYm dan XAGUSDm dari broker yang sama (490-516 hari M5).
Diuji korelasi, lead-lag, spike-following, dan divergence.

**Hasil: tidak ditemukan edge yang bisa dipercaya.** Temuan paling
penting: **korelasi antar-aset ini bersifat simultan, bukan prediktif** —
DXY dan silver bergerak bersamaan dengan gold, tidak mendahuluinya.

---

## 1. Korelasi Dasar

| Pasangan | Korelasi return M5 | Ekspektasi literatur |
|---|---|---|
| Gold vs DXY | **-0,046** | Negatif kuat (biasanya -0,7 sampai -0,9) |
| Gold vs Silver | **+0,091** | Positif kuat (biasanya +0,8 sampai +0,9) |

**Korelasi jauh lebih lemah dari yang umum diklaim.** Kemungkinan
penyebabnya: `DXYm` dan `XAGUSDm` di broker ini adalah instrumen sintetis
(CFD), bukan produk indeks/futures resmi — pergerakannya bisa saja tidak
identik dengan DXY (ICE) atau silver spot yang sesungguhnya.

Di skala waktu lebih besar (1 jam, 4 jam) korelasinya sedikit menguat
(gold-DXY sampai -0,07, gold-silver sampai +0,12) tetapi tetap jauh dari
"kuat".

---

## 2. Lead-Lag: Tidak Ada yang Mendahului

Diuji apakah DXY atau silver bergerak **lebih dulu** sebelum gold
mengikuti — ini yang dibutuhkan agar korelasi bisa dipakai untuk
prediksi, bukan sekadar observasi setelah kejadian.

```
DXY(t-1 jam) vs gold(t)     : corr = -0,0069  (nol)
Silver(t-1) sampai (t-10)   : semua di bawah 0,03 (nol)
```

**Korelasi hanya kuat di lag=0** (bergerak bersamaan). Begitu digeser
walau satu bar, korelasinya runtuh ke nol. Ini berarti: **informasi dari
DXY/silver tidak tersedia lebih dulu** — keduanya bergerak di waktu yang
sama dengan gold, bukan menjadi indikator pendahulu.

Konsekuensinya penting: bahkan jika korelasi kuat, ia tidak berguna untuk
trading — pada saat sinyal dari DXY/silver muncul, gold sudah bergerak
bersamaan, bukan menyusul.

---

## 3. Uji Langsung: Spike-Following

Meski lead-lag menunjukkan nol, tetap diuji secara langsung: saat silver
melonjak tajam (>2× volatilitas normalnya), apakah gold cukup cepat
untuk "disusul" dalam beberapa bar berikutnya?

```
Silver spike UP  -> BUY gold : WR=32,3% E=-0,8968R (n=5.268)
Silver spike DOWN -> SELL gold: WR=31,6% E=-0,9188R (n=5.577)
```

**Sangat rugi di kedua arah**, dengan sampel besar (>5.000). Pola ini
identik dengan temuan volatility-spike sebelumnya (`25-KALENDER-BERITA...`):
entry setelah lonjakan besar berarti "mengejar" harga yang sudah bergerak
jauh — chasing, bukan mengantisipasi.

---

## 4. Divergence: Gold dan Silver Bergerak Berlawanan

Hipotesis lebih canggih: saat gold dan silver **biasanya bergerak
bersama tapi tiba-tiba berlawanan arah**, salah satunya "salah" dan akan
terkoreksi.

Diuji dua hipotesis berlawanan:

| Hipotesis | Arah | WR | Expectancy |
|---|---|---|---|
| Mean-reversion (gold ikut koreksi ke silver) | SELL saat gold naik sendiri | 36,9% | -0,760R |
| Mean-reversion | BUY saat gold turun sendiri | 31,5% | -0,923R |
| Momentum (gold "benar", lanjut) | BUY saat gold naik sendiri | 32,4% | -0,896R |
| Momentum | SELL saat gold turun sendiri | 23,1% | -1,174R |

**Keempat arah gagal telak.** Baik hipotesis mean-reversion maupun
momentum sama-sama merugi besar. Sampelnya juga kecil (103-143 kejadian)
— divergence semacam ini jarang terjadi dan ketika terjadi, tidak
memberi sinyal apapun yang bisa diandalkan.

---

## 5. Kesimpulan

| Pertanyaan | Jawaban |
|---|---|
| DXY berkorelasi dengan gold di broker ini? | Lemah (-0,05), jauh dari ekspektasi umum |
| Silver berkorelasi dengan gold? | Lemah-sedang (+0,09 sampai +0,12) |
| Salah satunya mendahului yang lain? | **Tidak** — korelasi hanya di lag=0 |
| Bisa dipakai untuk entry gold? | **Tidak ditemukan cara yang menguntungkan** — 4 pendekatan berbeda diuji, semua rugi |

**Root cause:** korelasi antar-aset yang bersifat simultan (bukan
prediktif) secara struktural tidak bisa dipakai untuk sinyal entry —
informasinya tersedia di waktu yang sama, bukan lebih dulu. Ini berbeda
dari korelasi yang benar-benar berguna dalam trading (misalnya lead-lag
antar sesi trading berbeda zona waktu), yang butuh salah satu aset
benar-benar mendahului yang lain secara temporal.

---

## 6. Arah yang Masih Mungkin (Belum Dikerjakan)

1. **Data DXY/silver dari sumber lain** (bukan CFD broker ini) — untuk
   memastikan apakah lemahnya korelasi murni karena instrumen sintetis,
   bukan karena hubungan aslinya memang lemah
2. **Yield obligasi AS (US10Y)** — tidak tersedia sebagai simbol di
   broker ini, perlu sumber data terpisah
3. **Korelasi cross-session** (misalnya pergerakan sesi Asia
   memprediksi sesi London) — ini beda jenis lead-lag (temporal karena
   zona waktu berbeda, bukan antar-instrumen) dan belum diuji sama sekali
