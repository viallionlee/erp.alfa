# Mobile Purchase List - Info Badges

## ✅ Fitur Baru: Total Items & Total Qty Badges

Menambahkan info badge di setiap purchase card di mobile purchase list yang menampilkan:
1. **Total Item** - Jumlah produk berbeda (jumlah SKU)
2. **Total Qty** - Total quantity semua produk

---

## 📋 Perubahan yang Dibuat

### 1. Backend API (`purchasing/views.py`)

**Function**: `purchase_list_api()`

**Changes:**
```python
# Added prefetch_related for items
queryset = Purchase.objects.select_related(...).prefetch_related('items').order_by('-id')

# Calculate total items and total qty for each purchase
for purchase in page_obj:
    items = purchase.items.all()
    total_items = items.count()  # Jumlah produk berbeda
    total_qty = sum(item.quantity for item in items)  # Total qty
    
    data.append({
        # ... existing fields ...
        'total_items': total_items,  # NEW!
        'total_qty': total_qty,      # NEW!
    })
```

**Benefits:**
- ✅ Efficient query dengan `prefetch_related('items')`
- ✅ Calculate di backend, tidak di frontend
- ✅ Data ready untuk display

---

### 2. Frontend Template (`templates/purchasing/mobile_purchase_list.html`)

#### A. CSS Styling

**New Classes:**
```css
.purchase-card-badges {
    display: flex;
    gap: 5px;
    margin-top: 5px;
    flex-wrap: wrap;
}

.info-badge {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 2px 6px;
    border-radius: 8px;
    font-size: 0.65rem;
    font-weight: 500;
    background: #e7f1ff;  /* Light blue */
    color: #0d6efd;       /* Blue text */
}

.info-badge i {
    font-size: 0.7rem;
}
```

**Design:**
- Light blue background (#e7f1ff)
- Blue text (#0d6efd)
- Small, compact badges
- Flex layout with gap
- Icon + text inline

#### B. HTML Structure

**Added to each purchase card:**
```html
<div class="purchase-card-badges">
    <span class="info-badge">
        <i class="bi bi-box-seam"></i> 2 Item
    </span>
    <span class="info-badge">
        <i class="bi bi-123"></i> 15 Qty
    </span>
</div>
```

**JavaScript:**
```javascript
html += '<div class="purchase-card-badges">';
html += '<span class="info-badge"><i class="bi bi-box-seam"></i> ' + (purchase.total_items || 0) + ' Item</span>';
html += '<span class="info-badge"><i class="bi bi-123"></i> ' + (purchase.total_qty || 0) + ' Qty</span>';
html += '</div>';
```

**Icons:**
- `bi-box-seam` 📦 for Total Items
- `bi-123` 🔢 for Total Qty

---

## 📱 Visual Layout

### Before:
```
┌─────────────────────────────┐
│ PO-001          [Draft]     │
│ Tanggal: 2025-10-29         │
│ Supplier: ABC               │
│─────────────────────────────│
│ Rp 12,221        [👁] [✏]  │
└─────────────────────────────┘
```

### After:
```
┌─────────────────────────────┐
│ PO-001          [Draft]     │
│ Tanggal: 2025-10-29         │
│ Supplier: ABC               │
│ [📦 2 Item] [🔢 15 Qty]    │ ← NEW!
│─────────────────────────────│
│ Rp 12,221        [👁] [✏]  │
└─────────────────────────────┘
```

---

## 🧮 Calculation Logic

### Total Items
**Definition**: Jumlah produk berbeda (distinct SKU)

**Example:**
```
Purchase Items:
- Product A: qty 10
- Product B: qty 5

Total Items = 2  (2 produk berbeda)
```

**Code:**
```python
total_items = items.count()
```

---

### Total Qty
**Definition**: Total quantity semua produk

**Example:**
```
Purchase Items:
- Product A: qty 10
- Product B: qty 5

Total Qty = 15  (10 + 5)
```

**Code:**
```python
total_qty = sum(item.quantity for item in items)
```

---

## 🧪 Test Cases

### Test 1: Purchase Tanpa Item
**Data:**
- Purchase: DRAFT
- Items: 0

**Expected:**
```
[📦 0 Item] [🔢 0 Qty]
```

---

### Test 2: Purchase 1 Item
**Data:**
- Product A: qty 10

**Expected:**
```
[📦 1 Item] [🔢 10 Qty]
```

---

### Test 3: Purchase Multiple Items
**Data:**
- Product A: qty 10
- Product B: qty 5
- Product C: qty 3

**Expected:**
```
[📦 3 Item] [🔢 18 Qty]
```

---

### Test 4: Purchase Large Quantity
**Data:**
- Product A: qty 1000
- Product B: qty 2500

**Expected:**
```
[📦 2 Item] [🔢 3500 Qty]
```

---

## 🎯 Use Cases

### 1. Quick Overview
User dapat langsung lihat berapa banyak produk dan total quantity tanpa perlu buka detail

### 2. Comparison
Mudah compare antar purchase untuk lihat mana yang lebih besar

### 3. Validation
Check apakah jumlah items dan qty sesuai ekspektasi sebelum process

---

## 🔍 Debug Guide

### Check API Response

**Test API manually:**
```
http://localhost:8000/purchaseorder/purchase/api/?page=1
```

**Check JSON response:**
```json
{
  "data": [
    {
      "id": 1,
      "nomor_purchase": "PO-001",
      "total_items": 2,      ← Check this
      "total_qty": 15,       ← Check this
      ...
    }
  ]
}
```

### Check Console Log

**Open browser console (F12):**
```javascript
// Should see data with total_items and total_qty
console.log('[Mobile Purchase List] Processing purchase:', purchase);
```

### Check HTML Output

**Inspect element:**
```html
<div class="purchase-card-badges">
    <span class="info-badge">
        <i class="bi bi-box-seam"></i> 2 Item
    </span>
    <span class="info-badge">
        <i class="bi bi-123"></i> 15 Qty
    </span>
</div>
```

### Manual Test in Console

```javascript
// Get all badges
$('.info-badge').length  // Should > 0

// Get badge text
$('.info-badge').map(function() { 
    return $(this).text(); 
}).get()
// Expected: ["2 Item", "15 Qty", ...]
```

---

## 🎨 Styling Options

### Current Style (Light Blue):
```css
background: #e7f1ff;
color: #0d6efd;
```

### Alternative Styles:

#### Option 1: Green
```css
background: #d1f4e0;
color: #198754;
```

#### Option 2: Orange
```css
background: #ffe8d6;
color: #fd7e14;
```

#### Option 3: Purple
```css
background: #f0eaff;
color: #6f42c1;
```

#### Option 4: Gray
```css
background: #f8f9fa;
color: #6c757d;
```

---

## 📊 Performance Impact

### Before:
```
Query: Purchase.objects.select_related(...)
Items NOT prefetched → N+1 query for each purchase
```

### After:
```
Query: Purchase.objects.select_related(...).prefetch_related('items')
Items prefetched → Single additional query for all items
```

**Result:**
- ✅ More efficient (1 + 1 queries instead of N + 1)
- ✅ Faster page load
- ✅ Better UX

---

## ✅ Checklist

### Backend:
- [x] Add `prefetch_related('items')` to queryset
- [x] Calculate `total_items` for each purchase
- [x] Calculate `total_qty` for each purchase
- [x] Add to API response
- [x] No linter errors

### Frontend:
- [x] Add CSS for `.purchase-card-badges`
- [x] Add CSS for `.info-badge`
- [x] Add HTML structure in JavaScript
- [x] Use Bootstrap icons
- [x] Handle null/undefined values (|| 0)
- [x] No linter errors

### Testing:
- [ ] Test with 0 items
- [ ] Test with 1 item
- [ ] Test with multiple items
- [ ] Test with large quantities
- [ ] Test responsive on various screen sizes
- [ ] Test badge colors readable
- [ ] Test icons display correctly

---

## 🚀 Deployment

### Before Deploy:
1. Test API response includes new fields
2. Test frontend displays badges correctly
3. Test on mobile device (real or emulator)
4. Check performance (query count)

### After Deploy:
1. Monitor API response time
2. Check user feedback
3. Consider adding more info if useful

---

## 🎉 Summary

### Added:
- ✅ `total_items` field in API
- ✅ `total_qty` field in API
- ✅ Info badges in mobile UI
- ✅ Icons for visual clarity
- ✅ Responsive styling

### Benefits:
- ✅ Better UX - Quick overview without opening detail
- ✅ Efficient - Prefetch items to avoid N+1 queries
- ✅ Consistent - Same calculation logic for all
- ✅ Visual - Easy to scan and compare


