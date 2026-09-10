@echo off
cd /d "%~dp0"
title AI-TRADE - EXECUTOR (auto trading)

rem Aktifkan venv bila ada. Tanpa ini, .bat memakai python sistem yang
rem kemungkinan belum punya MetaTrader5/pandas terpasang.
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

echo ============================================
echo   MODE EXECUTOR - bot buka posisi SENDIRI
echo ============================================
echo.
echo Jendela ini HARUS tetap terbuka selama bot jalan.
echo Ganti virtual desktop (Win+Tab) aman - bot tetap jalan.
echo Menutup jendela ini atau Ctrl+C akan menghentikan bot.
echo.
echo Pastikan ini akun DEMO. Tekan Ctrl+C sekarang jika bukan.
timeout /t 5
python run_bot.py
echo.
echo === BOT BERHENTI ===
pause
