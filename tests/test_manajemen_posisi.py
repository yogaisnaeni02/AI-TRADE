"""
Tes aturan manajemen posisi (src/execution/manajemen_posisi.py).

Dijalankan tanpa pytest dan tanpa MetaTrader5:

    python tests/test_manajemen_posisi.py

Modul ini dipakai BERSAMA oleh bot live dan backtest/simulasi_live.py,
jadi tes di sini sekaligus menjaga keduanya tetap memutuskan hal yang sama.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.execution.manajemen_posisi import (  # noqa: E402
    ParamPosisi,
    putuskan,
    skor_awal_dari_data,
)
from src.strategy.setups import hitung_skor100  # noqa: E402

T = pd.Timestamp("2026-09-10 10:00")
M5 = pd.Timedelta(minutes=5)
P = ParamPosisi(breakeven_at_r=2.4, trail_atr_mult=2.0, max_bars_hold=48,
                spread_harga=0.26, autoclose_score_drop=20)


def bar(close: float, t: pd.Timestamp = T + 2 * M5, atr: float = 4.0, tinggi: bool = True):
    """Bar dengan skor100 tinggi (~100) atau rendah (~18) untuk arah buy."""
    return SimpleNamespace(
        time_utc=t, close=close, atr=atr,
        open=close - 1 if tinggi else close + 1,
        mom_24=1.5 if tinggi else 0.0, mom_24_q85=1.0,
        trend_htf="uptrend" if tinggi else "ranging",
        adx=30.0 if tinggi else 10.0, fib_position=0.9 if tinggi else 0.6,
        atr_percentile=0.5 if tinggi else 0.9, stoch_k=80.0 if tinggi else 50.0,
    )


def info(**kw) -> dict:
    d = {"entry": 4400.0, "sl_dist": 4.26, "be_done": False, "bar_entry": T, "score100": 0}
    d.update(kw)
    return d


# -- break-even dan trailing ---------------------------------------------


def test_be_dipicu_tepat_di_ambang():
    ambang = 4400.0 + 4.26 * 2.4
    k = putuskan(info(), True, 4395.74, bar(ambang), None, P)
    assert k.be_baru and abs(k.sl_baru - 4400.26) < 1e-9, k
    k = putuskan(info(), True, 4395.74, bar(ambang - 0.01), None, P)
    assert k.sl_baru is None and not k.be_baru, k


def test_be_sisi_sell():
    k = putuskan(info(), False, 4404.26, bar(4400.0 - 4.26 * 2.4), None, P)
    assert k.be_baru and abs(k.sl_baru - 4399.74) < 1e-9, k


def test_harga_ekstrem_memicu_be():
    """Simulasi per menit mengoper high menit itu; close saja belum cukup."""
    k = putuskan(info(), True, 4395.74, bar(4405.0), None, P, harga_ekstrem=4411.0)
    assert k.be_baru, k


def test_trailing_hanya_membaik():
    k = putuskan(info(be_done=True), True, 4400.26, bar(4412.0), None, P)
    assert abs(k.sl_baru - 4404.0) < 1e-9, k
    k = putuskan(info(be_done=True), True, 4405.0, bar(4412.0), None, P)
    assert k.sl_baru is None, "trailing tidak boleh melebarkan SL"
    k = putuskan(info(be_done=True), False, 4399.74, bar(4388.0), None, P)
    assert abs(k.sl_baru - 4396.0) < 1e-9, k


def test_tanpa_atr_tidak_ada_keputusan():
    k = putuskan(info(score100=95), True, 4395.74, bar(4420.0, atr=float("nan")), None, P)
    assert k.sl_baru is None and k.tutup is None, k


# -- auto-close ----------------------------------------------------------


def test_autoclose_hanya_saat_profit():
    rendah_rugi = bar(4399.0, tinggi=False)
    assert putuskan(info(score100=95), True, 4395.74, rendah_rugi, None, P).tutup is None

    rendah_untung = bar(4401.0, tinggi=False)
    k = putuskan(info(score100=95), True, 4395.74, rendah_untung, None, P)
    assert k.tutup == "autoclose", k
    assert k.skor_kini == hitung_skor100(rendah_untung, "buy"), k


def test_autoclose_mati_tanpa_skor_awal():
    k = putuskan(info(score100=0), True, 4395.74, bar(4401.0, tinggi=False), None, P)
    assert k.tutup is None, k


def test_autoclose_mode_bar_tutup():
    p = replace(P, autoclose_bar="tutup")
    berjalan_rendah = bar(4402.0, tinggi=False)

    # Bar berjalan anjlok, tetapi bar tutup masih kuat -> tidak ditutup.
    k = putuskan(info(score100=95), True, 4395.74, berjalan_rendah, bar(4401.0, t=T + M5), p)
    assert k.tutup is None, k

    # Bar tutup yang melemah dan profit -> ditutup.
    k = putuskan(info(score100=95), True, 4395.74, berjalan_rendah,
                 bar(4401.0, t=T + M5, tinggi=False), p)
    assert k.tutup == "autoclose", k

    # Bar tutup = bar sinyal itu sendiri belum membawa informasi baru.
    k = putuskan(info(score100=95), True, 4395.74, berjalan_rendah,
                 bar(4401.0, t=T, tinggi=False), p)
    assert k.tutup is None, k


# -- timeout -------------------------------------------------------------


def test_timeout_dari_selisih_waktu_bar():
    k = putuskan(info(), True, 4395.74, bar(4401.0, t=T + 48 * M5), None, P)
    assert k.tutup is None and k.umur_bar == 48, k
    k = putuskan(info(), True, 4395.74, bar(4401.0, t=T + 49 * M5), None, P)
    assert k.tutup == "timeout" and k.umur_bar == 49, k


# -- rekonstruksi & config -----------------------------------------------


def test_skor_awal_dari_data_bar_sinyal():
    kuat, lemah = bar(4400.0, t=T), bar(4401.0, t=T + M5, tinggi=False)
    df = pd.DataFrame([vars(kuat), vars(lemah)])

    skor, bar_sinyal = skor_awal_dari_data(df, T + M5 + pd.Timedelta(seconds=7), "buy")
    assert bar_sinyal == T, bar_sinyal
    assert skor == hitung_skor100(df.iloc[0], "buy") and skor > 0, skor

    skor, bar_sinyal = skor_awal_dari_data(df, T + 4 * M5, "buy")
    assert (skor, bar_sinyal) == (0, None), (skor, bar_sinyal)


def test_param_dari_config():
    cfg = {
        "position_management": {"breakeven_at_r": 2.4, "trail_atr_mult": 2.0,
                                "max_bars_hold": 48, "autoclose_score_drop": 15,
                                "autoclose_bar": "tutup"},
        "costs": {"spread_points": 260},
        "symbol": {"point": 0.001},
    }
    p = ParamPosisi.dari_config(cfg)
    assert (p.autoclose_score_drop, p.autoclose_bar) == (15, "tutup"), p
    assert abs(p.spread_harga - 0.26) < 1e-12, p

    cfg["position_management"]["autoclose_bar"] = "kemarin"
    try:
        ParamPosisi.dari_config(cfg)
    except ValueError:
        pass
    else:
        raise AssertionError("mode bar tak dikenal harus ditolak")


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
