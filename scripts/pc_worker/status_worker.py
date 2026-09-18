"""Terima PC worker baru dan tampilkan status semua worker.

    python scripts/pc_worker/status_worker.py      (lewat UTAMA-3-STATUS-WORKER.bat)

1. Worker yang baru dipasang dan minta terhubung ditanyakan satu per
   satu. Yang diterima mendapat folder rilis, dan laporannya ditampung di
   laporan/<kunci-pc>/.
2. Untuk tiap worker: terhubung atau tidak, kabar terakhir, versi kode,
   varian, equity, posisi, rem hari ini, dan baris [status] terakhir.
3. Journal semua worker digabung ke laporan/trades_gabungan.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO))

import rilis  # noqa: E402
import syncthing_alat as st  # noqa: E402

KONFIG_UTAMA = REPO / "pc_utama.json"
BASI_MENIT = 5  # status_worker.json ditulis tiap 30 detik, dikirim ~1 menit


def tanya_ya(teks: str) -> bool:
    try:
        return input(f"{teks} (y/n): ").strip().lower().startswith("y")
    except EOFError:
        return False


def terima_worker(api: st.Api, laporan: Path, otomatis: bool) -> None:
    """Terima perangkat tertunda, lalu folder laporan yang mereka tawarkan."""
    baru = []
    for dev_id, info in api.tertunda_perangkat().items():
        nama = info.get("name") or "(tanpa nama)"
        print(f"\n  Worker baru minta terhubung: {nama}")
        print(f"    ID     : {dev_id}")
        print(f"    alamat : {info.get('address', '?')}")
        if otomatis or tanya_ya("    Terima worker ini?"):
            api.pasang_perangkat(dev_id, nama)
            api.bagikan_folder(st.RILIS_ID, dev_id)
            baru.append(dev_id)
            print("    diterima - kode dikirim begitu keduanya terhubung.")
        else:
            print("    dilewati (akan ditanyakan lagi lain kali).")

    # Folder laporan baru ditawarkan worker SETELAH koneksi terbentuk,
    # jadi untuk worker yang baru diterima tunggu sebentar.
    batas = time.time() + (90 if baru else 0)
    while True:
        diterima = _terima_folder_laporan(api, laporan)
        if not baru or all(d in diterima for d in baru) or time.time() > batas:
            break
        time.sleep(3)
    for d in baru:
        if d not in diterima:
            print(f"  (laporan {d[:7]} belum ditawarkan - jalankan file ini lagi nanti)")


def _terima_folder_laporan(api: st.Api, laporan: Path) -> set[str]:
    diterima: set[str] = set()
    for folder_id, info in api.tertunda_folder().items():
        if not folder_id.startswith(st.PREFIKS_LAPORAN):
            continue
        for dev_id, tawaran in info.get("offeredBy", {}).items():
            if api.perangkat(dev_id) is None:
                continue  # hanya dari worker yang sudah diterima
            kunci = folder_id[len(st.PREFIKS_LAPORAN):]
            tujuan = laporan / kunci
            tujuan.mkdir(parents=True, exist_ok=True)
            api.pasang_folder(folder_id, tawaran.get("label") or folder_id, tujuan,
                              "receiveonly", [dev_id], rescanIntervalS=3600)
            print(f"  laporan '{kunci}' ditampung di {tujuan}")
            diterima.add(dev_id)
    return diterima


def _json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _angka(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _umur(iso: Optional[str]) -> Optional[timedelta]:
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - t


def _teks_umur(d: Optional[timedelta]) -> str:
    if d is None:
        return "belum pernah"
    menit = int(d.total_seconds() // 60)
    if menit < 1:
        return "barusan"
    if menit < 120:
        return f"{menit} menit lalu"
    return f"{menit // 60} jam lalu"


def _baris_terakhir(folder: Path, kata: str) -> Optional[str]:
    logs = sorted(folder.glob("bot_*.log"))
    if not logs:
        return None
    try:
        for baris in reversed(logs[-1].read_text(encoding="utf-8", errors="replace").splitlines()):
            if kata in baris:
                return baris.strip()
    except OSError:
        pass
    return None


def ringkas_trade(files: list[Path]) -> tuple[int, int, float]:
    """(total trade, trade minggu ini, P/L minggu ini)."""
    senin = datetime.now().date() - timedelta(days=datetime.now().weekday())
    total = minggu = 0
    pnl = 0.0
    for f in files:
        try:
            with open(f, encoding="utf-8", newline="") as fh:
                for r in csv.DictReader(fh):
                    total += 1
                    try:
                        keluar = datetime.fromisoformat(r.get("exit_time") or "").date()
                    except ValueError:
                        continue
                    if keluar >= senin:
                        minggu += 1
                        pnl += _angka(r.get("net_idr"))
        except OSError:
            continue
    return total, minggu, pnl


def tampilkan(api: Optional[st.Api], laporan: Path, rilis_dir: Path) -> None:
    terbaru = rilis.baca_versi(rilis_dir) or {}
    penugasan = terbaru.get("penugasan") or rilis.baca_penugasan(REPO)
    koneksi = api.koneksi() if api else {}
    folder_cfg = {}
    if api:
        for f in api.get("/rest/config/folders"):
            if f["id"].startswith(st.PREFIKS_LAPORAN):
                folder_cfg[f["id"][len(st.PREFIKS_LAPORAN):]] = f

    print(f"\nRilis terbaru: {terbaru.get('versi', 'belum pernah diterbitkan')}")
    kunci_semua = set(folder_cfg)
    if laporan.exists():
        kunci_semua |= {p.name for p in laporan.iterdir() if p.is_dir()}
    kunci_semua = sorted(kunci_semua)
    if not kunci_semua:
        print("\nBelum ada worker. Kirim PASANG-WORKER.bat ke PC worker.")

    for kunci in kunci_semua:
        folder = laporan / kunci
        stt = _json(folder / "status_worker.json")
        snap = _json(folder / "snapshot.json")
        devs = [d["deviceID"] for d in folder_cfg.get(kunci, {}).get("devices", [])]
        terhubung = any(koneksi.get(d, {}).get("connected") for d in devs)
        umur = _umur(stt.get("waktu_utc"))
        basi = umur is None or umur > timedelta(minutes=BASI_MENIT)

        print("\n" + "-" * 58)
        print(f"{stt.get('nama', kunci)}  [{kunci}]  "
              f"{'TERHUBUNG' if terhubung else 'TIDAK TERHUBUNG'} | kabar {_teks_umur(umur)}"
              f"{'  !! BASI' if basi else ''}")
        keadaan = stt.get("keadaan", "?")
        print(f"  keadaan : {keadaan}{' - ' + stt['pesan'] if stt.get('pesan') else ''}")
        versi = stt.get("versi_bot")
        catatan = ""
        if versi and terbaru.get("versi") and versi != terbaru["versi"]:
            catatan = "  !! belum versi terbaru"
        print(f"  versi   : {versi or '?'}{catatan}")
        tugas = penugasan.get(kunci)
        if tugas != stt.get("varian"):
            print(f"  varian  : {stt.get('varian')}  (penugasan: {tugas or 'tidak ada'})")
        else:
            print(f"  varian  : {tugas}")
        if snap:
            print(f"  akun    : equity Rp {_angka(snap.get('equity')):,.0f} | "
                  f"posisi {snap.get('open_positions', '?')} | hari ini "
                  f"{snap.get('day_trades', '?')} trade, P/L Rp {_angka(snap.get('day_pnl')):,.0f}"
                  f"{' | HALT' if snap.get('halted') else ''}")
        total, minggu, pnl = ringkas_trade(sorted(folder.glob("trades__*.csv")))
        print(f"  trade   : {total} tercatat | minggu ini {minggu}, P/L Rp {pnl:,.0f}")
        terakhir = _baris_terakhir(folder, "[status]")
        if terakhir:
            print(f"  status  : {terakhir}")

    tanpa_worker = sorted(set(penugasan) - set(kunci_semua))
    if tanpa_worker:
        print("\nDitugaskan tapi belum ada worker-nya: " + ", ".join(tanpa_worker))


def tulis_gabungan(laporan: Path) -> Optional[Path]:
    from src.monitoring.journal_gabung import baca_semua

    files = sorted(laporan.glob("*/trades__*.csv"))
    if not files:
        return None
    rows = baca_semua(files)
    kolom: list[str] = []
    for r in rows:
        kolom.extend(k for k in r if k not in kolom)
    tujuan = laporan / "trades_gabungan.csv"
    with open(tujuan, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=kolom, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return tujuan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--terima-semua", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--konfig", default=str(KONFIG_UTAMA), help=argparse.SUPPRESS)
    args = ap.parse_args()

    k = _json(Path(args.konfig))
    if not k:
        print("!! PC utama belum disiapkan - jalankan UTAMA-1-SIAPKAN.bat dulu.")
        return 1
    laporan, rilis_dir = Path(k["laporan"]), Path(k["rilis"])

    print("=" * 58)
    print(f"  STATUS WORKER  -  {datetime.now():%d %b %Y %H:%M}")
    print("=" * 58)
    api = None
    try:
        api = st.pastikan_jalan(Path(k["syncthing_exe"]), Path(k["syncthing_home"]))
        terima_worker(api, laporan, args.terima_semua)
    except Exception as e:  # noqa: BLE001
        print(f"!! Syncthing bermasalah: {e}")
        print("   Status di bawah dari laporan terakhir yang sudah tiba.")

    tampilkan(api, laporan, rilis_dir)
    p = tulis_gabungan(laporan)
    if p:
        print(f"\nJournal gabungan semua worker: {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
