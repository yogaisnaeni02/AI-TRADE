"""
Runner TERPISAH untuk setup frequent_micro — versi frekuensi tinggi.

Sengaja file berbeda dari run_bot.py agar sistem utama (momentum_fib) yang
sudah berjalan tidak tersentuh. Setup ini punya marjin keuntungan jauh
lebih tipis (+0,21% di atas breakeven, dibanding +5-7% untuk momentum_fib),
jadi memakai risiko lebih kecil dan limit harian lebih ketat sebagai
pengaman tambahan.

TIDAK BOLEH dijalankan bersamaan dengan run_bot.py pada AKUN YANG SAMA —
keduanya akan berebut koneksi MT5 (satu koneksi per proses) dan berebut
slot "1 posisi terbuka" di risk manager. Jalankan salah satu, atau jalankan
frequent_micro di akun demo terpisah.

Pemakaian:
    python run_bot_frequent.py --check
    python run_bot_frequent.py --advisor   (disarankan - amati dulu)
    python run_bot_frequent.py
"""

import argparse
import sys

from src.execution.bot import TradingBot


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--advisor", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--poll", type=int, default=10)
    args = ap.parse_args()

    bot = TradingBot(
        allowed_setups=("frequent_micro",),
        min_score=3,
        max_score=99,
    )
    if args.advisor:
        bot.mode = "ADVISOR"

    if args.check:
        import MetaTrader5 as mt5

        from src.execution.order_manager import OrderManager

        bot.gw.connect()
        bot.orders = OrderManager(bot.gw)
        acc = mt5.account_info()
        info = mt5.symbol_info(bot.symbol)
        df = bot.build_frame()

        print("=" * 58)
        print("PEMERIKSAAN — SETUP FREQUENT_MICRO (eksperimental)")
        print("=" * 58)
        print(f"  Akun          : {acc.login} @ {acc.server}")
        print(f"  Tipe          : {'DEMO' if acc.trade_mode == 0 else 'REAL'}")
        print(f"  Equity        : Rp {acc.equity:,.0f}")
        print(f"  Simbol        : {bot.symbol} (spread {info.spread} pts)")
        print(f"  Setup aktif   : {bot.allowed_setups}")
        print(f"  Mode          : {bot.mode}")
        print()
        print("  PERINGATAN: marjin keuntungan setup ini +0,21% di atas")
        print("  breakeven — jauh lebih tipis daripada momentum_fib (+5-7%).")
        print("  Disarankan risiko lebih kecil dan pantau ketat.")
        print("=" * 58)
        bot.gw.disconnect()
        return 0

    bot.run(poll_seconds=args.poll)
    return 0


if __name__ == "__main__":
    sys.exit(main())
