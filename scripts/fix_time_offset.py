"""
Perbaiki kolom `time_utc` yang bergeser 7 jam di data historis.

LATAR BELAKANG
--------------
`src/data/downloader.py` mengurangi `broker.server_utc_offset` (= 7) dari
waktu server MT5 lalu menamainya `time_utc`. Nilai 7 itu salah: server
broker ini UTC+0, sehingga epoch mentah dari MT5 SUDAH UTC dan pengurangan
tersebut menggeser seluruh data 7 jam ke belakang.

BUKTI (dari data itu sendiri, bukan dari config)
------------------------------------------------
Pasar forex tutup Jumat dan buka Minggu sekitar 21:00-22:00 UTC (17:00 New
York). Pada `data/raw/XAUUSDm_M5.parquet`:

    kolom          Jumat tutup   Minggu buka
    time_utc          14:55         15:00     <- meleset 7 jam
    time_server       21:55         22:00     <- cocok dengan kenyataan

Jadi `time_server` justru UTC yang benar, dan `time_utc` = UTC - 7 jam.

APA YANG DILAKUKAN SKRIP INI
----------------------------
Untuk file yang punya `time_server`  : time_utc <- time_server
Untuk file yang tidak punya          : time_utc <- time_utc + 7 jam
                                       (hanya bila terbukti bergeser)

File yang sudah benar DILEWATI. Deteksinya memakai batas akhir pekan, jadi
skrip ini aman dijalankan berulang (idempoten).

`data_corr/` sengaja tidak ikut diperbaiki: pemeriksaan menunjukkan
time_utc-nya sudah benar (tutup Jumat 21:55).

PEMAKAIAN
---------
    python scripts/fix_time_offset.py --check    # laporan saja, tidak menulis
    python scripts/fix_time_offset.py            # terapkan
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# HANYA data/raw. data_corr/ sudah benar - jangan disentuh.
#
# data/processed SENGAJA TIDAK ADA DI SINI (diperbaiki 10 Sep 2026).
#
# Skrip ini hanya menggeser kolom `time_utc`. File di data/processed juga
# menyimpan kolom TURUNAN waktu - session, session_date, is_trading_session,
# hour_utc, dayofweek, friday_cutoff, asia_high/low, sweep_* - dan kolom itu
# TIDAK ikut tergeser. Hasilnya file dengan time_utc benar tetapi label sesi
# masih salah 7 jam: jauh lebih berbahaya daripada file yang jelas-jelas
# salah, karena semuanya tampak konsisten padahal tidak.
#
# Itu benar-benar terjadi: backtest memblokir 7 jam penuh (termasuk seluruh
# sesi London) karena label basi, sementara bot live menghitung sesi dengan
# benar - backtest dan live menguji jam yang berbeda lagi.
#
# Cara yang benar untuk data/processed: BANGUN ULANG dari raw.
#     python -m src.features.pipeline
TARGET_GLOBS = ["data/raw/*.parquet"]

# Kehadiran kolom-kolom ini menandakan file harus DIBANGUN ULANG, bukan digeser.
DERIVED_TIME_COLUMNS = [
    "session", "session_date", "is_trading_session", "hour_utc",
    "dayofweek", "friday_cutoff", "asia_high", "asia_low",
]

OFFSET_HOURS = 7

# Ambang deteksi: bar Jumat terakhir pada data yang benar jatuh di atas jam
# ini (pasar tutup 21:00-22:00 UTC). Data yang bergeser -7 jatuh sekitar
# 14:00-15:00, jauh di bawahnya.
FRIDAY_CLOSE_MIN_HOUR = 19.0


def friday_close_hour(ts: pd.Series) -> float:
    """Jam bar Jumat terakhir, sebagai float. Penanda apakah data bergeser."""
    fri = ts[ts.dt.dayofweek == 4]
    if fri.empty:
        return float("nan")
    last = fri.dt.hour + fri.dt.minute / 60.0
    return float(last.max())


def classify(path: Path) -> tuple[str, str]:
    """Kembalikan (aksi, alasan) tanpa menulis apa pun."""
    df = pd.read_parquet(path)
    if "time_utc" not in df.columns:
        return "lewati", "tidak ada kolom time_utc"

    tu = pd.to_datetime(df["time_utc"])
    fri = friday_close_hour(tu)

    if pd.isna(fri):
        return "lewati", "tidak ada bar Jumat untuk diperiksa"

    if fri >= FRIDAY_CLOSE_MIN_HOUR:
        return "lewati", f"sudah benar (Jumat tutup {fri:.2f})"

    if "time_server" in df.columns:
        ts = pd.to_datetime(df["time_server"])
        delta = (ts - tu).unique()
        if len(delta) != 1:
            return "gagal", f"selisih time_server-time_utc tidak seragam: {delta}"
        gap = pd.Timedelta(delta[0]).total_seconds() / 3600
        if abs(gap - OFFSET_HOURS) > 1e-9:
            return "gagal", f"selisih {gap} jam, diharapkan {OFFSET_HOURS}"
        return "salin_server", f"Jumat tutup {fri:.2f} -> pakai time_server"

    return "geser", f"Jumat tutup {fri:.2f} -> tambah {OFFSET_HOURS} jam"


def apply_fix(path: Path, action: str) -> str:
    df = pd.read_parquet(path)
    before = friday_close_hour(pd.to_datetime(df["time_utc"]))

    if action == "salin_server":
        df["time_utc"] = pd.to_datetime(df["time_server"])
    elif action == "geser":
        df["time_utc"] = pd.to_datetime(df["time_utc"]) + pd.Timedelta(hours=OFFSET_HOURS)
    else:
        raise ValueError(action)

    after = friday_close_hour(pd.to_datetime(df["time_utc"]))
    if after < FRIDAY_CLOSE_MIN_HOUR:
        raise RuntimeError(
            f"{path.name}: setelah perbaikan Jumat tutup masih {after:.2f} — dibatalkan"
        )

    df.to_parquet(path, index=False)
    return f"Jumat tutup {before:.2f} -> {after:.2f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="laporan saja, tidak menulis")
    args = ap.parse_args()

    paths: list[Path] = []
    for g in TARGET_GLOBS:
        paths.extend(sorted(ROOT.glob(g)))

    if not paths:
        print("Tidak ada file parquet ditemukan.")
        return 1

    changed = skipped = failed = 0

    for p in paths:
        rel = p.relative_to(ROOT)
        try:
            action, reason = classify(p)
        except Exception as e:  # noqa: BLE001
            print(f"  GAGAL   {rel} — {type(e).__name__}: {e}")
            failed += 1
            continue

        if action == "lewati":
            print(f"  lewati  {rel} — {reason}")
            skipped += 1
        elif action == "gagal":
            print(f"  GAGAL   {rel} — {reason}")
            failed += 1
        elif args.check:
            print(f"  AKAN    {rel} — {reason}")
            changed += 1
        else:
            try:
                detail = apply_fix(p, action)
                print(f"  ok      {rel} — {detail}")
                changed += 1
            except Exception as e:  # noqa: BLE001
                print(f"  GAGAL   {rel} — {type(e).__name__}: {e}")
                failed += 1

    verb = "akan diperbaiki" if args.check else "diperbaiki"
    print(f"\n{changed} {verb}, {skipped} dilewati, {failed} gagal")

    stale = check_processed_stale()
    if stale:
        print()
        print("!! FILE TURUNAN HARUS DIBANGUN ULANG")
        for rel, reason in stale:
            print(f"   {rel} - {reason}")
        print()
        print("   data/processed sengaja tidak disentuh skrip ini: file di")
        print("   sana menyimpan kolom turunan waktu yang tidak ikut tergeser.")
        print("   Jalankan:  python -m src.features.pipeline")
        print()
        return 1

    return 1 if failed else 0


def check_processed_stale() -> list:
    """
    Laporkan file data/processed yang label sesinya tidak cocok dengan
    kolom time_utc-nya.

    Dibandingkan langsung, bukan lewat mtime: sebuah file bisa lebih baru
    dari raw tetapi tetap membawa label yang dihitung pada waktu lama.
    """
    out = []
    try:
        sys.path.insert(0, str(ROOT))
        from src.strategy.sessions import classify_session
    except Exception:  # noqa: BLE001
        return out

    for path in sorted(ROOT.glob("data/processed/*.parquet")):
        try:
            df = pd.read_parquet(path)
        except Exception:  # noqa: BLE001
            continue
        if "time_utc" not in df.columns:
            continue
        rel = str(path.relative_to(ROOT))
        if "session" in df.columns:
            match = (classify_session(pd.to_datetime(df["time_utc"])) == df["session"]).mean()
            if match < 0.999:
                out.append((rel, f"label sesi cocok hanya {match * 100:.1f}% dengan time_utc"))
        else:
            present = [c for c in DERIVED_TIME_COLUMNS if c in df.columns]
            if present:
                out.append((rel, f"kolom turunan tanpa session: {', '.join(present)}"))
    return out


if __name__ == "__main__":
    sys.exit(main())
