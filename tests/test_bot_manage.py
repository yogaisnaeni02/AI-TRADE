"""
Tes kabel TradingBot tanpa MetaTrader5.

Yang dijaga:
  - manage_positions() menerapkan keputusan manajemen_posisi (BE, auto-close)
  - posisi yang direkonstruksi setelah restart membawa skor awal
  - heartbeat membaca ambang fib varian, bukan angka yang ditulis mati
  - kegagalan membaca riwayat / menulis journal dilaporkan, rem tidak direset

    python tests/test_bot_manage.py
"""

from __future__ import annotations

import sys
import tempfile
import time
import types
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# -- palsukan MetaTrader5 sebelum modul apa pun mengimpornya -------------

fake = types.ModuleType("MetaTrader5")
for i, nama in enumerate(("TIMEFRAME_M1", "TIMEFRAME_M5", "TIMEFRAME_M15",
                          "TIMEFRAME_H1", "TIMEFRAME_H4"), start=1):
    setattr(fake, nama, i)
fake.POSITION_TYPE_BUY, fake.POSITION_TYPE_SELL = 0, 1
fake.DEAL_TYPE_BUY = 0
fake.TRADE_RETCODE_DONE = 10009
fake.last_error = lambda: (0, "ok")
fake.symbol_info_tick = lambda symbol: types.SimpleNamespace(
    time=int(time.time()), bid=4400.0, ask=4400.26)
fake.history_deals_get = lambda a, b: None
sys.modules["MetaTrader5"] = fake

from src.monitoring import notifier  # noqa: E402

notifier.send = lambda *a, **k: False  # tes TIDAK boleh mengirim Telegram sungguhan

from src.execution import bot as B  # noqa: E402
from src.strategy.setups import hitung_skor100  # noqa: E402

T = pd.Timestamp("2026-09-10 10:00")
M5 = pd.Timedelta(minutes=5)


class Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeOrders:
    def __init__(self, positions):
        self.positions = list(positions)
        self.modified: list[tuple[int, float]] = []
        self.closed: list[int] = []

    def get_positions(self):
        return list(self.positions)

    def modify_position(self, ticket, sl, tp=None):
        self.modified.append((ticket, sl))
        return True

    def close_position(self, ticket, volume=None):
        self.closed.append(ticket)
        self.positions = [p for p in self.positions if p.ticket != ticket]
        return Obj(success=True, price=4401.0)


def baris(t, close, tinggi=True, **kw) -> dict:
    """Bar M5 dengan skor100 tinggi (~100) atau rendah (~18) untuk buy."""
    d = dict(
        time_utc=t, close=close, open=close - 1 if tinggi else close + 1, atr=4.0,
        mom_24=1.5 if tinggi else 0.0, mom_24_q85=1.0,
        trend_htf="uptrend" if tinggi else "ranging",
        adx=30.0 if tinggi else 10.0, fib_position=0.9 if tinggi else 0.6,
        atr_percentile=0.5 if tinggi else 0.9, stoch_k=80.0 if tinggi else 50.0,
        session="london_ny", is_trading_session=True,
    )
    d.update(kw)
    return d


def posisi(ticket, harga=4400.0, sl=4395.74, tipe=0, waktu=None):
    return Obj(ticket=ticket, type=tipe, price_open=harga, sl=sl,
               time=waktu if waktu is not None else int(T.timestamp()))


def buat_bot(varian: str, tmp: Path):
    bot = B.TradingBot(variant=varian)
    bot.log_path = tmp / "bot.log"
    bot.catatan = []
    bot.log = bot.catatan.append
    return bot


# -- manajemen posisi ----------------------------------------------------


def test_be_diterapkan_lewat_keputusan_bersama(tmp: Path):
    bot = buat_bot("dua_arah", tmp)
    bot.orders = FakeOrders([posisi(1)])
    bot._entry_info[1] = {"entry": 4400.0, "sl_dist": 4.26, "be_done": False,
                          "bar_entry": T, "score100": 90}
    df = pd.DataFrame([baris(T, 4400), baris(T + M5, 4405), baris(T + 2 * M5, 4411)])
    bot.manage_positions(df)
    assert bot.orders.modified and abs(bot.orders.modified[0][1] - 4400.26) < 1e-9, bot.orders.modified
    assert bot._entry_info[1]["be_done"]
    assert not bot.orders.closed


def test_autoclose_bar_berjalan_menutup(tmp: Path):
    bot = buat_bot("autoclose", tmp)
    bot.param_posisi = replace(bot.param_posisi, autoclose_bar="berjalan")
    bot.orders = FakeOrders([posisi(2)])
    bot._entry_info[2] = {"entry": 4400.0, "sl_dist": 4.26, "be_done": False,
                          "bar_entry": T, "score100": 95}
    df = pd.DataFrame([baris(T, 4400), baris(T + M5, 4401), baris(T + 2 * M5, 4402, tinggi=False)])
    bot.manage_positions(df)
    assert bot.orders.closed == [2], bot.orders.closed
    assert any("AUTOCLOSE" in m for m in bot.catatan), bot.catatan
    assert 2 not in bot._entry_info


def test_autoclose_bar_tutup_mengabaikan_bar_berjalan(tmp: Path):
    bot = buat_bot("autoclose", tmp)
    bot.param_posisi = replace(bot.param_posisi, autoclose_bar="tutup")
    bot.orders = FakeOrders([posisi(3)])
    bot._entry_info[3] = {"entry": 4400.0, "sl_dist": 4.26, "be_done": False,
                          "bar_entry": T, "score100": 95}
    df = pd.DataFrame([baris(T, 4400), baris(T + M5, 4401), baris(T + 2 * M5, 4402, tinggi=False)])
    bot.manage_positions(df)
    assert not bot.orders.closed, "bar tutup masih kuat - tidak boleh ditutup"


def test_rekonstruksi_posisi_membawa_skor_awal(tmp: Path):
    """Regresi: posisi yang melewati restart dulu kehilangan score100,
    sehingga auto-close diam-diam mati untuknya."""
    bot = buat_bot("autoclose", tmp)
    waktu_entry = int((T + M5 + pd.Timedelta(seconds=7)).timestamp())
    bot.orders = FakeOrders([posisi(4, waktu=waktu_entry)])
    df = pd.DataFrame([baris(T, 4400), baris(T + M5, 4399), baris(T + 2 * M5, 4399.5)])
    bot.manage_positions(df)
    info = bot._entry_info[4]
    assert info["bar_entry"] == T, info
    assert info["score100"] == hitung_skor100(df.iloc[0], "buy") > 0, info


def test_rekonstruksi_mengenali_sl_sudah_impas(tmp: Path):
    bot = buat_bot("dua_arah", tmp)
    bot.orders = FakeOrders([posisi(5, sl=4400.26)])
    df = pd.DataFrame([baris(T, 4400), baris(T + M5, 4401), baris(T + 2 * M5, 4402)])
    bot.manage_positions(df)
    assert bot._entry_info[5]["be_done"], bot._entry_info[5]


# -- heartbeat -----------------------------------------------------------


def test_heartbeat_membaca_ambang_fib_varian(tmp: Path):
    """Regresi: fib 0,75/0,25 dan momentum sisi buy dulu ditulis mati."""
    df = pd.DataFrame([baris(T, 4300, trend_htf="downtrend", fib_position=0.28, mom_24=-2.0)])

    longgar = buat_bot("autoclose_agresif", tmp)   # sell bila fib < 0,30
    longgar._log_heartbeat(df)
    assert "semua syarat OK" in longgar.catatan[-1], longgar.catatan

    ketat = buat_bot("dua_arah", tmp)              # sell bila fib < 0,25
    ketat._log_heartbeat(df)
    assert "fib 0.28" in ketat.catatan[-1], ketat.catatan


# -- rem risiko & journal ------------------------------------------------


def test_riwayat_mt5_gagal_dilaporkan_sekali_dan_rem_bertahan(tmp: Path):
    bot = buat_bot("dua_arah", tmp)
    bot.risk.state.consecutive_losses = 3
    asli = B.posisi_tertutup
    try:
        B.posisi_tertutup = lambda **kw: None
        bot._sinkron_rem_dan_journal()
        bot._sinkron_rem_dan_journal()
    finally:
        B.posisi_tertutup = asli
    laporan = [m for m in bot.catatan if "riwayat deal MT5 gagal" in m]
    assert len(laporan) == 1, bot.catatan
    assert bot.risk.state.consecutive_losses == 3, "rem tidak boleh direset saat riwayat tak terbaca"


def test_journal_gagal_ditulis_rem_tetap_dari_riwayat(tmp: Path):
    """Regresi: dulu rem hanya diperbarui SETELAH CSV berhasil ditulis."""
    bot = buat_bot("dua_arah", tmp)
    sekarang = datetime.now().replace(microsecond=0)
    riwayat = [{"ticket": 9, "entry_time": (sekarang - timedelta(minutes=30)).isoformat(),
                "exit_time": sekarang.isoformat(), "net_idr": -70_000.0, "magic": bot._magic}]

    def gagal(**kw):
        raise PermissionError("trades.csv sedang dibuka program lain")

    asli_riwayat, asli_sync = B.posisi_tertutup, B.sync_closed_trades
    try:
        B.posisi_tertutup = lambda **kw: riwayat
        B.sync_closed_trades = gagal
        bot._sinkron_rem_dan_journal()
    finally:
        B.posisi_tertutup, B.sync_closed_trades = asli_riwayat, asli_sync

    assert bot.risk.state.day_trades == 1, bot.risk.state
    assert bot.risk.state.consecutive_losses == 1, bot.risk.state
    assert any("tulis logs/trades.csv gagal" in m for m in bot.catatan), bot.catatan


# -- runner --------------------------------------------------------------


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = []
    for fn in tests:
        with tempfile.TemporaryDirectory() as d:
            try:
                fn(Path(d))
            except AssertionError as e:
                failed.append((fn.__name__, f"assert gagal: {e}"))
            except Exception as e:  # noqa: BLE001
                failed.append((fn.__name__, f"{type(e).__name__}: {e}"))
            else:
                print(f"  ok    {fn.__name__}")
    for name, why in failed:
        print(f"  GAGAL {name} -> {why}")
    print(f"\n{len(tests) - len(failed)}/{len(tests)} lolos")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
