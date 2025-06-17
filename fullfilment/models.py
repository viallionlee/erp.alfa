from django.db import models
from django.contrib.postgres.fields import JSONField
from django.utils import timezone

# Create your models here.

class BatchList(models.Model):
    nama_batch = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status_batch = models.CharField(max_length=50, default='pending')

    def __str__(self):
        return self.nama_batch

class BatchItem(models.Model):
    batchlist = models.ForeignKey(BatchList, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True, blank=True)
    jumlah = models.IntegerField()
    jumlah_ambil = models.IntegerField(default=0)
    status_ambil = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.batchlist.nama_batch} - {self.product.nama_produk}"

class FilteredOrders(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    filter_params = models.JSONField()
    orders = models.JSONField()

    def __str__(self):
        return f"FilteredOrders {self.id} at {self.created_at}"

class ExportedOrder(models.Model):
    id = models.AutoField(primary_key=True)
    id_pesanan = models.CharField(max_length=100)
    product_id = models.CharField(max_length=100)
    export_time = models.DateTimeField(auto_now_add=True)
    exported_by = models.CharField(max_length=100, blank=True, null=True)
    extra_data = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"ExportedOrder {self.id_pesanan} - {self.product_id}"

class ReadyToPrint(models.Model):
    batchlist = models.ForeignKey(BatchList, on_delete=models.CASCADE)
    id_pesanan = models.CharField(max_length=100)
    brand = models.CharField(max_length=100, null=True, blank=True)  # Added brand field
    order_type = models.CharField(max_length=20, null=True, blank=True)  # Added order_type field
    status_print = models.CharField(max_length=20, default='pending')  # 'pending' or 'printed'
    printed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"ReadyToPrint {self.id_pesanan} ({self.status_print})"
