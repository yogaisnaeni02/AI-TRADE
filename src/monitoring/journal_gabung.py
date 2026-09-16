"""
Gabungkan journal trade dari beberapa PC menjadi satu tabel.

MASALAH YANG DISELESAIKAN
-------------------------
Bot dijalankan di beberapa PC dengan varian berbeda. Tiap PC menulis
`logs/trades.csv` sendiri, dan file itu ikut Git. Begitu dua PC sama-sama
menambah trade baru lalu push, Git melihat dua perubahan di baris yang
sama dan menghasilkan CONFLICT - di tengah file data, bukan kode.

Itu terjadi setiap kali kedua bot menulis trade, bukan sesekali.

CARA KERJA
----------
Tiap PC menulis ke file BERNAMA SENDIRI:

    logs/trades__<nama-pc>.csv

Nama PC diambil dari logs/nama_pc.txt (diisi sekali lewat
5-JALANKAN-VARIAN.bat). Karena nama filenya berbeda, dua PC tidak pernah
menyentuh file yang sama - tidak ada conflict, apa pun urutan push/pull.

Penggabungan terjadi saat DIBACA, bukan saat ditulis: `baca_semua()`
membaca semua file `trades__*.csv` plus `trades.csv` lama, membuang
duplikat berdasarkan ticket, lalu mengurutkannya.

KENAPA TIDAK MENGGABUNG SAAT MENULIS
------------------------------------
Menulis ke satu file bersama mengembalikan masalah aslinya. Menulis ke
file sendiri dan menggabung saat baca membuat operasi tulis tetap
sederhana dan tidak pernah bertabrakan - pola yang sama dipakai log
terdistribusi pada umumnya.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "logs"
NAMA_PC_FILE = LOG_DIR / "nama_pc.txt"

# File lama sebelum pemisahan per-PC. Tetap dibaca supaya riwayat trade
# yang sudah terkumpul tidak hilang.
TRADES_LAMA = LOG_DIR / "trades.csv"

_AMAN = re.compile(r"[^A-Za-z0-9_-]+")


def nama_pc() -> str:
    """Nama PC ini, dari logs/nama_pc.txt atau hostname."""
    try:
        if NAMA_PC_FILE.exists():
            teks = NAMA_PC_FILE.read_text(encoding="utf-8").strip()
            if teks:
                return teks
    except OSError:
        pass
    import socket
    return socket.gethostname()


def _slug(nama: str) -> str:
    """Nama PC -> potongan nama file yang aman di Windows."""
    bersih = _AMAN.sub("-", nama.strip()).strip("-")
    return bersih.lower() or "tanpa-nama"


def path_pc(nama: Optional[str] = None) -> Path:
    """Jalur file journal untuk satu PC."""
    return LOG_DIR / f"trades__{_slug(nama or nama_pc())}.csv"


def daftar_file() -> list[Path]:
    """Semua file journal yang ada: per-PC plus file lama."""
    files = sorted(LOG_DIR.glob("trades__*.csv"))
    if TRADES_LAMA.exists():
        files.append(TRADES_LAMA)
    return files


def baca_semua() -> list[dict]:
    """Gabungan seluruh journal, duplikat dibuang, terurut waktu masuk.

    Duplikat dibuang berdasarkan `ticket` - satu posisi hanya boleh muncul
    sekali walau filenya tersalin ke beberapa tempat. Baris tanpa ticket
    dipertahankan apa adanya (tidak bisa dibandingkan).
    """
    hasil: dict[str, dict] = {}
    tanpa_ticket: list[dict] = []

    for f in daftar_file():
        # Label PC diambil dari nama file, supaya baris lama yang belum
        # punya kolom `pc` tetap bisa ditelusuri asalnya.
        asal = f.stem[len("trades__"):] if f.stem.startswith("trades__") else "lama"
        try:
            with open(f, encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    row.setdefault("pc", asal)
                    if not row.get("pc"):
                        row["pc"] = asal
                    tick = (row.get("ticket") or "").strip()
                    if tick:
                        hasil.setdefault(tick, row)
                    else:
                        tanpa_ticket.append(row)
        except OSError:
            continue

    semua = list(hasil.values()) + tanpa_ticket
    semua.sort(key=lambda r: r.get("entry_time") or "")
    return semua


def tulis_gabungan(tujuan: Optional[Path] = None) -> Path:
    """Tulis hasil gabungan ke satu file untuk dibaca manusia/dashboard.

    File ini TURUNAN - boleh dihapus kapan saja dan dibangun ulang dari
    file per-PC. Jangan jadikan sumber kebenaran, dan jangan di-commit.
    """
    tujuan = tujuan or (LOG_DIR / "trades_gabungan.csv")
    rows = baca_semua()
    if not rows:
        return tujuan

    kolom: list[str] = []
    for r in rows:
        for k in r:
            if k not in kolom:
                kolom.append(k)

    LOG_DIR.mkdir(exist_ok=True)
    with open(tujuan, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=kolom, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return tujuan


def ringkas() -> str:
    """Ringkasan per PC dan per varian, untuk dicetak di terminal."""
    rows = baca_semua()
    if not rows:
        return "Belum ada trade tercatat."

    def _f(x) -> float:
        try:
            return float(x)
        except (TypeError, ValueError):
            return 0.0

    baris = [f"Total trade tergabung: {len(rows)}", ""]

    for kunci, judul in (("pc", "PER PC"), ("varian", "PER VARIAN")):
        grup: dict[str, list[dict]] = {}
        for r in rows:
            grup.setdefault(r.get(kunci) or "?", []).append(r)

        baris.append(judul)
        baris.append(f"  {'nama':<22} {'trade':>6} {'menang':>7} {'P/L (Rp)':>14}")
        for nama, g in sorted(grup.items()):
            menang = sum(1 for r in g if _f(r.get("net_idr")) > 0)
            pnl = sum(_f(r.get("net_idr")) for r in g)
            baris.append(f"  {nama:<22} {len(g):>6} {menang:>7} {pnl:>14,.0f}")
        baris.append("")

    return "\n".join(baris)


if __name__ == "__main__":
    print(ringkas())
    p = tulis_gabungan()
    print(f"File gabungan: {p}")
