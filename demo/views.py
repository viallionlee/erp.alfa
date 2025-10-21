from django.shortcuts import render
from django.http import JsonResponse
from .models import DemoExtract
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from products.models import Product, ProductsBundling
from django.db import transaction

def demoextract_page(request):
    data = list(DemoExtract.objects.select_related('product').values('id_pesanan', 'status', 'sku', 'jumlah', 'product_id', 'status_bundle', 'status_order'))
    return render(request, 'demoextract.html', {'data': data})

def demoextract_data(request):
    # DataTables expects a 'data' key with a list of dicts
    data = list(DemoExtract.objects.select_related('product').values('id_pesanan', 'status', 'sku', 'jumlah', 'product_id', 'status_bundle', 'status_order'))
    return JsonResponse({'data': data})

@csrf_exempt
@require_POST
def extract_skudemo(request):
    extracted_count = 0
    failed = []
    try:
        with transaction.atomic():
            parents = DemoExtract.objects.filter(
                status__iexact='Lunas'
            ).exclude(
                status_bundle__iexact='Y'
            )
            for parent in parents:
                sku = parent.sku.strip().upper()
                jumlah = parent.jumlah
                id_pesanan = parent.id_pesanan
                status = parent.status
                # Cari product berdasarkan SKU
                product_obj = Product.objects.filter(sku__iexact=sku).first()
                # Cek di products_product
                if product_obj:
                    parent.product = product_obj
                    parent.save(update_fields=['product'])
                    continue  # Sudah ada di product, tidak perlu extract
                # Cek di products_productbundling
                bundling = ProductsBundling.objects.filter(sku_bundling=sku).first()
                if not bundling or not bundling.sku_list:
                    failed.append(sku)
                    continue
                sku_qty_pairs = []
                for pair in bundling.sku_list.split(','):
                    if ':' in pair:
                        sku_child, qty_child = pair.split(':')
                        sku_child = sku_child.strip().upper()
                        try:
                            qty_child = int(qty_child)
                        except Exception:
                            qty_child = 1
                        sku_qty_pairs.append((sku_child, qty_child))
                for sku_child, qty_child in sku_qty_pairs:
                    product_child = Product.objects.filter(sku__iexact=sku_child).first()
                    DemoExtract.objects.create(
                        sku=sku_child,
                        jumlah=jumlah * qty_child,
                        id_pesanan=id_pesanan,
                        status=status,
                        product=product_child,
                        status_bundle=None
                    )
                    extracted_count += 1
                # Update status_bundle parent jika berhasil extract
                parent.status_bundle = 'Y'
                parent.save(update_fields=['status_bundle'])
        return JsonResponse({'success': True, 'extracted_count': extracted_count, 'failed': failed})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
