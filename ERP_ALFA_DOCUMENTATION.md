# ERP ALFA - Sistem Manajemen Gudang Terintegrasi

## 📋 Daftar Isi
1. [Overview Sistem](#overview-sistem)
2. [Model Database](#model-database)
3. [Workflow Utama](#workflow-utama)
4. [Proses Detail](#proses-detail)
5. [Status dan Transisi](#status-dan-transisi)
6. [Integrasi Antar Modul](#integrasi-antar-modul)

---

## 🏢 Overview Sistem

ERP ALFA adalah sistem manajemen gudang terintegrasi yang mengelola seluruh siklus hidup produk dari inbound hingga shipping. Sistem ini dirancang untuk warehouse e-commerce dengan fokus pada efisiensi operasional dan akurasi inventory.

### **Modul Utama:**
- **Products**: Manajemen master data produk
- **Inventory**: Manajemen stok dan lokasi
- **Orders**: Manajemen pesanan customer
- **Fulfillment**: Proses picking, packing, shipping
- **Analytics**: Laporan dan analisis

---

## 🗄️ Model Database

### **1. PRODUCTS MODULE**

#### **Product (Master Data)**
```python
class Product(models.Model):
    sku = CharField(unique=True)                    # SKU unik produk
    barcode = CharField(unique=True)                # Barcode produk
    nama_produk = CharField()                       # Nama produk
    variant_produk = CharField()                    # Variant produk
    brand = CharField()                             # Brand produk
    rak = CharField()                               # Lokasi rak default
    # Dimensi produk
    panjang_cm = DecimalField()                     # Panjang dalam cm
    lebar_cm = DecimalField()                       # Lebar dalam cm
    tinggi_cm = DecimalField()                      # Tinggi dalam cm
    berat_gram = DecimalField()                     # Berat dalam gram
    posisi_tidur = BooleanField()                   # Bisa posisi tidur
    photo = ImageField()                            # Foto produk
    is_active = BooleanField()                      # Status aktif
```

#### **ProductImportHistory**
- Mencatat history import produk dari Excel
- Tracking success/failed count

#### **ProductAddHistory**
- Mencatat penambahan produk manual
- Audit trail untuk perubahan produk

#### **ProductsBundling**
- Mengelola produk bundle (gabungan beberapa SKU)
- Contoh: Bundle skincare set

#### **ProductExtraBarcode**
- Barcode tambahan untuk produk yang sama
- Support multiple barcode per produk

#### **EditProductLog**
- Audit trail untuk perubahan produk
- Mencatat field yang berubah (old_value, new_value)

### **2. INVENTORY MODULE**

#### **Stock (Stok Utama)**
```python
class Stock(models.Model):
    product = OneToOneField(Product)                # Relasi ke produk
    sku = CharField(unique=True)                    # SKU produk
    quantity = IntegerField()                       # Stok di rak (ready)
    quantity_locked = IntegerField()                # Stok di-lock untuk batch
    quantity_putaway = IntegerField()               # Stok belum di putaway
    
    @property
    def quantity_ready_virtual(self):               # Stok siap jual
        return self.quantity - self.quantity_locked
```

#### **InventoryRakStock (Stok per Rak)**
```python
class InventoryRakStock(models.Model):
    product = ForeignKey(Product)                   # Produk
    rak = ForeignKey(Rak)                          # Lokasi rak
    quantity = IntegerField()                       # Quantity di rak
    quantity_opname = IntegerField()                # Quantity dari opname
    updated_at = DateTimeField()                    # Waktu update
```

#### **StockCardEntry (Kartu Stok)**
```python
class StockCardEntry(models.Model):
    TIPE_PERGERAKAN = [
        ('inbound', 'Inbound (+)'),
        ('outbound', 'Outbound (-)'),
        ('opname_in', 'Opname In (+)'),
        ('opname_out', 'Opname Out (-)'),
        ('kunci_stok', 'Kunci Stok (Batch) (-)'),
        ('reopen_batch', 'Batal Kunci Stok (+)'),
        ('close_batch', 'Close Batch (-)'),
        ('return_stock', 'Return Stock (+)'),
        ('pindah_rak', 'Pindah Rak'),
        ('koreksi_stok', 'Koreksi Stok (+/-)'),
    ]
    
    product = ForeignKey(Product)                   # Produk
    waktu = DateTimeField()                         # Waktu transaksi
    tipe_pergerakan = CharField(choices=TIPE_PERGERAKAN)
    qty = IntegerField()                            # Quantity
    qty_awal = IntegerField()                       # Quantity awal
    qty_akhir = IntegerField()                      # Quantity akhir
    user = ForeignKey(User)                         # User yang melakukan
    notes = TextField()                             # Catatan
    status = CharField()                            # Status transaksi
```

#### **Inbound & InboundItem**
```python
class Inbound(models.Model):
    nomor_inbound = CharField(unique=True)          # Nomor inbound
    tanggal = DateTimeField()                       # Tanggal inbound
    keterangan = TextField()                        # Keterangan
    supplier = ForeignKey(Supplier)                 # Supplier

class InboundItem(models.Model):
    inbound = ForeignKey(Inbound)                   # Relasi ke inbound
    product = ForeignKey(Product)                   # Produk
    quantity = IntegerField()                       # Quantity
```

#### **Rak & InventoryRakStockLog**
```python
class Rak(models.Model):
    kode_rak = CharField(unique=True)               # Kode rak
    nama_rak = CharField()                          # Nama rak
    kapasitas = IntegerField()                      # Kapasitas rak
    status = CharField()                            # Status rak

class InventoryRakStockLog(models.Model):
    produk = ForeignKey(Product)                    # Produk
    rak = ForeignKey(Rak)                          # Rak
    qty = IntegerField()                            # Quantity
    tipe_pergerakan = CharField()                   # Tipe pergerakan
    waktu_buat = DateTimeField()                    # Waktu transaksi
    user = ForeignKey(User)                         # User
    catatan = TextField()                           # Catatan
```

#### **Opname Models**
```python
class OpnameQueue(models.Model):
    product = ForeignKey(Product)                   # Produk
    lokasi = CharField()                            # Lokasi
    terakhir_opname = DateTimeField()               # Terakhir opname
    prioritas = IntegerField()                      # Prioritas
    status = CharField()                            # Status

class OpnameHistory(models.Model):
    product = ForeignKey(Product)                   # Produk
    tanggal_opname = DateTimeField()                # Tanggal opname
    qty_fisik = IntegerField()                      # Quantity fisik
    qty_sistem = IntegerField()                     # Quantity sistem
    selisih = IntegerField()                        # Selisih
    petugas_opname = ForeignKey(User)               # Petugas
    catatan = TextField()                           # Catatan
```

### **3. ORDERS MODULE**

#### **Order (Pesanan Customer)**
```python
class Order(models.Model):
    product = ForeignKey(Product)                   # Produk
    id_pesanan = CharField(db_index=True)           # ID pesanan
    sku = CharField(db_index=True)                  # SKU produk
    jumlah = IntegerField()                         # Jumlah pesanan
    status = CharField()                            # Status pesanan
    status_order = CharField()                      # Status order
    status_cancel = CharField()                     # Status cancel
    status_retur = CharField()                      # Status retur
    nama_batch = CharField()                        # Nama batch
    jumlah_ambil = IntegerField()                   # Jumlah yang diambil
    status_ambil = CharField()                      # Status ambil
    status_stock = CharField()                      # Status stok
    status_bundle = CharField()                     # Status bundle
    # Informasi customer & shipping
    channel = CharField()                           # Channel (Tokopedia, Shopee, dll)
    nama_toko = CharField()                         # Nama toko
    kurir = CharField()                             # Kurir
    awb_no_tracking = CharField()                   # AWB/Tracking number
    metode_pengiriman = CharField()                 # Metode pengiriman
```

#### **Order History Models**
- **OrderPrintHistory**: History pencetakan order
- **OrderPackingHistory**: History packing order
- **OrderShippingHistory**: History shipping order
- **OrderHandoverHistory**: History handover ke kurir

### **4. FULFILLMENT MODULE**

#### **BatchList (Batch Picking)**
```python
class BatchList(models.Model):
    nama_batch = CharField()                        # Nama batch
    created_at = DateTimeField()                    # Waktu dibuat
    completed_at = DateTimeField()                  # Waktu selesai
    status_batch = CharField()                      # Status batch
    close_count = IntegerField()                    # Jumlah kali di-close
```

#### **BatchItem (Item dalam Batch)**
```python
class BatchItem(models.Model):
    batchlist = ForeignKey(BatchList)               # Relasi ke batch
    product = ForeignKey(Product)                   # Produk
    jumlah = IntegerField()                         # Jumlah order
    jumlah_ambil = IntegerField()                   # Jumlah yang diambil
    jumlah_transfer = IntegerField()                # Jumlah yang ditransfer
    jumlah_terpakai = IntegerField()                # Jumlah yang terpakai
    jumlah_keep = IntegerField()                    # Jumlah yang di-keep
    status_ambil = CharField()                      # Status ambil
    completed_at = DateTimeField()                  # Waktu selesai
    completed_by = ForeignKey(User)                 # User yang menyelesaikan
```

#### **ReadyToPrint (Order Siap Print)**
```python
class ReadyToPrint(models.Model):
    id_pesanan = CharField(unique=True)             # ID pesanan
    batchlist = ForeignKey(BatchList)               # Relasi ke batch
    status_print = CharField()                      # Status print
    printed_at = DateTimeField()                    # Waktu print
    copied_at = DateTimeField()                     # Waktu copy
    handed_over_at = DateTimeField()                # Waktu handover
    printed_via = CharField()                       # Metode print
    printed_by = ForeignKey(User)                   # User yang print
```

#### **Return Models**
```python
class ReturnSession(models.Model):
    kode = CharField(unique=True)                   # Kode session
    created_by = ForeignKey(User)                   # User yang membuat
    created_at = DateTimeField()                    # Waktu dibuat
    status = CharField()                            # Status session
    notes = TextField()                             # Catatan

class ReturnItem(models.Model):
    session = ForeignKey(ReturnSession)             # Relasi ke session
    product = ForeignKey(Product)                   # Produk
    quantity = IntegerField()                       # Quantity return
    reason = CharField()                            # Alasan return
    condition = CharField()                         # Kondisi produk
```

---

## 🔄 Workflow Utama

### **1. INBOUND WORKFLOW**
```
Supplier → Inbound → InboundItem → Stock (quantity_putaway) → Putaway → Stock (quantity)
```

**Detail Proses:**
1. **Import Inbound**: Upload Excel dari supplier
2. **Create Inbound**: Buat dokumen inbound
3. **Stock Update**: Update `quantity_putaway` di Stock
4. **Putaway Process**: Pindahkan ke rak
5. **Final Update**: Update `quantity` di Stock dan InventoryRakStock

### **2. BATCH PICKING WORKFLOW**
```
Orders → Generate Batch → BatchList → BatchItem → Picking → ReadyToPrint → Printing → Packing → Shipping
```

**Detail Proses:**
1. **Import Orders**: Upload Excel pesanan customer
2. **Generate Batch**: Buat batch berdasarkan kriteria
3. **Batch Creation**: Buat BatchList dan BatchItem
4. **Stock Lock**: Update `quantity_locked` di Stock
5. **Picking Process**: Scan dan ambil produk
6. **Ready to Print**: Order siap untuk print
7. **Printing**: Print label dan dokumen
8. **Packing**: Pack produk
9. **Shipping**: Handover ke kurir

### **3. PUTAWAY WORKFLOW**
```
Stock (quantity_putaway) → Putaway Process → InventoryRakStock → Stock (quantity)
```

**Detail Proses:**
1. **Check Putaway List**: Lihat produk yang perlu di-putaway
2. **Scan Product**: Scan barcode produk
3. **Scan Rak**: Scan lokasi rak
4. **Update Stock**: Update quantity di Stock dan InventoryRakStock
5. **Create Log**: Buat log di StockCardEntry dan InventoryRakStockLog

### **4. SLOTTING WORKFLOW**
```
Product → Slotting Process → Rak Assignment → Update Product.rak
```

**Detail Proses:**
1. **Check Product**: Lihat produk yang belum ada lokasi
2. **Slotting Process**: Tentukan lokasi optimal
3. **Rak Assignment**: Assign ke rak tertentu
4. **Update Product**: Update field `rak` di Product

### **5. OPNAME WORKFLOW**
```
OpnameQueue → Opname Process → OpnameHistory → StockCardEntry → Stock Update
```

**Detail Proses:**
1. **Generate Queue**: Buat queue opname berdasarkan prioritas
2. **Opname Process**: Hitung fisik vs sistem
3. **Record History**: Catat di OpnameHistory
4. **Create Entry**: Buat entry di StockCardEntry
5. **Update Stock**: Update quantity di Stock

### **6. RETURN WORKFLOW**
```
Return Session → Return Item → Stock Update → StockCardEntry
```

**Detail Proses:**
1. **Create Session**: Buat session return
2. **Scan Return**: Scan produk yang di-return
3. **Record Item**: Catat di ReturnItem
4. **Update Stock**: Update quantity di Stock
5. **Create Entry**: Buat entry di StockCardEntry

---

## 📊 Proses Detail

### **INBOUND PROCESS**

#### **1. Import Inbound**
- Upload Excel file dari supplier
- Format: SKU, Quantity, Supplier, Tanggal
- Validasi data dan create Inbound + InboundItem
- Update `quantity_putaway` di Stock

#### **2. Putaway Process**
- Scan barcode produk
- Scan lokasi rak
- Validasi kapasitas rak
- Update quantity di InventoryRakStock
- Update `quantity` dan `quantity_putaway` di Stock
- Create log di StockCardEntry dan InventoryRakStockLog

### **BATCH PICKING PROCESS**

#### **1. Generate Batch**
- Filter order berdasarkan status dan kriteria
- Group order berdasarkan SKU
- Create BatchList dengan nama unik
- Create BatchItem untuk setiap SKU
- Update `quantity_locked` di Stock

#### **2. Picking Process**
- Scan barcode produk
- Validasi quantity yang diambil
- Update `jumlah_ambil` di BatchItem
- Update `quantity_locked` di Stock
- Create log di BatchItemLog

#### **3. Ready to Print**
- Order yang sudah di-pick masuk ke ReadyToPrint
- Status: pending → printed → copied → handed_over
- Tracking user dan waktu untuk setiap status

#### **4. Printing Process**
- Print label dan dokumen
- Update status di ReadyToPrint
- Record di OrderPrintHistory

#### **5. Packing Process**
- Pack produk sesuai order
- Update status packing
- Record di OrderPackingHistory

#### **6. Shipping Process**
- Handover ke kurir
- Update status shipping
- Record di OrderShippingHistory

### **PUTAWAY PROCESS**

#### **1. Putaway List**
- Tampilkan produk dengan `quantity_putaway > 0`
- Sort berdasarkan prioritas (SKU, brand, dll)

#### **2. Putaway Execution**
- Scan barcode produk
- Scan lokasi rak
- Validasi kapasitas dan kompatibilitas
- Update quantity di InventoryRakStock
- Update Stock (quantity, quantity_putaway)
- Create log entries

### **SLOTTING PROCESS**

#### **1. Slotting Analysis**
- Analisis karakteristik produk (dimensi, berat, brand)
- Analisis pola penjualan dan picking
- Tentukan lokasi optimal berdasarkan ABC analysis

#### **2. Slotting Assignment**
- Assign produk ke rak yang sesuai
- Update field `rak` di Product
- Consider kapasitas dan kompatibilitas

### **OPNAME PROCESS**

#### **1. Opname Queue**
- Generate queue berdasarkan prioritas
- Faktor: terakhir opname, nilai produk, akurasi historis

#### **2. Opname Execution**
- Hitung quantity fisik
- Bandingkan dengan quantity sistem
- Record selisih di OpnameHistory
- Create StockCardEntry untuk koreksi

#### **3. Stock Correction**
- Update quantity di Stock berdasarkan opname
- Update InventoryRakStock jika perlu
- Create audit trail lengkap

### **RETURN PROCESS**

#### **1. Return Session**
- Create session return dengan kode unik
- Assign user yang menangani

#### **2. Return Processing**
- Scan produk yang di-return
- Input alasan dan kondisi
- Record di ReturnItem
- Update quantity di Stock
- Create StockCardEntry

---

## 📈 Status dan Transisi

### **ORDER STATUS FLOW**
```
New → Pending → In Batch → Picked → Printed → Packed → Shipped → Delivered
```

### **BATCH STATUS FLOW**
```
Open → In Progress → Completed → Closed
```

### **STOCK STATUS**
- **Ready**: `quantity - quantity_locked` (siap jual)
- **Locked**: `quantity_locked` (dalam batch)
- **Putaway**: `quantity_putaway` (belum di rak)

### **PUTAWAY STATUS**
- **Pending**: Produk belum di-putaway
- **In Progress**: Sedang proses putaway
- **Completed**: Sudah di-putaway

### **OPNAME STATUS**
- **Pending**: Belum di-opname
- **In Progress**: Sedang opname
- **Completed**: Sudah di-opname

---

## 🔗 Integrasi Antar Modul

### **Products ↔ Inventory**
- Product.rak → InventoryRakStock.rak
- Product.sku → Stock.sku
- Product dimensions → Slotting algorithm

### **Inventory ↔ Orders**
- Stock.quantity → Order availability check
- Stock.quantity_locked → Batch generation
- StockCardEntry → Order fulfillment tracking

### **Orders ↔ Fulfillment**
- Order.id_pesanan → BatchItem → ReadyToPrint
- Order.status → Batch status tracking
- Order history → Fulfillment history

### **Inventory ↔ Fulfillment**
- Stock.quantity_locked → Batch picking
- InventoryRakStock → Picking location
- StockCardEntry → Fulfillment audit trail

### **Data Flow Summary**
```
Products (Master) → Inventory (Stock) → Orders (Demand) → Fulfillment (Execution)
     ↓                    ↓                    ↓                    ↓
Slotting ←→ Putaway ←→ Opname ←→ Return ←→ Batch Picking ←→ Shipping
```

---

## 🎯 Key Features

### **1. Real-time Stock Management**
- Multi-location tracking (Stock + InventoryRakStock)
- Lock mechanism untuk batch picking
- Virtual quantity calculation

### **2. Comprehensive Audit Trail**
- StockCardEntry untuk semua transaksi
- BatchItemLog untuk picking activities
- Order history untuk fulfillment tracking

### **3. Flexible Batch Management**
- Dynamic batch generation
- Transfer antar batch
- Keep mechanism untuk partial fulfillment

### **4. Advanced Slotting**
- ABC analysis integration
- Dimensional compatibility
- Capacity optimization

### **5. Integrated Return Management**
- Session-based return processing
- Condition tracking
- Stock reconciliation

### **6. Mobile-friendly Interface**
- Scan-based operations
- Responsive design
- Real-time updates

---

## 📋 Business Rules

### **Stock Management**
1. `quantity_ready_virtual = quantity - quantity_locked`
2. `quantity_total_virtual = quantity + quantity_putaway`
3. Tidak boleh negative stock
4. Lock quantity tidak boleh melebihi available quantity

### **Batch Management**
1. Batch harus di-close sebelum create batch baru
2. Transfer batch hanya untuk batch yang open
3. Keep quantity tidak boleh melebihi picked quantity

### **Putaway Rules**
1. Produk harus di-putaway sebelum bisa di-pick
2. Rak capacity tidak boleh terlampaui
3. Dimensional compatibility check

### **Opname Rules**
1. Opname harus dilakukan secara periodik
2. Selisih > threshold harus di-review
3. Koreksi harus diapprove oleh supervisor

---

## 🔧 Technical Architecture

### **Database Design**
- **Normalized**: Master data terpisah dari transaction data
- **Denormalized**: Performance optimization untuk reporting
- **Indexed**: Optimized untuk query patterns

### **API Design**
- **RESTful**: Standard HTTP methods
- **JSON**: Data exchange format
- **Authentication**: Session-based security

### **Frontend**
- **Bootstrap**: Responsive UI framework
- **DataTables**: Advanced table functionality
- **jQuery**: JavaScript library
- **Mobile-first**: Optimized for mobile devices

### **Backend**
- **Django**: Python web framework
- **PostgreSQL**: Primary database
- **Celery**: Background task processing
- **Redis**: Caching and session storage

---

*Dokumentasi ini mencakup seluruh sistem ERP ALFA yang sedang beroperasi. Semua workflow dan proses sudah diimplementasikan dan berfungsi sesuai dengan kebutuhan warehouse e-commerce.*



