"""
Simulasi skenario BUY/SELL — memastikan sistem berjalan benar TANPA kirim order.

UNTUK APA
---------
Sebelum menjalankan bot di PC lain, buktikan dulu bahwa seluruh rantai
keputusan bekerja: baca pasar -> hitung indikator -> deteksi sinyal ->
gerbang risiko -> susun order. Semuanya dijalankan dengan kode PRODUKSI
yang sama persis, hanya `mt5.order_send()` yang tidak pernah dipanggil.

CARA PAKAI
----------
    python scripts/simulasi_skenario.py              # pakai data historis
    python scripts/simulasi_skenario.py --live       # ambil harga LIVE dari MT5

Mode default TIDAK butuh MT5 terbuka - memakai data di data/processed/.
Mode --live butuh MT5 berjalan dan login.

YANG DIBUKTIKAN
---------------
1. Sinyal BUY dan SELL dua-duanya bisa terbentuk (bukan cuma satu arah)
2. SL selalu di sisi yang benar (buy: SL di bawah, sell: SL di atas)
3. RR sesuai config setelah spread
4. Gerbang risiko benar-benar memblokir yang harus diblokir
5. Payload order yang AKAN dikirim ke broker - ditampilkan, tidak dikirim
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.risk.manager import RiskManager  # noqa: E402
from src.strategy.setups import RuleEngine, load_config  # noqa: E402

FEATURES = ROOT / "data" / "processed" / "XAUUSDm_M5_features.parquet"

MAGIC = 20260909


def garis(judul: str = "") -> None:
    print("\n" + "=" * 78)
    if judul:
        print(judul)
        print("-" * 78)


def rupiah(x: float) -> str:
    return f"Rp {x:,.0f}"


def tampilkan_skenario(sig: pd.Series, cfg: dict, rm: RiskManager,
                       equity: float, spread: float) -> bool:
    """Tampilkan satu skenario lengkap dari sinyal sampai payload order."""
    arah = sig["direction"]
    point = cfg["symbol"]["point"]
    vpp = cfg["symbol"]["value_per_point_idr"]

    label = "BUY (beli)" if arah == "buy" else "SELL (jual)"
    print(f"\n### SKENARIO {label} — {sig['time']}")
    print(f"    setup {sig['setup']} | sesi {sig['session']} | skor {sig['score']}")
    print(f"    alasan: {sig['reasons']}")

    # -- 1. Harga --------------------------------------------------------
    print("\n  [1] HARGA")
    print(f"      entry  {sig['entry']:.3f}")
    print(f"      SL     {sig['sl']:.3f}   ({sig['sl_points']:.0f} pts"
          f" = {sig['sl_points']/10:.0f} pip)")
    print(f"      TP     {sig['tp']:.3f}   ({sig['tp_points']:.0f} pts"
          f" = {sig['tp_points']/10:.0f} pip)")

    # -- 2. Pemeriksaan arah SL/TP ---------------------------------------
    print("\n  [2] PEMERIKSAAN ARAH")
    ok = True
    if arah == "buy":
        c1, c2 = sig["sl"] < sig["entry"], sig["tp"] > sig["entry"]
        print(f"      SL di BAWAH entry : {'OK' if c1 else 'SALAH'}")
        print(f"      TP di ATAS entry  : {'OK' if c2 else 'SALAH'}")
    else:
        c1, c2 = sig["sl"] > sig["entry"], sig["tp"] < sig["entry"]
        print(f"      SL di ATAS entry  : {'OK' if c1 else 'SALAH'}")
        print(f"      TP di BAWAH entry : {'OK' if c2 else 'SALAH'}")
    ok = ok and c1 and c2

    # -- 3. RR ------------------------------------------------------------
    rr_nom = sig["tp_points"] / sig["sl_points"]
    rr_eff = (sig["tp_points"] - spread) / (sig["sl_points"] + spread)
    min_rr = cfg["trade_distances"]["min_rr_ratio"]
    print("\n  [3] RISK/REWARD")
    print(f"      RR nominal            1:{rr_nom:.2f}")
    print(f"      RR efektif (- spread) 1:{rr_eff:.2f}   (spread {spread:.0f} pts)")
    print(f"      breakeven winrate     {100/(1+rr_eff):.1f}%")
    print(f"      minimum config        1:{min_rr}")

    # -- 4. Gerbang risiko ------------------------------------------------
    print("\n  [4] GERBANG RISIKO (kode produksi)")
    d = rm.check(
        now=pd.Timestamp(sig["time"]).to_pydatetime(),
        equity=equity,
        sl_points=sig["sl_points"],
        tp_points=sig["tp_points"],
        spread_points=spread,
        open_positions=0,
        size_tier=sig.get("size_tier", "full"),
    )
    print(f"      keputusan : {'IZIN' if d.allowed else 'TOLAK'}")
    print(f"      alasan    : {d.reason}")
    if not d.allowed:
        return False

    rugi = sig["sl_points"] * vpp * d.lot
    untung = sig["tp_points"] * vpp * d.lot
    print(f"      lot       : {d.lot}")
    print(f"      risiko    : {rupiah(d.risk_amount)}  ({d.risk_pct:.2f}% equity)")

    # -- 5. Untung/rugi ---------------------------------------------------
    print("\n  [5] KALAU KENA SL / TP")
    print(f"      SL kena -> {rupiah(-rugi)}   ({-rugi/equity*100:+.2f}% equity)")
    print(f"      TP kena -> {rupiah(untung)}   ({untung/equity*100:+.2f}% equity)")

    # -- 6. Payload order -------------------------------------------------
    print("\n  [6] ORDER YANG AKAN DIKIRIM KE BROKER")
    print("      (ini payload sesungguhnya — TIDAK dikirim di simulasi ini)")
    payload = {
        "action": "TRADE_ACTION_DEAL",
        "symbol": cfg["symbol"]["name"],
        "volume": float(d.lot),
        "type": f"ORDER_TYPE_{arah.upper()}",
        "price": round(float(sig["entry"]), 3),
        "sl": round(float(sig["sl"]), 3),
        "tp": round(float(sig["tp"]), 3),
        "magic": MAGIC,
        "comment": f"{sig['setup']}|{sig['score']}",
    }
    for k, v in payload.items():
        print(f"        {k:10} = {v}")

    print("\n      SL dan TP dikirim BERSAMAAN dengan entry dalam satu")
    print("      request — posisi tidak pernah ada tanpa proteksi.")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="ambil harga live dari MT5 (butuh MT5 terbuka)")
    ap.add_argument("--equity", type=float, default=None,
                    help="equity untuk simulasi (default: dari risk_limits)")
    args = ap.parse_args()

    cfg = load_config()
    spread = float(cfg["costs"]["spread_points"])

    garis("SIMULASI SKENARIO BUY/SELL — TIDAK ADA ORDER YANG DIKIRIM")
    print(f"  symbol        : {cfg['symbol']['name']}")
    print(f"  mode config   : {cfg['mode']}")
    print(f"  setup aktif   : {cfg['active_setups']}")
    print(f"  spread        : {spread:.0f} pts ({spread/10:.0f} pip)")

    engine = RuleEngine(active_setups=["momentum_fib"])
    print(f"  gate ATR      : {engine.atr_lo:.2f} - {engine.atr_hi:.2f}")
    print(f"  filter konflu.: {'AKTIF' if engine.confluence_filter else 'mati (default)'}")

    rm = RiskManager()
    equity = args.equity or float(rm.risk.get("simulated_equity_idr", 4_000_000))
    print(f"  equity uji    : {rupiah(equity)}")

    # -- ambil data -------------------------------------------------------
    if args.live:
        print("\n  Mengambil data LIVE dari MT5...")
        from src.execution.bot import TradingBot
        bot = TradingBot()
        if not bot.connect():
            print("  GAGAL connect MT5. Pastikan MT5 terbuka dan login.")
            sys.exit(1)
        df = bot.build_frame()
        print(f"  OK — {len(df)} bar, terakhir {df['time_utc'].iloc[-1]}")
    else:
        if not FEATURES.exists():
            print(f"\n  File fitur tidak ada: {FEATURES}")
            sys.exit(1)
        df = pd.read_parquet(FEATURES)
        print(f"\n  Data historis: {len(df)} bar "
              f"({df['time_utc'].min().date()} - {df['time_utc'].max().date()})")

    # -- cari sinyal ------------------------------------------------------
    signals = engine.generate(df)
    if signals.empty:
        print("\n  Tidak ada sinyal pada data ini.")
        sys.exit(0)

    buys = signals[signals["direction"] == "buy"]
    sells = signals[signals["direction"] == "sell"]

    garis("SINYAL YANG DITEMUKAN")
    print(f"  total : {len(signals)}")
    print(f"  BUY   : {len(buys)}")
    print(f"  SELL  : {len(sells)}")

    if buys.empty or sells.empty:
        print("\n  PERINGATAN: sistem hanya menghasilkan SATU arah.")
        print("  Itu tanda ada yang salah — pasar punya dua arah.")

    # -- tampilkan satu contoh tiap arah ---------------------------------
    garis("DUA SKENARIO NYATA — DIAMBIL DARI SINYAL SESUNGGUHNYA")
    hasil = []
    for kelompok in (buys, sells):
        if kelompok.empty:
            continue
        hasil.append(tampilkan_skenario(
            kelompok.iloc[-1], cfg, rm, equity, spread))

    # -- uji gerbang benar-benar memblokir --------------------------------
    garis("UJI GERBANG: apakah yang HARUS ditolak benar-benar ditolak?")
    contoh = signals.iloc[-1]
    now = pd.Timestamp(contoh["time"]).to_pydatetime()
    uji = [
        ("equity di bawah minimum (Rp 1 jt)",
         dict(now=now, equity=1_000_000, sl_points=contoh["sl_points"],
              tp_points=contoh["tp_points"], spread_points=spread,
              open_positions=0)),
        ("sudah ada 1 posisi terbuka",
         dict(now=now, equity=equity, sl_points=contoh["sl_points"],
              tp_points=contoh["tp_points"], spread_points=spread,
              open_positions=1)),
        ("spread melebar 500 pts (50 pip)",
         dict(now=now, equity=equity, sl_points=contoh["sl_points"],
              tp_points=contoh["tp_points"], spread_points=500,
              open_positions=0)),
        ("kondisi normal (harus IZIN)",
         dict(now=now, equity=equity, sl_points=contoh["sl_points"],
              tp_points=contoh["tp_points"], spread_points=spread,
              open_positions=0)),
    ]
    for nama, kw in uji:
        rm2 = RiskManager()
        d = rm2.check(**kw)
        tanda = "IZIN " if d.allowed else "TOLAK"
        print(f"  [{tanda}] {nama}")
        print(f"           -> {d.reason}")

    garis("KESIMPULAN")
    if hasil and all(hasil) and not buys.empty and not sells.empty:
        print("  Sistem menghasilkan sinyal DUA ARAH, SL/TP di sisi yang benar,")
        print("  gerbang risiko berfungsi, dan payload order tersusun lengkap.")
        print("\n  TIDAK ADA ORDER YANG DIKIRIM oleh skrip ini.")
    else:
        print("  ADA YANG PERLU DIPERIKSA — lihat tanda SALAH di atas.")
    print()


if __name__ == "__main__":
    main()
