"""
Fase 0 - Probe Lingkungan & Spesifikasi Broker

Jalankan SETELAH MetaTrader 5 terbuka dan sudah login ke akun demo.

    python scripts/phase0_probe.py

Script ini read-only: tidak membuka posisi, tidak mengubah apa pun.
Outputnya adalah data yang dibutuhkan untuk mengunci parameter sistem
(position sizing, filter spread, kedalaman data historis).
"""

import sys
import time
from datetime import datetime

try:
    import MetaTrader5 as mt5
except ImportError:
    sys.exit("Paket MetaTrader5 belum terpasang. Jalankan: pip install MetaTrader5")


def probe_terminal():
    if not mt5.initialize():
        code, desc = mt5.last_error()
        print(f"[GAGAL] Tidak bisa connect ke MT5: ({code}) {desc}")
        if code == -6:
            print("        -> Terminal belum login. Buka MT5, login ke akun demo, lalu ulangi.")
        print("        -> Pastikan juga: Tools > Options > Expert Advisors >")
        print("           'Allow algorithmic trading' sudah dicentang.")
        return False

    ti, ai = mt5.terminal_info(), mt5.account_info()
    print("=" * 62)
    print("TERMINAL")
    print("=" * 62)
    print(f"  Nama          : {ti.name} (build {ti.build})")
    print(f"  Connected     : {ti.connected}")
    print(f"  Trade allowed : {ti.trade_allowed}")
    if not ti.trade_allowed:
        print("  [PERINGATAN] Algo trading belum diizinkan di terminal.")

    if ai:
        mode = {0: "DEMO", 1: "CONTEST", 2: "REAL"}.get(ai.trade_mode, "?")
        print(f"\n  Akun          : {ai.login} @ {ai.server}")
        print(f"  Tipe          : {mode}")
        print(f"  Balance       : {ai.balance} {ai.currency}")
        print(f"  Leverage      : 1:{ai.leverage}")
        if mode == "REAL":
            print("  [PERINGATAN] Ini akun REAL. Gunakan akun DEMO untuk pengembangan.")
    return True


def probe_symbols():
    """Cari nama simbol gold yang dipakai broker ini."""
    all_syms = mt5.symbols_get() or []
    cands = [s.name for s in all_syms if "XAU" in s.name.upper() or "GOLD" in s.name.upper()]

    # Buang pasangan gold yang BUKAN XAU/USD: XAUEUR, XAUGBP, BTCXAU, dst.
    # Tanpa filter ini, urutan alfabet bisa memilih BTCXAUm - instrumen
    # yang sama sekali berbeda.
    def is_gold_usd(name):
        u = name.upper()
        if u.startswith("BTC") or u.startswith("ETH"):
            return False
        return "XAUUSD" in u or u.startswith("GOLD")

    cands = sorted(cands, key=lambda n: (not is_gold_usd(n), "247" in n, len(n)))

    print("\n" + "=" * 62)
    print("SPESIFIKASI SIMBOL GOLD")
    print("=" * 62)
    if not cands:
        print("  Tidak ditemukan simbol gold. Cek Market Watch di MT5.")
        return []

    print(f"  Kandidat: {', '.join(cands)}\n")
    for name in cands:
        mt5.symbol_select(name, True)
        info, tick = mt5.symbol_info(name), mt5.symbol_info_tick(name)
        if not info:
            continue
        print(f"  --- {name} ---")
        print(f"    digits          : {info.digits}")
        print(f"    point           : {info.point}")
        print(f"    contract_size   : {info.trade_contract_size}")
        print(f"    tick_value      : {info.trade_tick_value}   <- KRITIS untuk sizing")
        print(f"    tick_size       : {info.trade_tick_size}")
        print(f"    volume_min      : {info.volume_min}")
        print(f"    volume_step     : {info.volume_step}")
        print(f"    volume_max      : {info.volume_max}")
        print(f"    stops_level     : {info.trade_stops_level} points (jarak SL/TP minimum)")
        print(f"    spread saat ini : {info.spread} points")
        if tick:
            print(f"    bid/ask         : {tick.bid} / {tick.ask}")
        print()
    return cands


def probe_history(symbol):
    """Cek seberapa dalam riwayat yang tersedia per timeframe."""
    print("=" * 62)
    print(f"KEDALAMAN RIWAYAT - {symbol}")
    print("=" * 62)

    timeframes = [
        ("M1", mt5.TIMEFRAME_M1, 750_000),
        ("M5", mt5.TIMEFRAME_M5, 225_000),
        ("M15", mt5.TIMEFRAME_M15, 125_000),
        ("H1", mt5.TIMEFRAME_H1, 31_000),
        ("H4", mt5.TIMEFRAME_H4, 15_000),
    ]

    for label, tf, needed in timeframes:
        bars = mt5.copy_rates_from_pos(symbol, tf, 0, needed)
        if bars is None or len(bars) == 0:
            print(f"  {label:4s}: tidak ada data ({mt5.last_error()})")
            continue
        oldest = datetime.fromtimestamp(bars[0]["time"])
        newest = datetime.fromtimestamp(bars[-1]["time"])
        span_days = (newest - oldest).days
        status = "CUKUP" if len(bars) >= needed * 0.9 else "KURANG"
        print(f"  {label:4s}: {len(bars):>8,} bar | {oldest:%Y-%m-%d} s/d {newest:%Y-%m-%d} "
              f"({span_days} hari) [{status}, butuh ~{needed:,}]")

    print("\n  Jika M1 KURANG: pertimbangkan Dukascopy atau vendor data historis.")


def probe_spread_sample(symbol, minutes=60):
    """Sampel spread dari bar M1 terakhir sebagai gambaran awal."""
    print("\n" + "=" * 62)
    print(f"SAMPEL SPREAD - {symbol} ({minutes} menit terakhir)")
    print("=" * 62)

    bars = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, minutes)
    if bars is None or len(bars) == 0:
        print("  Tidak ada data.")
        return

    spreads = sorted(int(b["spread"]) for b in bars)
    n = len(spreads)
    print(f"  min={spreads[0]}  median={spreads[n // 2]}  max={spreads[-1]} points")
    print(f"  p90={spreads[int(n * 0.9)]} points")
    print("\n  Catatan: ini hanya snapshot sesi saat ini. Untuk model biaya yang")
    print("  benar, kumpulkan sampel spread di Asia / London / NY secara terpisah")
    print("  selama beberapa hari (Fase 1).")


def probe_sizing(symbol, equity=None, risk_pct=3.0, sl_points=200):
    """
    Verifikasi position sizing NYATA di akun ini.

    Ini pengecekan terpenting untuk modal kecil: menjawab apakah lot minimum
    broker memungkinkan risk management yang layak, atau justru memaksa
    risiko yang menghancurkan akun.
    """
    print("\n" + "=" * 62)
    print("VERIFIKASI POSITION SIZING")
    print("=" * 62)

    info = mt5.symbol_info(symbol)
    ai = mt5.account_info()
    if not info or not ai:
        print("  Data tidak tersedia.")
        return

    equity = equity or ai.equity
    # Nilai uang per 1 point untuk 1 lot
    value_per_point_per_lot = info.trade_tick_value * (info.point / info.trade_tick_size)

    print(f"  Equity            : {equity:.2f} {ai.currency}")
    print(f"  Risiko target     : {risk_pct}%")
    print(f"  Asumsi SL         : {sl_points} points")
    print(f"  Nilai/point/lot   : {value_per_point_per_lot:.4f} {ai.currency}")
    print(f"  Leverage akun     : 1:{ai.leverage}")

    risk_amount = equity * (risk_pct / 100.0)
    ideal_lot = risk_amount / (sl_points * value_per_point_per_lot)

    # Bulatkan ke volume_step, tidak boleh di bawah volume_min
    steps = max(1, round(ideal_lot / info.volume_step))
    actual_lot = max(info.volume_min, steps * info.volume_step)
    actual_risk = actual_lot * sl_points * value_per_point_per_lot
    actual_pct = (actual_risk / equity) * 100 if equity else 0

    print(f"\n  Lot ideal (teoretis) : {ideal_lot:.5f}")
    print(f"  Lot minimum broker   : {info.volume_min}")
    print(f"  Lot yang bisa dipakai: {actual_lot}")
    print(f"  Risiko SEBENARNYA    : {actual_risk:.2f} {ai.currency} "
          f"= {actual_pct:.2f}% dari equity")

    print("\n  " + "-" * 58)
    if actual_pct <= risk_pct * 1.3:
        print(f"  [OK] Sizing sesuai target. Akun ini layak untuk sistem.")
    elif actual_pct <= 10:
        print(f"  [PERHATIAN] Risiko {actual_pct:.1f}% di atas target {risk_pct}%.")
        print(f"              Lot minimum membatasi presisi sizing.")
    else:
        print(f"  [BAHAYA] Lot minimum memaksa risiko {actual_pct:.1f}% per trade.")
        print(f"           Rentetan {int(100/actual_pct)} loss menghabiskan akun.")
        print(f"           -> Butuh AKUN CENT, atau modal jauh lebih besar.")
    print("  " + "-" * 58)

    # Margin - membuktikan leverage bukan faktor pembatas
    tick = mt5.symbol_info_tick(symbol)
    if tick and ai.leverage:
        margin = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, actual_lot, tick.ask)
        if margin:
            print(f"\n  Margin utk {actual_lot} lot : {margin:.2f} {ai.currency} "
                  f"({margin / equity * 100:.1f}% dari equity)")
            print(f"  -> Margin bukan faktor pembatas; yang membatasi adalah")
            print(f"     lot minimum dan jarak SL. Menaikkan leverage TIDAK")
            print(f"     mengubah kerugian saat SL kena.")


def probe_spread_by_session(symbol, days=5):
    """Analisis spread per sesi - menentukan jam trading yang layak."""
    print("\n" + "=" * 62)
    print(f"ANALISIS SPREAD PER SESI - {symbol} ({days} hari terakhir)")
    print("=" * 62)

    bars = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, days * 1440)
    if bars is None or len(bars) == 0:
        print("  Tidak ada data.")
        return

    # Sesi berdasarkan jam server broker (biasanya GMT+2/+3).
    # Verifikasi offset server sebelum memakai angka ini untuk produksi.
    sessions = {
        "Asia":            range(0, 8),
        "London open":     range(8, 11),
        "London-NY":       range(13, 17),
        "NY sore":         range(17, 22),
        "Rollover":        range(22, 24),
    }

    info = mt5.symbol_info(symbol)
    pip_factor = info.point / 0.01 if info else 1.0

    buckets = {name: [] for name in sessions}
    for b in bars:
        hour = datetime.fromtimestamp(b["time"]).hour
        for name, hours in sessions.items():
            if hour in hours:
                buckets[name].append(int(b["spread"]))
                break

    print(f"  {'Sesi':<14} {'Median':>7} {'p90':>7} {'Max':>7}   Rekomendasi")
    print("  " + "-" * 58)
    for name, vals in buckets.items():
        if not vals:
            continue
        vals.sort()
        n = len(vals)
        median, p90, mx = vals[n // 2], vals[int(n * 0.9)], vals[-1]
        # Normalisasi ke pip gold (0.01) agar ambang tidak bergantung
        # pada konvensi 'point' broker.
        med_pip = median * pip_factor
        if med_pip <= 20:
            rec = "TRADING UTAMA"
        elif med_pip <= 30:
            rec = "selektif"
        else:
            rec = "HINDARI"
        print(f"  {name:<14} {median:>7} {p90:>7} {mx:>7}   {rec} ({med_pip:.0f} pip)")

    all_vals = sorted(v for vals in buckets.values() for v in vals)
    if all_vals:
        med = all_vals[len(all_vals) // 2]
        print(f"\n  Median keseluruhan: {med} points")
        print(f"  TP minimum yang layak (8x spread): {med * 8} points")
        print(f"  -> Setup dengan target di bawah ini akan termakan biaya.")

    print("\n  CATATAN: jam di atas adalah jam SERVER broker, bukan WIB.")
    print("  Verifikasi offset server sebelum dipakai di logika sesi.")


def main():
    if not probe_terminal():
        mt5.shutdown()
        sys.exit(1)

    cands = probe_symbols()
    if cands:
        primary = cands[0]
        print(f"  Menggunakan '{primary}' untuk pengecekan berikutnya.")
        print("  (Jika ini bukan simbol yang dimaksud, sesuaikan manual.)")

        # Simbol yang baru di-select butuh waktu sinkronisasi sebelum
        # riwayat bar bisa diambil; tanpa ini copy_rates bisa gagal.
        mt5.symbol_select(primary, True)
        for _ in range(20):
            if mt5.copy_rates_from_pos(primary, mt5.TIMEFRAME_M1, 0, 1) is not None:
                break
            time.sleep(0.5)
        print()
        probe_history(primary)
        probe_spread_sample(primary)
        probe_spread_by_session(primary)
        probe_sizing(primary, risk_pct=3.0, sl_points=200)

    print("\n" + "=" * 62)
    print("Salin output ini ke docs/ sebagai catatan spesifikasi broker.")
    print("Yang WAJIB dipakai di risk manager:")
    print("  - tick_value & volume_min  -> position sizing")
    print("  - stops_level              -> jarak SL/TP minimum")
    print("  - median spread per sesi   -> filter entry & jam trading")
    print("=" * 62)
    mt5.shutdown()


if __name__ == "__main__":
    main()
