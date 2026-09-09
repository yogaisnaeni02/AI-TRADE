# Exit Berbasis Confidence Model (Timeframe M1)

**Tanggal:** 9 September 2026
**Permintaan:** "Bisa nggak main di M1, gak usah target pip besar, yang
penting untung — ambil profit kalau confidence model menurun, biarkan jalan
kalau confidence naik terus (mirip trailing stop tapi berbasis model)."

---

## Ringkasan

Ide ini diuji sungguh-sungguh — bukan ditolak dari asumsi. Hasilnya:

1. **Model M1 murni: tidak ada sinyal** (AUC ~0,50, seperti M5 minggu lalu)
2. **Horizon sangat pendek (1 menit): ADA sinyal nyata** (AUC 0,5412,
   stabil di 7 fold) — ini temuan baru yang tidak ditemukan sebelumnya
3. **Tapi dipakai sebagai exit dini: expectancy turun**, sama seperti
   trailing pip statis yang sudah diuji minggu lalu

Detail dan alasannya di bawah.

---

## 1. Tiga Percobaan Pertama: Tidak Ada Sinyal

| Target | Horizon | AUC | Catatan |
|---|---|---|---|
| Arah masih sama | 5 menit | 0,5025 | Persis acak |
| Untung > spread | 10 menit | 0,5149 | Nyaris acak |
| + 16 fitur lengkap | 10 menit | 0,5184 | Nyaris acak |
| Gabungan M5+M1 | 4 jam (label TP/SL) | 0,4923 | **Di bawah acak** — overfitting, sampel turun jadi 16.103 dari 86.279 |

Konsisten dengan hasil minggu lalu di M5 (AUC 0,5089, 5 framing berbeda).

---

## 2. Temuan Baru: Horizon 1 Menit Punya Sinyal Nyata

Diuji target "harga masih bergerak searah momentum dan untung > spread
dalam 1 menit ke depan":

| Horizon | AUC rata-rata |
|---|---|
| **1 menit** | **0,5412** |
| 2 menit | 0,5336 |
| 3 menit | 0,5227 |
| 5 menit | 0,5175 |

**Semakin pendek horizonnya, semakin kuat sinyalnya.** Ini pola yang masuk
akal secara mikrostruktur — momentum harga di rentang sangat pendek (order
flow jangka pendek) memang lebih mudah diprediksi daripada pergerakan
menit-menitan yang lebih panjang.

### Verifikasi stabilitas (7 fold walk-forward)

```
AUC per fold: 0,531 / 0,541 / 0,551 / 0,543 / 0,535 / 0,544 / 0,544
Rata-rata   : 0,5412
Std deviasi : 0,0061   <- sangat stabil, bukan kebetulan satu fold
```

Ini AUC terbaik yang ditemukan di seluruh proyek — lebih tinggi dan lebih
stabil daripada semua percobaan M5 sebelumnya.

---

## 3. Masalah: Target 1 Menit Terlalu Kecil untuk Ditradingkan Langsung

TP untuk "untung > spread dalam 1 menit" hanya **26 pip** (persis sebesar
spread). Kalau dipakai sebagai entry-exit mandiri dengan SL wajar 400 pip:

```
RR = 26/400 = 1:0,065
Breakeven winrate = 400/(400+26-26) = 100%
```

Butuh winrate mendekati 100% hanya untuk impas — dan sudah dibuktikan di
awal proyek (`02-KENAPA-WINRATE-TINGGI-TIDAK-BISA.md`) itu tidak ada di
kenyataan pasar mana pun.

**Sinyal 1 menit ini tidak bisa jadi strategi entry sendiri.** Nilainya
ada di tempat lain.

---

## 4. Uji Sesungguhnya: Dipakai Sebagai Exit Dini

Ini pengujian paling relevan dengan ide Anda. Skenario:

```
1. Entry via momentum_fib (M5) seperti biasa — SL 400 pip, TP 1.200 pip
2. Selama posisi terbuka, tiap menit cek model M1
3. Kalau posisi UNTUNG dan confidence momentum turun < 0,35 -> EXIT DINI
4. Kalau confidence masih tinggi -> TAHAN sampai TP/SL tersentuh
```

Diuji pada 108 trade nyata dari sinyal momentum_fib (periode Agustus–
September 2026, model dilatih di 70% data sebelumnya):

| Strategi | Winrate | Expectancy |
|---|---|---|
| **Tanpa exit dini (tunggu TP/SL)** | 35,2% | **+0,4074R** |
| **Dengan exit model M1** | **58,3%** | **+0,1379R** |

**Winrate melonjak (35,2% → 58,3%) tetapi expectancy anjlok** (+0,407R →
+0,138R) — turun 66%.

---

## 5. Mengapa Ini Terjadi — Pola yang Sama Berulang

Ini persis pola yang ditemukan minggu lalu dengan trailing pip statis
(`14-TRAILING-80PIP.md`):

```
Trailing pip statis (80 pip)  : WR 26,6%->51,5%, E +0,033R->-0,040R
Exit model M1 (confidence)    : WR 35,2%->58,3%, E +0,407R->+0,138R
```

**Mekanismenya identik**, meski alasannya (pip statis vs confidence model)
terdengar berbeda:

Strategi ini punya winrate rendah dan bergantung pada **sedikit pemenang
besar** untuk menutup banyak kekalahan kecil. Exit dini apa pun — entah
berbasis pip, ATR, atau confidence model — memotong pemenang itu sebelum
mencapai potensi penuhnya.

Confidence model 1-menit memang punya sinyal nyata (AUC 0,54) untuk
memprediksi 1 menit ke depan. Tetapi itu **tidak sama** dengan memprediksi
kapan trade 4-jam sebaiknya diakhiri. Confidence bisa turun sesaat lalu
naik lagi — exit dini menangkap fluktuasi jangka pendek yang tidak relevan
dengan arah besar 4 jam.

---

## 6. Apakah Ada Cara Memakainya yang Lebih Baik?

Dicoba variasi threshold dan kombinasi, konsisten menunjukkan pola sama:
makin ketat syarat exit dini, makin tinggi winrate, makin rendah
expectancy. Tidak ditemukan threshold yang membuat exit dini mengungguli
"tunggu TP/SL".

Kemungkinan penyebab struktural: horizon prediksi (1 menit) terlalu jauh
dari horizon keputusan (4 jam). Sinyal yang valid untuk "apa yang terjadi
1 menit lagi" bukan sinyal yang tepat untuk "apakah trade 4 jam ini masih
layak dipertahankan".

---

## 7. Yang Bernilai dari Percobaan Ini

Meski tidak menghasilkan exit strategy yang lebih baik, percobaan ini
menghasilkan temuan baru yang berharga:

> **Momentum M1 pada horizon 1 menit memiliki daya prediksi nyata
> (AUC 0,5412, stabil di 7 fold) — jauh lebih kuat daripada apa pun yang
> ditemukan di M5.**

Ini arah baru yang belum dieksplorasi: kemungkinan XAUUSD memang lebih
efisien di timeframe menengah (M5, target berjam-jam) daripada di
mikrostruktur sangat pendek (M1, target 1 menit). Ini konsisten dengan
banyak riset finansial: order flow jangka sangat pendek sering lebih
prediktif daripada pergerakan menit-menitan.

**Arah yang belum dicoba dan berpotensi:** memakai sinyal 1-menit ini
bukan untuk exit dari trade 4 jam, melainkan sebagai **strategi scalping
mandiri** dengan target dan biaya yang disesuaikan skalanya — bukan target
26 pip melawan spread 26 pip, melainkan mengumpulkan banyak sinyal kecil
di instrumen atau kondisi dengan spread jauh lebih rendah.

---

## 8. Ringkasan

| Pertanyaan | Jawaban |
|---|---|
| Main di M1 untuk exit dinamis? | Diuji, dan **tidak memperbaiki hasil** |
| Ada sinyal di M1 sama sekali? | **Ya** — horizon 1 menit, AUC 0,5412 (temuan baru) |
| Bisa dipakai sebagai exit dari trade 4 jam? | **Tidak** — menurunkan expectancy 66% |
| Kenapa? | Horizon 1 menit ≠ horizon 4 jam; memotong pemenang besar |
| Apa yang bernilai dari ini? | Sinyal M1 1-menit adalah arah baru untuk dieksplorasi terpisah |
| Rekomendasi untuk sistem sekarang | **Jangan diaktifkan** — expectancy tunggu-TP/SL tetap lebih baik |

Sistem utama tidak diubah oleh percobaan ini — `momentum_fib` tetap
memakai `breakeven_at_r: 2.0` tanpa trailing, sesuai kesimpulan
sebelumnya di `15-MANAJEMEN-RISIKO-YANG-BENAR.md`.
