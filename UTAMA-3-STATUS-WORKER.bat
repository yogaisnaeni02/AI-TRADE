@echo off
cd /d "%~dp0"
title AI-TRADE - status worker

rem Terima PC worker baru, lalu tampilkan status semua worker.
rem Aman dijalankan kapan saja, sesering apa pun.

if not exist ".venv\Scripts\python.exe" (
    echo !! Jalankan UTAMA-1-SIAPKAN.bat dulu.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" scripts\pc_worker\status_worker.py %*
pause
