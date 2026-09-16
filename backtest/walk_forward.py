"""
Walk-forward: pilih setelan di periode LATIH, ukur di periode UJI, lalu maju.

PERTANYAAN YANG DIJAWAB
-----------------------
"Varian mana yang sedang bagus?" hanya berguna kalau jawabannya BERTAHAN ke
periode berikutnya. Membandingkan varian pada satu periode penuh (yang
dilakukan bandingkan_varian.py dan simulasi_live.py) tidak menjawab itu:
pemenangnya dipilih memakai data yang sama dengan data yang menilainya.

Skrip ini memisahkannya:

    |--- latih 30 hari ---|--- uji 14 hari ---|
                          |--- latih 30 hari ---|--- uji 14 hari ---|
                                                ...

Di tiap lipatan, kandidat dijalankan pada periode LATIH, satu dipilih
menurut kriteria yang dinyatakan di muka, lalu HANYA pilihan itu dijalankan
pada periode UJI yang belum pernah dilihat. Hasil uji seluruh lipatan
disambung - itulah hasil "pemilih otomatis".

Pembandingnya: menjalankan SATU varian tetap di periode uji yang sama persis.
Kalau pemilih tidak mengalahkan varian tetap terbaik, memilih berdasarkan
performa terakhir hanya mengejar kebisingan - dan itu jawaban yang berguna,
bukan kegagalan skrip.

Equity dibawa maju antar lipatan (rem risiko dan min_equity ikut bekerja),
tetapi R per trade tetap dilaporkan karena skala-invariant.

Pemakaian:
    python backtest/walk_forward.py --dari 2026-06-01 --sampai 2026-09-09
    python backtest/walk_forward.py --latih 45 --uji 21 --pilih ER
    python backtest/walk_forward.py --kandidat baseline konfluensi dua_arah
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.engine import load_configs  # noqa: E402
from backtest.simulasi_live import (  # noqa: E402
    BAR,
    DILEWATI,
    FEAT_DEFAULT,
    M1_DEFAULT,
    MIN_RIWAYAT,
    DataSimulasi,
    FiturBarBerjalan,
    Opsi,
    jalankan_varian,
    ringkas,
    rp,
)
from src.variants import list_variants  # noqa: E402


# Di bawah ini korelasi latih-vs-uji tidak dilaporkan: dua titik selalu
# menghasilkan +-1,00, tiga titik hampir selalu ekstrem.
MIN_LIPATAN_KORELASI = 5


@dataclass
class Lipatan:
    no: int
    latih_dari: pd.Timestamp
    latih_sampai: pd.Timestamp
    uji_dari: pd.Timestamp
    uji_sampai: pd.Timestamp


def muat_penuh(feat_path: str, m1_path: str) -> tuple[pd.DataFrame, dict]:
    feat = pd.read_parquet(feat_path)
    feat["time_utc"] = feat["time_utc"].astype("datetime64[ns]")
    feat = feat.sort_values("time_utc").reset_index(drop=True)

    m1 = pd.read_parquet(m1_path, columns=["time_utc", "open", "high", "low", "close", "tick_volume"])
    m1["time_utc"] = m1["time_utc"].astype("datetime64[ns]")
    m1 = m1.sort_values("time_utc")
    m1["bar"] = m1["time_utc"].dt.floor("5min")
    per_bar = {t: g.drop(columns="bar").reset_index(drop=True) for t, g in m1.groupby("bar")}
    return feat, per_bar


def potong(feat: pd.DataFrame, fitur: FiturBarBerjalan, per_bar: dict,
           dari: pd.Timestamp, sampai: pd.Timestamp) -> Optional[DataSimulasi]:
    """Satu jendela simulasi. None bila datanya tidak memadai."""
    idx = feat.index[(feat["time_utc"] >= dari) & (feat["time_utc"] < sampai)]
    if len(idx) == 0:
        return None
    k0, k1 = int(idx.min()), int(idx.max())
    if k0 < MIN_RIWAYAT:
        return None
    sub = {t: g for t, g in per_bar.items() if dari <= t < sampai + BAR}
    return DataSimulasi(feat, fitur, sub, k0, k1, dari, sampai)


def buat_lipatan(mulai: pd.Timestamp, akhir: pd.Timestamp, latih: float,
                 uji: float, langkah: float) -> list[Lipatan]:
    """Daftar jendela latih->uji yang tidak pernah tumpang tindih.

    Periode uji SELALU tepat setelah periode latihnya dan tidak pernah
    memuat satu bar pun dari periode latih - itu satu-satunya hal yang
    membuat hasil uji layak disebut out-of-sample.
    """
    out: list[Lipatan] = []
    t = mulai
    while t + pd.Timedelta(days=latih + uji) <= akhir:
        latih_sampai = t + pd.Timedelta(days=latih)
        out.append(Lipatan(len(out) + 1, t, latih_sampai,
                           latih_sampai, latih_sampai + pd.Timedelta(days=uji)))
        t += pd.Timedelta(days=langkah)
    return out


def skor(res: dict, kriteria: str) -> float:
    """Nilai satu kandidat di periode latih. Makin besar makin dipilih."""
    st = ringkas(res["trades"])
    nilai = {"totR": st["R"], "ER": st["ER"], "t": st["t"]}[kriteria]
    return float("-inf") if nilai != nilai else float(nilai)  # NaN -> paling buruk


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--feat", default=str(FEAT_DEFAULT))
    ap.add_argument("--m1", default=str(M1_DEFAULT))
    ap.add_argument("--dari", required=True, help="awal periode keseluruhan, UTC")
    ap.add_argument("--sampai", required=True, help="akhir periode keseluruhan, UTC (eksklusif)")
    ap.add_argument("--latih", type=float, default=30, help="panjang periode latih (hari)")
    ap.add_argument("--uji", type=float, default=14, help="panjang periode uji (hari)")
    ap.add_argument("--langkah", type=float, default=None, help="geser tiap lipatan (default = --uji)")
    ap.add_argument("--kandidat", nargs="+", default=None, help="varian yang diperebutkan")
    ap.add_argument("--pilih", choices=("totR", "ER", "t"), default="totR",
                    help="kriteria pemilihan di periode latih")
    ap.add_argument("--min-trade", type=int, default=10,
                    help="kandidat dengan trade lebih sedikit dari ini diabaikan")
    ap.add_argument("--equity", type=float, default=Opsi.equity)
    ap.add_argument("--tanpa-halt-dd", action="store_true")
    ap.add_argument("--csv", help="simpan trade periode UJI (pemilih) ke file ini")
    args = ap.parse_args()

    settings, risk = load_configs()
    semua = list_variants()
    kandidat = args.kandidat or [n for n in semua if n not in DILEWATI]
    tidak_dikenal = [n for n in kandidat if n not in semua]
    if tidak_dikenal:
        print(f"Varian tidak dikenal: {tidak_dikenal}. Tersedia: {', '.join(semua)}")
        return 1

    feat, per_bar = muat_penuh(args.feat, args.m1)
    fitur = FiturBarBerjalan(feat)
    mulai, akhir = pd.Timestamp(args.dari), pd.Timestamp(args.sampai)
    langkah = pd.Timedelta(days=args.langkah if args.langkah else args.uji)

    lipatan = buat_lipatan(mulai, akhir, args.latih, args.uji, langkah.days)
    if not lipatan:
        print("Periode terlalu pendek untuk satu lipatan pun.")
        return 1

    print(f"WALK-FORWARD  latih {args.latih:g} hari -> uji {args.uji:g} hari, "
          f"geser {langkah.days} hari | {len(lipatan)} lipatan | "
          f"pilih menurut {args.pilih} (min {args.min_trade} trade) | "
          f"kandidat: {', '.join(kandidat)}")
    print(f"Periode {mulai:%d %b %Y} - {akhir:%d %b %Y} UTC | equity awal {rp(args.equity)} | "
          + ("halt DD dimatikan" if args.tanpa_halt_dd else "semua rem aktif"))

    opsi_dasar = Opsi(equity=args.equity, tanpa_halt_dd=args.tanpa_halt_dd)
    ekuitas_pemilih = args.equity
    ekuitas_tetap = {n: args.equity for n in kandidat}
    trades_pemilih: list = []
    trades_tetap: dict[str, list] = {n: [] for n in kandidat}
    baris_lipatan = []

    print("\n" + "=" * 104)
    print(f"{'#':>2} {'periode latih':<24} {'pilihan':<20} {'latih':>9} | "
          f"{'periode uji':<24} {'uji':>9} {'entry':>6}")
    print("-" * 104)

    for lip in lipatan:
        d_latih = potong(feat, fitur, per_bar, lip.latih_dari, lip.latih_sampai)
        d_uji = potong(feat, fitur, per_bar, lip.uji_dari, lip.uji_sampai)
        if d_latih is None or d_uji is None:
            print(f"{lip.no:>2} data tidak memadai - lipatan dilewati")
            continue

        # -- LATIH: semua kandidat, equity sama rata (hanya untuk memilih) --
        nilai: dict[str, float] = {}
        for nama in kandidat:
            res = jalankan_varian(nama, d_latih, settings, risk,
                                  replace(opsi_dasar, equity=args.equity))
            st = ringkas(res["trades"])
            nilai[nama] = skor(res, args.pilih) if st["n"] >= args.min_trade else float("-inf")

        pilihan = max(nilai, key=lambda n: nilai[n])
        if nilai[pilihan] == float("-inf"):
            print(f"{lip.no:>2} {lip.latih_dari:%d %b}-{lip.latih_sampai:%d %b}"
                  f"          (tidak ada kandidat memenuhi syarat - tidak trading)")
            continue

        # -- UJI: hanya pilihan, equity dibawa maju --------------------------
        res_uji = jalankan_varian(pilihan, d_uji, settings, risk,
                                  replace(opsi_dasar, equity=ekuitas_pemilih))
        st_uji = ringkas(res_uji["trades"])
        ekuitas_pemilih = res_uji["saldo"]
        trades_pemilih.extend(res_uji["trades"])

        # -- Pembanding: tiap varian TETAP di periode uji yang sama ----------
        for nama in kandidat:
            r = jalankan_varian(nama, d_uji, settings, risk,
                                replace(opsi_dasar, equity=ekuitas_tetap[nama]))
            ekuitas_tetap[nama] = r["saldo"]
            trades_tetap[nama].extend(r["trades"])

        print(f"{lip.no:>2} {lip.latih_dari:%d %b}-{lip.latih_sampai:%d %b}"
              f"{'':<14} {pilihan:<20} {nilai[pilihan]:>+9.2f} | "
              f"{lip.uji_dari:%d %b}-{lip.uji_sampai:%d %b}{'':<14} "
              f"{st_uji['R']:>+9.2f} {st_uji['n']:>6}")
        baris_lipatan.append({"lipatan": lip.no, "pilihan": pilihan,
                              "latih": nilai[pilihan], "uji_R": st_uji["R"],
                              "uji_entry": st_uji["n"]})

    if not baris_lipatan:
        print("\nTidak ada lipatan yang bisa dijalankan.")
        return 1

    st = ringkas(trades_pemilih)
    print("\n" + "=" * 104)
    print("HASIL DI PERIODE UJI SAJA (out-of-sample)")
    print(f"{'strategi':<28} {'entry':>6} {'TP':>4} {'SL':>4} {'WR':>5} {'E[R]':>8} {'t':>6} "
          f"{'totR':>9} {'equity akhir':>16}")
    print(f"{'pemilih walk-forward':<28} {st['n']:>6} {st['TP']:>4} {st['SL']:>4} "
          f"{st['wr'] if st['n'] else 0:>5.0%} {st['ER']:>+8.3f} {st['t']:>+6.2f} "
          f"{st['R']:>+9.2f} {rp(ekuitas_pemilih):>16}")
    for nama in kandidat:
        s = ringkas(trades_tetap[nama])
        print(f"{'tetap ' + nama:<28} {s['n']:>6} {s['TP']:>4} {s['SL']:>4} "
              f"{s['wr'] if s['n'] else 0:>5.0%} {s['ER']:>+8.3f} {s['t']:>+6.2f} "
              f"{s['R']:>+9.2f} {rp(ekuitas_tetap[nama]):>16}")

    dipilih = pd.Series([b["pilihan"] for b in baris_lipatan]).value_counts()
    print("\nVarian terpilih: " + ", ".join(f"{n} {c}x" for n, c in dipilih.items()))
    benar = sum(1 for b in baris_lipatan if b["uji_R"] > 0)
    print(f"Lipatan dengan hasil uji positif: {benar}/{len(baris_lipatan)}")
    # Korelasi dari segelintir titik TIDAK bermakna - dua titik selalu
    # memberi +-1,00, dan angka itu terlihat meyakinkan padahal kosong.
    # Lebih baik tidak dicetak daripada dibaca sebagai bukti.
    if len(baris_lipatan) >= MIN_LIPATAN_KORELASI:
        korelasi = pd.DataFrame(baris_lipatan)[["latih", "uji_R"]].corr().iloc[0, 1]
        print(f"Korelasi nilai latih vs hasil uji: {korelasi:+.2f} "
              "(mendekati nol = performa terakhir tidak meramalkan periode berikutnya)")
    else:
        print(f"Korelasi latih vs uji tidak dicetak: baru {len(baris_lipatan)} lipatan "
              f"(minimal {MIN_LIPATAN_KORELASI}); dari sesedikit itu angkanya tidak bermakna.")

    if args.csv:
        pd.DataFrame([{k: v for k, v in p.__dict__.items() if k != "info"}
                      for p in trades_pemilih]).to_csv(args.csv, index=False)
        print(f"\nTrade periode uji disimpan: {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
