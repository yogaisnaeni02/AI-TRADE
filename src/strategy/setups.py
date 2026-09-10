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
from typing import Literal, Optional, Sequence

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
    def __init__(
        self,
        config: Optional[dict] = None,
        active_setups: Optional[Sequence[str]] = None,
        momentum_sessions: Optional[Sequence[str]] = None,
    ):
        self.cfg = config or load_config()
        d = self.cfg["trade_distances"]
        self.sl_min = d["sl_min_points"]
        self.sl_max = d["sl_max_points"]
        self.tp_min = d["tp_min_points"]
        self.min_rr = d["min_rr_ratio"]
        self.atr_mult = d["atr_sl_multiplier"]
        self.point = self.cfg["symbol"]["point"]
        self.spread = self.cfg["costs"]["spread_points"]

        # Setup mana yang benar-benar dijalankan.
        #
        # BUG YANG DIPERBAIKI (10 Sep 2026): sebelumnya generate() selalu
        # mencoba SEMUA detektor berurutan dengan `break` pada match
        # pertama, dan _ny_vol_window ada di urutan pertama meski sudah
        # dinonaktifkan di config. Karena skor minimumnya sama dengan
        # min_score bot, ia selalu menang duluan, momentum_fib tidak pernah
        # dievaluasi di bar itu, lalu sinyalnya dibuang senyap oleh bot
        # karena setup-nya tidak aktif. Sekarang setup nonaktif tidak
        # pernah dipanggil sama sekali.
        self.active_setups = tuple(
            active_setups
            if active_setups is not None
            else self.cfg.get("active_setups", ["momentum_fib"])
        )

        # Sesi mana yang boleh ditradingkan momentum_fib.
        #
        # Dibuat bisa dikonfigurasi (10 Sep 2026) karena ranking sesi yang
        # dulu di-hardcode diukur pada data yang labelnya meleset 7 jam —
        # lihat docs/27-AUDIT-TEMUAN.md bagian 1. Angka lama tidak berlaku
        # dan sesi harus diukur ulang dari awal. None = semua sesi (24 jam).
        cfg_sessions = self.cfg.get("momentum_sessions", None)
        if momentum_sessions is not None:
            self.momentum_sessions: Optional[tuple[str, ...]] = tuple(momentum_sessions)
        elif cfg_sessions is not None:
            self.momentum_sessions = tuple(cfg_sessions)
        else:
            self.momentum_sessions = None

        # Gate ATR untuk momentum_fib, dari config agar bisa dikalibrasi
        # ulang tanpa menyentuh kode. Lihat catatan panjang di _momentum_fib.
        mf = self.cfg.get("momentum_fib", {}) or {}
        self.atr_lo = float(mf.get("atr_percentile_min", 0.20))
        self.atr_hi = float(mf.get("atr_percentile_max", 0.95))

        # Patuhi kolom `is_trading_session` atau tidak. MATI default.
        #
        # Jaring pengaman, bukan pengubah perilaku: sejak sessions.py
        # dikoreksi (10 Sep 2026) SEMUA sesi bertanda trade=True, sehingga
        # kolom itu selalu True dan flag ini tidak berpengaruh apa pun.
        #
        # Tetap ada karena penandaan trade=False pernah membuat backtest
        # memblokir 7 jam penuh tanpa disadari. Diukur pada daftar SESSIONS
        # yang lama (asia & pre_ny = False), efeknya besar:
        #   patuhi is_trading_session : n=457  E[R]=-0,1254  t=-1,65  DD 89%
        #   abaikan (24 jam penuh)    : n=897  E[R]=+0,1254  t=+2,14  DD 32%
        #
        # Jadi bila suatu saat ada sesi ditandai trade=False lagi, flag ini
        # membuat keputusannya eksplisit di config, bukan tersembunyi di
        # daftar hardcode.
        self.require_trading_session = bool(mf.get("require_trading_session", False))

        # Izinkan sisi SELL. MATI default.
        #
        # EKSPERIMEN DEMO, bukan setelan yang diyakini menguntungkan.
        # Backtest konsisten mengatakan sisi sell TIDAK punya edge:
        #
        #   varian                      n     E[R]      t   sisi sell   holdout
        #   sell mati (baseline)      693  +0,1188   1,78          -   +0,1489
        #   sell simetris            1170  +0,0539   1,07    -0,0379   -0,5333
        #   sell + H4 downtrend       820  +0,0974   1,60    -0,0494   +0,0750
        #   sell + H1&H4 downtrend    723  +0,0983   1,51    -0,3757   +0,1077
        #
        # Tiga definisi rezim diuji; tidak ada yang menyelamatkannya, dan
        # baseline tetap terbaik di holdout tersegel.
        #
        # Dinyalakan HANYA di akun demo untuk satu alasan: backtest bilang
        # negatif, pengamatan manual pemilik bilang sebaliknya, dan rezim
        # turun saat ini (14 hari -4,79%, downtrend 71,7%) adalah kondisi
        # yang di backtest hanya muncul di 1 dari 6 kuartal. Menguji di demo
        # tidak berbiaya, dan jendela ini mungkin tidak terulang berbulan.
        #
        # JANGAN nyalakan di akun real sebelum sisi sell lolos gerbangnya
        # sendiri (docs/29 bagian 9). Analisis buy dan sell WAJIB terpisah.
        self.allow_sell = bool(mf.get("allow_sell", False))


        # Filter konfluensi (candle searah + ADX + tren M5). MATI default.
        #
        # Kandidat terkuat di proyek ini. Diukur dengan halt DD dimatikan
        # tetapi batas harian TETAP AKTIF (metode yang benar - batas harian
        # adalah bagian dari sistem yang akan berjalan live; lihat docs/38):
        #
        #             tanpa filter    dengan filter
        #   n              675             519  (77%)
        #   E[R]        +0,1327         +0,2510
        #   t             +1,95           +3,14   <- lampaui ambang ~3,0
        #   walk-forward    3/5             5/5
        #   holdout 30%  +0,0748         +0,2805
        #
        # t=3,14 melampaui ambang Bonferroni ~3,0 yang ditetapkan docs/30
        # setelah 50+ percobaan pada data M5 yang sama. Ini satu-satunya
        # angka di proyek ini yang mencapainya - momentum_fib sendiri 1,95.
        #
        # Yang membuatnya bisa dipercaya: HOLDOUT 30% TERSEGEL juga positif
        # (+0,2805), dan data itu tidak pernah dipakai memilih filter.
        #
        # Tetap dimatikan karena docs/29 melarang mengubah logika sinyal
        # selama forward test berjalan. Aktifkan SETELAH forward test:
        #     momentum_fib:
        #       confluence_filter: true
        #
        # Pengukuran lengkap: docs/36-UJI-GABUNGAN-TEKNIK.md (30 filter),
        # docs/37-UJI-BOS-CHOCH.md (BOS/CHoCH gagal), docs/38 (metode).
        self.confluence_filter = bool(mf.get("confluence_filter", False))
        self.confluence_adx_min = float(mf.get("confluence_adx_min", 25.0))

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

        # Filter sesi, sekarang dari konfigurasi. None = semua sesi.
        #
        # RANKING SESI LAMA SUDAH DICABUT (10 Sep 2026). Komentar di sini
        # dulu mencatat:
        #     ny_afternoon +5,45% | london_ny +4,84% | rollover +3,26%
        #     asia -3,03% | london_open -3,39% | pre_ny -5,73%
        # Semua angka itu diukur pada data yang kolom time_utc-nya meleset
        # 7 jam, sehingga LABEL sesinya salah sasaran: yang diberi label
        # "ny_afternoon" sebenarnya sesi Tokyo, dan sesi London yang
        # sesungguhnya berlabel "asia" lalu ditolak — tidak pernah diuji
        # sekali pun. Lihat docs/27-AUDIT-TEMUAN.md bagian 1.
        #
        # Sesi harus diukur ulang dari nol dengan data yang sudah benar.
        # Sampai itu selesai, default-nya semua sesi dibuka.
        if self.momentum_sessions is not None and row.session not in self.momentum_sessions:
            return None

        # ATR dalam rentang normal adalah SYARAT, bukan bonus skor.
        #
        # DILONGGARKAN 0,30-0,85 -> 0,20-0,95 (10 Sep 2026), dari config.
        #
        # Rentang lama mencekik frekuensi: momentum_fib hanya menghasilkan
        # ~106 trade dalam 1,4 tahun, dan pada laju itu membuktikan edge
        # +0,10R butuh ~29 tahun. Setup sebagus apa pun tidak berguna kalau
        # tidak pernah bisa dibuktikan.
        #
        # Sapuan (scripts/sweep_frequency.py) menunjukkan pelonggaran gate
        # ini menaikkan jumlah trade dengan expectancy IKUT NAIK, bukan
        # turun. Periode penuh tanpa halt DD: baseline 602 trade / +0,100R
        # (t 1,42) -> 721 trade / +0,156R (t 2,38). Itu menandakan rentang lama
        # membuang peluang bagus, bukan menyaring yang jelek. Melonggarkan
        # gate LAIN (momentum, fib) tidak menambah apa pun, dan melonggarkan
        # semuanya sekaligus justru hancur (WR 15,6%) - jadi spesifik gate
        # ATR ini yang salah kalibrasi.
        #
        # Stabil di kedua paruh M5: +0,177R (Apr-Des 25) dan +0,134R
        # (Des 25-Sep 26). Max drawdown alami 32% - kill switch 20% AKAN
        # menyala kira-kira sekali per 1,4 tahun, dan itu sesuai desain.
        #
        # BATAS KEPERCAYAAN - baca sebelum menaikkan risiko:
        # t = 2,38 diperoleh setelah menguji ~50 kombinasi pada data yang
        # sama (termasuk 7 strategi alternatif yang semuanya negatif);
        # ambang jujurnya ~3,0. Dan varian ini NEGATIF di M15
        # (-0,141R atas 4,23 tahun), termasuk setelah SL dikalibrasi ulang.
        # Boleh jadi edge-nya memang khas M5, boleh jadi ini artefak 1,4
        # tahun data. Belum terjawab. Lihat docs/28-HASIL-KALIBRASI-ULANG.md
        if not (self.atr_lo <= row.atr_percentile <= self.atr_hi):
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
        # ASIMETRI YANG DISENGAJA — JANGAN "PERBAIKI" TANPA MEMBACA INI.
        #
        # `mom_24` BERTANDA (positif = harga naik). Ambang `mom_24_q85`
        # adalah kuantil 85, selalu positif. Jadi syarat di bawah berarti
        # "harga sedang naik kuat" — untuk KEDUA arah.
        #
        # Untuk sell, itu menuntut harga NAIK padahal trend_htf wajib
        # downtrend: dua syarat yang hampir saling meniadakan. Hasilnya
        # sistem ini praktis hanya BUY: 4.180 sinyal buy vs 9 sell.
        #
        # Terlihat seperti bug, dan secara logika memang salah. Tetapi
        # perbaikan simetris (-mom_24 untuk sell) SUDAH DIUJI dan MERUGIKAN:
        #
        #                    sekarang    simetris
        #   trade                 675       1.140
        #   E[R]             +0,1327     +0,0725
        #   t                  +1,95       +1,41
        #   holdout          +0,0748     +0,0477
        #
        #   dipecah per arah pada varian simetris:
        #     BUY  n=673  E=+0,1411  t=+2,07   <- semua edge ada di sini
        #     SELL n=520  E=-0,0151  t=-0,20   <- tidak ada edge
        #
        # Sisi sell tidak punya edge; menambahkannya hanya mengencerkan
        # sisi buy dengan 520 trade ber-expectancy nol. Asimetri ini tanpa
        # sengaja menyaringnya, jadi DIBIARKAN sebagai keputusan sadar.
        #
        # KONSEKUENSI: bukti sistem ini bias ke rezim emas NAIK (data Apr
        # 2025 - Sep 2026, $3.200 -> $4.400). Di bear market panjang sistem
        # akan jarang memberi sinyal. Lihat docs/39.
        # Arah ditentukan DULU, baru momentum diuji dengan tanda yang sesuai.
        #
        # Urutan ini dibalik 10 Sep 2026 agar sisi sell bisa diaktifkan.
        # Sebelumnya momentum diuji sebelum arah diketahui, sehingga sell
        # menuntut "harga sedang NAIK kuat" padahal trend_htf wajib
        # downtrend - dua syarat yang saling meniadakan.
        #
        # Perilaku BUY tidak berubah sama sekali: untuk buy, mom_arah =
        # +mom_24, identik dengan gate lama.
        if row.trend_htf == "uptrend" and row.fib_position > 0.75:
            direction = "buy"
        elif row.trend_htf == "downtrend" and row.fib_position < 0.25:
            if not self.allow_sell:
                return None
            direction = "sell"
        else:
            return None

        # Momentum bertanda: naik kuat untuk buy, turun kuat untuk sell.
        mom_arah = row.mom_24 if direction == "buy" else -row.mom_24
        if mom_arah > row.mom_24_q85:
            size_tier = "full"
        elif mom_arah > row.mom_24_q85 * 0.5:
            size_tier = "reduced"
        else:
            return None

        # Filter konfluensi - hanya MEMBUANG sinyal, tidak pernah mengubah
        # arah/SL/TP/lot. Sinyal yang lolos identik dengan tanpa filter.
        #
        # Dua syarat yang terbukti menyumbang sendiri-sendiri di holdout:
        #   ADX > 25       -> tren cukup kuat (E +0,026 -> +0,105 sendirian)
        #   candle searah  -> bar sinyal searah arah entry (-> +0,052)
        #   keduanya       -> +0,128
        #
        # MACD dan Stochastic sengaja TIDAK dipakai: keduanya MEMPERBURUK
        # hasil (-0,040R dan -0,065R). MACD mengulang informasi momentum(24)
        # yang sudah dipakai setup ini, hanya lebih terlambat.
        if self.confluence_filter:
            adx = getattr(row, "adx", None)
            if adx is None or pd.isna(adx) or adx <= self.confluence_adx_min:
                return None

            bull_candle = row.close > row.open
            if (direction == "buy") != bull_candle:
                return None

            # Tren struktur M5 tidak boleh MELAWAN arah entry. Sengaja
            # longgar - "ranging" tetap diterima, hanya arah berlawanan yang
            # ditolak. Membuang 3,4% trade, menaikkan E di kedua periode
            # (seleksi +0,143 -> +0,163, holdout +0,128 -> +0,155).
            #
            # BOS dan CHoCH sengaja TIDAK dipakai: keduanya memperburuk
            # (-0,026R dan -0,135R). BOS mengulang momentum(24) lebih
            # terlambat; CHoCH mencari pembalikan sementara setup ini mencari
            # kelanjutan. Lihat docs/37-UJI-BOS-CHOCH.md.
            trend_m5 = getattr(row, "trend", None)
            opposite = "downtrend" if direction == "buy" else "uptrend"
            if trend_m5 == opposite:
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

    def generate(self, df: pd.DataFrame, min_score: int = 5) -> pd.DataFrame:
        # default 7 -> 5 (10 Sep 2026) agar SAMA dengan TradingBot.
        #
        # Sebelumnya berbeda: bot memakai 5, default signature ini 7.
        # Siapa pun yang memanggil generate(df) tanpa argumen mengukur
        # sistem yang bukan yang berjalan live - dan itu terjadi: seluruh
        # angka docs/36 & docs/38 diukur pada min_score=7. Divergensi
        # backtest-live ketiga setelah max_bars dan label sesi. docs/38 §9.
        """
        Hasilkan sinyal untuk seluruh dataframe.

        min_score menyaring hanya setup grade A. Dengan risiko 3% per trade,
        selektivitas adalah bagian dari manajemen risiko — bukan kehati-hatian
        berlebihan.
        """
        signals: list[Signal] = []

        # Hanya setup AKTIF yang dipanggil, dan urutannya tidak lagi
        # menentukan siapa yang menang: semua kandidat di satu bar
        # dikumpulkan, lalu skor tertinggi yang dipakai.
        #
        # Versi lama memakai first-match-wins dengan _ny_vol_window di urutan
        # pertama meski setup itu nonaktif. Karena skor minimumnya sama
        # dengan min_score bot, ia selalu menang, momentum_fib tidak pernah
        # dievaluasi di bar tersebut, dan sinyalnya kemudian dibuang senyap
        # oleh bot. Efeknya setup yang aktif kehilangan sebagian peluangnya
        # tanpa jejak apa pun di log.
        strict_detectors = [
            (name, fn)
            for name, fn in (
                ("ny_vol_window", self._ny_vol_window),
                ("momentum_fib", self._momentum_fib),
                ("london_sweep", self._london_sweep),
                ("ny_momentum", self._ny_momentum),
            )
            if name in self.active_setups
        ]
        run_frequent_micro = "frequent_micro" in self.active_setups

        for row in df.itertuples():
            ok_strict, _ = self._passes_gates(
                row, require_session=self.require_trading_session
            )

            if ok_strict and strict_detectors:
                candidates = [
                    sig
                    for _, detector in strict_detectors
                    if (sig := detector(row)) and sig.score >= min_score
                ]
                if candidates:
                    signals.append(max(candidates, key=lambda s: s.score))
                    continue

            if not run_frequent_micro:
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
