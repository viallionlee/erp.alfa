from django.http import JsonResponse
from orders.models import Order
from django.db.models import F
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import render

def orders_checking(request, nama_batch=None):
    context = {
        'nama_batch': nama_batch,
        'show_tables': False,
    }

    order_id_to_process = None

    if request.method == 'POST':
        order_id_to_process = request.POST.get('order_id')
        print(f"DEBUG: orders_checking - POST request. order_id from POST: {order_id_to_process}")
    elif nama_batch:
        order_id_to_process = nama_batch
        print(f"DEBUG: orders_checking - GET request (path parameter). order_id from nama_batch: {order_id_to_process}")
    elif request.method == 'GET' and request.GET.get('order_id'):
        order_id_to_process = request.GET.get('order_id')
        print(f"DEBUG: orders_checking - GET request (query parameter). order_id from GET: {order_id_to_process}")

    if order_id_to_process:
        orders = Order.objects.filter(id_pesanan=order_id_to_process).select_related('product')
        print(f"DEBUG: orders_checking - Querying for Order ID: '{order_id_to_process}'")
        print(f"DEBUG: orders_checking - Orders exist: {orders.exists()}")

        if orders.exists():
            def build_rows(qs):
                rows = []
                for o in qs:
                    p = o.product
                    # Logic status_ambil otomatis
                    if o.jumlah_ambil == o.jumlah and o.jumlah > 0:
                        status_ambil = 'completed'
                    elif o.jumlah_ambil > 0:
                        status_ambil = 'partial'
                    else:
                        status_ambil = 'pending'
                    rows.append({
                        'sku': o.sku,
                        'barcode': p.barcode if p else '',
                        'nama_produk': p.nama_produk if p else '',
                        'variant_produk': p.variant_produk if p else '',
                        'brand': p.brand if p else '',
                        'jumlah': o.jumlah,
                        'jumlah_ambil': o.jumlah_ambil,
                        'status_ambil': status_ambil,
                        'photo_url': p.photo.url if p and p.photo else '/static/icons/alfaicon.png',
                    })
                return rows
            pending = orders.filter(jumlah_ambil__lt=F('jumlah'))
            completed = orders.filter(jumlah_ambil=F('jumlah'), jumlah__gt=0)
            context.update({
                'show_tables': True,
                'order_id': order_id_to_process,
                'pending_orders': build_rows(pending),
                'completed_orders': build_rows(completed),
            })
        else:
            context['error'] = f'Order ID "{order_id_to_process}" tidak ditemukan.'
            context['order_id'] = order_id_to_process

    return render(request, 'fullfilment/orders_checking.html', context)

# (scan_barcode_order_checking function intentionally not included, as per last instructions)
