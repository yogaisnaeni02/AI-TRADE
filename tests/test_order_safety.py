"""
Tes pengaman order — jalur yang paling mahal kalau salah.

Dijalankan tanpa pytest dan tanpa MetaTrader5:

    python tests/test_order_safety.py

MetaTrader5 tidak terpasang di mesin pengembangan, jadi modul mt5 dipalsukan
SEBELUM order_manager diimpor. Yang diuji adalah logikanya, bukan
integrasinya dengan terminal.

Fokus pada tiga perbaikan 10 Sep 2026:
  1. SL gagal dipasang -> posisi ditutup darurat, bukan dilaporkan "OK"
  2. r_multiple terisi dari lot + jarak SL
  3. positions_get() kosong diperlakukan sebagai kegagalan
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# -- palsukan MetaTrader5 sebelum modul apa pun mengimpornya -------------

RETCODE_DONE = 10009

fake = types.ModuleType("MetaTrader5")
fake.TRADE_RETCODE_DONE = RETCODE_DONE
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
fake.last_error = lambda: (0, "ok")
sys.modules["MetaTrader5"] = fake

from src.execution import order_manager as OM  # noqa: E402


class Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeBroker:
    """
    Broker palsu yang bisa disuruh gagal dengan cara tertentu.

    sl_attach_mode:
      "ok"       - SL langsung terpasang saat order
      "missing"  - SL kosong, tapi modify berhasil
      "reject"   - SL kosong dan modify SELALU ditolak
      "novisi"   - positions_get() selalu kosong
    """

    def __init__(self, sl_attach_mode="ok"):
        self.mode = sl_attach_mode
        self.positions: list[Obj] = []
        self.closed: list[int] = []
        self.modify_calls = 0
        self.next_ticket = 5001

    # -- API yang dipakai order_manager --
    def symbol_info(self, sym):
        return Obj(digits=3, point=0.001, filling_mode=2, trade_stops_level=0)

    def symbol_info_tick(self, sym):
        return Obj(ask=4400.0, bid=4399.740, time=1_760_000_000)

    def positions_get(self, symbol=None):
        if self.mode == "novisi":
            return []
        return list(self.positions)

    def order_send(self, req):
        if req["action"] == fake.TRADE_ACTION_DEAL:
            if req["volume"] == 0:  # penutupan
                return Obj(retcode=RETCODE_DONE, order=0, price=4400.0, volume=0)
            t = self.next_ticket
            self.next_ticket += 1
            sl = 0.0 if self.mode in ("missing", "reject", "novisi") else req["sl"]
            self.positions.append(
                Obj(ticket=t, magic=OM.MAGIC, type=fake.POSITION_TYPE_BUY,
                    volume=req["volume"], price_open=req["price"], sl=sl, tp=req["tp"])
            )
            return Obj(retcode=RETCODE_DONE, order=t, price=req["price"],
                       volume=req["volume"])

        if req["action"] == fake.TRADE_ACTION_SLTP:
            self.modify_calls += 1
            if self.mode == "reject":
                return Obj(retcode=99, order=0, price=0, volume=0)
            for p in self.positions:
                if p.ticket == req["position"]:
                    p.sl = req["sl"]
            return Obj(retcode=RETCODE_DONE, order=0, price=0, volume=0)

        return Obj(retcode=99, order=0, price=0, volume=0)


def install(broker: FakeBroker) -> None:
    """Sambungkan broker palsu ke modul mt5 tiruan."""
    fake.symbol_info = broker.symbol_info
    fake.symbol_info_tick = broker.symbol_info_tick
    fake.positions_get = broker.positions_get
    fake.order_send = broker.order_send

    # close_position mengirim DEAL berlawanan; catat tiket yang ditutup.
    orig = broker.order_send

    def spy(req):
        if req["action"] == fake.TRADE_ACTION_DEAL and "position" in req:
            broker.closed.append(req["position"])
            broker.positions = [p for p in broker.positions
                                if p.ticket != req["position"]]
            return Obj(retcode=RETCODE_DONE, order=req["position"],
                       price=4400.0, volume=req.get("volume", 0))
        return orig(req)

    fake.order_send = spy


def make_om(broker: FakeBroker):
    install(broker)
    gw = Obj(symbol="XAUUSDm", config={"symbol": {"point": 0.001}})
    return OM.OrderManager(gw)


# -- tes ----------------------------------------------------------------


def test_sl_terpasang_normal():
    b = FakeBroker("ok")
    r = make_om(b).open_position("buy", 0.01, sl=4396.0, tp=4411.12)
    assert r.success, r.comment
    assert b.positions[0].sl == 4396.0
    assert not b.closed, "posisi sehat tidak boleh ditutup"


def test_sl_kosong_dipasang_ulang():
    b = FakeBroker("missing")
    r = make_om(b).open_position("buy", 0.01, sl=4396.0, tp=4411.12)
    assert r.success, r.comment
    assert b.modify_calls >= 1, "harus mencoba memasang SL"
    assert b.positions[0].sl == 4396.0
    assert not b.closed


def test_sl_ditolak_posisi_ditutup_darurat():
    """Regresi: dulu modify_position() dipanggil lalu hasilnya DIBUANG,
    sehingga posisi tanpa SL dilaporkan sebagai 'berhasil'."""
    b = FakeBroker("reject")
    r = make_om(b).open_position("buy", 0.01, sl=4396.0, tp=4411.12)
    assert not r.success, "posisi tanpa SL TIDAK boleh dilaporkan berhasil"
    assert "SL gagal" in r.comment, r.comment
    assert b.closed, "posisi tanpa SL harus ditutup darurat"
    assert b.modify_calls >= 3, f"harus dicoba beberapa kali, baru {b.modify_calls}"


def test_posisi_tak_terbaca_dianggap_gagal():
    """positions_get() kosong bukan berarti aman - kita tidak tahu SL-nya."""
    b = FakeBroker("novisi")
    r = make_om(b).open_position("buy", 0.01, sl=4396.0, tp=4411.12)
    assert not r.success, r.comment
    assert "tidak terbaca" in r.comment or "SL gagal" in r.comment, r.comment


def test_sl_arah_salah_ditolak_sebelum_kirim():
    b = FakeBroker("ok")
    om = make_om(b)
    r = om.open_position("buy", 0.01, sl=4405.0, tp=4411.12)   # SL di ATAS harga
    assert not r.success
    assert "SL buy" in r.comment, r.comment
    assert not b.positions, "order tidak boleh terkirim sama sekali"


def test_sl_tidak_boleh_dilebarkan():
    b = FakeBroker("ok")
    om = make_om(b)
    om.open_position("buy", 0.01, sl=4396.0, tp=4411.12)
    t = b.positions[0].ticket
    assert om.modify_position(t, 4398.0), "menyempitkan SL harus boleh"
    assert not om.modify_position(t, 4390.0), "MELEBARKAN SL harus ditolak"
    assert b.positions[0].sl == 4398.0


# -- r_multiple di journal ----------------------------------------------


def test_risk_idr_dari_deal():
    from src.monitoring.journal import _risk_idr_from_deal

    cfg = {
        "symbol": {"point": 0.001, "value_per_point_idr": 1748.36},
        "trade_distances": {"sl_typical_points": 4000},
    }
    entry = Obj(price=4400.0, volume=0.01)

    # SL 4 USD di bawah entry = 4000 points
    risk = _risk_idr_from_deal(entry, 4396.0, cfg)
    assert abs(risk - 4000 * 1748.36 * 0.01) < 1, risk

    # SL tidak diketahui -> pakai sl_typical_points
    fallback = _risk_idr_from_deal(entry, 0.0, cfg)
    assert abs(fallback - 4000 * 1748.36 * 0.01) < 1, fallback


# -- runner --------------------------------------------------------------


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = []
    for fn in tests:
        try:
            fn()
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
