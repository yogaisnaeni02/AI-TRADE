"""Fixture bersama untuk pytest.

KENAPA ADA
----------
tests/test_risk_manager.py ditulis agar bisa dijalankan DUA cara:

    python tests/test_risk_manager.py     <- main() mengisi `tmp` sendiri
    pytest tests/                          <- pytest yang harus mengisinya

Cara pertama selalu berhasil (13/13 lolos). Cara kedua GAGAL karena pytest
tidak mengenal nama `tmp` - fixture bawaannya bernama `tmp_path`. Hasilnya
13 tes itu tidak pernah benar-benar dijalankan lewat pytest, hanya
dilaporkan sebagai ERROR.

Akibatnya berbahaya: `pytest tests/` selalu menampilkan 13 error, sehingga
error itu dianggap "wajar" dan diabaikan - termasuk seandainya nanti ada
error BARU yang sungguhan. Kebisingan tetap menyembunyikan sinyal.

Fixture di bawah menjembatani nama itu, sehingga kedua cara menjalankan
tes memberi hasil yang sama.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp(tmp_path: Path) -> Path:
    """Alias `tmp_path` bawaan pytest, dengan nama yang dipakai tes lama."""
    return tmp_path
