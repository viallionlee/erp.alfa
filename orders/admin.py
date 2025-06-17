from django.contrib import admin
from .models import Order, OrderImportHistory, OrderPrintHistory, OrderPackingHistory, OrderHandoverHistory

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'tanggal_pembuatan', 'status', 'jenis_pesanan', 'channel', 'nama_toko',
        'id_pesanan', 'sku', 'jumlah', 'harga_promosi',
        'catatan_pembeli', 'kurir', 'awb_no_tracking', 'metode_pengiriman', 'kirim_sebelum',
        'order_type', 'status_order', 'status_cancel', 'status_retur',
        'jumlah_ambil', 'status_ambil', 'nama_batch', 'product'
    ]
    search_fields = ['id_pesanan', 'sku']
    list_filter = ['status', 'status_order', 'kurir']

@admin.register(OrderImportHistory)
class OrderImportHistoryAdmin(admin.ModelAdmin):
    list_display = ['import_time', 'imported_by', 'file_name', 'notes']
    search_fields = ['file_name', 'notes']
    list_filter = ['imported_by', 'import_time']

@admin.register(OrderPrintHistory)
class OrderPrintHistoryAdmin(admin.ModelAdmin):
    list_display = ['order', 'waktu_print', 'status_print', 'user']
    search_fields = ['order__id_pesanan', 'status_print', 'user__username']
    list_filter = ['status_print', 'user']

@admin.register(OrderPackingHistory)
class OrderPackingHistoryAdmin(admin.ModelAdmin):
    list_display = ['order', 'waktu_pack', 'user']
    search_fields = ['order__id_pesanan', 'user__username']
    list_filter = ['user']

@admin.register(OrderHandoverHistory)
class OrderHandoverHistoryAdmin(admin.ModelAdmin):
    list_display = ['order', 'waktu_ho', 'user']
    search_fields = ['order__id_pesanan', 'user__username']
    list_filter = ['user']
