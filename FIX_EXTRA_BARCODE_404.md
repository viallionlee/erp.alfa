# Fix: Extra Barcode 404 Error

## 🐛 Masalah

**Error di Console:**
```
GET http://localhost:8000/products/api/extra-ba... 404 (Not Found)
[Extra Barcode] Error: HTTP 404: Not Found
```

**Error di UI:**
```
Gagal memuat extra barcode: HTTP 404: Not Found
```

---

## ✅ Perbaikan yang Dibuat

### 1. **Update `static/js/edit_product.js`**

**Tambahan:**
- ✅ Console log di initialization
- ✅ Check product ID exists
- ✅ Detailed error logging
- ✅ Better error messages

**Code:**
```javascript
document.addEventListener('DOMContentLoaded', function() {
    const extraBarcodeCard = document.getElementById('extra-barcode-card');
    if (!extraBarcodeCard) {
        console.log('[Extra Barcode] Card element not found');
        return;
    }

    const productId = extraBarcodeCard.dataset.productId;
    console.log('[Extra Barcode] Initializing for product ID:', productId);
    
    if (!productId) {
        console.error('[Extra Barcode] Product ID not found');
        return;
    }
    
    // ... rest of code
    
    function loadExtraBarcodes() {
        console.log('[Extra Barcode] Loading for product ID:', productId);
        
        fetch(`/products/api/extra-barcodes/${productId}/`)
            .then(response => {
                console.log('[Extra Barcode] Response status:', response.status);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('[Extra Barcode] Data received:', data);
                // ... display data
            })
            .catch((error) => {
                console.error('[Extra Barcode] Error:', error);
                // ... show error
            });
    }
});
```

---

### 2. **Collect Static Files**

```bash
python manage.py collectstatic --noinput --clear
```

**Result:**
- ✅ Old static files cleared
- ✅ New edit_product.js copied to staticfiles
- ✅ 170 static files collected

---

## 🧪 CARA TEST (PENTING!)

### Step 1: Hard Refresh Browser
```
Ctrl + Shift + R  (Windows/Linux)
Cmd + Shift + R   (Mac)
```

**ATAU:**

Clear browser cache:
```
Ctrl + Shift + Delete → Clear cached images and files
```

---

### Step 2: Reload Page
```
http://localhost:8000/products/edit/31814/
```

---

### Step 3: Check Console (F12)

**Expected Console Output (SUCCESS):**
```javascript
[Extra Barcode] Initializing for product ID: 31814
[Extra Barcode] Loading for product ID: 31814
[Extra Barcode] Response status: 200
[Extra Barcode] Data received: {success: true, extra_barcodes: []}
```

**Expected UI:**
```
Daftar Extra Barcode
┌──────────┬───────┐
│ Barcode  │ Aksi  │
├──────────┴───────┤
│ Tidak ada extra  │  ← Bukan error merah!
│ barcode.         │
└──────────────────┘
```

---

### Step 4: Test Add Extra Barcode

**Steps:**
1. Ketik barcode di input field: `TEST123`
2. Klik tombol "Tambah"

**Expected:**
- ✅ SweetAlert muncul: "Berhasil!"
- ✅ Barcode ditambahkan ke list
- ✅ Input field cleared

---

## 🔍 Debug Checklist

### Check 1: Static File Loaded?

**Open Network Tab (F12):**
1. Filter: `js`
2. Reload page
3. Find: `edit_product.js`
4. Status should be: **200 OK** (not 404)

### Check 2: Product ID Correct?

**Run in Console:**
```javascript
document.getElementById('extra-barcode-card').dataset.productId
// Expected: "31814"
```

### Check 3: API Endpoint Accessible?

**Open in new tab:**
```
http://localhost:8000/products/api/extra-barcodes/31814/
```

**Expected Response:**
```json
{
  "success": true,
  "extra_barcodes": []
}
```

**If you see login page or 403:**
→ User tidak login atau tidak punya permission `products.view_product`

### Check 4: Console Logs?

**After hard refresh, you should see:**
```javascript
[Extra Barcode] Initializing for product ID: 31814
[Extra Barcode] Loading for product ID: 31814
```

**If you DON'T see these logs:**
→ JavaScript file not loaded or old version cached

---

## 🚨 Common Issues & Solutions

### Issue 1: Still 404 after hard refresh

**Solution:**
```bash
# Clear staticfiles and recollect
python manage.py collectstatic --noinput --clear

# Then hard refresh browser: Ctrl+Shift+R
```

### Issue 2: Console shows "Card element not found"

**Solution:**
Check template has:
```html
<div id="extra-barcode-card" data-product-id="{{ product.id }}">
```

### Issue 3: Product ID is undefined

**Solution:**
Check template:
```django
data-product-id="{{ product.id }}"
```
Product object must be passed to template

### Issue 4: 403 Forbidden

**Solution:**
User needs permission: `products.view_product`

Add permission via Django admin:
```
Admin → Users → Select user → User permissions → Add "products | product | Can view product"
```

### Issue 5: CSRF token not found

**Solution:**
Template needs:
```django
{% csrf_token %}
```

---

## 📊 Verification Matrix

| Check | Expected | Status |
|-------|----------|--------|
| Static file exists | `static/js/edit_product.js` | ✅ |
| URL pattern exists | `/products/api/extra-barcodes/<id>/` | ✅ |
| View function exists | `get_product_extra_barcodes()` | ✅ |
| Product exists in DB | Product ID 31814 | ✅ |
| Extra barcodes count | 0 (empty) | ✅ |
| Static files collected | 170 files | ✅ |

---

## 🎯 Quick Test Steps

1. ✅ Hard refresh: `Ctrl + Shift + R`
2. ✅ Open Console: `F12`
3. ✅ Check console logs for `[Extra Barcode]`
4. ✅ Verify no 404 error
5. ✅ UI shows "Tidak ada extra barcode." (not red error)
6. ✅ Try add new barcode
7. ✅ Check if it works

---

## 🔧 Manual API Test

**Test langsung di browser (new tab):**

### Test 1: Get Extra Barcodes
```
http://localhost:8000/products/api/extra-barcodes/31814/
```

**Expected:**
```json
{
  "success": true,
  "extra_barcodes": []
}
```

### Test 2: Add Extra Barcode (via Postman/curl)
```bash
curl -X POST http://localhost:8000/products/api/add-extra-barcode/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: YOUR_CSRF_TOKEN" \
  -d '{"product_id": 31814, "barcode_value": "TEST123"}'
```

**Expected:**
```json
{
  "success": true,
  "message": "Extra barcode berhasil ditambahkan."
}
```

---

## ✅ Success Criteria

Test berhasil jika:

1. ✅ Console log muncul: `[Extra Barcode] Initializing for product ID: 31814`
2. ✅ Response status: 200 (not 404)
3. ✅ Data received: `{success: true, ...}`
4. ✅ UI shows: "Tidak ada extra barcode." (gray text, not red)
5. ✅ No error in console
6. ✅ Bisa tambah extra barcode
7. ✅ Bisa hapus extra barcode

---

## 📝 Summary

### Root Cause:
- Browser cache dengan static file lama
- Static file perlu di-collect ulang

### Fix Applied:
1. ✅ Update edit_product.js dengan detailed logging
2. ✅ Clear and collect static files
3. ✅ Better error messages
4. ✅ Validation for product ID

### Action Required:
1. ⚠️ **HARD REFRESH browser** (Ctrl+Shift+R)
2. ⚠️ **Check console** for logs
3. ⚠️ **Verify** error sudah hilang


