# Mobile Purchase Edit - Test Checklist

## ✅ Template Features Implemented

### 1. **Auto-Collapse Sections**
- ✅ Info Purchase section collapses when clicking other sections
- ✅ All sections are toggleable (click header to expand/collapse)
- ✅ Chevron icon rotates when collapsed

### 2. **Product Lookup**
- ✅ Search input with debouncing (300ms)
- ✅ Smart positioning (below/above/center viewport)
- ✅ Photo handling with fallback to placeholder
- ✅ Shows SKU, Barcode, Name, Brand, Variant
- ✅ Backdrop for closing dropdown
- ✅ Auto-hide on scroll/resize
- ✅ Click outside to close

### 3. **Add Product to List**
- ✅ Click result to add product
- ✅ Duplicate check (increment qty if exists)
- ✅ Product card with:
  - Photo/placeholder
  - SKU + Barcode
  - Name, Brand, Variant
  - Quantity controls (+/-)
  - Price input
  - Remove button
  - Hidden inputs for form submission

### 4. **Product Count Management**
- ✅ Auto-update product count badge
- ✅ Show/hide empty state message
- ✅ Initial check on page load

### 5. **Quantity Controls**
- ✅ Plus button (increment)
- ✅ Minus button (decrement, min 1)
- ✅ Delegated event handlers for dynamic items

### 6. **Remove Product**
- ✅ Remove button with delegated event handler
- ✅ Update product count after removal
- ✅ Show empty state if no products

### 7. **Sticky Bottom Bar**
- ✅ Fixed position at bottom
- ✅ Two buttons: Draft (gray) and Kirim (green)
- ✅ Form submit using `form="purchase-form"`
- ✅ 80px spacer to prevent overlap

### 8. **CSS Styling**
- ✅ Compact form sections
- ✅ Product cards with gradient backgrounds
- ✅ Photo handling
- ✅ Brand/Variant badges
- ✅ Empty state styling
- ✅ Sticky bar styling

---

## 🧪 Manual Testing Steps

### Test 1: Auto-Collapse Sections
1. Open http://localhost:8000/purchaseorder/purchase/{id}/edit/ in mobile view
2. Click on "Cari Produk" header
3. **Expected:** Info Purchase section should collapse
4. Click on "Info Purchase" header
5. **Expected:** Section should expand
6. Click on "Produk" header
7. **Expected:** Info Purchase should collapse again

### Test 2: Product Lookup
1. Click on "Cari Produk" section to expand
2. Type at least 2 characters in search box
3. **Expected:** Dropdown appears with products
4. **Expected:** Dropdown positioned below input (or above/center if no space)
5. **Expected:** Products show photo or placeholder icon
6. **Expected:** Products show SKU, Barcode, Name, Brand, Variant
7. Click outside dropdown
8. **Expected:** Dropdown closes

### Test 3: Add Product
1. Search for a product
2. Click on a product in results
3. **Expected:** Product added to list
4. **Expected:** Search box cleared
5. **Expected:** Dropdown closes
6. **Expected:** Product count updated
7. **Expected:** Empty state hidden
8. Search for the same product again
9. Click on it again
10. **Expected:** Quantity incremented (not duplicated)

### Test 4: Quantity Controls
1. Add a product to list
2. Click "+" button
3. **Expected:** Quantity increases
4. Click "-" button
5. **Expected:** Quantity decreases
6. Keep clicking "-" until quantity is 1
7. Click "-" again
8. **Expected:** Quantity stays at 1 (minimum)

### Test 5: Remove Product
1. Add a product to list
2. Click remove button (trash icon)
3. **Expected:** Product removed from list
4. **Expected:** Product count updated
5. Remove all products
6. **Expected:** Empty state message appears

### Test 6: Sticky Bottom Bar
1. Scroll down the page
2. **Expected:** Sticky bar stays at bottom
3. Click "Draft" button
4. **Expected:** Form submits with status='draft'
5. Click "Kirim" button
6. **Expected:** Form submits with status='pending'

### Test 7: Form Validation
1. Clear supplier selection
2. Try to submit form
3. **Expected:** Alert "Pilih supplier terlebih dahulu"
4. **Expected:** Form does not submit

---

## 🔍 Code Verification

### JavaScript Functions
```javascript
✅ $(document).ready() - Initialization
✅ Auto-collapse logic
✅ Product search with debouncing
✅ Smart dropdown positioning
✅ hideProductSearch() - Hide dropdown
✅ tambahProdukKePurchase() - Add product
✅ checkProductList() - Update count
✅ Delegated event handlers (plus/minus/remove)
✅ changeQty() - Legacy function
✅ removeProduct() - Legacy function
✅ Form validation
```

### HTML Elements
```html
✅ #info-purchase-header - Collapsible header
✅ #info-purchase-body - Collapsible body
✅ #product-search - Search input
✅ #product-search-results - Dropdown results
✅ #product-search-backdrop - Backdrop
✅ #products-list - Product list container
✅ #product-count - Count badge
✅ #no-product-msg - Empty state
✅ .compact-added-product - Product card
✅ .btn-plus, .btn-minus - Quantity buttons
✅ .btn-remove - Remove button
✅ .sticky-bottom-bar - Sticky bar
```

### CSS Classes
```css
✅ .compact-section-header - Collapsible header
✅ .compact-section-body - Collapsible body
✅ .compact-section-body.collapsed - Hidden state
✅ .compact-search-results - Dropdown
✅ .compact-search-backdrop - Backdrop
✅ .compact-product-item - Search result item
✅ .compact-added-product - Added product card
✅ .compact-added-photo - Product photo
✅ .compact-added-photo-placeholder - Placeholder
✅ .compact-added-row - SKU/Barcode row
✅ .compact-added-name - Product name
✅ .compact-added-brand - Brand badge
✅ .compact-added-variant - Variant badge
✅ .compact-added-qty - Quantity controls
✅ .compact-added-price - Price input
✅ .compact-remove-btn - Remove button
✅ .compact-empty-state - Empty state
✅ .sticky-bottom-bar - Sticky bar
✅ .sticky-btn-secondary - Draft button
✅ .sticky-btn-primary - Kirim button
```

---

## 📝 Notes

### Differences from Inbound Tambah Mobile
1. **Field Names:**
   - Inbound: `nama`, `variant`
   - Purchase: `nama_produk`, `variant_produk`

2. **Hidden Inputs:**
   - Inbound: `produk_sku[]`
   - Purchase: `produk_id[]`, `produk_sku[]`, `produk_qty[]`, `produk_harga[]`

3. **Price Input:**
   - Purchase has editable price input (harga_beli)
   - Inbound does not have price input

4. **Form Submission:**
   - Purchase: Submit to purchase_edit view with status parameter
   - Inbound: Submit to inbound_tambah view

### Backend Requirements
- ✅ `purchasing:search_product` endpoint exists
- ✅ Returns array of products with fields: `sku, barcode, nama_produk, variant_produk, brand, harga_beli, photo_url, stock_qty`
- ✅ `purchase_edit` view handles POST with `produk_id[]`, `produk_qty[]`, `produk_harga[]`

---

## ✅ Test Status

- [ ] Test 1: Auto-Collapse Sections
- [ ] Test 2: Product Lookup
- [ ] Test 3: Add Product
- [ ] Test 4: Quantity Controls
- [ ] Test 5: Remove Product
- [ ] Test 6: Sticky Bottom Bar
- [ ] Test 7: Form Validation

---

## 🎯 Next Steps

1. Open browser and navigate to mobile purchase edit page
2. Test all features manually using the checklist above
3. Verify all expected behaviors
4. Report any issues found

---

**Last Updated:** 2025-01-20
**Status:** Ready for Testing ✅





