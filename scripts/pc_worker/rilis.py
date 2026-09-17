"""Paket rilis: daftar file bersidik jari, verifikasi, dan penyalinan.

Dipakai dua sisi:
- PC utama (terbitkan.py) menyalin kode dari repo ke folder rilis.
- PC worker (jalankan_worker.py) menyalin folder rilis ke folder bot.

HANYA pustaka standar. Worker menjalankan file ini sebelum paket apa pun
terpasang, jadi tidak boleh ada impor pihak ketiga di sini.

Kenapa ada sidik jari per file: Syncthing mengirim file satu per satu
dengan urutan bebas. Tanpa pengecekan, worker bisa menyalin rilis yang
baru separuh tiba - sebagian modul versi baru, sebagian versi lama.
Itu persis yang terjadi 16 Sep 2026 (git pull di tengah bot berjalan).
Worker hanya memakai rilis yang SELURUH filenya cocok dengan VERSI.json.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Iterable, Optional

NAMA_VERSI = "VERSI.json"
PENUGASAN = "config/penugasan.yaml"

# Folder dan file yang tidak pernah dianggap bagian dari rilis.
_DIR_ABAIKAN = {"__pycache__", ".stfolder", ".stversions", ".git"}
_AKHIRAN_ABAIKAN = (".pyc", ".pyo", ".tmp")

_AMAN = re.compile(r"[^A-Za-z0-9_-]+")


def slug(nama: str) -> str:
    """Nama PC -> kunci penugasan dan nama file journal.

    HARUS sama persis dengan src/monitoring/journal_gabung._slug, supaya
    `pc-kantor` di penugasan.yaml menunjuk PC yang sama dengan
    logs/trades__pc-kantor.csv. Diduplikasi (bukan diimpor) karena file
    ini tidak boleh bergantung pada src/; tes memastikan keduanya sama.
    """
    bersih = _AMAN.sub("-", nama.strip()).strip("-")
    return bersih.lower() or "tanpa-nama"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def diabaikan(rel: str) -> bool:
    bagian = rel.replace("\\", "/").split("/")
    if any(b in _DIR_ABAIKAN for b in bagian):
        return True
    nama = bagian[-1]
    return (
        nama.endswith(_AKHIRAN_ABAIKAN)
        or nama.startswith(".syncthing.")
        or nama.startswith("~syncthing~")
    )


def buat_manifest(akar: Path, daftar: Iterable[str]) -> dict[str, str]:
    """{jalur relatif berformat posix: sha256} untuk file yang tidak diabaikan."""
    hasil: dict[str, str] = {}
    for rel in sorted({r.replace("\\", "/") for r in daftar}):
        if diabaikan(rel):
            continue
        p = akar / rel
        if p.is_file():
            hasil[rel] = sha256_file(p)
    return hasil


def sidik(manifest: dict[str, str], kecuali: Iterable[str] = ()) -> str:
    """Satu hash untuk seluruh manifest - dipakai membandingkan dua rilis."""
    buang = set(kecuali)
    h = hashlib.sha256()
    for rel in sorted(manifest):
        if rel in buang:
            continue
        h.update(f"{rel}\0{manifest[rel]}\n".encode("utf-8"))
    return h.hexdigest()[:16]


def sidik_kode(info: dict) -> str:
    """Sidik jari rilis TANPA penugasan.yaml.

    Mengubah penugasan satu PC tidak boleh memaksa SEMUA worker restart.
    Worker membandingkan sidik ini untuk kode, dan penugasannya sendiri
    secara terpisah.
    """
    return sidik(info.get("file", {}), kecuali=[PENUGASAN])


def baca_versi(folder: Path) -> Optional[dict]:
    try:
        with open(folder / NAMA_VERSI, encoding="utf-8") as f:
            info = json.load(f)
    except (OSError, ValueError):
        return None
    return info if isinstance(info.get("file"), dict) else None


def tulis_versi(folder: Path, info: dict) -> None:
    """Tulis VERSI.json secara atomik (tmp lalu ganti nama)."""
    tmp = folder / (NAMA_VERSI + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2, ensure_ascii=False)
    os.replace(tmp, folder / NAMA_VERSI)


def verifikasi(folder: Path) -> tuple[bool, Optional[dict], list[str]]:
    """Apakah seluruh file di VERSI.json ada dan isinya cocok?

    Mengembalikan (lengkap, info, daftar masalah - maksimal 5 contoh).
    """
    info = baca_versi(folder)
    if info is None:
        return False, None, [f"{NAMA_VERSI} belum ada"]
    masalah: list[str] = []
    for rel, sha in info["file"].items():
        p = folder / rel
        try:
            cocok = p.is_file() and sha256_file(p) == sha
        except OSError:
            cocok = False
        if not cocok:
            masalah.append(rel)
            if len(masalah) >= 5:
                break
    return not masalah, info, masalah


def cermin(sumber: Path, tujuan: Path, info: dict,
           pertahankan: Iterable[str] = ()) -> dict[str, int]:
    """Samakan isi `tujuan` dengan manifest di `info`, file diambil dari `sumber`.

    - File yang isinya berbeda disalin (lewat file sementara, lalu ganti nama).
    - File di `tujuan` yang tidak ada di manifest dihapus, KECUALI yang
      berada di bawah nama tingkat atas pada `pertahankan` (mis. logs/,
      STOP, venv) - data dan kill switch milik PC itu tidak boleh hilang.
    - VERSI.json ditulis PALING AKHIR, jadi keberadaannya berarti
      penyalinan selesai.
    """
    tujuan.mkdir(parents=True, exist_ok=True)
    tetap = set(pertahankan) | {NAMA_VERSI}
    manifest: dict[str, str] = info["file"]
    disalin = dihapus = 0

    for rel, sha in manifest.items():
        dst = tujuan / rel
        if dst.is_file() and sha256_file(dst) == sha:
            continue
        src = sumber / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".tmp")
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
        disalin += 1

    for akar, dirs, files in os.walk(tujuan, topdown=True):
        rel_akar = Path(akar).relative_to(tujuan).as_posix()
        if rel_akar == ".":
            dirs[:] = [d for d in dirs if d not in tetap and d not in _DIR_ABAIKAN]
            files = [f for f in files if f not in tetap]
        else:
            dirs[:] = [d for d in dirs if d not in _DIR_ABAIKAN]
        for nama in files:
            rel = nama if rel_akar == "." else f"{rel_akar}/{nama}"
            if rel not in manifest:
                try:
                    (Path(akar) / nama).unlink()
                    dihapus += 1
                except OSError:
                    pass

    # Folder yang jadi kosong setelah penghapusan ikut dibuang - kecuali
    # .stfolder: penanda Syncthing itu memang kosong, dan kalau terhapus
    # Syncthing menghentikan folder tersebut.
    for akar, dirs, files in os.walk(tujuan, topdown=False):
        p = Path(akar)
        if p == tujuan:
            continue
        bagian = p.relative_to(tujuan).parts
        if bagian[0] in tetap or any(b in _DIR_ABAIKAN for b in bagian):
            continue
        try:
            if not any(p.iterdir()):
                p.rmdir()
        except OSError:
            pass

    tulis_versi(tujuan, info)
    return {"disalin": disalin, "dihapus": dihapus}


# -- penugasan ------------------------------------------------------------

def urai_penugasan(teks: str) -> dict[str, str]:
    """Urai config/penugasan.yaml: pemetaan datar `nama-pc: varian`.

    Sengaja TIDAK memakai PyYAML - worker membacanya sebelum paket apa
    pun terpasang. Formatnya dibatasi agar pengurai sederhana ini cukup;
    terbitkan.py mencocokkan hasilnya dengan PyYAML sebelum menerbitkan,
    jadi format yang tidak didukung ketahuan di PC utama, bukan di worker.
    """
    hasil: dict[str, str] = {}
    for baris in teks.splitlines():
        isi = baris.split("#", 1)[0].strip()
        if not isi:
            continue
        if ":" not in isi:
            raise ValueError(f"baris penugasan tidak dikenal: {baris!r}")
        kunci, nilai = (s.strip().strip("'\"") for s in isi.split(":", 1))
        if not kunci or not nilai:
            raise ValueError(f"baris penugasan tidak lengkap: {baris!r}")
        hasil[kunci] = nilai
    return hasil


def baca_penugasan(folder: Path) -> dict[str, str]:
    try:
        teks = (folder / PENUGASAN).read_text(encoding="utf-8")
    except OSError:
        return {}
    return urai_penugasan(teks)
