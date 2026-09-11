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
echo.
echo Bot akan DINYALAKAN ULANG OTOMATIS bila berhenti tak terduga.
echo Untuk berhenti permanen: tutup jendela ini, atau Ctrl+C lalu pilih Y.
echo.
echo Pastikan ini akun DEMO. Tekan Ctrl+C sekarang jika bukan.
timeout /t 5

:jalan
echo.
echo [%date% %time%] menjalankan bot...
python run_bot.py
set KODE=%ERRORLEVEL%

rem Keluar bersih (Ctrl+C / berhenti disengaja) -> jangan restart.
if "%KODE%"=="0" goto selesai

rem Akun REAL tanpa --allow-real keluar dengan kode 1: itu penolakan
rem yang disengaja, bukan crash. Jangan dinyalakan ulang.
if "%KODE%"=="1" (
    echo.
    echo [%date% %time%] bot menolak jalan ^(kode 1^) - TIDAK dinyalakan ulang.
    echo Periksa pesan di atas: kemungkinan akun REAL atau konfigurasi salah.
    goto selesai
)

echo.
echo [%date% %time%] bot berhenti tak terduga ^(kode %KODE%^).
echo Menyalakan ulang dalam 30 detik... tekan Ctrl+C untuk membatalkan.
timeout /t 30
goto jalan

:selesai
echo.
echo === BOT BERHENTI ===
pause
