@echo off
cd /d "%~dp0"
title AI-TRADE - kendali Telegram

rem Melayani perintah dari Telegram: lihat status/saldo/P-L dan ganti varian.
rem Jendela ini HARUS tetap terbuka selama kendali dipakai.
rem
rem Hanya chat_id di config\settings.yaml (atau env AI_TRADE_TG_CHAT_ID)
rem yang dilayani. Tidak ada perintah yang bisa menutup posisi atau
rem melepas halt - itu tetap lewat PC utama.

if not exist ".venv\Scripts\python.exe" (
    echo !! Jalankan UTAMA-1-SIAPKAN.bat dulu.
    pause
    exit /b 1
)

:jalan
".venv\Scripts\python.exe" scripts\pc_worker\kendali_telegram.py %*
if "%ERRORLEVEL%"=="0" goto selesai
echo.
echo [%date% %time%] kendali berhenti tak terduga, mencoba lagi dalam 30 detik...
timeout /t 30
goto jalan

:selesai
echo.
echo === KENDALI TELEGRAM BERHENTI ===
pause
