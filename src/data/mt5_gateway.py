"""
Gateway MT5 — satu-satunya titik koneksi ke terminal.

Paket MetaTrader5 tidak thread-safe dan hanya mengizinkan satu koneksi
per proses. Semua akses ke MT5 harus lewat modul ini; jangan panggil
mt5.initialize() di tempat lain (termasuk dashboard).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import MetaTrader5 as mt5
import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "settings.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class MT5Gateway:
    """Koneksi tunggal ke terminal MT5, dengan verifikasi dan reconnect."""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or load_config()
        self.symbol = self.config["symbol"]["name"]
        self._connected = False

    # -- koneksi ---------------------------------------------------------

    def connect(self) -> bool:
        if self._connected and mt5.terminal_info() is not None:
            return True

        if not mt5.initialize():
            code, desc = mt5.last_error()
            raise ConnectionError(
                f"Gagal connect ke MT5: ({code}) {desc}. "
                "Pastikan terminal terbuka dan sudah login."
            )

        if not mt5.symbol_select(self.symbol, True):
            mt5.shutdown()
            raise ConnectionError(f"Simbol {self.symbol} tidak tersedia di server ini.")

        self._verify_symbol_matches_config()
        self._connected = True
        return True

    def _verify_symbol_matches_config(self) -> None:
        """
        Pastikan spesifikasi broker masih sama dengan yang tercatat di config.

        Broker bisa mengubah spesifikasi kontrak tanpa pemberitahuan. Kalau
        itu terjadi, position sizing yang memakai angka lama akan salah —
        lebih baik berhenti daripada menghitung lot dengan asumsi keliru.
        """
        info = mt5.symbol_info(self.symbol)
        if info is None:
            raise ConnectionError(f"symbol_info({self.symbol}) mengembalikan None.")

        cfg = self.config["symbol"]
        checks = [
            ("digits", info.digits, cfg["digits"]),
            ("point", info.point, cfg["point"]),
            ("volume_min", info.volume_min, cfg["volume_min"]),
            ("volume_step", info.volume_step, cfg["volume_step"]),
            ("contract_size", info.trade_contract_size, cfg["contract_size"]),
        ]
        for name, actual, expected in checks:
            if abs(float(actual) - float(expected)) > 1e-9:
                raise ValueError(
                    f"Spesifikasi broker berubah: {name} sekarang {actual}, "
                    f"config mencatat {expected}. Jalankan ulang "
                    f"scripts/phase0_probe.py dan perbarui config sebelum lanjut."
                )

    def disconnect(self) -> None:
        if self._connected:
            mt5.shutdown()
            self._connected = False

    def ensure_connected(self, retries: int = 3, delay: float = 2.0) -> bool:
        """Reconnect jika koneksi putus. Dipakai oleh loop live."""
        for attempt in range(retries):
            try:
                if mt5.terminal_info() is not None and self._connected:
                    return True
                self._connected = False
                return self.connect()
            except ConnectionError:
                if attempt == retries - 1:
                    raise
                time.sleep(delay)
        return False

    # -- info ------------------------------------------------------------

    def symbol_info(self):
        return mt5.symbol_info(self.symbol)

    def account_info(self):
        return mt5.account_info()

    def current_spread_points(self) -> Optional[int]:
        info = mt5.symbol_info(self.symbol)
        return int(info.spread) if info else None

    def is_trade_allowed(self) -> bool:
        ti, ai = mt5.terminal_info(), mt5.account_info()
        return bool(ti and ti.trade_allowed and ai and ai.trade_expert)

    # -- context manager -------------------------------------------------

    def __enter__(self) -> "MT5Gateway":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.disconnect()


def detect_server_offset_hours() -> int:
    """
    Deteksi offset waktu server MT5 terhadap UTC, langsung dari tick
    terkini — bukan angka statis di config.

    Offset statis berbahaya: broker bisa menggeser jam server (DST, migrasi
    server) tanpa pemberitahuan. Saat itu terjadi, offset lama membuat bot
    salah menghitung sesi trading dan diam padahal seharusnya aktif —
    persis yang ditemukan 9 Sep 2026 (bot mengira jam 12:35 WIB padahal
    sebenarnya 19:37 WIB, selisih 7 jam sesuai offset lama).

    CATATAN PERBANDINGAN (10 Sep 2026): versi sebelumnya memakai
    `datetime.fromtimestamp()` vs `datetime.now()`, yaitu dua nilai waktu
    LOKAL. Suku offset laptop kebetulan saling meniadakan sehingga hasilnya
    tetap benar, tetapi hanya secara kebetulan dan tidak jelas terbaca.
    Sekarang perbandingannya eksplisit di UTC sehingga tidak bergantung
    pada zona waktu mesin yang menjalankan bot.
    """
    info = mt5.symbol_info_tick(load_config()["symbol"]["name"])
    if info is None or info.time == 0:
        # JANGAN jatuh ke angka config secara diam-diam. Nilai statis di
        # config pernah salah 7 jam dan menggeser seluruh dataset; kalau
        # offset tidak bisa diukur, itu harus terlihat, bukan ditebak.
        raise ConnectionError(
            "Tidak bisa mengukur offset server: tick tidak tersedia. "
            "Pastikan MT5 terhubung dan simbol aktif di Market Watch."
        )

    # MT5 mengembalikan jam dinding server sebagai epoch. Membacanya
    # sebagai UTC memberi jam dinding server apa adanya, lalu selisihnya
    # terhadap UTC sekarang adalah offset server.
    server_wall = datetime.fromtimestamp(info.time, tz=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    return round((server_wall - now_utc).total_seconds() / 3600)


def bars_to_utc_frame(bars, offset_hours: int) -> "pd.DataFrame":
    """
    Ubah bar mentah MT5 menjadi DataFrame ber-`time_utc` yang benar.

    SATU-SATUNYA tempat konversi waktu di seluruh sistem. Sebelumnya
    `downloader.py` dan `bot.py` masing-masing menghitung sendiri dengan
    sumber offset yang BERBEDA (config statis vs deteksi runtime), sehingga
    data historis bergeser 7 jam terhadap data live — backtest dan bot
    memperdagangkan jam yang berbeda tanpa ada yang menyadarinya.

    `time_server` disimpan apa adanya agar konversi selalu bisa diaudit
    ulang tanpa mengunduh ulang.
    """
    import pandas as pd

    df = pd.DataFrame(bars)
    df["time_server"] = pd.to_datetime(df["time"], unit="s")
    df["time_utc"] = df["time_server"] - pd.Timedelta(hours=offset_hours)
    return df.drop(columns=["time"])


def points_to_pips(points: float, config: Optional[dict] = None) -> float:
    """Konversi point broker ke pip gold. Broker ini: 1 pip = 10 points."""
    cfg = config or load_config()
    return points / cfg["symbol"]["pip_in_points"]


def pips_to_points(pips: float, config: Optional[dict] = None) -> float:
    cfg = config or load_config()
    return pips * cfg["symbol"]["pip_in_points"]
