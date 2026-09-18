"""Alat Syncthing untuk jaringan PC utama <-> PC worker.

HANYA pustaka standar: file ini ikut dibundel ke PASANG-WORKER.bat dan
dijalankan di PC yang belum punya paket Python apa pun.

Syncthing dipakai dalam bentuk portable (satu syncthing.exe), bukan
installer: tidak butuh hak admin, tidak menyentuh PATH, dan tidak
bentrok dengan Syncthing lain yang mungkin sudah dipakai pemilik PC -
GUI-nya dipasang di port sendiri (18384, bukan 8384).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Callable, Optional

RILIS_ID = "aitrade-rilis"
PREFIKS_LAPORAN = "aitrade-laporan-"
PORT_GUI = 18384
API_RILIS_SYNCTHING = "https://api.github.com/repos/syncthing/syncthing/releases/latest"

# Proses Windows tanpa jendela konsol, lepas dari jendela yang menjalankannya.
_TANPA_JENDELA = 0x08000000      # CREATE_NO_WINDOW
_LEPAS = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


class GagalSyncthing(RuntimeError):
    pass


# -- unduh ----------------------------------------------------------------

def _ambil(url: str, timeout: int = 60) -> bytes:
    """Unduh berkas; kalau verifikasi sertifikat gagal, coba lewat Windows.

    KENAPA ADA (18 Sep 2026): pemasangan di satu PC kantor gagal dengan
    CERTIFICATE_VERIFY_FAILED saat mengunduh Syncthing, padahal browser di
    PC yang sama bisa membuka alamat itu. Python memakai penyimpanan
    sertifikatnya sendiri; proxy kantor yang menandatangani ulang HTTPS -
    atau Windows yang belum pernah mengambil root CA-nya - tidak terbaca
    dari sana.

    curl.exe (bawaan Windows 10 1803+) dan PowerShell memakai penyimpanan
    sertifikat WINDOWS, yang justru sudah memuat sertifikat proxy kantor.
    Isi unduhannya tetap dicocokkan dengan sha256 rilis resmi setelahnya,
    jadi jalur cadangan ini tidak melonggarkan pemeriksaan keaslian berkas.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "ai-trade-worker"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.URLError as e:
        if not isinstance(getattr(e, "reason", None), ssl.SSLCertVerificationError):
            raise
    return _ambil_lewat_windows(url, timeout)


def _ambil_lewat_windows(url: str, timeout: int = 60) -> bytes:
    """Unduh memakai curl.exe atau PowerShell - keduanya percaya CA Windows."""
    galat: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        keluar = Path(tmp) / "unduh.bin"
        curl = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "curl.exe"
        perintah = []
        if curl.exists():
            perintah.append([str(curl), "-fsSL", "--max-time", str(timeout),
                             "-o", str(keluar), url])
        perintah.append([
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "$ProgressPreference='SilentlyContinue'; "
            f"Invoke-WebRequest -UseBasicParsing -Uri '{url}' -OutFile '{keluar}'",
        ])
        for p in perintah:
            try:
                hasil = subprocess.run(p, capture_output=True, text=True,
                                       timeout=timeout + 60, creationflags=_TANPA_JENDELA)
            except (OSError, subprocess.SubprocessError) as e:
                galat.append(f"{Path(p[0]).name}: {e}")
                continue
            if hasil.returncode == 0 and keluar.exists() and keluar.stat().st_size:
                return keluar.read_bytes()
            galat.append(f"{Path(p[0]).name}: {(hasil.stderr or hasil.stdout).strip()[-200:]}")
    raise GagalSyncthing("unduhan gagal, termasuk lewat Windows: " + " | ".join(galat))


def _arsitektur() -> str:
    m = platform.machine().lower()
    if m in ("arm64", "aarch64"):
        return "arm64"
    if m in ("x86", "i386", "i686"):
        return "386"
    return "amd64"


def unduh(folder: Path, cetak: Callable[[str], None] = print) -> Path:
    """Pastikan folder/syncthing.exe ada; unduh rilis resmi terbaru bila belum.

    Checksum dicocokkan dengan sha256sum.txt.asc dari rilis yang sama.
    Catatan jujur: tanda tangan PGP-nya tidak diverifikasi (tidak ada gpg
    di PC worker), jadi ini melindungi dari unduhan rusak, bukan dari
    GitHub yang disusupi. Kedua file diambil lewat HTTPS dari GitHub.
    """
    exe = folder / "syncthing.exe"
    if exe.is_file():
        return exe
    folder.mkdir(parents=True, exist_ok=True)

    try:
        info = json.loads(_ambil(API_RILIS_SYNCTHING, timeout=30))
        tag = info["tag_name"]
        aset = {a["name"]: a["browser_download_url"] for a in info["assets"]}
        nama_zip = f"syncthing-windows-{_arsitektur()}-{tag}.zip"
        if nama_zip not in aset or "sha256sum.txt.asc" not in aset:
            raise GagalSyncthing(f"aset {nama_zip} tidak ditemukan di rilis {tag}")
        cetak(f"  mengunduh {nama_zip} (~12 MB)...")
        data = _ambil(aset[nama_zip], timeout=600)
        daftar_sha = _ambil(aset["sha256sum.txt.asc"], timeout=60).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
        raise GagalSyncthing(f"gagal mengunduh Syncthing: {e}") from e

    sha = hashlib.sha256(data).hexdigest()
    if not any(b.split()[:2] == [sha, nama_zip] for b in daftar_sha.splitlines()):
        raise GagalSyncthing("checksum Syncthing tidak cocok - unduhan rusak, coba lagi")

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        anggota = next(n for n in zf.namelist() if n.endswith("/syncthing.exe"))
        tmp = exe.with_suffix(".tmp")
        tmp.write_bytes(zf.read(anggota))
        os.replace(tmp, exe)
    cetak(f"  Syncthing {tag} terpasang di {exe}")
    return exe


# -- konfigurasi awal -----------------------------------------------------

def _set(induk: ET.Element, tag: str, nilai: str) -> None:
    el = induk.find(tag)
    if el is None:
        el = ET.SubElement(induk, tag)
    el.text = nilai


def siapkan_home(exe: Path, home: Path, port_gui: int = PORT_GUI,
                 uji_lokal: Optional[int] = None) -> None:
    """Buat kunci + config.xml sekali, lalu atur sebelum Syncthing pertama jalan.

    Diubah lewat XML (bukan REST) karena alamat GUI dan alamat dengar
    harus sudah benar SEBELUM proses pertama kali berjalan.

    `uji_lokal` hanya untuk pengujian di satu PC: dengar di 127.0.0.1 dan
    matikan discovery/relay, supaya tidak ada lalu lintas ke internet dan
    Windows Firewall tidak memunculkan dialog.
    """
    cfg = home / "config.xml"
    if cfg.exists():
        return
    home.mkdir(parents=True, exist_ok=True)
    hasil = subprocess.run(
        [str(exe), "generate", f"--home={home}", "--no-port-probing"],
        capture_output=True, text=True, timeout=120, creationflags=_TANPA_JENDELA,
    )
    if hasil.returncode != 0 or not cfg.exists():
        raise GagalSyncthing(f"syncthing generate gagal: {hasil.stderr.strip()[-300:]}")

    pohon = ET.parse(cfg)
    akar = pohon.getroot()
    _set(akar.find("gui"), "address", f"127.0.0.1:{port_gui}")
    opsi = akar.find("options")
    _set(opsi, "startBrowser", "false")
    _set(opsi, "urAccepted", "-1")
    _set(opsi, "crashReportingEnabled", "false")
    if uji_lokal:
        for el in opsi.findall("listenAddress"):
            opsi.remove(el)
        ET.SubElement(opsi, "listenAddress").text = f"tcp://127.0.0.1:{uji_lokal}"
        for tag in ("globalAnnounceEnabled", "localAnnounceEnabled",
                    "relaysEnabled", "natEnabled"):
            _set(opsi, tag, "false")
        _set(opsi, "autoUpgradeIntervalH", "0")
    pohon.write(cfg, encoding="utf-8", xml_declaration=False)


def argumen_serve(home: Path) -> list[str]:
    return [
        "serve", "--no-browser", "--no-console", f"--home={home}",
        f"--log-file={home / 'syncthing.log'}",
        "--log-max-size=5000000", "--log-max-old-files=2",
    ]


def mulai(exe: Path, home: Path) -> None:
    """Jalankan Syncthing di latar belakang, lepas dari jendela ini."""
    subprocess.Popen(
        [str(exe), *argumen_serve(home)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=_TANPA_JENDELA | _LEPAS, close_fds=True,
    )


# -- REST -----------------------------------------------------------------

class Api:
    """Klien REST Syncthing yang hanya mendengar di 127.0.0.1."""

    def __init__(self, home: Path):
        akar = ET.parse(home / "config.xml").getroot()
        gui = akar.find("gui")
        self.base = "http://" + gui.findtext("address", f"127.0.0.1:{PORT_GUI}")
        self.kunci = gui.findtext("apikey", "")

    def _req(self, metode: str, jalur: str, data=None, timeout: int = 15):
        body = None if data is None else json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            self.base + jalur, data=body, method=metode,
            headers={"X-API-Key": self.kunci, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            isi = r.read()
        return json.loads(isi) if isi.strip() else None

    def get(self, jalur: str):
        return self._req("GET", jalur)

    def put(self, jalur: str, data) -> None:
        self._req("PUT", jalur, data)

    def hidup(self) -> bool:
        try:
            return (self.get("/rest/system/ping") or {}).get("ping") == "pong"
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def tunggu_hidup(self, detik: int = 90) -> bool:
        batas = time.time() + detik
        while time.time() < batas:
            if self.hidup():
                return True
            time.sleep(1)
        return False

    def id_saya(self) -> str:
        return self.get("/rest/system/status")["myID"]

    # -- perangkat --

    def perangkat(self, device_id: str) -> Optional[dict]:
        try:
            return self.get(f"/rest/config/devices/{device_id}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def pasang_perangkat(self, device_id: str, nama: str,
                         alamat: Optional[list[str]] = None) -> None:
        dev = self.perangkat(device_id) or self.get("/rest/config/defaults/device")
        dev["deviceID"] = device_id
        dev["name"] = nama
        if alamat:
            dev["addresses"] = alamat
        self.put(f"/rest/config/devices/{device_id}", dev)

    def ganti_nama_saya(self, nama: str) -> None:
        dev = self.perangkat(self.id_saya())
        if dev and dev.get("name") != nama:
            dev["name"] = nama
            self.put(f"/rest/config/devices/{dev['deviceID']}", dev)

    # -- folder --

    def folder(self, folder_id: str) -> Optional[dict]:
        try:
            return self.get(f"/rest/config/folders/{folder_id}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def pasang_folder(self, folder_id: str, label: str, path: Path, tipe: str,
                      perangkat: list[str], **ekstra) -> None:
        """Buat atau perbarui folder; perangkat yang sudah terdaftar dipertahankan."""
        f = self.folder(folder_id) or self.get("/rest/config/defaults/folder")
        f.update({"id": folder_id, "label": label, "path": str(path), "type": tipe})
        f.update(ekstra)
        ada = {d["deviceID"] for d in f.get("devices", [])}
        for dev in [self.id_saya(), *perangkat]:
            if dev not in ada:
                f.setdefault("devices", []).append(
                    {"deviceID": dev, "introducedBy": "", "encryptionPassword": ""}
                )
                ada.add(dev)
        self.put(f"/rest/config/folders/{folder_id}", f)

    def bagikan_folder(self, folder_id: str, device_id: str) -> None:
        f = self.folder(folder_id)
        if f is None:
            raise GagalSyncthing(f"folder {folder_id} belum ada")
        if device_id not in {d["deviceID"] for d in f.get("devices", [])}:
            f["devices"].append({"deviceID": device_id, "introducedBy": "",
                                 "encryptionPassword": ""})
            self.put(f"/rest/config/folders/{folder_id}", f)

    # -- keadaan --

    def tertunda_perangkat(self) -> dict:
        return self.get("/rest/cluster/pending/devices") or {}

    def tertunda_folder(self) -> dict:
        return self.get("/rest/cluster/pending/folders") or {}

    def koneksi(self) -> dict:
        return (self.get("/rest/system/connections") or {}).get("connections", {})

    def status_folder(self, folder_id: str) -> dict:
        q = urllib.parse.urlencode({"folder": folder_id})
        return self.get(f"/rest/db/status?{q}") or {}


def pastikan_jalan(exe: Path, home: Path, cetak: Callable[[str], None] = print) -> Api:
    """Nyalakan Syncthing bila belum, lalu kembalikan klien REST-nya."""
    api = Api(home)
    if not api.hidup():
        cetak("  menyalakan Syncthing...")
        mulai(exe, home)
        if not api.tunggu_hidup():
            raise GagalSyncthing(
                f"Syncthing tidak merespons. Lihat {home / 'syncthing.log'}"
            )
    return api


# -- shortcut Windows -----------------------------------------------------

def _ps_kutip(s) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def _powershell(perintah: str) -> str:
    hasil = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", perintah],
        capture_output=True, text=True, timeout=60, creationflags=_TANPA_JENDELA,
    )
    if hasil.returncode != 0:
        raise GagalSyncthing(hasil.stderr.strip()[-300:] or "powershell gagal")
    return hasil.stdout.strip()


def folder_khusus(nama: str) -> Path:
    """'Desktop' atau 'Startup' - lewat Windows, karena Desktop sering
    dialihkan ke OneDrive dan jalurnya tidak bisa ditebak."""
    return Path(_powershell(f"[Environment]::GetFolderPath({_ps_kutip(nama)})"))


def buat_shortcut(lnk: Path, target: Path, argumen: str = "",
                  folder_kerja: Optional[Path] = None, diperkecil: bool = False) -> None:
    kerja = folder_kerja or target.parent
    _powershell(
        f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut({_ps_kutip(lnk)});"
        f"$s.TargetPath={_ps_kutip(target)};"
        f"$s.Arguments={_ps_kutip(argumen)};"
        f"$s.WorkingDirectory={_ps_kutip(kerja)};"
        f"$s.WindowStyle={7 if diperkecil else 1};"
        "$s.Save()"
    )


def argumen_teks(argumen: list[str]) -> str:
    """Gabung argumen untuk shortcut; yang mengandung spasi dikutip."""
    return " ".join(f'"{a}"' if " " in a else a for a in argumen)


def autostart_syncthing(exe: Path, home: Path, nama_shortcut: str) -> Path:
    lnk = folder_khusus("Startup") / f"{nama_shortcut}.lnk"
    buat_shortcut(lnk, exe, argumen_teks(argumen_serve(home)), diperkecil=True)
    return lnk
