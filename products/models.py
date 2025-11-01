from django.db import models
from django.conf import settings

# Create your models here.

class Product(models.Model):
    sku = models.CharField(max_length=100, unique=True)
    barcode = models.CharField(max_length=64, unique=True)
    nama_produk = models.CharField(max_length=255)
    variant_produk = models.CharField(max_length=255, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    rak = models.CharField(max_length=100, blank=True, null=True)
    # Dimensi produk
    panjang_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Panjang produk dalam cm")
    lebar_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Lebar produk dalam cm")
    tinggi_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Tinggi produk dalam cm")
    berat_gram = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Berat produk dalam gram")
    posisi_tidur = models.BooleanField(default=False, help_text='Bisa posisi tidur (hybrid stacking)')
    photo = models.ImageField(upload_to='product_photos/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    # Harga beli
    harga_beli = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Harga beli terakhir")
    last_purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Harga beli dari pembelian terakhir")
    last_purchase_date = models.DateTimeField(null=True, blank=True, help_text="Tanggal pembelian terakhir")
    hpp = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Harga Pokok Penjualan (HPP) - Weighted Average")

    def __str__(self):
        return f"{self.nama_produk} ({self.barcode})"

class ProductImportHistory(models.Model):
    import_time = models.DateTimeField(auto_now_add=True)
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    file_name = models.CharField(max_length=255)
    notes = models.TextField(blank=True, null=True)
    success_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.file_name} at {self.import_time}"

class ProductAddHistory(models.Model):
    """Model untuk mencatat history penambahan produk secara manual"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='add_history')
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    added_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = "Product Add History"
        verbose_name_plural = "Product Add Histories"
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.product.sku} added by {self.added_by} at {self.added_at}"

class ProductsBundling(models.Model):
    sku_bundling = models.CharField(max_length=100, unique=True)
    sku_list = models.TextField(help_text="Daftar SKU dipisahkan koma, contoh: SKU1,SKU2,SKU3")

    def __str__(self):
        return self.sku_bundling

class ProductExtraBarcode(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='extra_barcodes')
    barcode = models.CharField(max_length=64)

    def __str__(self):
        return f"{self.barcode} (extra for {self.product})"

class EditProductLog(models.Model):
    """Model untuk mencatat history perubahan produk"""
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='edit_logs')
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    edited_at = models.DateTimeField(auto_now_add=True)
    
    # Field yang berubah
    field_name = models.CharField(max_length=50, help_text="Nama field yang berubah")
    old_value = models.TextField(blank=True, null=True, help_text="Nilai lama")
    new_value = models.TextField(blank=True, null=True, help_text="Nilai baru")
    
    # Metadata
    change_type = models.CharField(
        max_length=20, 
        choices=[
            ('CREATE', 'Create'),
            ('UPDATE', 'Update'),
            ('DELETE', 'Delete'),
        ],
        default='UPDATE'
    )
    notes = models.TextField(blank=True, null=True, help_text="Catatan tambahan")
    
    # Fields untuk menyimpan informasi produk yang sudah dihapus
    product_sku = models.CharField(max_length=100, blank=True, null=True, help_text="SKU produk (untuk produk yang sudah dihapus)")
    product_name = models.CharField(max_length=255, blank=True, null=True, help_text="Nama produk (untuk produk yang sudah dihapus)")
    product_barcode = models.CharField(max_length=64, blank=True, null=True, help_text="Barcode produk (untuk produk yang sudah dihapus)")
    
    class Meta:
        verbose_name = "Product Edit Log"
        verbose_name_plural = "Product Edit Logs"
        ordering = ['-edited_at']
        indexes = [
            models.Index(fields=['product', '-edited_at']),
            models.Index(fields=['edited_by', '-edited_at']),
            models.Index(fields=['field_name']),
            models.Index(fields=['product_sku']),
            models.Index(fields=['change_type']),
        ]

    def __str__(self):
        if self.product:
            return f"{self.product.sku} - {self.field_name} changed by {self.edited_by} at {self.edited_at}"
        else:
            return f"{self.product_sku} (DELETED) - {self.field_name} changed by {self.edited_by} at {self.edited_at}"

