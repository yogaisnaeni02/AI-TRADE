@echo off
cd /d "%~dp0"
title AI-TRADE - siapkan PC utama

rem Sekali saja di PC UTAMA (tempat kode diubah dan hasil dianalisis).
rem Aman diulang. Lihat docs/51-CARA-RUN-DI-PC-LAIN.md bagian A.

echo ============================================
echo   SIAPKAN PC UTAMA
echo ============================================
echo.

if exist ".venv\Scripts\python.exe" goto venv_siap
echo [venv] Membuat .venv dan memasang paket (beberapa menit, sekali saja)...
python -m venv .venv
if errorlevel 1 (
    echo !! Gagal membuat venv. Pastikan Python 3.10+ terpasang dan ada di PATH.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt pytest
if errorlevel 1 (
    echo !! pip install gagal - periksa koneksi internet lalu jalankan lagi.
    pause
    exit /b 1
)

:venv_siap
".venv\Scripts\python.exe" scripts\pc_worker\siapkan_utama.py %*
pause
