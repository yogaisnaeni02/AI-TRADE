"""Kendali dari Telegram: lihat status worker dan ganti varian lewat nomor.

    python scripts/pc_worker/kendali_telegram.py   (lewat UTAMA-5-KENDALI-TELEGRAM.bat)

Berjalan di PC UTAMA, karena di sinilah penugasan dan folder rilis berada.
Perintah ditarik berkala dari Telegram (long polling) - tidak perlu IP
publik, port terbuka, atau server.

Perintah:
    /status                 kondisi semua worker
    /varian                 daftar PC dan varian, bernomor
    /varian <noPC> <noVar>  ganti varian PC itu, lalu terbitkan
    /berhenti <noPC>        PC itu berhenti menjalankan bot
    /bantuan                daftar perintah

SENGAJA TIDAK ADA perintah yang menutup posisi, melepas halt drawdown,
atau mematikan worker: satu salah ketik dari HP tidak boleh bisa
mengakhiri posisi yang sedang berjalan. Itu tetap lewat PC utama.

Hanya chat_id yang terdaftar di config/settings.yaml (atau env
AI_TRADE_TG_CHAT_ID) yang dilayani; pesan dari chat lain diabaikan.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

REPO = Path(__file__).resolve().parents[2]
SINI = Path(__file__).resolve().parent
sys.path.insert(0, str(SINI))
sys.path.insert(0, str(REPO))

import rilis  # noqa: E402
import status_worker as sw  # noqa: E402
from atur_penugasan import daftar_worker, folder_laporan, tulis_penugasan  # noqa: E402
from src.monitoring import notifier  # noqa: E402
from src.variants import list_variants  # noqa: E402

BERHENTI = "berhenti"
SIMPAN_OFFSET = REPO / "logs" / "tg_kendali.json"

# Perintah yang lebih tua dari ini diabaikan saat program baru dinyalakan.
# Tanpa batas ini, "/varian 1 5" yang dikirim tiga hari lalu akan dijalankan
# begitu PC utama menyala - padahal keadaannya sudah lain.
MAKS_UMUR_PERINTAH = timedelta(hours=6)

BANTUAN = (
    "Perintah:\n"
    "/status — kondisi semua worker\n"
    "/saldo — equity, balance, posisi terbuka, floating\n"
    "/hariini — trade dan P/L hari ini per PC\n"
    "/minggu — P/L minggu ini vs rem mingguan\n"
    "/total — P/L keseluruhan, winrate, per varian\n"
    "/trade — 5 trade terakhir\n"
    "/rem — status rem risiko tiap PC\n"
    "/varian — daftar PC dan varian (bernomor)\n"
    "/varian 1 5 — PC nomor 1 pakai varian nomor 5, lalu diterbitkan\n"
    "/berhenti 1 — PC nomor 1 berhenti menjalankan bot\n"
    "/bantuan — pesan ini\n\n"
    "Menutup posisi, melepas halt, dan menyalakan worker tetap lewat PC utama."
)


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _tanggal(iso: str):
    try:
        return datetime.fromisoformat(iso).date()
    except (TypeError, ValueError):
        return None


class Kendali:
    """Logika perintah, dipisah dari jaringan supaya bisa diuji."""

    def __init__(self, repo: Path = REPO, laporan: Optional[Path] = None,
                 terbitkan: Optional[Callable[[], tuple[bool, str]]] = None):
        self.repo = repo
        self._laporan = laporan
        self.terbitkan = terbitkan or self._terbitkan_asli

    # -- data --

    @property
    def laporan(self) -> Path:
        return self._laporan if self._laporan is not None else folder_laporan()

    def penugasan(self) -> dict[str, str]:
        try:
            return rilis.baca_penugasan(self.repo)
        except ValueError:
            return {}

    def daftar_pc(self) -> list[dict]:
        return daftar_worker(self.laporan, self.penugasan())

    def daftar_varian(self) -> list[str]:
        return list(list_variants())

    def _terbitkan_asli(self) -> tuple[bool, str]:
        hasil = subprocess.run(
            [sys.executable, str(SINI / "terbitkan.py"), "--ya"],
            cwd=self.repo, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        keluaran = (hasil.stdout or "") + (hasil.stderr or "")
        versi = next((b.strip() for b in keluaran.splitlines() if "Versi  :" in b), "")
        if hasil.returncode != 0:
            gagal = [b.strip() for b in keluaran.splitlines() if b.strip().startswith("!!")]
            return False, "\n".join(gagal[:3]) or "terbitkan gagal, lihat PC utama"
        return True, versi or "tidak ada perubahan untuk diterbitkan"

    # -- jawaban --

    def teks_varian(self) -> str:
        pcs, penugasan = self.daftar_pc(), self.penugasan()
        if not pcs:
            return ("Belum ada worker. Pasang lewat PASANG-WORKER.bat, "
                    "lalu terima di UTAMA-3-STATUS-WORKER.bat.")
        baris = ["PC:"]
        for i, w in enumerate(pcs, start=1):
            baris.append(f"{i}. {w['nama']} — sekarang: {penugasan.get(w['kunci'], 'belum diatur')}")
        baris.append("\nVarian:")
        for i, nama in enumerate(self.daftar_varian(), start=1):
            baris.append(f"{i}. {nama}")
        baris.append("\nBalas: /varian <no PC> <no varian>   mis. /varian 1 5")
        return "\n".join(baris)

    def teks_status(self) -> str:
        pcs = self.daftar_pc()
        terbaru = (rilis.baca_versi(Path(sw._json(self.repo / "pc_utama.json").get("rilis", "")))
                   or {}) if (self.repo / "pc_utama.json").exists() else {}
        baris = [f"Rilis terbaru: {terbaru.get('versi', '-')}"]
        if not pcs:
            baris.append("Belum ada worker.")
        for w in pcs:
            folder = self.laporan / w["kunci"]
            stt = sw._json(folder / "status_worker.json")
            snap = sw._json(folder / "snapshot.json")
            umur = sw._umur(stt.get("waktu_utc"))
            tanda = "⚠️" if (umur is None or umur > timedelta(minutes=sw.BASI_MENIT)) else "✅"
            baris.append(
                f"\n{tanda} {w['nama']} — {stt.get('keadaan', 'belum ada kabar')}"
                f" ({sw._teks_umur(umur)})"
            )
            tanda_versi = " (kode belum terbaru)" if sw.kode_tertinggal(stt, terbaru) else ""
            baris.append(f"varian {stt.get('varian') or '-'} · versi "
                         f"{stt.get('versi_bot') or '-'}{tanda_versi}")
            if snap:
                baris.append(
                    f"equity {notifier.rupiah(float(snap.get('equity') or 0))}"
                    f" · posisi {snap.get('open_positions', '?')}"
                    f" · hari ini {snap.get('day_trades', '?')} trade "
                    f"{notifier.rupiah(float(snap.get('day_pnl') or 0), tanda=True)}"
                    + (" · HALT" if snap.get("halted") else "")
                )
        return "\n".join(baris)

    # -- info dari journal & snapshot --

    def baris_journal(self) -> list[dict]:
        """Semua trade dari seluruh worker, duplikat tiket dibuang."""
        from src.monitoring.journal_gabung import baca_semua

        return baca_semua(sorted(self.laporan.glob("*/trades__*.csv")))

    def _snapshot(self, kunci: str) -> dict:
        return sw._json(self.laporan / kunci / "snapshot.json")

    def teks_saldo(self) -> str:
        pcs = self.daftar_pc()
        if not pcs:
            return "Belum ada worker."
        baris, total_eq, total_float = [], 0.0, 0.0
        for w in pcs:
            snap = self._snapshot(w["kunci"])
            if not snap:
                baris.append(f"{w['nama']}: belum ada kabar")
                continue
            eq, bal = _f(snap.get("equity")), _f(snap.get("balance"))
            floating = eq - bal
            total_eq += eq
            total_float += floating
            baris.append(
                f"{w['nama']}\n"
                f"  equity {notifier.rupiah(eq)} · balance {notifier.rupiah(bal)}\n"
                f"  posisi {snap.get('open_positions', 0)}"
                f" · floating {notifier.rupiah(floating, tanda=True)}"
                f" · DD {_f(snap.get('drawdown_pct')):.1f}%"
            )
        if len(pcs) > 1:
            baris.append(f"\nTotal equity {notifier.rupiah(total_eq)}"
                         f" · floating {notifier.rupiah(total_float, tanda=True)}")
        return "💰 <b>Saldo</b>\n" + "\n".join(baris)

    def _ringkas(self, rows: list[dict]) -> tuple[int, int, float]:
        menang = sum(1 for r in rows if _f(r.get("net_idr")) > 0)
        return len(rows), menang, sum(_f(r.get("net_idr")) for r in rows)

    def teks_hariini(self) -> str:
        hari = datetime.now().date()
        rows = [r for r in self.baris_journal() if _tanggal(r.get("exit_time", "")) == hari]
        baris = []
        for w in self.daftar_pc():
            punya = [r for r in rows if (r.get("pc") or "") == w["kunci"]]
            n, menang, pnl = self._ringkas(punya)
            snap = self._snapshot(w["kunci"])
            posisi = snap.get("open_positions", 0) if snap else 0
            baris.append(f"{w['nama']}: {n} trade ({menang} menang)"
                         f" · {notifier.rupiah(pnl, tanda=True)}"
                         + (f" · {posisi} posisi terbuka" if posisi else ""))
        n, menang, pnl = self._ringkas(rows)
        baris.append(f"\nSemua PC: {n} trade ({menang} menang) · {notifier.rupiah(pnl, tanda=True)}")
        return f"📅 <b>Hari ini ({hari:%d %b})</b>\n" + "\n".join(baris)

    def teks_minggu(self) -> str:
        senin = datetime.now().date() - timedelta(days=datetime.now().weekday())
        rows = [r for r in self.baris_journal()
                if (_tanggal(r.get("exit_time", "")) or senin - timedelta(days=1)) >= senin]
        baris = []
        for w in self.daftar_pc():
            punya = [r for r in rows if (r.get("pc") or "") == w["kunci"]]
            n, menang, pnl = self._ringkas(punya)
            snap = self._snapshot(w["kunci"])
            eq = _f(snap.get("equity")) if snap else 0.0
            pct = (pnl / eq * 100) if eq else 0.0
            batas = _f(self.batas().get("mingguan", 8.0))
            baris.append(f"{w['nama']}: {n} trade · {notifier.rupiah(pnl, tanda=True)}"
                         + (f" ({pct:+.1f}% dari equity, rem -{batas:.0f}%)" if eq else ""))
        n, menang, pnl = self._ringkas(rows)
        baris.append(f"\nSemua PC: {n} trade ({menang} menang) · {notifier.rupiah(pnl, tanda=True)}")
        return f"🗓 <b>Minggu ini (sejak {senin:%d %b})</b>\n" + "\n".join(baris)

    def teks_total(self) -> str:
        rows = self.baris_journal()
        if not rows:
            return "Belum ada trade tercatat dari worker."
        n, menang, pnl = self._ringkas(rows)
        untung = sum(_f(r.get("net_idr")) for r in rows if _f(r.get("net_idr")) > 0)
        rugi = -sum(_f(r.get("net_idr")) for r in rows if _f(r.get("net_idr")) < 0)
        pf = (untung / rugi) if rugi else float("inf")
        baris = [
            f"{n} trade · winrate {menang / n * 100:.0f}%",
            f"P/L {notifier.rupiah(pnl, tanda=True)} · profit factor {pf:.2f}",
            "\nPer varian:",
        ]
        per: dict[str, list[dict]] = {}
        for r in rows:
            per.setdefault(r.get("varian") or "?", []).append(r)
        for nama, g in sorted(per.items(), key=lambda kv: -self._ringkas(kv[1])[2]):
            gn, gm, gp = self._ringkas(g)
            baris.append(f"  {nama}: {gn} trade ({gm} menang) · {notifier.rupiah(gp, tanda=True)}")
        return "📊 <b>Total semua worker</b>\n" + "\n".join(baris)

    def teks_trade(self, jumlah: int = 5) -> str:
        rows = sorted(self.baris_journal(), key=lambda r: r.get("exit_time") or "")
        if not rows:
            return "Belum ada trade tercatat dari worker."
        baris = []
        for r in rows[-jumlah:][::-1]:
            waktu = (r.get("exit_time") or "")[5:16].replace("T", " ")
            baris.append(
                f"{waktu} · {r.get('pc', '?')} · {r.get('varian', '?')}\n"
                f"  {str(r.get('direction', '')).upper()} {r.get('lot', '')} lot"
                f" · {notifier.rupiah(_f(r.get('net_idr')), tanda=True)}"
                + (f" ({_f(r.get('r_multiple')):+.2f}R)" if r.get("r_multiple") else "")
            )
        return f"🧾 <b>{len(baris)} trade terakhir</b>\n" + "\n".join(baris)

    def batas(self) -> dict:
        """Batas rem dari config/risk_limits.yaml (dibaca ulang tiap perintah)."""
        import yaml

        try:
            with open(self.repo / "config" / "risk_limits.yaml", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            return {}
        return {
            "trade": cfg.get("daily", {}).get("max_trades", 12),
            "loss": cfg.get("daily", {}).get("max_consecutive_losses", 3),
            "harian": cfg.get("daily", {}).get("max_loss_percent", 4.0),
            "mingguan": cfg.get("weekly", {}).get("max_loss_percent", 8.0),
            "dd": cfg.get("global", {}).get("max_drawdown_percent", 20.0),
        }

    def teks_rem(self) -> str:
        b = self.batas()
        pcs = self.daftar_pc()
        if not pcs:
            return "Belum ada worker."
        baris = []
        for w in pcs:
            snap = self._snapshot(w["kunci"])
            if not snap:
                baris.append(f"{w['nama']}: belum ada kabar")
                continue
            eq = _f(snap.get("equity"))
            pnl = _f(snap.get("day_pnl"))
            pct = (pnl / eq * 100) if eq else 0.0
            baris.append(
                f"{w['nama']}\n"
                f"  trade {snap.get('day_trades', 0)}/{b.get('trade')}"
                f" · loss beruntun {snap.get('consecutive_losses', 0)}/{b.get('loss')}\n"
                f"  P/L hari ini {notifier.rupiah(pnl, tanda=True)} ({pct:+.1f}%,"
                f" rem -{_f(b.get('harian')):.0f}%)\n"
                f"  DD {_f(snap.get('drawdown_pct')):.1f}% (halt di {_f(b.get('dd')):.0f}%)"
                + (f"\n  🛑 HALT: {snap.get('halt_reason')}" if snap.get("halted") else "")
            )
        return "🚦 <b>Rem risiko</b>\n" + "\n".join(baris)

    def ganti(self, no_pc: int, nilai: str) -> str:
        pcs = self.daftar_pc()
        if not 1 <= no_pc <= len(pcs):
            return f"PC nomor {no_pc} tidak ada. Kirim /varian untuk melihat daftarnya."
        w = pcs[no_pc - 1]
        penugasan = self.penugasan()
        if penugasan.get(w["kunci"]) == nilai:
            return f"{w['nama']} memang sudah {nilai}."
        penugasan[w["kunci"]] = nilai
        tulis_penugasan(self.repo / rilis.PENUGASAN, penugasan)
        ok, pesan = self.terbitkan()
        if not ok:
            return f"{w['nama']} -> {nilai}, TAPI gagal diterbitkan:\n{pesan}"
        return (f"{w['nama']} -> {nilai}. Diterbitkan.\n{pesan}\n"
                "Bot di sana pindah begitu tidak ada posisi terbuka.")

    def perintah(self, teks: str) -> Optional[str]:
        """Balasan untuk satu pesan, atau None kalau bukan perintah."""
        bagian = (teks or "").strip().split()
        if not bagian or not bagian[0].startswith("/"):
            return None
        kata = bagian[0].split("@")[0].lower()   # /varian@NamaBot di grup
        arg = bagian[1:]

        if kata in ("/bantuan", "/help", "/start", "/mulai"):
            return BANTUAN
        if kata == "/status":
            return self.teks_status()
        if kata in ("/saldo", "/equity"):
            return self.teks_saldo()
        if kata in ("/hariini", "/hari"):
            return self.teks_hariini()
        if kata in ("/minggu", "/mingguan"):
            return self.teks_minggu()
        if kata == "/total":
            return self.teks_total()
        if kata in ("/trade", "/terakhir"):
            jumlah = int(arg[0]) if arg and arg[0].isdigit() else 5
            return self.teks_trade(max(1, min(jumlah, 20)))
        if kata == "/rem":
            return self.teks_rem()
        if kata == "/berhenti":
            if len(arg) != 1 or not arg[0].isdigit():
                return "Tulis: /berhenti <no PC>   mis. /berhenti 1"
            return self.ganti(int(arg[0]), BERHENTI)
        if kata == "/varian":
            if not arg:
                return self.teks_varian()
            varian = self.daftar_varian()
            if len(arg) != 2 or not all(a.isdigit() for a in arg):
                return "Tulis: /varian <no PC> <no varian>   mis. /varian 1 5"
            no_var = int(arg[1])
            if not 1 <= no_var <= len(varian):
                return f"Varian nomor {no_var} tidak ada (1-{len(varian)}). Kirim /varian."
            return self.ganti(int(arg[0]), varian[no_var - 1])
        return f"Perintah '{kata}' tidak dikenal.\n\n{BANTUAN}"


# -- jaringan -------------------------------------------------------------

def _api(token: str, metode: str, **params) -> dict:
    url = f"https://api.telegram.org/bot{token}/{metode}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=params.get("timeout", 10) + 15) as r:
        return json.loads(r.read())


def _baca_offset() -> int:
    try:
        return int(json.loads(SIMPAN_OFFSET.read_text(encoding="utf-8"))["offset"])
    except (OSError, ValueError, KeyError):
        return 0


def _simpan_offset(offset: int) -> None:
    try:
        SIMPAN_OFFSET.parent.mkdir(exist_ok=True)
        SIMPAN_OFFSET.write_text(json.dumps({"offset": offset}), encoding="utf-8")
    except OSError:
        pass


def jalan() -> int:
    token, chat_id = notifier._load_telegram_config()
    if not token or not chat_id:
        print("!! Token/chat_id Telegram belum diisi (config/settings.yaml atau env).")
        return 1

    notifier.set_label("AI-TRADE utama")
    notifier.set_varian(None)
    kendali = Kendali()
    offset = _baca_offset()
    print("=" * 58)
    print("  KENDALI TELEGRAM AKTIF")
    print(f"  Melayani chat {chat_id} saja. Ctrl+C untuk berhenti.")
    print("=" * 58)
    notifier.send("🎛 <b>Kendali Telegram aktif</b>\n\n" + BANTUAN)

    while True:
        try:
            data = _api(token, "getUpdates", offset=offset, timeout=30)
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"[{datetime.now():%H:%M:%S}] koneksi Telegram: {e}; coba lagi 10 detik")
            time.sleep(10)
            continue

        for upd in data.get("result", []):
            offset = max(offset, upd["update_id"] + 1)
            _simpan_offset(offset)
            pesan = upd.get("message") or upd.get("edited_message") or {}
            teks = pesan.get("text", "")
            asal = str(pesan.get("chat", {}).get("id", ""))
            if asal != str(chat_id):
                print(f"[{datetime.now():%H:%M:%S}] diabaikan, chat lain: {asal}")
                continue
            kirim = datetime.fromtimestamp(pesan.get("date", 0), timezone.utc)
            if datetime.now(timezone.utc) - kirim > MAKS_UMUR_PERINTAH:
                print(f"[{datetime.now():%H:%M:%S}] diabaikan, perintah kedaluwarsa: {teks}")
                continue
            try:
                balasan = kendali.perintah(teks)
            except Exception as e:  # noqa: BLE001
                balasan = f"Gagal menjalankan perintah: {type(e).__name__}: {e}"
            if balasan is None:
                continue
            print(f"[{datetime.now():%H:%M:%S}] {teks} -> {balasan.splitlines()[0][:60]}")
            notifier.send(balasan)


def main() -> int:
    try:
        return jalan()
    except KeyboardInterrupt:
        print("\nKendali Telegram dihentikan.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
