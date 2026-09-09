@echo off
cd /d "%~dp0"
echo ============================================
echo   DASHBOARD - buka http://localhost:8501
echo ============================================
streamlit run src/monitoring/dashboard.py
pause
