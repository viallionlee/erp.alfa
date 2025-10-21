from django.contrib import admin
from .models import PurchaseOrder, PurchaseOrderItem, PurchaseOrderHistory, PriceHistory, Purchase, PurchaseItem, Bank


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1
    fields = ('product', 'quantity', 'harga_beli', 'subtotal')
    readonly_fields = ('subtotal',)


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('nomor_po', 'supplier', 'tanggal_po', 'status', 'total_amount', 'created_by', 'received_by', 'received_at')
    list_filter = ('status', 'tanggal_po', 'supplier')
    search_fields = ('nomor_po', 'supplier__nama_supplier', 'notes')
    readonly_fields = ('total_amount', 'created_at', 'updated_at')
    inlines = [PurchaseOrderItemInline]
    
    fieldsets = (
        ('Informasi PO', {
            'fields': ('nomor_po', 'supplier', 'tanggal_po', 'status', 'total_amount')
        }),
        ('Tracking', {
            'fields': ('created_by', 'received_by', 'received_at', 'created_at', 'updated_at')
        }),
        ('Catatan', {
            'fields': ('notes',)
        }),
    )


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = ('po', 'product', 'quantity', 'harga_beli', 'subtotal')
    list_filter = ('po__status',)
    search_fields = ('po__nomor_po', 'product__sku', 'product__nama_produk')


@admin.register(PurchaseOrderHistory)
class PurchaseOrderHistoryAdmin(admin.ModelAdmin):
    list_display = ('po', 'action', 'user', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('po__nomor_po', 'user__username', 'notes')
    readonly_fields = ('po', 'action', 'user', 'timestamp', 'old_values', 'new_values')


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ('product', 'purchase_order', 'supplier', 'price', 'quantity', 'purchase_date')
    list_filter = ('supplier', 'purchase_date')
    search_fields = ('product__sku', 'product__nama_produk', 'purchase_order__nomor_po', 'supplier__nama_supplier')
    readonly_fields = ('product', 'purchase_order', 'purchase_order_item', 'price', 'quantity', 'supplier', 'purchase_date', 'created_at')
    date_hierarchy = 'purchase_date'


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1
    fields = ('product', 'quantity', 'harga_beli', 'subtotal')
    readonly_fields = ('subtotal',)


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('nomor_purchase', 'supplier', 'po', 'tanggal_purchase', 'status', 'total_amount', 'created_by', 'received_by')
    list_filter = ('status', 'tanggal_purchase', 'supplier')
    search_fields = ('nomor_purchase', 'supplier__nama_supplier', 'po__nomor_po', 'notes')
    readonly_fields = ('total_amount', 'created_at', 'updated_at')
    inlines = [PurchaseItemInline]
    
    fieldsets = (
        ('Informasi Purchase', {
            'fields': ('nomor_purchase', 'supplier', 'po', 'tanggal_purchase', 'tanggal_received', 'status', 'total_amount')
        }),
        ('Tracking', {
            'fields': ('created_by', 'received_by', 'created_at', 'updated_at')
        }),
        ('Catatan', {
            'fields': ('notes',)
        }),
    )


@admin.register(PurchaseItem)
class PurchaseItemAdmin(admin.ModelAdmin):
    list_display = ('purchase', 'product', 'quantity', 'harga_beli', 'subtotal')
    list_filter = ('purchase__status',)
    search_fields = ('purchase__nomor_purchase', 'product__sku', 'product__nama_produk')


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ('nama_bank', 'nomor_rekening', 'atas_nama', 'is_active', 'created_at')
    list_filter = ('is_active', 'nama_bank')
    search_fields = ('nama_bank', 'nomor_rekening', 'atas_nama')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Informasi Bank', {
            'fields': ('nama_bank', 'nomor_rekening', 'atas_nama', 'is_active')
        }),
        ('Catatan', {
            'fields': ('notes',)
        }),
        ('Tracking', {
            'fields': ('created_at', 'updated_at')
        }),
    )

