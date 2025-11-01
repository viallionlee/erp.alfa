# Generated manually

from django.db import migrations

def populate_product_info(apps, schema_editor):
    """Populate product_sku, product_name, product_barcode for existing logs"""
    EditProductLog = apps.get_model('products', 'EditProductLog')
    
    # Update logs that have product but missing product_sku
    logs_to_update = EditProductLog.objects.filter(
        product__isnull=False,
        product_sku__isnull=True
    )
    
    updated_count = 0
    for log in logs_to_update:
        if log.product:
            log.product_sku = log.product.sku
            log.product_name = log.product.nama_produk
            log.product_barcode = log.product.barcode
            log.save()
            updated_count += 1
    
    print(f"Updated {updated_count} existing log entries with product information")

def reverse_populate_product_info(apps, schema_editor):
    """Reverse migration - clear product info fields"""
    EditProductLog = apps.get_model('products', 'EditProductLog')
    EditProductLog.objects.update(
        product_sku=None,
        product_name=None,
        product_barcode=None
    )

class Migration(migrations.Migration):

    dependencies = [
        ('products', '0012_editproductlog_product_barcode_and_more'),
    ]

    operations = [
        migrations.RunPython(populate_product_info, reverse_populate_product_info),
    ]
