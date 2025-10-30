# Debug Guide: Mobile Tarik PO

## 🔧 Perubahan Terbaru

### Major Fix: Direct HTML Generation
**Sebelumnya**: Memanggil `tambahProdukKePurchase()` lalu set quantity/harga
**Sekarang**: Langsung build HTML dengan quantity dan harga_beli dari PO

**Keuntungan:**
- ✅ Lebih reliable (tidak depend ke logic function lain)
- ✅ Quantity dan harga_beli langsung correct dari awal
- ✅ Banyak console.log untuk debugging

---

## 🧪 Step-by-Step Testing

### 1. Buka Browser Console (WAJIB)
**Tekan F12** → Tab **Console**

### 2. Clear Console
Klik icon "Clear console" atau tekan `Ctrl+L`

### 3. Test Tarik PO

#### A. Pilih Supplier
```
1. Pilih supplier dari dropdown (contoh: "111")
2. Check console: tidak ada error
```

#### B. Klik "Cari PO"
```
1. Klik tombol "🔍 Cari PO"
2. Modal muncul
3. Check console: tidak ada error
```

**Expected Console Output:**
```
(Tidak ada log khusus untuk membuka modal)
```

#### C. Pilih PO
```
1. Klik "Pilih" pada salah satu PO
2. Modal tertutup
3. Check console untuk log berikut:
```

**Expected Console Output:**
```javascript
[Mobile Purchase Edit] PO Data loaded: {id: 1, nomor_po: "PO-20251029-0001", ...}
[Mobile Purchase Edit] Items count: 2
[Mobile Purchase Edit] Clearing products list...
[Mobile Purchase Edit] Adding 2 products from PO...
[Mobile Purchase Edit] Processing item 1 : SKU001
[Mobile Purchase Edit] Product data: {id: 1, sku: "SKU001", ...}
[Mobile Purchase Edit] Quantity: 10 Harga Beli: 50000
[Mobile Purchase Edit] Product added to list
[Mobile Purchase Edit] Processing item 2 : SKU002
[Mobile Purchase Edit] Product data: {id: 2, sku: "SKU002", ...}
[Mobile Purchase Edit] Quantity: 5 Harga Beli: 30000
[Mobile Purchase Edit] Product added to list
[Mobile Purchase Edit] Final product count: 2
```

#### D. Verify Results
```
1. Alert muncul: "PO berhasil dimuat! 2 produk ditambahkan."
2. Product count berubah: "Produk (0)" → "Produk (2)"
3. Produk visible di list
4. Quantity sesuai dengan console log
```

---

## 🔍 Detailed Debugging Steps

### Check 1: Supplier Selected?
**Run di Console:**
```javascript
$('select[name="supplier_id"]').val()
```
**Expected:** `"1"` atau ID supplier lain (bukan empty string)
**If empty:** Pilih supplier dulu!

### Check 2: Modal PO Muncul?
**Run di Console:**
```javascript
$('#cariPoModal').hasClass('show')
```
**Expected:** `true`
**If false:** Modal tidak terbuka, check Bootstrap JS loaded

### Check 3: List PO Ada Data?
**Run di Console:**
```javascript
$('#po_list_tbody tr').length
```
**Expected:** > 0
**If 0:** Supplier tidak punya PO atau API error

### Check 4: PO ID Terisi?
**Run di Console setelah pilih PO:**
```javascript
$('#po_id').val()
```
**Expected:** `"1"` atau ID PO lain
**If empty:** Click handler tidak jalan

### Check 5: API Call Success?
**Check Network Tab:**
1. Buka Tab **Network**
2. Filter: `json`
3. Pilih PO
4. Cari request ke `/purchaseorder/1/json/`
5. Status harus **200 OK**
6. Preview response:

```json
{
  "id": 1,
  "nomor_po": "PO-20251029-0001",
  "items": [
    {
      "product": {
        "id": 1,
        "sku": "SKU001",
        "nama_produk": "Product Name"
      },
      "quantity": 10,
      "harga_beli": 50000
    }
  ]
}
```

### Check 6: Products List Container Exists?
**Run di Console:**
```javascript
$('#products-list').length
```
**Expected:** `1`
**If 0:** Container tidak ada, check HTML template

### Check 7: Products Added?
**Run di Console setelah tarik PO:**
```javascript
$('#products-list .compact-added-product').length
```
**Expected:** Sama dengan jumlah items di PO (contoh: 2)
**If 0:** Product tidak ditambahkan, check console untuk error

### Check 8: Quantity Correct?
**Run di Console:**
```javascript
$('#products-list input[name="produk_qty[]"]').map(function() { return $(this).val(); }).get()
```
**Expected:** Array of quantities (contoh: `["10", "5"]`)
**If wrong:** Check item.quantity di PO data

### Check 9: Harga Beli Correct?
**Run di Console:**
```javascript
$('#products-list input[name="produk_harga_beli[]"]').map(function() { return $(this).val(); }).get()
```
**Expected:** Array of prices (contoh: `["50000", "30000"]`)
**If wrong:** Check item.harga_beli di PO data

---

## ❌ Common Errors & Solutions

### Error 1: "Pilih supplier terlebih dahulu"
**Penyebab:** Supplier belum dipilih
**Solusi:** Pilih supplier dari dropdown dulu

### Error 2: Modal tidak muncul
**Penyebab:** Bootstrap JS belum loaded
**Solusi:** 
```javascript
// Check Bootstrap loaded:
typeof bootstrap
// Expected: "object"
```

### Error 3: "Tidak ada PO untuk supplier ini"
**Penyebab:** Supplier tidak punya PO
**Solusi:** 
- Buat PO untuk supplier tersebut di desktop
- Atau pilih supplier lain yang sudah punya PO

### Error 4: Console log: "Error loading PO data"
**Penyebab:** API error
**Solusi:**
1. Check Network tab untuk detail error
2. Check Django logs
3. Pastikan endpoint `/purchaseorder/{id}/json/` accessible

### Error 5: Products tidak muncul tapi console log "Product added"
**Penyebab:** CSS hide atau container salah
**Solusi:**
```javascript
// Check if products hidden:
$('#products-list').is(':visible')
// Expected: true

// Check products-list-body visible:
$('#products-list-body').is(':visible')
// Expected: true
```

### Error 6: Quantity = 1 padahal di PO = 10
**Penyebab:** item.quantity tidak terbaca
**Solusi:** Check console log:
```
[Mobile Purchase Edit] Quantity: undefined
```
Berarti structure PO data salah, check API response

---

## 🎯 Verification Checklist

Setelah tarik PO, verify semua item berikut:

### Visual Check
- [ ] Alert "PO berhasil dimuat!" muncul
- [ ] Product count update (Produk (0) → Produk (X))
- [ ] Produk visible di list (tidak kosong)
- [ ] Foto produk muncul (jika ada)
- [ ] SKU dan nama produk benar
- [ ] Quantity control (-, input, +) ada
- [ ] Tombol hapus (X) ada

### Data Check
- [ ] Field "Nomor PO" terisi
- [ ] Hidden input `po_id` terisi
- [ ] Quantity sesuai dengan PO
- [ ] Harga beli sesuai dengan PO
- [ ] Semua hidden inputs ada:
  - `produk_id[]`
  - `produk_sku[]`
  - `produk_harga_beli[]`

### Console Check
- [ ] Tidak ada error di console
- [ ] Semua console.log muncul sesuai expected
- [ ] Final product count benar

### Functional Check
- [ ] Bisa edit quantity (+ dan -)
- [ ] Bisa hapus produk
- [ ] Bisa simpan purchase
- [ ] Product count update saat hapus

---

## 📊 Test Matrix

| Scenario | Supplier | PO Count | Items | Expected Result |
|----------|----------|----------|-------|-----------------|
| Normal | Selected | 1+ | 2+ | ✅ Success |
| No Supplier | Not Selected | - | - | ⚠️ Alert: Pilih supplier |
| No PO | Selected | 0 | - | ⚠️ Message: Tidak ada PO |
| Empty PO | Selected | 1 | 0 | ⚠️ Alert: Tidak ada produk |
| Large PO | Selected | 1 | 10+ | ✅ Success |
| Replace PO | Selected | 2 | Varies | ✅ Old cleared, new added |

---

## 🚀 Quick Test Script

Copy-paste ke console untuk quick test:

```javascript
// Test 1: Check Environment
console.log('=== Environment Check ===');
console.log('jQuery loaded:', typeof $ !== 'undefined');
console.log('Bootstrap loaded:', typeof bootstrap !== 'undefined');

// Test 2: Check Elements
console.log('=== Elements Check ===');
console.log('Supplier dropdown:', $('select[name="supplier_id"]').length);
console.log('Products list:', $('#products-list').length);
console.log('Nomor PO input:', $('#nomor_po').length);
console.log('PO ID hidden:', $('#po_id').length);

// Test 3: Check Current State
console.log('=== Current State ===');
console.log('Supplier selected:', $('select[name="supplier_id"]').val());
console.log('PO ID:', $('#po_id').val());
console.log('Product count:', $('#products-list .compact-added-product').length);

// Test 4: Manual Trigger
console.log('=== Manual Test ===');
console.log('Run: $("#cari_po_btn").click() to test');
```

---

## ✅ Success Criteria

Test dianggap **BERHASIL** jika semua checklist ini terpenuhi:

1. ✅ Supplier bisa dipilih
2. ✅ Modal Cari PO muncul
3. ✅ List PO ditampilkan
4. ✅ Bisa pilih PO
5. ✅ Field "Nomor PO" terisi
6. ✅ **Console log lengkap muncul**
7. ✅ **Produk ditambahkan ke list**
8. ✅ **Quantity sesuai dengan PO**
9. ✅ **Harga beli sesuai dengan PO**
10. ✅ Product count update
11. ✅ Alert konfirmasi muncul
12. ✅ Tidak ada error di console

---

## 📝 Report Template

Jika masih gagal, kirim info berikut:

```
Browser: Chrome/Firefox/Safari
Device: Desktop/iPhone/Android
URL: /purchaseorder/purchase/XX/edit/

Supplier Selected: Yes/No
Supplier ID: XX

Modal Opened: Yes/No
PO List Shown: Yes/No
PO Selected: Yes/No
PO ID: XX

Console Logs:
[paste console logs here]

Network Errors:
[paste network errors here]

Screenshot:
[attach screenshot]
```


