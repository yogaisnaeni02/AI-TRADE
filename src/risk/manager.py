"""
Risk manager — menolak eksekusi yang melanggar batasan.

Layer ini lebih menentukan hasil akhir daripada kecanggihan strategi.
Semua limit dibaca dari config/risk_limits.yaml dan dikunci di sini:
tidak ada jalur kode yang bisa melewatinya.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import yaml

ROOT = Path(__file__).resolve().parents[2]
RISK_PATH = ROOT / "config" / "risk_limits.yaml"
SETTINGS_PATH = ROOT / "config" / "settings.yaml"


def load_risk_config() -> dict:
    with open(RISK_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_settings() -> dict:
    with open(SETTINGS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class RiskDecision:
    allowed: bool
    reason: str
    lot: float = 0.0
    risk_amount: float = 0.0
    risk_pct: float = 0.0


@dataclass
class SessionState:
    """State harian/mingguan. Direset otomatis saat hari berganti."""
    day: Optional[date] = None
    day_pnl: float = 0.0
    day_trades: int = 0
    consecutive_losses: int = 0
    week_start: Optional[date] = None
    week_pnl: float = 0.0
    peak_equity: float = 0.0
    order_failures: int = 0
    halted: bool = False
    halt_reason: str = ""


class RiskManager:
    def __init__(self, config: Optional[dict] = None, risk: Optional[dict] = None):
        self.cfg = config or load_settings()
        self.risk = risk or load_risk_config()

        pt = self.risk["per_trade"]
        self.max_risk_pct = pt["max_risk_percent"]
        self.min_rr = pt["min_rr_ratio"]
        self.max_lot_pct = pt["max_lot_percent_equity"]

        dy = self.risk["daily"]
        self.max_daily_loss_pct = dy["max_loss_percent"]
        self.max_daily_trades = dy["max_trades"]
        self.max_consec_losses = dy["max_consecutive_losses"]

        self.max_weekly_loss_pct = self.risk["weekly"]["max_loss_percent"]

        gl = self.risk["global"]
        self.max_dd_pct = gl["max_drawdown_percent"]
        self.max_positions = gl["max_open_positions"]
        self.max_spread = self.cfg["costs"]["spread_max_accept"]

        self.derisking = self.risk.get("derisking", [])

        sym = self.cfg["symbol"]
        self.point = sym["point"]
        self.value_per_point = sym["value_per_point_idr"]
        self.vol_min = sym["volume_min"]
        self.vol_step = sym["volume_step"]
        self.vol_max = sym["volume_max"]

        self.state = SessionState()

    # -- state -----------------------------------------------------------

    def _roll_period(self, now: datetime, equity: float) -> None:
        today = now.date()
        if self.state.day != today:
            self.state.day = today
            self.state.day_pnl = 0.0
            self.state.day_trades = 0
            self.state.consecutive_losses = 0

        monday = today.fromordinal(today.toordinal() - today.weekday())
        if self.state.week_start != monday:
            self.state.week_start = monday
            self.state.week_pnl = 0.0

        self.state.peak_equity = max(self.state.peak_equity, equity)

    def current_drawdown_pct(self, equity: float) -> float:
        if self.state.peak_equity <= 0:
            return 0.0
        return (self.state.peak_equity - equity) / self.state.peak_equity * 100

    def effective_risk_pct(self, equity: float) -> float:
        """Risiko menurun otomatis saat drawdown membesar."""
        dd = self.current_drawdown_pct(equity)
        risk = self.max_risk_pct
        for rule in self.derisking:
            if dd >= rule.get("drawdown_above", 1e9):
                if "reduce_risk_to" in rule:
                    risk = min(risk, rule["reduce_risk_to"])
        return risk

    # -- sizing ----------------------------------------------------------

    def confidence_multiplier(self, confidence: Optional[float]) -> float:
        """
        Pengali lot berdasarkan keyakinan sinyal (0..1).

        HANYA aktif bila `adaptive_sizing.enabled` bernilai true di
        risk_limits.yaml. Default: NONAKTIF.

        Alasan default nonaktif: menaikkan lot hanya menguntungkan bila
        skor keyakinan benar-benar memprediksi hasil. Pengujian pada setup
        saat ini menunjukkan korelasi skor-hasil = -0,006 (praktis nol),
        sehingga menaikkan lot berarti membesarkan taruhan secara acak.

        Simulasi 1000 skenario (WR 41%, RR 1:3, 200 trade):
          lot tetap 3%          -> median 0,81x, bangkrut 1,5%
          lot 2x acak           -> median 0,66x, bangkrut 17,4%
          lot 3x acak           -> median 0,42x, bangkrut 42,8%
          lot 2x saat WR 55%    -> median 1,52x   <- baru di sini berguna

        Aktifkan hanya setelah forward test membuktikan sinyal berkeyakinan
        tinggi memang menghasilkan winrate lebih tinggi.
        """
        cfg = self.risk.get("adaptive_sizing", {})
        if not cfg.get("enabled", False) or confidence is None:
            return 1.0

        tiers = cfg.get("tiers", [])
        mult = 1.0
        for t in sorted(tiers, key=lambda x: x.get("min_confidence", 0)):
            if confidence >= t.get("min_confidence", 1.1):
                mult = t.get("multiplier", 1.0)

        return min(mult, cfg.get("max_multiplier", 2.0))

    def calculate_lot(
        self,
        equity: float,
        sl_points: float,
        confidence: Optional[float] = None,
        size_tier: str = "full",
    ) -> tuple[float, float]:
        """Hitung lot dari risiko dan jarak SL. Mengembalikan (lot, risk_amount)."""
        risk_pct = self.effective_risk_pct(equity)
        risk_pct *= self.confidence_multiplier(confidence)

        if size_tier == "reduced":
            mult = self.risk.get("tiered_sizing", {}).get("reduced_risk_multiplier", 0.5)
            risk_pct *= mult

        # Pengali tidak boleh menembus batas keras per-trade
        risk_pct = min(risk_pct, self.max_lot_pct)
        risk_amount = equity * (risk_pct / 100.0)

        raw = risk_amount / (sl_points * self.value_per_point)
        steps = max(1, round(raw / self.vol_step))
        lot = max(self.vol_min, min(steps * self.vol_step, self.vol_max))

        actual_risk = lot * sl_points * self.value_per_point
        return round(lot, 2), actual_risk

    # -- pemeriksaan utama -----------------------------------------------

    def check(
        self,
        now: datetime,
        equity: float,
        sl_points: float,
        tp_points: float,
        spread_points: float,
        open_positions: int,
        stop_file_exists: bool = False,
        news_blackout: bool = False,
        confidence: Optional[float] = None,
        size_tier: str = "full",
    ) -> RiskDecision:
        """Gerbang tunggal sebelum order dikirim. Gagal satu = tolak."""
        self._roll_period(now, equity)

        if stop_file_exists:
            return RiskDecision(False, "file STOP ada — kill switch manual aktif")

        # Equity tidak memadai. Melindungi dari dua kasus:
        #   - akun kosong (belum deposit, atau habis kena stop out)
        #   - equity di bawah margin minimum untuk 1 lot terkecil
        min_equity = self.risk.get("min_equity_idr", 500_000)
        if equity < min_equity:
            return RiskDecision(
                False,
                f"equity Rp {equity:,.0f} di bawah minimum Rp {min_equity:,.0f} "
                "— deposit dulu sebelum menjalankan bot",
            )

        if self.state.halted:
            return RiskDecision(False, f"sistem dihentikan: {self.state.halt_reason}")

        dd = self.current_drawdown_pct(equity)
        if dd >= self.max_dd_pct:
            self.state.halted = True
            self.state.halt_reason = f"drawdown {dd:.1f}% >= {self.max_dd_pct}%"
            return RiskDecision(False, self.state.halt_reason)

        if news_blackout:
            return RiskDecision(False, "window blackout berita")

        if open_positions >= self.max_positions:
            return RiskDecision(False, f"sudah ada {open_positions} posisi terbuka")

        if spread_points > self.max_spread:
            return RiskDecision(
                False, f"spread {spread_points:.0f} > batas {self.max_spread}"
            )

        if self.state.day_trades >= self.max_daily_trades:
            return RiskDecision(False, f"batas {self.max_daily_trades} trade/hari tercapai")

        if self.state.consecutive_losses >= self.max_consec_losses:
            return RiskDecision(
                False, f"{self.state.consecutive_losses} loss beruntun — stop sisa hari"
            )

        daily_limit = -equity * (self.max_daily_loss_pct / 100)
        if self.state.day_pnl <= daily_limit:
            return RiskDecision(False, f"batas loss harian {self.max_daily_loss_pct}% tercapai")

        weekly_limit = -equity * (self.max_weekly_loss_pct / 100)
        if self.state.week_pnl <= weekly_limit:
            return RiskDecision(False, f"batas loss mingguan {self.max_weekly_loss_pct}% tercapai")

        rr = (tp_points - spread_points) / (sl_points + spread_points)
        if rr < self.min_rr * 0.75:
            return RiskDecision(False, f"RR efektif {rr:.2f} di bawah minimum")

        lot, risk_amount = self.calculate_lot(equity, sl_points, confidence, size_tier)
        risk_pct = risk_amount / equity * 100 if equity else 0

        if risk_pct > self.max_lot_pct:
            return RiskDecision(
                False,
                f"lot minimum memaksa risiko {risk_pct:.1f}% > batas {self.max_lot_pct}%",
            )

        return RiskDecision(True, "lolos semua pemeriksaan", lot, risk_amount, risk_pct)

    # -- update setelah trade --------------------------------------------

    def record_trade(self, pnl: float) -> None:
        self.state.day_pnl += pnl
        self.state.week_pnl += pnl
        self.state.day_trades += 1
        self.state.consecutive_losses = (
            self.state.consecutive_losses + 1 if pnl < 0 else 0
        )

    def record_order_failure(self) -> bool:
        """Kembalikan True bila sistem harus dihentikan."""
        self.state.order_failures += 1
        limit = self.risk["circuit_breaker"]["consecutive_order_failures"]
        if self.state.order_failures >= limit:
            self.state.halted = True
            self.state.halt_reason = f"{self.state.order_failures} order gagal beruntun"
            return True
        return False

    def record_order_success(self) -> None:
        self.state.order_failures = 0

    def halt(self, reason: str) -> None:
        self.state.halted = True
        self.state.halt_reason = reason
