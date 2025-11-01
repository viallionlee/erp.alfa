from django.contrib import admin
from .models import Product, ProductImportHistory, ProductsBundling, EditProductLog
import csv
from django.http import HttpResponse
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import path
from django import forms

class CsvImportForm(forms.Form):
    csv_file = forms.FileField()

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'rak', 'panjang_cm', 'lebar_cm', 'tinggi_cm', 'berat_gram', 'photo'
    ]
    search_fields = ['sku', 'barcode', 'nama_produk', 'brand']
    list_filter = ['brand', 'rak']
    list_per_page = 1000  # Default 1000 per page
    list_max_show_all = 5000  # Allow 'Show all' up to 5000

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name='products-import-csv'),
            path('export-csv/', self.admin_site.admin_view(self.export_csv), name='products-export-csv'),
        ]
        return custom_urls + urls

    def import_csv(self, request):
        if request.method == "POST":
            form = CsvImportForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = form.cleaned_data['csv_file']
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)
                success, failed = 0, 0
                for row in reader:
                    try:
                        Product.objects.update_or_create(
                            sku=row['sku'],
                            defaults={
                                'barcode': row.get('barcode', ''),
                                'nama_produk': row.get('nama_produk', ''),
                                'variant_produk': row.get('variant_produk', ''),
                                'brand': row.get('brand', ''),
                                'rak': row.get('rak', ''),
                                'panjang_cm': row.get('panjang_cm', ''),
                                'lebar_cm': row.get('lebar_cm', ''),
                                'tinggi_cm': row.get('tinggi_cm', ''),
                                'berat_gram': row.get('berat_gram', ''),
                            }
                        )
                        success += 1
                    except Exception:
                        failed += 1
                messages.success(request, f"Import selesai. Sukses: {success}, Gagal: {failed}")
                return redirect("..")
        else:
            form = CsvImportForm()
        context = dict(
            self.admin_site.each_context(request),
            form=form,
        )
        return render(request, "admin/products_import.html", context)

    def export_csv(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=products.csv'
        writer = csv.writer(response)
        writer.writerow(['id', 'sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'rak', 'panjang_cm', 'lebar_cm', 'tinggi_cm', 'berat_gram'])
        for p in Product.objects.all():
            writer.writerow([p.id, p.sku, p.barcode, p.nama_produk, p.variant_produk, p.brand, p.rak, p.panjang_cm, p.lebar_cm, p.tinggi_cm, p.berat_gram])
        return response

@admin.register(ProductImportHistory)
class ProductImportHistoryAdmin(admin.ModelAdmin):
    list_display = ['import_time', 'imported_by', 'file_name', 'success_count', 'failed_count', 'notes']
    search_fields = ['file_name', 'notes']
    list_filter = ['imported_by', 'import_time']

admin.site.register(ProductsBundling)

@admin.register(EditProductLog)
class EditProductLogAdmin(admin.ModelAdmin):
    list_display = ['product', 'field_name', 'old_value', 'new_value', 'edited_by', 'edited_at', 'change_type']
    list_filter = ['change_type', 'field_name', 'edited_by', 'edited_at']
    search_fields = ['product__sku', 'product__nama_produk', 'field_name', 'notes']
    readonly_fields = ['product', 'edited_by', 'edited_at', 'field_name', 'old_value', 'new_value', 'change_type', 'notes']
    list_per_page = 50
    
    def has_add_permission(self, request):
        return False  # Log hanya dibuat otomatis, tidak bisa ditambah manual
    
    def has_change_permission(self, request, obj=None):
        return False  # Log tidak bisa diedit
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Hanya superuser yang bisa hapus log
