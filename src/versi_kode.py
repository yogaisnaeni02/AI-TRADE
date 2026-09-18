"""Versi kode yang sedang berjalan, dan permintaan restart dari PC worker.

KENAPA ADA
----------
16 Sep 2026 sebuah PC menjalankan kode dari sebelum 15 Sep malam tanpa
ada yang tahu - log tidak mencatat versi apa pun. Journal-nya tertulis ke
file lama dan rem harian terbaca nol setelah restart. Header log bot kini
selalu mencantumkan versi, jadi hal itu terlihat dari baris pertama.

Di PC worker (scripts/pc_worker/) versi dibaca dari VERSI.json yang ikut
di setiap rilis; di PC pengembang dari git.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

# Harus sama dengan scripts/pc_worker/jalankan_worker.py (dicek tes).
KODE_UPDATE = 3
FLAG_RESTART = "minta_restart.flag"


def teks_versi(root: Path) -> str:
    try:
        info = json.loads((root / "VERSI.json").read_text(encoding="utf-8"))
        return f"rilis {info.get('versi')} (commit {info.get('commit')})"
    except (OSError, ValueError):
        pass
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root, capture_output=True, text=True, timeout=5,
        )
        if commit.returncode != 0:
            return "tidak diketahui"
        # Hanya jalur KODE. logs/trades.csv yang ikut Git selalu berubah
        # di PC yang berdagang - kalau ikut dihitung, semua PC terbaca
        # "ada perubahan lokal" dan tanda itu jadi tidak berarti.
        kotor = subprocess.run(
            ["git", "status", "--porcelain", "--", "src", "config", "run_bot.py"],
            cwd=root, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return f"git {commit.stdout.strip()}{' + perubahan lokal' if kotor else ''}"
    except (OSError, subprocess.SubprocessError):
        return "tidak diketahui"


def alasan_restart(log_dir: Path) -> Optional[str]:
    """Isi logs/minta_restart.flag bila PC worker meminta restart, atau None."""
    flag = log_dir / FLAG_RESTART
    try:
        return flag.read_text(encoding="utf-8").strip() or "update"
    except FileNotFoundError:
        return None
    except OSError:
        return "update"
