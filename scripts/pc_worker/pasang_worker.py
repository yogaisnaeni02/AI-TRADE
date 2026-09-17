r"""Pemasang PC worker AI-TRADE.

Tidak dijalankan langsung: UTAMA-1-SIAPKAN.bat membundel file ini (bersama
syncthing_alat.py dan ID PC utama) ke dalam PASANG-WORKER.bat. Di PC
worker cukup klik dua kali file .bat itu.

HANYA pustaka standar - dijalankan sebelum paket apa pun terpasang.

Aman diulang: langkah yang sudah selesai dilewati, jadi kalau pemasangan
terputus (internet mati, jendela tertutup), cukup klik dua kali lagi.

Susunan folder di PC worker:

    AI-TRADE-WORKER\
      AI-TRADE-WORKER.bat   peluncur (shortcut desktop menunjuk ke sini)
      worker.json           nama PC + lokasi Syncthing
      syncthing\            syncthing.exe dan datanya
      rilis\                kiriman PC utama - HANYA MENERIMA, jangan diubah
      bot\                  salinan rilis tempat bot berjalan
      bot\logs\             dikirim otomatis ke PC utama
      venv\                 paket Python
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import syncthing_alat as st

PYTHON_MIN = (3, 10)

ISI_STIGNORE = """\
// Dibuat pemasang AI-TRADE worker. File di bawah TIDAK dikirim ke PC utama.
bot.lock
minta_restart.flag
*.tmp
"""

# Peluncur sengaja dibuat SANGAT kecil dan tidak pernah berubah. Semua
# logika ada di jalankan_worker.py yang ikut diperbarui lewat rilis. File
# .bat dibaca cmd baris demi baris selama berjalan; kalau isinya diganti di
# tengah jalan, cmd bisa mengeksekusi potongan baris yang salah.
ISI_PELUNCUR = r"""@echo off
title AI-TRADE Worker
cd /d "%~dp0"
set PYTHONDONTWRITEBYTECODE=1
set PYTHONIOENCODING=utf-8

:ulang
if not exist "rilis\scripts\pc_worker\jalankan_worker.py" (
    echo Kode dari PC utama belum tiba.
    echo Pastikan PC utama menyala dan sudah menerima PC ini.
    timeout /t 30
    goto ulang
)
"venv\Scripts\python.exe" "rilis\scripts\pc_worker\jalankan_worker.py" --folder "%~dp0."
set KODE=%ERRORLEVEL%
if "%KODE%"=="0" goto selesai
rem Kode 4: peluncur sendiri ikut diperbarui - langsung jalan lagi.
if "%KODE%"=="4" goto ulang
echo.
echo [%date% %time%] worker berhenti tak terduga (kode %KODE%), mencoba lagi dalam 30 detik...
echo Tekan Ctrl+C untuk membatalkan.
timeout /t 30
goto ulang

:selesai
echo.
echo === WORKER BERHENTI ===
pause
"""


def cetak(teks: str = "") -> None:
    print(teks, flush=True)


def judul(teks: str) -> None:
    cetak()
    cetak(f"--- {teks} " + "-" * max(0, 50 - len(teks)))


def tanya(pertanyaan: str, bawaan: str = "") -> str:
    try:
        jawab = input(f"{pertanyaan}{f' [{bawaan}]' if bawaan else ''}: ").strip()
    except EOFError:
        jawab = ""
    return jawab or bawaan


def tanya_ya(pertanyaan: str, bawaan: bool = True) -> bool:
    j = tanya(f"{pertanyaan} (y/n)", "y" if bawaan else "n").lower()
    return j.startswith("y")


def _jalankan(perintah: list[str], **kw) -> int:
    return subprocess.run(perintah, **kw).returncode


def tunggu_rilis(api: st.Api, folder: Path, id_utama: str, batas_detik: int) -> bool:
    """Tunggu kiriman pertama dari PC utama sampai lengkap dan terverifikasi."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import rilis as rilis_mod  # dibundel bersama file ini

    mulai = time.time()
    terakhir = ""
    while True:
        lengkap, info, _ = rilis_mod.verifikasi(folder / "rilis")
        if lengkap:
            cetak(f"  rilis {info.get('versi')} tiba dan lengkap.")
            return True
        try:
            terhubung = api.koneksi().get(id_utama, {}).get("connected", False)
            sf = api.status_folder(st.RILIS_ID)
            butuh = sf.get("needFiles", 0)
        except Exception:  # noqa: BLE001
            terhubung, butuh = False, 0
        # "Terhubung" saja belum berarti diterima: sambungan TLS terbentuk
        # dulu, baru PC utama memutuskan. Anggap menerima kode hanya bila
        # memang ada file yang sedang ditunggu.
        if terhubung and butuh:
            pesan = f"  diterima PC utama, menerima kode... (sisa {butuh} file)"
        else:
            pesan = ("  menunggu PC utama menerima PC ini "
                     "(jalankan UTAMA-3-STATUS-WORKER.bat di PC utama)...")
        if pesan != terakhir:
            cetak(pesan)
            terakhir = pesan
        if batas_detik and time.time() - mulai > batas_detik:
            return False
        time.sleep(5)


def main(konfig: dict, argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="PASANG-WORKER.bat")
    ap.add_argument("--folder", default=str(Path.home() / "AI-TRADE-WORKER"))
    ap.add_argument("--nama", default=None, help="nama PC (lewati pertanyaan)")
    ap.add_argument("--port-gui", type=int, default=st.PORT_GUI)
    ap.add_argument("--tanpa-shortcut", action="store_true")
    ap.add_argument("--tanpa-autostart", action="store_true")
    ap.add_argument("--tanpa-pip", action="store_true")
    ap.add_argument("--bot-otomatis", choices=["y", "n"], default=None,
                    help="jalankan bot otomatis saat Windows menyala")
    ap.add_argument("--tunggu-detik", type=int, default=0,
                    help="batas menunggu kiriman PC utama (0 = tanpa batas)")
    ap.add_argument("--cek", action="store_true", help="hanya periksa bundel lalu keluar")
    # Khusus pengujian di satu PC (lihat syncthing_alat.siapkan_home).
    ap.add_argument("--uji-lokal", type=int, default=None, help=argparse.SUPPRESS)
    ap.add_argument("--alamat-utama", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    id_utama = konfig["id_utama"]
    cetak("=" * 58)
    cetak("  PASANG AI-TRADE WORKER")
    cetak(f"  PC utama : {konfig.get('nama_utama', '?')} ({id_utama[:7]})")
    cetak(f"  Python   : {sys.version.split()[0]} ({sys.executable})")
    cetak("=" * 58)

    if sys.version_info < PYTHON_MIN:
        cetak(f"!! Python {sys.version.split()[0]} terlalu lama; butuh 3.10 atau lebih baru.")
        cetak("   Pasang Python 3.13 dari https://www.python.org/downloads/windows/")
        return 1
    if args.cek:
        cetak("Bundel OK.")
        return 0

    folder = Path(args.folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    berkas_worker = folder / "worker.json"
    lama = {}
    if berkas_worker.exists():
        try:
            lama = json.loads(berkas_worker.read_text(encoding="utf-8"))
        except ValueError:
            lama = {}

    # 1. Nama PC ---------------------------------------------------------
    judul("1. Nama PC")
    nama = args.nama or lama.get("nama") or tanya(
        "Nama PC ini (contoh: PC Kantor)", socket.gethostname()
    )
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import rilis as rilis_mod

    kunci = rilis_mod.slug(nama)
    cetak(f"  Nama: {nama}   ->  kunci penugasan: {kunci}")
    cetak(f"  Folder: {folder}")

    # 2. Syncthing -------------------------------------------------------
    judul("2. Syncthing")
    exe = st.unduh(folder / "syncthing", cetak)
    home = folder / "syncthing" / "home"
    st.siapkan_home(exe, home, args.port_gui, args.uji_lokal)
    api = st.pastikan_jalan(exe, home, cetak)
    api.ganti_nama_saya(f"AI-TRADE worker: {nama}")
    alamat = [args.alamat_utama] if args.alamat_utama else None
    api.pasang_perangkat(id_utama, konfig.get("nama_utama", "PC UTAMA"), alamat)

    (folder / "rilis").mkdir(exist_ok=True)
    logs = folder / "bot" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / ".stignore").write_text(ISI_STIGNORE, encoding="utf-8")
    # Nama PC dibaca bot (journal_gabung.nama_pc) untuk nama file journal.
    (logs / "nama_pc.txt").write_text(nama + "\n", encoding="utf-8")

    api.pasang_folder(
        st.RILIS_ID, "AI-TRADE rilis (dari PC utama)", folder / "rilis",
        "receiveonly", [id_utama], rescanIntervalS=3600,
    )
    api.pasang_folder(
        st.PREFIKS_LAPORAN + kunci, f"AI-TRADE laporan {nama}", logs,
        "sendonly", [id_utama], rescanIntervalS=300, fsWatcherDelayS=60,
    )
    cetak("  folder rilis (menerima) dan laporan (mengirim) terpasang.")

    if not args.tanpa_autostart:
        try:
            lnk = st.autostart_syncthing(exe, home, "AI-TRADE Syncthing")
            cetak(f"  Syncthing menyala otomatis saat Windows login ({lnk.name}).")
        except st.GagalSyncthing as e:
            cetak(f"  !! gagal membuat autostart Syncthing: {e}")

    data_worker = {
        "nama": nama, "kunci": kunci, "id_utama": id_utama,
        "syncthing_exe": str(exe), "syncthing_home": str(home),
        "dipasang": lama.get("dipasang") or time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    berkas_worker.write_text(json.dumps(data_worker, indent=2), encoding="utf-8")

    # 3. Terima kode dari PC utama ---------------------------------------
    judul("3. Menghubungkan ke PC utama")
    cetak("  ID PC INI (dibutuhkan PC utama):")
    cetak(f"    {api.id_saya()}")
    cetak()
    cetak("  Di PC UTAMA: klik dua kali UTAMA-3-STATUS-WORKER.bat,")
    cetak(f"  lalu jawab 'y' saat ditanya menerima '{nama}'.")
    cetak("  Jendela ini menunggu otomatis - biarkan terbuka.")
    if not tunggu_rilis(api, folder, id_utama, args.tunggu_detik):
        cetak("!! Kode belum tiba. Klik dua kali file pemasang ini lagi nanti.")
        return 2

    # 4. Paket Python ----------------------------------------------------
    judul("4. Paket Python")
    venv_py = folder / "venv" / "Scripts" / "python.exe"
    if not venv_py.exists():
        cetak("  membuat venv...")
        if _jalankan([sys.executable, "-m", "venv", str(folder / "venv")]) != 0:
            cetak("!! gagal membuat venv")
            return 1
    if args.tanpa_pip:
        cetak("  (pip dilewati)")
    else:
        cetak("  memasang paket (beberapa menit, sekali saja)...")
        req = folder / "rilis" / "requirements.txt"
        kode = _jalankan([str(venv_py), "-m", "pip", "install", "--disable-pip-version-check",
                          "-r", str(req)])
        if kode != 0:
            cetak("!! pip install gagal - periksa koneksi internet lalu jalankan pemasang lagi.")
            return 1
        (folder / "venv" / "requirements.sha256").write_text(
            rilis_mod.sha256_file(req), encoding="utf-8"
        )

    # 5. Peluncur & shortcut ---------------------------------------------
    judul("5. Peluncur")
    peluncur = folder / "AI-TRADE-WORKER.bat"
    peluncur.write_bytes(ISI_PELUNCUR.replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii"))
    cetak(f"  {peluncur}")
    if not args.tanpa_shortcut:
        try:
            desktop = st.folder_khusus("Desktop") / "AI-TRADE Worker.lnk"
            st.buat_shortcut(desktop, peluncur)
            cetak(f"  shortcut desktop: {desktop.name}")
        except st.GagalSyncthing as e:
            cetak(f"  !! gagal membuat shortcut desktop: {e}")
            cetak(f"     Jalankan langsung: {peluncur}")

        otomatis = args.bot_otomatis
        if otomatis is None:
            otomatis = "y" if tanya_ya("Jalankan bot otomatis setiap Windows menyala?") else "n"
        lnk_bot = None
        try:
            lnk_bot = st.folder_khusus("Startup") / "AI-TRADE Worker.lnk"
            if otomatis == "y":
                st.buat_shortcut(lnk_bot, peluncur, diperkecil=True)
                cetak("  bot menyala otomatis saat Windows login.")
            elif lnk_bot.exists():
                lnk_bot.unlink()
        except (st.GagalSyncthing, OSError) as e:
            cetak(f"  !! gagal mengatur autostart bot: {e}")

    judul("SELESAI")
    cetak(f"  Nama PC      : {nama}  (kunci penugasan: {kunci})")
    cetak("  Menjalankan  : klik dua kali 'AI-TRADE Worker' di desktop")
    cetak("  Varian       : diatur dari PC utama (config/penugasan.yaml)")
    cetak()
    cetak("  Sebelum menjalankan: MT5 terbuka, login ke akun DEMO, Algo Trading hijau.")
    if not args.tanpa_shortcut and tanya_ya("Jalankan worker sekarang?"):
        os.startfile(str(peluncur))  # jendela baru, pemasang boleh ditutup
    return 0
