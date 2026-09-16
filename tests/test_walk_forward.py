"""
Tes alat walk-forward (backtest/walk_forward.py).

Yang paling berbahaya dari alat semacam ini bukan salah hitung, melainkan
KEBOCORAN: periode uji memuat data yang sudah dipakai memilih. Tes pertama
di bawah mengunci itu.

    python tests/test_walk_forward.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.simulasi_live import FiturBarBerjalan, MIN_RIWAYAT, Posisi  # noqa: E402
from backtest.walk_forward import buat_lipatan, potong, skor  # noqa: E402

MULAI = pd.Timestamp("2026-01-01")


# -- pembentukan lipatan -------------------------------------------------


def test_uji_tidak_pernah_memuat_periode_latih():
    lipatan = buat_lipatan(MULAI, MULAI + pd.Timedelta(days=90), latih=30, uji=14, langkah=14)
    assert lipatan, "harus ada lipatan"
    for lip in lipatan:
        assert lip.uji_dari == lip.latih_sampai, lip
        assert lip.latih_dari + pd.Timedelta(days=30) == lip.latih_sampai, lip
        assert lip.uji_sampai - lip.uji_dari == pd.Timedelta(days=14), lip
        assert lip.uji_dari > lip.latih_dari, lip


def test_lipatan_bergeser_dan_berhenti_di_akhir_periode():
    akhir = MULAI + pd.Timedelta(days=90)
    lipatan = buat_lipatan(MULAI, akhir, latih=30, uji=14, langkah=14)
    assert lipatan[0].latih_dari == MULAI
    assert lipatan[1].latih_dari - lipatan[0].latih_dari == pd.Timedelta(days=14)
    assert all(lip.uji_sampai <= akhir for lip in lipatan), "uji tidak boleh melewati akhir data"
    assert [lip.no for lip in lipatan] == list(range(1, len(lipatan) + 1))


def test_periode_terlalu_pendek_tidak_menghasilkan_lipatan():
    assert buat_lipatan(MULAI, MULAI + pd.Timedelta(days=40), latih=30, uji=14, langkah=14) == []


# -- pemotongan jendela --------------------------------------------------


def _feat(n: int = 1200) -> pd.DataFrame:
    """Frame minimal: potong() hanya memakai time_utc, bukan nilai indikator."""
    return pd.DataFrame({
        "time_utc": pd.date_range(MULAI, periods=n, freq="5min"),
        "open": 4000.0, "high": 4001.0, "low": 3999.0, "close": 4000.0,
        "atr": 4.0, "plus_di": 20.0, "minus_di": 10.0, "adx": 25.0,
        "mom_24_q85": 1.0, "trend_htf": "uptrend",
    })


def test_potong_menolak_jendela_tanpa_riwayat_cukup():
    feat = _feat()
    fitur = FiturBarBerjalan(feat)
    awal = feat["time_utc"].iloc[0]
    # Jendela di awal data: bar sebelumnya tidak cukup untuk fitur bar berjalan.
    assert potong(feat, fitur, {}, awal, awal + pd.Timedelta(hours=2)) is None


def test_potong_memilih_bar_dan_m1_di_dalam_jendela():
    feat = _feat()
    fitur = FiturBarBerjalan(feat)
    dari = feat["time_utc"].iloc[MIN_RIWAYAT + 10]
    sampai = dari + pd.Timedelta(hours=1)
    per_bar = {t: pd.DataFrame({"time_utc": [t]}) for t in feat["time_utc"]}

    data = potong(feat, fitur, per_bar, dari, sampai)
    assert data is not None
    assert feat["time_utc"].iloc[data.k0] == dari
    assert feat["time_utc"].iloc[data.k1] < sampai
    assert all(dari <= t < sampai + pd.Timedelta(minutes=5) for t in data.m1_per_bar)


def test_potong_mengembalikan_none_di_luar_data():
    feat = _feat()
    fitur = FiturBarBerjalan(feat)
    jauh = feat["time_utc"].iloc[-1] + pd.Timedelta(days=5)
    assert potong(feat, fitur, {}, jauh, jauh + pd.Timedelta(days=1)) is None


# -- kriteria pemilihan --------------------------------------------------


def _posisi(r: float, alasan: str = "TP") -> Posisi:
    return Posisi(no=1, arah="buy", tier="full", skor100=90, waktu_sinyal=MULAI,
                  waktu_entry=MULAI, entry=4000.0, sl=3996.0, tp=4011.0, sl_awal=3996.0,
                  r_dist=4.0, tp_dist=11.0, lot=0.01, alasan=alasan, r=r,
                  waktu_exit=MULAI + pd.Timedelta(minutes=30), pnl_idr=r * 70_000)


def test_skor_memakai_kriteria_yang_diminta():
    res = {"trades": [_posisi(2.5), _posisi(-1.0), _posisi(-1.0)]}
    assert abs(skor(res, "totR") - 0.5) < 1e-9, skor(res, "totR")
    assert abs(skor(res, "ER") - 0.5 / 3) < 1e-9, skor(res, "ER")


def test_skor_tanpa_trade_paling_buruk():
    """Kandidat tanpa trade tidak boleh menang hanya karena nilainya NaN."""
    assert skor({"trades": []}, "ER") == float("-inf")
    assert skor({"trades": [_posisi(1.0)]}, "t") == float("-inf")   # t butuh >2 trade


# -- runner --------------------------------------------------------------


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
