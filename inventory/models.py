from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

# Create your models here.

class Stock(models.Model):
    product = models.OneToOneField('products.Product', on_delete=models.PROTECT, related_name='stock', null=True, blank=True)
    sku = models.CharField(max_length=100, unique=True, db_index=True, null=True, blank=True)
    quantity = models.IntegerField(default=0)  # Stok yang sudah di rak (ready)
    quantity_locked = models.IntegerField(default=0)  # Stok yang di-lock untuk batch
    quantity_putaway = models.IntegerField(default=0)  # Stok yang belum di putaway

    @property
    def quantity_ready_virtual(self):
        """Menghitung stok siap jual secara on-the-fly. Ini properti virtual."""
        return self.quantity - self.quantity_locked

    @property
    def quantity_total_virtual(self):
        """Total stok (ready + putaway)"""
        return self.quantity + self.quantity_putaway

    def __str__(self):
        return f"Stok untuk {self.sku}: Ready={self.quantity}, Locked={self.quantity_locked}, Putaway={self.quantity_putaway}"

    # def save(self, *args, **kwargs):
    #     self.quantity_ready = self.quantity - self.quantity_locked
    #     super(Stock, self).save(*args, **kwargs)





class Inbound(models.Model):
    id = models.AutoField(primary_key=True)
    nomor_inbound = models.CharField(max_length=100, unique=True, null=True, blank=True)
    tanggal = models.DateTimeField(null=True, blank=True)
    keterangan = models.TextField(blank=True, null=True)
    
    # Supplier (optional)
    supplier = models.ForeignKey('inventory.Supplier', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Transfer antar gudang
    from_warehouse = models.CharField(max_length=100, blank=True, null=True, help_text="Gudang asal")
    to_warehouse = models.CharField(max_length=100, blank=True, null=True, help_text="Gudang tujuan")
    
    # Link ke Purchase Order (optional, untuk tracking)
    po = models.ForeignKey('purchasing.PurchaseOrder', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Tracking fields
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='inbounds_created'
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='inbounds_received'
    )
    received_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.nomor_inbound or f"Inbound {self.id}"

class InboundItem(models.Model):
    inbound = models.ForeignKey(Inbound, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    quantity = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.inbound.nomor_inbound if self.inbound else '-'} - {self.product.nama_produk if self.product else '-'}"

class HistoryImportStock(models.Model):
    import_time = models.DateTimeField(auto_now_add=True)
    imported_by = models.CharField(max_length=100, blank=True, null=True)
    file_name = models.CharField(max_length=255)
    notes = models.TextField(blank=True, null=True)
    success_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.import_time} - {self.file_name}"

class InventoryRakStock(models.Model):
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    rak = models.ForeignKey('inventory.Rak', on_delete=models.PROTECT)
    quantity = models.IntegerField(default=0)
    quantity_opname = models.IntegerField(default=0)  # NEW: Quantity dari opname yang belum selesai
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'rak')
        indexes = [
            models.Index(fields=['rak', 'quantity']),
            models.Index(fields=['quantity']),
        ]

    def __str__(self):
        return f"{self.product} di {self.rak} (qty: {self.quantity}, opname: {self.quantity_opname})"
    
    @property
    def quantity_total(self):
        """Total quantity termasuk opname yang belum selesai"""
        return self.quantity + self.quantity_opname

class Supplier(models.Model):
    nama_supplier = models.CharField(max_length=255)
    nomor_telepon = models.CharField(max_length=50, blank=True, null=True)
    alamat = models.TextField(blank=True, null=True)
    kota = models.CharField(max_length=100, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.nama_supplier


# --- Tambahan: Model Opname ---
User = get_user_model()

class OpnameQueue(models.Model):
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    lokasi = models.CharField(max_length=100, blank=True, default='')
    terakhir_opname = models.DateTimeField(null=True, blank=True)
    prioritas = models.IntegerField(default=10)
    sumber_prioritas = models.CharField(max_length=30, default='cycle_count')
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('in_progress', 'In Progress'), ('done', 'Done')], default='pending')
    ditambahkan_pada = models.DateTimeField(auto_now_add=True)
    catatan = models.TextField(blank=True, default='')

    class Meta:
        unique_together = ('product', 'status')

    def __str__(self):
        return f"{self.product} - {self.status} - Prioritas {self.prioritas}"

class OpnameHistory(models.Model):
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    tanggal_opname = models.DateTimeField(auto_now_add=True)
    qty_fisik = models.IntegerField()
    qty_sistem = models.IntegerField()
    selisih = models.IntegerField()
    petugas_opname = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    catatan = models.TextField(blank=True, default='')

    def __str__(self):
        return f"{self.product} - {self.tanggal_opname} - Selisih {self.selisih}"

class StockCardEntry(models.Model):
    TIPE_PERGERAKAN = [
        ('inbound', 'Inbound (+)'),
        ('reverse_inbound', 'Reverse Inbound (-)'),
        ('purchase', 'Purchase (+)'),
        ('outbound', 'Outbound (-)'),
        ('reverse_outbound', 'Reverse Outbound (+)'),
        ('opname_in', 'Opname In (+)'),
        ('opname_out', 'Opname Out (-)'),
        ('kunci_stok', 'Kunci Stok (Batch) (-)'),
        ('reopen_batch', 'Batal Kunci Stok (Re-Open) (+)'),
        ('close_batch', 'Close Batch (-)'),
        ('reverse_batch', 'Reverse Batch (+)'),
        ('return_stock', 'Return Stock (+)'),
        ('reject_stock', 'Reject Stock (-)'),
        ('pindah_rak', 'Pindah Rak'),
        ('pindah_gudang', 'Pindah Gudang'),
        ('koreksi_stok', 'Koreksi Stok (+/-)'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('voided', 'Voided'),
    ]

    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='kartu_stok')
    waktu = models.DateTimeField(auto_now_add=True, db_index=True)
    tipe_pergerakan = models.CharField(max_length=30, choices=TIPE_PERGERAKAN)
    
    qty = models.IntegerField()  # Jumlah perubahan (+/-)
    qty_awal = models.IntegerField()
    qty_akhir = models.IntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active', db_index=True)
    
    # Generic Foreign Key untuk referensi
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    reference = GenericForeignKey('content_type', 'object_id')
    
    notes = models.CharField(max_length=255, blank=True, default='') # Diganti dari keterangan
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['-waktu']
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        user_str = f" oleh {self.user}" if self.user else ""
        return f"{self.product} | {self.tipe_pergerakan} ({self.qty}) | {self.waktu.strftime('%Y-%m-%d %H:%M')}{user_str}"

class InventoryRakStockLog(models.Model):
    TIPE_PERGERAKAN = [
        ('putaway_masuk', 'Putaway Masuk (+)'),
        ('picking_keluar', 'Picking Keluar (-)'),
        ('transfer_masuk', 'Transfer Rak Masuk (+)'),
        ('transfer_keluar', 'Transfer Rak Keluar (-)'),
        ('koreksi', 'Koreksi Stok (+/-)'),
        ('return_masuk', 'Return Masuk (+)'),
        ('return_keluar', 'Return Keluar (-)'),
    ]
    
    produk = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    rak = models.ForeignKey('inventory.Rak', on_delete=models.PROTECT)
    tipe_pergerakan = models.CharField(max_length=20, choices=TIPE_PERGERAKAN)
    
    qty = models.IntegerField()  # Jumlah perubahan (+/-)
    qty_awal = models.IntegerField()
    qty_akhir = models.IntegerField()
    
    # Generic Foreign Key untuk semua jenis referensi
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    referensi = GenericForeignKey('content_type', 'object_id')
    
    waktu_buat = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    catatan = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-waktu_buat']
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["produk", "rak"]),
            models.Index(fields=["waktu_buat"]),
        ]

    def __str__(self):
        user_str = f" oleh {self.user}" if self.user else ""
        referensi_str = f" | Ref: {self.referensi}" if self.referensi else ""
        return f"{self.produk} | {self.rak} | {self.tipe_pergerakan} ({self.qty}) | {self.waktu_buat.strftime('%Y-%m-%d %H:%M')}{user_str}{referensi_str}"

class FullOpnameSession(models.Model):
    """
    Master session untuk full opname - menaungi multiple sesi opname rak
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('in_progress', 'Sedang Berlangsung'),
        ('completed', 'Selesai'),
        ('cancelled', 'Dibatalkan'),
    ]
    
    session_code = models.CharField(max_length=50, unique=True)
    nama_opname = models.CharField(max_length=200)  # Contoh: "Opname Bulan Juli 2024"
    tanggal_mulai = models.DateTimeField(auto_now_add=True)
    tanggal_selesai = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    catatan = models.TextField(blank=True, null=True)
    
    # User management
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='full_opname_sessions_created')
    supervisor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='full_opname_sessions_supervised')
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='full_opname_sessions_completed')
    
    # Target rak (opsional - jika kosong berarti semua rak)
    target_raks = models.ManyToManyField('inventory.Rak', blank=True, related_name='full_opname_sessions')
    
    class Meta:
        ordering = ['-tanggal_mulai']
    
    def __str__(self):
        return f"{self.nama_opname} - {self.session_code} ({self.status})"
    
    @property
    def total_rak_sessions(self):
        """Total sesi opname rak dalam full opname ini"""
        return self.rak_opname_sessions.count()
    
    @property
    def completed_rak_sessions(self):
        """Total sesi opname rak yang sudah selesai"""
        return self.rak_opname_sessions.filter(status='selesai').count()
    
    @property
    def total_verified_items(self):
        """Total item yang sudah diverifikasi di semua sesi rak"""
        total_verified = 0
        total_items = 0
        for rak_session in self.rak_opname_sessions.all():
            total_verified += rak_session.verified_items_count
            total_items += rak_session.total_items
        return total_verified, total_items
    
    @property
    def progress_percentage(self):
        """Progress dalam persentase berdasarkan item yang sudah diverifikasi"""
        total_verified, total_items = self.total_verified_items
        if total_items == 0:
            return 0
        return (total_verified / total_items) * 100
    
    @property
    def total_selisih(self):
        """Total selisih dari semua sesi rak yang sudah selesai"""
        total = 0
        for rak_session in self.rak_opname_sessions.filter(status='selesai'):
            total += rak_session.total_selisih
        return total
    
    def save(self, *args, **kwargs):
        if not self.session_code:
            # Generate session code: FULL-OPNAME-{TIMESTAMP}
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            self.session_code = f"FULL-OPNAME-{timestamp}"
        super().save(*args, **kwargs)


class RakOpnameSession(models.Model):
    """
    Session untuk opname rak - untuk tracking batch opname
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'), # Mengubah 'Sedang Berlangsung'
        ('selesai', 'Completed'),     # Mengubah 'Selesai'
        ('dibatalkan', 'Cancelled'),   # Mengubah 'Dibatalkan'
    ]
    
    TIPE_SESSION_CHOICES = [
        ('full_opname', 'Full Opname'),
        ('reguler_opname', 'Reguler Opname'),
        ('partial_opname', 'Partial Opname'),
    ]
    
    # Relasi ke Full Opname Session (parent)
    full_opname_session = models.ForeignKey(FullOpnameSession, on_delete=models.CASCADE, related_name='rak_opname_sessions', null=True, blank=True)
    
    rak = models.ForeignKey('inventory.Rak', on_delete=models.PROTECT)
    session_code = models.CharField(max_length=50, unique=True)
    tipe_session = models.CharField(max_length=20, choices=TIPE_SESSION_CHOICES, default='reguler_opname', help_text="Tipe sesi opname: Full Opname (semua rak), Reguler Opname (1 rak), Partial Opname (pilih produk)")
    tanggal_mulai = models.DateTimeField(auto_now_add=True)
    tanggal_selesai = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    catatan = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='opname_sessions_created')
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='opname_sessions_completed')
    
    class Meta:
        ordering = ['-tanggal_mulai']
    
    def __str__(self):
        return f"Opname {self.rak.kode_rak} - {self.session_code} ({self.status})"
    
    @property
    def total_items(self):
        return self.items.count()
    
    @property
    def total_selisih(self):
        return sum(item.qty_selisih or 0 for item in self.items.all())
    
    @property
    def completed_items_count(self):
        """Jumlah item yang sudah diopname (qty_fisik tidak null)"""
        return self.items.filter(qty_fisik__isnull=False).count()
    
    @property
    def verified_items_count(self):
        """Jumlah item yang sudah diverifikasi (is_verified = True)"""
        return self.items.filter(is_verified=True).count()
    
    @property
    def progress_percentage(self):
        """Progress dalam persentase berdasarkan item yang sudah diverifikasi"""
        if self.total_items == 0:
            return 0
        return (self.verified_items_count / self.total_items) * 100
    
    def save(self, *args, **kwargs):
        if not self.session_code:
            # Generate session code: OPNAME-{RAK}-{TIMESTAMP}
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            self.session_code = f"OPNAME-{self.rak.kode_rak}-{timestamp}"
        super().save(*args, **kwargs)


class RakOpnameItem(models.Model):
    """
    Item opname untuk setiap produk dalam session opname
    """
    session = models.ForeignKey(RakOpnameSession, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    qty_sistem = models.IntegerField()  # Quantity di sistem sebelum opname
    qty_fisik = models.IntegerField(null=True, blank=True)  # Quantity hasil opname fisik
    qty_selisih = models.IntegerField(null=True, blank=True)  # Selisih (fisik - sistem)
    catatan = models.TextField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('session', 'product')
        ordering = ['product__nama_produk']
    
    def __str__(self):
        return f"{self.product.sku} - Sistem: {self.qty_sistem}, Fisik: {self.qty_fisik or 'Belum diopname'}"
    
    def save(self, *args, **kwargs):
        if self.qty_fisik is not None and self.qty_sistem is not None:
            self.qty_selisih = self.qty_fisik - self.qty_sistem
        super().save(*args, **kwargs)


class RakTransferSession(models.Model):
    """
    Sesi untuk transfer produk antar rak
    """
    MODE_CHOICES = [
        ('direct', 'Transfer Langsung'),
        ('transfer_putaway', 'Transfer Putaway'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('in_progress', 'Sedang Berlangsung'),
        ('ready_for_putaway', 'Siap Putaway'),
        ('selesai', 'Selesai'),
        ('dibatalkan', 'Dibatalkan'),
    ]
    
    session_code = models.CharField(max_length=50, unique=True)
    rak_asal = models.ForeignKey('inventory.Rak', on_delete=models.PROTECT, related_name='transfers_from')
    rak_tujuan = models.ForeignKey('inventory.Rak', on_delete=models.PROTECT, related_name='transfers_to')
    tanggal_transfer = models.DateTimeField(auto_now_add=True)
    tanggal_selesai = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    catatan = models.TextField(blank=True, null=True)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='direct')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='transfer_sessions_created')
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer_sessions_completed')
    
    class Meta:
        ordering = ['-tanggal_transfer']
    
    def __str__(self):
        return f"Transfer {self.rak_asal.kode_rak} → {self.rak_tujuan.kode_rak} - {self.session_code}"
    
    def save(self, *args, **kwargs):
        if not self.session_code:
            # Generate session code: TRANSFER-{FROM}-{TO}-{TIMESTAMP}
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            self.session_code = f"TRANSFER-{self.rak_asal.kode_rak}-{self.rak_tujuan.kode_rak}-{timestamp}"
        super().save(*args, **kwargs)


class RakTransferItem(models.Model):
    """
    Item transfer untuk setiap produk dalam sesi transfer rak
    """
    session = models.ForeignKey(RakTransferSession, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    qty_transfer = models.IntegerField()  # Quantity yang ditransfer
    qty_asal_sebelum = models.IntegerField()  # Quantity di rak asal sebelum transfer
    qty_asal_sesudah = models.IntegerField()  # Quantity di rak asal setelah transfer
    qty_tujuan_sebelum = models.IntegerField()  # Quantity di rak tujuan sebelum transfer
    qty_tujuan_sesudah = models.IntegerField()  # Quantity di rak tujuan setelah transfer
    catatan = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('session', 'product')
        ordering = ['product__nama_produk']
    
    def __str__(self):
        return f"{self.product.sku} - Transfer {self.qty_transfer} pcs"


class Rak(models.Model):
    # Choices untuk lokasi
    LOKASI_CHOICES = [
        ('DEKAT', 'DEKAT'),
        ('SEDANG', 'SEDANG'),
        ('JAUH', 'JAUH'),
        ('BEDA_GUDANG', 'BEDA GUDANG'),
    ]
    
    kode_rak = models.CharField(max_length=20, unique=True)
    nama_rak = models.CharField(max_length=100)
    barcode_rak = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    panjang_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    lebar_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    tinggi_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    kapasitas_kg = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    lokasi = models.CharField(max_length=20, choices=LOKASI_CHOICES, blank=True, null=True, help_text="Prioritas slotting: DEKAT (tinggi) → BEDA GUDANG (rendah)")
    keterangan = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'inventory_rak'

    def __str__(self):
        return f"{self.kode_rak} - {self.nama_rak}"
    
    @property
    def lokasi_priority_score(self):
        """Mendapatkan priority score untuk slotting berdasarkan lokasi"""
        priority_map = {
            'DEKAT': 4,      # Priority tertinggi
            'SEDANG': 3,     # Priority tinggi
            'JAUH': 2,       # Priority sedang
            'BEDA_GUDANG': 1, # Priority terendah
        }
        return priority_map.get(self.lokasi, 0) if self.lokasi else 0
    
    @property
    def dimensions_display(self):
        """Format dimensi untuk display"""
        dimensions = []
        if self.lebar_cm:
            dimensions.append(f"{float(self.lebar_cm):.1f}cm")
        if self.panjang_cm:
            dimensions.append(f"{float(self.panjang_cm):.1f}cm")
        if self.tinggi_cm:
            dimensions.append(f"{float(self.tinggi_cm):.1f}cm")
        
        return " x ".join(dimensions) if dimensions else "-"


class RakCapacity(models.Model):
    """
    Model untuk tracking kapasitas front yang tersedia di rak
    """
    rak = models.OneToOneField(Rak, on_delete=models.CASCADE, related_name='capacity')
    available_front = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Front space yang masih tersedia (cm)")
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Rak Capacity"
        verbose_name_plural = "Rak Capacities"
    
    def __str__(self):
        return f"{self.rak.kode_rak} - Tersedia: {self.available_front}cm"
    
    @property
    def used_front(self):
        """Front space yang sudah terpakai berdasarkan 3 dimensi"""
        if not self.rak.lebar_cm:
            return 0
        
        total_used_width = 0
        stocks = InventoryRakStock.objects.filter(rak=self.rak, quantity__gt=0).select_related('product')
        
        for stock in stocks:
            if stock.product.lebar_cm and stock.product.panjang_cm and stock.product.tinggi_cm:
                # Hitung berapa width slot yang dibutuhkan
                width_slots_needed = self._calculate_width_slots_needed(stock.product, stock.quantity)
                total_used_width += width_slots_needed * float(stock.product.lebar_cm)
            elif stock.product.lebar_cm:
                # Jika hanya width yang ada, gunakan perhitungan lama
                total_used_width += float(stock.product.lebar_cm) * stock.quantity
        
        return total_used_width
    
    def _calculate_width_slots_needed(self, product, quantity):
        """
        Hitung berapa slot width yang dibutuhkan berdasarkan 3 dimensi
        Mempertimbangkan semua kemungkinan orientasi produk (bisa ditidurkan/dirotasi)
        """
        if not (self.rak.lebar_cm and self.rak.panjang_cm and self.rak.tinggi_cm and 
                product.lebar_cm and product.panjang_cm and product.tinggi_cm):
            return 1  # Default jika ada dimensi yang kosong
        
        rak_width = float(self.rak.lebar_cm)
        rak_length = float(self.rak.panjang_cm)
        rak_height = float(self.rak.tinggi_cm)
        
        product_width = float(product.lebar_cm)
        product_length = float(product.panjang_cm)
        product_height = float(product.tinggi_cm)
        
        # Coba semua kemungkinan orientasi produk
        orientations = [
            # Orientasi normal: panjang x tinggi
            (product_length, product_height),
            # Orientasi ditidurkan: tinggi x panjang (jika tinggi produk jadi panjang)
            (product_height, product_length),
        ]
        
        max_products_per_slot = 0
        
        for prod_length, prod_height in orientations:
            # Hitung kapasitas untuk orientasi ini
            products_per_length = int(rak_length / prod_length) if prod_length > 0 else 1
            products_per_height = int(rak_height / prod_height) if prod_height > 0 else 1
            products_per_slot = products_per_length * products_per_height
            
            # Ambil yang maksimal
            max_products_per_slot = max(max_products_per_slot, products_per_slot)
        
        # Hitung berapa slot width yang dibutuhkan
        if max_products_per_slot > 0:
            width_slots_needed = (quantity + max_products_per_slot - 1) // max_products_per_slot  # Ceiling division
        else:
            width_slots_needed = 1
        
        return width_slots_needed
    
    @property
    def total_sku(self):
        """Total jumlah SKU yang berbeda di rak ini"""
        return InventoryRakStock.objects.filter(rak=self.rak, quantity__gt=0).values('product').distinct().count()
    
    @property
    def total_items(self):
        """Total jumlah barang (quantity) di rak ini"""
        return InventoryRakStock.objects.filter(rak=self.rak, quantity__gt=0).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
    
    @property
    def utilization_percentage(self):
        """Persentase penggunaan front space"""
        if not self.rak.lebar_cm:
            return 0
        return ((self.rak.lebar_cm - self.available_front) / self.rak.lebar_cm) * 100
    
    def update_available_front(self):
        """Update available front berdasarkan current stock dengan 3 dimensi"""
        total_used_width = self.used_front
        
        # Convert to float for calculation
        rak_width_float = float(self.rak.lebar_cm) if self.rak.lebar_cm else 0
        
        self.available_front = max(0, rak_width_float - total_used_width)
        self.save()

from django.conf import settings


class RakOpnameLog(models.Model):
    """
    Log untuk aktivitas opname rak
    """
    ACTION_CHOICES = [
        ('create', 'Buat Sesi'),
        ('add_item', 'Tambah Item'),
        ('update_item', 'Update Item'),
        ('delete_item', 'Hapus Item'),
        ('selesai', 'Selesai Opname'),
        ('batal', 'Batalkan Opname'),
    ]
    
    session = models.ForeignKey(RakOpnameSession, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.session} - {self.timestamp.strftime('%d/%m/%Y %H:%M')}"


class PutawaySlottingLog(models.Model):
    """
    Log untuk mencatat proses slotting/putaway produk ke rak tujuan
    
    Workflow:
    1. Inbound/Opname/Return → update Stock.quantity_putaway
    2. Item muncul di putaway list
    3. Slotting (auto/manual) → create object dengan suggested_rak
    4. Scan putaway → update putaway_by, putaway_time, quantity
    """
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    suggested_rak = models.ForeignKey('inventory.Rak', on_delete=models.PROTECT, null=True, blank=True)
    putaway_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    putaway_time = models.DateTimeField(null=True, blank=True)
    quantity = models.IntegerField(default=0)  # Quantity saat scan putaway
    notes = models.TextField(blank=True, null=True, help_text="Catatan slotting/putaway")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Putaway Slotting Log"
        verbose_name_plural = "Putaway Slotting Logs"

    def __str__(self):
        rak_info = f" → {self.suggested_rak.kode_rak}" if self.suggested_rak else " (No Rak)"
        putaway_info = f" oleh {self.putaway_by}" if self.putaway_by else ""
        return f"{self.product.sku}{rak_info} ({self.quantity} pcs){putaway_info}"


@receiver([post_save, post_delete], sender=Stock)
def invalidate_notification_cache_on_stock_change(sender, instance, **kwargs):
    """
    Invalidate notification cache when stock data changes
    """
    try:
        from erp_alfa.views import invalidate_notification_cache
        invalidate_notification_cache()
    except ImportError:
        pass  # Ignore if function not available

@receiver([post_save, post_delete], sender=OpnameQueue)
def invalidate_notification_cache_on_opname_change(sender, instance, **kwargs):
    """
    Invalidate notification cache when opname queue changes
    """
    try:
        from erp_alfa.views import invalidate_notification_cache
        invalidate_notification_cache()
    except ImportError:
        pass  # Ignore if function not available

@receiver([post_save, post_delete], sender='fullfilment.BatchList')
def invalidate_notification_cache_on_batch_change(sender, instance, **kwargs):
    """
    Invalidate notification cache when batch data changes
    """
    try:
        from erp_alfa.views import invalidate_notification_cache
        invalidate_notification_cache()
    except ImportError:
        pass  # Ignore if function not available

@receiver([post_save, post_delete], sender='inventory.RakTransferSession')
def invalidate_notification_cache_on_transfer_change(sender, instance, **kwargs):
    """
    Invalidate notification cache when transfer session changes
    """
    try:
        from erp_alfa.views import invalidate_notification_cache
        invalidate_notification_cache()
    except ImportError:
        pass  # Ignore if function not available

