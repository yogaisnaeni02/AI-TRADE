"""
Notifikasi Telegram — supaya tidak perlu menunggu di depan layar.

Masalah yang dijawab: sinyal entry jarang muncul (rata-rata 1 per ~7 jam),
meski sekali muncul hasilnya biasanya cepat diketahui (median 20 menit).
Menunggu di depan terminal untuk kejadian yang jarang itu tidak praktis.

Solusi: bot mengirim pesan ke HP Anda saat kejadian penting terjadi, jadi
Anda bisa kerjakan hal lain dan dapat kabar begitu ada aktivitas — bukan
mempercepat sinyal (itu sudah terbukti merusak strategi), tapi menghapus
kebutuhan untuk terus memelototi layar.

Setup (sekali saja):
  1. Chat ke @BotFather di Telegram, buat bot baru, catat TOKEN
  2. Chat ke bot yang baru dibuat, kirim pesan apa saja
  3. Buka https://api.telegram.org/bot<TOKEN>/getUpdates di browser,
     cari "chat":{"id": ANGKA_INI} - itu CHAT_ID Anda
  4. Isi TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID di config/settings.yaml
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import os

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "settings.yaml"


def _load_telegram_config() -> tuple[Optional[str], Optional[str]]:
    """
    Ambil kredensial Telegram. Variabel lingkungan didahulukan.

    config/settings.yaml IKUT GIT, jadi menaruh token di sana berarti
    token itu ter-push ke repo begitu diisi. Variabel lingkungan tidak
    ikut ke mana-mana:

        setx AI_TRADE_TG_TOKEN   "123456:ABC..."     (Windows, sekali saja)
        setx AI_TRADE_TG_CHAT_ID "987654321"

    Lalu buka jendela CMD baru - setx hanya berlaku untuk proses baru.

    Nilai di settings.yaml tetap dibaca sebagai cadangan agar setup lama
    tidak mendadak berhenti bekerja.
    """
    token = os.environ.get("AI_TRADE_TG_TOKEN")
    chat_id = os.environ.get("AI_TRADE_TG_CHAT_ID")
    if token and chat_id:
        return str(token), str(chat_id)

    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        tg = cfg.get("telegram", {})
        token, chat_id = token or tg.get("bot_token"), chat_id or tg.get("chat_id")
        if not token or not chat_id:
            return None, None
        return str(token), str(chat_id)
    except (OSError, yaml.YAMLError):
        return None, None


def send(message: str) -> bool:
    """
    Kirim pesan Telegram. Gagal secara diam-diam (log, tidak crash bot) —
    notifikasi adalah kenyamanan, bukan komponen kritis. Kegagalan kirim
    pesan tidak boleh menghentikan trading.
    """
    token, chat_id = _load_telegram_config()
    if not token:
        return False

    try:
        import urllib.request
        import urllib.parse

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }).encode()

        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


def notify_signal(direction: str, setup: str, tier: str, lot: float, sl: float, tp: float) -> None:
    emoji = "🟢" if direction == "buy" else "🔴"
    send(
        f"{emoji} <b>SINYAL {direction.upper()}</b>\n"
        f"Setup: {setup} (tier: {tier})\n"
        f"Lot: {lot} | SL: {sl:.2f} | TP: {tp:.2f}"
    )


def notify_order_result(success: bool, ticket: Optional[int], price: Optional[float], reason: str) -> None:
    if success:
        send(f"✅ <b>ORDER TERKIRIM</b>\nTicket: {ticket} @ {price:.2f}")
    else:
        send(f"⚠️ <b>ORDER GAGAL</b>\n{reason}")


def notify_position_closed(pnl_idr: float, outcome: str) -> None:
    emoji = "💰" if pnl_idr > 0 else "📉"
    send(
        f"{emoji} <b>POSISI TERTUTUP</b> ({outcome})\n"
        f"P/L: Rp {pnl_idr:,.0f}"
    )


def notify_halt(reason: str) -> None:
    send(f"🛑 <b>SISTEM BERHENTI</b>\n{reason}")


def notify_daily_summary(trades: int, pnl_idr: float, equity: float) -> None:
    send(
        f"📊 <b>Ringkasan Hari Ini</b>\n"
        f"Trade: {trades} | P/L: Rp {pnl_idr:,.0f}\n"
        f"Equity: Rp {equity:,.0f}"
    )


if __name__ == "__main__":
    ok = send("🔔 Tes notifikasi dari sistem trading XAUUSD. Jika Anda menerima ini, setup berhasil.")
    print("Terkirim." if ok else "Gagal — cek TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID di config/settings.yaml")
