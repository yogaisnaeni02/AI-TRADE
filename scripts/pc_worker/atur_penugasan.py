"""Atur varian tiap PC worker cukup dengan memilih NOMOR.

    python scripts/pc_worker/atur_penugasan.py    (lewat UTAMA-4-ATUR-VARIAN-WORKER.bat)

Tanpa mengetik kunci PC atau nama varian: pilih nomor worker, lalu nomor
varian - nomornya sama dengan daftar di 5-JALANKAN-VARIAN.bat. Hasilnya
ditulis ke config/penugasan.yaml, lalu bisa langsung diterbitkan.

Worker yang muncul di daftar adalah yang sudah DITERIMA di PC utama
(UTAMA-3-STATUS-WORKER.bat) atau yang sudah tercantum di penugasan.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parents[2]
SINI = Path(__file__).resolve().parent
sys.path.insert(0, str(SINI))
sys.path.insert(0, str(REPO))

import rilis  # noqa: E402
from src.variants import format_table, list_variants, pilih  # noqa: E402

BERHENTI = "berhenti"


def _json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def folder_laporan() -> Path:
    return Path(_json(REPO / "pc_utama.json").get("laporan") or REPO / "laporan")


def daftar_worker(laporan: Path, penugasan: dict[str, str]) -> list[dict]:
    kunci = set(penugasan)
    if laporan.exists():
        kunci |= {p.name for p in laporan.iterdir() if p.is_dir()}
    hasil = []
    for k in kunci:
        stt = _json(laporan / k / "status_worker.json")
        hasil.append({
            "kunci": k,
            "nama": stt.get("nama") or k,
            "berjalan": stt.get("varian"),
        })
    return sorted(hasil, key=lambda w: w["nama"].lower())


def tulis_penugasan(path: Path, penugasan: dict[str, str]) -> None:
    """Pertahankan komentar pembuka file, ganti seluruh baris pemetaan."""
    kepala: list[str] = []
    try:
        for baris in path.read_text(encoding="utf-8").splitlines():
            if baris.strip() and not baris.lstrip().startswith("#"):
                break
            kepala.append(baris)
    except OSError:
        pass
    while kepala and not kepala[-1].strip():
        kepala.pop()
    isi = [f"{k}: {v}" for k, v in sorted(penugasan.items())]
    teks = "\n".join(kepala + ([""] if kepala and isi else []) + isi) + "\n"
    path.write_text(teks, encoding="utf-8")


def terjemahkan(pilihan: str) -> Optional[str]:
    """'0' -> berhenti, 'h' -> '' (hapus), nomor/nama -> varian, None bila tidak dikenal."""
    teks = pilihan.strip().lower()
    if teks == "0":
        return BERHENTI
    if teks == "h":
        return ""
    return pilih(teks)


def tanya(teks: str) -> str:
    try:
        return input(teks).strip()
    except EOFError:
        return ""


def tampilkan_worker(workers: list[dict], penugasan: dict[str, str]) -> None:
    print(f"\n  {'no':<4}{'PC':<24}{'penugasan':<24}sedang berjalan")
    print("  " + "-" * 70)
    for i, w in enumerate(workers, start=1):
        tugas = penugasan.get(w["kunci"], "-")
        print(f"  {i:<4}{w['nama'][:22]:<24}{tugas:<24}{w['berjalan'] or '-'}")


def main() -> int:
    jalur = REPO / rilis.PENUGASAN
    try:
        penugasan = rilis.baca_penugasan(REPO)
    except ValueError as e:
        print(f"!! {rilis.PENUGASAN} tidak terbaca: {e}")
        return 1
    awal = dict(penugasan)

    print("=" * 58)
    print("  ATUR VARIAN TIAP PC WORKER")
    print("=" * 58)

    workers = daftar_worker(folder_laporan(), penugasan)
    if not workers:
        print("\nBelum ada worker. Pasang worker dan terima dulu lewat UTAMA-3-STATUS-WORKER.bat.")
        return 1

    varian = list_variants()
    while True:
        tampilkan_worker(workers, penugasan)
        p = tanya("\nNomor PC yang mau diubah (Enter = selesai): ")
        if not p:
            break
        if not p.isdigit() or not 1 <= int(p) <= len(workers):
            print(f"!! '{p}' tidak ada di daftar.")
            continue
        w = workers[int(p) - 1]

        print(f"\nVarian untuk {w['nama']} (sekarang: {penugasan.get(w['kunci'], '-')}):\n")
        print("0  berhenti  - worker hidup, bot TIDAK dijalankan")
        print("h  hapus     - hapus dari penugasan (sama-sama tidak menjalankan bot)\n")
        print(format_table())
        jawab = tanya("\nNomor varian (Enter = batal): ")
        if not jawab:
            continue
        hasil = terjemahkan(jawab)
        if hasil is None:
            print("!! pilihan tidak dikenal - tidak ada yang diubah.")
            continue
        status = str((varian.get(hasil) or {}).get("status", ""))
        if "riset" in status:
            print(f"!! {hasil} berstatus '{status}' - belum siap dijalankan bot.")
            if not tanya("   Tetap pilih? ketik 'ya': ").lower() == "ya":
                continue
        if hasil:
            penugasan[w["kunci"]] = hasil
        else:
            penugasan.pop(w["kunci"], None)
        print(f"-> {w['nama']}: {hasil or '(dihapus)'}")

    if penugasan == awal:
        print("\nTidak ada perubahan.")
        return 0

    print("\nPerubahan:")
    for k in sorted(set(awal) | set(penugasan)):
        if awal.get(k) != penugasan.get(k):
            print(f"  {k:<24} {awal.get(k, '-')}  ->  {penugasan.get(k, '-')}")
    tulis_penugasan(jalur, penugasan)
    print(f"Tersimpan di {rilis.PENUGASAN}.")

    print("\nWorker baru memakainya setelah DITERBITKAN.")
    if tanya("Terbitkan sekarang? (y/n): ").lower().startswith("y"):
        return subprocess.run([sys.executable, str(SINI / "terbitkan.py")], cwd=REPO).returncode
    print("Jalankan UTAMA-2-TERBITKAN.bat bila sudah siap.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
