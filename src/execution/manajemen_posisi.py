"""
Aturan manajemen posisi terbuka — SATU sumber untuk bot live dan simulasi.

KENAPA DIPISAH DARI bot.py
--------------------------
Aturan break-even, trailing, auto-close, dan timeout dulu ditulis langsung
di TradingBot.manage_positions(), yang terikat ke MetaTrader5. Engine
backtest menulis versinya sendiri, dan versi itu BERBEDA:
  - trailing diaktifkan langsung di pemicu, tanpa geser SL ke titik impas
  - pemicu dicek di close bar, bukan tiap siklus polling
  - auto-close tidak dimodelkan sama sekali

Akibatnya varian autoclose terlihat identik dengan induknya di backtest,
padahal di live perilakunya lain (simulasi 30 hari 16 Agu-15 Sep 2026:
autoclose -14,5R vs induknya -0,1R pada entry yang identik).

Modul ini murni - tanpa MT5, tanpa I/O - sehingga bot dan
backtest/simulasi_live.py memakai keputusan yang persis sama, dan aturannya
bisa diuji tanpa terminal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd

from ..strategy.setups import hitung_skor100

MODE_BAR_AUTOCLOSE = ("berjalan", "tutup")


@dataclass(frozen=True)
class ParamPosisi:
    breakeven_at_r: float
    trail_atr_mult: float
    max_bars_hold: int
    spread_harga: float
    autoclose_score_drop: int = 0
    # Bar yang dipakai menilai skor auto-close:
    #   "berjalan" : bar M5 yang belum tutup, dinilai tiap siklus (perilaku
    #                lama). Komponen candle (10 poin) dan momentum ikut
    #                berkedip selama bar terbentuk.
    #   "tutup"    : bar M5 terakhir yang sudah tutup - sama dengan cara
    #                sinyal entry dinilai.
    autoclose_bar: str = "berjalan"

    @classmethod
    def dari_config(
        cls,
        cfg: dict,
        breakeven_at_r: Optional[float] = None,
        trail_atr_mult: Optional[float] = None,
    ) -> "ParamPosisi":
        pm = cfg.get("position_management", {}) or {}
        mode = str(pm.get("autoclose_bar", "berjalan")).lower()
        if mode not in MODE_BAR_AUTOCLOSE:
            raise ValueError(
                f"position_management.autoclose_bar '{mode}' tidak dikenal "
                f"(pilihan: {', '.join(MODE_BAR_AUTOCLOSE)})"
            )
        return cls(
            # Default 1,5 / 2,5 sama dengan fallback lama di bot.py.
            breakeven_at_r=float(
                breakeven_at_r if breakeven_at_r is not None else pm.get("breakeven_at_r", 1.5)
            ),
            trail_atr_mult=float(
                trail_atr_mult if trail_atr_mult is not None else pm.get("trail_atr_mult", 2.5)
            ),
            max_bars_hold=int(pm.get("max_bars_hold", 48)),
            spread_harga=float(cfg["costs"]["spread_points"]) * float(cfg["symbol"]["point"]),
            autoclose_score_drop=int(pm.get("autoclose_score_drop", 0) or 0),
            autoclose_bar=mode,
        )


@dataclass
class Keputusan:
    """Hasil satu siklus untuk satu posisi. Pemanggil yang menerapkannya."""

    sl_baru: Optional[float] = None
    be_baru: bool = False           # SL baru saja digeser ke titik impas
    tutup: Optional[str] = None     # None | "autoclose" | "timeout"
    skor_awal: int = 0
    skor_kini: Optional[int] = None
    umur_bar: int = 0


def _nilai(row: Any, kolom: str) -> Any:
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(kolom)
    return getattr(row, kolom, None)


def putuskan(
    info: dict,
    is_buy: bool,
    sl_sekarang: float,
    bar_berjalan: Any,
    bar_tutup: Any,
    p: ParamPosisi,
    harga_ekstrem: Optional[float] = None,
) -> Keputusan:
    """
    Keputusan untuk SATU posisi pada satu siklus. `info` tidak diubah.

    info          : {"entry", "sl_dist", "be_done", "bar_entry", "score100"}
                    bar_entry = waktu bar SINYAL (dasar timeout)
    bar_berjalan  : bar M5 yang sedang terbentuk (df.iloc[-1] di bot)
    bar_tutup     : bar M5 terakhir yang sudah tutup (df.iloc[-2])
    harga_ekstrem : harga terbaik sejak siklus sebelumnya, untuk pemicu BE
                    dan trailing. Bot mengecek tiap ~3 detik sehingga cukup
                    memakai harga terkini (None). Simulasi per menit
                    mengoper high/low menit itu untuk mendekati polling bot.
    """
    k = Keputusan()

    atr = _nilai(bar_berjalan, "atr")
    if atr is None or pd.isna(atr) or atr <= 0:
        # Sama dengan perilaku lama: tanpa ATR sahih tidak ada keputusan apa pun.
        return k

    entry = float(info["entry"])
    harga = float(_nilai(bar_berjalan, "close"))
    acuan = harga if harga_ekstrem is None else float(harga_ekstrem)
    profit = (acuan - entry) if is_buy else (entry - acuan)

    # -- break-even lalu trailing --------------------------------------------
    if not info.get("be_done") and profit >= float(info["sl_dist"]) * p.breakeven_at_r:
        k.sl_baru = entry + p.spread_harga if is_buy else entry - p.spread_harga
        k.be_baru = True
    elif info.get("be_done"):
        trail = acuan - atr * p.trail_atr_mult if is_buy else acuan + atr * p.trail_atr_mult
        if (is_buy and trail > sl_sekarang) or (not is_buy and trail < sl_sekarang):
            k.sl_baru = trail

    # -- auto-close saat keyakinan menurun, HANYA saat profit ----------------
    skor_awal = int(info.get("score100") or 0)
    if p.autoclose_score_drop > 0 and skor_awal > 0:
        if p.autoclose_bar == "tutup":
            row = bar_tutup
            # Bar tutup yang masih bar sinyal (atau lebih tua) belum membawa
            # informasi baru sejak entry.
            t_row, t_sinyal = _nilai(row, "time_utc"), info.get("bar_entry")
            if t_row is not None and t_sinyal is not None and pd.Timestamp(t_row) <= pd.Timestamp(t_sinyal):
                row = None
            harga_ac = None if row is None else float(_nilai(row, "close"))
        else:
            row, harga_ac = bar_berjalan, harga

        if row is not None and harga_ac is not None:
            profit_ac = (harga_ac - entry) if is_buy else (entry - harga_ac)
            if profit_ac > 0:
                kini = hitung_skor100(row, "buy" if is_buy else "sell")
                k.skor_awal, k.skor_kini = skor_awal, kini
                if skor_awal - kini >= p.autoclose_score_drop:
                    k.tutup = "autoclose"

    # -- timeout -------------------------------------------------------------
    # Umur dihitung dari SELISIH WAKTU bar, bukan jumlah panggilan, sehingga
    # kebal terhadap interval polling.
    t_now, t_entry = _nilai(bar_berjalan, "time_utc"), info.get("bar_entry")
    if t_now is not None and t_entry is not None:
        k.umur_bar = int((pd.Timestamp(t_now) - pd.Timestamp(t_entry)).total_seconds() // 300)
        if k.tutup is None and k.umur_bar > p.max_bars_hold:
            k.tutup = "timeout"

    return k


def skor_awal_dari_data(df: pd.DataFrame, waktu_entry_utc: pd.Timestamp, arah: str) -> tuple[int, Optional[pd.Timestamp]]:
    """
    Skor100 bar SINYAL untuk posisi yang direkonstruksi setelah restart.

    Bot entry di siklus pertama setelah bar sinyal tutup, jadi bar sinyal =
    bar sebelum bar tempat entry terjadi. Mengembalikan (0, None) bila bar
    itu sudah tidak ada di data - auto-close lalu tidak berlaku untuk posisi
    tersebut, sama seperti sebelumnya, tetapi sekarang itu pengecualian,
    bukan aturan.
    """
    bar_sinyal = pd.Timestamp(waktu_entry_utc).floor("5min") - pd.Timedelta(minutes=5)
    cocok = df.loc[df["time_utc"] == bar_sinyal]
    if cocok.empty:
        return 0, None
    return int(hitung_skor100(cocok.iloc[-1], arah)), bar_sinyal
