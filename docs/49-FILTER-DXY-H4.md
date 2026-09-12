# Filter DXY H4: Kandidat "Cepat" yang Berbasis Data

**Tanggal:** 12 September 2026
**Konteks:** pemilik minta sesuatu yang cepat dikerjakan tapi tetap
berdasarkan data, bukan tebakan. `docs/31` #3.5 sudah menandai DXY H4
sebagai ide yang belum diuji — datanya sudah ada dari eksplorasi lama
(`data_corr/raw/DXYm_M5.parquet`), jadi ini kandidat tercepat yang masih
punya dasar hipotesis, bukan spekulasi baru.

---

## Kenapa Ini, Bukan yang Lain

`docs/26` sudah menguji DXY di **M5** dan gagal (korelasi −0,046, gerak
simultan bukan mendahului). Tapi hipotesis makro yang benar adalah DXY
bekerja di horizon **H4–D1**, bukan 5 menit — jadi kegagalan M5 tidak
membuktikan apa-apa soal H4. Ini beda kondisi, bukan mengulang uji yang
sudah gagal.

Datanya sudah tersedia (490 hari overlap dengan gold), jadi tidak perlu
menunggu unduhan baru — inilah yang membuatnya "cepat".

---

## Metode

`build_htf_context()` — fungsi anti-lookahead yang sama yang sudah
dipakai untuk H1/H4 gold — dipakai ulang untuk DXY, di-resample dari M5
ke H4, lalu digabung ke gold M5 dengan `merge_asof` (backward), sama
persis dengan cara gold menggabung konteks H1/H4-nya sendiri.

Diuji sebagai **filter** (hanya membuang sinyal), bukan generator sinyal
baru — pola yang sudah terbukti aman di `docs/36`.

---

## Hasil

### Hipotesis awal (DXY berlawanan arah = makro mendukung) — SALAH

| Varian | n | E[R] | t |
|---|---|---|---|
| Baseline (periode overlap) | 1.671 | +0,1371 | +3,19 |
| DXY berlawanan arah (mendukung, hipotesis) | 552 | +0,1333 | +1,77 |
| DXY searah (melawan, kontrol) | 459 | **+0,1878** | +2,29 |

Kebalikan dari hipotesis makro klasik — konsisten dengan `docs/26` yang
sudah menemukan hubungan gold-DXY di broker ini tidak mengikuti pola
literatur standar (kemungkinan karena instrumen sintetis CFD, bukan
indeks resmi).

### Yang justru bekerja: DXY H4 punya tren jelas (bukan ranging)

| | n | E[R] | t |
|---|---|---|---|
| Baseline | 1.671 | +0,1371 | +3,19 |
| **DXY H4 tren jelas (bukan ranging)** | **914** | **+0,1793** | **+3,07** |

## Verifikasi — Bukan Kebetulan

**Bukan proxy volatilitas gold sendiri.** Diuji pembanding: filter
berdasarkan ADX gold H4 sendiri (tinggi vs rendah) — hasilnya **berlawanan
arah** dari filter DXY (ADX gold tinggi malah sedikit lebih buruk:
+0,115 vs +0,143 rendah). Jadi filter DXY membawa informasi yang genuin
berbeda, bukan menyamar sebagai kekuatan tren gold yang sudah tertangkap.

**Stabil di kedua paruh:**
```
paruh-1 : n=443  E=+0,1706  t=+2,03
paruh-2 : n=470  E=+0,1899  t=+2,33
```

**Positif di 5/5 fold walk-forward** (baseline juga 5/5, jadi bukan
penyelamat periode buruk — tapi konsisten menaikkan mayoritas fold):
```
fold 1: +0,207  fold 2: +0,196  fold 3: +0,171  fold 4: +0,230  fold 5: +0,075
```

**Holdout 30% tersegel tetap positif:**
```
n=294  E=+0,1840  t=+1,78
```

**Dikombinasi dengan filter konfluensi yang sudah terverifikasi:**

| | n | E[R] | Holdout 30% |
|---|---|---|---|
| Konfluensi saja | 1.294 | +0,1468 | — |
| **Konfluensi + DXY H4** | **678** | **+0,1971** | **+0,2055** (n=220) |

---

## Kejujuran Batasan — Baca Sebelum Bersemangat

1. **Sampel masih kecil** untuk klaim kuat: 914 trade filter tunggal,
   220 untuk kombinasi holdout. t=1,71-1,78 di holdout **belum** melewati
   ambang t~3,0 yang disepakati proyek ini setelah 50+ percobaan pada
   data yang sama (`docs/30`).
2. **DXYm adalah CFD sintetis broker**, bukan indeks DXY resmi —
   `docs/26` sudah mencatat kecurigaan ini. Hasil di sini valid untuk
   **broker ini**, belum tentu untuk sumber DXY lain.
3. **Hanya 490 hari overlap** — lebih pendek dari 516 hari data gold
   utuh, karena DXYm mulai direkam belakangan.
4. **Total percobaan pada data M5 gold ini kini semakin banyak**
   (BOS/CHoCH, 7 algoritma ML, walk-forward, konfluensi, dan sekarang
   DXY) — ambang t jujur terus naik seiring jumlah percobaan. Filter ini
   BELUM melewati ambang itu sendirian.

---

## Rekomendasi

**Layak masuk antrean sebagai kandidat kedua**, di belakang filter
konfluensi yang sudah lebih matang (t=3,14 penuh, meski t=1,71 saat
dikombinasi — devaluasi wajar karena sampel menyusut).

Bukan "sudah terbukti, langsung pakai" — tapi **lebih kuat dari sekadar
tebakan**: hipotesis jelas, diuji dengan metode yang sama ketatnya
(walk-forward, holdout, uji kontrol untuk menyingkirkan proxy palsu),
dan lolos semua pemeriksaan itu. Statusnya sama seperti konfluensi
sebelum forward test: **terverifikasi secara backtest, belum diuji
live.**

### Langkah selanjutnya kalau mau dilanjutkan

1. Tambahkan sebagai varian baru di `config/variants.yaml`
   (`konfluensi_dxy`, magic sendiri) — supaya bisa dibandingkan
   berdampingan tanpa mengganggu forward test yang berjalan
2. **Jangan** langsung aktifkan di `baseline` — ikuti urutan `docs/29`:
   forward test dulu, baru kandidat baru
3. Kalau mau cepat melihatnya "hidup", jalankan di demo sebagai varian
   terpisah paralel dengan magic berbeda — sama seperti pola `dua_arah`
   yang sudah berjalan sekarang
