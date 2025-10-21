from django.contrib import admin
from .models import Stock, Inbound, InboundItem, HistoryImportStock, StockCardEntry
from .models import OpnameQueue, OpnameHistory, RakOpnameSession, RakOpnameItem, Rak
from .models import PutawaySlottingLog
from django.urls import reverse
from django.utils.html import format_html
from .models import Rak, StockCardEntry, Inbound, InboundItem, Supplier, RakOpnameSession, RakOpnameItem, RakOpnameLog

class InboundItemInline(admin.TabularInline):
    model = InboundItem
    extra = 1

@admin.register(Inbound)
class InboundAdmin(admin.ModelAdmin):
    list_display = ['nomor_inbound', 'tanggal', 'from_warehouse', 'to_warehouse', 'keterangan']
    inlines = [InboundItemInline]

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ['product', 'quantity']

@admin.register(HistoryImportStock)
class HistoryImportStockAdmin(admin.ModelAdmin):
    list_display = ['import_time', 'imported_by', 'file_name', 'success_count', 'failed_count']
    search_fields = ['file_name', 'imported_by', 'notes']
    list_filter = ['import_time']

@admin.register(OpnameQueue)
class OpnameQueueAdmin(admin.ModelAdmin):
    list_display = ['product', 'lokasi', 'terakhir_opname', 'prioritas', 'sumber_prioritas', 'status', 'ditambahkan_pada']
    list_filter = ['status', 'sumber_prioritas', 'prioritas']
    search_fields = ['product__sku', 'product__nama_produk', 'lokasi', 'catatan']
    ordering = ['prioritas', 'terakhir_opname']

@admin.register(OpnameHistory)
class OpnameHistoryAdmin(admin.ModelAdmin):
    list_display = ['product', 'tanggal_opname', 'qty_fisik', 'qty_sistem', 'selisih', 'petugas_opname']
    search_fields = ['product__sku', 'product__nama_produk', 'catatan']
    list_filter = ['tanggal_opname', 'petugas_opname']
    ordering = ['-tanggal_opname']

@admin.register(StockCardEntry)
class StockCardEntryAdmin(admin.ModelAdmin):
    list_display = ('product', 'waktu', 'tipe_pergerakan', 'qty', 'qty_awal', 'qty_akhir', 'linked_reference', 'notes', 'user')
    list_filter = ('tipe_pergerakan', 'waktu', 'product')
    search_fields = ('product__sku', 'product__nama_produk', 'notes')
    raw_id_fields = ('product', 'user')
    
    def linked_reference(self, obj):
        """
        Membuat link ke objek referensi (Inbound, Batch, dll.) di halaman admin.
        """
        if obj.reference:
            try:
                # Membuat URL admin secara dinamis
                app_label = obj.content_type.app_label
                model_name = obj.content_type.model
                url = reverse(f'admin:{app_label}_{model_name}_change', args=[obj.object_id])
                return format_html('<a href="{}">{}</a>', url, obj.reference)
            except:
                # Jika URL tidak ditemukan, tampilkan sebagai teks biasa
                return str(obj.reference)
        return "-"
    linked_reference.short_description = 'Reference'
    linked_reference.admin_order_field = 'content_type' # Memungkinkan sorting

admin.site.register(InboundItem)

class RakOpnameItemInline(admin.TabularInline):
    model = RakOpnameItem
    extra = 0
    readonly_fields = ['qty_sistem', 'qty_selisih', 'created_at', 'updated_at']
    fields = ['product', 'qty_sistem', 'qty_fisik', 'qty_selisih', 'is_verified', 'verified_by', 'verified_at', 'catatan']



@admin.register(Rak)
class RakAdmin(admin.ModelAdmin):
    list_display = ['kode_rak', 'nama_rak', 'barcode_rak', 'lokasi', 'created_at']
    search_fields = ['kode_rak', 'nama_rak', 'barcode_rak', 'lokasi']
    list_filter = ['lokasi', 'created_at']
    ordering = ['kode_rak']

@admin.register(RakOpnameSession)
class RakOpnameSessionAdmin(admin.ModelAdmin):
    list_display = ['session_code', 'rak', 'tanggal_mulai', 'created_by', 'status', 'total_items', 'total_selisih']
    list_filter = ['status', 'tanggal_mulai', 'rak']
    search_fields = ['session_code', 'rak__lokasi', 'created_by__username']
    readonly_fields = ['session_code', 'tanggal_mulai', 'total_items', 'total_selisih']
    date_hierarchy = 'tanggal_mulai'
    inlines = [RakOpnameItemInline]
    
    def total_items(self, obj):
        return obj.total_items
    total_items.short_description = 'Total Items'
    
    def total_selisih(self, obj):
        return obj.total_selisih
    total_selisih.short_description = 'Total Selisih'


@admin.register(RakOpnameItem)
class RakOpnameItemAdmin(admin.ModelAdmin):
    list_display = ['session', 'product', 'qty_sistem', 'qty_fisik', 'qty_selisih']
    list_filter = ['session__status', 'session__rak']
    search_fields = ['product__sku', 'product__nama_produk', 'session__rak__lokasi']
    readonly_fields = ['qty_selisih']


@admin.register(RakOpnameLog)
class RakOpnameLogAdmin(admin.ModelAdmin):
    list_display = ['session', 'action', 'user', 'timestamp']
    list_filter = ['action', 'timestamp', 'session__status']
    search_fields = ['session__rak__lokasi', 'user__username', 'details']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'

@admin.register(PutawaySlottingLog)
class PutawaySlottingLogAdmin(admin.ModelAdmin):
    list_display = ['product', 'suggested_rak', 'putaway_by', 'putaway_time', 'quantity', 'created_at']
    list_filter = ['putaway_time', 'suggested_rak', 'putaway_by', 'created_at']
    search_fields = ['product__sku', 'product__nama_produk', 'suggested_rak__kode_rak', 'putaway_by__username']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Produk', {
            'fields': ('product', 'quantity')
        }),
        ('Rak Tujuan', {
            'fields': ('suggested_rak', 'putaway_by')
        }),
        ('Metadata', {
            'fields': ('putaway_time', 'created_at')
        }),
    )
