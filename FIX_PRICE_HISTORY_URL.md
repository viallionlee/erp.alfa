# Fix: Price History URL - 404 Error

## 🐛 Masalah

**Error:** Page not found (404)
**URL Accessed:** `http://localhost:8000/purchasing/price-history/?sku=CIP46I1RGM`
**Error Message:** "The current path, purchasing/price-history/, didn't match any of these."

---

## 🔍 Root Cause

### Masalah Routing

**Di `erp_alfa/urls.py`:**
```python
path('purchaseorder/', include('purchasing.urls')),  ← Prefix adalah 'purchaseorder/'
```

**Di `purchasing/urls.py`:**
```python
path('price-history/', views.price_history, name='price_history'),
```

**URL yang benar seharusnya:**
```
http://localhost:8000/purchaseorder/price-history/?sku=...
                      ^^^^^^^^^^^^^^  ← Prefix benar
```

**Tapi di template ada hardcoded URL yang salah:**
```
http://localhost:8000/purchasing/price-history/?sku=...
                      ^^^^^^^^^^  ← SALAH! (should be 'purchaseorder')
```

---

## ✅ Perbaikan yang Dibuat

### 1. **products/index.html** (Line 689)

**Before:**
```javascript
const historyUrl = `/purchasing/price-history/?sku=${row.sku}`;  ❌ SALAH
```

**After:**
```javascript
const historyUrl = `/purchaseorder/price-history/?sku=${row.sku}`;  ✅ BENAR
```

---

### 2. **products/edit_product.html** (Line 9)

**Before:**
```html
<a href="/purchasing/price-history/?sku={{ product.sku }}" ...>  ❌ SALAH
```

**After:**
```html
<a href="{% url 'purchasing:price_history' %}?sku={{ product.sku }}" ...>  ✅ BENAR
```

**Keuntungan pakai `{% url %}`:**
- ✅ Dynamic - Tidak perlu hardcode URL
- ✅ Safe - Otomatis update jika URL pattern berubah
- ✅ Best Practice - Django recommendation

---

## 🧪 Test Cases

### Test 1: Dari Product List (Desktop)

**Steps:**
1. Buka `/products/`
2. Lihat kolom "Harga Beli" dengan icon grafik 📊
3. Klik icon grafik

**Expected:**
- ✅ Redirect ke: `http://localhost:8000/purchaseorder/price-history/?sku=...`
- ✅ Halaman price history muncul (TIDAK 404)
- ✅ Data history harga ditampilkan

---

### Test 2: Dari Edit Product

**Steps:**
1. Buka `/products/edit/31815/`
2. Klik tombol "📊 History Harga" di header

**Expected:**
- ✅ Redirect ke: `http://localhost:8000/purchaseorder/price-history/?sku=CIP46I1RGM`
- ✅ Halaman price history muncul (TIDAK 404)
- ✅ Data history harga untuk SKU CIP46I1RGM ditampilkan

---

## 🔧 URL Mapping Lengkap

### Main URLs (`erp_alfa/urls.py`)
```python
path('purchaseorder/', include('purchasing.urls')),
```

### Purchasing URLs (`purchasing/urls.py`)
```python
path('price-history/', views.price_history, name='price_history'),
```

### Combined Full URL
```
/purchaseorder/ + price-history/
= /purchaseorder/price-history/
```

### Named URL (Best Practice)
```django
{% url 'purchasing:price_history' %}?sku=XXX
```

Generates:
```
/purchaseorder/price-history/?sku=XXX
```

---

## 📋 URL Patterns Summary

| App | Prefix | Example | Named URL |
|-----|--------|---------|-----------|
| Products | `/products/` | `/products/` | `products:index` |
| Inventory | `/inventory/` | `/inventory/` | `inventory:stock_list` |
| Purchasing | `/purchaseorder/` | `/purchaseorder/` | `purchasing:po_list` |
| Finance | `/finance/` | `/finance/` | `finance:dashboard` |

**Note:** Purchasing app menggunakan prefix **`purchaseorder/`** bukan `purchasing/`!

---

## 🚨 Common Mistakes

### ❌ Wrong (Hardcoded dengan prefix salah)
```html
<a href="/purchasing/price-history/?sku=...">
```

### ❌ Wrong (Hardcoded prefix benar tapi tidak dynamic)
```html
<a href="/purchaseorder/price-history/?sku=...">
```

### ✅ Correct (Dynamic dengan Django URL tag)
```html
<a href="{% url 'purchasing:price_history' %}?sku=...">
```

---

## 🔍 How to Find Similar Issues

### Search for hardcoded URLs:
```bash
grep -r "href=\"/purchasing/" templates/
```

### Better: Use Django URL tags everywhere
```django
{% url 'app_name:view_name' %}
```

---

## ✅ Verification Checklist

After fix:
- [x] Update `products/index.html` - Line 689
- [x] Update `products/edit_product.html` - Line 9
- [ ] Test dari product list → Click icon history
- [ ] Test dari edit product → Click button "History Harga"
- [ ] Verify page loads (not 404)
- [ ] Verify data displays correctly

---

## 🎯 Summary

### Root Issue:
- ❌ Hardcoded URL menggunakan `/purchasing/` instead of `/purchaseorder/`
- ❌ Prefix salah karena app name ≠ URL prefix

### Fix Applied:
- ✅ Change hardcoded URL di 2 templates
- ✅ Use correct prefix `/purchaseorder/`
- ✅ Use Django `{% url %}` tag (best practice)

### Lesson Learned:
- ✅ Always use `{% url %}` tag instead of hardcoded paths
- ✅ Check URL prefix di `erp_alfa/urls.py` untuk setiap app
- ✅ App name tidak selalu sama dengan URL prefix

---

## 📝 Related URLs

| URL | Status | Used For |
|-----|--------|----------|
| `/purchaseorder/price-history/?sku=XXX` | ✅ Working | Price history page |
| `/purchasing/price-history/?sku=XXX` | ❌ 404 Error | Wrong prefix |
| `/purchaseorder/` | ✅ Working | PO List |
| `/purchaseorder/purchase/` | ✅ Working | Purchase List |


