from django.db import models
from products.models import Product

class DemoExtract(models.Model):
    sku = models.CharField(max_length=100)
    jumlah = models.IntegerField()
    id_pesanan = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=50, blank=True, null=True)
    product = models.ForeignKey(Product, blank=True, null=True, on_delete=models.SET_NULL)
    status_bundle = models.CharField(max_length=1, blank=True, null=True)
    status_order = models.CharField(max_length=50, blank=False, null=False, default='pending')

    def __str__(self):
        return f"{self.sku} - {self.jumlah}"
