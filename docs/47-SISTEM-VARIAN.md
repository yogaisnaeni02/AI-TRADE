# Sistem Varian — Pisah Fitur, Bandingkan, Jalankan Berdampingan

**Tanggal:** 12 September 2026
**Permintaan pemilik:** "bisa gak sih kita pisahin jadi per fitur gitu
biar kita pun gampang gunain yang mana dan bandinginnya untuk testing."

---

## Masalah Sebelumnya

Sistem punya beberapa fitur — filter konfluensi, sisi sell, dan (nanti)
filter ML — masing-masing punya flag sendiri tersebar di
`config/settings.yaml`: `confluence_filter`, `allow_sell`, dst. Untuk
menjalankan satu kombinasi tertentu harus mengedit `settings.yaml` manual,
dan tidak ada cara cepat membandingkan "mana yang lebih baik" tanpa
membaca kode satu per satu.

---

## Yang Dibangun

### 1. `config/variants.yaml` — daftar preset bernama

```yaml
varian:
  baseline:             # BUY saja, tanpa fitur tambahan
    magic: 20260909
  konfluensi:            # baseline + filter candle/ADX/tren
    magic: 20260910
  dua_arah:              # baseline + sell (eksperimen demo)
    magic: 20260911
  dua_arah_konfluensi:   # gabungan, belum diukur
    magic: 20260912
  ml_walkforward:        # riset, belum terintegrasi
    magic: 20260913
```

Tiap varian **menyatakan nilai penuh** tiap flag yang relevan (bukan cuma
yang diaktifkannya), supaya satu varian tidak diam-diam mewarisi flag
varian lain lewat `settings.yaml` yang berubah dari waktu ke waktu.

### 2. `src/variants.py` — loader

`resolve(nama, config_dasar)` mengembalikan `(config_hasil, magic, meta)`.

**Penting:** `resolve(None, ...)` mengikuti `settings.yaml` **apa
adanya** — tidak diam-diam memilih preset "baseline". Ini krusial:
`settings.yaml` sendiri sudah punya `allow_sell: true` tertulis langsung
di sana (eksperimen dua-arah teman kerja yang sedang berjalan). Kalau
`resolve(None)` memaksa preset baseline, bot yang jalan sekarang akan
kehilangan eksperimennya begitu kode ini di-pull — itu bug yang saya
tangkap dan perbaiki sebelum commit (lihat bagian 5).

### 3. Magic number per varian

Tiap varian punya magic sendiri (`20260909` s.d. `20260913`). Ini
memungkinkan **beberapa varian berjalan berdampingan** di akun demo yang
sama tanpa posisi/journal-nya bercampur — `OrderManager` dan `journal.py`
menyaring berdasarkan magic, bukan cuma satu konstanta tetap.

```python
OrderManager(gateway, magic=20260910)   # posisi varian "konfluensi"
```

### 4. `run_bot.py --varian <nama>`

```bash
python run_bot.py                    # settings.yaml apa adanya (lama)
python run_bot.py --varian konfluensi
python run_bot.py --daftar-varian    # lihat semua preset
```

### 5. `backtest/bandingkan_varian.py` — perbandingan langsung

```bash
python backtest/bandingkan_varian.py
python backtest/bandingkan_varian.py --varian baseline konfluensi
```

Hasil pada data penuh (516 hari), metode standar (hanya halt DD
dimatikan, lihat `docs/38`):

```
VARIAN                magic  PERIODE PENUH                          HOLDOUT 30%
baseline             20260909  n=1136 E[R]=+0.1886 t=+3.59 WR=32.2%  n=261 E[R]=+0.1829 t=+1.67
konfluensi           20260910  n=835  E[R]=+0.2376 t=+3.82 WR=32.9%  n=214 E[R]=+0.2014 t=+1.67
dua_arah             20260911  n=1758 E[R]=+0.1588 t=+3.78 WR=31.1%  n=530 E[R]=+0.1506 t=+1.97
dua_arah_konfluensi  20260912  n=1342 E[R]=+0.1507 t=+3.14 WR=30.8%  n=410 E[R]=+0.0924 t=+1.08
```

**Catatan angka baseline di sini (E[R]=+0,1886) berbeda dari `docs/38`
(+0,1327).** Sebabnya bukan bug — sejak `3407f23` tiga divergensi
backtest-live sudah ditutup (min_score 7→5, trailing dibaca dari config,
max_open_positions dibaca dari config alih-alih hardcode 1). Angka di
sini memakai engine yang sudah benar; `docs/38` memakai engine versi
sebelum perbaikan itu. Ini bukan perbandingan apel-ke-apel dengan dokumen
lama — jangan kutip silang tanpa menyebut versi engine-nya.

`ml_walkforward` sengaja tidak tampil beda dari `dua_arah` — filternya
belum diintegrasikan ke `RuleEngine` (masih riset berdiri sendiri di
`scripts/ml_walk_forward.py`, docs/46). Skrip mencetak peringatan
eksplisit untuk varian dengan `override: {}` supaya ini tidak disalah-
baca sebagai "ML tidak berpengaruh".

### 6. Journal mencatat kolom `magic` dan `varian`

`logs/trades.csv` sekarang punya dua kolom baru. File lama (sebelum
kolom ini ada) dimigrasi otomatis saat `sync_closed_trades()` dipanggil
pertama kali — baris lama diberi `magic=20260909, varian=baseline`,
yang benar untuk semua trade sebelum sistem varian ada.

---

## Yang TIDAK Berubah (diverifikasi eksplisit)

Perubahan ini murni aditif. Diverifikasi sebelum commit:

```python
TradingBot()                    # tanpa argumen varian
# -> magic=20260909, allow_sell=True (ikut settings.yaml apa adanya)
# IDENTIK dengan sebelum perubahan ini ada
```

- `OrderManager(gw)` tanpa argumen magic → `magic=20260909` (sama persis)
- `python run_bot.py` tanpa `--varian` → perilaku lama, tidak berubah
- Bot yang sedang berjalan di PC lain **tidak terpengaruh** oleh `git
  pull` ini — eksperimen dua-arahnya tetap jalan karena `settings.yaml`
  tidak disentuh, dan `resolve(None)` mengikutinya apa adanya

Tes: 11 lulus (13 error pre-existing, tidak terkait — fixture `tmp`
hilang di `test_risk_manager.py`, sudah ada sebelum perubahan ini).

---

## Cara Menambah Varian Baru

1. Tambah entri di `config/variants.yaml`: `magic` baru (belum pernah
   dipakai), `override` (nilai PENUH tiap flag relevan, bukan cuma yang
   diaktifkan), `status`, dan `dokumen` bila ada pengukurannya.
2. Uji lewat `backtest/bandingkan_varian.py --varian <nama_baru>`.
3. Jalankan di demo lewat `run_bot.py --varian <nama_baru>` — magic yang
   berbeda membuatnya aman berdampingan dengan varian lain yang sedang
   jalan di akun yang sama.

**Jangan** mengubah `magic` varian yang sudah pernah dipakai live —
riwayat trade lama di journal akan salah terhubung ke varian yang salah.
