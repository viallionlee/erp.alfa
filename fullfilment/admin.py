from django.contrib import admin
from .models import BatchList, BatchItem

class BatchItemInline(admin.TabularInline):
    model = BatchItem
    extra = 1

@admin.register(BatchList)
class BatchListAdmin(admin.ModelAdmin):
    list_display = ['id', 'nama_batch', 'created_at', 'completed_at', 'status_batch']
    inlines = [BatchItemInline]

@admin.register(BatchItem)
class BatchItemAdmin(admin.ModelAdmin):
    list_display = ['batchlist', 'product', 'jumlah', 'jumlah_ambil', 'status_ambil']
    search_fields = ['batchlist__nama_batch', 'product__nama_produk']
    list_filter = ['status_ambil']
