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
import socket

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "settings.yaml"

# Label PC ditempel di depan tiap pesan. Tanpa ini, notifikasi dari beberapa
# PC yang menjalankan bot untuk akun yang sama tidak bisa dibedakan di
# Telegram - persis kebutuhan yang muncul saat menguji di beberapa PC
# sekaligus (lihat insiden posisi dobel 14 Sep 2026, docs/51).
#
# Default hostname Windows (mis. DESKTOP-ABC123) sering tidak informatif.
# Override lewat env var AI_TRADE_PC_NAME, atau lewat run_bot.py --nama-pc
# (lihat set_label() di bawah) - dipilih pas menjalankan bot, tidak perlu
# rename PC atau restart Windows.
_LABEL = os.environ.get("AI_TRADE_PC_NAME") or socket.gethostname()

# Varian yang sedang dijalankan, ikut ditempel di tiap pesan. Dengan
# beberapa PC menjalankan varian berbeda di akun masing-masing, "TP +Rp
# 120.000" tanpa keterangan varian tidak bisa dihubungkan ke setelan mana
# pun - dan justru perbandingan antar varian itu inti forward test ini.
_VARIAN: Optional[str] = None


def set_label(name: str) -> None:
    """Timpa label yang ditempel di notifikasi (dipanggil dari run_bot.py)."""
    global _LABEL
    if name:
        _LABEL = name


def set_varian(name: Optional[str]) -> None:
    """Nama varian untuk ditempel di tiap pesan (dipanggil dari bot.py)."""
    global _VARIAN
    _VARIAN = name or None


def rupiah(nilai: float, tanda: bool = False) -> str:
    """'Rp 120.000' atau '+Rp 120.000' - dipakai seragam di semua pesan."""
    awalan = "+" if tanda and nilai > 0 else ("-" if nilai < 0 else "")
    return f"{awalan}Rp {abs(nilai):,.0f}"


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

    import ssl
    import urllib.error
    import urllib.parse
    import urllib.request

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    kepala = f"🖥 <b>{_LABEL}</b>" + (f" · {_VARIAN}" if _VARIAN else "")
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": f"{kepala}\n{message}",
        "parse_mode": "HTML",
    }).encode()

    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except urllib.error.URLError as e:
        # Sertifikat tidak bisa diverifikasi Python (proxy kantor yang
        # menandatangani ulang HTTPS, atau root CA belum ada di Windows).
        # curl.exe memakai penyimpanan sertifikat Windows, yang justru
        # sudah memuat sertifikat proxy itu. Tanpa cadangan ini, bot di PC
        # seperti itu berjalan TANPA notifikasi sama sekali, dan diamnya
        # tidak bisa dibedakan dari bot yang mati.
        if isinstance(getattr(e, "reason", None), ssl.SSLCertVerificationError):
            return _kirim_lewat_windows(url, data)
        return False
    except Exception:  # noqa: BLE001
        return False


def _kirim_lewat_windows(url: str, data: bytes) -> bool:
    import os
    import subprocess

    curl = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "curl.exe"
    if not curl.exists():
        return False
    try:
        hasil = subprocess.run(
            [str(curl), "-fsS", "--max-time", "15", "-X", "POST", "--data-binary", "@-", url],
            input=data, capture_output=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return hasil.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def notify_entry(direction: str, setup: str, tier: str, skor, lot: float,
                 harga: float, sl: float, tp: float, risiko_pct: float,
                 risiko_idr: float, ticket: Optional[int]) -> None:
    """Satu pesan saat posisi BENAR-BENAR terbuka.

    Dulu dikirim dua pesan: "SINYAL" saat sinyal lolos rem, lalu "ORDER
    TERKIRIM". Dua pesan untuk satu kejadian membuat notifikasi sulit
    dibaca cepat di HP, dan yang pertama belum tentu jadi posisi.
    """
    emoji = "🟢" if direction == "buy" else "🔴"
    rr = abs(tp - harga) / abs(harga - sl) if harga and abs(harga - sl) > 1e-9 else 0.0
    baris = [
        f"{emoji} <b>{direction.upper()} dibuka</b> · {setup}",
        f"{lot} lot @ {harga:.2f}",
        f"SL {sl:.2f} · TP {tp:.2f}" + (f" (RR 1:{rr:.1f})" if rr else ""),
        f"skor {skor} ({tier}) · risiko {risiko_pct:.2f}%"
        + (f" ({rupiah(risiko_idr)})" if risiko_idr else ""),
    ]
    if ticket:
        baris.append(f"tiket {ticket}")
    send("\n".join(baris))


def notify_order_gagal(alasan: str) -> None:
    send(f"⚠️ <b>ORDER GAGAL</b>\n{alasan}")


def notify_exit(sebab: str, direction: str, lot: float, harga_masuk: float,
                harga_keluar: float, net_idr: float, r_multiple, durasi_menit: float,
                trade_hari_ini: int, pnl_hari_ini: float, equity: float) -> None:
    """Pesan saat posisi tertutup: kena TP, SL, trailing, atau ditutup bot.

    Ini yang sebelumnya TIDAK PERNAH terkirim: fungsi lamanya ada tapi tak
    pernah dipanggil, sehingga dari Telegram hanya terlihat posisi dibuka,
    tidak pernah terlihat hasilnya.
    """
    emoji = "💰" if net_idr > 0 else ("📉" if net_idr < 0 else "➖")
    hasil = rupiah(net_idr, tanda=True)
    try:
        hasil += f" ({float(r_multiple):+.2f}R)"
    except (TypeError, ValueError):
        pass
    durasi = (f"{durasi_menit / 60:.1f} jam" if durasi_menit >= 90
              else f"{durasi_menit:.0f} mnt")
    send(
        f"{emoji} <b>{sebab}</b>\n"
        f"{direction.upper()} {lot} lot · {harga_masuk:.2f} → {harga_keluar:.2f} · {durasi}\n"
        f"P/L {hasil}\n"
        f"Hari ini {trade_hari_ini} trade · {rupiah(pnl_hari_ini, tanda=True)}\n"
        f"Equity {rupiah(equity)}"
    )


def notify_heartbeat(waktu: str, equity: float, dd_pct: float, posisi: int,
                     floating: float, trade_hari_ini: int, batas_trade: int,
                     pnl_hari_ini: float, rem: str, sesi: str,
                     cfg_hash: str, halt: Optional[str] = None) -> None:
    """Kabar berkala: bot hidup, porto sekarang, dan hasil hari ini.

    Kesenyapan harus bisa dibaca sebagai masalah (kejadian 11 Sep 2026: PC
    macet, 11 trade terlewat tanpa ada yang tahu). Isinya sengaja memuat
    equity dan P/L harian, supaya satu pesan cukup untuk tahu keadaan
    tanpa membuka PC.
    """
    baris = [
        f"⏱ <b>Bot hidup</b> · {waktu}",
        f"Equity {rupiah(equity)} (DD {dd_pct:.1f}%)",
        f"Posisi {posisi}" + (f" · floating {rupiah(floating, tanda=True)}" if posisi else ""),
        f"Hari ini {trade_hari_ini}/{batas_trade} trade · {rupiah(pnl_hari_ini, tanda=True)}",
        f"Rem: {rem} · sesi {sesi}",
        f"cfg {cfg_hash}",
    ]
    if halt:
        baris.append(f"🛑 HALT: {halt}")
    send("\n".join(baris))


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
