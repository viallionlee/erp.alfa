from django.contrib import admin
from .models import Order, OrderImportHistory, OrderPrintHistory, OrderPackingHistory, OrderHandoverHistory, OrdersList
from django.contrib import messages
from django.db.models import Q

@admin.register(OrdersList)
class OrdersListAdmin(admin.ModelAdmin):
    list_display = ('id_pesanan', 'customer', 'tanggal_pembuatan', 'keterangan', 'created_at')
    search_fields = ('id_pesanan', 'customer__nama_customer')
    list_filter = ('tanggal_pembuatan', 'customer')

    def delete_queryset(self, request, queryset):
        """
        Override delete method to implement custom cascade delete logic
        """
        for order_list in queryset:
            # Check if there are any orders with this id_pesanan
            orders_with_batch = Order.objects.filter(
                id_pesanan=order_list.id_pesanan,
                nama_batch__isnull=False
            ).exclude(nama_batch='')
            
            if orders_with_batch.exists():
                # If orders have batch_id, show error message
                self.message_user(
                    request,
                    f"Tidak dapat menghapus {order_list.id_pesanan} karena sudah memiliki batch_id. Hapus batch_id terlebih dahulu.",
                    level=messages.ERROR
                )
                continue
            
            # If no batch_id found, proceed with cascade delete
            try:
                # Delete all related orders first
                Order.objects.filter(id_pesanan=order_list.id_pesanan).delete()
                # Then delete the order list
                order_list.delete()
                self.message_user(
                    request,
                    f"Berhasil menghapus {order_list.id_pesanan} dan semua order terkait.",
                    level=messages.SUCCESS
                )
            except Exception as e:
                self.message_user(
                    request,
                    f"Error menghapus {order_list.id_pesanan}: {str(e)}",
                    level=messages.ERROR
                )

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'tanggal_pembuatan', 'status', 'jenis_pesanan', 'channel', 'nama_toko',
        'id_pesanan', 'sku', 'jumlah', 'harga_promosi',
        'catatan_pembeli', 'kurir', 'awb_no_tracking', 'metode_pengiriman', 'kirim_sebelum',
        'order_type', 'status_order', 'status_cancel', 'status_retur',
        'jumlah_ambil', 'status_ambil', 'nama_batch', 'product'
    ]
    list_editable = [
        'status', 'jenis_pesanan', 'channel', 'nama_toko',
        'jumlah', 'harga_promosi', 'catatan_pembeli', 'kurir', 
        'awb_no_tracking', 'metode_pengiriman', 'kirim_sebelum',
        'order_type', 'status_order', 'status_cancel', 'status_retur',
        'jumlah_ambil', 'status_ambil', 'nama_batch'
    ]
    search_fields = ['id_pesanan', 'sku']
    list_filter = ['status', 'status_order', 'kurir']
    list_per_page = 50
    save_on_top = True

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
