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
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        orders = Order.objects.filter(id_pesanan=order_id).select_related('product')
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
                    })
                return rows
            pending = orders.filter(jumlah_ambil__lt=F('jumlah'))
            completed = orders.filter(jumlah_ambil=F('jumlah'), jumlah__gt=0)
            context.update({
                'show_tables': True,
                'order_id': order_id,
                'pending_orders': build_rows(pending),
                'completed_orders': build_rows(completed),
            })
        else:
            context['error'] = 'Order ID tidak ditemukan.'
    return render(request, 'fullfilment/orders_checking.html', context)

# (scan_barcode_order_checking function intentionally not included, as per last instructions)
