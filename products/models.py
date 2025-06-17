from django.db import models
from django.conf import settings

# Create your models here.

class Product(models.Model):
    sku = models.CharField(max_length=100, unique=True)
    barcode = models.CharField(max_length=100, unique=True)
    nama_produk = models.CharField(max_length=255)
    variant_produk = models.CharField(max_length=255, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    rak = models.CharField(max_length=100, blank=True, null=True)
    photo = models.ImageField(upload_to='product_photos/', blank=True, null=True)

    def __str__(self):
        return self.nama_produk

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

class ProductsBundling(models.Model):
    sku_bundling = models.CharField(max_length=100, unique=True)
    sku_list = models.TextField(help_text="Daftar SKU dipisahkan koma, contoh: SKU1,SKU2,SKU3")

    def __str__(self):
        return self.sku_bundling

class Rak(models.Model):
    kode_rak = models.CharField(max_length=20, unique=True)
    nama_rak = models.CharField(max_length=100)
    panjang_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    lebar_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    tinggi_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    kapasitas_kg = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    lokasi = models.CharField(max_length=100, blank=True, null=True)
    keterangan = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'products_rak'

    def __str__(self):
        return f"{self.kode_rak} - {self.nama_rak}"

