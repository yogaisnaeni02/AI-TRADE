"""Lepas rem bot - periksa dulu apa yang menahannya, baru lepaskan.

UNTUK APA
---------
Bot bisa berhenti membuka posisi karena beberapa sebab berbeda, dan
masing-masing butuh perlakuan berbeda. Mengedit `logs/risk_state.json`
secara manual berbahaya: sebagian rem TIDAK disimpan di sana, jadi
menghapus file itu sering tidak menyelesaikan apa pun - sementara
`peak_equity` yang ikut terhapus membuat perhitungan drawdown salah.

Skrip ini memeriksa SEMUA sebab lebih dulu, menjelaskan yang ditemukan,
lalu hanya melepas yang memang perlu dilepas.

CARA PAKAI
----------
    python scripts/lepas_rem.py                  # periksa saja, tidak mengubah
    python scripts/lepas_rem.py --varian autoclose_agresif
    python scripts/lepas_rem.py --lepas          # benar-benar lepaskan

YANG PERLU DIKETAHUI
--------------------
Rem harian (rugi 45%, 3 batch beruntun, 100 trade) dihitung ULANG dari
journal setiap siklus, memakai trade BERTANGGAL HARI INI. Rem itu lepas
sendiri lewat tengah malam - tidak ada yang perlu dihapus. Yang benar-
benar tersimpan permanen hanya `halted` (circuit breaker drawdown dan
kegagalan order beruntun).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from src.risk.manager import RiskManager  # noqa: E402
from src.variants import apply_risk_override, apply_variant  # noqa: E402

STOP_FILE = ROOT / "STOP"
RISK_PATH = ROOT / "config" / "risk_limits.yaml"
SETTINGS_PATH = ROOT / "config" / "settings.yaml"


def _settings(varian: str) -> dict:
    base = yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8"))
    return apply_variant(base, varian)[0]


def _risk(varian: str) -> dict:
    base = yaml.safe_load(RISK_PATH.read_text(encoding="utf-8"))
    return apply_risk_override(base, varian)


def rupiah(x: float) -> str:
    return f"Rp {x:,.0f}"


def garis(judul: str = "") -> None:
    print("\n" + "=" * 72)
    if judul:
        print(judul)
        print("-" * 72)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--varian", default=None,
                    help="nama varian (mis. autoclose_agresif). "
                         "Penting: rem dihitung per magic varian.")
    ap.add_argument("--lepas", action="store_true",
                    help="benar-benar lepaskan rem (tanpa ini hanya memeriksa)")
    args = ap.parse_args()

    # RiskManager di main belum menerima nama varian, jadi config-nya
    # dirakit di sini lewat jalur yang sama dengan bot: settings + override
    # varian, lalu risk_limits + override_risk varian. Tanpa ini, angka
    # yang ditampilkan adalah batas varian DASAR (12 trade/hari), bukan
    # batas varian yang benar-benar dijalankan (100 trade/hari).
    if args.varian:
        rm = RiskManager(config=_settings(args.varian), risk=_risk(args.varian))
    else:
        rm = RiskManager()

    rm.load_state()
    now = datetime.now()
    rm.refresh_from_journal(now)

    garis("PEMERIKSAAN REM BOT")
    print(f"  varian        : {args.varian or '(config dasar)'}")
    print(f"  file state    : {rm.state_path}")
    print(f"  waktu         : {now:%d %b %Y %H:%M}")

    penahan: list[str] = []
    permanen: list[str] = []

    # -- 1. File STOP ----------------------------------------------------
    garis("1. File STOP (kill switch manual)")
    if STOP_FILE.exists():
        print(f"  AKTIF - {STOP_FILE}")
        print("  Bot menolak SEMUA entry baru selama file ini ada.")
        penahan.append("file STOP")
    else:
        print("  tidak ada - aman")

    # -- 2. Circuit breaker (SATU-SATUNYA yang permanen) -----------------
    garis("2. Circuit breaker (TERSIMPAN permanen)")
    if rm.state.halted:
        print(f"  AKTIF - {rm.state.halt_reason}")
        print("  Ini TIDAK lepas sendiri. Bot tidak akan jalan sampai direset.")
        permanen.append(rm.state.halt_reason or "halted")
    else:
        print("  tidak aktif - aman")
    print(f"  peak_equity tercatat: {rupiah(rm.state.peak_equity)}")

    # -- 3. Rem harian (lepas sendiri lewat tengah malam) ----------------
    garis("3. Rem harian (dihitung dari journal HARI INI)")
    print(f"  trade hari ini      : {rm.state.day_trades} / {rm.max_daily_trades}")
    print(f"  rugi hari ini       : {rupiah(rm.state.day_pnl)}")
    if rm.loss_mode == "batch":
        print(f"  batch rugi beruntun : {rm.state.consecutive_loss_batches}"
              f" / {rm.max_consec_loss_batches}")
        if rm.state.consecutive_loss_batches >= rm.max_consec_loss_batches:
            penahan.append("batch rugi beruntun")
    else:
        print(f"  loss beruntun       : {rm.state.consecutive_losses}"
              f" / {rm.max_consec_losses}")
        if rm.state.consecutive_losses >= rm.max_consec_losses:
            penahan.append("loss beruntun")
    if rm.state.day_trades >= rm.max_daily_trades:
        penahan.append("batas trade harian")

    # -- 4. Cek apakah rem harian benar-benar lepas besok ----------------
    besok = now + timedelta(days=1)
    rm.refresh_from_journal(besok)
    garis("4. Setelah lewat tengah malam")
    print(f"  trade             : {rm.state.day_trades}")
    print(f"  rugi harian       : {rupiah(rm.state.day_pnl)}")
    print(f"  batch beruntun    : {rm.state.consecutive_loss_batches}")
    print("  -> rem harian lepas SENDIRI, tidak perlu dihapus apa pun.")
    rm.refresh_from_journal(now)  # kembalikan ke kondisi sebenarnya

    # -- Kesimpulan ------------------------------------------------------
    garis("KESIMPULAN")
    if not penahan and not permanen:
        print("  Tidak ada rem yang aktif. Bot seharusnya bisa jalan.")
        print()
        print("  Kalau bot tetap tidak membuka posisi, sebabnya BUKAN rem:")
        print("    - equity di bawah min_equity_idr")
        print("    - filter sinyal (konfluensi ADX 35 membuang 58% sinyal)")
        print("    - di luar sesi trading / akhir pekan")
        print("    - lot minimum memaksa risiko > batas 5%")
        return 0

    if penahan:
        print("  Rem SEMENTARA (lepas sendiri lewat tengah malam):")
        for p in penahan:
            print(f"    - {p}")
    if permanen:
        print("  Rem PERMANEN (harus direset manual):")
        for p in permanen:
            print(f"    - {p}")

    if not args.lepas:
        print()
        print("  Untuk melepaskan, jalankan lagi dengan --lepas")
        return 0

    # -- Lepaskan --------------------------------------------------------
    garis("MELEPASKAN")
    if STOP_FILE.exists():
        STOP_FILE.unlink()
        print(f"  file STOP dihapus")

    if rm.state.halted:
        # peak_equity SENGAJA dipertahankan. Menolnya membuat drawdown
        # dihitung dari nol sehingga breaker tidak akan pernah menyala lagi
        # sampai equity melewati puncak lama - persis kebalikan dari yang
        # diinginkan setelah reset.
        rm.state.halted = False
        rm.state.halt_reason = ""
        rm.save_state()
        print("  circuit breaker direset (peak_equity DIPERTAHANKAN)")
        print(f"  peak_equity tetap {rupiah(rm.state.peak_equity)}")

    if penahan and not permanen:
        print("  Rem harian tidak perlu dilepas - ia dihitung dari journal")
        print("  hari ini dan lepas sendiri lewat tengah malam.")

    print()
    print("  Selesai. Jalankan bot seperti biasa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
