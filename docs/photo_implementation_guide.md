# Panduan Implementasi Foto Produk yang Benar

## Cara Memunculkan Foto Produk di Putaway Mobile

Berdasarkan analisis implementasi yang berhasil di `putaway_mobile.html`, berikut adalah pola yang benar untuk menampilkan foto produk:

### 1. Backend (Django View)

```python
# Di views.py, ambil Product object lengkap untuk mendapatkan foto
for product in products:
    try:
        product_obj = Product.objects.get(id=product['id'])
        photo_url = product_obj.photo.url if product_obj.photo else ''
    except Product.DoesNotExist:
        photo_url = ''
    
    enriched_products.append({
        **product,
        'photo': photo_url,  # Tambahkan photo URL sebagai string
        'suggested_rak': suggested_rak,
        'putaway_by': putaway_by
    })
```

**Key Points:**
- ✅ Mengambil Product object lengkap untuk mendapatkan foto
- ✅ Menggunakan `product_obj.photo.url` untuk mendapatkan URL foto
- ✅ Fallback ke string kosong jika foto tidak ada
- ✅ Menambahkan `photo` ke context sebagai string URL

### 2. Frontend Template

#### CSS Styling:
```css
.product-photo {
    width: 80px;
    height: 100px;
    border-radius: 8px;
    border: 2px solid #e9ecef;
    overflow: hidden;
    background: #f8f9fa;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: transform 0.2s;
}

.product-photo img {
    width: 100%;
    height: auto;
    object-fit: cover;
    border-radius: 6px;
}

.product-photo .no-photo {
    color: #6c757d;
    font-size: 2rem;
}
```

#### HTML Template:
```html
<div class="product-photo" onclick="openPhotoModal('{{ p.photo|default:'' }}', '{{ p.nama_produk }}')">
    {% if p.photo %}
        <img src="{{ p.photo }}" alt="{{ p.nama_produk }}" loading="lazy">
    {% else %}
        <div class="no-photo">
            <i class="bi bi-box"></i>
        </div>
    {% endif %}
</div>
```

**Key Points:**
- ✅ Conditional rendering dengan `{% if p.photo %}`
- ✅ Lazy loading dengan `loading="lazy"`
- ✅ Click handler untuk membuka modal foto
- ✅ Placeholder icon jika foto tidak ada
- ✅ Proper alt text untuk accessibility

### 3. JavaScript Modal

```javascript
function openPhotoModal(photoUrl, productName) {
    if (!photoUrl) {
        alert('Tidak ada foto produk');
        return;
    }
    
    const modal = document.getElementById('photoModal');
    const modalPhoto = document.getElementById('modalPhoto');
    const modalTitle = document.getElementById('modalTitle');
    
    modalPhoto.src = photoUrl;
    modalPhoto.alt = productName;
    modalTitle.textContent = productName;
    
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden'; // Prevent scrolling
}
```

**Key Points:**
- ✅ Validasi foto sebelum menampilkan modal
- ✅ Update src, alt, dan title secara dinamis
- ✅ Prevent body scroll saat modal terbuka

### 4. Modal HTML Structure

```html
<div id="photoModal" class="photo-modal">
    <div class="photo-modal-content">
        <span class="photo-modal-close" onclick="closePhotoModal()">&times;</span>
        <img id="modalPhoto" class="photo-modal-img" src="" alt="">
        <div id="modalTitle" class="photo-modal-title"></div>
    </div>
</div>
```

## Perbedaan dengan Implementasi JavaScript-Only

| Aspek | Template Conditional | JavaScript Conditional |
|-------|---------------------|----------------------|
| **Error Handling** | ✅ Template-level fallback | ❌ Bergantung pada onerror |
| **Performance** | ✅ Rendering langsung | ❌ Perlu JavaScript execution |
| **Accessibility** | ✅ Alt text langsung | ❌ Alt text dinamis |
| **SEO** | ✅ Crawlable | ❌ Tidak crawlable |
| **Reliability** | ✅ Lebih reliable | ❌ Bergantung pada JS |

## Rekomendasi

1. **Gunakan conditional rendering di template level** untuk error handling yang lebih baik
2. **Implementasi lazy loading** untuk performa yang optimal
3. **Consistent styling** dengan ukuran yang sesuai konteks
4. **Proper error handling** dengan fallback yang jelas
5. **Accessibility** dengan alt text yang meaningful

## Contoh Implementasi untuk Modal

Untuk modal daftar putaway, gunakan pola yang sama:

```html
<div class="modal-item-photo" onclick="showPhotoModal('${item.photo}', '${item.nama_produk}')">
    ${item.photo ? 
        `<img src="${item.photo}" alt="${item.nama_produk}" loading="lazy">` : 
        `<div class="no-photo"><i class="bi bi-box"></i></div>`
    }
</div>
```

Pola ini memberikan error handling yang robust, lazy loading untuk performa, dan user experience yang baik.

