# Position Sizing Adaptif — Lot Besar Saat Keyakinan Tinggi

**Tanggal:** 9 September 2026
**Pertanyaan:** "Kalau tingkat keberhasilannya tinggi, langsung lot besar saja?"

---

## Jawaban Singkat

**Idenya benar dan sudah dibangun. Tetapi dinonaktifkan sampai ada bukti.**

Menaikkan lot saat keyakinan tinggi adalah teknik sah yang dipakai trader
profesional. Syaratnya satu: **skor keyakinan harus benar-benar memprediksi
hasil.**

Pada sistem saat ini, syarat itu belum terpenuhi.

---

## 1. Uji: Apakah Skor Memprediksi Hasil?

Diukur pada 1.370 sinyal `momentum_fib`:

| Skor | Jumlah | Winrate |
|---|---|---|
| 7 | 291 | **33,7%** |
| 8 | 1.079 | **33,0%** |

```
Korelasi skor dengan hasil: -0,006
```

**Praktis nol.** Skor 8 tidak lebih baik dari skor 7 — bahkan sedikit lebih
buruk. Sistem skoring saat ini tidak membedakan sinyal bagus dari sinyal biasa.

Artinya menaikkan lot berdasar skor ini bukan "lot besar saat yakin",
melainkan **lot besar secara acak**.

---

## 2. Dampak Menaikkan Lot Tanpa Sinyal Valid

Simulasi 1.000 skenario, 200 trade, winrate 41%, RR 1:3:

| Strategi lot | Hasil akhir (median) | Drawdown | Peluang bangkrut |
|---|---|---|---|
| **Tetap 3%** | **0,81×** | 46,7% | **1,5%** |
| 2× saat "yakin" (acak) | 0,66× | 65,6% | 17,4% |
| 3× saat "yakin" (acak) | 0,42× | 76,3% | 42,8% |
| Besar terus (10%) | 0,24× | 81,8% | 70,1% |

Menaikkan lot tanpa sinyal keyakinan yang valid membuat hasil **turun**
sekaligus melonjakkan risiko kehilangan modal.

Ini bukan intuisi yang meleset sedikit — arahnya berlawanan sepenuhnya.

---

## 3. Kapan Ide Ini Menguntungkan

Simulasi yang sama, tetapi dengan skor keyakinan yang **benar-benar bekerja**
(sinyal berkeyakinan tinggi menghasilkan WR 55%, sisanya 36%):

| Strategi | Hasil akhir (median) |
|---|---|
| Lot tetap 3% | 0,84× |
| **Lot 2× saat WR benar-benar 55%** | **1,52×** |

Hampir dua kali lipat lebih baik. **Ide Anda tepat — yang kurang adalah
sinyal keyakinannya.**

Inilah alasan mekanismenya dibangun sekarang: begitu sinyal keyakinan yang
valid tersedia, tinggal diaktifkan.

---

## 4. Mekanisme yang Sudah Dibangun

### Konfigurasi (`config/risk_limits.yaml`)

```yaml
adaptive_sizing:
  enabled: false              # <- default NONAKTIF
  max_multiplier: 2.0         # batas keras
  tiers:
    - {min_confidence: 0.60, multiplier: 1.0}
    - {min_confidence: 0.70, multiplier: 1.5}
    - {min_confidence: 0.80, multiplier: 2.0}
```

### Cara kerja

```
Sinyal -> skor konfluensi -> confidence (0..1)
       -> confidence_multiplier() -> pengali risiko
       -> dibatasi max_lot_percent_equity (batas keras)
       -> lot final
```

Contoh bila diaktifkan (equity Rp 3,7 juta, SL 400 pip):

| Confidence | Pengali | Lot | Risiko |
|---|---|---|---|
| 0,50 | 1,0× | 0,02 | 3,78% |
| 0,75 | 1,5× | 0,02 | 3,78% |
| 0,85 | 2,0× | 0,03 | 5,67% |

### Pengaman berlapis

1. **Default nonaktif** — harus diaktifkan secara sadar
2. **`max_multiplier: 2.0`** — tidak bisa lebih dari 2× apa pun confidence-nya
3. **Batas keras `max_lot_percent_equity`** — pengali tidak bisa menembusnya
4. **De-risking drawdown tetap berlaku** — saat rugi, risiko tetap turun

---

## 5. Syarat Aktivasi

Aktifkan **hanya setelah** ketiganya terpenuhi:

- [ ] Forward test minimal **100 trade** di demo
- [ ] Sinyal berkeyakinan tinggi (confidence ≥ 0,8) menghasilkan winrate
      **minimal 10 poin di atas** sinyal biasa
- [ ] Perbedaan itu konsisten di minimal 3 periode berbeda

Cara memeriksa dari journal:

```python
import pandas as pd
t = pd.read_csv('logs/trades.csv')
t['conf'] = t['comment'].str.extract(r'_(\d+)').astype(float) / 10
hi = t[t.conf >= 0.8]
lo = t[t.conf < 0.8]
print(f"conf tinggi: WR {(hi.net_idr>0).mean()*100:.1f}% (n={len(hi)})")
print(f"conf biasa : WR {(lo.net_idr>0).mean()*100:.1f}% (n={len(lo)})")
```

Bila selisihnya kurang dari 10 poin, biarkan `enabled: false`.

### Cara mengaktifkan

Edit `config/risk_limits.yaml`:

```yaml
adaptive_sizing:
  enabled: true
```

Tidak perlu mengubah kode. Bot membaca ulang konfigurasi saat dijalankan.

---

## 6. Jalan Menuju Sinyal Keyakinan yang Valid

Skor konfluensi manual terbukti tidak memprediksi (korelasi −0,006). Yang
berpotensi menghasilkan sinyal keyakinan sungguhan:

**Machine learning (meta-labeling).** Model dilatih memprediksi probabilitas
sinyal berhasil, lalu probabilitas itu dipakai sebagai confidence. Berbeda
dengan skor manual, probabilitas model **dikalibrasi terhadap hasil aktual** —
jadi bisa diverifikasi apakah prediksi 70% benar-benar menang 70% dari waktu.

Semua prasyaratnya sudah siap: 88 fitur, labeling triple-barrier, kerangka
walk-forward. Ini juga yang membuat adaptive sizing bermakna — dua pekerjaan
yang saling melengkapi.

---

## 7. Ringkasan

| Pertanyaan | Jawaban |
|---|---|
| Ide lot adaptif bagus? | **Ya** — bisa hampir 2× lipat hasil |
| Sudah dibangun? | **Ya**, lengkap dengan pengaman |
| Aktif sekarang? | **Tidak** — skor belum memprediksi (korelasi −0,006) |
| Kalau dipaksa aktif? | Hasil turun 0,81× → 0,66×, bangkrut 1,5% → 17,4% |
| Kapan bisa aktif? | Setelah confidence terbukti di 100 trade forward test |
| Apa yang dibutuhkan? | Sinyal keyakinan valid — kandidat terbaik: ML |

Lot tetap 3% bukan pilihan konservatif di sini; itu pilihan yang **secara
matematis lebih baik** selama keyakinannya belum bisa diukur.
