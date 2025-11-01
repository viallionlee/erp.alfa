# Panduan AI untuk Proyek

Dokumen ini adalah sumber kebenaran (source of truth) untuk aturan bisnis, logika penting, dan preferensi gaya dalam proyek ini. AI harus merujuk ke file ini sebelum mengerjakan tugas untuk memastikan konsistensi.


important  

**INSTRUKSI UNTUK AI:**  
Sebelum memberikan atau mengirimkan kode, **WAJIB** menyebutkan lokasi file (path dan nama file) dengan jelas menggunakan format:  
`path/to/file.py`  
Tujuannya agar user tidak salah apply dan tahu di mana perubahan harus dilakukan.


---
product di `products` tidak bisa di delete jika `product` di temukan di `inventory_inbounditem` maupun `inventory_outbounditem`
dan di ubah menjadi deactivated
`jangan lupa utk load static , jgn cuma static `

## Pola Desain & Implementasi Umum

Pola-pola berikut adalah pendekatan standar yang harus digunakan di seluruh proyek untuk menjaga konsistensi.

### 1. Pola Tabel Data Modern
Setiap kali diminta untuk membuat tabel data baru, ikuti pedoman berikut untuk meniru gaya "Inventory Index":

- **Struktur HTML:** Bungkus tabel dalam `<div class="card table-container ...">`. Gunakan `<table class="table table-hover w-100">` dengan `id` unik dan header (`<thead>`) yang berisi baris judul dan baris filter (`id="filter-row"`).
- **Gaya CSS:** Salin blok `<style>` dari `templates/inventory/index.html` untuk konsistensi visual.
- **Fungsionalitas JS:** Gunakan DataTables.js, dan tentukan mode `server-side` atau `client-side` berdasarkan volume data.
- **Backend (Server-Side):** Jika menggunakan mode server-side, buat view API khusus untuk menangani permintaan AJAX dari DataTables.

### 2. Pola Hapus Data dengan Konfirmasi
Untuk menghapus item dari tabel secara aman dan interaktif:

1.  **Tombol Hapus adalah Form:** Bungkus setiap tombol "Hapus" dalam `<form>`-nya sendiri dengan `method="POST"`.

    ```html
    <form method="post" action="{% url 'app:delete_view' item.id %}">
        {% csrf_token %}
        <button type="submit">Hapus</button>
    </form>
    ```

2.  **JavaScript Mencegat Form:** Gunakan JavaScript untuk mencegat event `submit` form.
    -   Hentikan pengiriman form (`e.preventDefault()`).
    -   Tampilkan dialog konfirmasi (misalnya, SweetAlert2).
    -   Jika pengguna setuju, kirim form-nya (`form.submit()`).

3.  **View Django Standar:** `View` menangani `POST` biasa, menghapus objek, memberi pesan via `messages`, dan `redirect` kembali.

### 3. Pola Tampilan Mobile (Deteksi Otomatis)
- **Standar:** Gunakan pola deteksi otomatis seperti pada `batchpicking`.
- **Logika:** Dalam satu view yang sama:
    1.  Gunakan satu URL untuk desktop dan mobile.
    2.  Di dalam view, deteksi User-Agent dari `request.META`.
    3.  Tentukan nama file template yang akan dirender berdasarkan hasil deteksi (misalnya, `template.html` untuk desktop, `template_mobile.html` untuk mobile).
- **Contoh:**
    ```python
    def my_view(request):
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        is_mobile = re.search(r'mobile|android|iphone', user_agent)

        if is_mobile:
            template_name = 'app/my_view_mobile.html'
        else:
            template_name = 'app/my_view.html'
        
        context = {} # Siapkan konteks data
        return render(request, template_name, context)
    ```

### 4. Ketergantungan jQuery pada Template Baru
- **Aturan Wajib:** Setiap kali membuat template baru (terutama versi mobile) yang menggunakan sintaks jQuery (`$`), **wajib** untuk menyertakan library jQuery.
- **Implementasi:** Tambahkan tag `<script>` untuk jQuery di dalam `{% block extra_script %}` sebelum script custom lainnya.
    ```html
    {% block extra_script %}
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script>
        // Kode custom yang menggunakan $
        $(document).ready(function() { ... });
    </script>
    {% endblock %}
    ```
- **Alasan:** Lupa menyertakan ini akan menyebabkan error JavaScript `Uncaught ReferenceError: $ is not defined` dan semua script yang bergantung padanya akan gagal.

### 5. Penamaan Block Script di Template
- **Aturan Wajib:** Setiap kali membuat block script di template (untuk custom JavaScript), gunakan nama block yang unik dengan format:
  ```django
  {% block extra_script_[NAMA_HTML] %}
      ... script ...
  {% endblock %}
  ```
  Gantilah `[NAMA_HTML]` dengan nama file HTML (tanpa ekstensi) tempat block tersebut digunakan.
- **Contoh:**
  - Untuk `mobile_batchitem_detail.html` → `{% block extra_script_mobile_batchitem_detail %}`
  - Untuk `mobilebatchpicking_v2.html` → `{% block extra_script_mobilebatchpicking_v2 %}`
- **Alasan:**
  - Menghindari bentrok block antar halaman.
  - Mudah dicari dan di-maintain.
  - Jelas asal-usul script-nya.
- **Catatan:**
  - Jika ingin block script dieksekusi, pastikan parent template juga menyediakan block dengan nama yang sama, atau gunakan `{% block.super %}` jika ingin meng-extend script parent.

### 6. Pola Layout Mobile dengan List.js dan Card
Untuk tampilan daftar di versi mobile yang membutuhkan pencarian dan/atau filter, gunakan `List.js` bersama layout berbasis card (`div` dengan kelas Bootstrap seperti `card`, `list-group`, `list-group-item`).

**Prosedur:**
1.  **Struktur HTML:**
    -   Bungkus daftar item dalam `div` kontainer dengan `id` unik (misalnya `id="[NAMA_KONTENER]ListContainer"`).
    -   Tambahkan input pencarian dengan kelas `class="search form-control"` di dalam kontainer yang sama.
    -   Item-item daftar harus memiliki kelas `class="list"` dan di dalamnya setiap item harus berupa `div` atau elemen lain yang berisi data dengan atribut `data-[nama-data]` (misalnya `data-brand="{{ item.brand }}"`) untuk nilai yang akan difilter, dan elemen dengan kelas yang sesuai untuk `valueNames` List.js (misalnya `<div class="brand">{{ item.brand }}</div>`).
2.  **Integrasi List.js:**
    -   Sertakan library `List.js` dari CDN di dalam `{% block extra_script %}`.
    -   Inisialisasi `List.js` menggunakan ID kontainer dan tentukan `valueNames` yang sesuai untuk kolom yang dapat dicari dan difilter.
    -   Untuk filter dropdown dinamis (misalnya filter brand), isi opsi dropdown menggunakan JavaScript dengan mengambil data unik dari item yang ada di DOM, kemudian terapkan fungsi `List.js filter()` saat pilihan dropdown berubah.
- **Contoh Implementasi:** Lihat `templates/fullfilment/mobilebatchpicking_v2.html` sebagai referensi.

---

### 7. Konfigurasi Media Files untuk Foto Produk
Untuk menampilkan foto produk dengan benar, **WAJIB** mengikuti konfigurasi berikut:

**A. Settings (`erp_alfa/settings.py`):**
```python
# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'  # Pastikan ada forward slash

# Direktori tempat Django akan mencari file statis tambahan
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Direktori tempat file statis dikumpulkan saat deploy
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files (Product Images, etc)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')  # Gunakan os.path.join untuk konsistensi
```

**B. URLs (`erp_alfa/urls.py`):**
```python
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # ... existing urls ...
]

# Serve static and media files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

**C. Template:**
- **Wajib** menggunakan `{% load static %}` di setiap template yang menampilkan foto
- **Struktur folder:** Foto produk harus disimpan di `media/product_photos/`
- **Model field:** Gunakan `ImageField(upload_to='product_photos/')` pada model Product

**D. Troubleshooting:**
1. **Foto tidak muncul:** Restart Django server setelah mengubah konfigurasi
2. **Error 404:** Pastikan folder `media/product_photos/` ada dan berisi file foto
3. **Cache browser:** Clear browser cache (Ctrl+F5) jika foto masih tidak muncul
4. **Test URL:** Akses langsung `http://localhost:8000/media/product_photos/[nama_file].jpg` untuk memastikan file bisa diakses

**E. Upload Foto:**
- **Form:** Gunakan `enctype="multipart/form-data"` pada form upload
- **View:** Handle `request.FILES['photo']` untuk menyimpan foto
- **Template:** Gunakan `{{ product.photo.url }}` untuk menampilkan foto

---

## Aturan Logika Bisnis & Aplikasi Spesifik

Aturan ini berlaku untuk bagian-bagian tertentu dari aplikasi.

### 1. Aturan Navigasi Utama (`base.html`)
- **Standar Penandaan Aktif:** Untuk menentukan link navigasi yang 'active', **selalu** gunakan pengecekan substring pada `request.path`. Contoh: `{% if '/products/' in request.path %}`.
- **Standar Link:** Untuk atribut `href`, gunakan path URL secara langsung (hardcode), contoh: `href="/products/"`. Hindari `{% url %}` untuk navigasi utama karena kurang andal untuk struktur proyek ini.

### 2. Logika "Re-Open Batch" (Aplikasi `fullfilment`)
- **Tujuan:** Mengembalikan batch berstatus `closed` ke `completed` agar bisa diedit lagi.
- **Logika Kritis:** Proses ini **wajib** mengembalikan alokasi stok.
    1.  Cari `BatchItem` terkait.
    2.  Untuk setiap item, tambahkan kuantitasnya kembali ke `quantity_locked` pada model `Stock`.
    3.  Buat entri `StockCardEntry` baru dengan tipe `reopen_batch` untuk mencatat transaksi.
- **Lokasi Kode:** Logika utama ada di fungsi `reopen_batch` dalam `fullfilment/views.py`.

### 3. Menampilkan Data pada Halaman Daftar Versi Mobile
Untuk menampilkan data pada halaman daftar versi mobile (contoh: `inbound_mobile.html`), gunakan metode **Server-Side Rendering (SSR)**.

**Prosedur:**
1.  **View (Python):** Ambil semua data yang diperlukan dari database di dalam view Django. Lakukan semua proses sorting dan filtering di sini.
2.  **Kirim ke Template:** Kirim queryset yang sudah jadi tersebut langsung ke template melalui *context*.
3.  **Template (HTML):** Gunakan perulangan Django (`{% for item in list %}`) untuk menampilkan data. Jangan gunakan JavaScript (`fetch`/AJAX) untuk memuat data utama.

Pendekatan ini sama seperti yang digunakan pada `fullfilment/mobile_index.html` dan terbukti jauh lebih **stabil dan andal** daripada Client-Side Rendering (CSR) untuk halaman daftar sederhana, karena menghindari potensi error JavaScript dan masalah inkonsistensi data. 

Kesalahan `500 (Internal Server Error)` saat memfilter tabel DataTables di `batchorder.html` kemungkinan besar disebabkan oleh penanganan kolom `barcode` yang tidak tepat di backend, karena `barcode` adalah field dari model `Product` yang terkait, bukan langsung dari model `Order`.

Saya telah menganalisis fungsi `stock_data` di `inventory/views.py` sebagai referensi, yang berhasil menangani filter dan sort pada field terkait.

Berdasarkan analisis tersebut, saya akan memberikan perbaikan pada `fullfilment/views.py` (`batchorder_api`) dan `templates/fullfilment/batchorder.html`.

### Perubahan pada `fullfilment/views.py` (`batchorder_api`)

Fokus perbaikan adalah pada daftar `columns` dan logika `filtering` serta `sorting` agar sesuai dengan field terkait `product__barcode`, `product__nama_produk`, `product__variant_produk`, dan `product__brand`.

```python
<code_block_to_apply_changes_from>
```

### Perubahan pada `templates/fullfilment/batchorder.html`

Pastikan definisi kolom DataTables di frontend sesuai dengan urutan field yang Anda kirimkan dari backend di `data.append` pada fungsi `batchorder_api`.

```html
templates/fullfilment/batchorder.html
// ... existing code ...
<script>
$(document).ready(function () {
    var table = $('#batchOrderTable').DataTable({
        "processing": true,
        "serverSide": true,
        "ajax": {
            "url": '/fullfilment/batchorder/{{ nama_batch|urlencode }}/api/',
            "type": "GET",
            "dataSrc": "data"
        },
        "columns": [
            { "data": 0, "title": "ID Pesanan" }, // id_pesanan
            { "data": 1, "title": "SKU" }, // sku
            { "data": 2, "title": "Barcode" }, // KOREKSI: ini sesuai dengan product__barcode
            { "data": 3, "title": "Nama Produk" }, // KOREKSI: ini sesuai dengan product__nama_produk
            { "data": 4, "title": "Variant Produk" }, // KOREKSI: ini sesuai dengan product__variant_produk
            { "data": 5, "title": "Brand" }, // KOREKSI: ini sesuai dengan product__brand
            { "data": 6, "title": "Jumlah", "className": "text-end" }, // jumlah
            { "data": 7, "title": "Order Type" }, // order_type
            { 
                "data": 8, // Ini adalah PK
                "orderable": false, 
                "searchable": false, 
                "className": "text-center",
                "title": "Aksi",
                "render": function (data, type, row) {
                    var orderPk = data;
                    var orderId = row[0]; 
                    var orderSku = row[1]; 

                    // Tombol "Hapus dari Batch"
                    var eraseButton = `<button class="btn btn-warning btn-sm erase-order-btn" 
                                            data-order-id="${orderId}" 
                                            data-order-pk="${orderPk}"
                                            data-order-sku="${orderSku}">
                                        Hapus dari Batch
                                    </button>`;

                    // Tombol "Batalkan Order"
                    var cancelButton = `<button class="btn btn-danger btn-sm cancel-order-btn ms-2" 
                                            data-order-id="${orderId}" 
                                            data-order-pk="${orderPk}"
                                            data-order-sku="${orderSku}">
                                        Batalkan Order
                                    </button>`;
                    
                    return eraseButton + cancelButton;
                }
            }
        ],
        // ... language options ...
    });

    // ... event handlers for erase-order-btn and cancel-order-btn ...
});
</script>
{% endblock %}
```

Mohon terapkan perubahan ini secara manual. Perbaikan ini mengatasi potensi `FieldError` atau `AttributeError` ketika DataTables mencoba memfilter atau mengurutkan pada field `barcode` yang tidak langsung ada di model `Order`, dengan memastikan ia merujuk pada `product__barcode` yang benar. Ini seharusnya mengatasi `500 Internal Server Error` yang Anda alami saat memfilter. 