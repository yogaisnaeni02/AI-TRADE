"""
Trading bot — loop utama mode EXECUTOR.

Alur tiap bar M5 yang baru selesai:
  1. Ambil data terbaru dari MT5
  2. Hitung indikator, struktur, sesi
  3. Rule engine mencari sinyal
  4. Risk manager memeriksa (gerbang tunggal)
  5. Order manager mengirim order bila lolos
  6. Kelola posisi terbuka (break-even, trailing)

PENGAMAN:
  - File STOP di root langsung memblokir entry baru
  - Mode dibaca dari config; EXECUTOR wajib dinyatakan eksplisit
  - Akun REAL memerlukan konfirmasi tambahan
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import MetaTrader5 as mt5
import pandas as pd

from ..data.mt5_gateway import (
    MT5Gateway,
    ambil_pesan_offset,
    detect_server_offset_hours,
    load_config,
)
from ..features.indicators import add_all, add_extended
from ..features.pipeline import build_htf_context
from ..config_fingerprint import describe as cfg_describe, fingerprint as cfg_fingerprint
from ..risk.manager import RiskManager
from ..strategy import sessions, structure
from ..monitoring import notifier
from ..monitoring.journal import posisi_tertutup, sync_closed_trades
from ..strategy.setups import RuleEngine
from .manajemen_posisi import ParamPosisi, putuskan, skor_awal_dari_data
from .order_manager import OrderManager

ROOT = Path(__file__).resolve().parents[2]
STOP_FILE = ROOT / "STOP"
LOG_DIR = ROOT / "logs"
LOCK_FILE = LOG_DIR / "bot.lock"

TF_MAP = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
          "M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4}


class TradingBot:
    def __init__(
        self,
        config: Optional[dict] = None,
        breakeven_at_r: Optional[float] = None,
        trail_atr_mult: Optional[float] = None,
        min_score: int = 5,
        allowed_setups: Optional[tuple[str, ...]] = None,
        max_score: int = 99,
        variant: Optional[str] = None,
    ):
        base_cfg = config or load_config()

        # Varian (config/variants.yaml): satu nama -> kombinasi fitur +
        # magic number sendiri. variant=None berarti config dasar apa
        # adanya dengan magic bawaan - perilaku LAMA, tidak berubah.
        from ..variants import apply_risk_override, resolve as resolve_variant

        self.cfg, self._magic, self._variant_meta = resolve_variant(variant, base_cfg)
        self.variant_name = variant or "baseline"

        # Batas risiko juga bisa di-override per varian lewat `override_risk`
        # (mis. max_open_positions). Dipisah dari `override` karena
        # settings.yaml dan risk_limits.yaml adalah dua file berbeda.
        from ..risk.manager import load_risk_config
        risk_cfg = apply_risk_override(load_risk_config(), variant)

        # Parameter operasional dibaca dari config agar backtest dan live
        # memakai angka yang sama persis.
        self.gw = MT5Gateway(self.cfg)
        self.rules = RuleEngine(self.cfg)
        # Rem dihitung per MAGIC varian ini, bukan seluruh journal - lihat
        # catatan di RiskManager.__init__.
        self.risk = RiskManager(self.cfg, risk=risk_cfg, magic=self._magic)
        self.orders: Optional[OrderManager] = None

        # BE, trailing, auto-close, dan timeout. Logikanya di
        # manajemen_posisi.py, dipakai juga backtest/simulasi_live.py supaya
        # simulasi dan live memutuskan hal yang sama.
        self.param_posisi = ParamPosisi.dari_config(
            self.cfg, breakeven_at_r=breakeven_at_r, trail_atr_mult=trail_atr_mult
        )
        self.breakeven_at_r = self.param_posisi.breakeven_at_r
        self.trail_atr_mult = self.param_posisi.trail_atr_mult
        self.max_bars_hold = self.param_posisi.max_bars_hold
        self.autoclose_score_drop = self.param_posisi.autoclose_score_drop
        self.min_score = min_score
        self.max_score = max_score
        self.allowed_setups = tuple(
            allowed_setups or self.cfg.get("active_setups", ["momentum_fib"])
        )

        self.symbol = self.cfg["symbol"]["name"]
        self.point = self.cfg["symbol"]["point"]
        self.mode = self.cfg.get("mode", "OBSERVER")

        # Persetujuan eksplisit untuk berdagang di akun REAL. Disetel oleh
        # run_bot.py --allow-real; default False supaya akun real tidak
        # pernah tersentuh karena kelalaian.
        self.allow_real = False

        # Sidik jari konfigurasi sinyal, ditempelkan ke comment tiap order
        # agar forward test bisa dipisahkan per setelan. Lihat
        # src/config_fingerprint.py.
        self.cfg_hash = cfg_fingerprint(self.cfg, self.risk.risk, self.min_score)

        self._last_bar_time: Optional[pd.Timestamp] = None
        self._halt_notified = False
        self._entry_info: dict[int, dict] = {}  # ticket -> {entry, sl_dist, be_done}
        self._masalah: dict[str, tuple[str, float]] = {}  # sumber -> (pesan, waktu lapor)

        LOG_DIR.mkdir(exist_ok=True)
        self.log_path = LOG_DIR / f"bot_{datetime.now():%Y%m%d}.log"

    # -- util ------------------------------------------------------------

    def log(self, msg: str) -> None:
        line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
        print(line)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _teks_rem_rugi(self) -> str:
        """Teks rem rugi sesuai MODE YANG AKTIF.

        Sebelumnya log selalu mencetak "N/M loss beruntun" apa pun modenya.
        Pada varian ber-loss_mode "batch" itu menyesatkan: log menampilkan
        "6/3 loss beruntun" (terlihat seperti sudah lewat batas dan bot
        berhenti) padahal gerbang memakai penghitung BATCH yang saat itu
        baru 2/3 dan tetap mengizinkan entry. Angka yang dicetak harus
        angka yang benar-benar dipakai memutuskan.
        """
        st = self.risk.state
        if self.risk.loss_mode == "batch":
            return (
                f"{st.consecutive_loss_batches}/{self.risk.max_consec_loss_batches}"
                f" batch rugi ({st.consecutive_losses} posisi)"
            )
        return f"{st.consecutive_losses}/{self.risk.max_consec_losses} loss beruntun"

    def stop_requested(self) -> bool:
        return STOP_FILE.exists()

    def write_snapshot(self) -> None:
        """Tulis state ke JSON agar dashboard bisa membacanya tanpa
        membuka koneksi MT5 sendiri (API MT5 single-connection)."""
        import json

        acc = mt5.account_info()
        if acc is None:
            return

        positions = []
        for p in self.orders.get_positions() if self.orders else []:
            positions.append({
                "ticket": p.ticket,
                "type": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                "lot": p.volume,
                "entry": round(p.price_open, 3),
                "sl": round(p.sl, 3),
                "tp": round(p.tp, 3),
                "profit_idr": round(p.profit, 0),
            })

        snap = {
            "timestamp": datetime.now().isoformat(),
            "mode": self.mode,
            "symbol": self.symbol,
            "equity": acc.equity,
            "balance": acc.balance,
            "initial_equity": self.risk.state.peak_equity,
            "open_positions": len(positions),
            "positions": positions,
            "drawdown_pct": self.risk.current_drawdown_pct(acc.equity),
            "effective_risk_pct": self.risk.effective_risk_pct(acc.equity),
            "day_trades": self.risk.state.day_trades,
            "day_pnl": self.risk.state.day_pnl,
            "consecutive_losses": self.risk.state.consecutive_losses,
            "halted": self.risk.state.halted,
            "halt_reason": self.risk.state.halt_reason,
            "stop_file": self.stop_requested(),
        }
        try:
            with open(LOG_DIR / "snapshot.json", "w", encoding="utf-8") as f:
                json.dump(snap, f, indent=2)
        except OSError:
            pass

    # -- data ------------------------------------------------------------

    def _fetch(self, tf: str, n: int) -> pd.DataFrame:
        bars = mt5.copy_rates_from_pos(self.symbol, TF_MAP[tf], 0, n)
        if bars is None or len(bars) == 0:
            raise RuntimeError(f"gagal ambil {tf}: {mt5.last_error()}")
        df = pd.DataFrame(bars)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        # Offset dideteksi ULANG tiap panggilan, bukan dibaca dari config.
        # Server broker bisa bergeser (DST, migrasi) tanpa pemberitahuan;
        # offset statis membuat bot salah menghitung sesi dan diam padahal
        # seharusnya aktif.
        #
        # Sejak offset_server.PelacakOffset: nilai baru hanya dipakai bila
        # konsisten, supaya tick basi saat pasar jeda tidak menggeser jam.
        offset = detect_server_offset_hours()
        for pesan in ambil_pesan_offset():
            self.log(f"!! {pesan}")
        df["time_utc"] = df["time"] - pd.Timedelta(hours=offset)
        return df.drop(columns=["time"])

    def build_frame(self) -> pd.DataFrame:
        """Susun dataframe siap-analisis, sama persis dengan pipeline backtest."""
        base = self._fetch("M5", 1500)
        base = add_all(base)
        base = sessions.prepare(base)
        base = structure.add_structure(base)

        for tf, prefix in [("H1", "h1"), ("H4", "h4")]:
            ctx = build_htf_context(self._fetch(tf, 500), tf, prefix)
            base = pd.merge_asof(
                base.sort_values("time_utc"), ctx,
                left_on="time_utc", right_on="available_at", direction="backward",
            ).drop(columns=["available_at"])

        base["trend_htf"] = base["h1_trend"]
        opp = (
            ((base["h1_trend"] == "uptrend") & (base["h4_trend"] == "downtrend"))
            | ((base["h1_trend"] == "downtrend") & (base["h4_trend"] == "uptrend"))
        )
        base.loc[opp, "trend_htf"] = "ranging"
        flat = base["h1_trend"] == "ranging"
        base.loc[flat & (base["h1_close"] > base["h1_ema50"])
                 & (base["h4_trend"] != "downtrend"), "trend_htf"] = "uptrend"
        base.loc[flat & (base["h1_close"] < base["h1_ema50"])
                 & (base["h4_trend"] != "uptrend"), "trend_htf"] = "downtrend"

        base["htf_alignment"] = (
            (base["h1_trend"] == base["h4_trend"]).astype(int)
            + (base["trend"] == base["h1_trend"]).astype(int)
        ) / 2

        # Indikator lanjutan + ambang momentum. Harus identik dengan
        # pipeline backtest, jika tidak setup momentum_fib tak akan trigger.
        base = add_extended(base)
        base["mom_24_q85"] = (
            base["mom_24"].rolling(2000, min_periods=500).quantile(0.85).shift(1)
        )
        return base

    # -- manajemen posisi -------------------------------------------------

    def manage_positions(self, df: pd.DataFrame) -> None:
        """Terapkan keputusan manajemen_posisi.putuskan() ke posisi terbuka.

        Aturannya (BE, trailing, auto-close, timeout) sengaja tidak ditulis di
        sini lagi: backtest/simulasi_live.py memakai fungsi yang sama, jadi
        yang diukur simulasi adalah yang dijalankan bot.

        Catatan pengukuran auto-close yang dulu tertulis di sini (sapuan
        ambang 10-40 pada 1.440 trade, terbaik turun >=20: E[R] +0,2994 vs
        +0,2815 tanpa auto-close) TIDAK memodelkan bar berjalan yang dipakai
        bot. Ukuran ulang dengan cara live ada di docs/70.

        Timeout dihitung dari SELISIH WAKTU bar, bukan jumlah panggilan
        (DIPERBAIKI 15 Sep 2026 - dengan poll 3 detik penghitung per panggilan
        mencapai 48 "bar" dalam 2,4 menit).
        """
        last = df.iloc[-1]
        bar_tutup = df.iloc[-2] if len(df) > 1 else None

        for pos in self.orders.get_positions():
            info = self._entry_info.get(pos.ticket)
            if info is None:
                info = self._rekonstruksi_posisi(pos, df)
                self._entry_info[pos.ticket] = info
            info.setdefault("bar_entry", last["time_utc"])

            is_buy = pos.type == mt5.POSITION_TYPE_BUY
            k = putuskan(info, is_buy, pos.sl, last, bar_tutup, self.param_posisi)

            if k.sl_baru is not None:
                if k.be_baru:
                    info["be_done"] = True
                    self.log(f"  BE ticket {pos.ticket} -> SL {k.sl_baru:.3f}")
                if self.orders.modify_position(pos.ticket, k.sl_baru):
                    self.log(f"  SL ticket {pos.ticket} -> {k.sl_baru:.3f}")

            if k.tutup is None:
                continue
            res = self.orders.close_position(pos.ticket)
            if not res.success:
                continue
            if k.tutup == "autoclose":
                self.log(
                    f"  AUTOCLOSE ticket {pos.ticket}: skor {k.skor_awal}->{k.skor_kini} "
                    f"(turun {k.skor_awal - (k.skor_kini or 0)}, bar "
                    f"{self.param_posisi.autoclose_bar}) -> ditutup @ {res.price:.3f}"
                )
            else:
                self.log(
                    f"  TIMEOUT ticket {pos.ticket} setelah {k.umur_bar} bar "
                    f"-> ditutup @ {res.price:.3f}"
                )
            self._entry_info.pop(pos.ticket, None)

    def _rekonstruksi_posisi(self, pos, df: pd.DataFrame) -> dict:
        """State posisi yang dibuka sebelum bot di-restart.

        `bar_entry` diambil dari waktu buka milik broker, bukan bar sekarang;
        tanpa itu timeout terhitung ulang dari nol setiap restart.

        DIPERBAIKI: dulu `score100` tidak direkonstruksi, sehingga auto-close
        diam-diam MATI untuk setiap posisi yang melewati restart. Sekarang
        skor dihitung ulang dari bar sinyal di data yang sama. `be_done` juga
        dikenali dari SL yang sudah melewati harga entry.
        """
        is_buy = pos.type == mt5.POSITION_TYPE_BUY
        arah = "buy" if is_buy else "sell"
        waktu_entry = pd.Timestamp(pos.time, unit="s") - pd.Timedelta(
            hours=detect_server_offset_hours()
        )
        skor, bar_sinyal = skor_awal_dari_data(df, waktu_entry, arah)
        be_done = bool(pos.sl) and (
            (is_buy and pos.sl >= pos.price_open) or (not is_buy and pos.sl <= pos.price_open)
        )
        self.log(
            f"  posisi lama ticket {pos.ticket} direkonstruksi: skor awal "
            f"{skor if skor else 'tidak ditemukan (auto-close tidak berlaku)'}"
            f"{', SL sudah di titik impas' if be_done else ''}"
        )
        return {
            "entry": pos.price_open,
            "sl_dist": abs(pos.price_open - pos.sl) if pos.sl else df.iloc[-1]["atr"],
            "be_done": be_done,
            "bar_entry": bar_sinyal if bar_sinyal is not None else waktu_entry,
            "score100": skor,
        }

    # -- siklus -----------------------------------------------------------

    def _log_heartbeat(self, df: pd.DataFrame) -> None:
        """
        Laporan status berkala agar terlihat bot hidup dan sedang menunggu apa.

        Sinyal setup ini menggerombol: rata-rata 2,75/hari, tetapi jeda hingga
        19 hari tanpa sinyal pernah terjadi. Tanpa heartbeat, diamnya bot sulit
        dibedakan dari bot yang macet.
        """
        row = df.iloc[-1]
        wib = pd.Timestamp(row["time_utc"]) + pd.Timedelta(hours=7)

        if not row["is_trading_session"]:
            self.log(
                f"[status] {wib:%H:%M} WIB | sesi {row['session']} — "
                f"di luar jam trading, menunggu (london_ny 19:30, ny 23:00 WIB)"
            )
            return

        # Di dalam sesi: laporkan syarat mana yang belum terpenuhi
        kurang = []
        if pd.notna(row.get("atr_percentile")):
            # Ambang dibaca dari RuleEngine, BUKAN ditulis ulang di sini.
            #
            # DIPERBAIKI 10 Sep 2026: sebelumnya 0,30-0,85 di-hardcode,
            # padahal gate sesungguhnya sudah dilonggarkan ke 0,20-0,95.
            # Heartbeat jadi melaporkan "belum: ATR 0,25" untuk bar yang
            # sebenarnya LOLOS gate - hanya salah lapor, tidak memblokir
            # trade, tapi persis jenis kebohongan yang bikin pemilik ragu
            # apakah botnya jalan.
            if not (self.rules.atr_lo <= row["atr_percentile"] <= self.rules.atr_hi):
                kurang.append(
                    f"ATR {row['atr_percentile']:.2f} "
                    f"(butuh {self.rules.atr_lo:.2f}-{self.rules.atr_hi:.2f})"
                )
        # Arah dulu, lalu fib dan momentum dengan tanda dan ambang yang SAMA
        # dengan RuleEngine._momentum_fib.
        #
        # Ambang dibaca dari RuleEngine, bukan ditulis ulang di sini. Dulu
        # 0,75/0,25 di-hardcode, sehingga varian yang memakai ambang lain
        # (autoclose_agresif & pyramid5 memakai 0,70/0,30) melaporkan angka
        # yang SALAH - terlihat seperti sinyal ditolak oleh ambang yang
        # sebenarnya tidak berlaku (756b13c).
        #
        # Momentum juga dulu hanya diuji untuk sisi buy dan dibandingkan
        # dengan ambang PENUH, padahal gerbangnya menerima tier reduced di
        # atas 50% ambang - kondisi sell tidak pernah terlaporkan benar.
        tren = row.get("trend_htf")
        if tren not in ("uptrend", "downtrend"):
            kurang.append(f"HTF {tren}")
        elif tren == "downtrend" and not self.rules.allow_sell:
            kurang.append("HTF downtrend (sell tidak aktif)")
        else:
            is_buy = tren == "uptrend"
            fp = row.get("fib_position")
            if pd.notna(fp):
                if is_buy and fp <= self.rules.fib_buy_min:
                    kurang.append(f"fib {fp:.2f}<={self.rules.fib_buy_min:.2f}")
                elif not is_buy and fp >= self.rules.fib_sell_max:
                    kurang.append(f"fib {fp:.2f}>={self.rules.fib_sell_max:.2f}")
            mom, q = row.get("mom_24"), row.get("mom_24_q85")
            if pd.notna(mom) and pd.notna(q):
                mom_arah = mom if is_buy else -mom
                if mom_arah <= 0.5 * q:
                    kurang.append(
                        f"momentum {'naik' if is_buy else 'turun'} "
                        f"({mom_arah:.1f}<={0.5 * q:.1f})"
                    )

        if kurang:
            self.log(
                f"[status] {wib:%H:%M} WIB | sesi {row['session']} AKTIF — "
                f"belum: {', '.join(kurang)}"
            )
        else:
            self.log(f"[status] {wib:%H:%M} WIB | sesi {row['session']} — semua syarat OK")

    HB_TELEGRAM_JAM = 4          # kirim ringkasan tiap 4 jam

    def _heartbeat_telegram(self, df) -> None:
        """
        Kabar berkala ke Telegram supaya KESENYAPAN bisa dibaca sebagai
        masalah.

        Kejadian nyata 11 Sep 2026: PC kantor macet, bot baru dinyalakan
        ulang jam 15:37 WIB, dan 11 trade hari itu (5 di antaranya TP)
        terlewat begitu saja. Tidak ada yang memberi tahu.

        Prinsipnya dibalik: selama pesan datang tiap beberapa jam, sistem
        hidup. Begitu berhenti, ada yang salah - dan itu terbaca dalam
        hitungan menit, bukan jam.

        Gagal kirim TIDAK pernah menghentikan bot.
        """
        try:
            import time as _t
            sekarang = _t.time()
            if sekarang - getattr(self, "_hb_tg_terakhir", 0.0) < self.HB_TELEGRAM_JAM * 3600:
                return
            self._hb_tg_terakhir = sekarang

            acc = mt5.account_info()
            equity = acc.equity if acc else 0.0
            n_pos = len(self.orders.get_positions()) if self.orders else 0
            st = self.risk.state
            baris = df.iloc[-1]
            wib = pd.Timestamp(baris["time_utc"]) + pd.Timedelta(hours=7)

            pesan = [
                f"AI-TRADE hidup | {wib:%d %b %H:%M} WIB",
                f"cfg {self.cfg_hash} | {self.mode} | {self.symbol}",
                f"equity Rp {equity:,.0f} "
                f"(DD {self.risk.current_drawdown_pct(equity):.1f}%)",
                f"hari ini {st.day_trades}/{self.risk.max_daily_trades} trade, "
                f"P/L Rp {st.day_pnl:,.0f}",
                f"posisi terbuka {n_pos} | sesi {baris.get('session', '?')}",
            ]
            if st.halted:
                pesan.append(f"HALT: {st.halt_reason}")
            notifier.send(chr(10).join(pesan))
        except Exception:  # noqa: BLE001
            pass

    MASALAH_ULANG_DETIK = 3600

    def _lapor_masalah(self, sumber: str, err: Exception) -> None:
        """Log + Telegram untuk kegagalan yang dulu ditelan diam-diam.

        Dibatasi sekali per jam per sumber (atau saat pesannya berubah) supaya
        polling 3 detik tidak membanjiri log dan Telegram.
        """
        pesan = f"{type(err).__name__}: {err}"
        sekarang = time.time()
        lama = self._masalah.get(sumber)
        if lama and lama[0] == pesan and sekarang - lama[1] < self.MASALAH_ULANG_DETIK:
            return
        self._masalah[sumber] = (pesan, sekarang)
        self.log(f"!! {sumber} gagal: {pesan}")
        try:
            notifier.send(f"⚠️ {sumber} gagal\n{pesan}")
        except Exception:  # noqa: BLE001
            pass

    def _pulih(self, sumber: str) -> None:
        if self._masalah.pop(sumber, None):
            self.log(f"{sumber} pulih kembali.")

    def _sinkron_rem_dan_journal(self) -> None:
        """
        Rem risiko dari riwayat MT5 LANGSUNG; logs/trades.csv hanya catatan.

        DIPERBAIKI: dulu rem hanya diperbarui SETELAH trade baru berhasil
        ditulis ke logs/trades.csv, dan semua error di jalur itu ditelan
        (`except Exception: pass`). Kalau penulisan CSV gagal - mis. file
        sedang dibuka Excel - rem buta tanpa jejak: loss baru tidak pernah
        dihitung. 14 Sep 2026 bot live tetap entry setelah 4 SL beruntun
        padahal rem 3-loss sudah ada di kodenya; penyebab pastinya tidak bisa
        dipastikan tanpa log PC itu, tetapi jalur ini salah satu yang cocok.

        Sekarang: riwayat MT5 dibaca tiap siklus (seperti sebelumnya), rem
        dihitung dari situ, lalu CSV ditulis. Gagal baca riwayat -> counter
        rem lama dipertahankan. Gagal apa pun -> dilaporkan.
        """
        sumber_mt5, sumber_csv = "baca riwayat deal MT5", "tulis logs/trades.csv"
        try:
            baris = posisi_tertutup(days_back=7, config=self.cfg)
            if baris is None:
                raise RuntimeError(f"history_deals_get None: {mt5.last_error()}")
        except Exception as e:  # noqa: BLE001
            self._lapor_masalah(sumber_mt5, e)
            return
        self._pulih(sumber_mt5)
        self.risk.refresh_from_journal(datetime.now(), trades=baris)

        try:
            n = sync_closed_trades(days_back=7, config=self.cfg, rows=baris)
        except Exception as e:  # noqa: BLE001
            self._lapor_masalah(sumber_csv, e)
            return
        self._pulih(sumber_csv)
        if n:
            self.log(f"Journal: {n} trade baru dicatat")
            self.log(
                f"  Rem: {self.risk.state.day_trades}/{self.risk.max_daily_trades} trade"
                f" | P/L Rp {self.risk.state.day_pnl:,.0f}"
                f" | {self._teks_rem_rugi()}"
            )

    def process_bar(self, df: pd.DataFrame) -> None:
        # manage_positions() TIDAK dipanggil di sini lagi - sudah dijalankan
        # tiap siklus di run(), bukan hanya saat bar berganti. Lihat catatan
        # bug trailing di run().

        # Heartbeat tiap 12 bar M5 (1 jam) ke log, dan tiap HB_TELEGRAM_JAM
        # ke Telegram.
        #
        # Heartbeat Telegram bukan kenyamanan - ia mengubah "bot mati" dari
        # sesuatu yang baru ketahuan berjam-jam kemudian menjadi sesuatu yang
        # ketahuan dalam hitungan menit. Kejadian nyata 11 Sep 2026: PC macet,
        # bot baru dinyalakan ulang jam 15:37, dan 11 trade (5 di antaranya TP)
        # terlewat begitu saja.
        #
        # Prinsipnya dibalik: SENYAP berarti masalah. Selama pesan datang
        # tiap beberapa jam, sistem hidup. Begitu berhenti, ada yang salah.
        self._bar_count = getattr(self, "_bar_count", 0) + 1
        if self._bar_count % 12 == 1:
            self._log_heartbeat(df)
            self._heartbeat_telegram(df)

        if self.stop_requested():
            self.log("File STOP terdeteksi — tidak ada entry baru.")
            return

        # Bar terakhir mungkin belum selesai; pakai bar sebelum itu.
        closed = df.iloc[:-1]
        signals = self.rules.generate(closed.tail(3), min_score=self.min_score)
        if signals.empty:
            return

        sig = signals.iloc[-1]
        if sig["setup"] not in self.allowed_setups or sig["score"] > self.max_score:
            return

        # Hanya proses sinyal dari bar yang baru saja selesai
        if sig["time"] != closed.iloc[-1]["time_utc"]:
            return

        acc = mt5.account_info()
        info = mt5.symbol_info(self.symbol)
        if acc is None or info is None:
            self.log("Info akun/simbol tidak tersedia — lewati.")
            return

        # Keyakinan sinyal, dinormalisasi ke 0..1 dari skor konfluensi.
        # Hanya berpengaruh bila adaptive_sizing diaktifkan di
        # risk_limits.yaml (default nonaktif — lihat alasannya di sana).
        confidence = min(1.0, sig["score"] / 10.0)

        # Arah posisi yang sedang terbuka — dipakai gerbang "hanya searah".
        posisi_terbuka = self.orders.get_positions()
        arah_terbuka = [
            "buy" if p.type == mt5.POSITION_TYPE_BUY else "sell"
            for p in posisi_terbuka
        ]

        decision = self.risk.check(
            now=datetime.now(),
            equity=acc.equity,
            sl_points=sig["sl_points"],
            tp_points=sig["tp_points"],
            spread_points=info.spread,
            open_positions=len(posisi_terbuka),
            stop_file_exists=self.stop_requested(),
            confidence=confidence,
            size_tier=sig.get("size_tier", "full"),
            direction=sig["direction"],
            open_directions=arah_terbuka,
            # Untuk gerbang jarak antar entry (pyramiding). Dibandingkan
            # dengan harga buka posisi yang sudah ada.
            atr=float(sig["atr"]),
            harga=float(sig["entry"]),
            harga_posisi=[p.price_open for p in posisi_terbuka],
        )

        if not decision.allowed:
            self.log(f"SINYAL {sig['direction']} {sig['setup']} DITOLAK: {decision.reason}")
            if self.risk.state.halted and not self._halt_notified:
                self._halt_notified = True
                notifier.notify_halt(self.risk.state.halt_reason)
            return

        notifier.notify_signal(
            sig['direction'], sig['setup'], sig.get('size_tier', 'full'),
            decision.lot, sig['sl'], sig['tp'],
        )
        self.log(
            f"SINYAL {sig['direction'].upper()} {sig['setup']} "
            f"tier={sig.get('size_tier','full')} skor={sig['score']} "
            f"| lot={decision.lot} risiko={decision.risk_pct:.2f}% "
            f"(conf {confidence:.2f}, x{self.risk.confidence_multiplier(confidence):.1f}) "
            f"| SL={sig['sl']:.3f} TP={sig['tp']:.3f}"
        )

        if self.mode != "EXECUTOR":
            self.log(f"  mode {self.mode} — tidak dieksekusi (ADVISOR/OBSERVER)")
            return

        result = self.orders.open_position(
            direction=sig["direction"],
            lot=decision.lot,
            sl=sig["sl"],
            tp=sig["tp"],
            comment=f"{sig['setup']}_{sig['score']}_{self.cfg_hash}",
        )

        notifier.notify_order_result(result.success, result.ticket, result.price, result.comment)
        if result.success:
            self.risk.record_order_success()
            self._entry_info[result.ticket] = {
                "entry": result.price,
                "sl_dist": abs(result.price - sig["sl"]),
                "be_done": False,
                # Waktu bar saat entry - dasar penghitungan timeout.
                "bar_entry": sig["time"],
                # Skor keyakinan saat dibuka, dasar pembanding auto-close.
                "score100": int(sig.get("score100", 0)),
            }
            self.log(f"  ORDER OK ticket={result.ticket} @ {result.price:.3f}")
        else:
            self.log(f"  ORDER GAGAL: {result.comment}")
            if self.risk.record_order_failure():
                self.log("  !! Terlalu banyak kegagalan — sistem dihentikan.")
                notifier.notify_halt("Terlalu banyak order gagal beruntun")

    def _acquire_lock(self) -> bool:
        """
        Cegah dua bot berjalan bersamaan.

        API MetaTrader5 hanya mengizinkan SATU koneksi per proses ke satu
        terminal. Dua bot yang berjalan bersamaan akan saling mengganggu:
        order bisa dikirim dua kali, atau koneksi salah satunya gagal
        dengan cara yang sulit didiagnosis.
        """
        import os

        import socket

        host = socket.gethostname()
        LOG_DIR.mkdir(exist_ok=True)
        if LOCK_FILE.exists():
            raw = ""
            try:
                raw = LOCK_FILE.read_text().strip()
            except OSError:
                raw = ""

            # Format lock: "<host> <pid>". Format lama (hanya pid) tetap
            # dibaca supaya lock lama tidak bikin bot gagal start.
            parts = raw.split()
            lock_host = parts[0] if len(parts) == 2 else host
            try:
                pid = int(parts[-1]) if parts else None
            except ValueError:
                pid = None

            # Lock dari MESIN LAIN tidak boleh diambil alih.
            #
            # tasklist hanya melihat proses di mesin ini, jadi PID milik PC
            # lain selalu tampak "mati" dan lock-nya dirampas. Kalau logs/
            # ter-share (OneDrive, network drive), dua bot bisa jalan
            # bersamaan di akun yang sama: order dobel, dan max_open_positions
            # jebol karena keduanya membaca "belum ada posisi" berbarengan.
            if lock_host != host:
                self.log(f"!! Lock dipegang mesin lain: {lock_host} (PID {pid}).")
                self.log("!! Jalankan bot hanya di SATU PC per akun MT5.")
                self.log(f"!! Bila {lock_host} sudah pasti mati, hapus logs/bot.lock")
                return False

            if pid and pid != os.getpid():
                # Cek apakah proses itu masih hidup
                alive = False
                try:
                    import subprocess
                    out = subprocess.run(
                        ["tasklist", "/FI", f"PID eq {pid}"],
                        capture_output=True, text=True, timeout=10,
                    ).stdout
                    alive = str(pid) in out
                except Exception:  # noqa: BLE001
                    alive = True  # tidak bisa memastikan -> anggap hidup

                if alive:
                    self.log(f"!! Bot lain sudah berjalan (PID {pid}).")
                    self.log("!! Hentikan bot itu dulu, atau hapus logs/bot.lock")
                    return False

        LOCK_FILE.write_text(f"{host} {os.getpid()}")
        return True

    def _release_lock(self) -> None:
        try:
            if LOCK_FILE.exists():
                LOCK_FILE.unlink()
        except OSError:
            pass

    def run(self, poll_seconds: int = 10) -> None:
        if not self._acquire_lock():
            return

        self.gw.connect()
        self.orders = OrderManager(self.gw, magic=self._magic)

        acc = mt5.account_info()
        is_demo = acc.trade_mode == 0

        self.log("=" * 58)
        self.log(f"BOT START — mode {self.mode} — VARIAN: {self.variant_name}")
        self.log(f"Akun {acc.login} @ {acc.server} ({'DEMO' if is_demo else 'REAL'})")
        self.log(f"Equity Rp {acc.equity:,.0f} | simbol {self.symbol}")
        self.log(f"Setup: {self.allowed_setups} skor {self.min_score}-{self.max_score}")
        self.log(f"Konfigurasi sinyal: {cfg_describe(self.cfg, self.risk.risk, self.min_score)}")
        self.log("=" * 58)

        if self.mode == "EXECUTOR" and not is_demo:
            # DIPERKETAT 10 Sep 2026: dulu hanya time.sleep(10) lalu LANJUT
            # trading. Kalau terminal tidak diawasi selama 10 detik, bot
            # langsung berdagang dengan uang sungguhan tanpa satu pun
            # persetujuan eksplisit. Sekarang berhenti, dan butuh flag
            # --allow-real yang disengaja.
            self.log("!! AKUN REAL terdeteksi di mode EXECUTOR.")
            self.log("!! Basis bukti strategi ini belum memenuhi ambang untuk uang")
            self.log("!! sungguhan (t=2,25 dari 22 kombinasi; negatif di M15).")
            self.log("!! Lihat docs/28-HASIL-KALIBRASI-ULANG.md bagian 4.")
            if not self.allow_real:
                self.log("!! DIHENTIKAN. Jalankan dengan --allow-real bila memang disengaja.")
                self._release_lock()
                self.gw.disconnect()
                raise SystemExit(1)
            self.log("!! --allow-real aktif — melanjutkan ke akun REAL dalam 10 detik.")
            time.sleep(10)

        if not self.gw.is_trade_allowed():
            self.log("!! Algo trading tidak diizinkan di terminal — order akan gagal.")

        # Pulihkan state yang harus bertahan lintas restart.
        #
        # Sebelumnya baris ini menyetel peak_equity = equity saat ini, yang
        # membuat drawdown selalu terbaca 0% setiap kali bot di-restart —
        # sehingga kill switch global dan seluruh tangga derisking tidak
        # pernah bisa menyala. Counter harian direkonsiliasi dari journal,
        # bukan dimulai ulang dari nol.
        self.risk.load_state()
        self.risk.state.peak_equity = max(self.risk.state.peak_equity, acc.equity)
        self.risk.refresh_from_journal(datetime.now())   # cadangan: CSV
        self._sinkron_rem_dan_journal()                  # sumber utama: riwayat MT5
        self.risk.save_state()

        # Kabari bahwa bot benar-benar mulai. Bersama heartbeat berkala dan
        # notifikasi saat berhenti, ini membuat status bot terbaca dari HP
        # tanpa perlu remote ke PC.
        try:
            notifier.send(
                chr(10).join([
                    f"AI-TRADE START | {datetime.now():%d %b %H:%M} WIB",
                    f"cfg {self.cfg_hash} | {self.mode} | {self.symbol}",
                    f"akun {acc.login} ({'DEMO' if is_demo else 'REAL'})",
                    f"equity Rp {acc.equity:,.0f}",
                ])
            )
        except Exception:  # noqa: BLE001
            pass

        if self.risk.state.halted:
            self.log(f"!! Sistem dalam status HALT: {self.risk.state.halt_reason}")
            self.log("!! Tidak ada entry baru sampai logs/risk_state.json di-reset manual.")

        self.log(
            f"Rem hari ini: {self.risk.state.day_trades}/{self.risk.max_daily_trades} trade"
            f" | P/L Rp {self.risk.state.day_pnl:,.0f}"
            f" | {self._teks_rem_rugi()}"
            f" | puncak equity Rp {self.risk.state.peak_equity:,.0f}"
            f" (DD {self.risk.current_drawdown_pct(acc.equity):.1f}%)"
        )

        # Status koneksi. down_since != None berarti sedang putus; backoff
        # naik bertingkat supaya tidak membanjiri terminal yang sedang sakit.
        down_since: Optional[float] = None
        down_notified = False
        backoff = poll_seconds
        disconnect_limit = self.cfg.get("circuit_breaker", {}).get(
            "mt5_disconnect_seconds",
            self.risk.risk.get("circuit_breaker", {}).get("mt5_disconnect_seconds", 30),
        )

        try:
            while True:
                if self.stop_requested():
                    self.log("File STOP ada — bot idle, tidak membuka posisi baru.")

                try:
                    df = self.build_frame()
                    bar_time = df.iloc[-1]["time_utc"]

                    # MANAJEMEN POSISI DIJALANKAN TIAP SIKLUS, bukan hanya
                    # saat bar M5 berganti.
                    #
                    # BUG YANG DIPERBAIKI (15 Sep 2026): manage_positions()
                    # dulu hanya dipanggil dari dalam process_bar(), yang
                    # sendiri hanya jalan saat bar M5 baru terbentuk.
                    # Akibatnya trailing stop cuma dicek SEKALI PER 5 MENIT
                    # meski bot polling tiap beberapa detik.
                    #
                    # Dampaknya terukur di backtest: dari trade yang harganya
                    # sempat melewati ambang trailing 2,4R, hanya 11 dari 63
                    # yang terdeteksi - 52 sisanya menyentuh ambang di tengah
                    # bar lalu berbalik sebelum bar tutup, sehingga trailing
                    # tidak pernah aktif dan posisi rugi penuh (Rp 6,99 juta).
                    #
                    # Sinyal TETAP dievaluasi per bar selesai (process_bar),
                    # karena indikator hanya sahih pada bar yang sudah tutup.
                    # Yang dipindah ke sini hanya manajemen posisi terbuka.
                    if self.orders is not None:
                        self.manage_positions(df)

                    if bar_time != self._last_bar_time:
                        self._last_bar_time = bar_time
                        self.process_bar(df)

                    # Puncak equity diperbarui tiap siklus, bukan hanya saat
                    # ada sinyal — drawdown yang terjadi selama bot tidak
                    # menemukan setup tetap harus tercatat.
                    acc_now = mt5.account_info()
                    if acc_now is not None:
                        self.risk.observe_equity(acc_now.equity)

                    self.write_snapshot()

                    # Rem risiko + journal dari riwayat MT5 (tahan restart,
                    # dan kegagalannya dilaporkan - lihat method-nya).
                    self._sinkron_rem_dan_journal()

                    self.risk.save_state()

                except Exception as e:  # noqa: BLE001
                    # JANGAN biarkan reconnect mematikan bot.
                    #
                    # DIPERBAIKI 10 Sep 2026: ensure_connected() melempar
                    # ulang ConnectionError bila percobaan terakhir gagal.
                    # Karena dipanggil di dalam blok except tanpa pelindung,
                    # lemparan itu keluar dari try dan mematikan proses.
                    # MT5 tersendat beberapa detik (restart terminal, Wi-Fi
                    # putus, update broker) sudah cukup untuk membunuh bot,
                    # meninggalkan posisi terbuka tanpa trailing, tanpa
                    # break-even, dan tanpa max_bars_hold.
                    #
                    # Posisi terbuka justru MEMBUTUHKAN bot tetap hidup,
                    # jadi loop harus bertahan dan terus mencoba.
                    self.log(f"ERROR siklus: {type(e).__name__}: {e}")
                    try:
                        self.gw.ensure_connected()
                        if down_since is not None:
                            gone = time.time() - down_since
                            self.log(f"Koneksi pulih setelah {gone:.0f} detik.")
                            notifier.notify_halt(
                                f"Koneksi MT5 pulih setelah {gone:.0f} detik"
                            )
                            down_since = None
                            down_notified = False
                        backoff = poll_seconds
                    except Exception as ce:  # noqa: BLE001
                        if down_since is None:
                            down_since = time.time()
                        gone = time.time() - down_since

                        # Ambang dari config circuit_breaker: beri tahu,
                        # tapi JANGAN matikan bot.
                        if not down_notified and gone >= disconnect_limit:
                            down_notified = True
                            self.log(
                                f"!! Koneksi MT5 putus {gone:.0f}s "
                                f"(ambang {disconnect_limit}s)."
                            )
                            try:
                                notifier.notify_halt(
                                    f"Koneksi MT5 putus {gone:.0f} detik. "
                                    "Bot masih hidup dan terus mencoba."
                                )
                            except Exception:  # noqa: BLE001
                                pass

                        backoff = min(backoff * 2 if backoff else poll_seconds, 60)
                        self.log(
                            f"Reconnect gagal ({type(ce).__name__}). "
                            f"Coba lagi dalam {backoff}s."
                        )

                time.sleep(backoff)

        except KeyboardInterrupt:
            self.log("Dihentikan oleh pengguna.")
        finally:
            # Jangan laporkan "0 posisi" ketika sebenarnya kita tidak bisa
            # membacanya. Bot yang berhenti saat koneksi mati dulu selalu
            # mencetak 0, membuat posisi yang masih terbuka tak terlihat.
            try:
                n_open = len(self.orders.get_positions()) if self.orders else None
            except Exception:  # noqa: BLE001
                n_open = None

            if n_open is None:
                self.log("Posisi terbuka saat berhenti: TIDAK DIKETAHUI "
                         "(koneksi MT5 tidak terbaca) — periksa terminal manual.")
            else:
                self.log(f"Posisi terbuka saat berhenti: {n_open}")
                if n_open:
                    self.log("!! Posisi masih terbuka tanpa bot yang mengelolanya.")
                    self.log("!! Trailing dan max_bars_hold TIDAK aktif; "
                             "hanya SL/TP di server yang melindungi.")

            try:
                notifier.notify_halt(
                    f"Bot BERHENTI. Posisi terbuka: "
                    f"{'tidak diketahui' if n_open is None else n_open}"
                )
            except Exception:  # noqa: BLE001
                pass

            self.gw.disconnect()
            self._release_lock()


if __name__ == "__main__":
    TradingBot().run()
