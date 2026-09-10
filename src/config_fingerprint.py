"""
Sidik jari konfigurasi sinyal.

MASALAH YANG DISELESAIKAN
-------------------------
Forward test hanya bermakna bila seluruh trade di dalamnya berasal dari
setelan yang SAMA. Empat bulan lagi, saat melihat 200 trade, pertanyaannya:
yakin semuanya dari jalur sinyal yang identik?

Sampai sekarang tidak ada cara menjawabnya. `config/settings.yaml` ikut git,
sehingga satu `git pull` bisa mengubah jalur sinyal tanpa disadari — dan itu
sudah terjadi tiga kali dalam satu hari:

  1. `max_bars` backtest 120 vs live 48          (docs/30 §0.1)
  2. label sesi basi 7 jam di data/processed     (docs/38 §8)
  3. `generate()` default min_score 7 vs bot 5   (docs/38 §9)

Ketiganya diam-diam, dan ketiganya baru ketahuan setelah berminggu-minggu.

CARA KERJA
----------
Hash pendek dihitung dari nilai-nilai yang benar-benar menentukan sinyal,
lalu **ditempelkan ke comment order**. Karena MT5 menyimpan comment di
riwayat deal, hash itu ikut ke `logs/trades.csv` lewat journal tanpa
perlu state tambahan — dan tetap ada meski bot restart.

Hasilnya: `scripts/compare_live_vs_backtest.py` bisa MENOLAK menggabungkan
trade dari sidik jari berbeda, alih-alih diam-diam merata-ratakannya.

Comment MT5 dibatasi 31 karakter, jadi hash dipendekkan ke 4 hex — cukup
untuk mendeteksi perubahan yang tidak disengaja (peluang tabrakan 1/65.536),
bukan untuk melawan manipulasi.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

# Kunci yang mengubah SINYAL atau UKURAN POSISI. Menambah kunci di sini
# akan mengubah hash semua trade berikutnya - itu memang tujuannya.
#
# Yang sengaja TIDAK masuk: telegram, jalur log, poll_seconds, dan apa pun
# yang tidak mempengaruhi trade mana yang diambil atau sebesar apa.
SIGNAL_KEYS = [
    ("settings", ["symbol", "name"]),
    ("settings", ["mode"]),
    ("settings", ["active_setups"]),
    ("settings", ["momentum_fib"]),
    ("settings", ["trade_distances", "sl_min_points"]),
    ("settings", ["trade_distances", "sl_typical_points"]),
    ("settings", ["trade_distances", "sl_max_points"]),
    ("settings", ["trade_distances", "tp_min_points"]),
    ("settings", ["trade_distances", "min_rr_ratio"]),
    ("settings", ["trade_distances", "atr_sl_multiplier"]),
    ("settings", ["position_management", "breakeven_at_r"]),
    ("settings", ["position_management", "trail_atr_mult"]),
    ("settings", ["position_management", "max_bars_hold"]),
    ("settings", ["costs", "spread_max_accept"]),
    ("settings", ["broker", "server_utc_offset"]),
    ("risk", ["per_trade", "max_risk_percent"]),
    ("risk", ["per_trade", "min_rr_ratio"]),
    ("risk", ["per_trade", "max_lot_percent_equity"]),
    ("risk", ["daily", "max_trades"]),
    ("risk", ["daily", "max_loss_percent"]),
    ("risk", ["daily", "max_consecutive_losses"]),
    ("risk", ["weekly", "max_loss_percent"]),
    ("risk", ["global", "max_drawdown_percent"]),
    ("risk", ["global", "max_open_positions"]),
    ("risk", ["tiered_sizing"]),
    ("risk", ["adaptive_sizing"]),
]


def _dig(d: Any, path: list[str]) -> Any:
    for k in path:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def signal_config(settings: dict, risk: dict, min_score: int) -> dict:
    """Kumpulan nilai yang menentukan sinyal, dalam bentuk yang bisa dibaca."""
    src = {"settings": settings, "risk": risk}
    out: dict[str, Any] = {"min_score": min_score}
    for which, path in SIGNAL_KEYS:
        out[f"{which}.{'.'.join(path)}"] = _dig(src[which], path)

    # Jam sesi ikut menentukan sinyal tetapi tinggal di kode, bukan config.
    try:
        from .strategy.sessions import SESSIONS
        out["sessions"] = [[n, a, b, ok] for n, a, b, ok in SESSIONS]
    except Exception:  # noqa: BLE001
        out["sessions"] = "tidak terbaca"

    return out


def fingerprint(settings: dict, risk: dict, min_score: int, length: int = 4) -> str:
    """Hash pendek dari konfigurasi sinyal. Contoh: 'a3f2'."""
    blob = json.dumps(signal_config(settings, risk, min_score),
                      sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:length]


def describe(settings: dict, risk: dict, min_score: int) -> str:
    """Satu baris ringkas untuk log saat bot start."""
    c = signal_config(settings, risk, min_score)
    mf = c.get("settings.momentum_fib") or {}
    return (
        f"cfg={fingerprint(settings, risk, min_score)} "
        f"setup={c.get('settings.active_setups')} "
        f"min_score={min_score} "
        f"atr={mf.get('atr_percentile_min')}-{mf.get('atr_percentile_max')} "
        f"sell={mf.get('allow_sell', False)} "
        f"rr={c.get('settings.trade_distances.min_rr_ratio')} "
        f"risk={c.get('risk.per_trade.max_risk_percent')}% "
        f"maxpos={c.get('risk.global.max_open_positions')}"
    )
