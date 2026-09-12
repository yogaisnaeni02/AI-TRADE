"""
Order manager — mengirim dan mengelola order di MT5.

Prinsip keselamatan:
  - SL dan TP dikirim BERSAMAAN dengan entry, bukan sesudahnya. Order tanpa
    SL, meski sedetik, adalah eksposur tak terbatas.
  - SL tidak pernah dilebarkan. Hanya boleh bergerak searah profit.
  - Setiap order diverifikasi setelah dikirim; tidak ada asumsi berhasil.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal, Optional

import MetaTrader5 as mt5

MAGIC = 20260909  # magic bawaan (varian "baseline") - lihat config/variants.yaml


@dataclass
class OrderResult:
    success: bool
    ticket: Optional[int]
    price: Optional[float]
    lot: float
    comment: str
    retcode: Optional[int] = None


class OrderManager:
    def __init__(self, gateway, deviation_points: int = 50, magic: int = MAGIC):
        self.gw = gateway
        self.symbol = gateway.symbol
        self.deviation = deviation_points
        self.point = gateway.config["symbol"]["point"]
        # Magic per VARIAN (config/variants.yaml), bukan konstanta tunggal.
        # Memungkinkan beberapa varian berjalan berdampingan di akun yang
        # sama tanpa posisi/journal-nya bercampur. Default = MAGIC lama
        # supaya kode yang belum memberi argumen ini tetap berperilaku sama.
        self.magic = magic

    # -- helper ----------------------------------------------------------

    def _filling_mode(self) -> int:
        """Pilih filling mode yang didukung broker."""
        info = mt5.symbol_info(self.symbol)
        if info is None:
            return mt5.ORDER_FILLING_IOC
        # filling_mode adalah bitmask: 1=FOK, 2=IOC
        if info.filling_mode & 2:
            return mt5.ORDER_FILLING_IOC
        if info.filling_mode & 1:
            return mt5.ORDER_FILLING_FOK
        return mt5.ORDER_FILLING_RETURN

    def _normalize_price(self, price: float) -> float:
        digits = mt5.symbol_info(self.symbol).digits
        return round(price, digits)

    def _respects_stops_level(self, price: float, sl: float, tp: float) -> bool:
        """Broker menolak SL/TP yang terlalu dekat dengan harga."""
        info = mt5.symbol_info(self.symbol)
        min_dist = info.trade_stops_level * self.point
        if min_dist <= 0:
            return True
        return abs(price - sl) >= min_dist and abs(price - tp) >= min_dist

    # -- eksekusi --------------------------------------------------------

    def open_position(
        self,
        direction: Literal["buy", "sell"],
        lot: float,
        sl: float,
        tp: float,
        comment: str = "",
    ) -> OrderResult:
        """Buka posisi market dengan SL/TP menyatu dalam satu request."""
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return OrderResult(False, None, None, lot, "tick tidak tersedia")

        if direction == "buy":
            order_type, price = mt5.ORDER_TYPE_BUY, tick.ask
        else:
            order_type, price = mt5.ORDER_TYPE_SELL, tick.bid

        sl = self._normalize_price(sl)
        tp = self._normalize_price(tp)

        # Verifikasi arah SL benar — pengaman terhadap bug pemanggil
        if direction == "buy" and sl >= price:
            return OrderResult(False, None, None, lot, "SL buy harus di bawah harga")
        if direction == "sell" and sl <= price:
            return OrderResult(False, None, None, lot, "SL sell harus di atas harga")

        if not self._respects_stops_level(price, sl, tp):
            return OrderResult(False, None, None, lot, "SL/TP terlalu dekat (stops_level)")

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": float(lot),
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": comment[:31],  # MT5 membatasi panjang komentar
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_mode(),
        }

        result = mt5.order_send(request)
        if result is None:
            return OrderResult(False, None, None, lot, f"order_send None: {mt5.last_error()}")

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return OrderResult(
                False, None, None, lot,
                f"ditolak: {result.retcode} {result.comment}", result.retcode,
            )

        # Verifikasi SL benar-benar terpasang, dan TUTUP DARURAT bila gagal.
        #
        # DIPERBAIKI 10 Sep 2026. Versi sebelumnya memanggil
        # modify_position() lalu MEMBUANG nilai baliknya, sehingga posisi
        # tanpa SL tetap dilaporkan "berhasil". Pada XAUUSD dengan leverage
        # 2000, satu posisi tanpa SL bisa menghabiskan akun dalam satu
        # pergerakan - kerugian kecil yang disengaja jauh lebih murah.
        #
        # positions_get() kosong juga diperlakukan sebagai KEGAGALAN, bukan
        # sukses diam: kalau posisi tidak bisa diverifikasi, kita tidak tahu
        # apakah SL-nya ada.
        ok, why = self._ensure_stop_attached(result.order, sl, tp)
        if not ok:
            closed = self.close_position(result.order)
            return OrderResult(
                False, result.order, result.price, result.volume,
                f"SL gagal dipasang ({why}) - posisi "
                f"{'DITUTUP darurat' if closed.success else 'GAGAL DITUTUP, INTERVENSI MANUAL'}",
                result.retcode,
            )

        return OrderResult(
            True, result.order, result.price, result.volume, "berhasil", result.retcode
        )

    def _ensure_stop_attached(
        self, ticket: int, sl: float, tp: Optional[float], attempts: int = 3
    ) -> tuple[bool, str]:
        """
        Pastikan posisi punya SL. Coba pasang ulang beberapa kali.

        Mengembalikan (True, "") bila SL terpasang, atau (False, alasan)
        bila setelah semua percobaan SL masih kosong / posisi tak terbaca.
        """
        last = "tidak diketahui"

        for i in range(attempts):
            if i:
                time.sleep(0.5)

            positions = mt5.positions_get(symbol=self.symbol) or []
            pos = next(
                (p for p in positions if p.ticket == ticket or p.magic == self.magic),
                None,
            )
            if pos is None:
                last = "posisi tidak terbaca dari broker"
                continue

            if pos.sl != 0.0:
                return True, ""

            last = "SL masih 0.0 setelah order"
            if not self.modify_position(pos.ticket, sl, tp):
                last = "modify_position ditolak broker"

        return False, last

    def modify_position(self, ticket: int, sl: float, tp: Optional[float] = None) -> bool:
        """Ubah SL/TP. Menolak perubahan yang MELEBARKAN SL."""
        pos = None
        for p in mt5.positions_get(symbol=self.symbol) or []:
            if p.ticket == ticket:
                pos = p
                break
        if pos is None:
            return False

        sl = self._normalize_price(sl)

        # Pengaman: SL hanya boleh bergerak searah profit
        if pos.sl != 0.0:
            if pos.type == mt5.POSITION_TYPE_BUY and sl < pos.sl:
                return False
            if pos.type == mt5.POSITION_TYPE_SELL and sl > pos.sl:
                return False

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": self.symbol,
            "position": ticket,
            "sl": sl,
            "tp": self._normalize_price(tp) if tp is not None else pos.tp,
        }
        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE

    def close_position(self, ticket: int, volume: Optional[float] = None) -> OrderResult:
        """Tutup posisi, seluruhnya atau sebagian."""
        pos = None
        for p in mt5.positions_get(symbol=self.symbol) or []:
            if p.ticket == ticket:
                pos = p
                break
        if pos is None:
            return OrderResult(False, None, None, 0, "posisi tidak ditemukan")

        tick = mt5.symbol_info_tick(self.symbol)
        vol = float(volume) if volume else pos.volume

        if pos.type == mt5.POSITION_TYPE_BUY:
            order_type, price = mt5.ORDER_TYPE_SELL, tick.bid
        else:
            order_type, price = mt5.ORDER_TYPE_BUY, tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": vol,
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": "close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_mode(),
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            code = result.retcode if result else None
            return OrderResult(False, None, None, vol, "gagal menutup posisi", code)

        return OrderResult(True, ticket, result.price, vol, "ditutup", result.retcode)

    # -- query -----------------------------------------------------------

    def get_positions(self) -> list:
        """Hanya posisi milik sistem ini (ditandai magic number)."""
        return [p for p in (mt5.positions_get(symbol=self.symbol) or []) if p.magic == self.magic]

    def close_all(self) -> list[OrderResult]:
        return [self.close_position(p.ticket) for p in self.get_positions()]
