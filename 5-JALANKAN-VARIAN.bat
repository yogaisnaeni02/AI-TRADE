@echo off
cd /d "%~dp0"
title AI-TRADE - pilih varian

rem Aktifkan venv bila ada. Tanpa ini, .bat memakai python sistem yang
rem kemungkinan belum punya MetaTrader5/pandas terpasang.
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

echo ============================================
echo   JALANKAN BOT AI-TRADE
echo ============================================

rem -- 1. Nama PC untuk notifikasi Telegram ------------------------------
rem
rem Ditanya sekali lalu DIINGAT di logs\nama_pc.txt, supaya tidak perlu
rem mengetik ulang tiap menjalankan bot. Hapus file itu untuk mengganti.
rem
rem Tanpa label ini, notifikasi dari beberapa PC tidak bisa dibedakan di
rem Telegram - masalah nyata saat menjalankan bot di lebih dari satu PC.
set NAMAPC=
if exist "logs\nama_pc.txt" (
    for /f "usebackq delims=" %%N in ("logs\nama_pc.txt") do set NAMAPC=%%N
)

if not "%NAMAPC%"=="" goto nama_siap

echo.
echo Nama PC ini untuk notifikasi Telegram, mis. PC Rumah
echo Kosongkan lalu Enter untuk memakai nama Windows apa adanya.
echo.
set /p NAMAPC="Nama PC: "
if "%NAMAPC%"=="" goto nama_siap
if not exist "logs" mkdir "logs"
> "logs\nama_pc.txt" echo %NAMAPC%

:nama_siap
if "%NAMAPC%"=="" goto pilih_varian
echo.
echo Nama PC: %NAMAPC%    (hapus logs\nama_pc.txt untuk mengganti)

rem -- 2. Pilih varian ---------------------------------------------------
:pilih_varian
echo.
echo --------------------------------------------
echo   VARIAN YANG TERSEDIA
echo --------------------------------------------
python -m src.variants
echo.
echo Ketik NOMOR varian dari kolom "no" (nama lengkap juga boleh),
echo atau kosongkan lalu Enter untuk memakai config apa adanya (settings.yaml).
echo.
rem Dikosongkan dulu: set /p yang dijawab Enter kosong MEMPERTAHANKAN nilai
rem lama, sehingga pilihan salah sebelumnya akan terpakai lagi.
set PILIH=
set VARIAN=
set /p PILIH="Nomor varian: "

rem Terjemahkan nomor -> nama varian SEBELUM bot dijalankan.
rem
rem Tanpa ini, salah ketik baru ketahuan setelah menunggu 5 detik, lalu
rem gagal dengan traceback Python yang terlihat menakutkan - padahal cuma
rem typo. Mengetik nomor menghilangkan typo nama sama sekali.
if "%PILIH%"=="" goto varian_ok
for /f "delims=" %%V in ('python -m src.variants --pilih "%PILIH%"') do set VARIAN=%%V
if "%VARIAN%"=="" (
    echo.
    echo !! Pilihan "%PILIH%" tidak ada di daftar - ketik nomornya, mis. 4
    echo.
    goto pilih_varian
)
echo Varian terpilih: %VARIAN%

:varian_ok
set ARG=
set JUDUL=config apa adanya
if not "%VARIAN%"=="" set ARG=--varian %VARIAN%
if not "%VARIAN%"=="" set JUDUL=%VARIAN%
if not "%NAMAPC%"=="" set ARG=%ARG% --nama-pc "%NAMAPC%"

title AI-TRADE - %JUDUL%
echo.
echo ============================================
echo   MODE EXECUTOR - bot buka posisi SENDIRI
echo   Varian : %JUDUL%
echo   PC     : %NAMAPC%
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
echo [%date% %time%] menjalankan bot (varian: %JUDUL%)...
python run_bot.py %ARG%
set KODE=%ERRORLEVEL%

rem Keluar bersih (Ctrl+C / berhenti disengaja) -> jangan restart.
if "%KODE%"=="0" goto selesai

rem Akun REAL tanpa --allow-real keluar dengan kode 1: itu penolakan
rem yang disengaja, bukan crash. Jangan dinyalakan ulang.
if "%KODE%"=="1" (
    echo.
    echo [%date% %time%] bot menolak jalan ^(kode 1^) - TIDAK dinyalakan ulang.
    echo Periksa pesan di atas: kemungkinan akun REAL, varian salah ketik,
    echo atau konfigurasi bermasalah.
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
