# Panduan instalasi dan demo DSS Pemasok

## 1. Persiapan

Ekstrak seluruh isi `DSS-Streamlit.zip` ke satu folder. Pasang Python 3.12 atau lebih baru. Buka folder itu di VS Code, lalu buka **Terminal → New Terminal**. Pastikan `app.py`, `store.py`, `engine.py`, `requirements.txt`, folder `data`, dan folder `assets` tetap dalam folder proyek yang sama.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

Buka alamat `http://localhost:8501` yang muncul di terminal. Tekan `Ctrl+C` untuk menghentikan server.

## 2. Siapkan akun

1. Pada instalasi baru, halaman pertama meminta **nama pengguna dan kata sandi admin**. Gunakan kata sandi minimal 10 karakter. Catat kredensial ini di tempat aman.
2. Setelah masuk sebagai admin, buka **Kelola proyek → 3 · Akun DM**.
3. Buat akun untuk DM1, DM2, dan DM3 dengan nama pengguna dan kata sandi berbeda. Berikan kredensial masing-masing hanya kepada DM terkait.
4. Untuk penilai tambahan, gunakan **Tambah DM baru beserta akunnya**. Bobot awal DM baru 0%; atur pada tab **4 · Bobot & skala**.
5. Setiap DM membuka alamat server, masuk dengan akunnya sendiri, dan hanya melihat halaman **Penilaian saya**.

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

Proyek serta akun tersimpan pada `data/dss.sqlite3` di komputer server. File SQLite tidak disertakan dalam ZIP sumber dan dibuat otomatis saat instalasi baru. Simpan cadangan file database ketika server berhenti jika ingin mempertahankan akun dan data persis. Admin juga dapat mengekspor JSON untuk data proyek; setelah JSON diimpor pada instalasi lain, akun harus dibuat kembali karena JSON tidak berisi kata sandi.

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
