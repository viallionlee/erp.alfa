from django.contrib import admin
from .models import Stock, Inbound, InboundItem, Outbound, OutboundItem, HistoryImportStock

class InboundItemInline(admin.TabularInline):
    model = InboundItem
    extra = 1

@admin.register(Inbound)
class InboundAdmin(admin.ModelAdmin):
    list_display = ['nomor_inbound', 'tanggal', 'keterangan']
    inlines = [InboundItemInline]

class OutboundItemInline(admin.TabularInline):
    model = OutboundItem
    extra = 1

@admin.register(Outbound)
class OutboundAdmin(admin.ModelAdmin):
    list_display = ['nomor_outbound', 'tanggal', 'keterangan']
    inlines = [OutboundItemInline]

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ['product', 'quantity']

@admin.register(HistoryImportStock)
class HistoryImportStockAdmin(admin.ModelAdmin):
    list_display = ['import_time', 'imported_by', 'file_name', 'success_count', 'failed_count']
    search_fields = ['file_name', 'imported_by', 'notes']
    list_filter = ['import_time']

admin.site.register(InboundItem)
admin.site.register(OutboundItem)
