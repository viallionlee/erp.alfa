from django.db import models
from django.contrib.postgres.fields import JSONField
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import F, Sum, OuterRef, Subquery, Min, Window
from django.db.models.functions import Coalesce, RowNumber
from django.db.models import Count, Max
from products.models import Product

# Create your models here.

class OrdersCheckingHistory(models.Model):
    id_pesanan = models.CharField(max_length=100, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    scan_time = models.DateTimeField(auto_now_add=True)
    barcode_scanned = models.CharField(max_length=100)
    
    class Meta:
        verbose_name_plural = "Orders Checking Histories"
        ordering = ['-scan_time']

    def __str__(self):
        return f"{self.id_pesanan} scanned by {self.user} at {self.scan_time}"

class BatchList(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
    ]
    nama_batch = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status_batch = models.CharField(max_length=50, default='pending', choices=STATUS_CHOICES)
    close_count = models.IntegerField(default=0, help_text="Jumlah kali batch ini di-close")

    def __str__(self):
        return self.nama_batch

    class Meta:
        verbose_name = "Batch List"
        verbose_name_plural = "Batch Lists"
        permissions = [
            # === DESKTOP PERMISSIONS ===
            # Permission untuk module Shipping (Desktop)
            ("view_desktop_shipping_module", "Can access desktop shipping module (scanshipping + order-shipping-list)"),
            # Permission untuk module Packing (Desktop)
            ("view_desktop_packing_module", "Can access desktop packing module (scanpacking + order-packing-list)"),
            # Permission untuk module Picking (Desktop)
            ("view_desktop_picking_module", "Can access desktop picking module (scanpicking + order-checking-list)"),
            # Permission untuk Desktop Batchpicking
            ("view_desktop_batchpicking", "Can access desktop batchpicking module"),
            # Permission untuk Desktop Batch List
            ("view_desktop_batchlist", "Can view desktop batch list"),
            # Permission untuk Desktop Ready to Print
            ("view_desktop_readytoprint", "Can access desktop readytoprint module"),
            # Permission untuk Desktop Generate Batch
            ("view_desktop_generatebatch", "Can view desktop generate batch page"),
            ("change_desktop_generatebatch", "Can perform actions on desktop generate batch (filter, clear, check stock, generate batchlist)"),
            ("generate_desktop_batch", "Can generate desktop batch and access printed list"),
            # Permission untuk Desktop Return List
            ("view_desktop_returnlist", "Can access desktop return list module"),
            
            # === MOBILE PERMISSIONS ===
            # Permission untuk module Shipping (Mobile)
            ("view_mobile_shipping_module", "Can access mobile shipping module (scanshipping + order-shipping-list)"),
            # Permission untuk module Packing (Mobile)
            ("view_mobile_packing_module", "Can access mobile packing module (scanpacking + order-packing-list)"),
            # Permission untuk module Picking (Mobile)
            ("view_mobile_picking_module", "Can access mobile picking module (scanpicking + order-checking-list)"),
            # Permission untuk Mobile Batchpicking
            ("view_mobile_batchpicking", "Can access mobile batchpicking module"),
            # Permission untuk Mobile Batch List
            ("view_mobile_batchlist", "Can view mobile batch list"),
            # Permission untuk Mobile Ready to Print
            ("view_mobile_readytoprint", "Can access mobile readytoprint module"),
            # Permission untuk Mobile Generate Batch
            ("view_mobile_generatebatch", "Can view mobile generate batch page"),
            ("change_mobile_generatebatch", "Can perform actions on mobile generate batch (filter, clear, check stock, generate batchlist)"),
            ("generate_mobile_batch", "Can generate mobile batch and access printed list"),
            # Permission untuk Mobile Return List
            ("view_mobile_returnlist", "Can access mobile return list module"),
            
        ]

class BatchItem(models.Model):
    batchlist = models.ForeignKey(BatchList, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, null=True, blank=True)
    jumlah = models.IntegerField()
    jumlah_ambil = models.IntegerField(default=0)
    jumlah_transfer = models.IntegerField(default=0)  # Tambahkan field ini
    jumlah_terpakai = models.IntegerField(default=0)  # Yang sudah digunakan untuk ReadyToPrint
    jumlah_keep = models.IntegerField(default=0) # New field: jumlah_keep
    status_ambil = models.CharField(max_length=50)
    one_count = models.IntegerField(default=0)
    duo_count = models.IntegerField(default=0)
    tri_count = models.IntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='completed_batch_items')
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.batchlist.nama_batch} - {self.product.nama_produk}"

class BatchOrderLog(models.Model):
    """Mencatat semua perubahan signifikan pada order di dalam batch: cancel, erase, transfer."""
    ACTION_CHOICES = [
        ('CANCEL', 'Cancel Order'),
        ('ERASE', 'Erase from Batch'),
        ('TRANSFER', 'Transfer Batch'),
    ]
    
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action_type = models.CharField(max_length=10, choices=ACTION_CHOICES, db_index=True)
    
    batch_source = models.ForeignKey(BatchList, on_delete=models.SET_NULL, null=True, related_name='source_logs', help_text="Batch asal")
    batch_destination = models.ForeignKey(BatchList, on_delete=models.SET_NULL, null=True, blank=True, related_name='destination_logs', help_text="Batch tujuan (khusus transfer)")
    
    id_pesanan = models.CharField(max_length=255, db_index=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    sku = models.CharField(max_length=100, help_text="Denormalized SKU for history")
    product_name = models.CharField(max_length=255, blank=True, null=True, help_text="Denormalized product name")
    quantity = models.IntegerField()
    
    notes = models.TextField(blank=True, null=True, help_text="Alasan atau detail tambahan")

    def __str__(self):
        return f"{self.action_type} - {self.id_pesanan} ({self.sku}) by {self.user.username if self.user else 'System'} at {self.timestamp}"

    class Meta:
        verbose_name = "Batch Order Log"
        verbose_name_plural = "Batch Order Logs"
        ordering = ['-timestamp']


class ReadyToPrint(models.Model):
    id_pesanan = models.CharField(max_length=255, unique=True)
    batchlist = models.ForeignKey(BatchList, on_delete=models.CASCADE, related_name='ready_to_print_items')
    status_print = models.CharField(max_length=20, default='pending')
    printed_at = models.DateTimeField(null=True, blank=True)
    copied_at = models.DateTimeField(null=True, blank=True)
    handed_over_at = models.DateTimeField(null=True, blank=True)
    printed_via = models.CharField(max_length=20, null=True, blank=True, help_text="Metode pencetakan (e.g., SAT, PRIO, MIX)")
    printed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='printed_orders')

    def __str__(self):
        return f"{self.id_pesanan} - {self.status_print}"

class BatchItemLog(models.Model):
    waktu = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    batch = models.ForeignKey('BatchList', on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    jumlah_input = models.IntegerField(default=1)
    jumlah_ambil = models.IntegerField()

    class Meta:
        verbose_name = "Batch Item Log"
        verbose_name_plural = "Batch Item Logs"
        ordering = ['-waktu']

    def __str__(self):
        return f"{self.waktu} - {self.user} - {self.batch} - {self.product} - {self.jumlah_ambil}"

# NEW MODEL: OrderCancelLog
class OrderCancelLog(models.Model):
    order_id_scanned = models.CharField(max_length=255, db_index=True, help_text="ID Pesanan atau AWB yang discan")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, help_text="User yang melakukan scan")
    scan_time = models.DateTimeField(auto_now_add=True)
    status_pembayaran_at_scan = models.CharField(max_length=50, blank=True, null=True, help_text="Status Pembayaran Order saat discan")
    status_fulfillment_at_scan = models.CharField(max_length=50, blank=True, null=True, help_text="Status Fulfillment Order saat discan")
    status_retur = models.CharField(max_length=1, default='N', help_text="Status retur: N=Belum diproses, Y=Sudah diproses retur")

    class Meta:
        verbose_name = "Order Cancel Log"
        verbose_name_plural = "Order Cancel Logs"
        ordering = ['-scan_time']

    def __str__(self):
        return f"Log Cancel: {self.order_id_scanned} by {self.user.username if self.user else 'N/A'} (Retur: {self.status_retur})"

class ReturnSession(models.Model):
    kode = models.CharField(max_length=50, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='open', choices=[
        ('open', 'Open'),
        ('closed', 'Closed'),
    ])
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.kode}"

class ReturnItem(models.Model):
    session = models.ForeignKey(ReturnSession, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)

    qty = models.PositiveIntegerField(default=0) # Diperbarui: qty_target -> qty
    qty_scanned = models.PositiveIntegerField(default=0)
    qty_putaway = models.PositiveIntegerField(default=0) # Field baru untuk tracking putaway

    qc_status = models.CharField(max_length=10, choices=[
        ('pending', 'Pending'),
        ('pass', 'Passed QC'),
        ('fail', 'Failed QC'),
    ], default='pending')
    qc_notes = models.TextField(blank=True, null=True)

    putaway_status = models.CharField(max_length=10, choices=[
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('completed', 'Completed'),
    ], default='pending')

    last_scanned_at = models.DateTimeField(null=True, blank=True)
    last_scanned_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.product} x {self.qty} (Session: {self.session.kode})" # Diperbarui: qty_target -> qty

class ReturnScanLog(models.Model):
    return_item = models.ForeignKey(ReturnItem, on_delete=models.CASCADE, related_name='scanlogs', null=True, blank=True) # Tambahkan null=True, blank=True
    scanned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    scanned_at = models.DateTimeField(auto_now_add=True)
    qty = models.PositiveIntegerField(default=1)
    barcode = models.CharField(max_length=100)
    notes = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Scan {self.barcode} x{self.qty} at {self.scanned_at}"

class ReturnSourceLog(models.Model):
    return_item = models.ForeignKey('ReturnItem', on_delete=models.CASCADE, related_name='sources')
    session = models.ForeignKey('ReturnSession', on_delete=models.CASCADE, related_name='source_logs', null=True, blank=True)
    order_id = models.CharField(max_length=50, null=True, blank=True)
    batch = models.ForeignKey('BatchList', null=True, blank=True, on_delete=models.SET_NULL)
    qty = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        parts = []
        if self.order_id:
            parts.append(f"Order {self.order_id}")
        if self.batch:
            parts.append(f"Batch {self.batch.nama_batch}")
        # Tambahkan sesi ke string representasi jika ada
        if self.session:
            parts.append(f"Session {self.session.kode}")
        return f"{' & '.join(parts)} - {self.qty}"
