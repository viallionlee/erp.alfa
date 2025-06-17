# Standar library
import os
import json
import logging
from collections import defaultdict

# Third-party
import pandas as pd
import pytz

# Django core
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q, Count, F
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.timezone import now

# Django tables2
from django_tables2 import RequestConfig

# App imports
from .models import BatchList, BatchItem, ReadyToPrint
from orders.models import Order
from inventory.models import Stock
from products.models import Product
from .tables import BatchItemTable, ReadyToPrintTable
from .generatebatch_views import generatebatch, generatebatch_data, generatebatch_check_stock, generatebatch_update_batchlist
from .utils import get_sku_not_found

def index(request):
    batchlists = BatchList.objects.all().order_by('-created_at')
    for batch in batchlists:
        sku_not_found_list, sku_not_found_count = get_sku_not_found(batch.nama_batch)
        batch.sku_not_found_count = sku_not_found_count
        batch.sku_not_found_list = sku_not_found_list
        # Hitung total order, sku pending, sku completed per batch
        batch.total_sku = BatchItem.objects.filter(batchlist=batch).count()
        batch.sku_pending = BatchItem.objects.filter(batchlist=batch, status_ambil='pending').count()
        batch.sku_completed = BatchItem.objects.filter(batchlist=batch, status_ambil='completed').count()
        # Update status_batch otomatis jika semua sku sudah completed
        if batch.total_sku > 0 and batch.total_sku == batch.sku_completed and batch.status_batch != 'completed':
            batch.status_batch = 'completed'
            batch.save(update_fields=['status_batch'])
    return render(request, 'fullfilment/index.html', {
        'batchlists': batchlists,
    })

def unique_brands(request):
    # Get all SKUs from orders
    skus = Order.objects.values_list('sku', flat=True)
    # Get unique brands from products with those SKUs
    brands = Product.objects.filter(sku__in=skus).values_list('brand', flat=True).distinct()
    brands = [b for b in brands if b]  # Remove empty/null brands
    return JsonResponse({'brands': brands})

@csrf_exempt
@require_POST
def check_stock_for_orders(request):
    data = json.loads(request.body)
    orders = data.get('orders', [])
    # Kumpulkan data per id_pesanan dan product_id
    pesanan_map = defaultdict(list)
    for o in orders:
        id_pesanan = o.get('id_pesanan')
        product_id = o.get('product_id')
        try:
            jumlah = int(o.get('jumlah') or 0)
        except Exception:
            jumlah = 0
        if id_pesanan and product_id and jumlah > 0:
            pesanan_map[id_pesanan].append({'product_id': str(product_id), 'jumlah': jumlah, 'row': o})
    # Ambil semua product_id unik
    product_ids = set()
    for items in pesanan_map.values():
        for item in items:
            product_ids.add(item['product_id'])
    # Ambil stok dari inventory
    stock_qs = Stock.objects.filter(product_id__in=product_ids)
    stock_map = {str(s.product_id): s.quantity for s in stock_qs}
    # Hasil akhir
    out_rows = []
    for id_pesanan, items in pesanan_map.items():
        # Hitung total jumlah per product_id
        jumlah_per_product = defaultdict(int)
        for item in items:
            jumlah_per_product[item['product_id']] += item['jumlah']
        # Cek stok cukup atau tidak
        ready = True
        for pid, total_jumlah in jumlah_per_product.items():
            if stock_map.get(pid, 0) < total_jumlah:
                ready = False
                break
        # Assign status ke semua baris id_pesanan ini
        for item in items:
            row = item['row']
            out_rows.append({
                'id_pesanan': row.get('id_pesanan'),
                'product_id': row.get('product_id'),
                'jumlah': row.get('jumlah'),
                'check_stock': 'ready' if ready else 'not ready'
            })
    return JsonResponse({'orders': out_rows})

@csrf_exempt
@require_POST
def edit_row(request):
    try:
        data = json.loads(request.body)
        id_pesanan = data.get('id_pesanan')
        product_id = data.get('product_id')
        jumlah = data.get('jumlah')
        if not (id_pesanan and product_id and jumlah is not None):
            return JsonResponse({'success': False, 'error': 'Missing parameters'})
        # Coba cari order berdasarkan id_pesanan dan product_id (bisa berupa PK atau id produk)
        order_qs = Order.objects.filter(id_pesanan=id_pesanan)
        # product_id bisa PK Product atau fallback ORDERPK_{order_pk}
        if str(product_id).startswith('ORDERPK_'):
            try:
                order_pk = int(str(product_id).replace('ORDERPK_', ''))
                order_qs = order_qs.filter(pk=order_pk)
            except Exception:
                return JsonResponse({'success': False, 'error': 'Invalid product_id'})
        else:
            order_qs = order_qs.filter(product_id=product_id)
        updated = order_qs.update(jumlah=jumlah)
        if updated:
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Order not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
@require_POST
def delete_row(request):
    try:
        data = json.loads(request.body)
        id_pesanan = data.get('id_pesanan')
        product_id = data.get('product_id')
        if not (id_pesanan and product_id):
            return JsonResponse({'success': False, 'error': 'Missing parameters'})
        order_qs = Order.objects.filter(id_pesanan=id_pesanan)
        if str(product_id).startswith('ORDERPK_'):
            try:
                order_pk = int(str(product_id).replace('ORDERPK_', ''))
                order_qs = order_qs.filter(pk=order_pk)
            except Exception:
                return JsonResponse({'success': False, 'error': 'Invalid product_id'})
        else:
            order_qs = order_qs.filter(product_id=product_id)
        deleted, _ = order_qs.delete()
        if deleted:
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Order not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
      
def orders_data(request):
    try:
        from orders.models import Order
        from products.models import Product
        filters = request.GET.get('filters') or request.POST.get('filters')
        if filters:
            if isinstance(filters, str):
                try:
                    filters = json.loads(filters.replace("'", '"'))
                except Exception:
                    filters = {}
        else:
            filters = {}
        brand = filters.get('brand', [])
        order_type = filters.get('order_type', [])
        nama_toko = filters.get('nama_toko', [])
        # Pastikan semua filter berupa list dan buang string kosong
        if isinstance(brand, str):
            brand = [brand] if brand else []
        brand = [b for b in brand if b]
        if isinstance(order_type, str):
            order_type = [order_type] if order_type else []
        order_type = [o for o in order_type if o]
        if isinstance(nama_toko, str):
            nama_toko = [nama_toko] if nama_toko else []
        nama_toko = [n for n in nama_toko if n]
        # Queryset dasar: status lunas dan nama_batch kosong/null
        orders = Order.objects.filter(status__iexact='Lunas').filter(Q(nama_batch__isnull=True) | Q(nama_batch='')).select_related('product')
        if order_type:
            orders = orders.filter(order_type__in=order_type)
        if nama_toko:
            orders = orders.filter(nama_toko__in=nama_toko)
        if brand:
            skus = list(Product.objects.filter(brand__in=brand).values_list('sku', flat=True))
            if skus:
                orders = orders.filter(sku__in=skus)
            else:
                orders = orders.none()
        data = []
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
        return JsonResponse({
            'draw': int(request.GET.get('draw', 1)),
            'recordsTotal': orders.count(),
            'recordsFiltered': orders.count(),
            'data': data
        })
    except Exception as e:
        logging.error(f"Error in orders_data view: {str(e)}")
        return JsonResponse({'error': 'Internal Server Error'}, status=500)

def batchlist_check_duplicate(request):
    nama_batch = request.GET.get('nama_batch', '').strip()
    exists = False
    if nama_batch:
        exists = BatchList.objects.filter(nama_batch__iexact=nama_batch).exists()
    return JsonResponse({'exists': exists})

def batchlist_list_open(request):
    # Ambil semua batch dengan status_batch 'pending' (atau definisi batch open)
    batchlists = list(BatchList.objects.filter(status_batch='pending').values_list('nama_batch', flat=True))
    return JsonResponse({'batchlists': batchlists})



def batchpicking(request, nama_batch):
    batch = get_object_or_404(BatchList, nama_batch=nama_batch)
    from orders.models import Order
    from products.models import Product, ProductsBundling

    orders = Order.objects.filter(nama_batch=nama_batch)

    # Existing logic to prepare table_data
    order_jumlah_per_product = defaultdict(int)
    for o in orders:
        if o.product_id:
            order_jumlah_per_product[o.product_id] += o.jumlah

    table_data = []
    for product_id, jumlah in order_jumlah_per_product.items():
        product = Product.objects.filter(id=product_id).first()
        if not product:
            continue
        batchitem, created = BatchItem.objects.get_or_create(batchlist=batch, product=product, defaults={
            'jumlah': jumlah,
            'jumlah_ambil': 0,
            'status_ambil': 'pending',
        })
        if not created and batchitem.jumlah != jumlah:
            batchitem.jumlah = jumlah
            batchitem.save()

    items = BatchItem.objects.filter(batchlist=batch).select_related('product')
    for item in items:
        product = item.product
        table_data.append({
            'id': item.id,  # Tambahkan ID BatchItem untuk kebutuhan data-product-id
            'sku': product.sku if product else '',
            'barcode': product.barcode if product else '',
            'nama_produk': product.nama_produk if product else '',
            'variant_produk': product.variant_produk if product else '',
            'brand': product.brand if product else '',
            'rack': product.rak if product else '',
            'jumlah': item.jumlah,
            'jumlah_ambil': item.jumlah_ambil,
            'status_ambil': item.status_ambil,
        })

    total_pending = sum(1 for item in table_data if item['status_ambil'] != 'completed')
    total_completed = sum(1 for item in table_data if item['status_ambil'] == 'completed')

    orders = orders.order_by('id')
    batchitems = BatchItem.objects.filter(batchlist=batch)
    batchitem_fifo = defaultdict(int)
    for bi in batchitems:
        batchitem_fifo[bi.product_id] += bi.jumlah_ambil

    orders_per_pesanan = defaultdict(list)
    for o in orders:
        orders_per_pesanan[o.id_pesanan].append(o)

    ready_to_pick_ids = []
    for id_pesanan, order_items in orders_per_pesanan.items():
        # Hanya SKU yang status_bundle != 'Y' yang dicek FIFO
        order_items_fifo = [item for item in order_items if item.status_bundle != 'Y']
        order_needs = defaultdict(int)
        for item in order_items_fifo:
            order_needs[item.product_id] += item.jumlah
        all_ready = True
        temp_fifo = batchitem_fifo.copy()
        for product_id, jumlah_needed in order_needs.items():
            if temp_fifo[product_id] < jumlah_needed:
                all_ready = False
                break
            temp_fifo[product_id] -= jumlah_needed
        if all_ready:
            ready_to_pick_ids.append(id_pesanan)

    ready_to_pick = len(ready_to_pick_ids)
    total_order = len(orders_per_pesanan)

    sku_to_satuan = defaultdict(int)
    sku_to_gabungan = defaultdict(int)
    for o in orders:
        if o.sku:
            if o.order_type == '1':
                sku_to_satuan[o.sku] += o.jumlah
            else:
                sku_to_gabungan[o.sku] += o.jumlah

    for row in table_data:
        row['satuan'] = sku_to_satuan.get(row['sku'], 0)
        row['gabungan'] = sku_to_gabungan.get(row['sku'], 0)

    for idp in ready_to_pick_ids:
        ReadyToPrint.objects.get_or_create(
            batchlist=batch,
            id_pesanan=idp,
            defaults={
                'status_print': 'pending',
                'printed_at': None,
            }
        )

    # Hitung ulang setelah data ReadyToPrint sudah pasti ada
    sat_count = ReadyToPrint.objects.filter(batchlist=batch, printed_at__isnull=True, order_type='1').values('id_pesanan').distinct().count()
    brand_count = ReadyToPrint.objects.filter(batchlist=batch, printed_at__isnull=True, order_type__in=['1', '4']).values('id_pesanan').distinct().count()
    mix_count = ReadyToPrint.objects.filter(batchlist=batch, printed_at__isnull=True).values('id_pesanan').distinct().count()
    # Ganti perhitungan sku_not_found dengan utilitas
    sku_not_found_list, sku_not_found_count = get_sku_not_found(nama_batch)

    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
        template = 'fullfilment/mobilebatchpicking.html'
    else:
        template = 'fullfilment/batchpicking.html'
    return render(request, template, {
        'nama_picklist': batch.nama_batch,
        'details': table_data,
        'total_pending': total_pending,
        'total_completed': total_completed,
        'total_order': total_order,
        'ready_to_pick': ready_to_pick,
        'ready_to_pick_ids': ready_to_pick_ids,
        'sat_count': sat_count,
        'mix_count': mix_count,
        'brand_count': brand_count,
        'sku_not_found_count': sku_not_found_count,
        'sku_not_found_list': sku_not_found_list,
    })


@csrf_exempt
def update_barcode_picklist(request, nama_batch):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)
    try:
        import json
        data = json.loads(request.body)
        barcode = data.get('barcode')
        if not barcode:
            return JsonResponse({'success': False, 'error': 'Barcode tidak ditemukan.'})
        batch = BatchList.objects.filter(nama_batch=nama_batch).first()
        if not batch:
            return JsonResponse({'success': False, 'error': 'Batch tidak ditemukan.'})
        from products.models import Product
        product = Product.objects.filter(barcode=barcode).first()
        if not product:
            return JsonResponse({'success': False, 'error': 'Produk dengan barcode ini tidak ditemukan.'})
        batchitem = BatchItem.objects.filter(batchlist=batch, product=product).first()
        if not batchitem:
            return JsonResponse({'success': False, 'error': 'Item tidak ditemukan di batch.'})
        if batchitem.jumlah_ambil < batchitem.jumlah:
            batchitem.jumlah_ambil += 1
            if batchitem.jumlah_ambil >= batchitem.jumlah:
                batchitem.status_ambil = 'completed'
            else:
                batchitem.status_ambil = 'pending'
            batchitem.save()
            # --- Update brand & order_type di ReadyToPrint jika ada ---
            from orders.models import Order
            order = Order.objects.filter(nama_batch=nama_batch, product=product, order_type__in=['1', '4']).first()
            if order:
                brand = order.product.brand if order.product else ''
                ReadyToPrint.objects.filter(id_pesanan=order.id_pesanan).update(brand=brand, order_type=order.order_type)
            return JsonResponse({'success': True, 'jumlah_ambil': batchitem.jumlah_ambil, 'status_ambil': batchitem.status_ambil})
        else:
            return JsonResponse({'success': False, 'error': 'Jumlah ambil sudah cukup.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def update_manual(request, nama_batch):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)
    try:
        data = json.loads(request.body)
        barcode = data.get('barcode')
        jumlah_ambil = data.get('jumlah_ambil')
        if not barcode or jumlah_ambil is None:
            return JsonResponse({'success': False, 'error': 'Barcode dan jumlah_ambil wajib diisi.'})
        # Find the batch and batch item
        batch = BatchList.objects.filter(nama_batch=nama_batch).first()
        if not batch:
            return JsonResponse({'success': False, 'error': 'Batch tidak ditemukan.'})
        from products.models import Product
        product = Product.objects.filter(barcode=barcode).first()
        if not product:
            return JsonResponse({'success': False, 'error': 'Produk dengan barcode ini tidak ditemukan.'})
        batchitem = BatchItem.objects.filter(batchlist=batch, product=product).first()
        if not batchitem:
            return JsonResponse({'success': False, 'error': 'Item tidak ditemukan di batch.'})
        # Validasi jumlah_ambil
        if not isinstance(jumlah_ambil, int):
            try:
                jumlah_ambil = int(jumlah_ambil)
            except Exception:
                return JsonResponse({'success': False, 'error': 'Jumlah ambil tidak valid.'})
        if jumlah_ambil < 0 or jumlah_ambil > batchitem.jumlah:
            return JsonResponse({'success': False, 'error': 'Jumlah ambil di luar batas.'})
        batchitem.jumlah_ambil = jumlah_ambil
        if batchitem.jumlah_ambil >= batchitem.jumlah:
            batchitem.status_ambil = 'completed'
        else:
            batchitem.status_ambil = 'pending'
        batchitem.save()
        # --- Update brand & order_type di ReadyToPrint jika ada ---
        order = Order.objects.filter(nama_batch=nama_batch, product=product, order_type__in=['1', '4']).first()
        if order:
            brand = order.product.brand if order.product else ''
            ReadyToPrint.objects.filter(id_pesanan=order.id_pesanan).update(brand=brand, order_type=order.order_type)
        return JsonResponse({'success': True, 'jumlah_ambil': batchitem.jumlah_ambil, 'status_ambil': batchitem.status_ambil})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# Ready to Print Table View
def ready_to_print_list(request):
    nama_batch = request.GET.get('nama_batch')
    batchlist_id = None
    ready_to_pick_ids = []
    if nama_batch:
        try:
            batchlist_obj = BatchList.objects.get(nama_batch=nama_batch)
            batchlist_id = batchlist_obj.id
            # --- Tambahan: sinkronisasi otomatis jika belum ada data ---
            # Cek apakah sudah ada ReadyToPrint untuk batch ini
            if not ReadyToPrint.objects.filter(batchlist=batchlist_obj).exists():
                # Hitung ready_to_pick_ids (copy logic dari batchpicking)
                from orders.models import Order
                from .models import BatchItem
                from collections import defaultdict
                orders = Order.objects.filter(nama_batch=nama_batch).order_by('id')
                batchitems = BatchItem.objects.filter(batchlist=batchlist_obj)
                batchitem_fifo = defaultdict(int)
                for bi in batchitems:
                    batchitem_fifo[bi.product_id] += bi.jumlah_ambil
                orders_per_pesanan = defaultdict(list)
                for o in orders:
                    orders_per_pesanan[o.id_pesanan].append(o)
                for id_pesanan, order_items in orders_per_pesanan.items():
                    order_needs = defaultdict(int)
                    for item in order_items:
                        order_needs[item.product_id] += item.jumlah
                    all_ready = True
                    temp_fifo = batchitem_fifo.copy()
                    for product_id, jumlah_needed in order_needs.items():
                        if temp_fifo[product_id] < jumlah_needed:
                            all_ready = False
                            break
                        temp_fifo[product_id] -= jumlah_needed
                    if all_ready:
                        for product_id, jumlah_needed in order_needs.items():
                            batchitem_fifo[product_id] -= jumlah_needed
                        ready_to_pick_ids.append(id_pesanan)
                # Insert ke ReadyToPrint jika belum ada
                for idp in ready_to_pick_ids:
                    ReadyToPrint.objects.get_or_create(
                        batchlist=batchlist_obj,
                        id_pesanan=idp,
                        defaults={
                            'status_print': 'pending',
                            'printed_at': None,
                        }
                    )
        except BatchList.DoesNotExist:
            batchlist_id = None
    if batchlist_id:
        queryset = ReadyToPrint.objects.filter(batchlist_id=batchlist_id)
    else:
        queryset = ReadyToPrint.objects.none()
    table = ReadyToPrintTable(queryset)
    RequestConfig(request).configure(table)
    return render(request, 'fullfilment/readytoprint.html', {
        'table': table,
        'nama_batch': nama_batch or '',
    })

@csrf_exempt
def ready_to_print_print(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    import json
    data = json.loads(request.body)
    ids = data.get('ids', [])
    now = timezone.now()
    updated = ReadyToPrint.objects.filter(id__in=ids, status_print='pending').update(status_print='printed', printed_at=now)
    return JsonResponse({'success': True, 'updated': updated})

def calculate_sat_mix(batch_name):
    orders = Order.objects.filter(nama_batch=batch_name)
    sku_to_satuan = defaultdict(int)
    sku_to_gabungan = defaultdict(int)

    for o in orders:
        if o.sku:
            if o.order_type == '1':
                sku_to_satuan[o.sku] += 1
            elif o.order_type == '4':
                sku_to_gabungan[o.sku] += 1

    return sku_to_satuan, sku_to_gabungan

@csrf_exempt
def batchpicking_view(request, batch_name):
    batch = get_object_or_404(BatchList, nama_batch=batch_name)
    sku_to_satuan, sku_to_gabungan = calculate_sat_mix(batch_name)

    items = BatchItem.objects.filter(batchlist=batch).select_related('product')
    table_data = []

    for item in items:
        product = item.product
        table_data.append({
            'id': item.id,  # Tambahkan ID BatchItem untuk kebutuhan data-product-id
            'sku': product.sku if product else '',
            'barcode': product.barcode if product else '',
            'nama_produk': product.nama_produk if product else '',
            'variant_produk': product.variant_produk if product else '',
            'brand': product.brand if product else '',
            'rack': product.rak if product else '',
            'jumlah': item.jumlah,
            'jumlah_ambil': item.jumlah_ambil,
            'status_ambil': item.status_ambil,
            'satuan': sku_to_satuan.get(product.sku, 0),
            'gabungan': sku_to_gabungan.get(product.sku, 0),
        })

    return render(request, 'fullfilment/batchpicking.html', {
        'details': table_data,
        'nama_picklist': batch.nama_batch,
    })

def update_ready_to_print():
    orders = Order.objects.filter(order_type='1')
    for order in orders:
        ReadyToPrint.objects.update_or_create(
            id_pesanan=order.id_pesanan,
            defaults={
                'brand': order.brand,
                'order_type': order.order_type,
            }
        )

def update_ready_to_print_sat():
    orders = Order.objects.filter(order_type='1')
    for order in orders:
        ReadyToPrint.objects.update_or_create(
            id_pesanan=order.id_pesanan,
            defaults={
                'brand': order.brand,
                'order_type': order.order_type,
            }
        )

def update_ready_to_print_mix():
    orders = Order.objects.filter(order_type='4')
    for order in orders:
        ReadyToPrint.objects.update_or_create(
            id_pesanan=order.id_pesanan,
            defaults={
                'brand': order.brand,
                'order_type': order.order_type,
            }
        )

def get_sat_brands(request):
    from products.models import Product
    nama_batch = request.GET.get('nama_batch')
    brand_count = {}
    brand_to_idpesanan = {}
    if nama_batch:
        # Ambil semua ReadyToPrint untuk batch ini, hanya yang belum pernah di-print
        rtp_qs = ReadyToPrint.objects.filter(batchlist__nama_batch=nama_batch, printed_at__isnull=True)
        for rtp in rtp_qs:
            # Cari semua order dengan id_pesanan ini
            orders = Order.objects.filter(id_pesanan=rtp.id_pesanan)
            # Cek order_type dari salah satu order (asumsi sama untuk satu id_pesanan)
            order_type = None
            if orders.exists():
                order_type = orders.first().order_type
            if order_type == '1':
                # Kumpulkan semua product_id dari orders
                product_ids = orders.values_list('product_id', flat=True)
                # Cari semua brand unik dari products_product
                brands_set = set()
                for pid in product_ids:
                    if pid:
                        product = Product.objects.filter(id=pid).first()
                        if product and product.brand:
                            brands_set.add(product.brand)
                for brand in brands_set:
                    if brand not in brand_count:
                        brand_count[brand] = 0
                        brand_to_idpesanan[brand] = set()
                    brand_count[brand] += 1
                    brand_to_idpesanan[brand].add(rtp.id_pesanan)
    # Format untuk frontend: list of dicts, sorted descending by totalOrders
    result = [
        {'brand': b, 'totalOrders': c, 'id_pesanan_list': list(brand_to_idpesanan[b])}
        for b, c in brand_count.items()
    ]
    result = sorted(result, key=lambda x: x['totalOrders'], reverse=True)
    return JsonResponse({'success': True, 'brands': result})

from django.http import HttpResponse
import pandas as pd

def print_sat_brand(request):
    brand = request.GET.get('brand')
    nama_batch = request.GET.get('nama_batch')
    if not brand or not nama_batch:
        return JsonResponse({'success': False, 'error': 'Brand dan batch harus diisi'})
    from products.models import Product
    from orders.models import Order
    from .models import ReadyToPrint
    # Temukan semua id_pesanan di ReadyToPrint batch ini yang brand-nya cocok (order_type=1) dan belum pernah di-print
    rtp_qs = ReadyToPrint.objects.filter(batchlist__nama_batch=nama_batch, printed_at__isnull=True)
    idpesanan_set = set()
    rtp_ids_to_update = []
    for rtp in rtp_qs:
        orders = Order.objects.filter(id_pesanan=rtp.id_pesanan)
        order_type = None
        if orders.exists():
            order_type = orders.first().order_type
        if order_type == '1':
            product_ids = orders.values_list('product_id', flat=True)
            brands_set = set()
            for pid in product_ids:
                if pid:
                    product = Product.objects.filter(id=pid).first()
                    if product and product.brand == brand:
                        brands_set.add(product.brand)
            if brand in brands_set:
                idpesanan_set.add(rtp.id_pesanan)
                rtp_ids_to_update.append(rtp.id)
    # Buat DataFrame dan export ke Excel
    df = pd.DataFrame({'ID Pesanan': list(idpesanan_set)})
    file_path = f'static/print_sat_{brand}.xlsx'
    df.to_excel(file_path, index=False)
    # Update status_print dan printed_at di ReadyToPrint
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    now_jakarta = timezone.now().astimezone(jakarta_tz)
    ReadyToPrint.objects.filter(id__in=rtp_ids_to_update).update(status_print='printed', printed_at=now_jakarta)
    return JsonResponse({'success': True, 'file_path': '/' + file_path})

def print_all_sat_brands(request):
    nama_batch = request.GET.get('nama_batch')
    if not nama_batch:
        return JsonResponse({'success': False, 'error': 'Batch harus diisi'})

    from products.models import Product
    from orders.models import Order
    from .models import ReadyToPrint

    # Temukan semua id_pesanan di ReadyToPrint batch ini yang belum pernah di-print
    rtp_qs = ReadyToPrint.objects.filter(batchlist__nama_batch=nama_batch, printed_at__isnull=True)
    idpesanan_set = set()
    rtp_ids_to_update = []

    for rtp in rtp_qs:
        orders = Order.objects.filter(id_pesanan=rtp.id_pesanan)
        order_type = None
        if orders.exists():
            order_type = orders.first().order_type
        if order_type == '1':
            idpesanan_set.add(rtp.id_pesanan)
            rtp_ids_to_update.append(rtp.id)

    # Buat DataFrame dan export ke Excel
    df = pd.DataFrame({'ID Pesanan': list(idpesanan_set)})
    file_path = f'static/print_sat_all.xlsx'
    df.to_excel(file_path, index=False)

    # Update status_print dan printed_at di ReadyToPrint
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    now_jakarta = timezone.now().astimezone(jakarta_tz)
    ReadyToPrint.objects.filter(id__in=rtp_ids_to_update).update(status_print='printed', printed_at=now_jakarta)

    return JsonResponse({'success': True, 'file_path': '/' + file_path})

def get_brand_data(request):
    nama_batch = request.GET.get('nama_batch')
    if not nama_batch:
        return JsonResponse({'success': False, 'error': 'Batch harus diisi'})

    from products.models import Product
    from orders.models import Order
    from .models import ReadyToPrint

    # Ambil semua brand dengan order_type 1 dan 4
    rtp_qs = ReadyToPrint.objects.filter(batchlist__nama_batch=nama_batch, printed_at__isnull=True)
    brand_data = {}

    for rtp in rtp_qs:
        orders = Order.objects.filter(id_pesanan=rtp.id_pesanan)
        order_type = None
        if orders.exists():
            order_type = orders.first().order_type
        if order_type in ['1', '4']:
            product_ids = orders.values_list('product_id', flat=True)
            for pid in product_ids:
                if pid:
                    product = Product.objects.filter(id=pid).first()
                    if product:
                        brand = product.brand
                        if brand not in brand_data:
                            brand_data[brand] = 0
                        brand_data[brand] += 1

    # Sort brands by total orders descending
    sorted_brands = sorted(brand_data.items(), key=lambda x: x[1], reverse=True)
    brands = [{'brand': b[0], 'totalOrders': b[1]} for b in sorted_brands]

    return JsonResponse({'success': True, 'brands': brands})

def print_all_brands(request):
    nama_batch = request.GET.get('nama_batch')
    if not nama_batch:
        return JsonResponse({'success': False, 'error': 'Batch harus diisi'})

    from products.models import Product
    from orders.models import Order
    from .models import ReadyToPrint

    # Temukan semua id_pesanan di ReadyToPrint batch ini yang belum pernah di-print
    rtp_qs = ReadyToPrint.objects.filter(batchlist__nama_batch=nama_batch, printed_at__isnull=True)
    idpesanan_set = set()
    rtp_ids_to_update = []

    for rtp in rtp_qs:
        orders = Order.objects.filter(id_pesanan=rtp.id_pesanan)
        order_type = None
        if orders.exists():
            order_type = orders.first().order_type
        if order_type in ['1', '4']:
            idpesanan_set.add(rtp.id_pesanan)
            rtp_ids_to_update.append(rtp.id)

    # Buat DataFrame dan export ke Excel
    df = pd.DataFrame({'ID Pesanan': list(idpesanan_set)})
    file_path = f'static/print_all_brands.xlsx'
    df.to_excel(file_path, index=False)

    # Update status_print dan printed_at di ReadyToPrint
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    now_jakarta = timezone.now().astimezone(jakarta_tz)
    ReadyToPrint.objects.filter(id__in=rtp_ids_to_update).update(status_print='printed', printed_at=now_jakarta)

    return JsonResponse({'success': True, 'file_path': '/' + file_path})

def print_brand(request):
    brand = request.GET.get('brand')
    nama_batch = request.GET.get('nama_batch')
    if not brand or not nama_batch:
        return JsonResponse({'success': False, 'error': 'Brand dan batch harus diisi'})

    from products.models import Product
    from orders.models import Order
    from .models import ReadyToPrint

    # Temukan semua id_pesanan di ReadyToPrint batch ini yang brand-nya cocok (order_type=1, 2, atau 4) dan belum pernah di-print
    rtp_qs = ReadyToPrint.objects.filter(batchlist__nama_batch=nama_batch, printed_at__isnull=True)
    idpesanan_set = set()
    rtp_ids_to_update = []

    for rtp in rtp_qs:
        orders = Order.objects.filter(id_pesanan=rtp.id_pesanan)
        order_type = None
        if orders.exists():
            order_type = orders.first().order_type
        if order_type in ['1', '2', '4']:
            product_ids = orders.values_list('product_id', flat=True)
            brands_set = set()
            for pid in product_ids:
                if pid:
                    product = Product.objects.filter(id=pid).first()
                    if product and product.brand == brand:
                        brands_set.add(product.brand)
            if brand in brands_set:
                idpesanan_set.add(rtp.id_pesanan)
                rtp_ids_to_update.append(rtp.id)

    # Buat DataFrame dan export ke Excel
    df = pd.DataFrame({'ID Pesanan': list(idpesanan_set)})
    file_path = f'static/print_brand_{brand}.xlsx'
    df.to_excel(file_path, index=False)

    # Update status_print dan printed_at di ReadyToPrint
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    now_jakarta = timezone.now().astimezone(jakarta_tz)
    ReadyToPrint.objects.filter(id__in=rtp_ids_to_update).update(status_print='printed', printed_at=now_jakarta)

    return JsonResponse({'success': True, 'file_path': '/' + file_path})

@csrf_exempt
@require_POST
def print_mix(request, nama_batch):
    # Support both POST JSON and form POST
    if request.content_type == 'application/json':
        # Accept empty body, nama_batch from URL
        pass
    elif request.content_type == 'application/x-www-form-urlencoded':
        # Accept form POST, fallback
        pass
    # Fetch all id_pesanan from ReadyToPrint for the given batch
    rtp_qs = ReadyToPrint.objects.filter(batchlist__nama_batch=nama_batch, printed_at__isnull=True)
    idpesanan_set = rtp_qs.values_list('id_pesanan', flat=True)
    # Generate Excel file
    file_path = f'static/print_mix_{nama_batch}.xlsx'
    import pandas as pd
    df = pd.DataFrame({'ID Pesanan': list(idpesanan_set)})
    df.to_excel(file_path, index=False)
    # Update status_print and printed_at fields
    import pytz
    from django.utils import timezone
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    now_jakarta = timezone.now().astimezone(jakarta_tz)
    rtp_qs.update(status_print='printed', printed_at=now_jakarta)
    return JsonResponse({'success': True, 'file_path': '/' + file_path})

# Hapus view batchitem_detail_view dan endpoint terkait
def batchitem_detail_view(request, pk):
    batchitem = get_object_or_404(BatchItem, pk=pk)
    product = batchitem.product
    return render(request, 'fullfilment/batchitem_detail.html', {
        'product': product,
        'jumlah': batchitem.jumlah,
        'jumlah_ambil': batchitem.jumlah_ambil
    })

@require_POST
@csrf_exempt
def batchlist_delete(request, batch_id):
    from django.contrib import messages
    from orders.models import Order
    batch = BatchList.objects.filter(id=batch_id).first()
    if batch:
        # Hapus semua Order yang memiliki nama_batch sama
        deleted_orders, _ = Order.objects.filter(nama_batch=batch.nama_batch).delete()
        batch.delete()
        messages.success(request, f"Batchlist dengan ID {batch_id} dan {deleted_orders} order terkait berhasil dihapus.")
    else:
        messages.error(request, f"Batchlist dengan ID {batch_id} tidak ditemukan.")
    from django.shortcuts import redirect
    return redirect('fullfilment_index')

def batchpicking_sku_not_found_details(request, nama_batch):
    sku_not_found_list, _ = get_sku_not_found(nama_batch)
    return JsonResponse({'sku_not_found_list': sku_not_found_list})

@csrf_exempt
def mix_count_api(request):
    """Return total order mix (id_pesanan unik) dengan printed_at IS NULL untuk batch tertentu."""
    nama_batch = request.GET.get('nama_batch') or request.GET.get('batch_name')
    if not nama_batch:
        return JsonResponse({'success': False, 'error': 'Missing batch name'})
    batchlist = BatchList.objects.filter(nama_batch=nama_batch).first()
    if not batchlist:
        return JsonResponse({'success': False, 'error': 'Batch not found'})
    # Ambil id_pesanan unik yang printed_at IS NULL di ReadyToPrint
    mix_count = ReadyToPrint.objects.filter(batchlist=batchlist, printed_at__isnull=True).values('id_pesanan').distinct().count()
    return JsonResponse({'success': True, 'mix_count': mix_count})

def api_idpesanan_in_batch(request):
    from orders.models import Order
    nama_batch = request.GET.get('nama_batch')
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 25))
    if not nama_batch:
        return JsonResponse({'idpesanan_list': [], 'has_next': False, 'page': page})
    qs = Order.objects.filter(nama_batch=nama_batch).values_list('id_pesanan', flat=True).distinct()
    total = qs.count()
    start = (page - 1) * per_page
    end = start + per_page
    idpesanan_list = list(qs[start:end])
    has_next = end < total
    return JsonResponse({'idpesanan_list': idpesanan_list, 'has_next': has_next, 'page': page})

@csrf_exempt
def batchitem_update_jumlah_ambil(request, pk):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            jumlah_ambil = int(data.get('jumlah_ambil', 0))
            batchitem = get_object_or_404(BatchItem, pk=pk)
            if jumlah_ambil > batchitem.jumlah:
                return JsonResponse({'success': False, 'error': 'Jumlah ambil tidak boleh lebih dari jumlah'})
            batchitem.jumlah_ambil = jumlah_ambil
            # Auto update status_ambil jika sudah penuh
            if batchitem.jumlah_ambil >= batchitem.jumlah:
                batchitem.status_ambil = 'completed'
            else:
                batchitem.status_ambil = 'pending'
            batchitem.save()
            return JsonResponse({'success': True, 'completed': batchitem.status_ambil == 'completed'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid method'})

