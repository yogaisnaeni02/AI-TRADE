"""
Bandingkan hasil forward test live dengan ekspektasi backtest.

KENAPA SKRIP INI ADA
--------------------
Forward test hanya berguna kalau hasilnya bisa dibandingkan dengan angka
yang jadi dasar keputusan. Membandingkan winrate saja TIDAK cukup: pada
RR 1:2,78 breakeven ada di 28,17%, jadi winrate 30% bisa untung dan 27%
bisa rugi — yang menentukan expectancy.

Skrip ini membaca logs/trades.csv dan menjawab satu pertanyaan:

    Apakah hasil live konsisten dengan backtest, atau sudah menyimpang
    cukup jauh sehingga forward test harus dihentikan?

AMBANG KEPUTUSAN
----------------
Ditetapkan di docs/29-RENCANA-LANJUTAN.md bagian 9, SEBELUM data masuk,
supaya tidak dirasionalisasi setelah melihat hasilnya:

    n >= 50   dan winrate jauh di bawah 28,17%  -> hentikan lebih awal
    n >= 100  dan E[R] negatif                  -> hentikan, balik riset
    n >= 200  dan E[R] positif, CI tak memuat 0 -> boleh bicara akun real

PEMAKAIAN
---------
    python scripts/compare_live_vs_backtest.py
"""

from __future__ import annotations

import csv
import math
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRADES_CSV = ROOT / "logs" / "trades.csv"

# Acuan dari backtest M5 (docs/28-HASIL-KALIBRASI-ULANG.md bagian 1).
# Periode PENUH tanpa halt DD (docs/28 revisi 2). Angka lama 0.1749/31.77/
# 1.31/2.90 berasal dari backtest yang terpotong halt 20% pada Mar 2026.
# Pembanding SISI BUY, diukur dengan sell DIMATIKAN dan min_score=5.
#
# Alasannya: di live max_open_positions=2, sehingga buy tidak tergeser
# oleh sell. Memakai angka campuran (+0,1214) akan salah - itu populasi
# buy yang sudah terpotong sell di backtest yang hardcode 1 posisi.
# Lihat catatan di backtest/engine.py::run.
BT_EXPECTANCY = 0.1092
BT_WINRATE = 29.7
BT_PF = 1.20
BT_TRADES_PER_DAY = 1.64   # per hari KALENDER (845 trade / 515 hari)
BREAKEVEN_WR = 28.17   # RR 1:2,78 setelah spread 260 points

# Komentar yang menandai trade uji manual, bukan hasil strategi.
EXCLUDE_COMMENTS = ("test_exec", "demo_siklus")


def load_trades() -> list[dict]:
    if not TRADES_CSV.exists():
        return []
    rows = []
    with open(TRADES_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if not row.get("net_idr"):
                continue
            if any(c in (row.get("comment") or "") for c in EXCLUDE_COMMENTS):
                continue
            try:
                row["_net"] = float(row["net_idr"])
                row["_r"] = float(row["r_multiple"]) if row.get("r_multiple") else None
                row["_entry"] = datetime.fromisoformat(row["entry_time"])
                row["_dir"] = (row.get("direction") or "?").lower()
                # comment berformat "<setup>_<skor>_<cfghash>"; bagian
                # terakhir adalah sidik jari konfigurasi sinyal saat order
                # dibuka. Trade dari sidik jari berbeda TIDAK boleh
                # digabungkan - lihat src/config_fingerprint.py.
                parts = (row.get("comment") or "").rsplit("_", 1)
                row["_cfg"] = parts[1] if len(parts) == 2 and len(parts[1]) == 4 else "lama"
            except (ValueError, KeyError):
                continue
            rows.append(row)
    rows.sort(key=lambda r: r["_entry"])
    return rows


def stats(rows: list[dict]) -> dict:
    n = len(rows)
    wins = [r for r in rows if r["_net"] > 0]
    gross_win = sum(r["_net"] for r in wins)
    gross_loss = abs(sum(r["_net"] for r in rows if r["_net"] <= 0))

    rs = [r["_r"] for r in rows if r["_r"] is not None]
    out = {
        "n": n,
        "n_with_r": len(rs),
        "winrate": len(wins) / n * 100 if n else 0.0,
        "total_pnl": sum(r["_net"] for r in rows),
        "pf": gross_win / gross_loss if gross_loss else float("inf"),
    }

    if len(rs) >= 2:
        mean = sum(rs) / len(rs)
        var = sum((x - mean) ** 2 for x in rs) / (len(rs) - 1)
        se = math.sqrt(var) / math.sqrt(len(rs))
        out.update(
            expectancy=mean, se=se,
            ci_lo=mean - 1.96 * se, ci_hi=mean + 1.96 * se,
            t=mean / se if se > 0 else float("nan"),
        )
    return out


def verdict(s: dict) -> list[str]:
    """Terapkan ambang yang sudah ditetapkan di docs/29 bagian 9."""
    n = s["n"]
    out = []

    if n < 20:
        out.append(f"BELUM CUKUP DATA ({n} trade). Ambang pertama di n=50.")
        return out

    if n >= 50 and s["winrate"] < BREAKEVEN_WR - 5:
        out.append(
            f"HENTIKAN: winrate {s['winrate']:.2f}% jauh di bawah breakeven "
            f"{BREAKEVEN_WR}% pada n={n}."
        )

    e = s.get("expectancy")
    if e is None:
        out.append(
            "r_multiple belum terisi - E[R] tidak bisa dihitung. "
            "Pastikan bot memakai versi journal.py terbaru."
        )
        return out

    if n >= 100 and e < 0:
        out.append(f"HENTIKAN: E[R] {e:+.4f} negatif pada n={n}. Kembali ke riset.")

    if n >= 200:
        if e > 0 and s["ci_lo"] > 0:
            out.append(
                f"LOLOS: E[R] {e:+.4f}, CI 95% [{s['ci_lo']:+.4f} ; {s['ci_hi']:+.4f}] "
                "tidak memuat nol. Boleh bicara akun real, mulai risiko 0,5%."
            )
        elif e > 0:
            out.append(
                f"BELUM MEYAKINKAN: E[R] {e:+.4f} positif tapi CI "
                f"[{s['ci_lo']:+.4f} ; {s['ci_hi']:+.4f}] masih memuat nol. "
                "Lanjutkan demo."
            )

    if not out:
        out.append(f"LANJUTKAN: belum ada ambang yang terlampaui pada n={n}.")
    return out


def by_group(rows: list) -> dict:
    """Kelompokkan per (sidik jari config, arah)."""
    out = {}
    for r in rows:
        out.setdefault((r["_cfg"], r["_dir"]), []).append(r)
    return out


def main() -> int:
    rows = load_trades()
    if not rows:
        print(f"Belum ada trade tercatat di {TRADES_CSV}.")
        print("Bot akan mengisinya otomatis setelah posisi pertama tertutup.")
        return 0

    s = stats(rows)
    span_days = max((rows[-1]["_entry"] - rows[0]["_entry"]).days, 1)

    print("=" * 70)
    print("FORWARD TEST vs BACKTEST")
    print("=" * 70)
    print(f"Periode : {rows[0]['_entry']:%Y-%m-%d} s/d {rows[-1]['_entry']:%Y-%m-%d}"
          f"  ({span_days} hari)")
    print(f"Trade   : {s['n']}   (dengan r_multiple: {s['n_with_r']})")
    print()

    hdr = f"{'metrik':22s} {'live':>12s} {'backtest':>12s} {'selisih':>12s}"
    print(hdr)
    print("-" * len(hdr))

    def row(label, live, bt, fmt="{:>12.4f}"):
        d = live - bt
        print(f"{label:22s} {fmt.format(live)} {fmt.format(bt)} {fmt.format(d)}")

    if "expectancy" in s:
        row("E[R]", s["expectancy"], BT_EXPECTANCY)
    else:
        print(f"{'E[R]':22s} {'(r_multiple kosong)':>12s}")
    row("winrate %", s["winrate"], BT_WINRATE, "{:>12.2f}")
    row("profit factor", s["pf"], BT_PF, "{:>12.2f}")
    row("trade/hari", s["n"] / span_days, BT_TRADES_PER_DAY, "{:>12.2f}")
    print("-" * len(hdr))
    print(f"{'P/L total':22s} {'Rp ' + format(s['total_pnl'], ',.0f'):>12s}")

    if "expectancy" in s:
        print(f"\nCI 95% E[R] live : [{s['ci_lo']:+.4f} ; {s['ci_hi']:+.4f}]   t = {s['t']:.2f}")
        if s["ci_lo"] <= BT_EXPECTANCY <= s["ci_hi"]:
            print("Backtest buy (+0,1092R) BERADA di dalam CI live - konsisten.")
        else:
            print("Backtest buy (+0,1092R) DI LUAR CI live - hasil live menyimpang.")

    print(f"\nBreakeven winrate RR 1:2,78 = {BREAKEVEN_WR}%")
    print("\nVONIS")
    for line in verdict(s):
        print(f"  {line}")

    # Pecah per konfigurasi dan arah.
    #
    # Sejak eksperimen dua arah di demo (10 Sep 2026), trades.csv bisa
    # memuat buy DAN sell, dan bisa memuat lebih dari satu setelan bila
    # config sempat berubah. Merata-ratakan semuanya menghasilkan angka
    # yang tidak berarti apa-apa.
    groups = by_group(rows)
    if len(groups) > 1:
        print()
        print("=" * 70)
        print("PECAHAN PER KONFIGURASI DAN ARAH")
        print("=" * 70)
        print("Trade dari sidik jari config berbeda TIDAK dibandingkan satu")
        print("sama lain - jalur sinyalnya memang berbeda.")
        print()
        hdr2 = f"{'cfg':>6s} {'arah':>5s} {'n':>5s} {'E[R]':>9s} {'t':>6s} {'WR%':>6s} {'P/L':>14s}"
        print(hdr2)
        print("-" * len(hdr2))
        for (cfg, direction), g in sorted(groups.items()):
            st = stats(g)
            e = st.get("expectancy")
            es = f"{e:>+9.4f}" if e is not None else "        -"
            ts = f"{st['t']:>6.2f}" if st.get("t") is not None else "     -"
            print(f"{cfg:>6s} {direction:>5s} {st['n']:>5d} {es} {ts} "
                  f"{st['winrate']:>6.2f} {'Rp ' + format(st['total_pnl'], ',.0f'):>14s}")
        print("-" * len(hdr2))
        print()
        print("CATATAN: hanya kelompok BUY pada sidik jari terbaru yang")
        print("dihitung terhadap ambang docs/29 bagian 9. Sisi SELL adalah")
        print("eksperimen demo dengan ekspektasi awal NEGATIF dan punya")
        print("gerbangnya sendiri sebelum boleh ikut ke akun real.")
        print()
    print("\nAmbang lengkap: docs/29-RENCANA-LANJUTAN.md bagian 9")
    return 0


if __name__ == "__main__":
    sys.exit(main())
