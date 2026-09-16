@echo off
cd /d "%~dp0"
title AI-TRADE - lepas rem bot

rem Dipakai ketika bot berhenti membuka posisi dan Anda ingin tahu
rem kenapa, lalu melepaskannya.
rem
rem AMAN: langkah pertama hanya MEMERIKSA, tidak mengubah apa pun.
rem Perubahan baru terjadi setelah Anda menjawab Y.

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

echo ============================================
echo   LEPAS REM BOT
echo ============================================
echo.
echo Rem dihitung TERPISAH untuk tiap varian, jadi ketik varian
echo yang sedang Anda jalankan - kalau salah, angka batas yang
echo ditampilkan juga salah.
echo.
echo   baseline   konfluensi   dua_arah   dua_arah_konfluensi
echo   pyramid5   autoclose    autoclose_agresif
echo.

set VARIAN=
set /p VARIAN=Nama varian (kosongkan = config dasar):

echo.
echo --------------------------------------------
echo   LANGKAH 1: PERIKSA (tidak mengubah apa pun)
echo --------------------------------------------

if "%VARIAN%"=="" (
    python scripts\lepas_rem.py
) else (
    python scripts\lepas_rem.py --varian %VARIAN%
)
if errorlevel 1 (
    echo.
    echo !! Gagal memeriksa. Periksa pesan di atas.
    pause
    exit /b 1
)

echo.
echo --------------------------------------------
set LEPAS=
set /p LEPAS=Lepaskan rem sekarang? [y/N]:
if /i not "%LEPAS%"=="y" (
    echo.
    echo Tidak ada yang diubah.
    pause
    exit /b 0
)

echo.
if "%VARIAN%"=="" (
    python scripts\lepas_rem.py --lepas
) else (
    python scripts\lepas_rem.py --varian %VARIAN% --lepas
)

echo.
echo ============================================
echo   Selesai. Jalankan bot lewat 5-JALANKAN-VARIAN.bat
echo ============================================
pause
