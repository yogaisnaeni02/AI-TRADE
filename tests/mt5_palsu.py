"""
MetaTrader5 palsu BERSAMA untuk seluruh file tes.

KENAPA HARUS SATU OBJEK
-----------------------
Modul produksi menulis `import MetaTrader5 as mt5` di tingkat modul, jadi
mereka mengikat objek yang ada di sys.modules SAAT DIIMPOR PERTAMA KALI.

`python tests/test_x.py` mengimpor satu file tes saja, sehingga tiap file
bisa memasang objek palsunya sendiri tanpa masalah. `pytest tests/`
mengimpor SEMUANYA dalam satu proses: file tes yang diimpor belakangan akan
menambal objek palsu yang tidak lagi dipakai modul produksi, dan tesnya
gagal walau logikanya benar. Itu terjadi saat tests/test_bot_manage.py
ditambahkan - 7 tes di tests/test_order_safety.py langsung gagal.

`pasang()` mengembalikan objek palsu yang SAMA untuk semua pemanggil, dan
hanya menimpa sys.modules bila yang terpasang belum objek palsu kita -
paket MetaTrader5 sungguhan di PC bot tidak pernah ditambal.
"""

from __future__ import annotations

import sys
import time
import types

PENANDA = "_palsu_ai_trade"


def _tick_segar(symbol=None):
    """Tick 'baru saja' supaya deteksi offset server menghasilkan 0."""
    return types.SimpleNamespace(time=int(time.time()), bid=4400.0, ask=4400.26)


def pasang() -> types.ModuleType:
    """Pasang (atau ambil kembali) modul MetaTrader5 palsu bersama."""
    lama = sys.modules.get("MetaTrader5")
    if lama is not None and getattr(lama, PENANDA, False):
        return lama

    fake = types.ModuleType("MetaTrader5")
    setattr(fake, PENANDA, True)

    fake.TRADE_RETCODE_DONE = 10009
    fake.TRADE_ACTION_DEAL = 1
    fake.TRADE_ACTION_SLTP = 2
    fake.ORDER_TYPE_BUY = 0
    fake.ORDER_TYPE_SELL = 1
    fake.POSITION_TYPE_BUY = 0
    fake.POSITION_TYPE_SELL = 1
    fake.ORDER_FILLING_IOC = 1
    fake.ORDER_FILLING_FOK = 2
    fake.ORDER_FILLING_RETURN = 3
    fake.ORDER_TIME_GTC = 0
    fake.DEAL_TYPE_BUY = 0
    for i, nama in enumerate(("TIMEFRAME_M1", "TIMEFRAME_M5", "TIMEFRAME_M15",
                              "TIMEFRAME_H1", "TIMEFRAME_H4"), start=1):
        setattr(fake, nama, i)

    fake.last_error = lambda: (0, "ok")
    fake.symbol_info_tick = _tick_segar
    fake.history_deals_get = lambda a, b: None

    sys.modules["MetaTrader5"] = fake
    return fake
