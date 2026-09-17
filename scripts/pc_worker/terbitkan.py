"""Terbitkan kode dan config dari repo ini ke semua PC worker.

    python scripts/pc_worker/terbitkan.py            (lewat UTAMA-2-TERBITKAN.bat)
    python scripts/pc_worker/terbitkan.py --paksa    izinkan perubahan belum di-commit
    python scripts/pc_worker/terbitkan.py --lewati-tes

Yang dilakukan:
  1. Periksa git: kode yang diterbitkan harus sudah di-commit, supaya
     versi di worker selalu bisa dilacak ke satu commit.
  2. Periksa config/penugasan.yaml: format dan nama varian.
  3. Jalankan tes.
  4. Salin HANYA yang dibutuhkan bot (JALUR_RILIS) ke folder rilis,
     lalu tulis VERSI.json paling akhir. Syncthing meneruskannya ke worker.

Worker memasang rilis baru sendiri, saat bot-nya tidak punya posisi terbuka.
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO))

import rilis  # noqa: E402

# Yang dibutuhkan bot untuk berjalan - tidak lebih. Data, backtest, docs,
# dan log PC utama sengaja tidak ikut: worker tidak memakainya, dan logs/
# milik PC utama tidak boleh menimpa journal worker.
JALUR_RILIS = ["run_bot.py", "requirements.txt", "src", "config", "scripts/pc_worker"]
PERTAHANKAN_DI_RILIS = (".stignore",)
KONFIG_UTAMA = REPO / "pc_utama.json"


def git(*argumen: str) -> str:
    hasil = subprocess.run(["git", *argumen], cwd=REPO, capture_output=True, text=True)
    if hasil.returncode != 0:
        raise RuntimeError(f"git {' '.join(argumen)} gagal: {hasil.stderr.strip()}")
    return hasil.stdout


def daftar_file() -> list[str]:
    """File ter-track + file baru yang tidak di-.gitignore, di JALUR_RILIS."""
    keluaran = git("ls-files", "--cached", "--others", "--exclude-standard", "--", *JALUR_RILIS)
    return [b for b in keluaran.splitlines() if b and (REPO / b).is_file()]


def periksa_penugasan() -> list[str]:
    """Masalah di penugasan.yaml, kosong bila aman."""
    import yaml

    from src.variants import list_variants

    jalur = REPO / rilis.PENUGASAN
    if not jalur.exists():
        return [f"{rilis.PENUGASAN} tidak ada"]
    teks = jalur.read_text(encoding="utf-8")
    try:
        sederhana = rilis.urai_penugasan(teks)
    except ValueError as e:
        return [str(e)]
    lengkap = yaml.safe_load(teks) or {}
    # Worker memakai pengurai sederhana. Kalau hasilnya beda dengan PyYAML,
    # formatnya di luar yang didukung - hentikan di sini, bukan di worker.
    if {str(k): str(v) for k, v in lengkap.items()} != sederhana:
        return ["format penugasan.yaml di luar yang didukung (pakai `kunci: varian` per baris)"]

    masalah = []
    varian = set(list_variants())
    for kunci, nilai in sederhana.items():
        if rilis.slug(kunci) != kunci:
            masalah.append(f"kunci '{kunci}' bukan format nama PC (seharusnya '{rilis.slug(kunci)}')")
        if nilai != "berhenti" and nilai not in varian:
            masalah.append(f"{kunci}: varian '{nilai}' tidak ada di config/variants.yaml")
    return masalah


def jalankan_tes() -> bool:
    import importlib.util

    if importlib.util.find_spec("pytest") is None:
        print("!! pytest belum terpasang: .venv\\Scripts\\pip install pytest")
        return False
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=REPO).returncode == 0


def folder_rilis_bawaan() -> Path:
    try:
        return Path(json.loads(KONFIG_UTAMA.read_text(encoding="utf-8"))["rilis"])
    except (OSError, ValueError, KeyError):
        return REPO.parent / "AI-TRADE-rilis"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rilis", default=None, help="folder rilis (bawaan dari pc_utama.json)")
    ap.add_argument("--paksa", action="store_true", help="izinkan perubahan belum di-commit")
    ap.add_argument("--lewati-tes", action="store_true")
    ap.add_argument("--ya", action="store_true", help="jangan bertanya konfirmasi")
    args = ap.parse_args()
    tujuan = Path(args.rilis) if args.rilis else folder_rilis_bawaan()

    print("=" * 58)
    print("  TERBITKAN RILIS KE PC WORKER")
    print("=" * 58)

    commit = git("rev-parse", "--short", "HEAD").strip()
    branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    # penugasan.yaml boleh diubah tanpa commit: itu setelan operasional
    # (PC mana menjalankan apa), bukan kode. Isinya tetap tercatat di
    # VERSI.json setiap rilis, jadi riwayatnya tidak hilang.
    kotor = [
        b for b in git("status", "--porcelain", "--", *JALUR_RILIS).splitlines()
        if b and not b.endswith(rilis.PENUGASAN)
    ]
    print(f"  Branch : {branch}   commit {commit}")
    print(f"  Tujuan : {tujuan}")

    if kotor:
        print(f"\n  Perubahan belum di-commit ({len(kotor)}):")
        for b in kotor[:15]:
            print(f"    {b}")
        if not args.paksa:
            print("\n!! Commit dulu, supaya versi di worker bisa dilacak ke satu commit.")
            print("   (Atau jalankan dengan --paksa untuk uji coba.)")
            return 1
    if branch != "main" and not args.ya:
        print(f"\n!! Ini branch '{branch}', bukan main. Semua worker akan menjalankan kode branch ini.")
        if input("   Tetap terbitkan? ketik 'ya': ").strip().lower() != "ya":
            return 1

    print("\n[1/3] Memeriksa penugasan...")
    masalah = periksa_penugasan()
    if masalah:
        for m in masalah:
            print(f"  !! {m}")
        return 1
    penugasan = rilis.urai_penugasan((REPO / rilis.PENUGASAN).read_text(encoding="utf-8"))
    for kunci, varian in sorted(penugasan.items()):
        print(f"  {kunci:<24} -> {varian}")
    if not penugasan:
        print("  (kosong - belum ada worker yang menjalankan bot)")

    print("\n[2/3] Menjalankan tes...")
    if args.lewati_tes:
        print("  dilewati (--lewati-tes)")
    elif not jalankan_tes():
        print("!! Tes gagal - rilis dibatalkan. Worker tetap memakai versi sebelumnya.")
        return 1

    print("\n[3/3] Menyalin ke folder rilis...")
    manifest = rilis.buat_manifest(REPO, daftar_file())
    lama = rilis.baca_versi(tujuan)
    if lama and rilis.sidik(lama["file"]) == rilis.sidik(manifest):
        print(f"  Tidak ada perubahan sejak rilis {lama.get('versi')}. Tidak ada yang diterbitkan.")
        return 0

    sekarang = datetime.now()
    info = {
        "versi": f"{sekarang:%Y%m%d-%H%M}-{commit}{'-ubahan' if kotor else ''}",
        "commit": commit,
        "branch": branch,
        "ada_ubahan_lokal": bool(kotor),
        "dibuat": sekarang.isoformat(timespec="seconds"),
        "oleh": socket.gethostname(),
        "penugasan": penugasan,
        "file": manifest,
    }
    hasil = rilis.cermin(REPO, tujuan, info, PERTAHANKAN_DI_RILIS)
    print(f"  Versi  : {info['versi']}")
    print(f"  File   : {len(manifest)} ({hasil['disalin']} disalin, {hasil['dihapus']} dihapus)")
    if lama:
        print(f"  Sebelumnya: {lama.get('versi')}")
    print("\nSelesai. Worker memasangnya sendiri begitu bot-nya tidak punya posisi terbuka.")
    print("Pantau dengan UTAMA-3-STATUS-WORKER.bat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
