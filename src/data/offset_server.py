"""
Pelacak offset jam server MT5 terhadap UTC — murni, tanpa MetaTrader5.

MASALAH
-------
detect_server_offset_hours() menghitung offset dari waktu TICK TERAKHIR
setiap kali dipanggil. Selama pasar aktif hasilnya benar. Tetapi saat tidak
ada tick - jeda harian emas 21:00-22:00 UTC (04:00-05:00 WIB) dan akhir
pekan - tick terakhir makin basi dan pembulatannya melenceng:

    tick basi 31 menit   -> -0,52 jam -> dibulatkan -1
    tick basi 49 jam     -> -49        (restart hari Minggu)

Bot lalu menggeser seluruh time_utc sebesar itu. Label sesi, cutoff Jumat
dan timeout ikut salah, dan perubahan bar_time palsu memicu process_bar()
ulang pada bar lama saat pasar tutup - order ditolak, penghitung order gagal
beruntun naik, dan 3 kegagalan menghentikan sistem.

PERBAIKAN
---------
Offset aktif hanya BERUBAH bila pengukuran baru:
  1. jatuh dekat bilangan bulat jam (tick segar),
  2. masuk rentang zona waktu nyata, dan
  3. konsisten selama KONFIRMASI_MENIT.

Tick basi terus bergeser sehingga tidak pernah lolos syarat 3, sedangkan
perubahan offset sungguhan (DST, migrasi server) tetap terdeteksi karena
selama pasar aktif pengukurannya stabil.

Nilai awal = broker.server_utc_offset di config (sudah diverifikasi dan
dijaga downloader), sehingga bot yang di-restart saat pasar tutup tidak
menebak dari tick Jumat. Perbedaan config vs pengukuran tetap dilaporkan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

TOLERANSI_MENIT = 10
KONFIRMASI_MENIT = 30
RENTANG_JAM = (-12, 14)


def ukur(tick_epoch: int, now_utc: datetime) -> tuple[int, bool]:
    """(offset dibulatkan ke jam, segar?) dari satu tick.

    MT5 mengembalikan jam dinding server sebagai epoch; membacanya sebagai
    UTC memberi jam dinding server apa adanya.
    """
    server_wall = datetime.fromtimestamp(tick_epoch, tz=timezone.utc)
    jam = (server_wall - now_utc).total_seconds() / 3600
    bulat = round(jam)
    segar = (abs(jam - bulat) * 60 <= TOLERANSI_MENIT
             and RENTANG_JAM[0] <= bulat <= RENTANG_JAM[1])
    return int(bulat), segar


@dataclass
class PelacakOffset:
    offset_config: Optional[int] = None
    aktif: Optional[int] = None
    kandidat: Optional[int] = None
    kandidat_sejak: Optional[datetime] = None
    pesan: list[str] = field(default_factory=list)

    def perbarui(self, tick_epoch: int, now_utc: datetime) -> int:
        bulat, segar = ukur(tick_epoch, now_utc)

        if self.aktif is None:
            if self.offset_config is not None:
                self.aktif = int(self.offset_config)
            elif segar:
                self.aktif = bulat
            else:
                raise ConnectionError(
                    "Offset server belum pernah terukur, config tidak mencatatnya, "
                    "dan tick terakhir basi (pasar tutup?). Coba lagi saat pasar buka."
                )

        if not segar or bulat == self.aktif:
            self.kandidat = self.kandidat_sejak = None
            return self.aktif

        if self.kandidat != bulat:
            self.kandidat, self.kandidat_sejak = bulat, now_utc
            self.pesan.append(
                f"offset server terukur {bulat} jam, beda dari yang dipakai "
                f"({self.aktif}) - menunggu konfirmasi {KONFIRMASI_MENIT} menit"
            )
        elif now_utc - self.kandidat_sejak >= timedelta(minutes=KONFIRMASI_MENIT):
            self.pesan.append(
                f"OFFSET SERVER BERUBAH {self.aktif} -> {bulat} jam "
                f"(konsisten {KONFIRMASI_MENIT} menit). Perbarui "
                "broker.server_utc_offset di config/settings.yaml."
            )
            self.aktif = bulat
            self.kandidat = self.kandidat_sejak = None
        return self.aktif

    def ambil_pesan(self) -> list[str]:
        out, self.pesan = self.pesan, []
        return out
