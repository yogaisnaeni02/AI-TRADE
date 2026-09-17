"""Peluncur bot di PC worker.

Dipanggil AI-TRADE-WORKER.bat. Urutan kerjanya berulang terus:

  1. Pastikan Syncthing menyala.
  2. Kalau folder rilis LENGKAP dan kodenya beda dengan folder bot,
     salin rilis ke folder bot. Hanya dilakukan saat bot TIDAK berjalan.
  3. Baca penugasan PC ini dari config/penugasan.yaml.
  4. Jalankan run_bot.py dengan varian itu.
  5. Selama bot berjalan, pantau rilis. Kalau ada kode baru atau
     penugasan PC ini berubah, minta bot berhenti SAAT TIDAK ADA POSISI
     TERBUKA (file logs/minta_restart.flag), lalu kembali ke langkah 2.
  6. Tulis logs/status_worker.json tiap 30 detik - itu yang dibaca PC
     utama untuk tahu worker ini hidup, versi apa, varian apa.

HANYA pustaka standar: berkas ini berjalan dari folder rilis, dan tetap
harus bisa jalan walau paket di venv rusak atau belum terpasang.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rilis  # noqa: E402
import syncthing_alat as st  # noqa: E402

BERHENTI = "berhenti"          # nilai penugasan: PC ini sengaja tidak menjalankan bot
KODE_UPDATE = 3                # run_bot.py keluar dengan kode ini untuk update
KODE_PELUNCUR_BARU = 4         # berkas ini sendiri diperbarui; AI-TRADE-WORKER.bat menjalankan ulang
FLAG_RESTART = "minta_restart.flag"
STATUS = "status_worker.json"
PERTAHANKAN_DI_BOT = ("logs", "STOP")

# Modul yang dimuat proses peluncur ini. Kalau rilis membawa versi baru
# dari salah satunya, proses yang sedang berjalan masih memegang versi
# lama di memori - jadi peluncur harus memulai ulang dirinya sendiri.
MODUL_PELUNCUR = ("jalankan_worker.py", "rilis.py", "syncthing_alat.py")
JALUR_PELUNCUR = "scripts/pc_worker/"


class PeluncurDiperbarui(Exception):
    pass


def sidik_berkas_peluncur(folder: Path) -> dict[str, str]:
    hasil = {}
    for nama in MODUL_PELUNCUR:
        try:
            hasil[nama] = rilis.sha256_file(folder / nama)
        except OSError:
            hasil[nama] = ""
    return hasil


class Worker:
    def __init__(self, folder: Path, perintah_bot: Optional[list[str]] = None,
                 jeda: int = 30):
        self.folder = folder
        self.rilis = folder / "rilis"
        self.bot = folder / "bot"
        self.logs = self.bot / "logs"
        self.venv_py = folder / "venv" / "Scripts" / "python.exe"
        self.data = json.loads((folder / "worker.json").read_text(encoding="utf-8"))
        self.nama = self.data["nama"]
        self.kunci = self.data["kunci"]
        self.perintah_bot = perintah_bot
        self.jeda = jeda
        self.keadaan = "mulai"
        self.pesan = ""
        self.varian: Optional[str] = None
        self.proses: Optional[subprocess.Popen] = None
        self.sidik_berjalan: Optional[str] = None
        self.minta_update_sejak: Optional[float] = None
        self.sidik_peluncur = sidik_berkas_peluncur(Path(__file__).resolve().parent)

    # -- util ------------------------------------------------------------

    def log(self, teks: str) -> None:
        baris = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [worker] {teks}"
        print(baris, flush=True)
        try:
            self.logs.mkdir(parents=True, exist_ok=True)
            with open(self.logs / f"worker_{datetime.now():%Y%m%d}.log", "a",
                      encoding="utf-8") as f:
                f.write(baris + "\n")
        except OSError:
            pass

    def set_keadaan(self, keadaan: str, pesan: str = "") -> None:
        if (keadaan, pesan) != (self.keadaan, self.pesan):
            self.keadaan, self.pesan = keadaan, pesan
            self.log(f"{keadaan}{': ' + pesan if pesan else ''}")
        self.tulis_status()

    def tulis_status(self) -> None:
        versi_bot = rilis.baca_versi(self.bot) or {}
        versi_rilis = rilis.baca_versi(self.rilis) or {}
        status = {
            "nama": self.nama,
            "kunci": self.kunci,
            "host": socket.gethostname(),
            "waktu_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "waktu_lokal": datetime.now().isoformat(timespec="seconds"),
            "keadaan": self.keadaan,
            "pesan": self.pesan,
            "varian": self.varian,
            "versi_bot": versi_bot.get("versi"),
            "commit_bot": versi_bot.get("commit"),
            "versi_rilis": versi_rilis.get("versi"),
            "pid_bot": self.proses.pid if self.proses and self.proses.poll() is None else None,
            "python": sys.version.split()[0],
        }
        try:
            self.logs.mkdir(parents=True, exist_ok=True)
            tmp = self.logs / (STATUS + ".tmp")
            tmp.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.logs / STATUS)
        except OSError:
            pass

    def syncthing(self) -> None:
        try:
            st.pastikan_jalan(Path(self.data["syncthing_exe"]),
                              Path(self.data["syncthing_home"]), self.log)
        except Exception as e:  # noqa: BLE001
            # Tanpa Syncthing bot tetap boleh jalan dengan versi yang ada;
            # hanya kiriman kode dan laporan yang tertunda.
            self.log(f"!! Syncthing tidak bisa dinyalakan: {e}")

    # -- rilis & penugasan -----------------------------------------------

    def rilis_lengkap(self) -> Optional[dict]:
        lengkap, info, _ = rilis.verifikasi(self.rilis)
        return info if lengkap else None

    def tugas_dari(self, folder: Path) -> Optional[str]:
        try:
            return rilis.baca_penugasan(folder).get(self.kunci)
        except ValueError as e:
            self.log(f"!! penugasan.yaml tidak terbaca: {e}")
            return None

    def perbarui_bot(self) -> None:
        """Salin rilis ke folder bot bila kodenya beda. Bot harus sedang mati."""
        info = self.rilis_lengkap()
        if info is None:
            if rilis.baca_versi(self.bot) is None:
                self.set_keadaan("menunggu_kode", "kiriman pertama dari PC utama belum lengkap")
            return
        lama = rilis.baca_versi(self.bot)
        if lama is not None and rilis.sidik(lama["file"]) == rilis.sidik(info["file"]):
            return
        self.log(f"memasang rilis {info.get('versi')} "
                 f"(sebelumnya {lama.get('versi') if lama else 'belum ada'})")
        hasil = rilis.cermin(self.rilis, self.bot, info, PERTAHANKAN_DI_BOT)
        self.log(f"  {hasil['disalin']} file disalin, {hasil['dihapus']} dihapus")
        self.pasang_paket()

    def pasang_paket(self) -> None:
        req = self.bot / "requirements.txt"
        catatan = self.folder / "venv" / "requirements.sha256"
        if not req.exists() or not self.venv_py.exists() or self.perintah_bot:
            return
        sha = rilis.sha256_file(req)
        try:
            if catatan.read_text(encoding="utf-8").strip() == sha:
                return
        except OSError:
            pass
        self.set_keadaan("memasang_paket", "requirements.txt berubah")
        kode = subprocess.run([str(self.venv_py), "-m", "pip", "install",
                               "--disable-pip-version-check", "-r", str(req)]).returncode
        if kode == 0:
            catatan.write_text(sha, encoding="utf-8")
        else:
            self.log("!! pip install gagal - bot tetap dicoba dengan paket yang ada")

    def perlu_restart(self) -> Optional[str]:
        """Alasan bot harus berhenti untuk update, atau None."""
        info = self.rilis_lengkap()
        if info is None:
            return None
        if rilis.sidik_kode(info) != self.sidik_berjalan:
            return f"kode baru {info.get('versi')}"
        tugas = self.tugas_dari(self.rilis)
        if tugas != self.varian:
            return f"penugasan berubah: {self.varian} -> {tugas}"
        return None

    # -- bot -------------------------------------------------------------

    def bot_lama_hidup(self) -> Optional[int]:
        """PID bot dari logs/bot.lock bila proses itu masih hidup di PC ini.

        Terjadi kalau peluncur mati (crash, dibunuh) tapi bot anaknya tetap
        berjalan. bot.lock sudah mencegah bot kedua berdagang, tapi tanpa
        pengecekan ini peluncur terus menyalakan bot baru yang langsung
        menolak jalan - dan statusnya tampak seperti crash berulang.
        """
        try:
            host, pid_teks = (self.logs / "bot.lock").read_text().split()
            pid = int(pid_teks)
        except (OSError, ValueError):
            return None
        if host != socket.gethostname():
            return None
        try:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                 capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        return pid if str(pid) in out and "python" in out.lower() else None

    def perintah(self, varian: str) -> list[str]:
        if self.perintah_bot:
            return [*self.perintah_bot, "--varian", varian]
        return [str(self.venv_py), "run_bot.py", "--varian", varian, "--nama-pc", self.nama]

    def jalankan_bot(self, varian: str) -> int:
        flag = self.logs / FLAG_RESTART
        flag.unlink(missing_ok=True)
        info = rilis.baca_versi(self.bot) or {}
        self.sidik_berjalan = rilis.sidik_kode(info) if info else None
        self.varian = varian
        self.minta_update_sejak = None

        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        self.proses = subprocess.Popen(self.perintah(varian), cwd=self.bot, env=env)
        self.set_keadaan("berjalan", f"varian {varian}, versi {info.get('versi')}")

        try:
            while True:
                try:
                    kode = self.proses.wait(timeout=self.jeda)
                    break
                except subprocess.TimeoutExpired:
                    pass
                alasan = self.perlu_restart()
                if alasan and self.minta_update_sejak is None:
                    self.minta_update_sejak = time.time()
                    flag.write_text(alasan, encoding="utf-8")
                    self.set_keadaan("menunggu_posisi_tutup",
                                     f"{alasan}; bot berhenti begitu tidak ada posisi terbuka")
                elif not alasan and self.minta_update_sejak is not None:
                    # Rilis dibatalkan/dikembalikan sebelum bot sempat berhenti.
                    flag.unlink(missing_ok=True)
                    self.minta_update_sejak = None
                    self.set_keadaan("berjalan", f"varian {varian}")
                else:
                    self.tulis_status()
        except KeyboardInterrupt:
            # Ctrl+C juga sampai ke bot (satu jendela konsol). Tunggu bot
            # menutup dirinya dengan rapi - jangan dibunuh, posisinya
            # sedang dikelola.
            self.log("Ctrl+C - menunggu bot berhenti...")
            try:
                self.proses.wait()
            except KeyboardInterrupt:
                pass
            raise
        finally:
            flag.unlink(missing_ok=True)
        return kode

    def cek_peluncur(self) -> None:
        """Mulai ulang proses ini bila rilis lengkap membawa peluncur versi lain.

        Hanya dipanggil saat bot TIDAK berjalan, jadi tidak ada posisi yang
        ditinggal tanpa pengelola.
        """
        info = self.rilis_lengkap()
        if info is None:
            return
        di_rilis = {n: info["file"].get(JALUR_PELUNCUR + n, "") for n in MODUL_PELUNCUR}
        if not all(di_rilis.values()):
            return  # rilis tanpa peluncur - tidak ada yang bisa dijalankan ulang
        if di_rilis != self.sidik_peluncur:
            raise PeluncurDiperbarui(info.get("versi"))

    def putaran(self) -> None:
        """Satu putaran: perbarui, baca tugas, jalankan bot, tangani kode keluar."""
        self.syncthing()
        self.cek_peluncur()
        self.perbarui_bot()
        if rilis.baca_versi(self.bot) is None:
            time.sleep(self.jeda)
            return

        sumber = self.rilis if self.rilis_lengkap() else self.bot
        varian = self.tugas_dari(sumber)
        if varian is None:
            self.varian = None
            self.set_keadaan("belum_ditugaskan",
                             f"tambahkan '{self.kunci}: <varian>' di config/penugasan.yaml PC utama")
            time.sleep(self.jeda)
            return
        if varian == BERHENTI:
            self.varian = BERHENTI
            self.set_keadaan("dihentikan_pc_utama", "penugasan PC ini: berhenti")
            time.sleep(self.jeda)
            return

        pid_lama = self.bot_lama_hidup()
        if pid_lama:
            # Minta bot lama berhenti lewat jalur yang sama dengan update:
            # ia keluar sendiri begitu tidak punya posisi terbuka, lalu
            # putaran berikutnya menjalankan bot yang diawasi peluncur ini.
            (self.logs / FLAG_RESTART).write_text("diambil alih peluncur worker", encoding="utf-8")
            self.set_keadaan("bot_lama_masih_jalan",
                             f"bot PID {pid_lama} dari sesi sebelumnya masih hidup; "
                             "diambil alih begitu tidak ada posisi terbuka")
            time.sleep(self.jeda)
            return

        kode = self.jalankan_bot(varian)
        self.proses = None
        if kode == KODE_UPDATE:
            self.set_keadaan("memperbarui", "bot berhenti untuk update")
            return
        if kode == 1:
            # Kode 1 bisa berarti akun REAL (penolakan disengaja), MT5
            # belum login, atau varian tidak dikenal. Tidak berbahaya untuk
            # dicoba lagi - bot menolak SEBELUM membuka posisi - jadi worker
            # tetap mencoba, dengan jeda panjang agar log tidak banjir.
            self.set_keadaan("bot_gagal",
                             "kode 1: MT5 belum login, akun REAL, atau varian salah. "
                             "Periksa log bot. Dicoba lagi 2 menit.")
            time.sleep(max(self.jeda, 120))
            return
        self.set_keadaan("bot_berhenti", f"kode {kode}; dinyalakan ulang dalam {self.jeda} detik")
        time.sleep(self.jeda)

    def jalan(self, sekali: bool = False) -> int:
        self.log(f"WORKER START - {self.nama} ({self.kunci}) di {self.folder}")
        try:
            while True:
                self.putaran()
                if sekali:
                    return 0
        except PeluncurDiperbarui as e:
            self.set_keadaan("memperbarui", f"peluncur worker diperbarui (rilis {e}), memulai ulang")
            return KODE_PELUNCUR_BARU
        except KeyboardInterrupt:
            self.set_keadaan("dimatikan", "dihentikan di PC worker (Ctrl+C / jendela ditutup)")
            return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default=str(Path(__file__).resolve().parents[3]))
    ap.add_argument("--jeda", type=int, default=30, help=argparse.SUPPRESS)
    ap.add_argument("--sekali", action="store_true", help=argparse.SUPPRESS)
    # Pengujian: jalankan perintah ini alih-alih run_bot.py.
    ap.add_argument("--perintah-bot", nargs="+", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()
    w = Worker(Path(args.folder).resolve(), args.perintah_bot, args.jeda)
    return w.jalan(sekali=args.sekali)


if __name__ == "__main__":
    sys.exit(main())
