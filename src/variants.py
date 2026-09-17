"""
Loader varian — pilih satu preset dari config/variants.yaml dan terapkan
sebagai override di atas settings.yaml dasar.

KENAPA ADA
----------
Sistem punya beberapa fitur yang masing-masing punya flag sendiri
(confluence_filter, allow_sell, dst). Modul ini memberi satu titik pilih:
nama varian -> config lengkap + magic number khusus untuk varian itu.

Magic number per varian memungkinkan beberapa varian jalan BERDAMPINGAN
di akun demo yang sama tanpa bercampur di journal atau dashboard — tiap
`positions_get()` dan `history_deals_get()` disaring per magic.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
VARIANTS_PATH = ROOT / "config" / "variants.yaml"

BASELINE_MAGIC = 20260909


def _deep_merge(base: dict, override: dict) -> dict:
    """Gabung rekursif: override menang, tapi tidak menghapus kunci lain."""
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_variants_file() -> dict:
    if not VARIANTS_PATH.exists():
        return {"varian": {}}
    with open(VARIANTS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"varian": {}}


def list_variants() -> dict[str, dict]:
    """Nama varian -> metadata (deskripsi, status, magic, dst)."""
    return load_variants_file().get("varian", {})


def get_variant(name: str) -> dict:
    """Metadata satu varian. Melempar KeyError dengan pesan yang berguna."""
    variants = list_variants()
    if name not in variants:
        tersedia = ", ".join(sorted(variants)) or "(tidak ada varian terdaftar)"
        raise KeyError(f"varian '{name}' tidak dikenal. Tersedia: {tersedia}")
    return variants[name]


def apply_variant(base_config: dict, name: str) -> tuple[dict, int, dict]:
    """Terapkan override varian ke atas config dasar.

    Return: (config_hasil, magic_number, metadata_varian)
    """
    meta = get_variant(name)
    override = meta.get("override") or {}
    merged = _deep_merge(base_config, override)
    magic = int(meta.get("magic", BASELINE_MAGIC))
    return merged, magic, meta


def apply_risk_override(base_risk: dict, name: Optional[str]) -> dict:
    """Terapkan `override_risk` varian ke atas risk_limits.yaml.

    Dipisah dari apply_variant() karena settings.yaml dan risk_limits.yaml
    adalah dua file berbeda yang dimuat terpisah. Varian yang hanya
    mengubah batas risiko (mis. max_open_positions) memakai kunci
    `override_risk`, bukan `override`.

    name=None -> risk apa adanya, tidak disentuh.
    """
    if name is None:
        return base_risk
    meta = get_variant(name)
    override = meta.get("override_risk") or {}
    if not override:
        return base_risk
    return _deep_merge(base_risk, override)


def resolve(name: Optional[str], base_config: Optional[dict] = None) -> tuple[dict, int, dict]:
    """Titik masuk utama.

    name=None -> config dasar (settings.yaml) APA ADANYA, magic bawaan.
    TIDAK diam-diam memilih varian "baseline" — settings.yaml sendiri
    bisa berubah dari waktu ke waktu (mis. eksperimen allow_sell yang
    ditulis langsung di sana), dan siapa pun yang memanggil TradingBot()
    tanpa argumen varian mengharapkan perilaku "ikuti config", bukan
    "override diam-diam ke preset tertentu". Untuk benar-benar memakai
    preset "baseline" dari variants.yaml, sebutkan namanya secara eksplisit.
    """
    if base_config is None:
        from src.data.mt5_gateway import load_config
        base_config = load_config()

    if name is None:
        return base_config, BASELINE_MAGIC, {}

    return apply_variant(base_config, name)


def format_table() -> str:
    """Tabel ringkas semua varian bernomor, untuk ditampilkan di CLI.

    Nomornya urutan di config/variants.yaml - nomor yang sama diterima
    `pilih()`, jadi orang cukup mengetik "3" alih-alih nama lengkap.
    """
    variants = list_variants()
    if not variants:
        return "(tidak ada varian terdaftar di config/variants.yaml)"

    rows = []
    for no, (name, meta) in enumerate(variants.items(), start=1):
        rows.append((
            str(no),
            name,
            str(meta.get("magic", "-")),
            str(meta.get("status", "-")),
            (meta.get("deskripsi") or "").strip().split("\n")[0][:60],
        ))

    wn = max(len(r[0]) for r in rows) + 2
    w0 = max(len(r[1]) for r in rows) + 2
    w1 = max(len(r[2]) for r in rows) + 2
    w2 = max(len(r[3]) for r in rows) + 2

    lines = [f"{'no':<{wn}}{'varian':<{w0}}{'magic':<{w1}}{'status':<{w2}}deskripsi"]
    lines.append("-" * (wn + w0 + w1 + w2 + 40))
    for no, name, magic, status, desc in rows:
        lines.append(f"{no:<{wn}}{name:<{w0}}{magic:<{w1}}{status:<{w2}}{desc}")
    return "\n".join(lines)


def pilih(pilihan: str) -> Optional[str]:
    """Nomor dari format_table() atau nama varian -> nama varian, None bila tidak dikenal.

    Nama tetap diterima (tanpa beda huruf besar/kecil) supaya kebiasaan
    lama dan skrip yang sudah memakai nama tidak rusak.
    """
    teks = (pilihan or "").strip()
    nama = list(list_variants())
    if teks.isdigit():
        i = int(teks)
        return nama[i - 1] if 1 <= i <= len(nama) else None
    cocok = [n for n in nama if n.lower() == teks.lower()]
    return cocok[0] if cocok else None


if __name__ == "__main__":
    # Dipakai 5-JALANKAN-VARIAN.bat - tanpa mengimpor MetaTrader5, jadi cepat.
    #   python -m src.variants              tabel bernomor
    #   python -m src.variants --pilih 3    cetak nama varian; kode 1 bila tidak dikenal
    import sys

    if len(sys.argv) == 3 and sys.argv[1] == "--pilih":
        hasil = pilih(sys.argv[2])
        if hasil is None:
            sys.exit(1)
        print(hasil)
    else:
        print(format_table())
