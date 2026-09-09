# XAUUSD Trading Assistant

Sistem asisten trading XAUUSD berbasis machine learning, berjalan lokal
dan terhubung ke MetaTrader 5.

**Status:** Tahap perencanaan — belum ada implementasi
**Modal:** Rp 800.000 (akun cent)
**Timeframe:** M5 utama, M1 untuk timing entry
**Mode risiko:** Agresif (3% per trade)

---

## Urutan Baca Dokumen

| # | Dokumen | Isi | Untuk siapa |
|---|---|---|---|
| 1 | [docs/00-MASTER-PLAN.md](docs/00-MASTER-PLAN.md) | Arsitektur, ilmu trading, metodologi ML | Teknis |
| 2 | [docs/01-SMALL-CAPITAL-AGGRESSIVE.md](docs/01-SMALL-CAPITAL-AGGRESSIVE.md) | Parameter modal kecil, leverage, spread | Teknis + klien |
| 3 | [docs/02-KENAPA-WINRATE-TINGGI-TIDAK-BISA.md](docs/02-KENAPA-WINRATE-TINGGI-TIDAK-BISA.md) | Penjelasan kendala matematis | **Klien** |
| 4 | [docs/03-ROADMAP-DETAIL.md](docs/03-ROADMAP-DETAIL.md) | Rencana kerja tahap demi tahap | Teknis + klien |

**Jika hanya sempat membaca satu:** dokumen 03 (roadmap).
**Jika menjelaskan ke klien:** mulai dari dokumen 02.

---

## Ringkasan Pendekatan

**Target sistem:**

| Metrik | Target | Catatan |
|---|---|---|
| Expectancy | > +0,25R | **Metrik utama** |
| Winrate | 45–55% | Efek samping, bukan tujuan |
| Risk-Reward | 1:2 minimum | Sumber edge sesungguhnya |
| Profit Factor | > 1,4 | |
| Max Drawdown | < 25% | Batas mode agresif |

**Yang tidak dikejar:** winrate tinggi. Winrate 90% mudah dibuat (TP kecil,
SL besar) tetapi menghasilkan kerugian. Penjelasan lengkap di dokumen 02.

**Ilmu trading yang dipakai:**
- Market structure (BOS, CHoCH) sebagai filter arah
- Analisis sesi — London & NY overlap saja
- Liquidity sweep sebagai setup unggulan
- ATR sebagai dasar seluruh perhitungan risiko
- ML sebagai penyaring kualitas sinyal (meta-labeling), bukan prediktor harga

---

## Status Lingkungan

| Item | Status |
|---|---|
| MetaTrader 5 | Terinstall |
| Python 3.13.4 (64-bit) | Terinstall |
| Paket `MetaTrader5` 5.0.5735 | Terinstall |
| Koneksi MT5 ↔ Python | **Belum** — terminal belum login |
| Broker | **Belum dipilih** — blocker utama |

---

## Langkah Berikutnya

1. **Pilih broker** dengan akun cent yang menyediakan XAUUSD
   (kriteria: dokumen 01, Bagian 2.1)
2. Buka **akun demo** di broker tersebut
3. Login MT5, aktifkan: Tools → Options → Expert Advisors →
   "Allow algorithmic trading"
4. Jalankan verifikasi:

```bash
python scripts/phase0_probe.py
```

Script bersifat read-only — tidak membuka posisi. Outputnya menampilkan
spesifikasi simbol, kedalaman riwayat, spread per sesi, dan verifikasi
position sizing.

**Yang harus diperiksa di output:** bagian VERIFIKASI POSITION SIZING harus
menampilkan `[OK]`. Jika `[BAHAYA]`, broker tersebut tidak layak — ganti
sebelum melanjutkan.

---

## Struktur Project

```
PROJECT CUAN/
├── docs/          # Dokumentasi perencanaan
├── scripts/       # Utilitas (probe broker)
├── config/        # Konfigurasi (belum dibuat)
├── src/           # Kode sistem (belum dibuat)
├── backtest/      # Engine backtest (belum dibuat)
└── data/          # Data historis (belum dibuat)
```

---

## Catatan Risiko

Trading forex/CFD berisiko tinggi. Mayoritas trader ritel mengalami kerugian.

Sistem ini adalah alat bantu, bukan jaminan profit. Mode agresif (risiko 3%
per trade) memiliki probabilitas kehilangan sebagian besar modal sekitar 15%
dalam 12 bulan, bahkan dengan sistem yang memiliki edge positif.

Gunakan hanya modal yang siap hilang. Performa masa lalu tidak menjamin
hasil di masa depan.
