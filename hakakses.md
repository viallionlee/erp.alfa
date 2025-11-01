# Dokumentasi Hak Akses Template - ERP ALFA

## Ringkasan
Dokumen ini menjabarkan detail hak akses yang diperlukan untuk mengakses setiap template dalam sistem ERP ALFA. Fokus dokumen ini adalah pada hak akses untuk membuka/view template, bukan hak akses untuk fungsi-fungsi spesifik.

## Sistem Permission
ERP ALFA menggunakan sistem permission Django dengan decorator berikut:
- `@login_required` - Memerlukan user untuk login
- `@permission_required('app.permission_name', raise_exception=True)` - Memerlukan permission spesifik
- `@custom_auth_and_permission_required('permission_name')` - Custom decorator untuk auth dan permission

---

# Template Hak Akses per Aplikasi

## 1. CORE TEMPLATES

### Base Templates

**Template:** `base.html`
- **View Function:** N/A (Base template)
- **Permission Required:** Tidak ada
- **Catatan:** Template dasar untuk desktop

**Template:** `base_mobile.html`  
- **View Function:** N/A (Base template)
- **Permission Required:** Tidak ada
- **Catatan:** Template dasar untuk mobile

**Template:** `home.html`
- **View Function:** `erp_alfa.views.home`
- **Permission Required:** `@login_required`
- **Catatan:** Halaman utama desktop

**Template:** `mobile_home.html`
- **View Function:** `fullfilment.mobile_views.mobile_home`
- **Permission Required:** Tidak ada requirement khusus
- **Catatan:** Halaman utama mobile

**Template:** `403.html`
- **View Function:** N/A (Error template)
- **Permission Required:** Tidak ada
- **Catatan:** Template error access denied

### Authentication Templates

**Template:** `registration/login.html`
- **View Function:** `erp_alfa.views.CustomLoginView`
- **Permission Required:** Tidak ada
- **Catatan:** Login page desktop

**Template:** `registration/login_mobile.html`
- **View Function:** `erp_alfa.views.CustomLoginView`
- **Permission Required:** Tidak ada
- **Catatan:** Login page mobile

### Account Templates

**Template:** `accounts/profile.html`
- **View Function:** `accounts.views.profile`
- **Permission Required:** `@login_required`
- **Catatan:** Halaman profil user

## 2. FULLFILMENT TEMPLATES

### Dashboard & Index

**Template:** `fullfilment/index.html`
- **View Function:** `fullfilment.views.index`
- **Permission Required:** `@login_required` + Custom device check
- **Catatan:** Check permission berdasarkan mobile/desktop

**Template:** `fullfilment/mobile_index.html`
- **View Function:** `fullfilment.mobile_views.mobile_batch_index`
- **Permission Required:** Tidak ada requirement khusus
- **Catatan:** Mobile batch index

**Template:** `fullfilment/dashboard.html`
- **View Function:** `fullfilment.dashboard.dashboard`
- **Permission Required:** `@login_required`
- **Catatan:** Dashboard fulfillment

### Batch Management

**Template:** `fullfilment/generatebatch.html`
- **View Function:** `fullfilment.generatebatch_views.generatebatch`
- **Permission Required:** `@permission_required('fullfilment.view_generatebatch')`
- **Catatan:** Generate batch page

**Template:** `fullfilment/batchorder.html`
- **View Function:** `fullfilment.views.batchorder_view`
- **Permission Required:** `@permission_required('fullfilment.view_batchlist')`
- **Catatan:** Batch order detail

**Template:** `fullfilment/batchpicking.html`
- **View Function:** `fullfilment.views.mobilebatchpicking`
- **Permission Required:** `@login_required`
- **Catatan:** Batch picking interface

**Template:** `fullfilment/mobilebatchpicking.html`
- **View Function:** `fullfilment.views.mobilebatchpicking`
- **Permission Required:** `@login_required`
- **Catatan:** Mobile batch picking

**Template:** `fullfilment/editorderbatch.html`
- **View Function:** `fullfilment.views.edit_order_batch_view`
- **Permission Required:** `@login_required`
- **Catatan:** Edit order dalam batch

**Template:** `fullfilment/batchitem_table.html`
- **View Function:** `fullfilment.views.batchitem_table_view`
- **Permission Required:** `@permission_required('fullfilment.change_batchlist')`
- **Catatan:** Tabel batch items

**Template:** `fullfilment/batchitemlogs.html`
- **View Function:** `fullfilment.views.batchitemlogs`
- **Permission Required:** `@login_required`
- **Catatan:** Log batch items

**Template:** `fullfilment/mobile_batchitem_detail.html`
- **View Function:** `fullfilment.views.batchitem_detail_view`
- **Permission Required:** `@login_required`
- **Catatan:** Detail batch item mobile

### Ready to Print & Printing

**Template:** `fullfilment/readytoprint.html`
- **View Function:** `fullfilment.views.ready_to_print_list`
- **Permission Required:** `@permission_required('fullfilment.view_readytoprint')`
- **Catatan:** Daftar ready to print

**Template:** `fullfilment/printedlist.html`
- **View Function:** `fullfilment.views.printed_list`
- **Permission Required:** `@login_required`
- **Catatan:** Daftar yang sudah di-print

**Template:** `fullfilment/not_ready_to_pick_details.html`
- **View Function:** `fullfilment.views.not_ready_to_pick_details`
- **Permission Required:** `@login_required`
- **Catatan:** Detail order tidak siap pick

**Template:** `fullfilment/unallocated_stock_list.html`
- **View Function:** `fullfilment.views.unallocated_stock_list`
- **Permission Required:** `@login_required`
- **Catatan:** Daftar stok tidak teralokasi

### Scanning Operations

**Template:** `fullfilment/scanpicking.html`
- **View Function:** `fullfilment.orderschecking.orders_checking`
- **Permission Required:** `@permission_required('fullfilment.view_picking_module')`
- **Catatan:** Scan picking interface

**Template:** `fullfilment/mobile_scanpicking.html`
- **View Function:** `fullfilment.orderschecking.orders_checking`
- **Permission Required:** `@permission_required('fullfilment.view_picking_module')`
- **Catatan:** Mobile scan picking

**Template:** `fullfilment/scanpicking_list.html`
- **View Function:** `fullfilment.views.scanpicking_list_view`
- **Permission Required:** `@permission_required('fullfilment.view_scanpicking')`
- **Catatan:** List scan picking

**Template:** `fullfilment/scanpicking_history.html`
- **View Function:** `fullfilment.orderschecking.orders_checking_history`
- **Permission Required:** `@permission_required('fullfilment.view_picking_module')`
- **Catatan:** History scan picking

**Template:** `fullfilment/mobile_clickpicking.html`
- **View Function:** `fullfilment.views.mobile_clickpicking_view`
- **Permission Required:** `@login_required`
- **Catatan:** Mobile click picking

**Template:** `fullfilment/scanpacking.html`
- **View Function:** `fullfilment.scanpacking.scanpacking`
- **Permission Required:** `@permission_required('fullfilment.view_scanpacking')`
- **Catatan:** Scan packing interface

**Template:** `fullfilment/mobile_scanpacking.html`
- **View Function:** `fullfilment.scanpacking.scanpacking`
- **Permission Required:** `@permission_required('fullfilment.view_packing_module')`
- **Catatan:** Mobile scan packing

**Template:** `fullfilment/scanpacking_list.html`
- **View Function:** `fullfilment.scanpacking.scanpacking_list_view`
- **Permission Required:** `@permission_required('fullfilment.view_scanpacking')`
- **Catatan:** List scan packing

**Template:** `fullfilment/scanshipping.html`
- **View Function:** `fullfilment.views.ready_to_ship` / `fullfilment.scanshipping.scanshipping`
- **Permission Required:** `@login_required` / `@permission_required('fullfilment.view_shipping_module')`
- **Catatan:** Scan shipping interface

**Template:** `fullfilment/mobile_scanshipping.html`
- **View Function:** Sesuai dengan desktop version
- **Permission Required:** Sama dengan desktop
- **Catatan:** Mobile scan shipping

### Return Management

**Template:** `fullfilment/returnlist.html`
- **View Function:** `fullfilment.returnlist.returnlist_dashboard`
- **Permission Required:** `@permission_required('fullfilment.view_returnlist')`
- **Catatan:** Dashboard return list

**Template:** `fullfilment/returnlist_mobile.html`
- **View Function:** Mobile version of return list
- **Permission Required:** `@permission_required('fullfilment.view_returnlist')`
- **Catatan:** Mobile return list

**Template:** `fullfilment/returnsession_detail.html`
- **View Function:** `fullfilment.returnlist.returnsession_detail`
- **Permission Required:** `@login_required`
- **Catatan:** Detail return session

**Template:** `fullfilment/scanretur.html`
- **View Function:** `fullfilment.views.scanretur_view` / `fullfilment.returnlist.scanretur_view`
- **Permission Required:** `@permission_required('fullfilment.view_scanretur')`
- **Catatan:** Scan return interface

**Template:** `fullfilment/scanordercancel.html`
- **View Function:** `fullfilment.returnlist.scanordercancel_view`
- **Permission Required:** `@login_required`
- **Catatan:** Scan order cancel

**Template:** `fullfilment/scanordercancel_mobile.html`
- **View Function:** Mobile version
- **Permission Required:** `@login_required`
- **Catatan:** Mobile scan order cancel

**Template:** `fullfilment/putaway_return_session.html`
- **View Function:** `fullfilment.returnlist.putaway_return_session`
- **Permission Required:** `@login_required`
- **Catatan:** Putaway return session

**Template:** `fullfilment/scan_return_cancelled_order.html`
- **View Function:** `fullfilment.views.scan_return_cancelled_order_view`
- **Permission Required:** `@login_required`
- **Catatan:** Scan return cancelled order

### Shipping & Reporting

**Template:** `fullfilment/order_shipping_list.html`
- **View Function:** `fullfilment.scanshipping.order_shipping_list_view`
- **Permission Required:** `@permission_required('fullfilment.view_shipping_module')`
- **Catatan:** List order shipping

**Template:** `fullfilment/mobile_order_shipping_list.html`
- **View Function:** Mobile version
- **Permission Required:** `@permission_required('fullfilment.view_shipping_module')`
- **Catatan:** Mobile order shipping list

**Template:** `fullfilment/order_packing_list.html`
- **View Function:** `fullfilment.scanpacking.order_packing_list_view`
- **Permission Required:** `@permission_required('fullfilment.view_packing_module')`
- **Catatan:** List order packing

**Template:** `fullfilment/mobile_order_packing_list.html`
- **View Function:** Mobile version
- **Permission Required:** `@permission_required('fullfilment.view_packing_module')`
- **Catatan:** Mobile order packing list

**Template:** `fullfilment/order_shipping_detail.html`
- **View Function:** `fullfilment.scanshipping.order_shipping_detail_view`
- **Permission Required:** `@login_required`
- **Catatan:** Detail order shipping

**Template:** `fullfilment/ordershippingreport.html`
- **View Function:** `fullfilment.scanshipping.order_shipping_report_view`
- **Permission Required:** `@login_required`
- **Catatan:** Report order shipping

**Template:** `fullfilment/shippinghistory.html`
- **View Function:** `fullfilment.scanshipping.shipping_history_view`
- **Permission Required:** `@login_required`
- **Catatan:** History shipping

**Template:** `fullfilment/shipping_history_mobile.html`
- **View Function:** Mobile version
- **Permission Required:** `@login_required`
- **Catatan:** Mobile shipping history

**Template:** `fullfilment/shipping_report_pdf.html`
- **View Function:** PDF template
- **Permission Required:** N/A
- **Catatan:** Template PDF shipping report

### Other Templates

**Template:** `fullfilment/order_cancel_log.html`
- **View Function:** `fullfilment.views.order_cancel_log_view`
- **Permission Required:** `@login_required`
- **Catatan:** Log cancel order

**Template:** `fullfilment/order_cancel_log_mobile.html`
- **View Function:** Mobile version
- **Permission Required:** `@login_required`
- **Catatan:** Mobile log cancel order

**Template:** `fullfilment/scanbatch.html`
- **View Function:** `fullfilment.views.scanbatch`
- **Permission Required:** `@login_required`
- **Catatan:** Scan batch interface

---

## 3. INVENTORY TEMPLATES

### Main Inventory

**Template:** `inventory/index.html`
- **View Function:** `inventory.views.index`
- **Permission Required:** `@login_required`
- **Catatan:** Halaman utama inventory

**Template:** `inventory/mobile_index.html`
- **View Function:** `inventory.views.index` (mobile)
- **Permission Required:** `@login_required`
- **Catatan:** Mobile inventory index

**Template:** `inventory/mobile_inventory.html`
- **View Function:** `inventory.views.mobile_inventory`
- **Permission Required:** `@login_required`
- **Catatan:** Mobile inventory page

### Stock Management

**Template:** `inventory/stock_card.html`
- **View Function:** `inventory.views.stock_card_view`
- **Permission Required:** `@permission_required('inventory.view_stock')`
- **Catatan:** Stock card view

### Inbound Management

**Template:** `inventory/inbound.html`
- **View Function:** `inventory.views.inbound_list`
- **Permission Required:** `@permission_required('inventory.view_inbound')`
- **Catatan:** List inbound

**Template:** `inventory/inbound_mobile.html`
- **View Function:** Mobile version
- **Permission Required:** `@permission_required('inventory.view_inbound')`
- **Catatan:** Mobile inbound list

**Template:** `inventory/inbound_tambah.html`
- **View Function:** `inventory.views.inbound_tambah`
- **Permission Required:** `@permission_required('inventory.add_inbound')`
- **Catatan:** Tambah inbound

**Template:** `inventory/inbound_tambah_mobile.html`
- **View Function:** Mobile version
- **Permission Required:** `@permission_required('inventory.add_inbound')`
- **Catatan:** Mobile tambah inbound

**Template:** `inventory/inbound_edit.html`
- **View Function:** `inventory.views.inbound_edit`
- **Permission Required:** `@login_required`
- **Catatan:** Edit inbound

**Template:** `inventory/inbound_edit_mobile.html`
- **View Function:** Mobile version
- **Permission Required:** `@login_required`
- **Catatan:** Mobile edit inbound

**Template:** `inventory/inbound_confirm_delete.html`
- **View Function:** `inventory.views.inbound_delete`
- **Permission Required:** `@permission_required('inventory.delete_inbound')`
- **Catatan:** Konfirmasi hapus inbound

**Template:** `inventory/addinbound.html`
- **View Function:** Legacy template
- **Permission Required:** Legacy
- **Catatan:** Template lama

### Supplier Management

**Template:** `inventory/daftar_supplier.html`
- **View Function:** `inventory.views.daftar_supplier`
- **Permission Required:** `@permission_required('inventory.view_supplier')`
- **Catatan:** Daftar supplier

### Rak Management

**Template:** `inventory/rak_list.html`
- **View Function:** `inventory.rak_views.rak_list`
- **Permission Required:** `@permission_required('inventory.view_rak')`
- **Catatan:** Daftar rak

**Template:** `inventory/rak_mobile.html`
- **View Function:** Mobile version
- **Permission Required:** `@permission_required('inventory.view_rak')`
- **Catatan:** Mobile daftar rak

**Template:** `inventory/rak_stock.html`
- **View Function:** `inventory.rak_views.rak_stock`
- **Permission Required:** `@permission_required('inventory.view_rak')`
- **Catatan:** Stok per rak

**Template:** `inventory/rak_stock_mobile.html`
- **View Function:** Mobile version
- **Permission Required:** `@permission_required('inventory.view_rak')`
- **Catatan:** Mobile stok per rak

**Template:** `inventory/rak_stock_detail.html`
- **View Function:** `inventory.rak_views.rak_stock_detail`
- **Permission Required:** `@permission_required('inventory.view_rak')`
- **Catatan:** Detail stok rak

**Template:** `inventory/rak_capacity.html`
- **View Function:** `inventory.rakcapacity.rak_capacity_view`
- **Permission Required:** `@permission_required('inventory.view_rak')`
- **Catatan:** Kapasitas rak

**Template:** `inventory/stock_position_mobile.html`
- **View Function:** `inventory.rak_views.stock_position_view`
- **Permission Required:** `@permission_required('inventory.view_rak')`
- **Catatan:** Mobile posisi stok

### Putaway Management

**Template:** `inventory/putaway.html`
- **View Function:** `inventory.views.putaway_list`
- **Permission Required:** `@permission_required('inventory.view_putaway')`
- **Catatan:** List putaway

**Template:** `inventory/putaway_mobile.html`
- **View Function:** Mobile version
- **Permission Required:** `@permission_required('inventory.view_putaway')`
- **Catatan:** Mobile putaway list

**Template:** `inventory/putaway_scan.html`
- **View Function:** `inventory.views.putaway_scan`
- **Permission Required:** `@permission_required('inventory.change_putaway')`
- **Catatan:** Scan putaway

**Template:** `inventory/putaway_scan_mobile.html`
- **View Function:** Mobile version
- **Permission Required:** `@permission_required('inventory.change_putaway')`
- **Catatan:** Mobile scan putaway

**Template:** `inventory/putaway_history.html`
- **View Function:** `inventory.views.putaway_history`
- **Permission Required:** `@permission_required('inventory.view_putaway')`
- **Catatan:** History putaway

**Template:** `inventory/putaway_history_mobile.html`
- **View Function:** Mobile version
- **Permission Required:** `@permission_required('inventory.view_putaway')`
- **Catatan:** Mobile history putaway

**Template:** `inventory/slotting_history.html`
- **View Function:** `inventory.views.slotting_history`
- **Permission Required:** `@login_required`
- **Catatan:** History slotting

**Template:** `inventory/slotting_history_mobile.html`
- **View Function:** Mobile version
- **Permission Required:** `@login_required`
- **Catatan:** Mobile history slotting

### Opname Management

**Template:** `inventory/opname_rak_list.html`
- **View Function:** `inventory.opname_views.opname_rak_list`
- **Permission Required:** `@permission_required('inventory.view_opname')`
- **Catatan:** List opname rak

**Template:** `inventory/opname_rak_list_mobile.html`
- **View Function:** Mobile version
- **Permission Required:** `@permission_required('inventory.view_opname')`
- **Catatan:** Mobile list opname rak

**Template:** `inventory/opname_rak_work.html`
- **View Function:** `inventory.opname_views.opname_rak_work`
- **Permission Required:** `@permission_required('inventory.add_opname')`
- **Catatan:** Work opname rak

**Template:** `inventory/opname_rak_detail.html`
- **View Function:** `inventory.opname_views.opname_rak_detail`
- **Permission Required:** `@permission_required('inventory.view_opname')`
- **Catatan:** Detail opname rak

**Template:** `inventory/opname_rak_detail_mobile.html`
- **View Function:** Mobile version
- **Permission Required:** `@permission_required('inventory.view_opname')`
- **Catatan:** Mobile detail opname rak

**Template:** `inventory/opname_input_mobile.html`
- **View Function:** Mobile input opname
- **Permission Required:** `@permission_required('inventory.add_opname')`
- **Catatan:** Mobile input opname

**Template:** `inventory/opnamequeue_mobile.html`
- **View Function:** Mobile opname queue
- **Permission Required:** `@login_required`
- **Catatan:** Mobile opname queue

**Template:** `inventory/rakopname_session_list.html`
- **View Function:** `inventory.views.rakopname_session_list`
- **Permission Required:** `@login_required`
- **Catatan:** List session opname rak

**Template:** `inventory/full_opname_list.html`
- **View Function:** `inventory.opname_views.full_opname_list`
- **Permission Required:** `@permission_required('inventory.view_opname')`
- **Catatan:** List full opname

**Template:** `inventory/full_opname_list_mobile.html`
- **View Function:** Mobile version
- **Permission Required:** `@permission_required('inventory.view_opname')`
- **Catatan:** Mobile list full opname

**Template:** `inventory/full_opname_detail.html`
- **View Function:** `inventory.opname_views.full_opname_detail`
- **Permission Required:** `@permission_required('inventory.view_opname')`
- **Catatan:** Detail full opname

**Template:** `inventory/full_opname_detail_mobile.html`
- **View Function:** Mobile version
- **Permission Required:** `@permission_required('inventory.view_opname')`
- **Catatan:** Mobile detail full opname

**Template:** `inventory/full_opname_create_mobile.html`
- **View Function:** Mobile create full opname
- **Permission Required:** `@permission_required('inventory.add_opname')`
- **Catatan:** Mobile create full opname

### Transfer Management

**Template:** `inventory/transfer_rak_list.html`
- **View Function:** `inventory.transfer_views.transfer_rak_list`
- **Permission Required:** `@permission_required('inventory.view_raktransfer')`
- **Catatan:** List transfer rak

**Template:** `inventory/transfer_rak_work.html`
- **View Function:** `inventory.transfer_views.transfer_rak_work`
- **Permission Required:** `@permission_required('inventory.add_raktransfer')`
- **Catatan:** Work transfer rak

**Template:** `inventory/transfer_rak_detail.html`
- **View Function:** `inventory.transfer_views.transfer_rak_detail`
- **Permission Required:** `@permission_required('inventory.view_raktransfer')`
- **Catatan:** Detail transfer rak

**Template:** `inventory/transfer_rak_cancel.html`
- **View Function:** `inventory.transfer_views.transfer_rak_cancel`
- **Permission Required:** `@permission_required('inventory.change_raktransfer')`
- **Catatan:** Cancel transfer rak

**Template:** `inventory/transfer_putaway_mobile.html`
- **View Function:** Mobile transfer putaway
- **Permission Required:** `@permission_required('inventory.view_raktransfer')`
- **Catatan:** Mobile transfer putaway

---

## 4. PRODUCTS TEMPLATES

### Main Product Management

**Template:** `products/index.html`
- **View Function:** `products.views.index`
- **Permission Required:** `@login_required`
- **Catatan:** Halaman utama products

**Template:** `products/viewall.html`
- **View Function:** `products.views.viewall`
- **Permission Required:** `@login_required`
- **Catatan:** View all products

**Template:** `products/add_product.html`
- **View Function:** `products.views.add_product`
- **Permission Required:** `@login_required`
- **Catatan:** Tambah produk

**Template:** `products/edit_product.html`
- **View Function:** `products.views.edit_product`
- **Permission Required:** `@login_required`
- **Catatan:** Edit produk

### Import & History

**Template:** `products/import_history.html`
- **View Function:** `products.views.import_history_view`
- **Permission Required:** `@permission_required('products.view_product')`
- **Catatan:** History import produk

**Template:** `products/import_status.html`
- **View Function:** `products.views.import_products`
- **Permission Required:** `@login_required`
- **Catatan:** Status import produk

**Template:** `products/add_history.html`
- **View Function:** `products.views.add_history_view`
- **Permission Required:** `@permission_required('products.view_product')`
- **Catatan:** History tambah produk

### Barcode Management

**Template:** `products/extrabarcode.html`
- **View Function:** `products.views.extrabarcode_view`
- **Permission Required:** `@permission_required('products.view_product')`
- **Catatan:** Extra barcode

**Template:** `products/extrabarcode_tambah.html`
- **View Function:** `products.views.extrabarcode_add_view`
- **Permission Required:** `@permission_required('products.add_product')`
- **Catatan:** Tambah extra barcode

### SKU Bundling

**Template:** `products/sku_bundling.html`
- **View Function:** `products.views.sku_bundling_list`
- **Permission Required:** `@permission_required('products.view_product')`
- **Catatan:** List SKU bundling

**Template:** `products/sku_bundling_form.html`
- **View Function:** `products.views.sku_bundling_add` / `sku_bundling_edit`
- **Permission Required:** `@permission_required('products.add_product')`
- **Catatan:** Form SKU bundling

**Template:** `products/sku_bundling_delete_confirm.html`
- **View Function:** `products.views.sku_bundling_delete`
- **Permission Required:** `@permission_required('products.delete_product')`
- **Catatan:** Konfirmasi hapus SKU bundling

**Template:** `products/sku_bundling_import_form.html`
- **View Function:** `products.views.import_sku_bundling`
- **Permission Required:** `@login_required`
- **Catatan:** Import SKU bundling

### Product Logs & Dimensions

**Template:** `products/product_edit_logs.html`
- **View Function:** `products.views.product_edit_logs`
- **Permission Required:** `@permission_required('products.view_product')`
- **Catatan:** Log edit produk

**Template:** `products/product_dimension.html`
- **View Function:** `products.views.product_dimension_view`
- **Permission Required:** `@permission_required('products.view_product')`
- **Catatan:** Dimensi produk

---

## 5. ORDERS TEMPLATES

### Main Order Management

**Template:** `orders/index.html`
- **View Function:** `orders.views.index`
- **Permission Required:** `@permission_required('orders.view_order')`
- **Catatan:** Halaman utama orders

**Template:** `orders/addorder.html`
- **View Function:** `orders.views.add_order` / `orders_listedit`
- **Permission Required:** `@permission_required('orders.add_order')`
- **Catatan:** Tambah/edit order

**Template:** `orders/orders_list.html`
- **View Function:** `orders.views.orders_list`
- **Permission Required:** `@permission_required('orders.view_order')`
- **Catatan:** List orders

**Template:** `orders/allorders.html`
- **View Function:** `orders.views.all_orders_view`
- **Permission Required:** `@permission_required('orders.view_order')`
- **Catatan:** Semua orders

**Template:** `orders/editorder.html`
- **View Function:** `orders.views.edit_order_view`
- **Permission Required:** `@permission_required('orders.change_order')`
- **Catatan:** Edit order

### Order Details

**Template:** `orders/orders_listdetail.html`
- **View Function:** `orders.views.orders_listdetail`
- **Permission Required:** `@permission_required('orders.view_order')`
- **Catatan:** Detail order list

**Template:** `orders/orders_detail.html`
- **View Function:** `orders.views.orders_detail`
- **Permission Required:** `@permission_required('orders.view_order')`
- **Catatan:** Detail order

**Template:** `orders/orderlist_delete.html`
- **View Function:** `orders.views.orders_delete`
- **Permission Required:** `@permission_required('orders.delete_order')`
- **Catatan:** Konfirmasi hapus order

### Import Management

**Template:** `orders/orderimport_history.html`
- **View Function:** `orders.views.orderimport_history`
- **Permission Required:** `@permission_required('orders.view_order')`
- **Catatan:** History import order

---

## Catatan Penting

### 1. Device-Based Permissions
Beberapa view functions menggunakan sistem permission berbasis device:
```python
def check_permission_by_device(request, permission_name):
    if is_mobile:
        mobile_permission = f'fullfilment.view_mobile_{permission_name}'
        legacy_permission = f'fullfilment.view_{permission_name}'
        return request.user.has_perm(mobile_permission) or request.user.has_perm(legacy_permission)
    else:
        desktop_permission = f'fullfilment.view_desktop_{permission_name}'
        legacy_permission = f'fullfilment.view_{permission_name}'
        return request.user.has_perm(desktop_permission) or request.user.has_perm(legacy_permission)
```

### 2. Mobile Template Detection
Sistem secara otomatis mendeteksi User-Agent dan mengarahkan ke template mobile yang sesuai jika diakses dari perangkat mobile.

### 3. Permission Naming Convention
- Format: `app_name.action_model_name`
- Contoh: `fullfilment.view_batchlist`, `inventory.add_inbound`, `products.delete_product`

### 4. Login Required vs Permission Required
- `@login_required`: Hanya perlu login, tidak perlu permission khusus
- `@permission_required`: Perlu permission spesifik, otomatis mengecek login juga

### 5. Template Inheritance
Beberapa template menggunakan inheritance dari `base.html` atau `base_mobile.html`, jadi permission untuk base template juga perlu dipertimbangkan.

---

**Last Updated:** Oktober 2025  
**Version:** 1.0  
**Maintained by:** ERP ALFA Development Team
