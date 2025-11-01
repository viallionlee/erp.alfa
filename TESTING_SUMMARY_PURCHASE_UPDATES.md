# Testing Summary - Purchase Updates

## 📋 List Perubahan yang Perlu Ditest

### 1. ✅ Purchase Verify List - Dynamic Summary Cards
**File**: `purchasing/views.py`, `templates/purchasing/purchase_verify_list.html`

**Test Cases**:
- [ ] Buka `/purchasing/purchase-verify/`
- [ ] Check summary cards menampilkan data awal
- [ ] Klik tab "Verified" → Summary cards harus berubah
- [ ] Klik tab "Belum Verified" → Summary cards harus berubah
- [ ] Pilih date range → Summary cards harus update
- [ ] Pilih supplier → Summary cards harus update
- [ ] Search nomor purchase → Summary cards harus update
- [ ] Switch tab sambil ada filter lain → Semua filter tetap aktif

**Expected Result**: Summary cards selalu dinamis sesuai filter yang dipilih

---

### 2. ✅ Purchase List - Tombol Update (Hapus Verify)
**File**: `templates/purchasing/purchase_list.html`

**Test Cases**:
- [ ] Buka `/purchaseorder/purchase/`
- [ ] Purchase dengan status "draft" → Ada tombol: Detail, Edit, Hapus
- [ ] Purchase dengan status "pending" → Ada tombol: **Receive** (hijau), Detail, Edit, Hapus
- [ ] Purchase dengan status "received" → Ada tombol: Detail, **Edit** (masih boleh!)
- [ ] Purchase dengan status "verified" → Ada tombol: Detail saja (tidak ada Edit/Hapus)
- [ ] ❌ Tidak ada tombol "Verify" sama sekali (sudah dihapus)

**Expected Result**: 
- Tombol "Verify" tidak muncul di purchase list
- Purchase "received" masih bisa di-edit
- Purchase "verified" tidak bisa di-edit

---

### 3. ✅ Purchase Edit - Block Verified Purchase
**File**: `purchasing/views.py` (function `purchase_edit`)

**Test Cases**:
- [ ] Edit purchase dengan status "draft" → Berhasil
- [ ] Edit purchase dengan status "pending" → Berhasil
- [ ] Edit purchase dengan status "received" → Berhasil
- [ ] Edit purchase dengan status "verified" → Error message: "Purchase yang sudah verified tidak dapat di-edit lagi. Silakan hubungi Finance untuk perubahan."
- [ ] Redirect ke detail page setelah error

**Expected Result**: Verified purchase tidak bisa di-edit (protected di backend)

---

### 4. ✅ Finance Menu - Notification Badges
**File**: `erp_alfa/context_processors.py`, `erp_alfa/views.py`, `templates/base.html`

**Test Cases**:
- [ ] Login dengan user yang punya permission Finance
- [ ] Hover menu "Finance" → Dropdown muncul
- [ ] Check submenu "Purchase Verify" → Ada badge kuning jika ada purchase received
- [ ] Check submenu "Purchase Payment" → Ada badge merah jika ada payment unpaid/partial
- [ ] Check submenu "Purchase Tax Invoice" → Ada badge biru jika ada pending tax invoice
- [ ] Biarkan halaman terbuka 30 detik → Badge auto-refresh
- [ ] Verify 1 purchase → Badge count berkurang

**Expected Result**: Badge muncul dan auto-update setiap 30 detik

---

### 5. ✅ Mobile Home - Purchase List Card
**File**: `templates/mobile_home.html`

**Test Cases**:
- [ ] Buka mobile home `/mobile-home/` atau root `/`
- [ ] Scroll ke section "📋 INVENTORY"
- [ ] Check ada card "Purchase List" dengan icon 🛒 (cart-check)
- [ ] Card ada setelah "Full Opname Rak"
- [ ] Klik card → Redirect ke `/purchaseorder/purchase/`
- [ ] Card hanya muncul jika user punya permission `purchase_view` atau `purchase_warehouse`

**Expected Result**: Purchase List card ada di Inventory section

---

### 6. ✅ Mobile Purchase List - Icons
**File**: `templates/purchasing/mobile_purchase_list.html`

**Test Cases**:
- [ ] Buka `/purchaseorder/purchase/` di mobile/desktop
- [ ] Header: Icon 🛒 `bi bi-cart-check` muncul
- [ ] Tombol Buat: Icon ➕ `bi bi-plus-circle` muncul (jika ada permission)
- [ ] Action buttons:
  - [ ] Receive: `bi bi-box-arrow-in-down` (box arrow down)
  - [ ] Detail: `bi bi-eye` (eye)
  - [ ] Edit: `bi bi-pencil` (pencil)
  - [ ] Delete: `bi bi-trash` (trash)

**Expected Result**: Semua icon muncul dengan benar

---

## 🧪 Test Workflow End-to-End

### Scenario: Purchase Lifecycle dengan User yang Berbeda

1. **Marketing/Warehouse (create/receive)**:
   - [ ] Login sebagai warehouse user
   - [ ] Buka Purchase List dari mobile home (Inventory section)
   - [ ] Create new purchase
   - [ ] Receive purchase (status: pending → received)
   - [ ] Check bisa edit purchase yang sudah received
   - [ ] Check tidak ada tombol "Verify"

2. **Finance (verify)**:
   - [ ] Login sebagai finance user
   - [ ] Check menu Finance → ada badge notifikasi di "Purchase Verify"
   - [ ] Buka Purchase Verify List
   - [ ] Tab "Belum Verified" → Ada purchase yang baru di-receive
   - [ ] Check summary cards
   - [ ] Filter by date → Summary cards update
   - [ ] Filter by supplier → Summary cards update
   - [ ] Verify purchase
   - [ ] Check badge berkurang
   - [ ] Tab "Verified" → Purchase muncul di sini
   - [ ] Summary cards berubah

3. **Warehouse mencoba edit verified purchase**:
   - [ ] Login sebagai warehouse user
   - [ ] Buka Purchase List
   - [ ] Purchase verified tidak ada tombol Edit
   - [ ] Coba akses URL edit langsung → Error message muncul

---

## 🎯 Success Criteria

✅ Semua test cases passed
✅ Tidak ada error di console browser
✅ Tidak ada error di Django logs
✅ Badge notifikasi update otomatis
✅ Summary cards dinamis sesuai filter
✅ Permission system berjalan dengan benar
✅ User tidak bisa bypass permission via URL

---

## 📝 Notes

- Test di browser Chrome/Firefox
- Test di mobile view (responsive)
- Check network tab untuk API calls
- Check Django logs untuk error backend
- Test dengan user yang berbeda permission level


