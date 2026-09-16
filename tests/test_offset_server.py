"""
Tes pelacak offset jam server (src/data/offset_server.py), tanpa MetaTrader5.

    python tests/test_offset_server.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.offset_server import KONFIRMASI_MENIT, PelacakOffset, ukur  # noqa: E402

# Selasa 21:00 UTC - awal jeda harian emas (04:00 WIB).
NOW = datetime(2026, 9, 15, 21, 0, tzinfo=timezone.utc)


def epoch(dt: datetime) -> int:
    return int(dt.timestamp())


def test_ukur_menandai_tick_basi():
    assert ukur(epoch(NOW - timedelta(seconds=3)), NOW) == (0, True)
    assert ukur(epoch(NOW - timedelta(minutes=31)), NOW) == (-1, False)
    assert ukur(epoch(NOW - timedelta(hours=49)), NOW)[1] is False


def test_tick_segar_dipakai():
    p = PelacakOffset(offset_config=0)
    assert p.perbarui(epoch(NOW - timedelta(seconds=2)), NOW) == 0


def test_jeda_harian_tidak_menggeser_jam():
    """Regresi: tick 21:00 yang dibaca sampai 22:10 dulu menghasilkan -1."""
    p = PelacakOffset(offset_config=0)
    tick = epoch(NOW)
    for menit in range(0, 71):
        got = p.perbarui(tick, NOW + timedelta(minutes=menit))
        assert got == 0, f"menit {menit}: offset {got}"


def test_restart_akhir_pekan_tidak_menebak_dari_tick_jumat():
    p = PelacakOffset(offset_config=0)
    assert p.perbarui(epoch(NOW - timedelta(hours=49)), NOW) == 0


def test_perubahan_sungguhan_terdeteksi_setelah_konfirmasi():
    p = PelacakOffset(offset_config=0)
    for menit in range(0, KONFIRMASI_MENIT):
        now = NOW + timedelta(minutes=menit)
        assert p.perbarui(epoch(now + timedelta(hours=1)), now) == 0, menit
    now = NOW + timedelta(minutes=KONFIRMASI_MENIT)
    assert p.perbarui(epoch(now + timedelta(hours=1)), now) == 1
    pesan = p.ambil_pesan()
    assert any("BERUBAH" in m for m in pesan), pesan
    assert p.ambil_pesan() == [], "pesan harus dikosongkan setelah dibaca"


def test_tanpa_config_tick_basi_menolak_menebak():
    p = PelacakOffset(offset_config=None)
    try:
        p.perbarui(epoch(NOW - timedelta(minutes=31)), NOW)
    except ConnectionError:
        pass
    else:
        raise AssertionError("tanpa config dan tick basi harus menolak, bukan menebak")


def test_tanpa_config_tick_segar_diukur():
    p = PelacakOffset(offset_config=None)
    assert p.perbarui(epoch(NOW + timedelta(hours=2)), NOW) == 2


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = []
    for fn in tests:
        try:
            fn()
        except AssertionError as e:
            failed.append((fn.__name__, f"assert gagal: {e}"))
        except Exception as e:  # noqa: BLE001
            failed.append((fn.__name__, f"{type(e).__name__}: {e}"))
        else:
            print(f"  ok    {fn.__name__}")
    for name, why in failed:
        print(f"  GAGAL {name} -> {why}")
    print(f"\n{len(tests) - len(failed)}/{len(tests)} lolos")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
