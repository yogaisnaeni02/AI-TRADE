"""
Backtester event-driven dengan biaya realistis.

Prinsip: lebih baik hasil pesimis yang jujur daripada optimis yang menyesatkan.
Selisih antara backtest dan live hampir selalu berasal dari biaya yang tidak
dimodelkan.

Yang dimodelkan:
  - Spread (dibayar penuh saat entry)
  - Slippage entry dan slippage SL (SL biasanya kena lebih buruk)
  - Eksekusi di bar BERIKUTNYA (sinyal di close bar t -> entry di open t+1)
  - Ambiguitas SL/TP dalam satu bar

Ambiguitas SL/TP: bila dalam satu bar M5 harga menyentuh SL dan TP, data M5
tidak menyimpan urutannya. Dua mode:
  "pessimistic" — anggap SL duluan (aman, dipakai untuk periode tanpa M1)
  "m1"          — buka data M1 untuk melihat urutan sebenarnya
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal, Optional

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "settings.yaml"
RISK_PATH = ROOT / "config" / "risk_limits.yaml"


def load_configs() -> tuple[dict, dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    with open(RISK_PATH, encoding="utf-8") as f:
        risk = yaml.safe_load(f)
    return cfg, risk


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    setup: str
    direction: str
    entry_price: float
    exit_price: float
    sl: float
    tp: float
    lot: float
    outcome: str            # tp / sl / timeout
    gross_points: float
    cost_points: float
    net_points: float
    pnl_idr: float
    r_multiple: float
    bars_held: int
    score: int
    resolution: str         # bagaimana ambiguitas diselesaikan

    def to_dict(self) -> dict:
        return asdict(self)


class Backtester:
    def __init__(
        self,
        config: Optional[dict] = None,
        risk: Optional[dict] = None,
        df_m1: Optional[pd.DataFrame] = None,
        ambiguity_mode: Literal["pessimistic", "m1"] = "pessimistic",
    ):
        cfg, rk = load_configs()
        self.cfg = config or cfg
        self.risk = risk or rk

        self.point = self.cfg["symbol"]["point"]
        self.value_per_point = self.cfg["symbol"]["value_per_point_idr"]
        self.vol_min = self.cfg["symbol"]["volume_min"]
        self.vol_step = self.cfg["symbol"]["volume_step"]

        self.spread = self.cfg["costs"]["spread_points"]
        self.slippage = self.cfg["costs"]["slippage_assume_points"]

        # Lama tahan posisi diambil dari config yang SAMA dengan yang dibaca
        # bot live (src/execution/bot.py: position_management.max_bars_hold).
        #
        # BUG YANG DIPERBAIKI (10 Sep 2026): nilai ini dulu di-hardcode 120
        # sebagai default argumen _simulate(), dan run() tidak pernah
        # mengopernya. Backtest karena itu menahan posisi sampai 10 jam
        # sementara bot live memotong di 4 jam — dua sistem yang berbeda.
        #
        # Efeknya bukan cuma beda hasil: posisi yang menahan 10 jam memblokir
        # sinyal berikutnya (satu posisi pada satu waktu), sehingga jumlah
        # trade backtest jauh lebih kecil dari yang bisa dicapai live dan
        # setiap pengukuran per sesi kekurangan sampel.
        pm = self.cfg.get("position_management", {})
        self.max_bars_hold = pm.get("max_bars_hold", 48)

        self.risk_pct = self.risk["per_trade"]["max_risk_percent"]
        self.max_daily_loss = self.risk["daily"]["max_loss_percent"]
        self.max_daily_trades = self.risk["daily"]["max_trades"]
        self.max_consec_losses = self.risk["daily"]["max_consecutive_losses"]
        self.max_dd = self.risk["global"]["max_drawdown_percent"]

        self.df_m1 = df_m1
        self.ambiguity_mode = ambiguity_mode
        if ambiguity_mode == "m1" and df_m1 is None:
            raise ValueError("mode 'm1' butuh df_m1")

        if df_m1 is not None:
            self.m1_from = df_m1["time_utc"].min()
            self.m1_to = df_m1["time_utc"].max()

    # -- sizing ----------------------------------------------------------

    def _lot_size(self, equity: float, sl_points: float, size_tier: str = "full") -> float:
        risk_pct = self.risk_pct
        if size_tier == "reduced":
            mult = self.risk.get("tiered_sizing", {}).get("reduced_risk_multiplier", 0.5)
            risk_pct *= mult
        risk_amount = equity * (risk_pct / 100.0)
        raw = risk_amount / (sl_points * self.value_per_point)
        steps = max(1, round(raw / self.vol_step))
        return max(self.vol_min, steps * self.vol_step)

    # -- resolusi ambiguitas ---------------------------------------------

    def _resolve_m1(
        self, bar_start, bar_end, sl: float, tp: float, direction: str
    ) -> Optional[str]:
        """Lihat urutan sentuhan SL/TP di dalam bar memakai data M1."""
        if self.df_m1 is None:
            return None
        if bar_start < self.m1_from or bar_start > self.m1_to:
            return None

        mask = (self.df_m1["time_utc"] >= bar_start) & (self.df_m1["time_utc"] < bar_end)
        sub = self.df_m1.loc[mask]
        if sub.empty:
            return None

        for r in sub.itertuples():
            if direction == "buy":
                hit_sl, hit_tp = r.low <= sl, r.high >= tp
            else:
                hit_sl, hit_tp = r.high >= sl, r.low <= tp
            if hit_sl and hit_tp:
                return "sl"      # masih ambigu di M1 -> tetap pesimis
            if hit_sl:
                return "sl"
            if hit_tp:
                return "tp"
        return None

    # -- simulasi satu trade ---------------------------------------------

    def _simulate(
        self,
        df: pd.DataFrame,
        sig: pd.Series,
        equity: float,
        max_bars: Optional[int] = None,
        breakeven_at_r: Optional[float] = None,
        trail_atr_mult: Optional[float] = None,
    ) -> Optional[Trade]:
        if max_bars is None:
            max_bars = self.max_bars_hold

        entry_idx = int(sig["idx"]) + 1  # eksekusi bar berikutnya
        if entry_idx >= len(df):
            return None

        direction = sig["direction"]
        bar = df.iloc[entry_idx]

        # Entry: bayar spread + slippage, keduanya merugikan
        slip = self.slippage * self.point
        if direction == "buy":
            entry = bar["open"] + self.spread * self.point + slip
        else:
            entry = bar["open"] - self.spread * self.point - slip

        # SL/TP digeser mengikuti harga entry aktual
        sl_dist = sig["sl_points"] * self.point
        tp_dist = sig["tp_points"] * self.point
        sl = entry - sl_dist if direction == "buy" else entry + sl_dist
        tp = entry + tp_dist if direction == "buy" else entry - tp_dist

        lot = self._lot_size(equity, sig["sl_points"], sig.get("size_tier", "full"))

        end_idx = min(entry_idx + max_bars, len(df) - 1)
        outcome, exit_price, exit_idx, resolution = "timeout", None, end_idx, "none"

        # Manajemen posisi aktif: SL bergerak, tidak pernah melebar.
        # Data menunjukkan TP butuh ~35 bar sementara SL kena di ~14 bar,
        # jadi banyak trade bergerak benar tapi kena SL lebih dulu.
        r_dist = sl_dist
        be_done = False

        for i in range(entry_idx, end_idx + 1):
            b = df.iloc[i]

            # URUTAN PENTING: SL/TP diperiksa DULU dengan level yang berlaku
            # sebelum bar ini, baru trailing diperbarui memakai close bar
            # yang sudah selesai.
            #
            # Versi sebelumnya memperbarui SL memakai high/low bar berjalan
            # lalu memeriksanya di bar yang sama — itu lookahead bias, dan
            # membuat backtest melaporkan hasil hingga 13x lebih baik dari
            # kenyataan (profit 22R padahal TP dibatasi 3R).

            if direction == "buy":
                hit_sl, hit_tp = b["low"] <= sl, b["high"] >= tp
            else:
                hit_sl, hit_tp = b["high"] >= sl, b["low"] <= tp

            if hit_sl and hit_tp:
                res = None
                if self.ambiguity_mode == "m1":
                    res = self._resolve_m1(
                        b["time_utc"], b["time_utc"] + pd.Timedelta(minutes=5),
                        sl, tp, direction,
                    )
                if res is None:
                    outcome, resolution = "sl", "pessimistic"
                else:
                    outcome, resolution = res, "m1_resolved"
                exit_price = sl if outcome == "sl" else tp
                exit_idx = i
                break
            if hit_sl:
                outcome, exit_price, exit_idx, resolution = "sl", sl, i, "clean"
                break
            if hit_tp:
                outcome, exit_price, exit_idx, resolution = "tp", tp, i, "clean"
                break

            # Perbarui trailing SETELAH bar dipastikan tidak menyentuh SL/TP.
            # Memakai close (bar sudah selesai), bukan high/low.
            #
            # Trigger di breakeven_at_r AKTIFKAN trailing ATR langsung (bukan
            # geser SL ke breakeven dulu). Diuji 9 Sep 2026: trigger 80%
            # jarak TP (=2.4R pada RR 1:3) + trailing ATR x2.0 memberi
            # E=+0,0308R (vs tanpa trailing +0,0319R) TAPI 4/6 kuartal
            # positif (vs 3/6 tanpa trailing) - lebih konsisten dengan
            # biaya expectancy minimal. Lihat docs/14-TRAILING-80PIP.md #8.
            if breakeven_at_r and not be_done and i > entry_idx:
                prof = (b["close"] - entry) if direction == "buy" else (entry - b["close"])
                if prof >= r_dist * breakeven_at_r:
                    be_done = True

            if trail_atr_mult and be_done and i > entry_idx:
                atr_now = b.get("atr", sig["atr"])
                if pd.notna(atr_now) and atr_now > 0:
                    if direction == "buy":
                        sl = max(sl, b["close"] - atr_now * trail_atr_mult)
                    else:
                        sl = min(sl, b["close"] + atr_now * trail_atr_mult)

        if exit_price is None:
            exit_price = df.iloc[end_idx]["close"]

        # SL kena biasanya lebih buruk dari harga persis (gap, likuiditas)
        if outcome == "sl":
            exit_price += (-slip if direction == "buy" else slip)

        gross = (exit_price - entry) if direction == "buy" else (entry - exit_price)
        gross_points = gross / self.point
        cost_points = self.spread + self.slippage

        pnl = gross_points * self.value_per_point * lot
        risk_amount = sig["sl_points"] * self.value_per_point * lot

        return Trade(
            entry_time=df.iloc[entry_idx]["time_utc"],
            exit_time=df.iloc[exit_idx]["time_utc"],
            setup=sig["setup"],
            direction=direction,
            entry_price=entry,
            exit_price=exit_price,
            sl=sl,
            tp=tp,
            lot=lot,
            outcome=outcome,
            gross_points=gross_points,
            cost_points=cost_points,
            net_points=gross_points,
            pnl_idr=pnl,
            r_multiple=pnl / risk_amount if risk_amount else 0.0,
            bars_held=exit_idx - entry_idx,
            score=int(sig["score"]),
            resolution=resolution,
        )

    # -- run -------------------------------------------------------------

    def run(
        self,
        df: pd.DataFrame,
        signals: pd.DataFrame,
        initial_equity: Optional[float] = None,
        breakeven_at_r: Optional[float] = None,
        trail_atr_mult: Optional[float] = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Jalankan backtest dengan seluruh batasan risiko aktif.

        initial_equity default mengikuti risk_limits.simulated_equity_idr,
        bukan angka 800.000 seperti sebelumnya. Pada equity 800.000 lot
        minimum 0,01 memaksa risiko ~8,7% per trade, sehingga setiap kurva
        equity, max drawdown, dan pemicu `halted` yang dihitung dengan
        default lama tidak sahih. R-multiple tetap sahih karena
        skala-invariant, tetapi metrik berbasis equity tidak.
        """
        if initial_equity is None:
            initial_equity = float(self.risk.get("simulated_equity_idr", 3_700_000))
        equity = initial_equity
        peak = equity
        trades: list[Trade] = []
        curve: list[dict] = []

        day_pnl, day_trades, consec_losses = 0.0, 0, 0
        current_day = None
        busy_until_idx = -1
        halted = False

        for _, sig in signals.iterrows():
            if halted:
                break

            day = pd.Timestamp(sig["time"]).date()
            if day != current_day:
                current_day, day_pnl, day_trades, consec_losses = day, 0.0, 0, 0

            # Satu posisi pada satu waktu
            if int(sig["idx"]) <= busy_until_idx:
                continue
            if day_trades >= self.max_daily_trades:
                continue
            if day_pnl <= -equity * (self.max_daily_loss / 100):
                continue
            if consec_losses >= self.max_consec_losses:
                continue

            trade = self._simulate(
                df, sig, equity,
                breakeven_at_r=breakeven_at_r,
                trail_atr_mult=trail_atr_mult,
            )
            if trade is None:
                continue

            equity += trade.pnl_idr
            peak = max(peak, equity)
            dd = (peak - equity) / peak * 100

            day_pnl += trade.pnl_idr
            day_trades += 1
            consec_losses = consec_losses + 1 if trade.pnl_idr < 0 else 0

            busy_until_idx = int(sig["idx"]) + trade.bars_held + 1
            trades.append(trade)
            curve.append(
                {"time": trade.exit_time, "equity": equity, "drawdown_pct": dd}
            )

            if dd >= self.max_dd:
                halted = True

        trades_df = pd.DataFrame([t.to_dict() for t in trades]) if trades else pd.DataFrame()
        curve_df = pd.DataFrame(curve) if curve else pd.DataFrame()
        return trades_df, curve_df
