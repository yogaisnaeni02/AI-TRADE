"""
Runner bot trading.

Pemakaian:
    python run_bot.py              # jalankan sesuai config apa adanya
    python run_bot.py --varian konfluensi   # jalankan preset bernama
    python run_bot.py --daftar-varian       # lihat semua preset tersedia
    python run_bot.py --advisor    # paksa mode ADVISOR (sinyal saja)
    python run_bot.py --check      # cek koneksi & konfigurasi, lalu keluar
    python run_bot.py --allow-real # izinkan EXECUTOR di akun REAL (sengaja)

Tanpa --varian, bot memakai settings.yaml APA ADANYA - perilaku lama,
tidak berubah. --varian memuat preset dari config/variants.yaml dengan
magic number sendiri, sehingga beberapa varian bisa berjalan berdampingan
di akun demo yang sama tanpa posisi/journal-nya bercampur.

Tanpa --allow-real, bot MENOLAK jalan bila mendeteksi akun real di mode
EXECUTOR. Itu disengaja: basis bukti strategi ini belum memenuhi ambang
untuk uang sungguhan (docs/28-HASIL-KALIBRASI-ULANG.md bagian 4).

Kill switch: buat file bernama STOP di folder ini. Bot berhenti membuka
posisi baru (posisi terbuka tetap dikelola sampai tertutup).
"""

import argparse
import sys
from pathlib import Path

from src.execution.bot import TradingBot


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--advisor", action="store_true", help="mode sinyal saja")
    ap.add_argument("--check", action="store_true", help="cek koneksi lalu keluar")
    ap.add_argument(
        "--poll", type=int, default=3,
        help=(
            "interval polling (detik). DIUBAH dari 10 -> 3 (13 Sep 2026) "
            "atas permintaan pemilik untuk deteksi bar baru lebih cepat. "
            "Satu siklus build_frame() makan ~1 detik; nilai di bawah 2 "
            "berisiko siklus saling tumpuk saat MT5/network melambat."
        ),
    )
    ap.add_argument(
        "--varian", default=None,
        help="preset dari config/variants.yaml (kosong = settings.yaml apa adanya)",
    )
    ap.add_argument(
        "--daftar-varian", action="store_true",
        help="tampilkan semua varian terdaftar, lalu keluar",
    )
    ap.add_argument(
        "--allow-real",
        action="store_true",
        help="izinkan EXECUTOR di akun REAL (tanpa ini bot berhenti)",
    )
    args = ap.parse_args()

    if args.daftar_varian:
        from src.variants import format_table
        print(format_table())
        return 0

    if args.poll < 2:
        print(f"!! --poll {args.poll} sangat agresif — satu siklus build_frame()")
        print("   makan ~1 detik, jadi risiko siklus saling tumpuk saat MT5")
        print("   atau jaringan melambat. Tetap dijalankan sesuai permintaan.")

    bot = TradingBot(variant=args.varian)
    bot.allow_real = args.allow_real
    if args.advisor:
        bot.mode = "ADVISOR"

    if args.check:
        from src.execution.order_manager import OrderManager
        import MetaTrader5 as mt5

        bot.gw.connect()
        bot.orders = OrderManager(bot.gw)
        acc = mt5.account_info()
        info = mt5.symbol_info(bot.symbol)
        df = bot.build_frame()

        print("=" * 58)
        print("PEMERIKSAAN SISTEM")
        print("=" * 58)
        print(f"  Varian        : {bot.variant_name}  (magic {bot._magic})")
        print(f"  Akun          : {acc.login} @ {acc.server}")
        print(f"  Tipe          : {'DEMO' if acc.trade_mode == 0 else 'REAL'}")
        print(f"  Equity        : Rp {acc.equity:,.0f}")
        print(f"  Simbol        : {bot.symbol} (spread {info.spread} pts)")
        print(f"  Algo trading  : {'AKTIF' if bot.gw.is_trade_allowed() else 'TIDAK AKTIF'}")
        print(f"  Mode          : {bot.mode}")
        print(f"  Kill switch   : {'AKTIF (STOP ada)' if bot.stop_requested() else 'tidak aktif'}")
        print(f"  Data          : {len(df)} bar, terakhir {df.iloc[-1]['time_utc']}")
        print(f"  Sesi saat ini : {df.iloc[-1]['session']}")
        print(f"  Posisi terbuka: {len(bot.orders.get_positions())}")
        if bot.mode == "EXECUTOR" and acc.trade_mode != 0 and not bot.allow_real:
            print("  !! AKUN REAL + EXECUTOR: bot akan MENOLAK jalan.")
            print("  !! Tambahkan --allow-real bila memang disengaja.")
        print("=" * 58)
        bot.gw.disconnect()
        return 0

    bot.run(poll_seconds=args.poll)
    return 0


if __name__ == "__main__":
    sys.exit(main())
