from django.db import models
from django.conf import settings

# Create your models here.

class Stock(models.Model):
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    sku = models.CharField(max_length=100, blank=True, null=True)  # Tambah kolom sku
    quantity = models.IntegerField(default=0)
    quantity_locked = models.IntegerField(default=0)
    quantity_ready = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        self.quantity_ready = self.quantity - self.quantity_locked
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.nama_produk} - {self.quantity}"

class Inbound(models.Model):
    nomor_inbound = models.CharField(max_length=100, unique=True)
    tanggal = models.DateTimeField()  # Ubah ke DateTimeField
    keterangan = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nomor_inbound

class InboundItem(models.Model):
    inbound = models.ForeignKey(Inbound, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.IntegerField()

    def __str__(self):
        return f"{self.inbound.nomor_inbound} - {self.product.nama_produk}"

class Outbound(models.Model):
    nomor_outbound = models.CharField(max_length=100, unique=True)
    tanggal = models.DateField()
    keterangan = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nomor_outbound

class OutboundItem(models.Model):
    outbound = models.ForeignKey(Outbound, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.IntegerField()

    def __str__(self):
        return f"{self.outbound.nomor_outbound} - {self.product.nama_produk}"

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
    rak = models.ForeignKey('products.Rak', on_delete=models.PROTECT)
    quantity = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'rak')

    def __str__(self):
        return f"{self.product} di {self.rak} (qty: {self.quantity})"

class InventoryRakInboundItem(models.Model):
    inbound_item = models.ForeignKey('inventory.InboundItem', on_delete=models.PROTECT)
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    rak = models.ForeignKey('products.Rak', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=0)
    waktu_input = models.DateTimeField(auto_now_add=True)
    keterangan = models.TextField(blank=True, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.product} ke {self.rak} (qty: {self.quantity}) oleh {self.user}"