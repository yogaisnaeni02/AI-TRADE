# Verifikasi Independen: ML Walk-Forward Lolos Ambang

**Tanggal:** 12 September 2026
**Konteks:** rekan kerja push temuan di branch `riset/ml-volatilitas`
(`scripts/ml_walk_forward.py`, commit `59fc7b2`) — klaim AUC 0,56 (t=3,54)
out-of-sample, pertama kali ada ML yang lolos ambang t~3,0. Diverifikasi
independen di sini sebelum diakui.

---

## Ringkasan

**Klaim direproduksi persis, dan lolos empat uji stres tambahan yang
menggugurkan semua kandidat ML palsu sebelumnya (docs/41, docs/42).**
Ini kandidat pertama di seluruh proyek yang layak dipertimbangkan serius.

**Belum diaktifkan di produksi** — masih di branch terpisah, dan AUC 0,56
tergolong lemah meski nyata.

---

## 1. Reproduksi Persis

Dijalankan ulang di mesin ini, kode identik:

```
PREDIKSI OUT-OF-SAMPLE : 1.351 trade
  benar-benar TP       : 392 (29,0%)
  AUC                  : 0,5618  (SE 0,0174, t +3,54)

Q1 rendah  n=338  TP 23,1%  E[R] -0,0672
Q2         n=338  TP 28,7%  E[R] +0,1397
Q3         n=338  TP 30,8%  E[R] +0,2138
Q4 tinggi  n=337  TP 33,5%  E[R] +0,3079
selisih Q4-Q1 = +0,3751R  t=2,81

buang 25% terendah  n=1013  E[R]=+0,2204  t=3,93
```

Angka identik sampai 4 desimal. Tidak ada kebocoran tersembunyi dari
lingkungan yang berbeda.

---

## 2. Kenapa Metodenya Lebih Kuat dari Semua Percobaan Sebelumnya

| | `docs/41` (holdout tunggal) | `docs/42` (7 algoritma) | Walk-forward (ini) |
|---|---|---|---|
| Validasi | 1 titik potong | 1 titik potong | **puluhan titik potong berurutan** |
| Populasi latih | semua bar (86.279) atau sinyal (4.189) | sinyal | **1.751 trade tereksekusi** |
| Target | TP/SL | TP/SL | TP/SL |
| AUC terbaik | 0,55 (tidak stabil) | 0,55 (tidak stabil) | **0,56 (stabil di semua seed)** |

Perbedaan yang paling menentukan: **dilatih pada 1.751 trade yang benar-
benar dieksekusi**, bukan 86.279 bar atau bahkan 4.189 sinyal mentah.
`train.py` lama melatih meta-model pada seluruh populasi bar padahal bot
hanya bertindak di sinyal — itu melatih pada distribusi yang salah.

Walk-forward juga tidak mengizinkan "keberuntungan satu holdout menyamar
jadi kemampuan" — persis mekanisme yang menggugurkan kandidat BB squeeze
(`docs/32`) dan pullback M1 (`docs/31`) sebelumnya, sekarang dibangun
sebagai desain, bukan pengecekan tambahan.

---

## 3. Empat Uji Stres — Semua Lolos

Kandidat-kandidat ML sebelumnya gugur di sini. Yang ini tidak.

### a. Stabilitas seed

```
seed    1  AUC 0,5681  t +3,90
seed    7  AUC 0,5612  t +3,51
seed   42  AUC 0,5618  t +3,54
seed  123  AUC 0,5655  t +3,76
seed  999  AUC 0,5637  t +3,65
```

Rentang **0,0069** — dibandingkan varian ML sebelumnya yang berayun
+0,047 sampai +0,312 (6,7x lipat) hanya karena seed (`docs/41` bagian 4b).
Ini bukan kebetulan angka acak.

### b. Sapuan hiperparameter (9 kombinasi)

```
AUC berkisar 0,5363 - 0,5698, SEMUA t > 2,0
```

Tidak ada satu pun kombinasi yang jatuh ke bawah acak — pola yang sama
sekali berbeda dari sapuan `docs/42` (rentang 0,46-0,55, tiga di bawah
acak).

### c. Belah dua periode prediksi

```
paruh awal   n=675  AUC 0,5782  t +3,19
paruh akhir  n=676  AUC 0,5555  t +2,24
```

Positif di **kedua** paruh — menggugurkan kemungkinan "edge" ini cuma
produk satu rezim pendek.

### d. Kepentingan fitur — bukan jebakan `hour_utc`

Rekan kerja sudah memperingatkan: prediksi volatilitas (AUC 0,82 di
percobaan awal mereka) ternyata cuma menghafal `hour_utc`, dan arahnya
**berlawanan** dengan profit. Diperiksa ulang untuk model TP ini:

```
atr             76   <- dominan
adx             31
hour_utc        24   <- urutan 3, bukan mendominasi
mom_24          17
atr_percentile  13
h1_adx          13
fib_position     5
htf_alignment    1
rsi              0
```

`atr` dan `adx` (kekuatan tren & volatilitas relatif terhadap arah)
mendominasi, bukan waktu. Ini konsisten dengan seluruh temuan proyek:
yang bisa diprediksi dari data ini berkaitan dengan kekuatan gerakan,
dan di sini kekuatan gerakan itu **berkorelasi dengan TP tercapai** —
beda dari jebakan volatilitas yang arahnya terbalik.

---

## 4. Kenapa Berbeda dari 7 Algoritma yang Gagal (docs/42)

Bukan soal algoritma (LightGBM dipakai di kedua percobaan). Bedanya:

1. **Populasi latih benar** — 1.751 trade tereksekusi, bukan 86.279 bar
   atau 4.189 sinyal mentah sebelum gerbang risiko
2. **Walk-forward**, bukan satu holdout — puluhan titik uji, bukan satu
3. **Retrain berkala** (tiap 50 trade) — model ikut menyesuaikan rezim,
   bukan satu model beku untuk semua periode

`docs/42` sudah membuktikan algoritma bukan masalahnya (7 algoritma semua
gagal pada populasi yang sama). Yang berubah di sini adalah **populasi
dan skema validasi**, dan itu yang ternyata menentukan.

---

## 5. Kenapa BELUM Diaktifkan — dan Ini Harus Ditegaskan

AUC 0,56 nyata, tapi **lemah**. Konteks yang wajib diingat:

- Ini masih data **M5 yang sama** yang sudah diuji berkali-kali
  (`docs/06`, `docs/22`, `docs/36`, `docs/37`, `docs/41`, `docs/42`) —
  bukan sumber informasi baru
- 1.751 trade adalah sampel kecil untuk klaim permanen
- Rekan kerja sendiri menyatakan langkah berikutnya: **uji M15 (4,2
  tahun)** sebelum dipercaya lebih jauh — belum dikerjakan
- `docs/29` melarang mengubah jalur sinyal selama forward test berjalan,
  dan filter konfluensi (`docs/36`, t=3,14) sudah antre duluan untuk
  diaktifkan setelah forward test selesai

Menambahkan ML sekarang berarti dua perubahan jalur sinyal bersaing
untuk kredit yang sama pada sampel forward test yang masih kecil.
Urutannya tetap: **konfluensi dulu, ML menyusul setelah terbukti di
M15 dan/atau live.**

---

## 6. Yang Perlu Diperiksa Lagi Sebelum Aktivasi

Prasyarat tambahan, di luar yang rekan kerja sudah sebutkan (uji M15):

1. **Kombinasi dengan filter konfluensi** — apakah keduanya menambah
   informasi berbeda, atau saling tumpang tindih (fitur `adx` dipakai
   kedua-duanya)?
2. **Latensi retrain di live** — walk-forward retrain tiap 50 trade tidak
   otomatis berarti murah dijalankan tiap siklus bot; perlu skema retrain
   terjadwal (mis. mingguan) yang tidak menyentuh jalur order.
3. **Ambang t jujur sudah naik lagi.** `docs/30` menghitung ambang ~3,0
   dari 50+ percobaan; sesi ini menambah puluhan lagi (BOS/CHoCH, 7
   algoritma, walk-forward, berbagai holdout). Jumlah total percobaan
   pada data M5 yang sama kini realistis di atas 100 — ambang Bonferroni
   yang jujur mendekati **3,3-3,5**. t=3,54 pada AUC dan t=3,93 pada
   filter 25% MASIH lolos di ambang itu, tapi marginnya menipis.

---

## 7. Kesimpulan

| Pertanyaan | Jawaban |
|---|---|
| Direproduksi? | Ya, identik 4 desimal |
| Lolos stabilitas seed? | Ya — rentang 0,007 (vs 6,7x lipat kandidat lama) |
| Lolos sapuan hiperparameter? | Ya — 9/9 kombinasi t>2,0 |
| Lolos belah dua? | Ya — positif kedua paruh |
| Jebakan `hour_utc`? | Tidak — atr/adx dominan, arah selaras profit |
| Layak produksi sekarang? | **Belum** — tunggu uji M15, urutan setelah konfluensi |

Ini pertama kalinya ML di proyek ini lolos pemeriksaan yang menggugurkan
`docs/41` dan `docs/42`. Kesimpulan lama ("ML tidak menemukan apa pun di
data M5") perlu direvisi menjadi: **ML tidak menemukan apa pun ketika
dilatih pada populasi yang salah dan divalidasi dengan satu holdout;
dilatih pada trade tereksekusi dan divalidasi walk-forward, ada sinyal
lemah tapi nyata.**
