@echo off
cd /d "%~dp0"
echo ============================================
echo   CEK KESIAPAN SISTEM
echo ============================================
python run_bot.py --check
echo.
pause
