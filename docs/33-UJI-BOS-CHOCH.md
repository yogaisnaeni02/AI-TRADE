# Uji BOS / CHoCH sebagai Filter

**Tanggal:** 10 September 2026
**Permintaan:** "kalau gunain BOS/CHoCH juga gimana?"

---

## Ringkasan

Dua hasil terpisah:

1. **BUG DITEMUKAN:** kolom `choch` tidak pernah menyala sekali pun dalam
   100.000 bar. Kondisinya mustahil terpenuhi. Sudah diperbaiki.
2. **BOS dan CHoCH sebagai filter: TIDAK BERGUNA.** Keduanya menurunkan
   expectancy. Yang berguna justru turunannya yang paling sederhana —
   "tren M5 tidak melawan arah entry".

---

## 1. Bug: CHoCH Tidak Pernah Menyala

`src/strategy/structure.py` menuntut pergantian **langsung** uptrend ↔
downtrend dalam satu bar:

```python
if prev_trend == "downtrend" and cur_trend == "uptrend":
    choch[i] = 1
elif prev_trend == "uptrend" and cur_trend == "downtrend":
    choch[i] = -1
```

Tetapi `classify_trend` **selalu melewati "ranging"** di antaranya. Transisi
yang benar-benar terjadi pada 100.000 bar:

```
downtrend -> ranging     3.411x
ranging   -> downtrend   3.411x
ranging   -> uptrend     3.667x
uptrend   -> ranging     3.666x
uptrend   -> downtrend       0x   <- yang dicari kode
downtrend -> uptrend         0x   <- yang dicari kode
```

Kedua cabang itu **kode mati**. Akibatnya:

- `choch` = 0 di seluruh dataset
- `bars_since_choch` = −1 di seluruh dataset
- Bonus skor "CHoCH konfirmasi" di `setups.py::_london_sweep`
  **tidak pernah diberikan**

Dampak ke sistem yang berjalan: **nol**, karena `london_sweep` sudah
dinonaktifkan dan `momentum_fib` tidak memakai CHoCH. Tetapi ini kolom yang
diam-diam bohong — siapa pun yang memakainya di masa depan akan mendapat
konstanta nol tanpa peringatan.

**Perbaikan:** simpan tren berarah TERAKHIR (bukan tren bar sebelumnya),
lalu tandai saat muncul tren berarah yang berbeda. Setelah diperbaiki CHoCH
menyala **4.230 kali** — angka yang wajar untuk 100.000 bar.

---

## 2. Hasil Pengujian (516 hari, 909 trade baseline)

| Filter | n | E[R] | WR% | PF | dE |
|---|---|---|---|---|---|
| **BASELINE momentum_fib** | 909 | +0,0733 | 28,2 | 1,10 | — |
| **Tren M5 tidak melawan** | **878** | **+0,0882** | 28,6 | 1,12 | **+0,015** |
| Tren M5 searah | 495 | +0,0765 | 28,1 | 1,11 | +0,003 |
| BOS searah ≤12 bar | 373 | +0,0469 | 27,3 | 1,06 | −0,026 |
| BOS searah ≤6 bar | 346 | +0,0411 | 27,2 | 1,06 | −0,032 |
| Ada BOS (arah apa pun) | 277 | +0,0160 | 26,4 | 1,02 | −0,057 |
| BOS searah (bar ini) | 275 | +0,0102 | 26,2 | 1,01 | −0,063 |
| CHoCH(fix) searah ≤24 bar | 319 | −0,0620 | 24,5 | 0,92 | −0,135 |
| JAUH dari CHoCH (>48 bar) | 120 | −0,0744 | 25,0 | 0,90 | −0,148 |

### Kenapa BOS gagal

BOS = harga menembus swing terakhir searah tren. Masalahnya sama dengan MACD
di `docs/32`: **`momentum_fib` sudah menangkap informasi itu lebih awal**.
Saat BOS terkonfirmasi, dorongan yang mau ditumpangi sudah berjalan —
entry jadi terlambat, dan SL 400 pip harus menanggung jarak yang sudah
ditempuh.

Semakin ketat syarat BOS, semakin buruk hasilnya (−0,026R untuk ≤12 bar,
−0,063R untuk bar ini juga). Pola monoton itu memperkuat tafsir
"keterlambatan", bukan kebetulan sampel.

### Kenapa CHoCH gagal, bahkan setelah diperbaiki

CHoCH menandai **pembalikan arah**. `momentum_fib` adalah setup
**kelanjutan tren**. Keduanya bertentangan secara desain: menyaring sinyal
kelanjutan dengan syarat "baru saja berbalik" berarti mengambil trade tepat
saat struktur sedang paling tidak stabil.

Hasilnya negatif di **kedua paruh** (−0,066 dan −0,058) — konsisten, bukan
kebetulan.

Kebalikannya (jauh dari CHoCH) juga negatif, dan berlawanan antar paruh.
Jadi bukan sekadar "arahnya kebalik" — CHoCH memang tidak membawa informasi
yang berguna untuk setup ini.

---

## 3. Stabilitas dan Holdout

| Filter | Paruh-1 | Paruh-2 | Holdout | Vonis |
|---|---|---|---|---|
| BASELINE | +0,081 | +0,066 | +0,026 | — |
| Tren M5 tidak melawan | +0,066 | +0,109 | +0,095 | stabil |
| BOS searah ≤6 bar | +0,012 | +0,070 | +0,305 | stabil tapi E turun |
| BOS searah (bar ini) | +0,050 | **−0,035** | +0,216 | **BERLAWANAN** |
| Ada BOS | +0,068 | **−0,042** | +0,196 | **BERLAWANAN** |
| CHoCH(fix) ≤24 bar | −0,066 | −0,058 | +0,134 | negatif konsisten |
| JAUH dari CHoCH | +0,014 | **−0,166** | −0,181 | **BERLAWANAN** |

Perhatikan varian BOS: **holdout-nya tinggi (+0,216 sampai +0,305) padahal
hasil penuhnya buruk.** Itu justru tanda bahaya — n di holdout cuma 62-87,
dan dua paruh periode seleksi berlawanan arah. Persis pola yang menggugurkan
BB squeeze di `docs/32` dan varian pullback di `docs/31`.

---

## 4. Satu Hal yang Berguna

`Tren M5 tidak melawan` — tolak sinyal buy saat tren M5 downtrend, dan
sebaliknya. Ini syarat paling longgar yang bisa dibuat dari struktur:
membuang hanya 31 dari 909 trade (3,4%).

Diuji sebagai tambahan pada kandidat dari `docs/32`:

| | Seleksi (70%) | HOLDOUT (30%) |
|---|---|---|
| Candle + ADX>25 | +0,1426 (n=476) | +0,1282 (n=164) |
| **+ tren M5 tidak melawan** | **+0,1634** (n=464) | **+0,1547** (n=157) |

Naik di **kedua** periode, dengan ongkos 7 trade. Ditambahkan ke filter
konfluensi opsional (tetap MATI secara default).

---

## 5. Kesimpulan

**BOS dan CHoCH tidak dipakai.** Alasannya bukan implementasi yang kurang
baik, melainkan tumpang tindih konsep:

- **BOS** mengukur hal yang sama dengan momentum(24), hanya lebih terlambat
- **CHoCH** mencari pembalikan, sementara setup ini mencari kelanjutan

Ini pola ketiga kalinya dalam dua hari: MACD (`docs/32`), Stochastic
(`docs/32`), sekarang BOS/CHoCH. **Menambah indikator yang mengukur ulang
informasi yang sudah dipakai tidak menambah edge — hanya menambah
keterlambatan dan mengurangi sampel.**

Yang terbukti membantu justru syarat-syarat sederhana yang mengukur hal
BERBEDA dari sinyal utama: kekuatan tren (ADX), bentuk bar entry (candle),
dan arah struktur (tren M5).

Bug CHoCH tetap diperbaiki meski kolomnya tidak dipakai — kolom yang selalu
bernilai nol adalah jebakan untuk pengembangan berikutnya.
