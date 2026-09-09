@echo off
cd /d "%~dp0"
echo ============================================
echo   MODE ADVISOR - sinyal saja, TIDAK eksekusi
echo   Tekan Ctrl+C untuk berhenti
echo ============================================
python run_bot.py --advisor
pause
