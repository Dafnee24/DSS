# Panduan instalasi dan demo DSS Pemasok

## 1. Clone dan jalankan

Pasang Git dan Python 3.12 atau lebih baru. Buka Terminal (macOS) atau PowerShell (Windows). Perintah berikut mengunduh proyek dari GitHub, memasang paket, dan menjalankan Streamlit. Excel tidak perlu dipasang.

### macOS

```bash
git clone https://github.com/Dafnee24/DSS.git
cd DSS
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

### Windows PowerShell

```powershell
git clone https://github.com/Dafnee24/DSS.git
cd DSS
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Buka `http://localhost:8501` atau alamat yang muncul di terminal. Tekan `Ctrl+C` untuk menghentikan server. Saat menjalankan lagi, masuk ke folder `DSS` dan ulangi perintah `... -m streamlit run app.py` sesuai sistem operasi. Jika folder proyek sudah ada, jalankan `git pull origin main` dari dalam folder itu untuk mengambil pembaruan.

## 2. Akun demo yang langsung tersedia

Pada clone baru, aplikasi otomatis membuat akun berikut saat pertama dijalankan. **Tidak perlu membuat admin atau akun DM secara manual.**

| Peran | Nama pengguna | Kata sandi |
| --- | --- | --- |
| Admin | `admin` | `AdminDSS2026!` |
| DM1 | `dm1` | `DM1DSS2026!` |
| DM2 | `dm2` | `DM2DSS2026!` |
| DM3 | `dm3` | `DM3DSS2026!` |

Admin dapat melihat hasil seluruh DM dan mengelola proyek. Setiap DM masuk dengan akunnya sendiri dan hanya dapat mengubah penilaiannya sendiri. Untuk penilai tambahan, admin memakai **Kelola proyek → 3 · Akun DM → Tambah DM baru beserta akunnya**. Bobot awal DM baru 0%; atur di tab **4 · Bobot & skala**.

Kredensial di atas adalah akun **demo yang dipublikasikan bersama source code**. Jika aplikasi dibuka untuk orang lain melalui jaringan, ganti kata sandi admin dan tiap DM terlebih dahulu. Kata sandi di database disimpan sebagai hash, sedangkan tabel di atas memang berisi kata sandi demo untuk pengujian.

### Jika kata sandi demo salah setelah `git pull`

`git pull` memperbarui program, tetapi **tidak mengganti akun pada `data/dss.sqlite3` yang sudah ada**. Jadi pada clone yang pernah dijalankan, gunakan akun lama. Untuk mencoba empat akun demo tanpa menghapus data lama, hentikan Streamlit (`Ctrl+C`), buka terminal di folder clone tersebut, lalu jalankan dengan **database demo terpisah**:

macOS:

```bash
DSS_DB_PATH="$PWD/data/dss-demo.sqlite3" .venv/bin/python -m streamlit run app.py
```

Windows PowerShell:

```powershell
$env:DSS_DB_PATH = (Join-Path (Get-Location) 'data\dss-demo.sqlite3')
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Perintah ini membuat `dss-demo.sqlite3` pada pemakaian pertama dan menyiapkan akun pada tabel di atas. Database lama `dss.sqlite3` tetap ada. Di PowerShell, jalankan `Remove-Item Env:DSS_DB_PATH` sebelum kembali ke database lama; di macOS, jalankan perintah Streamlit biasa tanpa awalan `DSS_DB_PATH=...`. Jika pernah memakai `dss-demo.sqlite3` dan mengubah kata sandinya, gunakan nama file demo baru.

Pada satu komputer, beberapa akun dapat didemokan lewat jendela browser yang berbeda atau mode privat. Jika DM mengakses dari perangkat lain pada jaringan yang sama, jalankan Streamlit dengan alamat jaringan yang sesuai dan gunakan alamat komputer server. Pengaturan jaringan di luar komputer lokal menjadi tanggung jawab penyelenggara demo.

## 3. Alur demo yang disarankan

1. **Admin:** buka Hasil grup; pada data awal Al1 adalah ranking 1.
2. **DM1:** masuk di browser lain; ubah satu Linguistic Term, misalnya Al1-C8, lalu klik **Simpan penilaian saya**. Pastikan DM1 hanya melihat matriksnya sendiri.
3. **Admin:** muat ulang Hasil grup; lihat perubahan skor DM1 dan ranking gabungan. Pada tab Perbandingan DM, hasil DM2 dan DM3 tetap berasal dari penilaian mereka sendiri.
4. **DM2:** masuk dengan akun berbeda; ubah salah satu nilainya. Coba lihat bahwa tidak ada pemilih atau editor DM1 di akun DM2.
5. **Admin:** buka Kelola proyek → Bobot & skala, ubah bobot, lalu lihat hasil grup. Buka Rincian perhitungan untuk melihat MEREC dan MARCOS.
6. **DM:** klik **Konfirmasi penilaian selesai** setelah memeriksa tabel. Admin melihat status pada tab **Status & catatan**.
7. **Admin:** unduh JSON dan ZIP hasil dari tab **Berkas**. JSON memuat proyek, penilaian, status, catatan, dan riwayat; **kata sandi akun tidak diekspor**.

## 4. Penyimpanan dan pemulihan

Proyek serta akun tersimpan pada `data/dss.sqlite3` di komputer server. File SQLite tidak diunggah ke GitHub dan dibuat otomatis saat aplikasi pertama kali berjalan. Setiap clone baru mulai dari data Excel awal dan empat akun demo di atas. `git pull` **tidak menghapus atau mengganti** akun pada database yang sudah ada; jadi clone lama tetap memakai kata sandi yang sebelumnya dibuat atau diubah. Jika ingin mencoba akun demo tanpa mengganggu data lama, clone proyek lagi ke folder baru, misalnya `git clone https://github.com/Dafnee24/DSS.git DSS-demo`.

Simpan cadangan database ketika server berhenti jika ingin mempertahankan akun dan data persis. Admin juga dapat mengekspor JSON untuk data proyek; JSON tidak berisi kata sandi akun.

Impor Excel hanya mendukung struktur awal 14 alternatif × 12 kriteria × 3 DM. Jika struktur telah diubah melalui aplikasi, gunakan JSON. Impor dan pemulihan proyek hanya dapat dilakukan admin. Perubahan admin dari tab Kelola proyek akan ditolak jika ada browser lain yang menyimpan penilaian lebih baru; muat ulang halaman sebelum mengulanginya.

## 5. Pengujian

```bash
python -m unittest discover -s tests -v
```

Tes mencakup kecocokan 4.924 sel numerik data awal terhadap cache Excel, login, pembatasan akses DM/admin, penyimpanan dari dua akun DM, konflik perubahan admin, serta alur UI. Excel tidak perlu terpasang.

## 6. Jika terjadi kendala

- `ModuleNotFoundError`: ulangi pemasangan `requirements.txt` menggunakan Python dari `.venv`.
- Lupa kata sandi DM: admin dapat memakai **Reset kata sandi DM** pada tab Akun DM.
- Lupa kata sandi admin: tidak ada pintu belakang di aplikasi. Pulihkan dari cadangan database atau buat instalasi baru; menghapus database lama juga menghapus seluruh data dan akun.
- Perubahan DM belum terlihat pada admin: muat ulang halaman admin; pastikan DM telah menekan tombol **Simpan penilaian saya**.
- Input ditolak: nama harus terisi dan unik; Linguistic Term harus dari skala; nilai crisp positif; sedikitnya satu bobot DM lebih dari nol.
- Hasil tidak sama dengan Excel: pulihkan data awal, samakan input/bobot, dan hitung ulang workbook Excel. Pembandingan alamat sel hanya berlaku pada struktur awal.
