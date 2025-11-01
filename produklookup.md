# PRODUK LOOKUP V2 - AI IMPLEMENTATION GUIDE

## AI_INSTRUCTIONS
This file contains implementation rules for Product Lookup V2. Follow ALL rules exactly. Use as reference for all product lookup implementations.

---

## MANDATORY_RULES

### REQUIRED_IMPLEMENTATION:
- Vanilla JavaScript (NO jQuery) - MANDATORY
- Fetch API for AJAX - MANDATORY  
- Debouncing 300ms - MANDATORY
- Loading state prevention - MANDATORY
- Photo integration with zoom - MANDATORY
- Keyboard navigation - MANDATORY
- JSON.stringify/parse data management - MANDATORY
- Duplicate prevention - MANDATORY
- Click outside to close - MANDATORY
- Stock display quantity_ready_virtual - MANDATORY
- Photo URL validation (empty if file doesn't exist) - MANDATORY
- Variant produk in API response - MANDATORY
- Font-size 0.8rem for dropdown - MANDATORY
- Row height 90px minimum - MANDATORY
- Photo size 90x90px (all places) - MANDATORY
- Fallback icon bi-file-image (32px) - MANDATORY
- Magnifier icon 24x24px - MANDATORY
- Container width 1065px maximum - MANDATORY
- Column widths: Photo 120px, Kode Produk 180px, Detail Produk flexible, Stock 120px, Harga Beli 120px - MANDATORY
- Header alignment: Center - MANDATORY
- Data alignment: SKU/Barcode/Nama/Variant left, Brand right, Stock/Harga center, Subtotal right - MANDATORY

---

## DEBOUNCING_IMPLEMENTATION

### CRITICAL_PREVENT_DROPDOWN_AUTO_SHOW:
```javascript
// MANDATORY: Global state
let searchTimeout = null;
let isSearching = false;

// MANDATORY: Input event with debouncing
document.getElementById('produk_search').addEventListener('input', function() {
    let keyword = this.value.trim();
    
    if (searchTimeout) clearTimeout(searchTimeout);
    
    if (!keyword) {
        document.getElementById('search-result-box').style.display = 'none';
        return;
    }
    
    searchTimeout = setTimeout(() => {
        if (!isSearching) {
            searchProdukManual(keyword, renderSearchResultBox);
        }
    }, 300);
});

// MANDATORY: API call with loading state
function searchProdukManual(keyword, callback) {
    if (isSearching) return;
    
    isSearching = true;
    
    fetch(`/inventory/produk-lookup?q=${encodeURIComponent(keyword)}&mode=manual&page_size=1000`)
        .then(response => response.json())
        .then(data => {
            isSearching = false;
            callback(data);
        })
        .catch(error => {
            isSearching = false;
            callback([]);
        });
}
```

### FORBIDDEN_PATTERNS:
```javascript
// FORBIDDEN: No debouncing - dropdown auto shows
document.getElementById('produk_search').addEventListener('input', function() {
    searchProdukManual(keyword, renderSearchResultBox); // Direct API call!
});

// FORBIDDEN: No loading state - multiple API calls
function searchProdukManual(keyword, callback) {
    fetch(...).then(...); // Multiple simultaneous calls!
}
```

---

## SCRIPT_PLACEMENT_RULES

### CORRECT_PLACEMENT:
```html
{% extends 'base.html' %}
{% block content %}
<!-- HTML content -->
{% endblock %}

{% block extra_script %}
<script>
// CORRECT: Script here - jQuery, Bootstrap, SweetAlert2 already loaded
let searchTimeout = null;
let isSearching = false;
// ... JavaScript code
</script>
{% endblock %}
```

### FORBIDDEN_PLACEMENT:
```html
{% extends 'base.html' %}
{% block content %}
<!-- HTML content -->
<script>
// FORBIDDEN: Script here - jQuery may not be loaded!
let searchTimeout = null;
// ... JavaScript code
</script>
{% endblock %}
```

### BASE_HTML_LOADING_ORDER:
```html
<!-- Dependencies loaded first -->
<script src="bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script src="jquery-3.7.0.min.js"></script>
<script src="dataTables.min.js"></script>
<script src="sweetalert2@11"></script>

<!-- {% block extra_script %} here -->
{% block extra_script %}{% endblock %}

<!-- Additional base.html scripts -->
<script src="idle_timer.js"></script>
```

---

## IMPLEMENTATION_CHECKLIST

### CORE_IMPLEMENTATION:
- [ ] Vanilla JavaScript (NO jQuery)
- [ ] Fetch API for AJAX
- [ ] Debouncing 300ms with searchTimeout
- [ ] Loading state prevention with isSearching flag
- [ ] JSON.stringify/parse data management
- [ ] Duplicate prevention check existing row
- [ ] Click outside to close event listener

### VISUAL_FEATURES:
- [ ] Photo display 90x90px (all places) with object-fit cover
- [ ] Magnifier icon with hover effect (24x24px)
- [ ] Zoom modal Bootstrap modal
- [ ] Fallback icon bi-file-image for no photo (32px)
- [ ] Container width 1065px maximum - MANDATORY
- [ ] Column widths properly set (Photo 120px, Kode Produk 180px, Detail Produk flexible, Stock 120px, Harga Beli 120px) - MANDATORY
- [ ] Kode Produk: 2 rows (SKU + Barcode) - MANDATORY
- [ ] Detail Produk: 2 rows (Nama + Variant & Brand) - MANDATORY
- [ ] Header alignment: Center - MANDATORY
- [ ] Data alignment: SKU/Barcode/Nama/Variant left, Brand right, Stock/Harga center, Subtotal right - MANDATORY
- [ ] Responsive dropdown width follows form input
- [ ] Dropdown height 600px (STANDARD) - MANDATORY max-height: 600px
- [ ] Row height 90px minimum - MANDATORY
- [ ] Font-size 0.8rem for dropdown table - MANDATORY

### USER_EXPERIENCE:
- [ ] Keyboard navigation (Arrow keys + Enter + Escape)
- [ ] Loading state flag prevents multiple calls
- [ ] Progressive loading (20 items first)
- [ ] Infinite scroll pagination
- [ ] Stock display uses quantity_ready_virtual

### DATA_MANAGEMENT:
- [ ] JSON serialization for form data
- [ ] Photo URL from API response (empty if file doesn't exist)
- [ ] Stock calculation quantity_ready_virtual
- [ ] Variant produk included in API response (MANDATORY)
- [ ] Error handling with try-catch
- [ ] Photo file existence validation before returning URL

### CRITICAL_CHECKS:
- [ ] Dropdown does NOT auto show (has debouncing)
- [ ] NO multiple API calls (has loading state)
- [ ] Photo zoom works (has modal and event handler)
- [ ] Keyboard navigation smooth (has highlight and scroll)
- [ ] Stock display correct (quantity_ready not quantity)
- [ ] Click outside closes dropdown (has event listener)
- [ ] Duplicate prevention (check existing row)
- [ ] Script in {% block extra_script %} (NOT in content)
- [ ] Photo URL validation (empty if file doesn't exist)
- [ ] Variant produk included in API response
- [ ] Dropdown font-size 0.8rem
- [ ] Row height minimum 90px
- [ ] Photo size 90x90px (all places)
- [ ] Fallback icon bi-file-image (not bi-image) with size 32px
- [ ] Magnifier icon 24x24px
- [ ] Container width 1065px maximum
- [ ] Column widths: Photo 120px, Kode Produk 180px, Detail Produk flexible, Stock 120px, Harga Beli 120px
- [ ] Kode Produk: 2 rows (SKU + Barcode)
- [ ] Detail Produk: 2 rows (Nama + Variant & Brand)
- [ ] Header alignment: Center
- [ ] Data alignment: SKU/Barcode/Nama/Variant left, Brand right, Stock/Harga center, Subtotal right

---

## TROUBLESHOOTING_ISSUES

### PROBLEM_DROPDOWN_AUTO_SHOW:
CAUSE: No debouncing
SOLUTION: Add searchTimeout and isSearching flag

### PROBLEM_MODAL_DROPDOWN_NOT_SHOW:
CAUSE: Script in {% block content %} not {% block extra_script %}
SOLUTION: Move script to {% block extra_script %}

### PROBLEM_STOCK_DISPLAY_WRONG:
CAUSE: Using quantity not quantity_ready_virtual
SOLUTION: Use produk.qty_fisik from API or resp.data[0][8]

### PROBLEM_PHOTO_ZOOM_NOT_WORK:
CAUSE: No event handler or modal
SOLUTION: Add photo zoom event listener and modal HTML

### PROBLEM_KEYBOARD_NAV_NOT_SMOOTH:
CAUSE: No highlight class or scrollIntoView
SOLUTION: Add .table-active class and scrollIntoView

### PROBLEM_MULTIPLE_API_CALLS:
CAUSE: No loading state prevention
SOLUTION: Add isSearching flag

### PROBLEM_BROKEN_IMAGE_ICON:
CAUSE: API returns photo URL but file doesn't exist
SOLUTION: Validate photo file existence before returning URL

### PROBLEM_VARIANT_NOT_DISPLAYED:
CAUSE: API doesn't include variant_produk in response
SOLUTION: Add variant_produk field to API response

---

## QUICK_REFERENCE

### MANDATORY_GLOBAL_VARIABLES:
```javascript
let selectedIdx = -1;
let currentRows = [];
let searchTimeout = null; // For debouncing
let isSearching = false; // For prevent multiple API calls
```

### MANDATORY_STYLING_RULES:
```css
/* Container width */
#search-result-box {
    max-height: 600px;
    overflow-y: auto;
    max-width: 1065px;
}

#search-result-box table {
    font-size: 0.8rem;
    width: 100%;
    table-layout: fixed;
}

#search-result-box tbody tr {
    height: 90px;
    min-height: 90px;
}

/* Column widths */
#search-result-box th:nth-child(1),  /* Photo */
#search-result-box td:nth-child(1) {
    width: 120px;
}

#search-result-box th:nth-child(2),  /* Kode Produk */
#search-result-box td:nth-child(2) {
    width: 180px;
}

#search-result-box th:nth-child(3),  /* Detail Produk - Flexible */
#search-result-box td:nth-child(3) {
    width: auto;
    max-width: none;
}

#search-result-box th:nth-child(4),  /* Stock */
#search-result-box td:nth-child(4) {
    width: 120px;
}

#search-result-box th:nth-child(5),  /* Harga Beli */
#search-result-box td:nth-child(5) {
    width: 120px;
}

/* Header alignment - Center */
#search-result-box th {
    text-align: center;
}

/* Kode Produk - 2 rows (SKU + Barcode) */
#search-result-box td:nth-child(2) {
    vertical-align: middle;
    padding: 8px;
    text-align: left;
}
#search-result-box td:nth-child(2) .sku-row {
    font-weight: 600;
    font-size: 0.85rem;
    color: #0d6efd;
    text-align: left;
}
#search-result-box td:nth-child(2) .barcode-row {
    font-size: 0.75rem;
    color: #6c757d;
    text-align: left;
}

/* Detail Produk - 2 rows (Nama + Variant & Brand) */
#search-result-box td:nth-child(3) {
    vertical-align: middle;
    padding: 8px;
    text-align: left;
}
#search-result-box td:nth-child(3) .nama-row {
    font-weight: 500;
    font-size: 0.85rem;
    margin-bottom: 4px;
    word-wrap: break-word;
    text-align: left;
}
#search-result-box td:nth-child(3) .variant-brand-row {
    font-size: 0.75rem;
    color: #6c757d;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
#search-result-box td:nth-child(3) .variant-text {
    text-align: left;
}
#search-result-box td:nth-child(3) .brand-text {
    font-weight: 500;
    color: #198754;
    margin-left: 8px;
    text-align: right;
}

/* Stock & Harga Beli - Center aligned */
#search-result-box td:nth-child(4),
#search-result-box td:nth-child(5) {
    vertical-align: middle;
    text-align: center;
}

/* Photo sizes */
#search-result-box .product-photo-zoom img {
    width: 90px;
    height: 90px;
    object-fit: cover;
}

/* All photos (dropdown & table) */
.product-photo-zoom img {
    width: 90px;
    height: 90px;
    object-fit: cover;
}

/* Magnifier icon */
.product-photo-zoom .magnifier-icon {
    width: 24px;
    height: 24px;
    font-size: 12px;
}
```

### MANDATORY_CSS_CLASSES:
```css
.table-active { background-color: #e3f2fd !important; }
.product-photo-zoom { position: relative; cursor: pointer; }
.magnifier-icon { /* hover effect */ }
```

### MANDATORY_DROPDOWN_STYLING:
```html
<!-- MANDATORY: Dropdown height 600px, row height 90px, photo 90x90px, container 1065px -->
<div id="search-result-box" class="border rounded mt-1 bg-white shadow-sm" 
     style="display:none; position:absolute; z-index:10; min-width:100%; max-width:1065px; overflow-x:auto; max-height:600px; overflow-y:auto;">
  <table class="table table-sm mb-0" style="font-size:0.8rem; width:100%; table-layout:fixed;">
    <thead>
      <tr style="background:#f8f9fa;">
        <th style="width:120px; text-align:center;">Photo</th>
        <th style="width:180px; text-align:center;">Kode Produk</th>
        <th style="width:auto; text-align:center;">Detail Produk</th>
        <th style="width:120px; text-align:center;">Stock</th>
        <th style="width:120px; text-align:center;">Harga Beli</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>
</div>
```

**CRITICAL RULES:**
- `max-height: 600px` - MANDATORY for dropdown
- `font-size: 0.8rem` - MANDATORY for table text
- `row height: 90px` - MANDATORY minimum
- `photo size: 90x90px` - MANDATORY for all places (dropdown & table)
- `container width: 1065px` - MANDATORY maximum width
- `table-layout: fixed` - MANDATORY for consistent column widths

**COLUMN WIDTH RULES:**
- Photo: 120px (fixed)
- Kode Produk: 180px (fixed)
  - Row 1: SKU (left aligned, bold, blue)
  - Row 2: Barcode (left aligned, small, gray)
- Detail Produk: Auto (flexible, fills remaining space)
  - Row 1: Nama Produk (left aligned, bold)
  - Row 2: Variant (left aligned) + Brand (right aligned, green)
- Stock: 120px (fixed, center aligned)
- Harga Beli: 120px (fixed, center aligned)

**CALCULATION:**
- Fixed columns: 120 + 180 + 120 + 120 = 540px
- Detail Produk: 1065 - 540 = 525px (flexible)

**ALIGNMENT RULES:**
- Header: Center aligned (all columns)
- Photo: Center aligned
- SKU: Left aligned
- Barcode: Left aligned
- Nama Produk: Left aligned
- Variant: Left aligned
- Brand: Right aligned (green color)
- Stock: Center aligned
- Harga Beli: Center aligned
- Subtotal: Right aligned

### API_ENDPOINTS:
- Product Search: `/inventory/produk-lookup?q=keyword&mode=manual&page_size=1000`
- Stock Data: `/inventory/data/?columns=[{search:{value:sku}}]`
- Index 8 = quantity_ready (ready stock)

### API_PHOTO_URL_VALIDATION:
```python
# MANDATORY: Check if photo file exists before returning URL
photo_url = ''
if p.photo:
    try:
        # Check if file exists
        if p.photo.storage.exists(p.photo.name):
            photo_url = p.photo.url
    except:
        pass

# Return empty string if photo not exists
# JavaScript will show fallback icon
```

**CRITICAL:** Always return empty string if photo file doesn't exist!
- ❌ FORBIDDEN: Return URL if file doesn't exist (causes broken image icon)
- ✅ CORRECT: Return empty string if file doesn't exist (shows fallback icon)

### API_RESPONSE_DATA:
```javascript
{
    "sku": "PROD001",
    "barcode": "1234567890",
    "nama_produk": "Product Name",
    "variant_produk": "Variant Name",  // MANDATORY - include variant
    "brand": "Brand Name",
    "harga_beli": 10000,
    "photo_url": "",  // Empty if no photo
    "stock_qty": 50
}
```

**MANDATORY FIELDS:**
- `sku` - Product SKU
- `barcode` - Product barcode
- `nama_produk` - Product name
- `variant_produk` - Product variant (MANDATORY)
- `brand` - Product brand
- `harga_beli` - Purchase price
- `photo_url` - Photo URL (empty if no photo)
- `stock_qty` - Stock quantity

---

## AI_SUMMARY

This file contains MANDATORY rules for Product Lookup V2 implementation.
Use checklist above to ensure ALL features implemented correctly.

**CRITICAL FOCUS AREAS:**
1. **Debouncing & Script Placement** - Prevent dropdown auto-show and jQuery loading issues
2. **Photo URL Validation** - Always validate file existence before returning URL
3. **Variant Produk** - MUST include variant_produk in API response
4. **Styling Rules** - Font-size 0.8rem, row height 90px, photo 90x90px (all places), container 1065px
5. **Fallback Icon** - Use bi-file-image (not bi-image) for products without photo (32px)
6. **Container & Column Widths** - Container 1065px max, Column widths: Photo 120px, Kode Produk 180px, Detail Produk flexible, Stock 120px, Harga Beli 120px
7. **Column Layout** - Kode Produk: 2 rows (SKU + Barcode), Detail Produk: 2 rows (Nama + Variant & Brand)
8. **Alignment** - Header center, SKU/Barcode/Nama/Variant left, Brand right, Stock/Harga center, Subtotal right

---

## END_OF_AI_GUIDE