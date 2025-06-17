from celery import shared_task
from .models import Product, ProductImportHistory
from django.utils import timezone
import pandas as pd
import io, csv

@shared_task
def import_products_task(rows, filename, user_id=None):
    existing_skus = set(Product.objects.values_list('sku', flat=True))
    existing_barcodes = set(Product.objects.values_list('barcode', flat=True))
    grouped = {}
    for row in rows:
        sku = str(row.get('sku', '')).strip()
        barcode = str(row.get('barcode', '')).strip()
        key = (sku, barcode)
        if key in grouped:
            pass
        else:
            grouped[key] = row
    success, failed = 0, 0
    failed_notes = []
    products_to_create = []
    for (sku, barcode), row in grouped.items():
        if sku in existing_skus or barcode in existing_barcodes:
            failed += 1
            failed_notes.append(f"Duplicate SKU/barcode: {sku}/{barcode}")
            continue
        products_to_create.append(Product(
            sku=sku,
            barcode=barcode,
            nama_produk=row.get('nama_produk', ''),
            variant_produk=row.get('variant_produk', ''),
            brand=row.get('brand', ''),
            rak=row.get('rak', ''),
        ))
    if products_to_create:
        Product.objects.bulk_create(products_to_create, batch_size=1000)
        success += len(products_to_create)
    ProductImportHistory.objects.create(
        import_time=timezone.now(),
        imported_by_id=user_id,
        file_name=filename,
        notes='; '.join(failed_notes),
        success_count=success,
        failed_count=failed
    )
    return {'success': success, 'failed': failed, 'notes': failed_notes}
