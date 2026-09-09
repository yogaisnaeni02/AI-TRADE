# Adendum: Strategi Modal Kecil Agresif (Rp 800.000)

**Versi:** 1.0
**Tanggal:** 9 September 2026
**Status:** Adendum untuk `00-MASTER-PLAN.md`
**Tujuan klien:** Menumbuhkan modal Rp 800.000 secara agresif
**Broker:** Belum dipilih — masih ada ruang untuk keputusan yang tepat

---

## 1. Angka yang Harus Dilihat Dulu

Dokumen ini akan memberikan sistem agresif yang Anda minta. Tapi agresif
harus dibangun di atas aritmetika yang benar, bukan di atas harapan. Berikut
angka yang menentukan segalanya.

### 1.1 Masalah Inti: Lot Minimum vs Modal

Modal: Rp 800.000 = **sekitar $48** (kurs 16.600).

Pada XAUUSD, nilai per point untuk tiap ukuran lot:

| Lot | Nilai per 1 point | Tersedia di |
|---|---|---|
| 1.00 (standard) | $10,00 | Semua broker |
| 0.10 (mini) | $1,00 | Semua broker |
| 0.01 (micro) | $0,10 | **Lot minimum broker standard** |
| 0.001 | $0,01 | Sebagian broker micro |
| 0.01 **cent** | $0,001 efektif | **Akun cent** |

SL yang layak untuk XAUUSD M5 adalah ATR(14) x 1.5, yang secara historis
berkisar **150–250 points**. Kita pakai 200 points sebagai angka kerja.

**Konsekuensinya pada modal $48:**

| Tipe Akun | Lot Min | Risiko per Trade (SL 200 pts) | % dari Modal $48 | Tahan Berapa Loss Beruntun |
|---|---|---|---|---|
| Standard | 0.01 | $20,00 | **41,7%** | **2 trade** |
| Micro | 0.001 | $2,00 | 4,2% | 23 trade |
| **Cent** | 0.01 cent | $0,20 | **0,42%** | 238 trade |

Baris pertama adalah alasan mayoritas akun kecil hilang dalam hitungan hari.
Bukan karena strateginya jelek — karena **lot minimum memaksa risiko 42% per
trade**, dan tidak ada strategi yang selamat dari itu.

> **Kesimpulan yang tidak bisa ditawar:** Dengan modal Rp 800.000, sistem ini
> **hanya boleh dijalankan di akun CENT.** Akun standard secara matematis
> adalah kehancuran terjadwal, bukan trading.

### 1.2 Mengapa "Winrate Tinggi" Justru Menghancurkan Akun Kecil

Anda meminta winrate tinggi untuk membesarkan modal. Saya perlu tunjukkan
kenapa logika ini terbalik, karena inilah jebakan yang menghabiskan mayoritas
akun ritel.

Winrate tinggi sangat mudah dibuat. Pasang TP kecil dan SL besar:

| Setup | Winrate | Hitungan per 100 Trade | Hasil |
|---|---|---|---|
| TP 20 pts / SL 400 pts | ~93% | 93 x 20 = +1.860 ; 7 x 400 = −2.800 | **−940 pts** |
| TP 50 pts / SL 200 pts | ~75% | 75 x 50 = +3.750 ; 25 x 200 = −5.000 | **−1.250 pts** |
| TP 300 pts / SL 150 pts | ~42% | 42 x 300 = +12.600 ; 58 x 150 = −8.700 | **+3.900 pts** |

Baris ketiga punya winrate **paling rendah** dan profit **paling besar**.

Dua baris pertama terasa luar biasa selama beberapa minggu — Anda menang
terus. Lalu satu rentetan loss menghapus semua akumulasi. Ini bukan nasib
buruk; ini hasil yang sudah tertulis di ekspektasinya sejak awal.

**Yang menumbuhkan modal adalah expectancy, bukan winrate:**

```
Expectancy = (Winrate x Avg Win) − (Lossrate x Avg Loss)
```

Sistem apa pun dengan expectancy negatif akan menghabiskan modal — tidak
peduli setinggi apa winrate-nya, tidak peduli secanggih apa AI-nya. Sebaliknya
sistem dengan expectancy positif akan tumbuh meski sering kalah.

**Maka target sistem ini adalah expectancy setinggi mungkin, dan winrate
dibiarkan menjadi apa pun hasilnya.** Itulah definisi agresif yang benar.

### 1.3 Proyeksi Jujur Pertumbuhan Modal

Ini bagian yang paling perlu Anda lihat sebelum memutuskan lanjut.

Asumsi: sistem berjalan **baik** (PF 1.4, expectancy +0.25R), risiko agresif
**3% per trade**, sekitar 60 trade per bulan. Ini menghasilkan sekitar
**+15% per bulan** — angka yang sangat bagus, di atas mayoritas fund
profesional.

| Bulan | Modal (Rp) | Profit Bulan Itu |
|---|---|---|
| 0 | 800.000 | — |
| 3 | 1.216.000 | 158.000 |
| 6 | 1.850.000 | 241.000 |
| 12 | 4.280.000 | 558.000 |
| 24 | 22.900.000 | 2.987.000 |

Angka bulan 24 terlihat menarik. Tapi ada tiga hal yang harus dipahami:

1. **Ini skenario terbaik yang berjalan mulus 24 bulan tanpa gangguan.**
   Probabilitas realistisnya rendah — bukan karena sistemnya jelek, tapi
   karena 24 bulan adalah waktu yang panjang untuk regime market tidak berubah.

2. **Risiko 3% per trade berarti drawdown besar adalah kepastian, bukan
   kemungkinan.** Dengan 3%/trade, rentetan 10 loss (yang pasti terjadi di
   ratusan trade) menghasilkan **DD sekitar 26%**. Anda harus siap secara
   mental melihat modal turun dari Rp 2 juta ke Rp 1,5 juta dan tetap
   menjalankan sistem tanpa mengubah apa pun.

3. **Tahun pertama menghasilkan sekitar Rp 3,5 juta.** Dengan asumsi terbaik.
   Sambil menanggung risiko kehilangan seluruh modal.

### 1.4 Perbandingan Tingkat Risiko

Ini trade-off sesungguhnya dari "agresif":

| Risiko/Trade | Return/Bln (est.) | Max DD (est.) | Risk of Ruin* | Modal Bulan 12 |
|---|---|---|---|---|
| 0,5% (standar pro) | ~2,5% | 8% | <1% | Rp 1.076.000 |
| 1,5% (moderat) | ~7% | 18% | ~3% | Rp 1.800.000 |
| **3% (agresif)** | **~15%** | **26%** | **~12%** | **Rp 4.280.000** |
| 5% (sangat agresif) | ~25% | 45% | ~35% | Rp 11.600.000 |
| 10% (judi) | — | >80% | **>85%** | Rp 0 |

*Risk of Ruin = probabilitas kehilangan lebih dari 50% modal dalam 12 bulan,
dengan asumsi sistem punya edge positif yang terbukti.

**Rekomendasi saya: 3%.** Ini agresif secara nyata (6x lipat standar
profesional), memberi pertumbuhan yang berarti, dan risk of ruin-nya masih
di bawah ambang yang bisa dipertanggungjawabkan.

Baris 5% dan 10% saya cantumkan untuk transparansi, bukan sebagai opsi.
Pada 10%, matematikanya menjamin kehancuran terlepas dari kualitas sistem —
itu bukan trading agresif, itu setoran ke broker dengan langkah tambahan.

---

## 2. Perubahan Desain untuk Mode Agresif

Bagian ini menggantikan parameter terkait di `00-MASTER-PLAN.md`. Semua
bagian lain (ilmu trading, arsitektur, ML, anti-lookahead) tetap berlaku
penuh.

### 2.1 Wajib: Akun Cent

Ini prasyarat mutlak, bukan preferensi.

**Cara kerja akun cent:** Deposit Rp 800.000 ($48) ditampilkan sebagai
**4.800 cent**. Semua perhitungan lot bekerja pada skala 1/100. Efeknya:
lot minimum menjadi 100x lebih kecil, sehingga risk management proper bisa
dijalankan.

**Kriteria pemilihan broker (belum Anda tentukan — putuskan sebelum Fase 0):**

| Kriteria | Syarat | Alasan |
|---|---|---|
| **Akun cent** | Wajib tersedia | Tanpa ini, proyek tidak layak jalan |
| **XAUUSD di akun cent** | Wajib | Sebagian broker hanya sediakan forex pair di cent |
| **Spread XAUUSD** | < 25 points rata-rata | Biaya terbesar sistem ini — lihat Bagian 2.1c |
| **Leverage** | 1:200 s/d 1:500 | Cukup. Di atas 1:1000 tidak menambah manfaat (Bagian 2.1b) |
| **Regulasi** | ASIC / FCA / CySEC | Modal kecil tetap butuh broker yang tidak menghilang |
| **Riwayat data M1** | Minimal 1 tahun | Dibutuhkan untuk training model |
| **API MT5** | Aktif, algo trading diizinkan | Sistem berjalan lewat API |
| **Eksekusi** | Market execution, no dealing desk | Hindari requote |

> **Peringatan:** broker yang menawarkan bonus deposit besar atau leverage
> 1:3000 biasanya tidak teregulasi ketat. Untuk modal kecil, godaannya besar —
> tapi broker yang menolak withdrawal membuat seluruh proyek ini sia-sia.
> Regulasi lebih penting daripada bonus.

### 2.1b Leverage — Klarifikasi Penting

Pertanyaan yang wajar muncul: apakah leverage tinggi (1:1000, 1:3000) bisa
membantu membesarkan modal kecil? Jawabannya perlu presisi, karena ini salah
satu miskonsepsi paling merusak di trading ritel.

**Leverage tidak mengubah risiko. Leverage hanya mengubah margin.**

Uang yang hilang saat SL kena ditentukan sepenuhnya oleh dua hal:
```
Kerugian = Lot x Jarak SL (points) x Nilai per point
```

Leverage tidak ada dalam rumus itu. Buktinya, dengan modal $48, lot 0.01,
SL 200 points:

| Leverage | Margin Dibutuhkan | Rugi Saat SL Kena | Margin Bebas |
|---|---|---|---|
| 1:100 | $40,00 | **$20** | $8 |
| 1:500 | $8,00 | **$20** | $40 |
| 1:1000 | $4,00 | **$20** | $44 |
| 1:3000 | $1,33 | **$20** | $46,67 |

Kolom "Rugi Saat SL Kena" **identik di semua baris**. Menaikkan leverage dari
1:100 ke 1:3000 tidak menghemat satu sen pun saat trade kalah.

**Yang sebenarnya dilakukan leverage tinggi:** menghapus batas alami yang
mencegah Anda membuka posisi terlalu besar.

| Leverage | Lot Maksimum yang Bisa Dibuka ($48) | Pergerakan yang Menghabiskan Akun |
|---|---|---|
| 1:100 | ~0,012 lot | 400 points |
| 1:500 | ~0,06 lot | 80 points |
| 1:1000 | ~0,12 lot | 40 points |
| 1:3000 | ~0,36 lot | **13 points** |

Baris terakhir: pergerakan 13 points di XAUUSD terjadi dalam hitungan detik.
Di leverage 1:100, broker akan **menolak** Anda membuka posisi sebesar itu —
dan penolakan tersebut adalah proteksi.

**Keputusan sistem:**

```yaml
leverage:
  minimum_dibutuhkan: 1:200      # cukup untuk sizing 3% dengan margin longgar
  rekomendasi: 1:500             # ruang aman, tanpa risiko berlebih
  hindari: 1:1000 ke atas        # tidak menambah manfaat, menghapus rem
```

Dengan risiko 3% dan lot dihitung dari jarak SL, **margin tidak akan pernah
menjadi faktor pembatas.** Leverage di atas 1:500 tidak memberi kemampuan
tambahan apa pun untuk sistem ini.

> **Sinyal peringatan broker:** leverage 1:2000–1:3000 hampir selalu
> ditawarkan broker offshore tanpa regulasi ketat. Bagi modal kecil godaannya
> besar, tapi risiko sesungguhnya bukan di leverage-nya — melainkan pada
> broker yang bisa menolak withdrawal atau menghilang. Regulasi (ASIC/FCA/
> CySEC) jauh lebih bernilai daripada angka leverage.

---

### 2.1c Perhitungan Spread — Faktor Penentu Sesungguhnya

Spread jauh lebih menentukan nasib sistem ini daripada leverage. Di modal
kecil dengan timeframe M1/M5, spread adalah **biaya terbesar dan paling
sering diremehkan**.

**Mekanismenya:** setiap posisi dibuka pada harga ask dan ditutup pada harga
bid. Selisihnya (spread) langsung menjadi kerugian di detik pertama. Sebuah
trade harus bergerak sebesar spread hanya untuk mencapai titik impas.

**Dampak spread terhadap expectancy:**

Ambil setup: SL 200 points, TP 400 points (RR 1:2), winrate 45%.

| Spread | RR Efektif | Expectancy/Trade | Perubahan |
|---|---|---|---|
| 0 (teoretis) | 1 : 2,00 | +0,350R | baseline |
| 15 points | 1 : 1,79 | +0,266R | −24% |
| 25 points | 1 : 1,67 | +0,213R | −39% |
| 35 points | 1 : 1,55 | +0,161R | **−54%** |
| 50 points | 1 : 1,40 | +0,085R | **−76%** |

Spread 35 points **memotong lebih dari separuh profitabilitas sistem** —
tanpa mengubah apa pun pada strateginya. Inilah alasan filter spread di
sistem ini bersifat gate (tolak langsung), bukan sekadar poin penilaian.

**Mengapa target kecil mustahil di M1:**

| Target TP | Spread 25 pts | Porsi Biaya | Layak? |
|---|---|---|---|
| 30 points | 25 | **83%** | Tidak — hampir semua profit termakan |
| 50 points | 25 | 50% | Tidak |
| 100 points | 25 | 25% | Marginal |
| 200 points | 25 | 12,5% | Ya |
| 400 points | 25 | **6,25%** | Ya — target sistem ini |

Ini bukti kuantitatif mengapa scalping M1 dengan target 20–50 points tidak
bisa profitabel di XAUUSD ritel. Bukan karena strateginya salah, tapi karena
biayanya melebihi edge yang mungkin diperoleh.

**Aturan wajib sistem:** `TP minimum >= 8 x spread rata-rata`

**Perilaku spread XAUUSD per sesi (perlu diverifikasi di broker Anda):**

| Sesi | Waktu (WIB) | Spread Tipikal | Kebijakan Sistem |
|---|---|---|---|
| Asia | 06:00–14:00 | 25–45 pts | Tidak trading |
| London open | 14:00–17:00 | 15–25 pts | **Trading utama** |
| London–NY overlap | 19:30–23:00 | 12–20 pts | **Trading utama** |
| NY sore | 23:00–04:00 | 20–35 pts | Selektif |
| Rollover (04:00–05:00) | — | 50–150 pts | **Blackout total** |
| Saat rilis berita | — | 80–300 pts | **Blackout total** |

Perhatikan: dua sesi trading utama kita justru adalah sesi dengan spread
terendah. Ini bukan kebetulan — likuiditas tinggi menghasilkan spread sempit
sekaligus pergerakan yang layak ditradingkan. Kedua alasan itu saling
menguatkan.

**Implementasi filter spread (gate, bukan skor):**

```python
MAX_SPREAD_ENTRY = 30      # points - tolak entry di atas ini
MAX_SPREAD_RATIO = 2.0     # tolak jika spread > 2x median 20 hari

def boleh_entry(symbol, tp_distance):
    spread = get_spread_points(symbol)
    if spread > MAX_SPREAD_ENTRY:
        return False, f"spread {spread} melebihi batas"
    if spread > median_spread_20d(symbol) * MAX_SPREAD_RATIO:
        return False, "spread abnormal - kemungkinan berita/rollover"
    if tp_distance < spread * 8:
        return False, "target terlalu kecil relatif terhadap biaya"
    return True, "ok"
```

**Biaya total yang harus dimodelkan di backtest** (bukan hanya spread):

| Komponen | Estimasi XAUUSD | Catatan |
|---|---|---|
| Spread | 15–30 pts | Variabel per sesi — jangan pakai konstanta |
| Slippage entry | 2–8 pts | Lebih besar saat volatil |
| Slippage SL | 3–15 pts | SL sering kena lebih buruk dari harga |
| Komisi | 0–7 pts ekuivalen | Tergantung tipe akun |
| Swap (overnight) | Bervariasi | Sistem intraday: hindari dengan tutup sebelum rollover |
| **Total per trade** | **20–60 pts** | **Ini yang harus dilawan setiap trade** |

Backtest yang hanya memodelkan spread tetap 20 points akan menghasilkan
angka yang jauh lebih optimistis daripada realita. Model biaya realistis
adalah pembeda utama antara backtest yang bisa dipercaya dan yang menyesatkan.

---

### 2.2 Parameter Risiko — Mode Agresif

Menggantikan Bagian 7.2 di master plan:

```yaml
# MODE AGRESIF - modal kecil, akun cent
# Setiap angka di sini adalah hasil trade-off yang disengaja.
# Jangan naikkan tanpa memahami Bagian 1.4.

per_trade:
  max_risk_percent: 3.0        # 6x standar profesional
  min_rr_ratio: 2.0            # DINAIKKAN dari 1.5 - kompensasi risiko besar
  max_lot_percent_equity: 5.0  # hard cap absolut

harian:
  max_loss_percent: 9.0        # setara 3 loss beruntun -> stop
  max_trades: 6                # DITURUNKAN dari 10 - kualitas di atas kuantitas
  max_consecutive_losses: 3    # stop sisa hari, bukan sekadar jeda

mingguan:
  max_loss_percent: 15.0       # stop sisa minggu, evaluasi wajib

global:
  max_drawdown_percent: 25.0   # MATIKAN SISTEM - review menyeluruh
  max_open_positions: 1        # tidak berubah - jangan pernah dinaikkan
  max_spread_points: 30        # DIPERKETAT - biaya lebih menyakitkan di modal kecil
```

**Perhatikan pola pentingnya:** saat risiko per trade naik 6x lipat, hampir
semua parameter lain justru **diperketat** — RR minimum naik, jumlah trade
turun, filter spread diperketat. Ini bukan inkonsistensi. Inilah cara agresif
yang bertahan hidup: mengambil risiko lebih besar pada **lebih sedikit
setup berkualitas lebih tinggi**, bukan pada lebih banyak setup sembarangan.

Agresif yang naif menaikkan semua angka sekaligus. Itu yang menghabiskan akun.

### 2.3 Seleksi Setup — Hanya Grade A

Dengan risiko 3% per trade, setiap trade harus benar-benar layak. Sistem
hanya mengambil setup dengan skor konfluensi tertinggi.

**Sistem skoring (entry hanya jika skor >= 7 dari 10):**

| Faktor | Poin | Keterangan |
|---|---|---|
| Sesi London/NY overlap | 2 | Wajib — Asia tidak ditradingkan sama sekali |
| Searah struktur HTF (H1+H4) | 2 | Wajib — tidak pernah melawan HTF |
| Liquidity sweep terkonfirmasi | 2 | Setup unggulan |
| CHoCH di M1 setelah sweep | 1 | Konfirmasi timing |
| Entry di FVG / order block | 1 | Kualitas lokasi entry |
| ATR di rentang normal (p30–p85) | 1 | Bukan market mati, bukan berita |
| Probabilitas model ML >= 0.65 | 1 | Filter akhir |
| **Spread <= 25 points** | **gate** | Bukan poin — langsung tolak jika gagal |
| **Di luar window berita** | **gate** | Bukan poin — langsung tolak jika gagal |

Konsekuensinya: **1–3 trade per hari, bukan 10–15.** Ini disengaja.

Di modal kecil, satu trade buruk dengan risiko 3% menghapus hasil dua trade
bagus. Selektivitas bukan kehati-hatian berlebihan — ini justru sumber
agresivitas yang sesungguhnya, karena modal terkonsentrasi hanya pada setup
dengan expectancy tertinggi.

### 2.4 Manajemen Posisi untuk Memaksimalkan RR

Dengan risiko 3%, memaksimalkan sisi kemenangan menjadi krusial.

```
Entry     : posisi penuh berdasarkan hitungan risiko 3%
1.0R      : geser SL ke break-even + biaya spread
            -> mulai titik ini, trade tidak bisa rugi lagi
1.5R      : tutup 50% posisi (kunci profit)
Sisa 50%  : trailing stop ATR x 2.0
            -> biarkan berjalan; ini sumber trade 4R-6R
Timeout   : tutup paksa setelah 40 bar M5 jika belum kena TP/SL
```

**Alasan struktur ini:** distribusi profit trading sangat timpang — sebagian
kecil trade menghasilkan mayoritas keuntungan. Menutup semua posisi di 2R
memotong justru trade yang paling berharga. Kombinasi partial close (mengunci
profit, menstabilkan equity curve) dengan runner (menangkap ekor distribusi)
memberi keduanya.

Break-even di 1R sangat penting di mode agresif: setelah titik itu, trade
tersebut tidak bisa lagi menyentuh modal Anda.

### 2.5 Compounding Bertahap — dan Kapan Menariknya

**Aturan compounding:**

```python
# Lot dihitung ulang dari equity aktual setiap trade
risk_amount = current_equity * 0.03
```

Modal naik, lot naik otomatis. Ini mesin pertumbuhannya.

**Aturan de-risking (sama pentingnya):**

| Kondisi | Aksi |
|---|---|
| DD > 15% | Turunkan risiko ke 1,5% sampai equity pulih |
| DD > 20% | Turunkan risiko ke 1,0%, evaluasi sistem |
| DD > 25% | **Stop total**, review menyeluruh |
| Modal > 2x awal | Pertimbangkan tarik modal awal (lihat di bawah) |

**Penarikan modal — putuskan sekarang, bukan nanti:**

Saat modal mencapai **Rp 1.600.000 (2x lipat)**, ada keputusan penting:
tarik Rp 800.000 (modal awal) keluar, lanjutkan trading dengan profit saja.

Setelah itu, secara matematis Anda tidak bisa rugi lagi dari uang sendiri.
Ini mengubah karakter psikologis seluruh proyek — dan psikologi adalah faktor
yang paling sering merusak sistem yang sebenarnya sudah bagus.

Saya sarankan menuliskan aturan ini sekarang, saat belum ada uang di meja.
Keputusan yang dibuat saat modal sudah 2x lipat hampir selalu lebih buruk,
karena saat itu ada euforia dan dorongan untuk "gaspol karena lagi bagus".

---

## 3. Yang Tetap Tidak Boleh Dilakukan

Mode agresif menaikkan risiko per trade. Mode agresif **tidak** membuka
praktik-praktik berikut. Semua ini menciptakan ilusi winrate tinggi lalu
menghapus akun.

| Larangan | Yang Terjadi pada Modal Rp 800rb |
|---|---|
| **Martingale** | Akun habis di rentetan loss ke-4. Bukan kemungkinan — kepastian matematis |
| **Grid tanpa SL** | Satu trend gold 500 points menghapus seluruh modal |
| **Averaging down** | Memperbesar posisi yang sudah terbukti salah |
| **Trading tanpa SL** | Satu spike berita = akun nol |
| **Risiko > 5% per trade** | Risk of ruin melewati 35%, edge apa pun tidak relevan |
| **Melebarkan SL saat floating loss** | Cara paling umum akun kecil mati |
| **Menambah posisi saat rugi** | Kerugian tidak berkorelasi dengan peluang pemulihan |
| **Menonaktifkan limit saat "yakin"** | Limit dibuat justru untuk momen merasa yakin |

Semua ini akan **dikunci di level kode**, bukan sekadar dicatat di dokumen.
Risk manager menolak eksekusi yang melanggar aturan ini, dan aturannya berada
di file konfigurasi terpisah (`risk_limits.yaml`) agar perubahannya disengaja
dan terlihat.

---

## 4. Kriteria Kelulusan Sebelum Uang Nyata

Karena risikonya 3% per trade, standar validasi justru **dinaikkan**, bukan
diturunkan. Modal kecil tidak punya ruang untuk kesalahan yang bisa diserap.

**Backtest (Fase 3–4):**
- [ ] Profit Factor > 1,5 (dinaikkan dari 1,25)
- [ ] Expectancy > 0,25R
- [ ] Max DD < 25% pada simulasi risiko 3%
- [ ] Konsisten profit di **minimal 8 dari 10 fold** walk-forward
- [ ] Monte Carlo: DD persentil ke-95 masih di bawah 35%
- [ ] Sensitivitas parameter +/-20% tidak menghancurkan hasil
- [ ] Minimal 200 trade dalam sampel uji

**Forward test demo (Fase 7) — minimal 6 minggu:**
- [ ] Minimal 60 trade tercatat
- [ ] Profit Factor > 1,3 di kondisi live
- [ ] Deviasi dari backtest < 30%
- [ ] Tidak ada pelanggaran risk limit
- [ ] Sistem berjalan tanpa intervensi manual

**Live bertahap:**
- [ ] Bulan 1: risiko **1%** (bukan 3%) — verifikasi eksekusi nyata
- [ ] Bulan 2: risiko 2% jika metrik sesuai
- [ ] Bulan 3+: risiko 3% penuh jika tetap konsisten

Menaikkan risiko langsung ke 3% di hari pertama live berarti melewatkan
satu-satunya kesempatan mendeteksi masalah eksekusi (slippage nyata, perilaku
broker, bug) selagi biayanya masih murah.

---

## 5. Skenario Realistis 12 Bulan

Agar keputusan Anda berdasar gambaran lengkap, bukan hanya skenario terbaik:

| Skenario | Probabilitas | Modal Bulan 12 | Penyebab |
|---|---|---|---|
| **Sangat baik** | ~10% | Rp 4.000.000+ | Sistem punya edge nyata, regime market kondusif |
| **Baik** | ~20% | Rp 1.800.000–3.000.000 | Edge ada, ada periode drawdown |
| **Impas** | ~30% | Rp 600.000–1.200.000 | Edge tipis, termakan biaya transaksi |
| **Rugi** | ~25% | Rp 200.000–600.000 | Edge tidak bertahan di luar sampel |
| **Habis** | ~15% | Mendekati Rp 0 | Sistem gagal, atau disiplin risk dilanggar |

Angka-angka ini adalah estimasi berdasar tingkat kegagalan umum proyek
algo trading ritel, bukan hasil perhitungan presisi. Tapi urutan besarannya
mencerminkan realita: **peluang gagal lebih besar daripada peluang berhasil
besar.** Itu berlaku untuk semua trading, dan lebih tajam lagi di modal kecil
dengan risiko agresif.

Yang bisa dikendalikan bukan hasilnya, melainkan kualitas prosesnya —
validasi yang jujur, risk management yang dikunci di kode, dan disiplin
menjalankan sistem tanpa intervensi emosional. Bagian 4 di atas ada untuk itu.

---

## 6. Rekomendasi Akhir

Anda memilih untuk mengejar profit dari Rp 800.000. Saya akan bangun sistem
yang memberi peluang terbaik untuk itu, dengan tiga syarat yang menurut saya
tidak bisa dinegosiasikan:

1. **Akun cent.** Tanpa ini, sistem apa pun akan gagal karena lot minimum
   memaksa risiko 42% per trade. Ini bukan preferensi teknis — ini penentu
   apakah proyek ini punya peluang sama sekali.

2. **Risiko 3%, bukan lebih.** Ini sudah 6x lipat standar profesional dan
   memberi potensi pertumbuhan nyata. Di atas 5%, matematika risk of ruin
   mengambil alih dan kualitas sistem menjadi tidak relevan.

3. **Target expectancy, bukan winrate.** Sistem akan punya winrate sekitar
   40–50% dengan RR 1:2 atau lebih. Ini akan terasa "sering kalah" — dan
   justru inilah bentuk sistem yang menumbuhkan modal. Jika di tengah jalan
   sistem diubah untuk mengejar winrate tinggi, expectancy-nya akan runtuh.

Satu catatan yang perlu saya sampaikan sekali dan tidak akan saya ulangi:
dengan skenario terbaik pun, tahun pertama menghasilkan sekitar Rp 3,5 juta,
dengan probabilitas kehilangan modal sekitar 15%. Jika di titik mana pun
Anda punya akses ke tambahan modal, menunggu sampai modal 5–10 juta akan
mengubah proyek ini dari "pertaruhan dengan peluang tipis" menjadi "usaha
dengan ekspektasi masuk akal" — karena pada modal itu, risiko 1% sudah cukup
menghasilkan sesuatu yang berarti, dan risk of ruin turun drastis.

Tapi itu keputusan Anda, dan Anda sudah menyatakannya. Plan ini dibangun
untuk pilihan yang Anda ambil.

---

## 7. Langkah Berikutnya

**Keputusan yang harus diambil sebelum coding:**
1. Pilih broker dengan akun cent + XAUUSD (kriteria di Bagian 2.1)
2. Konfirmasi tingkat risiko: 3% (rekomendasi) atau angka lain
3. Sepakati aturan penarikan modal di 2x lipat (Bagian 2.5)

**Setelah broker dipilih:**
4. Buka akun **demo** dulu di broker tersebut
5. Jalankan `scripts/phase0_probe.py` — verifikasi spread, tick value,
   stops_level, dan kedalaman riwayat M1 di akun cent
6. Mulai Fase 0 sesuai `00-MASTER-PLAN.md`

**Catatan teknis penting untuk akun cent:** `tick_value` dan `contract_size`
di akun cent **berbeda** dari akun standard. Script probe akan menampilkan
angka sebenarnya. Position sizing wajib memakai angka dari probe, bukan
asumsi — kesalahan di sini menghasilkan lot 100x lebih besar dari yang
dimaksud, dan modal habis dalam satu trade.

---

*Adendum ini melengkapi, bukan menggantikan, `00-MASTER-PLAN.md`. Seluruh
metodologi (market structure, sesi, ML meta-labeling, anti-lookahead,
backtesting realistis) tetap berlaku penuh. Yang berubah hanya parameter
risiko dan tingkat selektivitas setup.*
