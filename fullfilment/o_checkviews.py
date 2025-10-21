from django.http import JsonResponse
from orders.models import Order
from django.db.models import F
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import render
import json
from products.models import Product

def orders_scan(request):
    table_rows = None
    order_id = None
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        orders = Order.objects.filter(id_pesanan=order_id).select_related('product')
        if orders.exists():
            table_rows = []
            for o in orders:
                p = o.product
                if o.jumlah_ambil == o.jumlah and o.jumlah > 0:
                    status_ambil = 'Completed'
                elif o.jumlah_ambil > 0:
                    status_ambil = 'Partial'
                else:
                    status_ambil = 'Pending'
                table_rows.append({
                    'sku': o.sku,
                    'barcode': p.barcode if p else '',
                    'nama_produk': p.nama_produk if p else '',
                    'variant_produk': p.variant_produk if p else '',
                    'brand': p.brand if p else '',
                    'jumlah': o.jumlah,
                    'jumlah_ambil': o.jumlah_ambil,
                    'status_ambil': status_ambil,
                })
        else:
            table_rows = 'not_found'
    return render(request, 'fullfilment/orders_scan.html', {
        'table_rows': table_rows,
        'order_id': order_id,
    })

@csrf_exempt
@require_POST
def scan_barcode_order_scan(request):
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        barcode = data.get('barcode')
        if not order_id or not barcode:
            return JsonResponse({'success': False, 'error': 'Order ID dan barcode wajib diisi.'})
        try:
            product = Product.objects.get(barcode=barcode)
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Barcode tidak ditemukan di master produk.'})
        try:
            order = Order.objects.get(id_pesanan=order_id, product_id=product.id)
        except Order.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Produk/barcode ini tidak ada di order ini.'})
        if order.jumlah_ambil >= order.jumlah:
            return JsonResponse({'success': False, 'error': 'Jumlah ambil sudah sesuai jumlah pesanan.'})
        order.jumlah_ambil += 1
        order.save(update_fields=['jumlah_ambil'])
        return JsonResponse({'success': True, 'jumlah_ambil': order.jumlah_ambil})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
