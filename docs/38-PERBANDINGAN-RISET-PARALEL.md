# Perbandingan Dua Jalur Riset Paralel

**Tanggal:** 10 September 2026
**Pertanyaan pemilik:** "temanku push juga, coba compare lebih bagus yang mana"

---

## Jawaban Singkat

**Keduanya benar, dan keduanya perlu.** Bukan jawaban diplomatis — keduanya
mengerjakan hal yang berbeda dan hasilnya saling menguatkan:

- **Rekan kerja** menjawab *"adakah strategi LAIN?"* → jawabannya tidak ada
  di M5, dan itu dibuktikan dengan bersih
- **Sesi ini** menjawab *"bisakah strategi YANG ADA diperbaiki?"* → bisa,
  dan lolos holdout tersegel

Yang paling penting: **metode rekan kerja lebih benar daripada metode saya**,
dan setelah filter saya diukur ulang dengan metode mereka, hasilnya
**menguat**, bukan melemah.

---

## 1. Temuan yang Sama, Ditemukan Terpisah

Keduanya menemukan bug yang sama dari arah berbeda, dalam beberapa jam yang
sama, tanpa saling tahu:

**Backtest terpotong halt drawdown 20%.**

| | Terpotong | Periode penuh |
|---|---|---|
| trade | 323 | **909** |
| trade terakhir | 10 Des 2025 | 8 Sep 2026 |
| max drawdown | 20,4% | 49,1% |

Rekan kerja menemukannya saat mengaudit angka `docs/28`. Saya menemukannya
saat baseline uji M1 cuma menghasilkan 31 trade dari 697 sinyal — filter
yang MEMBUANG sinyal malah menghasilkan trade LEBIH BANYAK, yang mustahil.

Dua jalan berbeda, satu bug yang sama, saling mengonfirmasi. Itu bukti yang
lebih kuat daripada satu temuan sendirian.

---

## 2. Perbedaan Metode — dan Siapa yang Benar

Angka kami sempat berbeda: mereka 721 trade / +0,156R, saya 909 / +0,073R.
Ditelusuri, penyebabnya **cara mematikan guardrail saat mengukur**:

| Metode | n | E[R] | t |
|---|---|---|---|
| Mereka: **hanya halt DD** dimatikan, batas harian tetap aktif | 675 | **+0,1327** | **+1,95** |
| Saya: **semua guardrail** dimatikan | 909 | +0,0733 | +1,27 |

**Metode mereka lebih benar.** Alasannya: batas harian (max 6 trade/hari,
max rugi harian, max 3 loss beruntun) adalah bagian dari strategi yang
akan benar-benar berjalan di live. Mematikannya membuat backtest mengukur
sistem yang tidak akan pernah ada.

Yang wajib dimatikan hanya **halt DD**, karena itu menghentikan simulasi
selamanya dan memotong periode — bukan sekadar melewatkan trade.

Angka 675/+0,1327 sedikit berbeda dari 721/+0,1557 milik mereka; selisihnya
kemungkinan dari versi file fitur. Yang penting kesimpulannya sama.

---

## 3. Konsekuensi: Filter Konfluensi Justru Menguat

Filter saya (`candle searah + ADX>25 + tren M5 tidak melawan`) diukur ulang
dengan metode yang benar:

| | Tanpa filter | **Dengan filter** |
|---|---|---|
| n (periode penuh) | 675 | **519** (77%) |
| E[R] | +0,1327 | **+0,2510** |
| **t** | +1,95 | **+3,14** |
| Winrate | 29,8% | **32,8%** |
| Walk-forward | 3/5 fold | **5/5 fold** |
| Belah dua | +0,133 / +0,132 | **+0,207 / +0,298** |
| Holdout 30% | +0,0748 | **+0,2805** |

**t = 3,14 melampaui ambang Bonferroni ~3,0** yang ditetapkan rekan kerja
di `docs/30`. Ini pertama kalinya ada angka di proyek ini yang mencapainya —
`momentum_fib` sendiri hanya 2,38 (versi mereka) atau 1,95 (terukur di sini).

Dan **5/5 fold walk-forward positif**, naik dari 3/5 tanpa filter.

Catatan kejujuran: t = 3,14 diukur pada data yang sama tempat filter dipilih.
Yang membedakannya dari klaim lain adalah **holdout 30% tersegel juga
positif (+0,2805)** — data itu tidak pernah dipakai memilih.

---

## 4. Perbandingan Per Bidang

| Bidang | Rekan kerja | Sesi ini |
|---|---|---|
| **Pertanyaan** | adakah strategi lain? | bisakah yang ada diperbaiki? |
| **Cakupan** | 25 varian M5 + 5 varian H1 | 30 filter di atas momentum_fib |
| **Data** | M5 1,4 thn + H1 9,7 thn | M5 1,4 thn + M1 103 hari |
| **Temuan utama** | tidak ada strategi M5 lain; Donchian H1 layak tapi butuh Rp 17-45 jt | filter konfluensi t=3,14, lolos holdout |
| **Bug ditemukan** | backtest terpotong; data H1 pre-2017 rusak; 7 strategi lama diuji pada jam salah | backtest terpotong; CHoCH kode mati |
| **Metode** | halt DD dimatikan, guardrail lain aktif (benar) | sempat mematikan semua (dikoreksi) |
| **Holdout tersegel** | tidak dipakai | dipakai (30%) |
| **Kode berubah** | tidak (hanya komentar) | gate opsional, mati default |

### Kekuatan masing-masing

**Rekan kerja lebih kuat di:**
- **Cakupan data.** H1 9,7 tahun melewati 5 rezim harga ($1.200 → $4.500).
  Bukti lintas-tahun jauh lebih berbobot daripada 1,4 tahun M5.
- **Analisis modal.** Menghitung bahwa Donchian H1 butuh Rp 17-45 juta
  karena lot minimum — analisis yang menyelamatkan dari strategi yang
  terlihat bagus tapi akan menghabiskan akun.
- **Kejujuran metode.** Menghitung sendiri bahwa ambang t naik ke ~3,0
  setelah 50+ percobaan, lalu menyatakan momentum_fib (2,38) **tidak
  mencapainya**. Itu disiplin yang benar.
- **Menemukan data H1/H4 pre-2017 rusak** — ATR 1,1% per jam pada emas
  $1.250 mustahil, dan 300 bar/tahun bukan H1.

**Sesi ini lebih kuat di:**
- **Holdout tersegel.** Satu-satunya obat untuk multiple testing, dan
  rekan kerja tidak memakainya. Ini yang membuat t=3,14 bisa dipercaya.
- **Verifikasi stabilitas berlapis.** Belah dua + walk-forward + holdout
  menggugurkan 2 kandidat yang tampak menang (BB squeeze +0,149R, pullback
  M1 +0,123R) — keduanya ternyata rata-rata dua paruh berlawanan.
- **Hasil yang bisa langsung dipakai** tanpa tambahan modal.
- **Bug CHoCH** yang membuat kolomnya selalu nol.

---

## 5. Satu Koreksi untuk Rencana Rekan Kerja

`docs/31` bagian 3.4 menempatkan **BOS/CHoCH sebagai filter arah** di daftar
prioritas, disebut "uji termurah di daftar".

**Sudah diuji di sesi ini — hasilnya negatif** (`docs/37`):

| | E[R] | vs baseline |
|---|---|---|
| BOS searah ≤12 bar | +0,0469 | −0,026 |
| BOS searah (bar ini) | +0,0102 | −0,063 |
| CHoCH searah ≤24 bar | −0,0620 | −0,135 |

Ambang lolos yang mereka tetapkan (selisih ≥0,10R, n ≥75%) **tidak tercapai
sama sekali** — arahnya bahkan berlawanan.

Dan ada catatan penting untuk mereka: `docs/31` menulis "structure.py sudah
menghitung `bos`/`choch`". Benar untuk `bos`, **salah untuk `choch`** —
kolom itu bernilai nol di seluruh 100.000 bar karena syaratnya mustahil
terpenuhi. Sudah diperbaiki di sesi ini.

Jadi item #4 di daftar prioritas mereka bisa dicoret, dan waktunya dialihkan
ke #1 (entry presisi M1) atau #3 (lintas-sesi Tokyo→London), yang keduanya
belum tersentuh.

---

## 6. Yang Tidak Bertabrakan

Tidak ada konflik kode. Merge bersih:

- Perubahan mereka di `setups.py` **hanya komentar** (koreksi angka)
- Perubahan saya menambah **gate opsional yang mati secara default**
- Dokumen digeser: milik saya 30-33 → **34-37**, milik mereka tetap 30-31

Default terverifikasi tidak berubah setelah merge: n=675, E=+0,1327,
`confluence_filter: False`.

---

## 7. Rekomendasi

**Jangan pilih salah satu.** Urutan yang masuk akal:

1. **Sekarang:** lanjutkan forward test tanpa perubahan. Kedua jalur sepakat
   soal ini, dan `docs/29` melarang mengubah jalur sinyal.

2. **Setelah forward test (~200 trade):** aktifkan filter konfluensi. Ini
   satu-satunya kandidat yang lolos holdout tersegel DAN melampaui ambang
   t~3,0, dan tidak butuh modal tambahan.

3. **Kalau modal naik ke Rp 17 jt+:** pertimbangkan Donchian H1 rekan kerja
   sebagai edge **kedua** yang berjalan berdampingan — bukan pengganti. Dua
   edge tidak berkorelasi (intraday momentum vs multi-day trend) saling
   melunakkan drawdown. Syaratnya: ukur `swap_mode` dulu, dan port ke
   `backtest/engine.py`.

4. **Riset berikutnya:** ikuti `docs/31` milik rekan kerja, coret item #4
   (BOS/CHoCH, sudah gugur), prioritaskan #1 dan #3.

### Satu hal yang perlu diketahui pemilik

Rekan kerja menemukan **drawdown alami strategi ini 32-49%**, sementara kill
switch dipasang di 20%. Artinya kill switch **diharapkan menyala** sekitar
sekali per 1,4 tahun. Itu rem bekerja sesuai desain, bukan kerusakan —
tetapi berarti akan ada momen di mana bot berhenti sendiri dan butuh reset
manual `logs/risk_state.json` setelah dievaluasi.

Filter konfluensi tidak menghilangkan ini (maxDD dengan filter 20,8% vs
20,4% tanpa) — yang menurunkan drawdown adalah **ukuran risiko per trade**,
persis seperti kesimpulan rekan kerja di `docs/30` bagian 1.5.

---

## 8. Rekonsiliasi Setelah Merge Kedua (10 Sep 2026, malam)

Rekan kerja menandai satu blocker di `docs/31`: angka baseline "tanpa
filter" tidak cocok antara `docs/38` (n=675, t=1,95) dan pengukuran mereka
pasca-merge (n=897, t=2,14). Diselesaikan di sini.

### Temuan mereka yang mengubah data

`fix_time_offset.py` hanya menggeser kolom `time_utc`, **tidak menghitung
ulang kolom turunannya**. File `data/processed/` punya `time_utc` benar
tetapi `session`, `is_trading_session`, `hour_utc`, `asia_high/low`, dan
`sweep_*` masih nilai lama yang meleset 7 jam.

Mereka membangun ulang file fitur dari raw. Diverifikasi di sesi ini:

```
label sesi tersimpan cocok dgn time_utc : 100,0%
is_trading_session True                 : 100,0%
```

Sebelum rebuild, backtest memblokir 7 jam penuh (06–13 UTC, termasuk
seluruh sesi London) sementara bot live menghitung sesi dengan benar —
backtest dan live menguji jam yang berbeda. Temuan yang bagus.

### Angka konfluensi diukur ulang pada data hasil rebuild

| | Tanpa filter | Dengan filter |
|---|---|---|
| Sinyal | 4.189 | 2.038 |
| n | 675 | **519** (77%) |
| E[R] | +0,1327 | **+0,2510** |
| t | +1,95 | **+3,14** |
| Paruh-1 / Paruh-2 | +0,133 / +0,132 | +0,207 / +0,298 |
| Holdout 30% | +0,0748 | **+0,2805** |

**Identik sampai empat desimal dengan `docs/36` dan `docs/38`.** Angka
konfluensi tidak terpengaruh rebuild, jadi tetap sahih.

### Kenapa n=675 vs n=897 berbeda

Selisihnya **bukan** data, melainkan guardrail mana yang dimatikan:

| Cara mengukur | n | E[R] | t |
|---|---|---|---|
| Hanya halt DD dimatikan (dipakai docs/36 & 38) | **675** | +0,1327 | +1,95 |
| Semua guardrail dimatikan | 909 | +0,0733 | +1,27 |
| min_score 6, hanya halt DD | 796 | +0,1501 | +2,39 |

Angka 897 tidak tereproduksi pada kombinasi mana pun dengan file fitur
sekarang — kemungkinan besar diukur **sebelum** rebuild mereka sendiri
selesai, atau dengan `min_score` berbeda.

**Yang penting:** perbandingan konfluensi selalu memakai baseline dan
metode yang SAMA (675, hanya halt DD dimatikan), diukur pada file yang
sama, dalam satu proses. Jadi selisih +0,1327 → +0,2510 sahih apa pun
angka absolut baseline yang dipilih.

Blocker ini **selesai**: bukan ketidakcocokan data, melainkan dua cara
mengukur yang berbeda. Standar yang dipakai ke depan: **hanya halt DD yang
dimatikan**, sesuai alasan di bagian 2.

---

## 9. Penutup Rekonsiliasi: Penyebab n=897 Ditemukan (10 Sep 2026, malam)

Bagian 8 menutup blocker dengan dugaan *"kemungkinan besar diukur sebelum
rebuild, atau dengan `min_score` berbeda"*. Dugaan kedua benar, dan sekarang
terbukti persis.

### Penyebabnya `min_score`

Diukur pada file fitur yang sama pasca-merge, metode sama (hanya halt DD
dimatikan, batas harian tetap aktif):

| `min_score` | sinyal | n | E[R] | t | keterangan |
|---|---|---|---|---|---|
| 3 | 7.621 | **897** | +0,1254 | 2,14 | angka yang tidak tereproduksi di bagian 8 |
| **5** | 7.285 | **885** | +0,1300 | **2,20** | **yang dipakai bot live** |
| 6 | — | 796 | +0,1501 | 2,39 | (diuji di bagian 8) |
| **7** | 4.189 | **675** | +0,1327 | **1,95** | **dipakai `docs/36` & `docs/38`** |

n=897 adalah `min_score=3`. Bagian 8 menguji `min_score=6` tetapi tidak 3,
sehingga tidak ketemu.

### Temuan yang lebih penting: `min_score` live ≠ `min_score` yang diukur

- `RuleEngine.generate()` default signature-nya **`min_score=7`**
- `TradingBot.__init__` memakai **`min_score=5`** (`bot.py:53`)

Siapa pun yang memanggil `generate(df)` tanpa argumen mengukur sistem yang
**berbeda dari yang berjalan live**. Seluruh angka `docs/36` dan `docs/38`
diukur pada `min_score=7`.

**Ini divergensi backtest↔live yang ketiga di proyek ini**, setelah
`max_bars` (`docs/30` §0.1) dan label sesi (bagian 8). Polanya identik:
nilai default di satu tempat, nilai berbeda di tempat lain, tidak ada yang
mengikat keduanya.

### Konsekuensi untuk t = 3,14

| `min_score` | tanpa filter | dengan konfluensi |
|---|---|---|
| 7 | t 1,95 | **t 3,14** — lolos ambang |
| **5 (live)** | t 2,20 | **t 2,42** — belum lolos |

Angka 519 / +0,2510 / t 3,14 **direproduksi persis** di sesi ini, jadi
sahih. Tetapi berlaku **hanya pada `min_score=7`**. Pada setelan yang
benar-benar berjalan, filter memberi t = 2,42.

Kesimpulan bagian 8 bahwa "selisih +0,1327 → +0,2510 sahih apa pun angka
absolut baseline" tetap benar **sebagai perbandingan relatif** — dan
holdout tersegel menguatkannya di kedua setelan:

| | tanpa filter | dengan filter |
|---|---|---|
| holdout, `min_score` 5 | +0,1455 | **+0,2856** |
| holdout, `min_score` 7 | +0,1022 | **+0,3218** |

Filternya nyata. Yang belum pasti hanya seberapa kuat pada setelan live.

### Temuan sampingan: skor TIDAK terbalik

Larangan "jangan pakai confidence score untuk keputusan apa pun" di
`docs/28` dan `docs/29` bersandar pada temuan lama bahwa skor terbalik
(skor 6 = +0,361R, skor 8 = −0,219R). Temuan itu diukur pada data berlabel
waktu salah 7 jam. Diukur ulang pada data yang sudah benar:

| kelompok skor | penuh | belah-1 | belah-2 | holdout |
|---|---|---|---|---|
| 4–6 | +0,024 | +0,098 | −0,065 | **−0,019** |
| **7–8** | **+0,247** | +0,121 | **+0,347** | **+0,323** |

Skor tinggi **tidak pernah lebih buruk di potongan mana pun**. Larangan itu
dasarnya gugur dan perlu ditinjau ulang.

Catatan kejujuran: belah-1 selisihnya hanya +0,023. Arahnya konsisten,
besarannya tidak — jadi ini membalik klaim lama, bukan menegakkan klaim baru.

### Keputusan yang menunggu pemilik

Menaikkan `min_score` bot 5 → 7 membuang skor 4–6 yang terukur lemah
(+0,024) dan menyisakan 7–8 (+0,247). Konsekuensinya **forward test yang
sedang berjalan harus dimulai ulang**, karena jalur sinyal berubah.

- **Tetap 5** — data live tidak terkontaminasi, evaluasi tetap di n=200
- **Pindah ke 7** — setelan lebih baik secara terukur, jam mulai dari nol

Rekomendasi: tetap 5. Data live yang bersih lebih berharga daripada +0,1R
di backtest yang sudah dipakai 50+ percobaan. Tapi apa pun pilihannya,
**samakan default `generate()` dengan `min_score` bot** supaya divergensi
ini tidak terulang.
