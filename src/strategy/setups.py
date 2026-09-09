"""
Rule engine: menghasilkan sinyal trading dari struktur, sesi, dan indikator.

Dua setup:
  1. London Sweep Reversal  — setup unggulan, RR terbaik
  2. NY Momentum Continuation — searah tren, frekuensi lebih tinggi

Parameter jarak SL/TP mengikuti config, yang sudah disesuaikan dengan
spread 26 pip broker ini: SL minimum 150 pip, TP minimum 300 pip. Setup
dengan target lebih kecil tidak layak — biaya memakan terlalu besar.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "settings.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class Signal:
    idx: int
    time: pd.Timestamp
    setup: str
    direction: Literal["buy", "sell"]
    entry: float
    sl: float
    tp: float
    sl_points: float
    tp_points: float
    rr: float
    score: int
    atr: float
    session: str
    reasons: str
    size_tier: str = "full"   # "full" (1x risiko) atau "reduced" (risiko lebih kecil)

    def to_dict(self) -> dict:
        return asdict(self)


class RuleEngine:
    def __init__(self, config: Optional[dict] = None):
        self.cfg = config or load_config()
        d = self.cfg["trade_distances"]
        self.sl_min = d["sl_min_points"]
        self.sl_max = d["sl_max_points"]
        self.tp_min = d["tp_min_points"]
        self.min_rr = d["min_rr_ratio"]
        self.atr_mult = d["atr_sl_multiplier"]
        self.point = self.cfg["symbol"]["point"]
        self.spread = self.cfg["costs"]["spread_points"]

    # -- helper ----------------------------------------------------------

    def _price_to_points(self, price_diff: float) -> float:
        return abs(price_diff) / self.point

    def _points_to_price(self, points: float) -> float:
        return points * self.point

    def _sl_distance_points(self, atr_value: float) -> float:
        """Jarak SL dari ATR, dibatasi min/max sesuai karakter broker."""
        raw = self._price_to_points(atr_value * self.atr_mult)
        return float(min(max(raw, self.sl_min), self.sl_max))

    # -- filter umum -----------------------------------------------------

    def _passes_gates(self, row, require_session: bool = True) -> tuple[bool, str]:
        """Gate keras — gagal salah satu berarti tolak, bukan kurangi skor."""
        if require_session and not row.is_trading_session:
            return False, "di luar sesi trading"
        if row.friday_cutoff:
            return False, "Jumat sore - risiko gap weekend"
        if pd.isna(row.atr) or row.atr <= 0:
            return False, "ATR tidak tersedia"
        if pd.isna(row.atr_percentile):
            return False, "persentil ATR belum tersedia"
        if row.atr_percentile < 0.20:
            return False, "volatilitas terlalu rendah - spread mendominasi"
        if row.atr_percentile > 0.95:
            return False, "volatilitas ekstrem - kemungkinan berita"
        if row.spread > self.cfg["costs"]["spread_max_accept"]:
            return False, f"spread {row.spread} terlalu lebar"
        return True, ""

    def _build_signal(
        self, row, setup: str, direction: str, score: int, reasons: list[str],
        size_tier: str = "full",
    ) -> Optional[Signal]:
        """Susun sinyal lengkap dengan SL/TP, tolak jika RR tidak memadai."""
        entry = row.close
        sl_pts = self._sl_distance_points(row.atr)
        sl_dist = self._points_to_price(sl_pts)

        if direction == "buy":
            sl = entry - sl_dist
        else:
            sl = entry + sl_dist

        tp_pts = max(sl_pts * self.min_rr, self.tp_min)
        tp_dist = self._points_to_price(tp_pts)
        tp = entry + tp_dist if direction == "buy" else entry - tp_dist

        # Biaya spread dibayar di depan; RR efektif dihitung setelahnya
        rr_effective = (tp_pts - self.spread) / (sl_pts + self.spread)
        if rr_effective < self.min_rr * 0.75:
            return None

        return Signal(
            idx=row.Index,
            time=row.time_utc,
            setup=setup,
            direction=direction,
            entry=entry,
            sl=sl,
            tp=tp,
            sl_points=sl_pts,
            tp_points=tp_pts,
            rr=round(rr_effective, 2),
            score=score,
            atr=row.atr,
            session=row.session,
            reasons="; ".join(reasons),
            size_tier=size_tier,
        )

    # -- setup 1: London Sweep Reversal ----------------------------------

    def _london_sweep(self, row) -> Optional[Signal]:
        """
        Harga menyapu Asia range lalu berbalik.

        Logikanya: stop order menumpuk di luar Asia range. Saat London buka,
        harga sering menyapu level itu untuk mengambil likuiditas, lalu
        bergerak ke arah sebenarnya.
        """
        if row.session not in ("london_open", "london_ny"):
            return None
        if pd.isna(row.asia_high) or pd.isna(row.asia_low):
            return None

        score = 2  # sesi wajib
        reasons = [f"sesi {row.session}"]

        if row.sweep_low:
            direction = "buy"
            reasons.append("sweep Asia low")
            score += 2
        elif row.sweep_high:
            direction = "sell"
            reasons.append("sweep Asia high")
            score += 2
        else:
            return None

        # CHoCH searah reversal = konfirmasi pergantian karakter
        if (direction == "buy" and row.choch == 1) or (
            direction == "sell" and row.choch == -1
        ):
            score += 1
            reasons.append("CHoCH konfirmasi")

        # Tren HTF searah -> bobot tambahan; berlawanan -> tolak
        if direction == "buy" and row.trend_htf == "downtrend":
            return None
        if direction == "sell" and row.trend_htf == "uptrend":
            return None
        if (direction == "buy" and row.trend_htf == "uptrend") or (
            direction == "sell" and row.trend_htf == "downtrend"
        ):
            score += 2
            reasons.append("searah tren HTF")

        if 0.30 <= row.atr_percentile <= 0.85:
            score += 1
            reasons.append("volatilitas ideal")

        # Rejection wick: bukti penolakan harga di level sweep
        body = abs(row.close - row.open)
        rng = row.high - row.low
        if rng > 0 and body / rng < 0.5:
            score += 1
            reasons.append("rejection wick")

        return self._build_signal(row, "london_sweep", direction, score, reasons)

    # -- setup 2: NY Momentum --------------------------------------------

    def _ny_momentum(self, row) -> Optional[Signal]:
        """Pullback ke EMA20 searah tren saat sesi NY overlap."""
        if row.session != "london_ny":
            return None
        if pd.isna(row.ema20) or pd.isna(row.adx):
            return None

        score = 2
        reasons = ["sesi london_ny"]

        if row.adx < 25:
            return None
        score += 1
        reasons.append(f"ADX {row.adx:.0f} - trending")

        if row.trend_htf == "uptrend" and row.trend == "uptrend":
            direction = "buy"
        elif row.trend_htf == "downtrend" and row.trend == "downtrend":
            direction = "sell"
        else:
            return None

        score += 2
        reasons.append("tren M5 & HTF selaras")

        # Harga harus dekat EMA20 (pullback), bukan sudah jauh berlari
        dist_ema = abs(row.close - row.ema20) / row.atr if row.atr > 0 else 99
        if dist_ema > 1.0:
            return None
        score += 1
        reasons.append("pullback ke EMA20")

        if (direction == "buy" and row.plus_di > row.minus_di) or (
            direction == "sell" and row.minus_di > row.plus_di
        ):
            score += 1
            reasons.append("DI searah")

        if 0.30 <= row.atr_percentile <= 0.85:
            score += 1
            reasons.append("volatilitas ideal")

        return self._build_signal(row, "ny_momentum", direction, score, reasons)

    # -- setup 3: Momentum Continuation (fib + momentum) ------------------

    def _momentum_fib(self, row) -> Optional[Signal]:
        """
        Momentum kuat + harga di bagian atas range + tren HTF searah.

        Ditemukan lewat pengujian daya prediksi seluruh fitur terhadap
        hasil trade (RR 1:3). Tiga komponennya:

          mom_24 tinggi   : momentum 24 bar, dinormalisasi ATR
          fib_position    : posisi harga dalam range 100 bar (0=low, 1=high)
          trend_htf       : konfirmasi arah dari H1/H4

        Logika ekonominya: harga yang bergerak kuat DAN berada di dekat
        puncak range DAN searah tren besar cenderung melanjutkan — ini
        momentum, bukan mean reversion.

        Validasi:
          in-sample   +0,050R (WR 27,87%)
          out-sample  +0,069R (WR 28,35%)
          6/6 kuartal positif, 15/15 variasi parameter positif
          (breakeven WR untuk RR 1:3 = 25,4%; entry acak = 24,5%)
        """
        need = ("mom_24", "fib_position", "mom_24_q85")
        if any(not hasattr(row, f) or pd.isna(getattr(row, f)) for f in need):
            return None

        # Sesi yang terbukti menguntungkan untuk momentum (uji per sesi,
        # winrate vs breakeven 25,41%):
        #   ny_afternoon +5,45% | london_ny +4,84% | rollover +3,26%
        #   asia -3,03% | london_open -3,39% | pre_ny -5,73%  <- ditolak
        #
        # rollover ditambahkan (9 Sep 2026) untuk memperpendek jeda tunggu:
        # menutupi jam 19:30-06:00 WIB (10,5 jam), bukan cuma 19:30-04:00.
        # Dampak: WR turun tipis 30,77%->30,41%, tetap 5/6 kuartal positif.
        if row.session not in ("ny_afternoon", "london_ny", "rollover"):
            return None

        # ATR dalam rentang normal adalah SYARAT, bukan bonus skor.
        if not (0.30 <= row.atr_percentile <= 0.85):
            return None

        # Dua tier momentum, KEDUANYA terbukti untung, ukuran risiko beda:
        #
        #   TIER PENUH (mom_24 > 100% ambang): WR 32,25% | +6,84% vs BE
        #     -> risiko 1x. Ini sinyal berkualitas tinggi.
        #
        #   TIER KECIL (mom_24 > 50% ambang, di bawah tier penuh): WR 28,01%
        #     | +2,60% vs BE. Masih menguntungkan, tapi jarak ke breakeven
        #     lebih tipis -> risiko diperkecil.
        #
        #   Di bawah 50% ambang TIDAK diambil sama sekali: pengujian
        #   menunjukkan tier itu sudah RUGI (WR turun ke bawah breakeven
        #   saat filter lain juga dilonggarkan). Lihat docs/18.
        if row.mom_24 > row.mom_24_q85:
            size_tier = "full"
        elif row.mom_24 > row.mom_24_q85 * 0.5:
            size_tier = "reduced"
        else:
            return None

        # Arah ditentukan tren HTF; sisi bawah range untuk sell
        if row.trend_htf == "uptrend" and row.fib_position > 0.75:
            direction = "buy"
        elif row.trend_htf == "downtrend" and row.fib_position < 0.25:
            direction = "sell"
        else:
            return None

        score = 5 if size_tier == "full" else 3
        reasons = [
            f"momentum {'kuat' if size_tier=='full' else 'sedang'} (mom_24 {row.mom_24:.1f})",
            f"fib_position {row.fib_position:.2f}",
            f"HTF {row.trend_htf}",
            f"tier={size_tier}",
        ]

        if row.is_trading_session:
            score += 1
            reasons.append(f"sesi {row.session}")

        if hasattr(row, "stoch_k") and pd.notna(row.stoch_k):
            if (direction == "buy" and row.stoch_k > 70) or (
                direction == "sell" and row.stoch_k < 30
            ):
                score += 1
                reasons.append("stochastic konfirmasi")

        if 0.30 <= row.atr_percentile <= 0.85:
            score += 1
            reasons.append("volatilitas ideal")

        return self._build_signal(row, "momentum_fib", direction, score, reasons, size_tier)

    # -- setup 4: NY Volatility Window ------------------------------------

    def _ny_vol_window(self, row) -> Optional[Signal]:
        """
        Jendela waktu + volatilitas: jam 16-22 UTC dengan ATR di atas median.

        Ditemukan lewat diagnostik sistematis (bukan asumsi). Diagnostik
        mengungkap bahwa filter arah trend_htf TIDAK berguna (uptrend 23,86%
        vs downtrend 23,39%, baseline 23,65%) - yang membedakan justru
        KAPAN, bukan ke mana.

        Jam 16-22 UTC = 23:00-05:00 WIB, mencakup NY sore sampai rollover.
        Volatilitas di atas persentil 60 menyaring periode pasar mati.

        Validasi (breakeven WR = 25,41%):
          keseluruhan  : WR 26,47% (n=7.602)
          in-sample    : 26,29%
          out-sample   : 26,87%   <- lebih baik dari in-sample
          per kuartal  : 5/6 di atas breakeven

        Arah tetap mengikuti trend_htf karena harus memilih satu sisi;
        diagnostik menunjukkan kedua arah berkinerja setara di jendela ini.
        """
        if not (16 <= row.time_utc.hour <= 22):
            return None
        if pd.isna(row.atr_percentile) or row.atr_percentile <= 0.60:
            return None

        # Arah ditentukan RSI, bukan trend_htf.
        #
        # Diagnostik mengungkap trend_htf hampir tidak punya daya prediksi
        # (uptrend 23,86% vs downtrend 23,39%, baseline 23,65%). Pengujian
        # beberapa penentu arah di jendela ini:
        #   RSI>50          : WR 26,97% | OOS 29,21% | 5/6 kuartal
        #   trend_htf       : WR 27,17% | OOS 27,06% | 5/6 kuartal
        #   harga vs EMA20  : WR 26,88% | OOS 29,11% | 4/6 kuartal
        #   selalu buy/sell : WR 24,6-25,3% (pembanding tanpa arah)
        #
        # RSI dipilih karena OOS tertinggi dan tidak bergantung pada
        # klasifikasi swing yang rapuh.
        if pd.isna(row.rsi):
            return None
        direction = "buy" if row.rsi > 50 else "sell"

        score = 5
        reasons = [
            f"jendela NY (jam {row.time_utc.hour} UTC)",
            f"ATR pct {row.atr_percentile:.2f}",
            f"RSI {row.rsi:.0f}",
        ]

        if hasattr(row, "mom_24") and pd.notna(row.mom_24):
            if (direction == "buy" and row.mom_24 > 0) or (
                direction == "sell" and row.mom_24 < 0
            ):
                score += 1
                reasons.append("momentum searah")

        if hasattr(row, "adx") and pd.notna(row.adx) and row.adx > 25:
            score += 1
            reasons.append(f"ADX {row.adx:.0f}")

        return self._build_signal(row, "ny_vol_window", direction, score, reasons)

    # -- setup 5: Frequent Micro-Momentum (eksperimental, terpisah) -------

    def _frequent_micro(self, row) -> Optional[Signal]:
        """
        Versi frekuensi tinggi dari momentum_fib — SETUP TERPISAH, tidak
        menggantikan momentum_fib.

        Dibuat atas permintaan eksplisit untuk sinyal lebih sering (~1 per
        2 jam, bukan 1 per jam - itu sudah rugi, lihat catatan di bawah).
        Filter dilonggarkan ke titik PALING LONGGAR yang masih terukur
        untung:

          momentum > 50% ambang (bukan 100%)
          fib_position tetap ketat (>0.75 / <0.25)
          ATR tetap 0.30-0.85
          TANPA filter sesi -> aktif 24 jam, termasuk Asia/London/pre-NY

        Hasil uji sistematis (breakeven WR = 25,41%):
          filter ini           : 11,65 sinyal/hari, WR 25,62% (+0,21%)
          1 tingkat lebih longgar: 13,72/hari, WR 25,33% (-0,08%) <- RUGI

        Celah keuntungannya SANGAT TIPIS (+0,21%). Ini alasan setup ini
        TIDAK diaktifkan default (lihat active_setups di settings.yaml) -
        harus diaktifkan sadar, dan idealnya dengan risiko lebih kecil
        daripada momentum_fib karena marjin amannya jauh lebih sempit.

        TIDAK ADA konfigurasi yang mencapai "1 sinyal per jam" (24/hari)
        sambil tetap untung. Titik itu sudah diuji dan hasilnya -0,08%
        sampai -0,78% di bawah breakeven, tergantung seberapa longgar.
        """
        need = ("mom_24", "fib_position", "mom_24_q85")
        if any(not hasattr(row, f) or pd.isna(getattr(row, f)) for f in need):
            return None

        if row.mom_24 <= row.mom_24_q85 * 0.5:
            return None

        if not (0.30 <= row.atr_percentile <= 0.85):
            return None

        if row.trend_htf == "uptrend" and row.fib_position > 0.75:
            direction = "buy"
        elif row.trend_htf == "downtrend" and row.fib_position < 0.25:
            direction = "sell"
        else:
            return None

        score = 3  # selalu di bawah momentum_fib - marjin lebih tipis
        reasons = [
            f"micro-momentum (mom_24 {row.mom_24:.1f})",
            f"fib_position {row.fib_position:.2f}",
            f"HTF {row.trend_htf}",
            "TANPA filter sesi - 24 jam",
        ]

        return self._build_signal(
            row, "frequent_micro", direction, score, reasons, size_tier="reduced"
        )

    # -- generator utama -------------------------------------------------

    def generate(self, df: pd.DataFrame, min_score: int = 7) -> pd.DataFrame:
        """
        Hasilkan sinyal untuk seluruh dataframe.

        min_score menyaring hanya setup grade A. Dengan risiko 3% per trade,
        selektivitas adalah bagian dari manajemen risiko — bukan kehati-hatian
        berlebihan.
        """
        signals: list[Signal] = []

        for row in df.itertuples():
            ok_strict, _ = self._passes_gates(row, require_session=True)

            if ok_strict:
                found = False
                for detector in (
                    self._ny_vol_window,
                    self._momentum_fib,
                    self._london_sweep,
                    self._ny_momentum,
                ):
                    sig = detector(row)
                    if sig and sig.score >= min_score:
                        signals.append(sig)
                        found = True
                        break
                if found:
                    continue

            # frequent_micro didesain TANPA filter sesi (24 jam) - pakai
            # gerbang longgar (masih menjaga ATR minimum, spread, Jumat sore)
            ok_loose, _ = self._passes_gates(row, require_session=False)
            if not ok_loose:
                continue
            sig = self._frequent_micro(row)
            if sig and sig.score >= min_score:
                signals.append(sig)

        if not signals:
            return pd.DataFrame()

        return pd.DataFrame([s.to_dict() for s in signals])
