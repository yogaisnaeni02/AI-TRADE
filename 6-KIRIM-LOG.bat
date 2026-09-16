@echo off
cd /d "%~dp0"
title AI-TRADE - kirim log harian

rem Kirim journal PC ini ke repo, lalu ambil milik PC lain.
rem
rem AMAN dijalankan kapan saja, termasuk saat bot sedang berjalan - yang
rem dikirim hanya file journal, bukan kode.
rem
rem Tidak pernah bentrok karena tiap PC menulis file BERNAMA SENDIRI
rem (trades__<nama-pc>.csv). Dua PC tidak menyentuh file yang sama.

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

echo ============================================
echo   KIRIM LOG TRADE KE REPO
echo ============================================
echo.

rem 0. Buang perubahan pada file RUNTIME sebelum pull.
rem
rem snapshot.json ditulis ulang bot tiap beberapa detik. Kalau file itu
rem masih tercatat di Git pada klon lama, `git pull` akan GAGAL dengan
rem "local changes would be overwritten" setiap kali bot berjalan.
rem Membuangnya aman - bot menulisnya lagi dalam hitungan detik.
git checkout -- logs/snapshot.json 2>nul

rem 1. Ambil dulu milik PC lain. Dilakukan SEBELUM commit supaya tidak
rem    perlu merge di tengah jalan.
echo [1/3] Mengambil log dari PC lain...
git pull --rebase origin main
if errorlevel 1 (
    echo.
    echo !! Gagal mengambil dari remote. Periksa koneksi internet.
    echo    Log lokal TIDAK hilang - coba lagi nanti.
    pause
    exit /b 1
)

rem 2. Kirim journal PC ini.
echo.
echo [2/3] Mengirim log PC ini...
git add logs/trades__*.csv logs/trades.csv 2>nul
git diff --cached --quiet
if errorlevel 1 (
    git commit -q -m "data: log trade dari PC ini"
    git push origin main
    if errorlevel 1 (
        echo.
        echo !! Gagal mengirim. Coba jalankan lagi.
        pause
        exit /b 1
    )
    echo     terkirim.
) else (
    echo     tidak ada trade baru untuk dikirim.
)

rem 3. Bangun file gabungan + tampilkan ringkasan.
rem
rem logs/trades_gabungan.csv berisi trade dari SEMUA PC dalam satu file,
rem siap dibuka di Excel. File ini TURUNAN - tidak ikut Git, dibangun
rem ulang tiap kali skrip ini dijalankan.
echo.
echo [3/3] Menggabungkan log semua PC...
echo.
python -m src.monitoring.journal_gabung

echo.
echo ============================================
pause
