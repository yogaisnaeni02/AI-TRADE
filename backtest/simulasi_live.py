"""
Simulasi varian SEPERTI BOT LIVE, per bar M1.

KENAPA ADA (di samping backtest/engine.py)
------------------------------------------
engine.py mensimulasikan manajemen posisi versinya sendiri di close bar M5:
trailing tanpa langkah titik impas, tanpa auto-close, tanpa mode batch.
Varian yang bedanya justru di situ (autoclose, autoclose_agresif, pyramid5)
tidak bisa diukur jujur di sana - autoclose tampil identik dengan induknya.

Skrip ini memakai kode yang SAMA dengan bot:
  - RuleEngine untuk sinyal (bar M5 tutup, entry di open bar berikutnya)
  - manajemen_posisi.putuskan() untuk BE, trailing, auto-close, timeout
  - RiskManager produksi, per magic varian (termasuk mode batch)

Yang disimulasikan sendiri hanya "broker" dan waktu:
  - buy masuk di ask (open + spread), sell di bid; SL/TP absolut dari sinyal
  - SL/TP tersentuh di high/low M1; SL dan TP di menit yang sama -> SL duluan
  - fitur bar M5 yang sedang terbentuk dihitung tiap menit (bot menilai
    auto-close dan trailing pada bar yang belum tutup)

Batasan: bot mengecek tiap ~3 detik, simulasi tiap menit (pemicu BE dan
trailing memakai high/low menit itu). Bar M5 tanpa data M1 disimulasikan
sebagai satu langkah. Tiap varian dianggap punya akun sendiri.

Pemakaian:
  python backtest/simulasi_live.py --dari 2026-06-01 --sampai 2026-09-09
  python backtest/simulasi_live.py --varian dua_arah autoclose --autoclose-bar tutup
  python backtest/simulasi_live.py --feat fitur.parquet --m1 m1.parquet --hari 30
"""

from __future__ import annotations

import argparse
import copy
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.engine import load_configs  # noqa: E402
from src.execution.manajemen_posisi import MODE_BAR_AUTOCLOSE, ParamPosisi, putuskan  # noqa: E402
from src.risk.manager import RiskManager  # noqa: E402
from src.strategy.setups import RuleEngine  # noqa: E402
from src.variants import apply_risk_override, apply_variant, list_variants  # noqa: E402

FEAT_DEFAULT = ROOT / "data" / "processed" / "XAUUSDm_M5_features.parquet"
M1_DEFAULT = ROOT / "data" / "raw" / "XAUUSDm_M1.parquet"
WIB = pd.Timedelta(hours=7)  # jam PC bot; rem harian mengikuti tanggal lokal
BAR = pd.Timedelta(minutes=5)
ALPHA = 1 / 14
MIN_RIWAYAT = 600
KOLOM_SKOR = ("time_utc", "open", "close", "mom_24", "mom_24_q85", "trend_htf",
              "adx", "fib_position", "atr_percentile", "stoch_k")
DILEWATI = {"ml_walkforward": "override kosong - filter ML belum terintegrasi ke RuleEngine"}
PASANGAN_AUTOCLOSE = (("dua_arah", "autoclose"), ("pyramid5", "autoclose_agresif"))


class FiturBarBerjalan:
    """Fitur bar M5 yang SEDANG terbentuk, dihitung inkremental dari bar k-1.

    Rumus identik dengan src/features/indicators.py (EWM Wilder
    adjust=False, jendela rolling 14/100/200) - tests/test_simulasi_live.py
    membandingkannya dengan pipeline asli. Menghitung ulang ratusan bar tiap
    menit simulasi terlalu lambat untuk periode berbulan-bulan.
    """

    def __init__(self, feat: pd.DataFrame):
        self.t = feat["time_utc"].to_numpy()
        self.H, self.L, self.C, self.O = (
            feat[c].to_numpy(float) for c in ("high", "low", "close", "open"))
        self.ATR, self.PDI, self.MDI, self.ADX = (
            feat[c].to_numpy(float) for c in ("atr", "plus_di", "minus_di", "adx"))
        self.Q85 = feat["mom_24_q85"].to_numpy(float)
        self.HTF = feat["trend_htf"].to_numpy(object)

    def hitung(self, k: int, ph: float, pl: float, pc: float) -> SimpleNamespace:
        H, L, C, ATR = self.H, self.L, self.C, self.ATR
        o = self.O[k]
        ph, pl = max(ph, o), min(pl, o)
        tr = max(ph - pl, abs(ph - C[k - 1]), abs(pl - C[k - 1]))
        atr = ATR[k - 1] + ALPHA * (tr - ATR[k - 1])

        up, dn = ph - H[k - 1], L[k - 1] - pl
        pdm = up if (up > dn and up > 0) else 0.0
        mdm = dn if (dn > up and dn > 0) else 0.0
        pe = self.PDI[k - 1] * ATR[k - 1] / 100
        me = self.MDI[k - 1] * ATR[k - 1] / 100
        pe += ALPHA * (pdm - pe)
        me += ALPHA * (mdm - me)
        pdi, mdi = 100 * pe / atr, 100 * me / atr
        dx = 100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) else np.nan
        adx = self.ADX[k - 1] + ALPHA * (dx - self.ADX[k - 1]) if dx == dx else self.ADX[k - 1]

        lo100, hi100 = min(L[k - 99:k].min(), pl), max(H[k - 99:k].max(), ph)
        lo14, hi14 = min(L[k - 13:k].min(), pl), max(H[k - 13:k].max(), ph)
        win = ATR[k - 199:k]
        less = float(np.sum(win < atr))
        eq = float(np.sum(win == atr)) + 1.0
        return SimpleNamespace(
            time_utc=self.t[k], atr=atr, open=o, close=pc,
            mom_24=(pc - C[k - 24]) / atr, mom_24_q85=self.Q85[k], trend_htf=self.HTF[k],
            adx=adx,
            fib_position=(pc - lo100) / (hi100 - lo100) if hi100 > lo100 else np.nan,
            atr_percentile=(less + (eq + 1) / 2) / 200,
            stoch_k=100 * (pc - lo14) / (hi14 - lo14) if hi14 > lo14 else np.nan,
        )


@dataclass
class DataSimulasi:
    feat: pd.DataFrame
    fitur: FiturBarBerjalan
    m1_per_bar: dict
    k0: int
    k1: int
    start: pd.Timestamp
    end: pd.Timestamp

    def baris_tutup(self, k: int) -> SimpleNamespace:
        r = self.feat.iloc[k - 1]
        return SimpleNamespace(**{c: r[c] for c in KOLOM_SKOR})


def muat_data(feat_path, m1_path, dari=None, sampai=None, hari=None) -> DataSimulasi:
    feat = pd.read_parquet(feat_path)
    feat["time_utc"] = feat["time_utc"].astype("datetime64[ns]")
    feat = feat.sort_values("time_utc").reset_index(drop=True)

    end = feat["time_utc"].max() + BAR
    if sampai is not None:
        end = min(end, pd.Timestamp(sampai))
    if dari is not None:
        start = pd.Timestamp(dari)
    elif hari is not None:
        start = end - pd.Timedelta(days=float(hari))
    else:
        raise ValueError("isi --dari atau --hari")

    idx = feat.index[(feat["time_utc"] >= start) & (feat["time_utc"] < end)]
    if len(idx) == 0:
        raise ValueError(f"tidak ada bar M5 di {start} -> {end}")
    k0, k1 = int(idx.min()), int(idx.max())
    if k0 < MIN_RIWAYAT:
        raise ValueError(f"butuh >= {MIN_RIWAYAT} bar M5 sebelum jendela; mulai lebih lambat")

    m1 = pd.read_parquet(m1_path, columns=["time_utc", "open", "high", "low", "close", "tick_volume"])
    m1["time_utc"] = m1["time_utc"].astype("datetime64[ns]")
    m1 = m1[(m1["time_utc"] >= start) & (m1["time_utc"] < end + BAR)].sort_values("time_utc")
    m1["bar"] = m1["time_utc"].dt.floor("5min")
    per_bar = {t: g.drop(columns="bar").reset_index(drop=True) for t, g in m1.groupby("bar")}
    return DataSimulasi(feat, FiturBarBerjalan(feat), per_bar, k0, k1, start, end)


@dataclass
class Opsi:
    # Equity akun demo saat simulasi dibuat. risk_limits.simulated_equity_idr
    # (Rp 4 jt) SAMA dengan min_equity_idr, jadi rugi pertama saja sudah
    # membuat varian diblok "equity di bawah minimum".
    equity: float = 5_500_000.0
    tanpa_halt_dd: bool = False
    autoclose_bar: Optional[str] = None


@dataclass
class Posisi:
    no: int
    arah: str
    tier: str
    skor100: int
    waktu_sinyal: pd.Timestamp
    waktu_entry: pd.Timestamp
    entry: float
    sl: float
    tp: float
    sl_awal: float
    r_dist: float
    tp_dist: float
    lot: float
    info: dict = field(default_factory=dict)
    waktu_be: Optional[pd.Timestamp] = None
    mfe: float = 0.0
    skor_min: Optional[int] = None
    waktu_exit: Optional[pd.Timestamp] = None
    harga_exit: float = float("nan")
    alasan: str = ""
    pnl_idr: float = 0.0
    r: float = 0.0

    @property
    def jenis(self) -> str:
        return "autoclose" if self.alasan.startswith("autoclose") else self.alasan


def jalankan_varian(nama: str, data: DataSimulasi, settings: dict, risk: dict, opsi: Opsi) -> dict:
    feat, fitur, k0, k1 = data.feat, data.fitur, data.k0, data.k1
    cfg, magic, meta = apply_variant(settings, nama)
    if opsi.autoclose_bar is not None:
        cfg = copy.deepcopy(cfg)
        cfg.setdefault("position_management", {})["autoclose_bar"] = opsi.autoclose_bar
    rk = copy.deepcopy(apply_risk_override(risk, nama))
    if opsi.tanpa_halt_dd:
        # Sama dengan bandingkan_varian.py: halt DD memotong PERIODE, bukan
        # guardrail harian yang memang bagian dari strategi (docs/38).
        rk["global"]["max_drawdown_percent"] = 1e5

    param = ParamPosisi.dari_config(cfg)
    eng = RuleEngine(config=cfg)
    sigs = eng.generate(feat.loc[k0:k1])
    if not sigs.empty:
        sigs["time"] = pd.to_datetime(sigs["time"])
    sig_by_idx = {int(s.idx): s for s in sigs.itertuples()} if not sigs.empty else {}

    point, vpp = cfg["symbol"]["point"], cfg["symbol"]["value_per_point_idr"]
    spr_pts = cfg["costs"]["spread_points"]
    spr = spr_pts * point

    tmp = tempfile.TemporaryDirectory(prefix=f"simlive_{nama}_")
    rm = RiskManager(cfg, risk=rk, journal_path=Path(tmp.name) / "tidak_dipakai.csv",
                     state_path=Path(tmp.name) / "risk_state.json", magic=magic)
    rm.state.peak_equity = opsi.equity

    saldo = opsi.equity
    kurva = [opsi.equity]
    journal: list[dict] = []
    buka: list[Posisi] = []
    selesai: list[Posisi] = []
    tolak: Counter = Counter()
    hari_min_equity: set = set()
    no = 0

    def floating(bid: float) -> float:
        tot = 0.0
        for p in buka:
            g = (bid - p.entry) if p.arah == "buy" else (p.entry - (bid + spr))
            tot += g / point * vpp * p.lot
        return tot

    def tutup(p: Posisi, harga: float, waktu: pd.Timestamp, alasan: str, catat: bool = True) -> None:
        nonlocal saldo
        gross = (harga - p.entry) if p.arah == "buy" else (p.entry - harga)
        p.harga_exit, p.waktu_exit, p.alasan = harga, waktu, alasan
        p.pnl_idr = gross / point * vpp * p.lot
        p.r = gross / p.r_dist
        buka.remove(p)
        selesai.append(p)
        if catat:
            saldo += p.pnl_idr
            kurva.append(saldo)
            journal.append({
                "ticket": p.no, "entry_time": (p.waktu_entry + WIB).isoformat(),
                "exit_time": (waktu + WIB).isoformat(), "net_idr": round(p.pnl_idr, 2),
                "magic": magic,
            })
            rm.refresh_from_journal((waktu + WIB).to_pydatetime(), trades=journal)

    cl = fitur.O[k0]
    for k in range(k0, k1 + 1):
        t = feat.at[k, "time_utc"]
        o = fitur.O[k]
        now = (t + WIB).to_pydatetime()

        # 1) timeout di siklus pertama bar baru (manage_positions sebelum process_bar)
        if buka:
            di_open = fitur.hitung(k, o, o, o)
            for p in list(buka):
                kep = putuskan(p.info, p.arah == "buy", p.sl, di_open, None, param)
                if kep.umur_bar > param.max_bars_hold:
                    tutup(p, o if p.arah == "buy" else o + spr, t, "timeout")

        # 2) sinyal dari bar yang baru tutup -> gerbang risiko -> entry di open
        s = sig_by_idx.get(k - 1)
        if s is not None:
            rm.refresh_from_journal(now, trades=journal)
            eq = saldo + floating(o)
            rm.observe_equity(eq)
            d = rm.check(
                now=now, equity=eq, sl_points=s.sl_points, tp_points=s.tp_points,
                spread_points=spr_pts, open_positions=len(buka),
                confidence=min(1.0, s.score / 10.0), size_tier=s.size_tier,
                direction=s.direction, open_directions=[p.arah for p in buka],
            )
            if not d.allowed:
                tolak["".join("N" if ch.isdigit() else ch for ch in d.reason)] += 1
                if d.reason.startswith("equity"):
                    hari_min_equity.add(now.date())
            else:
                if s.direction == "buy":
                    entry, valid = o + spr, (s.sl < o) and (s.tp > o)
                else:
                    entry, valid = o, (s.sl > o + spr) and (s.tp < o + spr)
                if not valid:
                    tolak["stops invalid (harga sudah lewat SL/TP saat entry)"] += 1
                else:
                    no += 1
                    buka.append(Posisi(
                        no=no, arah=s.direction, tier=s.size_tier, skor100=int(s.score100),
                        waktu_sinyal=s.time, waktu_entry=t, entry=entry, sl=s.sl, tp=s.tp,
                        sl_awal=s.sl, r_dist=abs(entry - s.sl), tp_dist=abs(s.tp - entry),
                        lot=d.lot,
                        info={"entry": entry, "sl_dist": abs(entry - s.sl), "be_done": False,
                              "bar_entry": s.time, "score100": int(s.score100)},
                    ))

        if not buka:
            continue

        # 3) langkah per menit di dalam bar
        sub = data.m1_per_bar.get(t)
        if sub is None or sub.empty:
            sub = feat.loc[[k], ["time_utc", "open", "high", "low", "close"]].reset_index(drop=True)
        elif fitur.H[k] > sub["high"].max() + 0.05 or fitur.L[k] < sub["low"].min() - 0.05:
            # Menit tanpa transaksi tidak punya bar M1. Ekstrem bar M5 yang tidak
            # tertangkap M1 ditaruh di akhir bar (SL tetap dicek dulu).
            extra = {"time_utc": sub["time_utc"].iloc[-1], "open": sub["close"].iloc[-1],
                     "high": fitur.H[k], "low": fitur.L[k], "close": fitur.C[k]}
            sub = pd.concat([sub, pd.DataFrame([extra])], ignore_index=True)

        bar_tutup = data.baris_tutup(k) if param.autoclose_bar == "tutup" else None
        ph, pl = -np.inf, np.inf
        for row in sub.itertuples(index=False):
            op, hi, lo, cl, tm = row.open, row.high, row.low, row.close, row.time_utc
            ph, pl = max(ph, hi), min(pl, lo)
            fc = None
            for p in list(buka):
                is_buy = p.arah == "buy"
                if is_buy:
                    fav = hi - p.entry
                    hit_sl, hit_tp = lo <= p.sl, hi >= p.tp
                else:
                    fav = p.entry - (lo + spr)
                    hit_sl, hit_tp = hi + spr >= p.sl, lo + spr <= p.tp
                p.mfe = max(p.mfe, fav)

                if hit_sl:
                    harga = min(p.sl, op) if is_buy else max(p.sl, op + spr)
                    tutup(p, harga, tm, "trailing/BE" if p.info["be_done"] else "SL")
                    continue
                if hit_tp:
                    tutup(p, p.tp, tm, "TP")
                    continue

                fc = fc or fitur.hitung(k, ph, pl, cl)
                kep = putuskan(p.info, is_buy, p.sl, fc, bar_tutup, param,
                               harga_ekstrem=hi if is_buy else lo)
                if kep.sl_baru is not None:
                    if kep.be_baru:
                        p.info["be_done"], p.waktu_be = True, tm
                    # order_manager.modify_position menolak SL yang melebar
                    if (is_buy and kep.sl_baru > p.sl) or (not is_buy and kep.sl_baru < p.sl):
                        p.sl = kep.sl_baru
                if kep.skor_kini is not None:
                    p.skor_min = kep.skor_kini if p.skor_min is None else min(p.skor_min, kep.skor_kini)
                if kep.tutup is not None:
                    alasan = (f"autoclose ({kep.skor_awal}->{kep.skor_kini})"
                              if kep.tutup == "autoclose" else kep.tutup)
                    tutup(p, cl if is_buy else cl + spr, tm, alasan)
            if buka:
                rm.observe_equity(saldo + floating(cl))

    for p in list(buka):
        tutup(p, cl if p.arah == "buy" else cl + spr, data.end, "masih terbuka", catat=False)

    kv = np.array(kurva)
    puncak = np.maximum.accumulate(kv)
    hasil = {
        "name": nama, "magic": magic, "meta": meta, "cfg": cfg, "risk": rk, "param": param,
        "sigs": sigs, "trades": selesai, "tolak": tolak, "saldo": saldo,
        "max_dd": float(((puncak - kv) / puncak).max() * 100),
        "halt": rm.state.halt_reason if rm.state.halted else "",
        "hari_min_equity": sorted(hari_min_equity),
    }
    tmp.cleanup()
    return hasil


# -- laporan ----------------------------------------------------------------


def rp(x: float) -> str:
    return f"Rp {x:,.0f}".replace(",", ".")


def ringkas(tr: list[Posisi]) -> dict:
    tut = [p for p in tr if p.alasan != "masih terbuka"]
    a = Counter(p.jenis for p in tr)
    r = np.array([p.r for p in tut]) if tut else np.array([])
    return {
        "n": len(tr), "TP": a["TP"], "SL": a["SL"], "trail": a["trailing/BE"],
        "AC": a["autoclose"], "tmout": a["timeout"], "open": a["masih terbuka"],
        "wr": float((r > 0).mean()) if len(r) else float("nan"),
        "R": float(r.sum()) if len(r) else 0.0,
        "ER": float(r.mean()) if len(r) else float("nan"),
        "t": float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))) if len(r) > 2 and r.std(ddof=1) > 0 else float("nan"),
        "pnl": sum(p.pnl_idr for p in tut),
    }


def episode(sigs: pd.DataFrame) -> int:
    if sigs.empty:
        return 0
    s = sigs.sort_values("idx")
    return int(((s["idx"].diff() != 1) | (s["direction"] != s["direction"].shift())).sum())


def status(res: dict) -> str:
    bagian = []
    if res["halt"]:
        bagian.append("HALT")
    if res["hari_min_equity"]:
        bagian.append(f"equity<min sejak {res['hari_min_equity'][0]:%d %b}")
    return ", ".join(bagian) or "-"


def cetak(res: dict, mingguan: bool, detail: bool) -> None:
    cfg, rk, param = res["cfg"], res["risk"], res["param"]
    mf = cfg["momentum_fib"]
    tr = res["trades"]
    st = ringkas(tr)
    sig = res["sigs"]
    n_buy = int((sig["direction"] == "buy").sum()) if not sig.empty else 0

    print("\n" + "=" * 100)
    print(f"VARIAN {res['name']}  (magic {res['magic']}) | sell={mf.get('allow_sell')} "
          f"konfluensi={mf.get('confluence_filter')} fib={mf.get('fib_buy_min', 0.75)}/"
          f"{mf.get('fib_sell_max', 0.25)} maxpos={rk['global']['max_open_positions']} "
          f"loss_mode={rk['daily'].get('loss_mode', 'trade')} autoclose="
          + (f"{param.autoclose_score_drop}/bar-{param.autoclose_bar}" if param.autoclose_score_drop else "mati"))
    print(f"  Sinyal {len(sig)} bar (buy {n_buy}, sell {len(sig) - n_buy}) dalam {episode(sig)} episode"
          f" | entry {st['n']} | ditolak {sum(res['tolak'].values())}: "
          + "; ".join(f"{n}x {why}" for why, n in res["tolak"].most_common(3)))
    print(f"  TP {st['TP']} | SL {st['SL']} | trailing/BE {st['trail']} | autoclose {st['AC']} | "
          f"timeout {st['tmout']} | terbuka {st['open']} || WR {st['wr']:.0%} | "
          f"E[R] {st['ER']:+.3f} (t {st['t']:+.2f}) | total {st['R']:+.2f}R | {rp(st['pnl'])} | "
          f"maxDD {res['max_dd']:.1f}% | {status(res)}")
    sl = [p for p in tr if p.alasan == "SL"]
    if sl:
        b = Counter()
        for p in sl:
            x = min(p.mfe / p.tp_dist, 1.0)
            b["<25%" if x < .25 else "25-50%" if x < .5 else "50-75%" if x < .75
              else "75-90%" if x < .9 else ">=90%"] += 1
        print("  SL penuh menurut jarak terjauh ke TP: "
              + " | ".join(f"{k} {b[k]}" for k in ("<25%", "25-50%", "50-75%", "75-90%", ">=90%")))

    if mingguan and tr:
        per_w: dict = {}
        for p in tr:
            w = (p.waktu_entry + WIB).normalize()
            per_w.setdefault(w - pd.Timedelta(days=w.dayofweek), []).append(p)
        for w in sorted(per_w):
            s2 = ringkas(per_w[w])
            print(f"    minggu {w:%d %b}: entry {s2['n']:>3} | TP {s2['TP']:>2} SL {s2['SL']:>3} "
                  f"trail {s2['trail']:>2} AC {s2['AC']:>3} | {s2['R']:>+7.2f}R {rp(s2['pnl']):>13}")
    if detail:
        for p in tr:
            print(f"    {p.no:>4} {(p.waktu_entry + WIB):%d/%m %H:%M} {p.arah:<4} s100 {p.skor100:>3} "
                  f"maks {min(p.mfe / p.tp_dist, 1.0):>4.0%} TP -> {(p.waktu_exit + WIB):%d/%m %H:%M} "
                  f"{p.r:>+5.2f}R {p.alasan}")


def banding_pasangan(hasil: list[dict], a: str, b: str) -> None:
    """Entry identik di dua varian yang hanya beda cara keluar."""
    ra = next((r for r in hasil if r["name"] == a), None)
    rb = next((r for r in hasil if r["name"] == b), None)
    if ra is None or rb is None:
        return
    ib = {(p.waktu_entry, p.arah): p for p in rb["trades"]}
    n, tot_a, tot_b = 0, 0.0, 0.0
    kat: Counter = Counter()
    d_r: Counter = Counter()
    for p in ra["trades"]:
        q = ib.get((p.waktu_entry, p.arah))
        if q is None:
            continue
        n += 1
        tot_a += p.r
        tot_b += q.r
        if p.jenis == q.jenis and abs(p.r - q.r) <= 0.05:
            continue
        kat[f"{p.jenis} -> {q.jenis}"] += 1
        d_r[f"{p.jenis} -> {q.jenis}"] += q.r - p.r
    print(f"\nPASANGAN {a} -> {b}: {n} entry identik, total {tot_a:+.2f}R -> {tot_b:+.2f}R "
          f"(hanya di {a}: {len(ra['trades']) - n}, hanya di {b}: {len(rb['trades']) - n})")
    for key, c in kat.most_common():
        print(f"    {c:>3}x {key:<28} selisih {d_r[key]:+.2f}R")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--feat", default=str(FEAT_DEFAULT), help="parquet fitur M5 (pipeline.build_dataset)")
    ap.add_argument("--m1", default=str(M1_DEFAULT), help="parquet bar M1")
    ap.add_argument("--dari", help="awal jendela, UTC (mis. 2026-06-01)")
    ap.add_argument("--sampai", help="akhir jendela, UTC, eksklusif (default: akhir data)")
    ap.add_argument("--hari", type=float, help="panjang jendela bila --dari kosong (default 30)")
    ap.add_argument("--varian", nargs="+", help="default: semua varian yang bisa disimulasikan")
    ap.add_argument("--autoclose-bar", choices=MODE_BAR_AUTOCLOSE, default=None,
                    help="timpa position_management.autoclose_bar untuk semua varian")
    ap.add_argument("--tanpa-halt-dd", action="store_true",
                    help="matikan HANYA halt drawdown global (metode bandingkan_varian.py)")
    ap.add_argument("--equity", type=float, default=Opsi.equity)
    ap.add_argument("--mingguan", action="store_true", help="rincian per minggu")
    ap.add_argument("--detail", action="store_true", help="cetak tiap trade")
    ap.add_argument("--csv", help="simpan semua trade ke file ini")
    args = ap.parse_args()
    if args.dari is None and args.hari is None:
        args.hari = 30

    data = muat_data(args.feat, args.m1, args.dari, args.sampai, args.hari)
    settings, risk = load_configs()
    semua = list_variants()
    names = args.varian or [n for n in semua if n not in DILEWATI]
    unknown = [n for n in names if n not in semua]
    if unknown:
        print(f"Varian tidak dikenal: {unknown}. Tersedia: {', '.join(semua)}")
        return 1

    bar_m1 = sum(1 for k in range(data.k0, data.k1 + 1) if data.feat.at[k, "time_utc"] in data.m1_per_bar)
    n_bar = data.k1 - data.k0 + 1
    print(f"Jendela {data.start + WIB:%d %b %Y %H:%M} -> {data.end + WIB:%d %b %Y %H:%M} WIB | "
          f"{n_bar} bar M5, {bar_m1 / n_bar:.0%} punya data M1 | equity awal {rp(args.equity)} | "
          + ("halt DD dimatikan" if args.tanpa_halt_dd else "semua rem aktif")
          + (f" | autoclose_bar={args.autoclose_bar}" if args.autoclose_bar else ""))

    opsi = Opsi(equity=args.equity, tanpa_halt_dd=args.tanpa_halt_dd, autoclose_bar=args.autoclose_bar)
    hasil = []
    for name in names:
        res = jalankan_varian(name, data, settings, risk, opsi)
        cetak(res, args.mingguan, args.detail)
        hasil.append(res)

    print("\n" + "=" * 100)
    print(f"{'varian':<20} {'sinyal':>6} {'entry':>5} {'TP':>4} {'SL':>4} {'trail':>5} {'autoC':>5} "
          f"{'WR':>4} {'E[R]':>7} {'t':>6} {'totR':>8} {'P/L':>14} {'maxDD':>6}  status")
    rows = []
    for res in hasil:
        st = ringkas(res["trades"])
        print(f"{res['name']:<20} {len(res['sigs']):>6} {st['n']:>5} {st['TP']:>4} {st['SL']:>4} "
              f"{st['trail']:>5} {st['AC']:>5} {st['wr'] if st['n'] else 0:>4.0%} {st['ER']:>+7.3f} "
              f"{st['t']:>+6.2f} {st['R']:>+8.2f} {rp(st['pnl']):>14} {res['max_dd']:>5.1f}%  {status(res)}")
        for p in res["trades"]:
            d = {k: v for k, v in p.__dict__.items() if k != "info"}
            rows.append({"varian": res["name"], **d})

    for a, b in PASANGAN_AUTOCLOSE:
        banding_pasangan(hasil, a, b)

    if args.csv:
        pd.DataFrame(rows).to_csv(args.csv, index=False)
        print(f"\nTrade disimpan: {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
