# Test: Mobile Purchase Edit - Tarik PO

## 🔧 Perubahan yang Dibuat

### File: `templates/purchasing/mobile_purchase_edit.html`

**Perbaikan:**
1. ✅ Ganti `#product-list` → `#products-list` (container yang benar)
2. ✅ Ganti `addProductToList()` → `tambahProdukKePurchase()` (function yang benar)
3. ✅ Tambah console.log untuk debugging
4. ✅ Set quantity dan harga_beli dari PO ke produk
5. ✅ Panggil `checkProductList()` untuk update counter

**Endpoint yang Digunakan (SAMA dengan Desktop):**
- `/purchaseorder/data/` - List PO by supplier
- `/purchaseorder/{id}/json/` - Detail PO dengan items

---

## 🧪 Test Steps

### Pre-requisites:
1. Sudah ada PO dengan status "draft" atau "pending" di database
2. PO tersebut punya supplier dan minimal 1-2 produk
3. Login dengan user yang punya permission `purchase_warehouse`

---

### Test Case 1: Tarik PO dengan Supplier Sudah Dipilih

**Steps:**
1. Buka mobile browser atau responsive mode
2. Navigate ke Purchase Edit: `/purchaseorder/purchase/{id}/edit/` (id = draft purchase)
3. **Pilih Supplier** dari dropdown (contoh: supplier "111")
4. Klik tombol **"🔍 Cari PO"**
5. Modal "Cari Purchase Order" muncul
6. List PO dari supplier terpilih ditampilkan (cek di table)
7. Klik tombol **"Pilih"** pada salah satu PO (contoh: PO-20251029-0001)
8. Modal tertutup
9. Field "Nomor PO" terisi otomatis dengan nomor PO yang dipilih

**Expected Results:**
- ✅ Modal muncul
- ✅ List PO muncul (tidak kosong)
- ✅ Field "Nomor PO" terisi
- ✅ **Produk dari PO otomatis ditambahkan** ke `#products-list`
- ✅ Product count berubah (contoh: dari "Produk (0)" → "Produk (2)")
- ✅ Alert muncul: "PO berhasil dimuat! 2 produk ditambahkan."
- ✅ Quantity dan harga beli sesuai dengan PO

---

### Test Case 2: Tarik PO Tanpa Pilih Supplier Dulu

**Steps:**
1. Buka mobile purchase edit (draft)
2. **JANGAN pilih supplier** (biarkan kosong)
3. Klik tombol **"🔍 Cari PO"**

**Expected Results:**
- ✅ Alert muncul: "Pilih supplier terlebih dahulu"
- ❌ Modal TIDAK muncul

---

### Test Case 3: Supplier Tidak Punya PO

**Steps:**
1. Buka mobile purchase edit
2. Pilih supplier yang **tidak memiliki PO**
3. Klik tombol "🔍 Cari PO"
4. Modal muncul

**Expected Results:**
- ✅ Modal muncul
- ✅ Table menampilkan: "Tidak ada PO untuk supplier ini"
- ❌ Tidak ada data PO di table

---

### Test Case 4: PO Tidak Punya Produk

**Steps:**
1. Pilih supplier
2. Klik "Cari PO"
3. Pilih PO yang **tidak punya item/produk**

**Expected Results:**
- ✅ Field "Nomor PO" terisi
- ✅ Alert muncul: "PO tidak memiliki produk."
- ✅ Product list tetap kosong (Produk (0))

---

### Test Case 5: Ganti PO yang Sudah Dipilih

**Steps:**
1. Pilih PO pertama (contoh: PO-001, 2 produk)
2. Produk dari PO-001 ditambahkan (Produk (2))
3. Klik "Cari PO" lagi
4. Pilih PO kedua yang berbeda (contoh: PO-002, 3 produk)

**Expected Results:**
- ✅ Product list **di-clear** (produk lama dihapus)
- ✅ Produk dari PO-002 ditambahkan
- ✅ Product count berubah dari (2) → (3)
- ✅ Field "Nomor PO" berubah ke PO-002

---

### Test Case 6: Edit Quantity Setelah Tarik PO

**Steps:**
1. Tarik PO (2 produk ditambahkan)
2. Edit quantity produk pertama (klik tombol + atau -)
3. Edit harga beli (jika ada input field)

**Expected Results:**
- ✅ Quantity bisa diubah
- ✅ Harga beli bisa diubah
- ✅ Changes di-autosave

---

## 🐛 Debug Checklist

Jika masih error, cek hal berikut:

### 1. Check Console Browser (F12)
**Buka Developer Tools → Console, cari:**
- `[Mobile Purchase Edit] PO Data loaded:` → Harus ada log ini
- Error message → Catat error untuk debugging

### 2. Check Network Tab
**Buka Developer Tools → Network:**
- Request ke `/purchaseorder/data/` → Status harus 200 OK
- Request ke `/purchaseorder/{id}/json/` → Status harus 200 OK
- Check response data (preview) → Harus ada items array

### 3. Check HTML Elements
**Buka Developer Tools → Elements:**
```javascript
// Run di console:
$('#products-list').length  // Harus return 1
$('#nomor_po').length       // Harus return 1
$('#po_id').length          // Harus return 1
```

### 4. Check Function Exists
**Run di console:**
```javascript
typeof tambahProdukKePurchase  // Harus return "function"
typeof checkProductList         // Harus return "function"
```

### 5. Manual Test PO API
**Test manual di browser:**
```
http://localhost:8000/purchaseorder/1/json/
```
Response harus JSON dengan struktur:
```json
{
  "id": 1,
  "nomor_po": "PO-20251029-0001",
  "supplier": "Supplier Name",
  "items": [
    {
      "product": {
        "id": 1,
        "sku": "SKU001",
        "nama_produk": "Product Name",
        ...
      },
      "quantity": 10,
      "harga_beli": 50000
    }
  ]
}
```

---

## 🔍 Common Issues & Solutions

### Issue 1: Modal muncul tapi list PO kosong
**Solusi:**
- Check apakah supplier punya PO di database
- Check response API `/purchaseorder/data/` di Network tab
- Pastikan parameter `supplier_id` terkirim dengan benar

### Issue 2: Produk tidak ditambahkan setelah pilih PO
**Solusi:**
- Check console untuk error
- Check apakah `tambahProdukKePurchase()` dipanggil
- Check apakah `#products-list` ada di DOM
- Check response API `/purchaseorder/{id}/json/` ada items

### Issue 3: Alert "Error loading PO data"
**Solusi:**
- Check Network tab untuk error detail
- Check apakah endpoint `/purchaseorder/{id}/json/` accessible
- Check Django logs untuk error backend

### Issue 4: Product count tidak update
**Solusi:**
- Check apakah `checkProductList()` dipanggil
- Check apakah `#product-count` element ada di DOM
- Manual run di console: `checkProductList()`

### Issue 5: Supplier dropdown kosong di modal
**Solusi:**
- Check apakah sudah pilih supplier di form sebelum klik "Cari PO"
- Check apakah `supplier_id` value terisi

---

## ✅ Success Criteria

Test dianggap **BERHASIL** jika:

1. ✅ Modal Cari PO bisa dibuka
2. ✅ List PO muncul berdasarkan supplier
3. ✅ Bisa pilih PO dari list
4. ✅ Field "Nomor PO" terisi otomatis
5. ✅ **Produk dari PO otomatis ditambahkan** ke list
6. ✅ Product count update (Produk (0) → Produk (X))
7. ✅ Alert konfirmasi muncul
8. ✅ Quantity dan harga beli sesuai dengan PO
9. ✅ Bisa edit quantity setelah tarik PO
10. ✅ **Behavior sama dengan desktop** (consistency)

---

## 📊 Comparison: Desktop vs Mobile

| Feature | Desktop | Mobile | Status |
|---------|---------|--------|--------|
| API Endpoint | `/purchaseorder/data/` | `/purchaseorder/data/` | ✅ Same |
| PO Detail API | `/purchaseorder/{id}/json/` | `/purchaseorder/{id}/json/` | ✅ Same |
| Container | `#produk-table tbody` | `#products-list` | ✅ Different (mobile specific) |
| Add Function | `tambahProdukKeTable()` | `tambahProdukKePurchase()` | ✅ Different (mobile specific) |
| Modal Size | `modal-xl` | `modal-lg` | ✅ Mobile optimized |
| Search Type | By Supplier & Nomor PO | By Supplier only | ✅ Simplified for mobile |

---

## 🎯 Next Steps After Success

Setelah test berhasil:
1. ✅ Test di berbagai device mobile (iPhone, Android)
2. ✅ Test di berbagai browser (Chrome, Safari, Firefox)
3. ✅ Test edge cases (PO kosong, supplier tanpa PO, dll)
4. ✅ Update documentation
5. ✅ Deploy ke staging untuk UAT


