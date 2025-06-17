from django.contrib import admin
from .models import DemoExtract

@admin.register(DemoExtract)
class DemoExtractAdmin(admin.ModelAdmin):
    list_display = ('sku', 'jumlah')
    search_fields = ('sku',)
