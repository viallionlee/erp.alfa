# Ringkasan Persyaratan Fungsional (FRD) - mobile_batchitem_detail.html

Dokumen ini menyajikan persyaratan fungsional inti untuk halaman "Detail Item Batch" pada aplikasi mobile ERP_ALFA.

## Tujuan Halaman
Halaman ini berfungsi sebagai antarmuka utama bagi staf gudang untuk memproses item produk dalam sebuah batch, memungkinkan verifikasi, penyesuaian kuantitas, dan pengelolaan foto produk.

## Fungsionalitas Utama:

1.  **Tampilan Informasi Produk:**
    *   Menampilkan detail produk: nama, varian, SKU, barcode, brand.
    *   Menampilkan foto produk (jika tersedia) atau placeholder.
    *   Menampilkan "Jumlah Total" produk yang harus diambil.

2.  **Manajemen Kuantitas Barang:**
    *   Menampilkan "Jumlah Ambil" saat ini dalam form input.
    *   Memungkinkan penambahan, pengurangan, atau pengaturan "Jumlah Ambil" hingga maksimum melalui tombol.
    *   Input kuantitas terkunci secara default dan hanya dapat diubah setelah barcode yang benar dipindai.

3.  **Pemindaian Barcode:**
    *   Menyediakan input untuk pemindaian barcode produk.
    *   Memvalidasi barcode yang dipindai dengan barcode produk yang ditampilkan.
    *   Mengaktifkan input kuantitas jika barcode valid.
    *   Memberikan umpan balik visual dan audio untuk barcode yang valid/tidak valid.

4.  **Pengelolaan Foto Produk:**
    *   Memungkinkan pengguna untuk mengunggah foto baru atau menghapus foto produk yang sudah ada.

5.  **Penyimpanan & Umpan Balik:**
    *   Perubahan pada "Jumlah Ambil" secara otomatis disimpan ke backend via AJAX.
    *   Memberikan umpan balik visual pada input kuantitas (sukses/gagal penyimpanan).
    *   Setelah selesai picking untuk produk, memutar suara sukses, menampilkan konfirmasi, dan mengarahkan kembali ke daftar batch.

6.  **Aksi Halaman:**
    *   Tombol "Save & Back" untuk menyimpan dan kembali.
    *   Tombol "Reload" untuk menyimpan dan memuat ulang halaman.
