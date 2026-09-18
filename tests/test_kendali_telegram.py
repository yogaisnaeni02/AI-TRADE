"""Tes kendali Telegram (scripts/pc_worker/kendali_telegram.py).

Yang dijaga:
- perintah ganti varian memakai NOMOR, dan nomor di luar daftar ditolak
  sebelum apa pun ditulis;
- perintah yang berisiko (menutup posisi, melepas halt) memang tidak ada;
- angka yang dilaporkan (saldo, P/L harian, total) diambil dari laporan
  worker, bukan dikarang.

Tidak ada jaringan: penerbitan diganti stub, pengiriman pesan tidak dipakai.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "pc_worker"))
sys.path.insert(0, str(ROOT))

import kendali_telegram as kt  # noqa: E402
import rilis  # noqa: E402
from src.variants import list_variants  # noqa: E402

VARIAN = list(list_variants())

RISK_YAML = """\
daily:
  max_loss_percent: 4.0
  max_trades: 12
  max_consecutive_losses: 3
weekly:
  max_loss_percent: 8.0
global:
  max_drawdown_percent: 20.0
"""


def _worker(laporan: Path, kunci: str, nama: str, varian: str, snap: dict,
            trades: list[tuple[str, float, str]] = ()) -> None:
    folder = laporan / kunci
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "status_worker.json").write_text(json.dumps({
        "nama": nama, "kunci": kunci, "keadaan": "berjalan", "varian": varian,
        "versi_bot": "20260918-1714-c327771",
        "waktu_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }), encoding="utf-8")
    (folder / "snapshot.json").write_text(json.dumps(snap), encoding="utf-8")
    if trades:
        baris = ["ticket,direction,lot,exit_time,net_idr,r_multiple,varian"]
        for i, (waktu, net, var) in enumerate(trades, start=1):
            baris.append(f"{kunci}{i},buy,0.01,{waktu},{net},,{var}")
        (folder / f"trades__{kunci}.csv").write_text("\n".join(baris) + "\n", encoding="utf-8")


@pytest.fixture
def kendali(tmp_path):
    repo, laporan = tmp_path / "repo", tmp_path / "laporan"
    (repo / "config").mkdir(parents=True)
    (repo / rilis.PENUGASAN).write_text(
        f"# catatan\n\npc-kantor: {VARIAN[3]}\npc3: {VARIAN[4]}\n", encoding="utf-8")
    (repo / "config" / "risk_limits.yaml").write_text(RISK_YAML, encoding="utf-8")

    kemarin = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    hari_ini = datetime.now().isoformat(timespec="seconds")
    _worker(laporan, "pc-kantor", "PC Kantor", VARIAN[3],
            {"equity": 5208252, "balance": 5185000, "open_positions": 1, "day_trades": 2,
             "day_pnl": -158199, "consecutive_losses": 2, "drawdown_pct": 7.2, "halted": False},
            [(hari_ini, -158199, VARIAN[3]), (kemarin, 240000, VARIAN[3])])
    _worker(laporan, "pc3", "PC3", VARIAN[4],
            {"equity": 3100000, "balance": 3100000, "open_positions": 0, "day_trades": 0,
             "day_pnl": 0, "consecutive_losses": 0, "drawdown_pct": 1.0,
             "halted": True, "halt_reason": "drawdown 20%"},
            [(hari_ini, 50000, VARIAN[4])])

    terbit = {"dipanggil": 0}

    def stub():
        terbit["dipanggil"] += 1
        return True, "Versi  : 20260918-1800-abc1234"

    k = kt.Kendali(repo=repo, laporan=laporan, terbitkan=stub)
    k.terbit = terbit
    return k


# -- ganti varian dengan nomor ------------------------------------------------

def test_varian_tanpa_argumen_menampilkan_daftar_bernomor(kendali):
    teks = kendali.perintah("/varian")
    assert "1. PC Kantor" in teks and "2. PC3" in teks
    assert f"1. {VARIAN[0]}" in teks and f"{len(VARIAN)}. {VARIAN[-1]}" in teks
    assert "/varian 1 5" in teks


def test_ganti_varian_menulis_penugasan_dan_menerbitkan(kendali):
    teks = kendali.perintah(f"/varian 1 {len(VARIAN)}")
    assert "PC Kantor" in teks and VARIAN[-1] in teks and "Diterbitkan" in teks
    assert kendali.terbit["dipanggil"] == 1
    assert kendali.penugasan()["pc-kantor"] == VARIAN[-1]
    # Penugasan PC lain tidak ikut berubah, komentar file dipertahankan.
    assert kendali.penugasan()["pc3"] == VARIAN[4]
    assert (kendali.repo / rilis.PENUGASAN).read_text(encoding="utf-8").startswith("# catatan")


def test_berhenti_memakai_nomor_pc(kendali):
    assert "berhenti" in kendali.perintah("/berhenti 2")
    assert kendali.penugasan()["pc3"] == "berhenti"


@pytest.mark.parametrize("perintah", ["/varian 9 1", "/varian 1 99", "/varian satu dua",
                                      "/varian 1", "/berhenti", "/berhenti x"])
def test_nomor_salah_ditolak_tanpa_mengubah_apa_pun(kendali, perintah):
    sebelum = kendali.penugasan()
    teks = kendali.perintah(perintah)
    assert kendali.penugasan() == sebelum
    assert kendali.terbit["dipanggil"] == 0
    assert "tidak ada" in teks or "Tulis:" in teks


def test_gagal_terbit_dilaporkan_apa_adanya(tmp_path, kendali):
    kendali.terbitkan = lambda: (False, "!! Tes gagal - rilis dibatalkan.")
    teks = kendali.perintah(f"/varian 1 {len(VARIAN)}")
    assert "gagal diterbitkan" in teks and "Tes gagal" in teks


def test_varian_yang_sama_tidak_menerbitkan_ulang(kendali):
    teks = kendali.perintah("/varian 1 4")
    assert "memang sudah" in teks
    assert kendali.terbit["dipanggil"] == 0


# -- info -----------------------------------------------------------------------

def test_saldo(kendali):
    teks = kendali.perintah("/saldo")
    assert "PC Kantor" in teks and "Rp 5,208,252" in teks
    assert "floating +Rp 23,252" in teks          # equity - balance
    assert "Total equity Rp 8,308,252" in teks    # dua akun dijumlah


def test_hari_ini_dan_minggu(kendali):
    hari = kendali.perintah("/hariini")
    assert "PC Kantor: 1 trade (0 menang) · -Rp 158,199" in hari
    assert "PC3: 1 trade (1 menang) · +Rp 50,000" in hari
    assert "Semua PC: 2 trade (1 menang) · -Rp 108,199" in hari

    minggu = kendali.perintah("/minggu")
    assert "Minggu ini" in minggu and "rem -8%" in minggu


def test_total_dan_trade_terakhir(kendali):
    total = kendali.perintah("/total")
    assert "3 trade · winrate 67%" in total
    assert "+Rp 131,801" in total                  # -158.199 + 240.000 + 50.000
    assert VARIAN[3] in total and VARIAN[4] in total

    trade = kendali.perintah("/trade 2")
    assert "2 trade terakhir" in trade
    assert "pc-kantor" in trade or "pc3" in trade


def test_rem_menampilkan_batas_dan_halt(kendali):
    teks = kendali.perintah("/rem")
    assert "trade 2/12" in teks and "loss beruntun 2/3" in teks
    assert "rem -4%" in teks and "halt di 20%" in teks
    assert "🛑 HALT: drawdown 20%" in teks


# -- pengaman -------------------------------------------------------------------

def test_tidak_ada_perintah_berisiko(kendali):
    for perintah in ("/tutup", "/closeall", "/lepasrem", "/halt", "/restart"):
        teks = kendali.perintah(perintah)
        assert "tidak dikenal" in teks
    # Tidak ada BARIS PERINTAH yang menawarkan hal berisiko; kalimat
    # penutup boleh menyebutnya justru untuk menegaskan itu tidak ada.
    perintah_ada = [b.lower() for b in kt.BANTUAN.splitlines() if b.startswith("/")]
    assert not any("tutup" in b or "lepas" in b or "halt" in b for b in perintah_ada)


def test_pesan_biasa_diabaikan(kendali):
    assert kendali.perintah("halo bre") is None
    assert kendali.perintah("") is None


def test_perintah_dengan_nama_bot_di_grup(kendali):
    assert kendali.perintah("/status@AiTradeBot") == kendali.perintah("/status")
