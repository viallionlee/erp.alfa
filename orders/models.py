from django.db import models
from django.conf import settings
from django.db import transaction

# Create your models here.

class OrderImportHistory(models.Model):
    import_time = models.DateTimeField(auto_now_add=True)
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    file_name = models.CharField(max_length=255)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.file_name} at {self.import_time}"


class Order(models.Model):
    product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True, blank=True)
    tanggal_pembuatan = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=50, blank=True, null=True)
    jenis_pesanan = models.CharField(max_length=50, blank=True, null=True)
    channel = models.CharField(max_length=50, blank=True, null=True)
    nama_toko = models.CharField(max_length=100, blank=True, null=True)
    id_pesanan = models.CharField(max_length=100, db_index=True, blank=True, null=True)
    sku = models.CharField(max_length=100, db_index=True)
    jumlah = models.IntegerField(default=0)
    harga_promosi = models.FloatField(blank=True, null=True)
    catatan_pembeli = models.TextField(blank=True, null=True)
    kurir = models.CharField(max_length=100, blank=True, null=True)
    awb_no_tracking = models.CharField(max_length=100, blank=True, null=True)
    metode_pengiriman = models.CharField(max_length=100, blank=True, null=True)
    kirim_sebelum = models.CharField(max_length=100, blank=True, null=True)
    order_type = models.CharField(max_length=50, blank=True, null=True)
    status_order = models.CharField(max_length=50, blank=True, null=True)
    status_cancel = models.CharField(max_length=50, blank=True, null=True)
    status_retur = models.CharField(max_length=50, blank=True, null=True)
    nama_batch = models.CharField(max_length=100, blank=True, null=True)
    jumlah_ambil = models.IntegerField(default=0)
    status_ambil = models.CharField(max_length=50, blank=True, null=True)
    import_history = models.ForeignKey('OrderImportHistory', on_delete=models.CASCADE, null=True, blank=True, related_name='orders')
    status_stock = models.CharField(max_length=50, blank=True, null=True)
    status_bundle = models.CharField(max_length=50, blank=True, null=True)

    class Meta:     
        indexes = [
            models.Index(fields=['id_pesanan']),
            models.Index(fields=['sku']),
        ]

    def __str__(self):
        return f"Order {self.id_pesanan} - {self.sku}"


class OrderPrintHistory(models.Model):
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE)
    waktu_print = models.DateTimeField(auto_now_add=True)
    status_print = models.CharField(max_length=50)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.order.id_pesanan} - {self.status_print} - {self.waktu_print}"

class OrderPackingHistory(models.Model):
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE)
    waktu_pack = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.order.id_pesanan} - {self.waktu_pack}"

class OrderHandoverHistory(models.Model):
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE)
    waktu_ho = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.order.id_pesanan} - {self.waktu_ho}"

class OrderCukup(models.Model):
    id_pesanan = models.CharField(max_length=100, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.id_pesanan

class OrderTidakCukup(models.Model):
    id_pesanan = models.CharField(max_length=100, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.id_pesanan

class Customer(models.Model):
    LEVEL_CHOICES = [
        ('normal', 'Normal'),
        ('vip', 'VIP'),
        ('vvip', 'VVIP'),
    ]
    nama_customer = models.CharField(max_length=255)
    alamat_cust = models.TextField(blank=True, null=True)
    kota = models.CharField(max_length=100, blank=True, null=True)
    kode_pos = models.CharField(max_length=20, blank=True, null=True)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='normal')

    def __str__(self):
        return self.nama_customer

class OrdersList(models.Model):
    class Meta:
        db_table = 'orders_orderlist'
    id_pesanan = models.CharField(max_length=100, db_index=True, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders_lists')
    tanggal_pembuatan = models.DateTimeField()
    keterangan = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.id_pesanan} - {self.customer.nama_customer}"

    @classmethod
    def delete_with_details(cls, id):
        with transaction.atomic():
            obj = cls.objects.get(pk=id)
            # Hapus semua Order dengan id_pesanan yang sama
            from .models import Order
            Order.objects.filter(id_pesanan=obj.id_pesanan).delete()
            obj.delete()
