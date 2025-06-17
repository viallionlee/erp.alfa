# File khusus logic orders checking (scan order, tampil tabel, scan barcode, dsb)
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db.models import F
from orders.models import Order
from .models import ReadyToPrint
from products.models import Product  # Pastikan import model Product
from django.views.decorators.csrf import ensure_csrf_cookie
import json


def orders_checking(request, nama_batch=None):
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    context = {
        'nama_batch': nama_batch,
        'show_tables': False,
    }
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        orders = Order.objects.filter(id_pesanan=order_id).exclude(status_bundle='Y').select_related('product')
        if orders.exists():
            def build_rows(qs):
                rows = []
                for o in qs:
                    p = o.product
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
    # Pilih template mobile jika user agent mobile
    if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
        template = 'fullfilment/mobileorderchecking.html'
    else:
        template = 'fullfilment/orders_checking.html'
    return render(request, template, context)


def orders_checking_scan_barcode(request, nama_batch=None):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method.'}, status=405)
    try:
        data = json.loads(request.body)
        barcode = data.get('barcode')
        order_id = data.get('order_id')
        if not barcode or not order_id:
            return JsonResponse({'success': False, 'error': 'Barcode/order_id required.'})
        # Cari product dengan barcode
        try:
            product = Product.objects.get(barcode=barcode)
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Barcode tidak ditemukan.'})
        # Cari order yang sesuai TANPA filter status_bundle
        try:
            order = Order.objects.get(id_pesanan=order_id, product=product)
        except Order.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Barcode tidak valid atau tidak ditemukan pada order ini.'})
        # Cek over input
        if order.jumlah_ambil >= order.jumlah:
            return JsonResponse({'success': False, 'error': 'Over input: Produk telah melewati batas input'})
        # Update jumlah_ambil jika masih kurang dari jumlah
        if order.jumlah_ambil < order.jumlah:
            order.jumlah_ambil += 1
            order.save()
        # Ambil ulang data tabel, exclude status_bundle='Y'
        orders = Order.objects.filter(id_pesanan=order_id).exclude(status_bundle='Y').select_related('product')
        def build_rows(qs):
            rows = []
            for o in qs:
                p = o.product
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
        return JsonResponse({
            'success': True,
            'pending_orders': build_rows(pending),
            'completed_orders': build_rows(completed),
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})