@echo off
cd /d "%~dp0"
title AI-TRADE - ADVISOR (sinyal saja)

rem Aktifkan venv bila ada. Tanpa ini, .bat memakai python sistem yang
rem kemungkinan belum punya MetaTrader5/pandas terpasang.
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

echo ============================================
echo   MODE ADVISOR - sinyal saja, TIDAK eksekusi
echo   Tekan Ctrl+C untuk berhenti
echo ============================================
python run_bot.py --advisor
pause
