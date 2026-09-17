@echo off
cd /d "%~dp0"
title AI-TRADE - atur varian worker

rem Pilih nomor PC worker lalu nomor varian - tanpa mengetik nama.
rem Hasilnya ditulis ke config\penugasan.yaml, lalu bisa langsung diterbitkan.

if not exist ".venv\Scripts\python.exe" (
    echo !! Jalankan UTAMA-1-SIAPKAN.bat dulu.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" scripts\pc_worker\atur_penugasan.py %*
pause
