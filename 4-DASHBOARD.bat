@echo off
cd /d "%~dp0"
title AI-TRADE - Dashboard

rem Aktifkan venv bila ada. Tanpa ini, .bat memakai python sistem yang
rem kemungkinan belum punya MetaTrader5/pandas terpasang.
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

echo ============================================
echo   DASHBOARD - buka http://localhost:8501
echo ============================================
echo Aman dijalankan bersamaan dengan bot: dashboard
echo membaca file log, tidak connect ke MT5.
echo.
streamlit run src/monitoring/dashboard.py
pause
