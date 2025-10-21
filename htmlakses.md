# Hak Akses Aplikasi Fullfilment

Dokumen ini memetakan file template HTML dengan hak akses (permission) Django yang diperlukan untuk mengakses halaman tersebut. Format yang digunakan adalah `nama_kode_permission` (`Deskripsi di Panel Admin`).

---

## FULLFILMENT

### Generate Batch
- **generatebatch.html**
  - **desktop**: `fullfilment.view_desktop_generatebatch` (`Fullfilment | Batch List | Can view desktop generate batch page`)
  - **mobile**: -
- **genbatchlist.html**
  - **desktop**: `fullfilment.generate_desktop_batch` (`Fullfilment | Batch List | Can generate desktop batch and access printed list`)
  - **mobile**: `fullfilment.generate_mobile_batch` (`Fullfilment | Batch List | Can generate mobile batch and access printed list`)

---

### Batch List / Order
- **batchorder.html**
  - **desktop**: `fullfilment.view_desktop_batchlist` (`Fullfilment | Batch List | Can view desktop batch list`)
  - **mobile**: -
- **batchitem_detail.html**
  - **desktop**: `fullfilment.view_desktop_batchlist` (`Fullfilment | Batch List | Can view desktop batch list`)
  - **mobile**: -
- **mobile_batchitem_detail.html**
  - **desktop**: -
  - **mobile**: `fullfilment.view_mobile_batchlist` (`Fullfilment | Batch List | Can view mobile batch list`)
- **index.html (Desktop)**
  - **desktop**: `fullfilment.view_desktop_batchlist` (`Fullfilment | Batch List | Can view desktop batch list`)
  - **mobile**: -
- **mobile_index.html (Mobile)**
  - **desktop**: -
  - **mobile**: `fullfilment.view_mobile_batchlist` (`Fullfilment | Batch List | Can view mobile batch list`)

---

### Batch Picking
- **batchpicking.html**
  - **desktop**: `fullfilment.view_desktop_batchpicking` (`Fullfilment | Batch List | Can access desktop batchpicking module`)
  - **mobile**: -
- **mobilebatchpicking.html**
  - **desktop**: -
  - **mobile**: `fullfilment.view_mobile_batchpicking` (`Fullfilment | Batch List | Can access mobile batchpicking module`)

---

### Picking Module (Scan Picking)
- **orders_scan.html (Desktop Scanner)**
  - **desktop**: `fullfilment.view_desktop_picking_module` (`Fullfilment | Batch List | Can access desktop picking module (scanpicking + order-checking-list)`)
  - **mobile**: -
- **mobileorderchecking.html (Mobile Scanner)**
  - **desktop**: -
  - **mobile**: `fullfilment.view_mobile_picking_module` (`Fullfilment | Batch List | Can access mobile picking module (scanpicking + order-checking-list)`)
- **order_checking_list.html (History)**
  - **desktop**: `fullfilment.view_desktop_picking_module` (`Fullfilment | Batch List | Can access desktop picking module (scanpicking + order-checking-list)`)
  - **mobile**: `fullfilment.view_mobile_picking_module` (`Fullfilment | Batch List | Can access mobile picking module (scanpicking + order-checking-list)`)

---

### Packing Module (Scan Packing)
- **scanpacking.html**
  - **desktop**: `fullfilment.view_desktop_packing_module` (`Fullfilment | Batch List | Can access desktop packing module (scanpacking + order-packing-list)`)
  - **mobile**: -
- **mobile_scanpacking.html**
  - **desktop**: -
  - **mobile**: `fullfilment.view_mobile_packing_module` (`Fullfilment | Batch List | Can access mobile packing module (scanpacking + order-packing-list)`)
- **order_packing_list.html**
  - **desktop**: `fullfilment.view_desktop_packing_module` (`Fullfilment | Batch List | Can access desktop packing module (scanpacking + order-packing-list)`)
  - **mobile**: -
- **mobile_order_packing_list.html**
  - **desktop**: -
  - **mobile**: `fullfilment.view_mobile_packing_module` (`Fullfilment | Batch List | Can access mobile packing module (scanpacking + order-packing-list)`)

---

### Shipping Module (Scan Shipping)
- **scanshipping.html**
  - **desktop**: `fullfilment.view_desktop_shipping_module` (`Fullfilment | Batch List | Can access desktop shipping module (scanshipping + order-shipping-list)`)
  - **mobile**: -
- **mobile_scanshipping.html**
  - **desktop**: -
  - **mobile**: `fullfilment.view_mobile_shipping_module` (`Fullfilment | Batch List | Can access mobile shipping module (scanshipping + order-shipping-list)`)
- **order_shipping_list.html**
  - **desktop**: `fullfilment.view_desktop_shipping_module` (`Fullfilment | Batch List | Can access desktop shipping module (scanshipping + order-shipping-list)`)
  - **mobile**: -
- **mobile_order_shipping_list.html**
  - **desktop**: -
  - **mobile**: `fullfilment.view_mobile_shipping_module` (`Fullfilment | Batch List | Can access mobile shipping module (scanshipping + order-shipping-list)`)

---

### Ready To Print
- **readytoprint.html**
  - **desktop**: `fullfilment.view_desktop_readytoprint` (`Fullfilment | Batch List | Can access desktop readytoprint module`)
  - **mobile**: `fullfilment.view_mobile_readytoprint` (`Fullfilment | Batch List | Can access mobile readytoprint module`)

---

### Return List
- **returnlist.html**
  - **desktop**: `fullfilment.view_desktop_returnlist` (`Fullfilment | Batch List | Can access desktop return list module`)
  - **mobile**: -
- **returnlist_mobile.html**
  - **desktop**: -
  - **mobile**: `fullfilment.view_mobile_returnlist` (`Fullfilment | Batch List | Can access mobile return list module`)

---

### Lainnya (Tanpa Permission Spesifik / Akses Umum)
- **dashboard.html**: Memerlukan login (`login_required`)
- **orders_scan.html**: Memerlukan login (`login_required`)
- **scanordercancel.html / scanordercancel_mobile.html**: Memerlukan login (`login_required`)
- **order_cancel_log.html / order_cancel_log_mobile.html**: Memerlukan login (`login_required`)
