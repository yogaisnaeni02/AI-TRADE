"""Tes jaringan PC utama <-> worker (scripts/pc_worker).

Syncthing sendiri tidak dites di sini (butuh dua proses dan jaringan);
yang dites adalah bagian yang menentukan KEAMANAN update:
- worker tidak memakai rilis yang baru separuh tiba,
- penyalinan tidak menghapus logs/ atau kill switch STOP milik worker,
- bot hanya diminta berhenti lewat flag, dan kode keluarnya disepakati,
- file pemasang .bat yang dibundel benar-benar bisa diekstrak dan jalan.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "pc_worker"))
sys.path.insert(0, str(ROOT))

import jalankan_worker as jw  # noqa: E402
import rilis  # noqa: E402
import siapkan_utama  # noqa: E402
from src import versi_kode  # noqa: E402
from src.monitoring import journal_gabung  # noqa: E402


def _tulis(akar: Path, isi: dict[str, str]) -> None:
    for rel, teks in isi.items():
        p = akar / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(teks, encoding="utf-8")


def _terbitkan(sumber: Path, tujuan: Path, versi: str) -> dict:
    daftar = [p.relative_to(sumber).as_posix() for p in sumber.rglob("*") if p.is_file()]
    info = {"versi": versi, "commit": "abc1234", "file": rilis.buat_manifest(sumber, daftar)}
    rilis.cermin(sumber, tujuan, info)
    return info


# -- kesepakatan antar modul ------------------------------------------------

@pytest.mark.parametrize("nama", ["PC Kantor", "pc3", "DESKTOP-NSAADIC", "  a b/c  ", "***", "Laptop_2"])
def test_slug_sama_dengan_nama_file_journal(nama):
    # Kunci penugasan harus menunjuk file journal yang sama.
    assert rilis.slug(nama) == journal_gabung._slug(nama)


def test_kode_update_dan_flag_disepakati_bot_dan_worker():
    assert jw.KODE_UPDATE == versi_kode.KODE_UPDATE
    assert jw.FLAG_RESTART == versi_kode.FLAG_RESTART


def test_alasan_restart(tmp_path):
    assert versi_kode.alasan_restart(tmp_path) is None
    (tmp_path / versi_kode.FLAG_RESTART).write_text("kode baru X", encoding="utf-8")
    assert versi_kode.alasan_restart(tmp_path) == "kode baru X"


# -- manifest & verifikasi ---------------------------------------------------

def test_verifikasi_menolak_rilis_yang_belum_lengkap(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "rilis"
    _tulis(src, {"run_bot.py": "a", "src/x.py": "b", "src/__pycache__/x.pyc": "junk"})
    info = _terbitkan(src, dst, "v1")
    assert "src/__pycache__/x.pyc" not in info["file"]
    assert rilis.verifikasi(dst)[0]

    # Syncthing baru mengirim sebagian: satu file masih versi lama.
    (dst / "src" / "x.py").write_text("lama", encoding="utf-8")
    lengkap, _, masalah = rilis.verifikasi(dst)
    assert not lengkap and masalah == ["src/x.py"]

    (dst / "src" / "x.py").unlink()
    assert not rilis.verifikasi(dst)[0]


def test_sidik_kode_mengabaikan_penugasan():
    a = {"run_bot.py": "1", rilis.PENUGASAN: "p1"}
    b = {"run_bot.py": "1", rilis.PENUGASAN: "p2"}
    c = {"run_bot.py": "2", rilis.PENUGASAN: "p1"}
    assert rilis.sidik_kode({"file": a}) == rilis.sidik_kode({"file": b})
    assert rilis.sidik_kode({"file": a}) != rilis.sidik_kode({"file": c})
    assert rilis.sidik(a) != rilis.sidik(b)


# -- penyalinan ----------------------------------------------------------------

def test_cermin_mempertahankan_logs_stop_dan_penanda_syncthing(tmp_path):
    src, bot = tmp_path / "src", tmp_path / "bot"
    _tulis(src, {"run_bot.py": "baru", "src/a.py": "a"})
    _tulis(bot, {
        "run_bot.py": "lama", "src/basi.py": "x", "src/lama/b.py": "y",
        "logs/trades__pc.csv": "journal", "STOP": "stop",
    })
    (bot / ".stfolder").mkdir()

    daftar = ["run_bot.py", "src/a.py"]
    info = {"versi": "v2", "file": rilis.buat_manifest(src, daftar)}
    hasil = rilis.cermin(src, bot, info, pertahankan=("logs", "STOP"))

    assert (bot / "run_bot.py").read_text(encoding="utf-8") == "baru"
    assert (bot / "src" / "a.py").exists()
    assert not (bot / "src" / "basi.py").exists()
    assert not (bot / "src" / "lama").exists()       # folder kosong ikut dibuang
    assert (bot / "logs" / "trades__pc.csv").read_text(encoding="utf-8") == "journal"
    assert (bot / "STOP").exists()
    assert (bot / ".stfolder").is_dir()              # penanda Syncthing tetap ada
    assert rilis.baca_versi(bot)["versi"] == "v2"
    assert hasil == {"disalin": 2, "dihapus": 2}


# -- penugasan -----------------------------------------------------------------

def test_urai_penugasan():
    teks = textwrap.dedent("""\
        # komentar
        pc-kantor: dua_arah_konfluensi   # catatan
        pc3: "pyramid5"

        laptop: berhenti
    """)
    assert rilis.urai_penugasan(teks) == {
        "pc-kantor": "dua_arah_konfluensi", "pc3": "pyramid5", "laptop": "berhenti",
    }
    with pytest.raises(ValueError):
        rilis.urai_penugasan("pc-kantor dua_arah")
    with pytest.raises(ValueError):
        rilis.urai_penugasan("pc-kantor:")


def test_penugasan_repo_valid():
    import terbitkan

    assert terbitkan.periksa_penugasan() == []


def test_periksa_penugasan_menolak_varian_dan_kunci_salah(tmp_path, monkeypatch):
    import terbitkan

    _tulis(tmp_path, {rilis.PENUGASAN: "PC Kantor: dua_arah\npc3: varian_khayalan\n"})
    monkeypatch.setattr(terbitkan, "REPO", tmp_path)
    masalah = terbitkan.periksa_penugasan()
    assert any("PC Kantor" in m and "pc-kantor" in m for m in masalah)
    assert any("varian_khayalan" in m for m in masalah)


# -- worker: update hanya lewat flag ----------------------------------------

BOT_PALSU = """\
import pathlib, sys, time
flag = pathlib.Path("logs") / "minta_restart.flag"
pathlib.Path("logs").mkdir(exist_ok=True)
(pathlib.Path("logs") / "jalan.txt").write_text(pathlib.Path("run_bot.py").read_text()[:20] + " " + sys.argv[-1])
batas = time.time() + 30
while time.time() < batas:
    if flag.exists():
        sys.exit(3)
    time.sleep(0.1)
sys.exit(0)
"""


def test_worker_memasang_rilis_baru_lewat_flag(tmp_path):
    folder = tmp_path / "worker"
    (folder / "bot" / "logs").mkdir(parents=True)
    (folder / "worker.json").write_text(
        '{"nama": "PC Uji", "kunci": "pc-uji", "syncthing_exe": "x", "syncthing_home": "x"}',
        encoding="utf-8",
    )
    sumber = tmp_path / "repo"
    _tulis(sumber, {"run_bot.py": "# versi-1\n", rilis.PENUGASAN: "pc-uji: konfluensi\n"})
    _terbitkan(sumber, folder / "rilis", "v1")

    bot_palsu = tmp_path / "bot_palsu.py"
    bot_palsu.write_text(BOT_PALSU, encoding="utf-8")
    w = jw.Worker(folder, perintah_bot=[sys.executable, str(bot_palsu)], jeda=1)
    w.syncthing = lambda: None

    hasil = {}
    t = threading.Thread(target=lambda: hasil.setdefault("ok", w.putaran()), daemon=True)
    t.start()
    jalan = folder / "bot" / "logs" / "jalan.txt"
    batas = time.time() + 15
    while not jalan.exists() and time.time() < batas:
        time.sleep(0.1)
    assert jalan.read_text() == "# versi-1\n konfluensi"
    assert w.keadaan == "berjalan"

    # PC utama menerbitkan kode baru saat bot berjalan.
    _tulis(sumber, {"run_bot.py": "# versi-2\n"})
    _terbitkan(sumber, folder / "rilis", "v2")
    t.join(timeout=20)
    assert not t.is_alive(), "worker tidak meminta bot berhenti"
    assert w.keadaan == "memperbarui"
    assert not (folder / "bot" / "logs" / "minta_restart.flag").exists()

    # Putaran berikutnya memasang v2 lalu menjalankan bot lagi.
    jalan.unlink()
    t = threading.Thread(target=w.putaran, daemon=True)
    t.start()
    batas = time.time() + 15
    while not jalan.exists() and time.time() < batas:
        time.sleep(0.1)
    assert jalan.read_text() == "# versi-2\n konfluensi"
    assert rilis.baca_versi(folder / "bot")["versi"] == "v2"
    (folder / "bot" / "logs" / "minta_restart.flag").write_text("selesai tes")
    t.join(timeout=10)


def test_worker_tanpa_penugasan_tidak_menjalankan_bot(tmp_path):
    folder = tmp_path / "worker"
    (folder / "bot" / "logs").mkdir(parents=True)
    (folder / "worker.json").write_text(
        '{"nama": "PC Lain", "kunci": "pc-lain", "syncthing_exe": "x", "syncthing_home": "x"}',
        encoding="utf-8",
    )
    sumber = tmp_path / "repo"
    _tulis(sumber, {"run_bot.py": "x", rilis.PENUGASAN: "pc-uji: konfluensi\n"})
    _terbitkan(sumber, folder / "rilis", "v1")
    w = jw.Worker(folder, perintah_bot=[sys.executable, "-c", "raise SystemExit(9)"], jeda=0)
    w.syncthing = lambda: None
    w.putaran()
    assert w.keadaan == "belum_ditugaskan"
    assert w.proses is None


def test_peluncur_memulai_ulang_diri_saat_berkasnya_berubah(tmp_path):
    folder = tmp_path / "worker"
    (folder / "bot" / "logs").mkdir(parents=True)
    (folder / "worker.json").write_text(
        '{"nama": "PC Uji", "kunci": "pc-uji", "syncthing_exe": "x", "syncthing_home": "x"}',
        encoding="utf-8",
    )
    sumber = tmp_path / "repo"
    asli = ROOT / "scripts" / "pc_worker"
    # Disalin per byte: sidik jari dihitung dari byte, dan write_text di
    # Windows mengubah akhir baris.
    (sumber / "scripts" / "pc_worker").mkdir(parents=True)
    for n in jw.MODUL_PELUNCUR:
        (sumber / "scripts" / "pc_worker" / n).write_bytes((asli / n).read_bytes())
    _tulis(sumber, {"run_bot.py": "x", rilis.PENUGASAN: "pc-lain: konfluensi\n"})
    _terbitkan(sumber, folder / "rilis", "v1")

    w = jw.Worker(folder, perintah_bot=[sys.executable, "-c", "pass"], jeda=0)
    w.syncthing = lambda: None
    w.putaran()                          # peluncur sama -> tidak restart
    assert w.keadaan == "belum_ditugaskan"

    with open(sumber / "scripts" / "pc_worker" / "rilis.py", "ab") as f:
        f.write(b"\n# baru\n")
    _terbitkan(sumber, folder / "rilis", "v2")
    assert w.jalan() == jw.KODE_PELUNCUR_BARU


@pytest.mark.skipif(sys.platform != "win32", reason="memakai tasklist")
def test_bot_lama_yang_masih_hidup_tidak_didobel(tmp_path):
    import socket

    folder = tmp_path / "worker"
    (folder / "bot" / "logs").mkdir(parents=True)
    (folder / "worker.json").write_text(
        '{"nama": "PC Uji", "kunci": "pc-uji", "syncthing_exe": "x", "syncthing_home": "x"}',
        encoding="utf-8",
    )
    sumber = tmp_path / "repo"
    _tulis(sumber, {"run_bot.py": "x", rilis.PENUGASAN: "pc-uji: konfluensi\n"})
    _terbitkan(sumber, folder / "rilis", "v1")

    lama = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        lock = folder / "bot" / "logs" / "bot.lock"
        lock.write_text(f"{socket.gethostname()} {lama.pid}")
        w = jw.Worker(folder, perintah_bot=[sys.executable, "-c", "raise SystemExit(9)"], jeda=0)
        w.syncthing = lambda: None
        w.putaran()
        assert w.keadaan == "bot_lama_masih_jalan"
        assert w.proses is None
        assert (folder / "bot" / "logs" / jw.FLAG_RESTART).exists()
    finally:
        lama.kill()
        lama.wait()

    # Proses di lock sudah mati -> lock basi diabaikan, bot baru dijalankan.
    w.putaran()
    assert w.keadaan == "bot_berhenti"


def test_penugasan_pc_lain_tidak_membuat_worker_terbaca_tertinggal():
    import status_worker as sw

    rilis_lama = {"versi": "v1", "sidik_kode": "aaa"}
    rilis_baru = {"versi": "v2", "sidik_kode": "aaa"}   # kode sama, penugasan beda
    rilis_kode_baru = {"versi": "v3", "sidik_kode": "bbb"}
    worker = {"versi_bot": "v1", "sidik_bot": "aaa"}

    assert not sw.kode_tertinggal(worker, rilis_lama)
    assert not sw.kode_tertinggal(worker, rilis_baru)
    assert sw.kode_tertinggal(worker, rilis_kode_baru)

    # Worker versi lama belum mengirim sidik jari -> jatuh ke label versi.
    lawas = {"versi_bot": "v1"}
    assert sw.kode_tertinggal(lawas, rilis_baru)
    assert not sw.kode_tertinggal(lawas, rilis_lama)
    assert not sw.kode_tertinggal({}, rilis_baru)


def test_unduhan_dialihkan_ke_windows_saat_sertifikat_gagal(monkeypatch, tmp_path):
    """PC kantor dengan proxy HTTPS tetap bisa mengunduh Syncthing."""
    import ssl
    import subprocess as sp
    import urllib.error
    import urllib.request

    import syncthing_alat as st

    def gagal_sertifikat(req, **kw):  # noqa: ARG001
        raise urllib.error.URLError(ssl.SSLCertVerificationError("verify failed"))

    monkeypatch.setattr(urllib.request, "urlopen", gagal_sertifikat)

    dipakai = []

    def jalan_palsu(perintah, **kw):
        dipakai.append(Path(perintah[0]).name)
        keluar = perintah[perintah.index("-o") + 1] if "-o" in perintah else None
        if keluar:
            Path(keluar).write_bytes(b"isi berkas")
        return subprocess.CompletedProcess(perintah, 0, "", "")

    monkeypatch.setattr(sp, "run", jalan_palsu)
    # curl.exe bawaan Windows dipalsukan lewat SystemRoot, bukan dengan
    # menambal Path.exists - penambalan itu ikut mengenai berkas unduhan.
    (tmp_path / "System32").mkdir()
    (tmp_path / "System32" / "curl.exe").write_bytes(b"")
    monkeypatch.setenv("SystemRoot", str(tmp_path))
    assert st._ambil("https://contoh/berkas.zip") == b"isi berkas"
    assert dipakai == ["curl.exe"]

    # Kegagalan jaringan biasa tetap dilempar, bukan diam-diam dialihkan.
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, **kw: (_ for _ in ()).throw(urllib.error.URLError("mati")))
    with pytest.raises(urllib.error.URLError):
        st._ambil("https://contoh/berkas.zip")


# -- pilih dengan nomor ----------------------------------------------------------

def test_pilih_varian_dengan_nomor_atau_nama():
    from src.variants import format_table, list_variants, pilih

    nama = list(list_variants())
    assert pilih("1") == nama[0]
    assert pilih(f" {len(nama)} ") == nama[-1]
    assert pilih("0") is None and pilih(str(len(nama) + 1)) is None
    assert pilih(nama[1].upper()) == nama[1]
    assert pilih("tidak_ada") is None and pilih("") is None
    # Nomor di tabel harus nomor yang diterima pilih().
    baris = format_table().splitlines()[2:]
    assert [b.split()[:2] for b in baris] == [[str(i), n] for i, n in enumerate(nama, 1)]


def test_atur_penugasan_terjemahan_dan_tulis(tmp_path):
    import atur_penugasan as ap
    from src.variants import list_variants

    assert ap.terjemahkan("0") == "berhenti"
    assert ap.terjemahkan("H") == ""
    assert ap.terjemahkan("2") == list(list_variants())[1]
    assert ap.terjemahkan("99") is None

    p = tmp_path / "penugasan.yaml"
    p.write_text("# kepala 1\n#   contoh: x\n\npc-lama: baseline  # komentar\n", encoding="utf-8")
    ap.tulis_penugasan(p, {"pc3": "pyramid5", "pc-kantor": "dua_arah_konfluensi"})
    teks = p.read_text(encoding="utf-8")
    assert teks == "# kepala 1\n#   contoh: x\n\npc-kantor: dua_arah_konfluensi\npc3: pyramid5\n"
    assert rilis.urai_penugasan(teks) == {"pc3": "pyramid5", "pc-kantor": "dua_arah_konfluensi"}


# -- file pemasang .bat ---------------------------------------------------------

def _bat(tmp_path) -> Path:
    return siapkan_utama.buat_bat_worker("AAAAAAA-BBBBBBB", "PC utama uji", tmp_path / "PASANG.bat")


def test_bat_pemasang_ascii_crlf_dan_bundel_bisa_jalan(tmp_path):
    bat = _bat(tmp_path)
    data = bat.read_bytes()
    data.decode("ascii")
    assert b"\n" not in data.replace(b"\r\n", b"")

    baris = data.decode("ascii").split("\r\n")
    penanda = [i for i, b in enumerate(baris) if b.startswith(siapkan_utama.PENANDA)]
    assert len(penanda) == 1

    py = tmp_path / "ekstrak.py"
    py.write_text("\n".join(baris[penanda[0] + 1:]), encoding="ascii")
    hasil = subprocess.run([sys.executable, str(py), "--cek"], capture_output=True, text=True,
                           timeout=60)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr
    assert "Bundel OK" in hasil.stdout
    assert "AAAAAAA" in hasil.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="butuh cmd.exe")
def test_bat_pemasang_lewat_cmd(tmp_path):
    # Menguji rantai asli di Windows: cari Python -> findstr -> more -> python.
    bat = _bat(tmp_path)
    hasil = subprocess.run(["cmd", "/c", str(bat), "--cek"], capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=120)
    assert "Bundel OK" in hasil.stdout, hasil.stdout + hasil.stderr
