@echo off
cd /d "%~dp0"
title AI-TRADE - terbitkan rilis ke worker

rem Kirim kode + config (termasuk config\penugasan.yaml) ke semua PC worker.
rem Kode harus sudah di-commit dan tes harus lulus.

if not exist ".venv\Scripts\python.exe" (
    echo !! Jalankan UTAMA-1-SIAPKAN.bat dulu.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" scripts\pc_worker\terbitkan.py %*
pause
