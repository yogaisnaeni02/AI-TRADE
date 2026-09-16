"""Buat laporan Markdown lokal sebelum pull atau push."""

from __future__ import annotations

import json
import re
import socket
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
REPORT_DIR = ROOT / "docs" / "AnalisaLog"
sys.path.insert(0, str(ROOT))

from src.monitoring.journal_gabung import path_pc


def slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-")
    return cleaned.upper() or "PC"


def read_snapshot() -> dict:
    path = LOG_DIR / "snapshot.json"
    try:
        with path.open(encoding="utf-8") as file:
            value = json.load(file)
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    now = datetime.now()
    pc = socket.gethostname()
    local_file = path_pc()
    local_rows = []
    if local_file.exists():
        import csv

        with local_file.open(encoding="utf-8", newline="") as file:
            local_rows = list(csv.DictReader(file))

    snapshot = read_snapshot()
    report_path = REPORT_DIR / f"LOG-{slug(pc)}-{now:%Y%m%d-%H%M%S}.md"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    latest = local_rows[-1] if local_rows else {}
    bot_lock = LOG_DIR / "bot.lock"
    bot_status = "terdeteksi (logs/bot.lock ada)" if bot_lock.exists() else "tidak terdeteksi"

    lines = [
        f"# Laporan Bot dan Trade - {pc}",
        "",
        f"- Waktu pemeriksaan: `{now.isoformat(timespec='seconds')}`",
        f"- PC: `{pc}`",
        f"- Status bot berdasarkan lock: **{bot_status}**",
        f"- File journal lokal: `{local_file.relative_to(ROOT).as_posix()}`",
        f"- Jumlah trade lokal: **{len(local_rows)}**",
        f"- Snapshot terakhir: `{snapshot.get('timestamp', 'tidak tersedia')}`",
        f"- Equity snapshot: `{snapshot.get('equity', 'tidak tersedia')}`",
        "",
        "## Trade Terakhir",
        "",
    ]
    if latest:
        lines.extend([
            f"- Ticket: `{latest.get('ticket', '-')}`",
            f"- Waktu entry: `{latest.get('entry_time', '-')}`",
            f"- Arah: `{latest.get('direction', '-')}`",
            f"- Varian: `{latest.get('varian', '-')}`",
            f"- Net IDR: `{latest.get('net_idr', '-')}`",
        ])
    else:
        lines.append("Belum ada trade lokal yang tercatat.")

    lines.extend([
        "",
        "## Aturan Sinkronisasi",
        "",
        "- Laporan ini dibuat sebelum `git pull` atau `git push`.",
        "- Jangan menghapus atau mengganti nama laporan lama.",
        "- Journal runtime tetap berada di `logs/`; folder ini hanya arsip analisis.",
    ])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Laporan dibuat: {report_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
