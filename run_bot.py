"""
Runner bot trading.

Pemakaian:
    python run_bot.py              # jalankan sesuai config
    python run_bot.py --advisor    # paksa mode ADVISOR (sinyal saja)
    python run_bot.py --check      # cek koneksi & konfigurasi, lalu keluar

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
    ap.add_argument("--poll", type=int, default=10, help="interval polling (detik)")
    args = ap.parse_args()

    bot = TradingBot()
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
        print("=" * 58)
        bot.gw.disconnect()
        return 0

    bot.run(poll_seconds=args.poll)
    return 0


if __name__ == "__main__":
    sys.exit(main())
