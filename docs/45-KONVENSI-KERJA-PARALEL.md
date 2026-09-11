# Konvensi Kerja Paralel

**Tanggal:** 11 September 2026
**Kenapa ada:** dua sesi bekerja pada repo ini bersamaan (laptop pribadi +
PC kantor). Sudah terjadi satu konflik merge di `setups.py` dan **dua
tabrakan nomor dokumen** dalam satu hari. Konvensi di bawah mencegahnya,
dan lebih penting: mencegah kode setengah jadi sampai ke bot yang berjalan.

---

## 1. `main` selalu bisa dijalankan bot

PC yang menjalankan bot melakukan `git pull origin main` lalu restart.
Karena itu **`main` tidak boleh memuat kode setengah jadi.**

Yang boleh masuk `main`:
- perbaikan yang sudah diuji (tes lolos)
- dokumentasi
- fitur di belakang flag yang **mati default**

Yang TIDAK boleh masuk `main`:
- eksperimen yang belum jelas dipakai atau tidak
- perubahan jalur sinyal tanpa pengukuran

## 2. Riset di branch, bukan di `main`

```bash
git checkout -b riset/<topik>        # mis. riset/ml-volatilitas
# ... kerja, commit sebanyak perlu ...
git push -u origin riset/<topik>     # opsional, kalau perlu dibagi
```

Merge ke `main` hanya kalau hasilnya **dipakai**. Kalau gagal, branch-nya
dibuang — tapi **dokumennya tetap di-merge**, karena hasil negatif juga
informasi yang mahal (lihat `docs/30`, `docs/35`, `docs/37`).

Branch yang sedang jalan saat dokumen ini ditulis: `riset/ml-volatilitas`.

## 3. Nomor dokumen: ambil blok, jangan nomor berikutnya

Masalahnya: dua sesi sama-sama melihat "nomor bebas berikutnya 43" lalu
sama-sama memakainya.

Aturan: **klaim satu blok 10 nomor di tabel ini sebelum menulis.**

| Blok | Pemilik | Terpakai |
|---|---|---|
| 27–33 | laptop pribadi | 27, 28, 29, 30, 31 |
| 34–42 | PC kantor | 34, 35, 36, 37, 38, 39, 40, 41, 42 |
| 43–49 | PC kantor | 43 |
| 50–59 | laptop pribadi | 44 (di luar blok, sisa pergeseran) |
| 60–69 | PC kantor | — |

Kalau bloknya habis, tambahkan baris baru di tabel ini **dalam commit yang
sama** dengan dokumen pertama di blok itu.

## 4. Sebelum push: selalu `fetch` dulu

```bash
git fetch origin
git log --oneline HEAD..origin/main     # ada yang baru?
git merge origin/main                   # gabungkan dulu kalau ada
```

Menggabungkan lebih awal jauh lebih murah daripada menggabungkan setelah
dua hari kerja menumpuk.

## 5. Kalau konflik di `setups.py` atau `config/`

Hampir selalu **dua fitur berbeda yang dua-duanya valid**, bukan satu benar
satu salah. Sudah terjadi sekali: satu sesi menambah `require_trading_session`,
sesi lain menambah `confluence_filter`, keduanya di tempat yang sama.

Gabungkan keduanya. Jangan pilih salah satu, dan jangan `--ours`/`--theirs`
pada file kode.

Untuk file `.parquet` (biner, tidak bisa di-merge): ambil salah satu lalu
**bangun ulang** dengan `python -m src.features.pipeline` supaya konsisten
dengan `sessions.py` hasil merge.

## 6. Setelah merge yang menyentuh jalur sinyal

Jalankan ini sebelum menganggap selesai:

```bash
python scripts/fix_time_offset.py --check    # data tidak bergeser
python tests/test_risk_manager.py            # 13 tes
python tests/test_order_safety.py            # 7 tes
python tests/test_structure_choch.py         # 4 tes
```

Dan periksa sidik jari config berubah atau tidak:

```bash
python -c "import sys,yaml;sys.path.insert(0,'.');from src.config_fingerprint import describe;print(describe(yaml.safe_load(open('config/settings.yaml',encoding='utf-8')),yaml.safe_load(open('config/risk_limits.yaml',encoding='utf-8')),5))"
```

Kalau hash berubah, **forward test yang sedang berjalan terputus** — trade
sebelum dan sesudah tidak boleh digabungkan. `scripts/compare_live_vs_backtest.py`
sudah memisahkannya otomatis, tapi sadari konsekuensinya sebelum merge.

## 7. Yang tidak boleh diubah tanpa kesepakatan

Karena forward test sedang berjalan di demo:

- `config/settings.yaml`: `momentum_fib`, `trade_distances`, `active_setups`, `mode`
- `config/risk_limits.yaml`: `per_trade`, `daily`, `global`
- `src/strategy/setups.py`: logika `_momentum_fib`
- `src/strategy/sessions.py`: daftar `SESSIONS`

Mengubah salah satunya mengubah sidik jari config dan memulai ulang
forward test dari nol. Bahas dulu.
