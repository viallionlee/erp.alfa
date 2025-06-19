from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Q
from .filters import GenerateBatchOrderFilter

# Migrated from oms/views.py
def generatebatch(request):
    from orders.models import Order
    from django_tables2 import RequestConfig
    from .tables import GenerateBatchOrderTable
    orders = Order.objects.filter(status__iexact='Lunas').filter(Q(nama_batch__isnull=True) | Q(nama_batch='')).select_related('product')
    total_order_valid = orders.values('id_pesanan').distinct().count()
    f = GenerateBatchOrderFilter(request.GET, queryset=orders)
    filtered_order_count = f.qs.values('id_pesanan').distinct().count()
    table = GenerateBatchOrderTable(f.qs)
    RequestConfig(request, paginate={'per_page': 50}).configure(table)
    # SKU Not Found (tanpa batch, sama seperti index orders)
    order_skus = set(orders.exclude(status_bundle='Y').values_list('sku', flat=True))
    from products.models import Product
    master_skus = set(Product.objects.values_list('sku', flat=True))
    sku_not_found_list = sorted(order_skus - master_skus)
    sku_not_found_count = len(sku_not_found_list)
    return render(request, 'fullfilment/generatebatch.html', {
        'table': table,
        'filter': f,
        'total_order_valid': total_order_valid,
        'total_order_filter': filtered_order_count,
        'sku_not_found_count': sku_not_found_count,
        'sku_not_found_list': sku_not_found_list,
    })


def generatebatch_data(request):
    from orders.models import Order
    try:
        orders = Order.objects.filter(status__iexact='Lunas').filter(Q(nama_batch__isnull=True) | Q(nama_batch='')).select_related('product')
        data = []
        # Kumpulkan unique values untuk setiap kolom filter
        unique_kirim_sebelum = set()
        unique_kurir = set()
        unique_nama_toko = set()
        unique_brand = set()
        unique_order_type = set()
        for order in orders:
            product = order.product if hasattr(order, 'product') else None
            data.append({
                'status_stock': order.status_stock,
                'product_id': order.product_id,
                'tanggal_pembuatan': order.tanggal_pembuatan,
                'channel': order.channel,
                'nama_toko': order.nama_toko,
                'id_pesanan': order.id_pesanan,
                'sku': order.sku,
                'nama_produk': product.nama_produk if product else '',
                'variant_produk': product.variant_produk if product else '',
                'brand': product.brand if product else '',
                'jumlah': order.jumlah,
                'kurir': order.kurir,
                'metode_pengiriman': order.metode_pengiriman,
                'kirim_sebelum': order.kirim_sebelum,
                'order_type': order.order_type,
            })
            if order.kirim_sebelum:
                unique_kirim_sebelum.add(order.kirim_sebelum)
            if order.kurir:
                unique_kurir.add(order.kurir)
            if order.nama_toko:
                unique_nama_toko.add(order.nama_toko)
            if product and product.brand:
                unique_brand.add(product.brand)
            if order.order_type:
                unique_order_type.add(order.order_type)
        return JsonResponse({
            'draw': int(request.GET.get('draw', 1)),
            'recordsTotal': orders.count(),
            'recordsFiltered': orders.count(),
            'data': data,
            'filter_options': {
                'kirim_sebelum': sorted(unique_kirim_sebelum),
                'kurir': sorted(unique_kurir),
                'nama_toko': sorted(unique_nama_toko),
                'brand': sorted(unique_brand),
                'order_type': sorted(unique_order_type),
            }
        })
    except Exception as e:
        return JsonResponse({'error': 'Internal Server Error'}, status=500)


from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

@csrf_exempt
@require_GET
def generatebatch_check_stock(request):
    from collections import defaultdict
    from orders.models import OrderCukup, OrderTidakCukup, Order
    from inventory.models import Stock
    # Hapus semua data lama
    OrderCukup.objects.all().delete()
    OrderTidakCukup.objects.all().delete()
    orders = Order.objects.filter(status__iexact='Lunas').filter(Q(nama_batch__isnull=True) | Q(nama_batch='')).select_related('product')
    f = GenerateBatchOrderFilter(request.GET, queryset=orders)
    qs = f.qs
    pesanan_map = defaultdict(list)
    for o in qs:
        pesanan_map[o.id_pesanan].append(o)
    all_skus = set(o.sku for o in qs if o.sku)
    all_product_ids = set()
    for o in qs:
        if o.product_id:
            all_product_ids.add(o.product_id)
    stock_map = {s.product_id: s.quantity for s in Stock.objects.filter(product_id__in=all_product_ids)}
    quantity_left = stock_map.copy()
    result = {}
    cukup_count = 0
    tidak_cukup_count = 0
    check_stock_per_row = {}
    # Gunakan set untuk unique id_pesanan
    ordercukup_ids = set()
    ordertidakcukup_ids = set()
    for id_pesanan, items in pesanan_map.items():
        product_jumlah = defaultdict(int)
        for o in items:
            if o.product_id:
                product_jumlah[o.product_id] += o.jumlah
        cukup = True
        for product_id, total_jumlah in product_jumlah.items():
            if quantity_left.get(product_id, 0) < total_jumlah:
                cukup = False
                break
        if cukup:
            for product_id, total_jumlah in product_jumlah.items():
                quantity_left[product_id] -= total_jumlah
            result[id_pesanan] = 'cukup'
            cukup_count += 1
            ordercukup_ids.add(id_pesanan)
            for o in items:
                check_stock_per_row[o.pk] = 'cukup'
        else:
            result[id_pesanan] = 'tidak cukup'
            tidak_cukup_count += 1
            ordertidakcukup_ids.add(id_pesanan)
            for o in items:
                check_stock_per_row[o.pk] = 'tidak cukup'
    # Bulk insert hasil baru, hanya unique id_pesanan
    from orders.models import OrderCukup, OrderTidakCukup
    ordercukup_bulk = [OrderCukup(id_pesanan=pid) for pid in ordercukup_ids]
    ordertidakcukup_bulk = [OrderTidakCukup(id_pesanan=pid) for pid in ordertidakcukup_ids]
    if ordercukup_bulk:
        OrderCukup.objects.bulk_create(ordercukup_bulk)
    if ordertidakcukup_bulk:
        OrderTidakCukup.objects.bulk_create(ordertidakcukup_bulk)
    return JsonResponse({
        'result': result,
        'check_stock_per_row': check_stock_per_row,
        'summary': {
            'stock_cukup': cukup_count,
            'stock_tidak_cukup': tidak_cukup_count,
            'total': len(pesanan_map)
        }
    })

@csrf_exempt
@require_POST
def generatebatch_update_batchlist(request):
    import logging
    logger = logging.getLogger(__name__)
    try:
        import json
        import urllib.parse
        data = json.loads(request.body)
        ambil = data.get('ambil')  # 'cukup', 'tidak cukup', atau 'semua'
        mode = data.get('mode')    # 'create' atau 'update'
        nama_batch = data.get('nama_batch', '').strip()
        filters = data.get('filters', '')  # Ambil filter dari body
        from fullfilment.models import BatchList
        # Validasi
        if not ambil or not mode or not nama_batch:
            return JsonResponse({'success': False, 'message': 'Parameter tidak lengkap.'}, status=400)
        # Cek duplikat nama_batch jika create
        if mode == 'create':
            if BatchList.objects.filter(nama_batch__iexact=nama_batch).exists():
                return JsonResponse({'success': False, 'message': 'Nama batchlist sudah ada.'}, status=400)
            batchlist = BatchList.objects.create(nama_batch=nama_batch, status_batch='pending')
        else:
            # Cari batchlist yang status_batch masih 'pending' (bukan NULL)
            batchlist = BatchList.objects.filter(nama_batch=nama_batch, status_batch='pending').first()
            if not batchlist:
                return JsonResponse({'success': False, 'message': 'Batchlist tidak ditemukan atau sudah selesai.'}, status=400)
        # Ambil id_pesanan dari tabel OrderCukup/OrderTidakCukup sesuai pilihan user
        from orders.models import OrderCukup, OrderTidakCukup
        if ambil == 'cukup':
            id_pesanan_pilih = set(OrderCukup.objects.values_list('id_pesanan', flat=True))
        elif ambil == 'tidak cukup':
            id_pesanan_pilih = set(OrderTidakCukup.objects.values_list('id_pesanan', flat=True))
        elif ambil == 'semua':
            id_pesanan_cukup = set(OrderCukup.objects.values_list('id_pesanan', flat=True))
            id_pesanan_tidakcukup = set(OrderTidakCukup.objects.values_list('id_pesanan', flat=True))
            id_pesanan_pilih = id_pesanan_cukup.union(id_pesanan_tidakcukup)
        else:
            return JsonResponse({'success': False, 'message': 'Pilihan ambil tidak valid.'}, status=400)
        id_pesanan_pilih = set(str(x).strip() for x in id_pesanan_pilih)
        logger.warning(f"DEBUG: id_pesanan_pilih = {id_pesanan_pilih}")
        updated = 0
        if id_pesanan_pilih:
            from django.db import connection
            placeholders = ','.join(['%s'] * len(id_pesanan_pilih))
            sql = f"UPDATE orders_order SET nama_batch = %s WHERE id_pesanan IN ({placeholders})"
            params = [nama_batch] + list(id_pesanan_pilih)
            logger.warning(f"DEBUG: SQL = {sql}")
            logger.warning(f"DEBUG: params = {params}")
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                updated = cursor.rowcount
        logger.info(f"Rows updated (raw SQL): {updated}")
        return JsonResponse({'success': True, 'updated': updated, 'nama_batch': nama_batch})
    except Exception as e:
        logger.exception('Error in generatebatch_update_batchlist')
        # Write error to server.log
        try:
            with open(r'C:/Users/m3vil/OneDrive/Desktop/ERP.ALFA/erp_alfa/logs/server.log', 'a', encoding='utf-8') as f:
                import traceback
                f.write(f"[generatebatch_update_batchlist] ERROR: {str(e)}\n")
                f.write(traceback.format_exc())
                f.write('\n')
        except Exception as log_exc:
            pass  # Avoid recursive logging errors
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
def filter_selected(request):
    if request.method == 'POST':
        selected_ids = request.POST.getlist('selected_ids')
        orders = Order.objects.filter(pk__in=selected_ids)
        total_order_valid = orders.values('id_pesanan').distinct().count()
        f = GenerateBatchOrderFilter(request.GET, queryset=orders)
        filtered_order_count = f.qs.values('id_pesanan').distinct().count()
        table = GenerateBatchOrderTable(f.qs)
        RequestConfig(request, paginate={'per_page': 50}).configure(table)
        # SKU Not Found
        order_skus = set(orders.exclude(status_bundle='Y').values_list('sku', flat=True))
        from products.models import Product
        master_skus = set(Product.objects.values_list('sku', flat=True))
        sku_not_found_list = sorted(order_skus - master_skus)
        sku_not_found_count = len(sku_not_found_list)
        return render(request, 'fullfilment/generatebatch.html', {
            'table': table,
            'filter': f,
            'total_order_valid': total_order_valid,
            'total_order_filter': filtered_order_count,
            'sku_not_found_count': sku_not_found_count,
            'sku_not_found_list': sku_not_found_list,
            'selected_ids': selected_ids,
        })
    return redirect('fullfilment-generatebatch')
