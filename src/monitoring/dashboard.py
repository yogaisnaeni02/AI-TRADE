"""
Dashboard monitoring — Streamlit.

PENTING: dashboard TIDAK memanggil mt5.initialize() sendiri saat bot sedang
berjalan. Paket MetaTrader5 hanya mengizinkan satu koneksi per proses; dua
proses yang initialize bersamaan menyebabkan kegagalan yang sulit didiagnosis.

Karena itu dashboard membaca dari file log dan snapshot yang ditulis bot.
Koneksi MT5 langsung hanya dipakai bila bot sedang tidak berjalan.

Jalankan:  streamlit run src/monitoring/dashboard.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "logs"
SNAPSHOT = LOG_DIR / "snapshot.json"
STOP_FILE = ROOT / "STOP"
TRADES_DB = LOG_DIR / "trades.csv"

st.set_page_config(page_title="XAUUSD Trading Bot", page_icon="📊", layout="wide")


def read_snapshot() -> dict:
    if not SNAPSHOT.exists():
        return {}
    try:
        with open(SNAPSHOT, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def read_log(lines: int = 60) -> list[str]:
    logs = sorted(LOG_DIR.glob("bot_*.log"))
    if not logs:
        return []
    with open(logs[-1], encoding="utf-8", errors="replace") as f:
        return f.readlines()[-lines:]


def read_trades() -> pd.DataFrame:
    if not TRADES_DB.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(TRADES_DB)
    except (pd.errors.EmptyDataError, OSError):
        return pd.DataFrame()


# -- header ---------------------------------------------------------------

st.title("XAUUSD Trading Bot")

snap = read_snapshot()
age = None
if snap.get("timestamp"):
    age = (datetime.now() - datetime.fromisoformat(snap["timestamp"])).total_seconds()

c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    if STOP_FILE.exists():
        st.error("KILL SWITCH AKTIF")
    elif age is None:
        st.warning("Bot belum jalan")
    elif age < 120:
        st.success("Bot aktif")
    else:
        st.warning(f"Diam {age/60:.0f} mnt")

c2.metric("Mode", snap.get("mode", "-"))
c3.metric("Equity", f"Rp {snap.get('equity', 0):,.0f}")
c4.metric("Posisi terbuka", snap.get("open_positions", 0))

dd = snap.get("drawdown_pct", 0)
c5.metric("Drawdown", f"{dd:.1f}%", delta=None if dd < 15 else "de-risking aktif")

if snap.get("halted"):
    st.error(f"SISTEM DIHENTIKAN: {snap.get('halt_reason', 'tidak diketahui')}")

st.divider()

# -- kontrol --------------------------------------------------------------

left, right = st.columns([1, 3])

with left:
    st.subheader("Kontrol")
    if STOP_FILE.exists():
        st.warning("Bot tidak akan membuka posisi baru.")
        if st.button("Aktifkan kembali", use_container_width=True):
            STOP_FILE.unlink()
            st.rerun()
    else:
        if st.button("STOP — hentikan entry baru", type="primary", use_container_width=True):
            STOP_FILE.write_text(f"dihentikan manual {datetime.now():%Y-%m-%d %H:%M:%S}\n")
            st.rerun()
    st.caption(
        "STOP hanya memblokir entry BARU. Posisi terbuka tetap dikelola "
        "(break-even & trailing) sampai tertutup."
    )

    st.subheader("Sesi hari ini")
    st.text(f"Trade      : {snap.get('day_trades', 0)}")
    st.text(f"P/L         : Rp {snap.get('day_pnl', 0):,.0f}")
    st.text(f"Loss berurut: {snap.get('consecutive_losses', 0)}")
    st.text(f"Risiko aktif: {snap.get('effective_risk_pct', 0):.1f}%")

with right:
    st.subheader("Posisi terbuka")
    positions = snap.get("positions", [])
    if positions:
        st.dataframe(pd.DataFrame(positions), use_container_width=True, hide_index=True)
    else:
        st.info("Tidak ada posisi terbuka.")

    st.subheader("Log terbaru")
    log_lines = read_log(40)
    st.code("".join(log_lines) if log_lines else "Belum ada log.", language=None)

st.divider()

# -- riwayat trade --------------------------------------------------------

st.subheader("Riwayat trade")
trades = read_trades()

if trades.empty:
    st.info("Belum ada trade tercatat.")
else:
    m1, m2, m3, m4 = st.columns(4)
    wins = (trades["pnl_idr"] > 0).sum()
    m1.metric("Total trade", len(trades))
    m2.metric("Winrate", f"{wins / len(trades) * 100:.1f}%")
    m3.metric("P/L total", f"Rp {trades['pnl_idr'].sum():,.0f}")
    if "r_multiple" in trades.columns:
        m4.metric("Expectancy", f"{trades['r_multiple'].mean():+.3f} R")

    if "pnl_idr" in trades.columns:
        equity = snap.get("initial_equity", 3_700_000) + trades["pnl_idr"].cumsum()
        st.line_chart(equity, height=220)

    st.dataframe(trades.tail(30), use_container_width=True, hide_index=True)

st.caption("Halaman menyegarkan otomatis setiap 30 detik.")
st.markdown(
    '<meta http-equiv="refresh" content="30">', unsafe_allow_html=True
)
