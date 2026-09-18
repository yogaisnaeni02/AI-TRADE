"""Siapkan PC utama: Syncthing, folder rilis, dan file pemasang worker.

    python scripts/pc_worker/siapkan_utama.py      (lewat UTAMA-1-SIAPKAN.bat)

Sekali saja per PC utama; aman diulang. Hasil akhirnya PASANG-WORKER.bat
di folder repo - file itulah yang dikirim ke PC worker.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import sys
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SINI = Path(__file__).resolve().parent
sys.path.insert(0, str(SINI))

import syncthing_alat as st  # noqa: E402

KONFIG_UTAMA = REPO / "pc_utama.json"
BAT_WORKER = REPO / "PASANG-WORKER.bat"
PENANDA = "#==PYTHON=="

# Berkas yang dibundel ke dalam PASANG-WORKER.bat.
BUNDEL = ("syncthing_alat.py", "rilis.py", "pasang_worker.py")

# Bagian .bat: cari/pasang Python, lalu ekstrak bagian Python di bawah
# PENANDA ke file sementara dan jalankan. Semua ASCII, baris CRLF.
TEMPLAT_BAT = r"""@echo off
setlocal
title AI-TRADE Worker - pemasangan
echo Memeriksa Python...

call :cari_python
if defined PY goto python_siap

echo Python belum terpasang. Memasang Python 3.13 lewat winget...
where winget >nul 2>nul
if errorlevel 1 goto python_manual
winget install -e --id Python.Python.3.13 --scope user --accept-package-agreements --accept-source-agreements
call :cari_python
if defined PY goto python_siap

:python_manual
echo.
echo !! Python tidak bisa dipasang otomatis.
echo    1. Unduh Python dari https://www.python.org/downloads/windows/
echo    2. Saat memasang, centang "Add python.exe to PATH"
echo    3. Klik dua kali file ini lagi
echo.
pause
exit /b 1

:python_siap
set "SKRIP=%TEMP%\aitrade_pasang_%RANDOM%.py"
set BARIS=
for /f "delims=:" %%A in ('findstr /n /b /c:"__PENANDA__" "%~f0"') do set BARIS=%%A
if not defined BARIS (
    echo !! File pemasang rusak - minta file baru dari PC utama.
    pause
    exit /b 1
)
more +%BARIS% "%~f0" > "%SKRIP%"
"%PY%" "%SKRIP%" %*
set KODE=%ERRORLEVEL%
del "%SKRIP%" >nul 2>nul
echo.
pause
exit /b %KODE%

:cari_python
set "PY="
for /f "delims=" %%E in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%E"
if defined PY exit /b 0
for /f "delims=" %%E in ('python -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%E"
if defined PY exit /b 0
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PY=%%D\python.exe"
exit /b 0

__PENANDA__
"""

TEMPLAT_PY = '''# AI-TRADE worker - pemasang. Dibuat otomatis oleh UTAMA-1-SIAPKAN.bat.
import base64, json, sys, tempfile, zlib
from pathlib import Path

KONFIG = json.loads(__KONFIG__)
BERKAS = {
__BERKAS__
}

folder = Path(tempfile.mkdtemp(prefix="aitrade_pasang_"))
for nama, isi in BERKAS.items():
    (folder / nama).write_bytes(zlib.decompress(base64.b64decode("".join(isi.split()))))
sys.path.insert(0, str(folder))
import pasang_worker
sys.exit(pasang_worker.main(KONFIG, sys.argv[1:]))
'''


def buat_bat_worker(id_utama: str, nama_utama: str, tujuan: Path = BAT_WORKER) -> Path:
    """Bundel pemasang worker + ID PC utama ke satu file .bat."""
    potongan = []
    for nama in BUNDEL:
        b64 = base64.b64encode(zlib.compress((SINI / nama).read_bytes(), 9)).decode("ascii")
        baris = "\n".join(b64[i:i + 76] for i in range(0, len(b64), 76))
        potongan.append(f'    {nama!r}: """\n{baris}\n""",')
    konfig = json.dumps({"id_utama": id_utama, "nama_utama": nama_utama})
    py = (TEMPLAT_PY
          .replace("__KONFIG__", repr(konfig))
          .replace("__BERKAS__", "\n".join(potongan)))
    teks = TEMPLAT_BAT.replace("__PENANDA__", PENANDA) + py
    # `more` di cmd membaca sesuai codepage konsol: harus ASCII murni.
    teks.encode("ascii")
    tujuan.write_bytes(teks.replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii"))
    return tujuan


def main() -> int:
    lokal = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "AI-TRADE-Syncthing"
    ap = argparse.ArgumentParser()
    ap.add_argument("--rilis", default=str(REPO.parent / "AI-TRADE-rilis"))
    ap.add_argument("--laporan", default=str(REPO / "laporan"))
    ap.add_argument("--syncthing", default=str(lokal), help="folder syncthing.exe dan datanya")
    ap.add_argument("--port-gui", type=int, default=st.PORT_GUI)
    ap.add_argument("--nama", default=f"AI-TRADE utama ({socket.gethostname()})")
    ap.add_argument("--tanpa-autostart", action="store_true")
    ap.add_argument("--bat-saja", action="store_true",
                    help="hanya buat ulang PASANG-WORKER.bat dari pc_utama.json")
    ap.add_argument("--uji-lokal", type=int, default=None, help=argparse.SUPPRESS)
    ap.add_argument("--konfig", default=str(KONFIG_UTAMA), help=argparse.SUPPRESS)
    ap.add_argument("--bat", default=str(BAT_WORKER), help=argparse.SUPPRESS)
    args = ap.parse_args()
    berkas_konfig = Path(args.konfig)

    print("=" * 58)
    print("  SIAPKAN PC UTAMA")
    print("=" * 58)

    if args.bat_saja:
        k = json.loads(berkas_konfig.read_text(encoding="utf-8"))
        p = buat_bat_worker(k["device_id"], k["nama"], Path(args.bat))
        print(f"  {p}")
        return 0

    rilis_dir = Path(args.rilis).resolve()
    laporan_dir = Path(args.laporan).resolve()
    folder_st = Path(args.syncthing).resolve()
    home = folder_st / "home"

    print("\n[1/4] Syncthing")
    try:
        exe = st.unduh(folder_st)
        st.siapkan_home(exe, home, args.port_gui, args.uji_lokal)
        api = st.pastikan_jalan(exe, home)
    except st.GagalSyncthing as e:
        print(f"!! {e}")
        return 1
    api.ganti_nama_saya(args.nama)
    id_saya = api.id_saya()
    print(f"  berjalan - ID PC utama: {id_saya[:7]}...")

    print("\n[2/4] Folder rilis dan laporan")
    rilis_dir.mkdir(parents=True, exist_ok=True)
    laporan_dir.mkdir(parents=True, exist_ok=True)
    api.pasang_folder(st.RILIS_ID, "AI-TRADE rilis (ke worker)", rilis_dir, "sendonly", [],
                      rescanIntervalS=3600)
    print(f"  rilis   : {rilis_dir}  (hanya mengirim)")
    print(f"  laporan : {laporan_dir}  (satu subfolder per worker)")

    print("\n[3/4] Autostart")
    if args.tanpa_autostart:
        print("  dilewati")
    else:
        try:
            lnk = st.autostart_syncthing(exe, home, "AI-TRADE Syncthing (utama)")
            print(f"  Syncthing menyala otomatis saat Windows login ({lnk.name})")
        except st.GagalSyncthing as e:
            print(f"  !! gagal membuat autostart: {e}")

    konfig = {
        "nama": args.nama, "device_id": id_saya,
        "syncthing_exe": str(exe), "syncthing_home": str(home),
        "rilis": str(rilis_dir), "laporan": str(laporan_dir),
    }
    berkas_konfig.write_text(json.dumps(konfig, indent=2), encoding="utf-8")

    print("\n[4/4] File pemasang worker")
    bat = buat_bat_worker(id_saya, args.nama, Path(args.bat))
    print(f"  {bat}")

    print("\nSelesai. Langkah berikutnya:")
    print("  1. UTAMA-2-TERBITKAN.bat   -> kirim kode ke folder rilis")
    print("  2. Kirim PASANG-WORKER.bat ke PC worker, klik dua kali di sana")
    print("  3. UTAMA-3-STATUS-WORKER.bat -> terima worker baru & pantau")
    return 0


if __name__ == "__main__":
    sys.exit(main())
