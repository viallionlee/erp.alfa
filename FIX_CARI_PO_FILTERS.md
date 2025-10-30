# Fix: Cari PO Filters - Desktop & Mobile

## 🐛 Masalah yang Ditemukan

### 1. Desktop Purchase Edit
- ❌ Tidak filter by supplier → Semua PO muncul
- ❌ Tidak filter by status → Received & Verified juga muncul

### 2. Mobile Purchase Edit
- ❌ Filter by supplier tapi tidak filter by status
- ❌ Kolom status tidak tampil valuenya (kosong)

### 3. API Endpoint
- ✅ API `/purchaseorder/data/` sudah support filter `supplier_id` dan `status`
- ❌ Tapi tidak digunakan dengan benar oleh frontend

---

## ✅ Perbaikan yang Dibuat

### Desktop Purchase Edit (`purchase_edit.html`)

**Before:**
```javascript
function loadPOList(keyword, searchType = 'supplier') {
    $.getJSON('/purchaseorder/data/', {
        search: keyword,
        search_type: searchType
    }, function(response) {
        // No supplier_id filter
        // No status filter
    });
}
```

**After:**
```javascript
function loadPOList(keyword, searchType = 'supplier') {
    const supplierId = $('#supplier_id').val();
    
    $.getJSON('/purchaseorder/data/', {
        search: keyword,
        search_type: searchType,
        supplier_id: supplierId,  // ✅ Filter by selected supplier
        length: 100
    }, function(response) {
        // ✅ Filter only draft and pending
        let filteredData = response.data.filter(function(po) {
            const status = po.status ? po.status.toLowerCase() : '';
            return status === 'draft' || status === 'pending';
        });
        
        // ✅ Console log untuk debugging
        console.log('[Desktop Purchase Edit] Total PO:', response.data.length);
        console.log('[Desktop Purchase Edit] Filtered PO (draft/pending):', filteredData.length);
    });
}
```

**Changes:**
1. ✅ Ambil `supplier_id` dari form
2. ✅ Kirim `supplier_id` ke API
3. ✅ Filter response hanya draft & pending
4. ✅ Tambah console log
5. ✅ Update message: "Tidak ada PO (Draft/Pending) ditemukan"

---

### Mobile Purchase Edit (`mobile_purchase_edit.html`)

**Before:**
```javascript
function loadPOList(supplierId) {
    $.getJSON('/purchaseorder/data/', {
        supplier_id: supplierId,
        search_type: 'supplier'
    }, function(response) {
        response.data.forEach(function(po) {
            // No status filter
            // Status badge: Draft, Pending, Received (all shown)
        });
    });
}
```

**After:**
```javascript
function loadPOList(supplierId) {
    $.getJSON('/purchaseorder/data/', {
        supplier_id: supplierId,
        search_type: 'supplier',
        length: 100
    }, function(response) {
        // ✅ Filter only draft and pending
        let filteredData = response.data.filter(function(po) {
            const status = po.status ? po.status.toLowerCase() : '';
            return status === 'draft' || status === 'pending';
        });
        
        filteredData.forEach(function(po) {
            const status = po.status ? po.status.toLowerCase() : '';
            
            // ✅ Status badge now shows value!
            let statusBadge = '';
            if (status === 'draft') {
                statusBadge = '<span class="badge bg-warning">Draft</span>';
            } else if (status === 'pending') {
                statusBadge = '<span class="badge bg-info">Pending</span>';
            }
            
            html += `
                <tr>
                    <td>${po.nomor_po || '-'}</td>
                    <td>${po.tanggal_po || '-'}</td>
                    <td>${statusBadge}</td>  <!-- ✅ Now shows badge! -->
                    <td>...</td>
                </tr>
            `;
        });
    });
}
```

**Changes:**
1. ✅ Filter response hanya draft & pending
2. ✅ Status badge sekarang muncul (Draft/Pending)
3. ✅ Badge color: Draft (warning/kuning), Pending (info/biru)
4. ✅ Tambah console log
5. ✅ Update message: "Tidak ada PO (Draft/Pending) untuk supplier ini"
6. ✅ Handle null values: `po.nomor_po || '-'`

---

## 📊 Comparison: Before vs After

### Desktop

| Aspect | Before | After |
|--------|--------|-------|
| Filter Supplier | ❌ No | ✅ Yes (`supplier_id`) |
| Filter Status | ❌ No | ✅ Yes (Draft/Pending only) |
| Show Received PO | ✅ Yes | ❌ No (filtered out) |
| Show Verified PO | ✅ Yes | ❌ No (filtered out) |
| Console Log | ❌ No | ✅ Yes |

### Mobile

| Aspect | Before | After |
|--------|--------|-------|
| Filter Supplier | ✅ Yes | ✅ Yes |
| Filter Status | ❌ No | ✅ Yes (Draft/Pending only) |
| Show Status Value | ❌ Empty | ✅ Badge visible |
| Status Colors | ❌ N/A | ✅ Warning/Info |
| Console Log | ❌ No | ✅ Yes |

---

## 🧪 Test Cases

### Test 1: Desktop - Filter by Supplier

**Steps:**
1. Buka purchase edit (desktop)
2. Pilih supplier "111"
3. Klik "Cari PO"

**Expected:**
- ✅ Hanya PO dari supplier "111" yang muncul
- ✅ Hanya PO dengan status Draft/Pending
- ✅ PO Received/Verified tidak muncul
- ✅ Console log: Total & Filtered count

**Console Output:**
```
[Desktop Purchase Edit] Total PO: 10
[Desktop Purchase Edit] Filtered PO (draft/pending): 3
```

---

### Test 2: Mobile - Filter by Supplier & Status

**Steps:**
1. Buka mobile purchase edit
2. Pilih supplier "111"
3. Klik "🔍 Cari PO"

**Expected:**
- ✅ Modal muncul
- ✅ Hanya PO dari supplier "111"
- ✅ Hanya status Draft/Pending
- ✅ Kolom Status menampilkan badge
- ✅ Draft = badge kuning
- ✅ Pending = badge biru
- ✅ Console log muncul

**Visual Check:**
```
Nomor PO          | Tanggal           | Status    | Aksi
------------------|-------------------|-----------|-------
PO-20251029-0001  | 29-10-2025 17:29  | [Draft]   | Pilih
PO/20251018/0007  | 18-10-2025 10:27  | [Pending] | Pilih
```

**Console Output:**
```
[Mobile Purchase Edit] Total PO: 10
[Mobile Purchase Edit] Filtered PO (draft/pending): 2
```

---

### Test 3: Supplier Tanpa PO Draft/Pending

**Steps:**
1. Pilih supplier yang hanya punya PO Received/Verified
2. Klik "Cari PO"

**Expected Desktop:**
- ✅ Message: "Tidak ada PO (Draft/Pending) ditemukan"

**Expected Mobile:**
- ✅ Message: "Tidak ada PO (Draft/Pending) untuk supplier ini"

---

### Test 4: Pilih PO Draft

**Steps:**
1. Pilih supplier
2. Pilih PO dengan status "Draft"
3. Check produk ditambahkan

**Expected:**
- ✅ PO bisa dipilih
- ✅ Produk ter-load
- ✅ Field Nomor PO terisi
- ✅ Alert: "PO berhasil dimuat!"

---

### Test 5: Pilih PO Pending

**Steps:**
1. Pilih supplier
2. Pilih PO dengan status "Pending"
3. Check produk ditambahkan

**Expected:**
- ✅ PO bisa dipilih
- ✅ Produk ter-load
- ✅ Field Nomor PO terisi
- ✅ Alert: "PO berhasil dimuat!"

---

## 🔍 Debug Commands

### Desktop
```javascript
// Check supplier selected
$('#supplier_id').val()

// Check PO list loaded
$('#po_list_tbody tr').length

// Check filter applied
// Should see console logs
```

### Mobile
```javascript
// Check supplier selected
$('select[name="supplier_id"]').val()

// Check PO list loaded
$('#po_list_tbody tr').length

// Check status badges visible
$('#po_list_tbody .badge').length  // Should > 0
```

---

## 🎯 Business Rules

### Status Filter Rules
**Allowed for Tarik PO:**
- ✅ Draft - Boleh ditarik
- ✅ Pending - Boleh ditarik

**Not Allowed:**
- ❌ Received - Sudah diterima, tidak boleh ditarik lagi
- ❌ Verified - Sudah diverifikasi, tidak boleh ditarik lagi

**Reason:**
- PO yang sudah Received/Verified kemungkinan sudah diproses
- Untuk menghindari duplikasi purchase dari PO yang sama
- Maintain data integrity

---

## 🚨 Breaking Changes

### None!
Tidak ada breaking changes karena:
- ✅ API endpoint sama
- ✅ Parameter backward compatible
- ✅ Hanya menambah filter (tidak mengubah existing behavior)
- ✅ User yang tidak pilih supplier masih dapat alert

---

## ✅ Checklist

### Desktop
- [x] Filter by supplier_id
- [x] Filter hanya Draft/Pending
- [x] Console log untuk debugging
- [x] Update message "tidak ada data"
- [x] Test dengan berbagai supplier
- [x] Test dengan supplier tanpa PO

### Mobile
- [x] Filter by supplier_id (already working)
- [x] Filter hanya Draft/Pending
- [x] Tampilkan status badge
- [x] Badge colors correct
- [x] Console log untuk debugging
- [x] Update message "tidak ada data"
- [x] Test dengan berbagai supplier
- [x] Test status badge muncul

---

## 📝 Notes

1. **API tidak diubah** - Semua perubahan di frontend saja
2. **Filtering di frontend** - Filter status dilakukan di JavaScript setelah dapat response
3. **Alternative**: Bisa juga tambah parameter `status=draft,pending` di API call, tapi ini lebih flexible
4. **Performance**: Filter di frontend OK karena jumlah PO per supplier biasanya tidak terlalu banyak
5. **Consistency**: Desktop dan mobile sekarang menggunakan logic yang sama

---

## 🎉 Summary

### Fixed Issues:
1. ✅ Desktop sekarang filter by supplier
2. ✅ Desktop hanya show Draft/Pending PO
3. ✅ Mobile hanya show Draft/Pending PO
4. ✅ Mobile status badge sekarang visible
5. ✅ Consistency antara desktop & mobile

### Improved:
1. ✅ Tambah console log untuk debugging
2. ✅ Better error messages
3. ✅ Handle null values
4. ✅ Badge colors yang jelas

### No Changes Needed:
1. ✅ API endpoint (sudah support filters)
2. ✅ Database schema
3. ✅ Backend views


