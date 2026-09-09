# Kenapa Sistem Winrate 90% Tidak Bisa Dibuat Profitabel

**Versi:** 1.0
**Tanggal:** 9 September 2026
**Status:** Penjelasan teknis — pendukung `01-SMALL-CAPITAL-AGGRESSIVE.md`

Dokumen ini menjawab pertanyaan: *"Kenapa tidak bisa dibuat sistem winrate
90% yang menghasilkan profit besar dari modal kecil? Kendala teknisnya di
mana?"*

Jawabannya perlu presisi, karena kendalanya **bukan** pada kualitas sistem,
kecanggihan AI, atau usaha pengembangan. Kendalanya ada pada aritmetika yang
berlaku untuk semua pelaku pasar tanpa kecuali.

---

## 1. Winrate 90% Itu Mudah — Justru Itu Masalahnya

Membuat sistem winrate 90% tidak sulit sama sekali. Resepnya satu baris:

```
TP = 20 points
SL = 400 points
```

Selesai. Sistem ini akan menang sekitar 90–93% dari seluruh trade.

Alasannya sederhana: harga gold berfluktuasi terus-menerus. Peluang harga
menyentuh +20 points sebelum menyentuh −400 points memang sangat besar.

**Sekarang hitung uangnya, per 100 trade:**

| | Jumlah | Points/trade | Total |
|---|---|---|---|
| Menang | 90 | +20 | **+1.800** |
| Kalah | 10 | −400 | **−4.000** |
| Subtotal | | | **−2.200** |
| Spread (25 pts x 100) | | | **−2.500** |
| **Hasil akhir** | | | **−4.700 points** |

Winrate 90%. Rugi 4.700 points.

Pada modal Rp 800.000 di akun cent dengan risiko 3%, sistem seperti ini
menghabiskan modal dalam waktu sekitar 2–4 bulan — sambil memberi perasaan
"sedang menang" hampir setiap hari.

**Kesimpulan pertama:** masalahnya bukan mencapai winrate 90%. Masalahnya
adalah winrate 90% dan profitabilitas saling bertentangan secara matematis.

---

## 2. Hukum yang Tidak Bisa Dilanggar

Ada hubungan matematis yang berlaku universal:

> **Semakin tinggi winrate, semakin kecil rasio TP terhadap SL yang bisa
> Anda peroleh.**

Ini bukan kelemahan strategi tertentu. Ini konsekuensi langsung dari sifat
pergerakan harga. Untuk menang lebih sering, target harus lebih dekat; target
lebih dekat berarti profit lebih kecil, dan SL harus lebih jauh agar tidak
tersentuh duluan.

### 2.1 Breakeven Risk-Reward

Untuk setiap winrate, ada RR minimum agar sistem tidak rugi:

```
RR_breakeven = (1 − winrate) / winrate
```

Bandingkan dengan RR yang realistis bisa diperoleh di pasar:

| Winrate | RR realistis di pasar | RR breakeven | Selisih (= edge) |
|---|---|---|---|
| 90% | 1 : 0,11 | 1 : 0,11 | **0** |
| 80% | 1 : 0,25 | 1 : 0,25 | **0** |
| 70% | 1 : 0,43 | 1 : 0,43 | **0** |
| 60% | 1 : 0,67 | 1 : 0,67 | **0** |
| 50% | 1 : 1,00 | 1 : 1,00 | **0** |
| **45%** | **1 : 2,00** | 1 : 1,22 | **+0,78** |
| **40%** | **1 : 2,50** | 1 : 1,50 | **+1,00** |
| 35% | 1 : 3,00 | 1 : 1,86 | **+1,14** |

Kolom terakhir adalah inti seluruh persoalan.

Di winrate tinggi, RR yang bisa diperoleh **persis sama** dengan RR yang
dibutuhkan untuk impas. Selisihnya nol. Tidak ada ruang untuk profit — dan
belum menghitung biaya transaksi.

Di winrate 40–45%, ada jarak lebar antara keduanya. **Jarak itulah edge.**

> **Edge tidak berasal dari sering menang. Edge berasal dari jarak antara
> RR yang diperoleh dan RR yang dibutuhkan untuk impas.**

### 2.2 Mengapa Angka di Kolom Kedua Bukan Karangan

Angka "RR realistis" di atas bukan asumsi sembarangan. Itu konsekuensi dari
probabilitas: peluang harga menyentuh jarak X sebelum jarak Y kira-kira
berbanding terbalik dengan rasio jaraknya.

Artinya, dalam pasar yang efisien, **hasil kali winrate dengan RR cenderung
konstan**. Anda bisa memilih kombinasinya, tapi tidak bisa memaksimalkan
keduanya sekaligus. Menaikkan yang satu menurunkan yang lain.

Inilah kendala teknis yang sesungguhnya. Bukan keterbatasan model, data,
atau komputasi.

---

## 3. Spread: Yang Mengubah "Impas" Menjadi "Rugi"

Tabel di Bagian 2.1 menunjukkan sistem winrate tinggi berada di titik impas.
Spread-lah yang mendorongnya ke wilayah rugi — dan dampaknya tidak merata.

**Spread menghantam TP kecil jauh lebih keras:**

| Target TP | Spread 25 pts | Profit bersih | Porsi termakan |
|---|---|---|---|
| 20 points | 25 | **−5** | **125%** |
| 30 points | 25 | 5 | 83% |
| 50 points | 25 | 25 | 50% |
| 100 points | 25 | 75 | 25% |
| 200 points | 25 | 175 | 12,5% |
| 400 points | 25 | 375 | **6,25%** |

Baris pertama layak dibaca dua kali: **dengan TP 20 points dan spread 25
points, trade yang "menang" tetap menghasilkan kerugian.** Harga bergerak
persis sesuai prediksi, tapi biayanya melebihi profitnya.

Sistem winrate 90% membutuhkan TP kecil. TP kecil adalah yang paling
dihancurkan spread. Keduanya tidak bisa didamaikan.

**Ini kendala teknis paling konkret:** biaya transaksi melebihi target profit.
Tidak ada model, indikator, atau arsitektur AI yang bisa mengubah aritmetika
ini.

---

## 4. Mengapa Modal Kecil Memperparah Situasi

Modal kecil tidak mengubah hukum di atas, tetapi menciptakan tekanan yang
mendorong ke arah yang salah.

**Logika yang terasa masuk akal tapi menyesatkan:**

```
"Modal kecil, jadi harus diputar cepat"
        -> perkecil TP agar sering profit
        -> perkecil SL agar rugi kecil
        -> perbanyak frekuensi trade
        -> masuk tepat ke zona di mana spread memakan segalanya
```

Bandingkan dua trader dengan sistem identik:

| | Modal Rp 500 juta | Modal Rp 800 ribu |
|---|---|---|
| Risiko 0,5% | Rp 2.500.000 | Rp 4.000 |
| Terasa seperti | Jumlah berarti | Tidak berarti |
| Dorongan psikologis | Sabar menunggu setup | "Harus lebih agresif" |
| TP yang dipilih | 400 points (santai) | 30 points (buru-buru) |
| Hasil | Profitabel | Termakan biaya |

Sistemnya sama. Hukum pasarnya sama. Yang berbeda hanya tekanan psikologis —
dan tekanan itulah yang menghancurkan akun kecil, bukan ukuran modalnya.

**Konsekuensi kedua modal kecil:** untuk menghasilkan jumlah yang terasa
berarti, risiko per trade harus dinaikkan. Risiko naik berarti probabilitas
kehancuran naik. Ini trade-off yang melekat, bukan masalah yang bisa
dipecahkan dengan sistem yang lebih baik.

---

## 5. Yang Bisa Dioptimalkan vs Yang Tidak Bisa

Ini pemetaan jujur, agar upaya diarahkan ke tempat yang menghasilkan.

### 5.1 BISA Dioptimalkan — dan Sudah Ada di Plan

| Optimasi | Dampak | Cara |
|---|---|---|
| **Turunkan spread** | Expectancy +25% | Broker ECN, spread 25 -> 15 pts |
| **Pilih jam terbaik** | Expectancy +15% | Hanya London open & NY overlap |
| **Naikkan winrate tanpa mengecilkan TP** | Expectancy +20-30% | **Ini tugas ML meta-labeling** |
| **Maksimalkan sisi menang** | RR 2,0 -> 2,5 | Trailing stop, partial close |
| **Kurangi trade buruk** | Expectancy +10-20% | Skoring konfluensi, gate spread |

**Efek gabungan:** ini bisa menggeser sistem dari impas menjadi profitabel.
Nyata, terukur, dan seluruhnya sudah masuk dalam rencana kerja.

Perhatikan baris ketiga secara khusus. **Inilah satu-satunya jalur sah
menuju winrate lebih tinggi:** menyaring setup buruk agar winrate naik dari
40% ke 50–55% **sambil mempertahankan TP besar**. Bukan dengan mengecilkan
target.

Naik ke 55% dengan RR tetap 1:2 adalah hasil yang sangat baik dan realistis.
Itu target sistem ini.

### 5.2 TIDAK BISA Dipecahkan Siapa Pun

| Yang diinginkan | Status |
|---|---|
| Winrate 90% **dan** profitabel | Kontradiksi matematis |
| Profit besar dari modal kecil **tanpa** risiko besar | Kontradiksi matematis |
| Menghilangkan spread | Di luar kendali; itu pendapatan broker |
| Memprediksi rilis berita | Informasi belum ada saat prediksi dibuat |
| Sistem tanpa periode drawdown | Bertentangan dengan sifat statistik |

Baris pertama layak ditegaskan dengan pembanding:

> **Renaissance Technologies** — dana kuantitatif paling sukses dalam
> sejarah, dengan PhD matematika, fisika, dan kriptografi terbaik dunia,
> infrastruktur komputasi masif, serta akses data yang tidak tersedia bagi
> publik — beroperasi pada **winrate sekitar 50,75%**.
>
> Jika sistem winrate 90% yang profitabel dapat dibangun, mereka sudah
> menemukannya beberapa dekade lalu. Mereka tidak menemukannya karena secara
> matematis hal itu tidak ada untuk ditemukan.

Setiap klaim winrate di atas 80% yang beredar berasal dari salah satu dari
empat hal ini:

1. **Martingale/grid** — floating loss tidak dihitung sebagai kekalahan
2. **TP kecil, SL raksasa** — seperti Bagian 1; akun habis pada rentetan loss
3. **Lookahead bias** — backtest melihat data masa depan
4. **Cherry-picking** — hanya periode terbaik yang ditampilkan

---

## 6. Perbandingan Langsung Dua Sistem

Angka konkret, per 100 trade, spread 25 points, modal Rp 800.000, risiko 3%:

| | **Sistem A** (winrate tinggi) | **Sistem B** (expectancy tinggi) |
|---|---|---|
| Winrate | **90%** | 45% |
| TP / SL | 20 / 400 pts | 400 / 200 pts |
| Menang | 90 x 20 = +1.800 | 45 x 400 = +18.000 |
| Kalah | 10 x 400 = −4.000 | 55 x 200 = −11.000 |
| Spread | −2.500 | −2.500 |
| **Net** | **−4.700 pts** | **+4.500 pts** |
| Expectancy | −0,12R | **+0,41R** |
| Perasaan harian | Menang terus | **Sering kalah** |
| Modal setelah 12 bulan | **Rp 0** | **Rp 4.280.000** |

Sistem B kalah lebih sering daripada menang. Sistem B yang menumbuhkan modal.

Baris "perasaan harian" bukan sekadar catatan — itu tantangan sesungguhnya.
Menjalankan Sistem B berarti menerima 55 kekalahan dari 100 trade tanpa
kehilangan disiplin. Secara psikologis jauh lebih berat daripada Sistem A,
meskipun hasilnya berlawanan.

---

## 7. Menjawab Pertanyaan Aslinya

**"Kenapa modal kecil tidak bisa langsung profit besar? Kendalanya di
sistemnya?"**

Bukan di sistemnya. Ada tiga kendala, dan ketiganya berada di luar jangkauan
rekayasa perangkat lunak:

1. **Aritmetika winrate-RR.** Hasil kali keduanya cenderung konstan di pasar
   efisien. Winrate tinggi otomatis berarti RR rendah. Tidak ada model yang
   bisa melanggar ini.

2. **Spread sebagai biaya tetap.** Sistem winrate tinggi butuh TP kecil, dan
   TP kecil adalah yang paling dihancurkan spread. Pada TP 20 points dengan
   spread 25 points, trade yang menang pun tetap rugi.

3. **Profit besar menuntut risiko besar.** Menumbuhkan Rp 800.000 secara
   signifikan memerlukan risiko per trade yang tinggi, dan risiko tinggi
   membawa probabilitas kehancuran yang tinggi. Ini pertukaran yang melekat,
   bukan cacat yang bisa diperbaiki.

**Yang bisa dilakukan** adalah memaksimalkan expectancy: spread serendah
mungkin, jam terbaik, seleksi setup ketat, dan ML untuk menaikkan winrate
dari 40% ke 50–55% tanpa mengorbankan ukuran TP. Itu pekerjaan nyata dengan
hasil terukur, dan itulah isi rencana kerja ini.

**Yang tidak bisa dilakukan** adalah menghapus pertukaran mendasar antara
winrate dan risk-reward. Bukan karena belum ditemukan caranya — melainkan
karena secara matematis tidak ada.

---

## 8. Target yang Benar untuk Sistem Ini

Ini yang akan dikejar, dan alasan setiap angkanya:

| Metrik | Target | Alasan |
|---|---|---|
| Winrate | 45–55% | Hasil dari RR 1:2, bukan tujuan yang dikejar |
| Risk-Reward | 1:2 minimum | Sumber edge sesungguhnya |
| Expectancy | > +0,25R | **Metrik utama — ini yang menumbuhkan modal** |
| Profit Factor | > 1,5 | Validasi konsistensi |
| Max Drawdown | < 25% | Batas risiko mode agresif |

Jika suatu saat muncul dorongan untuk menaikkan winrate dengan mengecilkan
TP, dokumen ini adalah pengingatnya: langkah itu menaikkan angka yang terlihat
bagus sambil menghancurkan angka yang sebenarnya menentukan hasil.

**Ukur sistem ini dengan expectancy. Winrate adalah efek samping, bukan
tujuan.**
