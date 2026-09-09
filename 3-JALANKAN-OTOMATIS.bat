@echo off
cd /d "%~dp0"
echo ============================================
echo   MODE EXECUTOR - bot buka posisi SENDIRI
echo   Tekan Ctrl+C untuk berhenti
echo ============================================
echo.
echo Pastikan ini akun DEMO. Tekan Ctrl+C sekarang jika bukan.
timeout /t 5
python run_bot.py
pause
