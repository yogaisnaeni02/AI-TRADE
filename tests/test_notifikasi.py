"""Tes isi notifikasi Telegram.

Yang dijaga di sini: pesan memuat hal yang dipakai pemilik untuk memutuskan
(PC mana, varian apa, kejadian apa, untung/rugi berapa, porto sekarang),
dan sebab penutupan posisi tidak salah baca - SL yang berakhir untung
adalah trailing/break-even, bukan kekalahan.

Tidak ada yang benar-benar dikirim: `send` diganti penangkap.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# MetaTrader5 tidak ada di mesin pengembangan; journal hanya butuh
# konstanta DEAL_REASON_* dan itu dibaca lewat getattr.
sys.modules.setdefault("MetaTrader5", types.ModuleType("MetaTrader5"))

from src.monitoring import notifier  # noqa: E402
from src.monitoring.journal import _sebab_exit  # noqa: E402

TP, SL, EXPERT, SO, CLIENT = 5, 4, 3, 6, 0


@pytest.fixture
def terkirim(monkeypatch):
    pesan: list[str] = []
    monkeypatch.setattr(notifier, "send", lambda teks: pesan.append(teks) or True)
    return pesan


def _notifier_segar():
    """Salinan modul notifier yang berdiri sendiri.

    tests/test_bot_manage.py mengganti notifier.send dengan stub saat
    diimpor, supaya tesnya tidak pernah mengirim Telegram sungguhan. Tes
    di bawah justru menguji isi send() itu sendiri, jadi ia memakai
    salinan modul sendiri - bukan mengembalikan stub milik tes lain.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "notifier_uji", ROOT / "src" / "monitoring" / "notifier.py"
    )
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_label_pc_dan_varian_ikut_di_tiap_pesan(monkeypatch):
    dikirim = {}

    def palsu(req, **kw):  # noqa: ARG001
        dikirim["body"] = req.data       # isi ada di objek Request
        raise OSError("tidak benar-benar dikirim")

    segar = _notifier_segar()
    monkeypatch.setattr(segar, "_load_telegram_config", lambda: ("token", "chat"))
    monkeypatch.setattr(segar, "_LABEL", "PC Kantor")
    monkeypatch.setattr(segar, "_VARIAN", "dua_arah_konfluensi")
    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", palsu)
    assert segar.send("halo") is False          # gagal kirim tidak melempar
    isi = dikirim["body"].decode()
    assert "PC+Kantor" in isi and "dua_arah_konfluensi" in isi


def test_set_varian_bisa_dikosongkan():
    notifier.set_varian("konfluensi")
    assert notifier._VARIAN == "konfluensi"
    notifier.set_varian(None)
    assert notifier._VARIAN is None


def test_rupiah():
    assert notifier.rupiah(1234567) == "Rp 1,234,567"
    assert notifier.rupiah(120000, tanda=True) == "+Rp 120,000"
    assert notifier.rupiah(-78676, tanda=True) == "-Rp 78,676"
    assert notifier.rupiah(0, tanda=True) == "Rp 0"


def test_pesan_entry_memuat_arah_varian_harga_dan_risiko(terkirim):
    notifier.notify_entry("buy", "momentum_fib", "reduced", 6, 0.01,
                          4335.74, 4331.35, 4346.77, 1.30, 78676, 3826517825)
    teks = terkirim[0]
    assert "BUY dibuka" in teks and "momentum_fib" in teks
    assert "0.01 lot @ 4335.74" in teks
    assert "SL 4331.35" in teks and "TP 4346.77" in teks
    assert "RR 1:2.5" in teks
    assert "skor 6 (reduced)" in teks and "1.30%" in teks and "Rp 78,676" in teks
    assert "tiket 3826517825" in teks


def test_pesan_exit_memuat_sebab_hasil_dan_porto(terkirim):
    notifier.notify_exit("TP tercapai", "buy", 0.01, 4335.74, 4346.77,
                         120000, 2.0, 35, 3, -50000, 5208252)
    teks = terkirim[0]
    assert "TP tercapai" in teks
    assert "4335.74 → 4346.77" in teks and "35 mnt" in teks
    assert "+Rp 120,000" in teks and "(+2.00R)" in teks
    assert "Hari ini 3 trade" in teks and "-Rp 50,000" in teks
    assert "Equity Rp 5,208,252" in teks


def test_pesan_exit_tanpa_r_multiple_tetap_terkirim(terkirim):
    # r_multiple kosong terjadi untuk posisi yang dibuka sebelum restart.
    notifier.notify_exit("SL kena", "sell", 0.02, 4349.4, 4344.5,
                         -78676, "", 125, 4, -291748, 5208252)
    teks = terkirim[0]
    assert "SL kena" in teks and "R)" not in teks
    assert "2.1 jam" in teks       # durasi panjang ditulis dalam jam
    assert "📉" in teks


def test_heartbeat_memuat_porto_dan_pnl_harian(terkirim):
    notifier.notify_heartbeat("18 Sep 15:00 WIB", 5208252, 5.3, 1, 23000,
                              2, 12, -158199, "2/3 loss beruntun",
                              "london_open", "4f92")
    teks = terkirim[0]
    assert "Bot hidup" in teks and "18 Sep 15:00 WIB" in teks
    assert "Equity Rp 5,208,252 (DD 5.3%)" in teks
    assert "Posisi 1 · floating +Rp 23,000" in teks
    assert "Hari ini 2/12 trade · -Rp 158,199" in teks
    assert "2/3 loss beruntun" in teks and "london_open" in teks
    assert "HALT" not in teks


def test_heartbeat_tanpa_posisi_tidak_menyebut_floating(terkirim):
    notifier.notify_heartbeat("18 Sep 16:00 WIB", 5208252, 5.3, 0, 0,
                              0, 12, 0, "0/3 loss beruntun", "asia", "4f92",
                              halt="drawdown 20%")
    teks = terkirim[0]
    assert "floating" not in teks
    assert "🛑 HALT: drawdown 20%" in teks


@pytest.mark.parametrize("reason,net,harapan", [
    (TP, 120000, "TP tercapai"),
    (SL, -78676, "SL kena"),
    (SL, 45000, "trailing/BE"),      # stop sudah digeser -> bukan kekalahan
    (EXPERT, -12000, "ditutup bot"),
    (SO, -900000, "STOP OUT margin"),
    (CLIENT, 5000, "ditutup manual"),
    (-1, 0, "ditutup manual"),       # reason tidak terbaca
])
def test_sebab_exit(reason, net, harapan):
    assert _sebab_exit(reason, net) == harapan
