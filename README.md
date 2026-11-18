# DSS Pemasok - Prototipe Streamlit

Prototipe pemilihan pemasok dengan **MEREC-MARCOS**, mengikuti rumus pada `data/DSS PROJECT.xlsx`. Jurnal menjadi referensi kasus; metode asli SWARA-EDAS dari jurnal tidak digunakan. Data awal memuat 14 alternatif, 12 kriteria, dan 3 pengambil keputusan (DM). Alternatif, kriteria, dan DM dapat ditambah, diubah, atau dihapus oleh admin.

## Jalankan

Python 3.12 atau lebih baru; clone repo ini lalu jalankan pada macOS:

```bash
git clone https://github.com/Dafnee24/DSS.git
cd DSS
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Buka `http://localhost:8501`. Langkah Windows PowerShell dan daftar akun demo ada di [PANDUAN_INSTALASI.md](PANDUAN_INSTALASI.md).

## Masuk dan alur kerja

Pada clone baru, aplikasi otomatis membuat akun demo admin, DM1, DM2, dan DM3. Nama pengguna dan kata sandinya tercantum di [panduan instalasi](PANDUAN_INSTALASI.md). Admin dapat menambah DM baru beserta akunnya dalam satu langkah. Kata sandi di database disimpan sebagai hash PBKDF2; kredensial demo di panduan bersifat publik dan perlu diganti jika server dibuka ke jaringan.

Clone lama yang diperbarui dengan `git pull` tetap memakai akun lama pada database lokal. Lihat bagian **Jika kata sandi demo salah setelah `git pull`** dalam panduan untuk menjalankan database demo terpisah tanpa menghapus data lama.

1. **Admin - Kelola proyek:** atur alternatif, kriteria, akun DM, bobot, dan skala. Impor/ekspor data ada pada tab Berkas.
2. **DM - Penilaian saya:** masuk dengan akun sendiri, pilih atau ubah kode Linguistic Term pada tabel miliknya, lalu klik **Simpan penilaian saya**. DM dapat melihat skor miliknya dan mengonfirmasi penilaian selesai. Tidak ada pemilih DM lain pada tampilan DM.
3. **Admin - Hasil grup:** lihat ranking gabungan, skor semua DM, bobot MEREC, status pengisian, catatan, dan riwayat keputusan. Perubahan yang disimpan DM muncul setelah halaman admin dimuat ulang.
4. **Admin - Rincian perhitungan:** pilih satu DM dan satu tahap untuk menelusuri tabel MEREC/MARCOS serta padanan alamat Excel awal.

Data bersama disimpan dalam SQLite di `data/dss.sqlite3` pada komputer yang menjalankan Streamlit. Akun yang masuk sebagai DM hanya menerima data penilaiannya sendiri dari penyimpanan dan operasi simpan di server hanya dapat mengubah matriks DM yang terikat ke akun itu. Admin memiliki akses ke seluruh hasil. Perubahan dari browser berbeda tersimpan dalam proyek yang sama; admin perlu memuat ulang halaman untuk melihat perubahan terbaru.

Admin dapat mengubah kata sandi sendiri, mereset kata sandi DM, dan menghapus akun saat DM dihapus. DM dapat mengganti kata sandinya sendiri. SQLite dan akun demo lokal ini ditujukan untuk prototipe; penempatan di internet memerlukan pengamanan operasional tambahan.

## Rumus dan kesetaraan Excel

Rumus dalam `engine.py` tidak diubah oleh sistem login. Data awal masih dicocokkan dengan **4.924 sel numerik** yang tersimpan di workbook, toleransi `1e-12`.

| Tahap | Rumus / perilaku | Lokasi Excel awal |
| --- | --- | --- |
| Linguistik ke crisp | Pencarian persis kode pada skala | B24:M37 |
| Normalisasi MEREC | Benefit: min(x)/x; Cost: x/max(x) | B41:M54 |
| Performa MEREC | LN(1 + jumlah ABS(LN(n_ij))/n) | B58:O71 |
| Performa tanpa kriteria j | Keluarkan suku j; pembagi tetap n (12 pada data awal) | B75:M88 |
| Efek dan bobot | E_j = jumlah ABS(S'_ij - S_i); w_j = E_j / jumlah E | B92:N107 |
| AAI dan AI | AAI: terburuk; AI: terbaik menurut Cost/Benefit | B112:M127 |
| Normalisasi MARCOS | Benefit: x/AI; Cost: AI/x | B131:M146 |
| Matriks terbobot | v_ij = normalisasi MARCOS × bobot MEREC; S_i = jumlah v_ij | B150:N165 |
| Utilitas MARCOS | K-, K+, f(K), lalu ranking menurun | B169:H182 |
| Agregasi grup | Jumlah (skor MARCOS tiap DM × bobot DM) | Rekap!H27:I40 |

Bobot kriteria dihitung oleh MEREC **per DM** dan dipakai oleh MARCOS DM yang sama. Bobot pengambil keputusan baru digunakan untuk menjumlahkan skor akhir DM. Tidak ada pembulatan di tengah perhitungan atau normalisasi otomatis bobot DM. Nilai seri mengikuti `RANK` Excel.

Setelah struktur alternatif/kriteria/DM berubah, rumus yang sama bekerja dengan dimensi dan `n` baru. Template Excel awal tidak menyediakan alamat sel pembanding untuk struktur baru. Simpan struktur dinamis melalui JSON; impor XLSX hanya mendukung tata letak awal 14 × 12 × 3.

## Berkas proyek

- `app.py`: UI Streamlit dan alur peran.
- `store.py`: akun, pembatasan akses, serta penyimpanan SQLite bersama.
- `engine.py`: perhitungan MEREC-MARCOS dan ranking.
- `project_ops.py`: perubahan struktur dan catatan grup.
- `workbook_io.py`: impor XLSX/JSON dan ekspor hasil.
- `PANDUAN_INSTALASI.md`: panduan instalasi dan menjalankan aplikasi.

Uji seluruh model, akses, dan UI:

```bash
.venv/bin/python -m unittest discover -s tests -v
```
