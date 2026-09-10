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

from ..data.mt5_gateway import MT5Gateway, detect_server_offset_hours, load_config
from ..features.indicators import add_all, add_extended
from ..features.pipeline import build_htf_context
from ..risk.manager import RiskManager
from ..strategy import sessions, structure
from ..monitoring import notifier
from ..monitoring.journal import sync_closed_trades
from ..strategy.setups import RuleEngine
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
    ):
        self.cfg = config or load_config()

        # Parameter operasional dibaca dari config agar backtest dan live
        # memakai angka yang sama persis.
        pm = self.cfg.get("position_management", {})
        self.gw = MT5Gateway(self.cfg)
        self.rules = RuleEngine(self.cfg)
        self.risk = RiskManager(self.cfg)
        self.orders: Optional[OrderManager] = None

        self.breakeven_at_r = (
            breakeven_at_r if breakeven_at_r is not None else pm.get("breakeven_at_r", 1.5)
        )
        self.trail_atr_mult = (
            trail_atr_mult if trail_atr_mult is not None else pm.get("trail_atr_mult", 2.5)
        )
        self.max_bars_hold = pm.get("max_bars_hold", 48)
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

        self._last_bar_time: Optional[pd.Timestamp] = None
        self._halt_notified = False
        self._entry_info: dict[int, dict] = {}  # ticket -> {entry, sl_dist, be_done}

        LOG_DIR.mkdir(exist_ok=True)
        self.log_path = LOG_DIR / f"bot_{datetime.now():%Y%m%d}.log"

    # -- util ------------------------------------------------------------

    def log(self, msg: str) -> None:
        line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
        print(line)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

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
        offset = detect_server_offset_hours()
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
        """Break-even dan trailing stop untuk posisi terbuka."""
        last = df.iloc[-1]
        atr_now = last["atr"]
        if pd.isna(atr_now) or atr_now <= 0:
            return

        for pos in self.orders.get_positions():
            info = self._entry_info.get(pos.ticket)
            if info is None:
                # Posisi dari sesi sebelumnya — rekonstruksi dari data broker
                info = {
                    "entry": pos.price_open,
                    "sl_dist": abs(pos.price_open - pos.sl) if pos.sl else atr_now,
                    "be_done": False,
                }
                self._entry_info[pos.ticket] = info

            is_buy = pos.type == mt5.POSITION_TYPE_BUY
            price = last["close"]
            r_dist = info["sl_dist"]
            profit_dist = (price - info["entry"]) if is_buy else (info["entry"] - price)

            new_sl = None

            if not info["be_done"] and profit_dist >= r_dist * self.breakeven_at_r:
                spread_buf = self.cfg["costs"]["spread_points"] * self.point
                new_sl = info["entry"] + spread_buf if is_buy else info["entry"] - spread_buf
                info["be_done"] = True
                self.log(f"  BE ticket {pos.ticket} -> SL {new_sl:.3f}")

            elif info["be_done"]:
                trail = (price - atr_now * self.trail_atr_mult) if is_buy else (
                    price + atr_now * self.trail_atr_mult
                )
                if (is_buy and trail > pos.sl) or (not is_buy and trail < pos.sl):
                    new_sl = trail

            if new_sl is not None:
                if self.orders.modify_position(pos.ticket, new_sl):
                    self.log(f"  SL ticket {pos.ticket} -> {new_sl:.3f}")

            # Timeout: tutup posisi yang ditahan melebihi batas.
            # Backtest memakai batas yang sama, jadi live harus konsisten.
            bars_held = info.setdefault("bars", 0)
            info["bars"] = bars_held + 1
            if info["bars"] > self.max_bars_hold:
                res = self.orders.close_position(pos.ticket)
                if res.success:
                    self.log(
                        f"  TIMEOUT ticket {pos.ticket} setelah "
                        f"{info['bars']} bar -> ditutup @ {res.price:.3f}"
                    )
                    self._entry_info.pop(pos.ticket, None)

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
        if pd.notna(row.get("mom_24")) and pd.notna(row.get("mom_24_q85")):
            if row["mom_24"] <= row["mom_24_q85"]:
                kurang.append(f"momentum ({row['mom_24']:.1f}<{row['mom_24_q85']:.1f})")
        if pd.notna(row.get("atr_percentile")):
            if not (0.30 <= row["atr_percentile"] <= 0.85):
                kurang.append(f"ATR {row['atr_percentile']:.2f}")
        if row.get("trend_htf") == "ranging":
            kurang.append("HTF ranging")
        elif pd.notna(row.get("fib_position")):
            fp = row["fib_position"]
            if row["trend_htf"] == "uptrend" and fp <= 0.75:
                kurang.append(f"fib {fp:.2f}<0.75")
            elif row["trend_htf"] == "downtrend" and fp >= 0.25:
                kurang.append(f"fib {fp:.2f}>0.25")

        if kurang:
            self.log(
                f"[status] {wib:%H:%M} WIB | sesi {row['session']} AKTIF — "
                f"belum: {', '.join(kurang)}"
            )
        else:
            self.log(f"[status] {wib:%H:%M} WIB | sesi {row['session']} — semua syarat OK")

    def process_bar(self, df: pd.DataFrame) -> None:
        self.manage_positions(df)

        # Heartbeat tiap 12 bar M5 (1 jam)
        self._bar_count = getattr(self, "_bar_count", 0) + 1
        if self._bar_count % 12 == 1:
            self._log_heartbeat(df)

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

        decision = self.risk.check(
            now=datetime.now(),
            equity=acc.equity,
            sl_points=sig["sl_points"],
            tp_points=sig["tp_points"],
            spread_points=info.spread,
            open_positions=len(self.orders.get_positions()),
            stop_file_exists=self.stop_requested(),
            confidence=confidence,
            size_tier=sig.get("size_tier", "full"),
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
            comment=f"{sig['setup']}_{sig['score']}",
        )

        notifier.notify_order_result(result.success, result.ticket, result.price, result.comment)
        if result.success:
            self.risk.record_order_success()
            self._entry_info[result.ticket] = {
                "entry": result.price,
                "sl_dist": abs(result.price - sig["sl"]),
                "be_done": False,
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
        self.orders = OrderManager(self.gw)

        acc = mt5.account_info()
        is_demo = acc.trade_mode == 0

        self.log("=" * 58)
        self.log(f"BOT START — mode {self.mode}")
        self.log(f"Akun {acc.login} @ {acc.server} ({'DEMO' if is_demo else 'REAL'})")
        self.log(f"Equity Rp {acc.equity:,.0f} | simbol {self.symbol}")
        self.log(f"Setup: {self.allowed_setups} skor {self.min_score}-{self.max_score}")
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
        self.risk.refresh_from_journal(datetime.now())
        self.risk.save_state()

        if self.risk.state.halted:
            self.log(f"!! Sistem dalam status HALT: {self.risk.state.halt_reason}")
            self.log("!! Tidak ada entry baru sampai logs/risk_state.json di-reset manual.")

        self.log(
            f"Rem hari ini: {self.risk.state.day_trades}/{self.risk.max_daily_trades} trade"
            f" | P/L Rp {self.risk.state.day_pnl:,.0f}"
            f" | {self.risk.state.consecutive_losses}/{self.risk.max_consec_losses} loss beruntun"
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

                    # Catat trade yang baru tertutup ke journal.
                    # Sumbernya riwayat MT5, bukan state internal - tahan
                    # terhadap restart atau crash.
                    try:
                        # config dioper agar journal bisa menghitung
                        # r_multiple dari lot + jarak SL tiap posisi.
                        # Tanpa kolom itu hasil live tidak bisa
                        # dibandingkan dengan expectancy backtest.
                        n = sync_closed_trades(days_back=7, config=self.cfg)
                        if n:
                            self.log(f"Journal: {n} trade baru dicatat")
                            # Rekonsiliasi rem risiko dari journal yang baru
                            # diperbarui. Tanpa langkah ini batas harian,
                            # mingguan, dan loss beruntun tidak pernah terisi.
                            self.risk.refresh_from_journal(datetime.now())
                            self.log(
                                f"  Rem: {self.risk.state.day_trades}/{self.risk.max_daily_trades} trade"
                                f" | P/L Rp {self.risk.state.day_pnl:,.0f}"
                                f" | {self.risk.state.consecutive_losses}/{self.risk.max_consec_losses}"
                                " loss beruntun"
                            )
                    except Exception:  # noqa: BLE001
                        pass

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
