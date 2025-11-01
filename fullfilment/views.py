from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.db import transaction
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required

# Third-party
from openpyxl import Workbook
from django_tables2 import RequestConfig
# from asgiref.sync import async_to_sync
# from channels.layers import get_channel_layer
from django.utils.encoding import smart_str
from django.template.loader import render_to_string
from itertools import groupby
from operator import attrgetter
import io
from django.core.paginator import Paginator
from django.middleware.csrf import get_token

# App imports
from .models import BatchList, BatchItem, ReadyToPrint, BatchItemLog, BatchOrderLog, OrderCancelLog, ReturnSession, ReturnItem
from orders.models import Order, OrderPackingHistory, OrderHandoverHistory, OrderPrintHistory
from inventory.models import Stock, OpnameQueue, StockCardEntry
from products.models import Product, ProductExtraBarcode
from inventory.models import Rak
from .tables import ReadyToPrintTable
from .utils import get_sku_not_found
from django.db.models import F, Sum, OuterRef, Subquery, Min, Window, Case, When, Value, IntegerField
from django.db.models.functions import Coalesce, RowNumber
from django.db.models import Count, Max, Exists
from django.contrib.auth.models import User
from collections import defaultdict

from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import ImageOps
from django.contrib.contenttypes.models import ContentType
from .readytoprint_logic import calculate_and_sync_ready_to_print # <-- 1. Impor fungsi baru

import json
import logging
from collections import defaultdict, Counter
import datetime
import time
import pytz

# Import dashboard logic
from .dashboard import dashboard as dashboard_view
from django.core.exceptions import PermissionDenied

def get_device_type(request):
    """
    Helper function untuk detect device type
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    return 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent

def check_permission_by_device(request, permission_name):
    """
    Helper function untuk check permission berdasarkan device type
    """
    is_mobile = get_device_type(request)
    
    if is_mobile:
        mobile_permission = f'fullfilment.view_mobile_{permission_name}'
        legacy_permission = f'fullfilment.view_{permission_name}'
        return request.user.has_perm(mobile_permission) or request.user.has_perm(legacy_permission)
    else:
        desktop_permission = f'fullfilment.view_desktop_{permission_name}'
        legacy_permission = f'fullfilment.view_{permission_name}'
        return request.user.has_perm(desktop_permission) or request.user.has_perm(legacy_permission)

@login_required
def index(request):
    # Permission check untuk mobile vs desktop menggunakan helper function
    from django.core.exceptions import PermissionDenied
    if not check_permission_by_device(request, 'batchlist'):
        is_mobile = get_device_type(request)
        device_type = "mobile" if is_mobile else "desktop"
        raise PermissionDenied(f"Anda tidak memiliki akses ke {device_type} batch list")

    # Tambahkan subquery untuk mengecek keberadaan order
    order_exists_subquery = Order.objects.filter(nama_batch=OuterRef('nama_batch')).values('pk')
    
    base_queryset = BatchList.objects.annotate(
        has_orders=Exists(order_exists_subquery),
        status_order=Case(
            When(status_batch='open', then=Value(1)),
            When(status_batch='closed', then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
    ).order_by('status_order', '-created_at')  # Open batch dulu, lalu closed batch

    paginator = Paginator(base_queryset, 25) # 25 batch per halaman
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Hitung summary untuk batch yang masih open
    open_batches = BatchList.objects.filter(status_batch='open')
    total_open_batches = open_batches.count()
    
    # Summary untuk batch open (sisanya tetap berdasarkan status OPEN)
    total_sku_open = 0
    total_sku_completed_open = 0
    total_orders_open = 0
    total_orders_to_pick_open = 0
    total_orders_printed_open = 0
    total_unallocated_sku_open = 0
    total_over_stock_open = 0
    
    for open_batch in open_batches:
        batch_items = BatchItem.objects.filter(batchlist=open_batch)
        total_sku_open += batch_items.count()
        total_sku_completed_open += batch_items.filter(jumlah_ambil__gte=F('jumlah')).count()
        total_over_stock_open += batch_items.filter(jumlah_ambil__gt=F('jumlah')).count()
        
        # Orders
        batch_orders = Order.objects.filter(nama_batch=open_batch.nama_batch).exclude(status_bundle='Y')
        total_orders_open += batch_orders.values('id_pesanan').distinct().count()
        total_orders_to_pick_open += ReadyToPrint.objects.filter(batchlist=open_batch).values_list('id_pesanan', flat=True).distinct().count()
        total_orders_printed_open += ReadyToPrint.objects.filter(batchlist=open_batch, printed_at__isnull=False).values_list('id_pesanan', flat=True).distinct().count()
        
        # Unallocated SKU
        picked_quantities = batch_items.values('product_id').annotate(total_picked=Sum('jumlah_ambil'))
        ready_to_print_ids = ReadyToPrint.objects.filter(batchlist=open_batch).values_list('id_pesanan', flat=True)
        needed_quantities = Order.objects.filter(nama_batch=open_batch.nama_batch, id_pesanan__in=ready_to_print_ids).values('product_id').annotate(total_needed=Sum('jumlah'))
        
        picked_map = {item['product_id']: item['total_picked'] for item in picked_quantities}
        needed_map = {item['product_id']: item['total_needed'] for item in needed_quantities}
        
        product_ids = set(picked_map.keys()).union(set(needed_map.keys()))
        for product_id in product_ids:
            picked_qty = picked_map.get(product_id, 0)
            needed_qty = needed_map.get(product_id, 0)
            if picked_qty > needed_qty:
                total_unallocated_sku_open += 1
    
    # Hitung summary untuk SEMUA batch (tidak terbatas yang open saja)
    all_batches = BatchList.objects.all()
    
    # 1. Order Gantung - dari semua batch
    total_orders_gantung_all = 0
    for batch in all_batches:
        total_orders_gantung_all += len(get_not_ready_to_pick_ids(batch))
    
    # 2. SKU Overstock - dari semua batch
    total_over_stock_all = 0
    for batch in all_batches:
        batch_items = BatchItem.objects.filter(batchlist=batch)
        total_over_stock_all += batch_items.filter(jumlah_ambil__gt=F('jumlah')).count()
    
    # 3. SKU Gantung - dari semua batch
    total_unallocated_sku_all = 0
    for batch in all_batches:
        batch_items = BatchItem.objects.filter(batchlist=batch)
        picked_quantities = batch_items.values('product_id').annotate(total_picked=Sum('jumlah_ambil'))
        ready_to_print_ids = ReadyToPrint.objects.filter(batchlist=batch).values_list('id_pesanan', flat=True)
        needed_quantities = Order.objects.filter(nama_batch=batch.nama_batch, id_pesanan__in=ready_to_print_ids).values('product_id').annotate(total_needed=Sum('jumlah'))
        
        picked_map = {item['product_id']: item['total_picked'] for item in picked_quantities}
        needed_map = {item['product_id']: item['total_needed'] for item in needed_quantities}
        
        product_ids = set(picked_map.keys()).union(set(needed_map.keys()))
        for product_id in product_ids:
            picked_qty = picked_map.get(product_id, 0)
            needed_qty = needed_map.get(product_id, 0)
            if picked_qty > needed_qty:
                total_unallocated_sku_all += 1
    
    # Lakukan kalkulasi hanya untuk batch di halaman saat ini
    for batch in page_obj:
        sku_not_found_list, sku_not_found_count = get_sku_not_found(batch.nama_batch)
        batch.sku_not_found_count = sku_not_found_count
        batch.sku_not_found_list = sku_not_found_list

        # Hitung SKU Completed dan Over Stock
        batch_items = BatchItem.objects.filter(batchlist=batch)
        total_sku_batch_items = batch_items.count()
        completed_sku = batch_items.filter(jumlah_ambil__gte=F('jumlah')).count()
        
        # Hitung Over Stock: Jumlah BatchItem dimana jumlah_ambil > jumlah
        over_stock_count = batch_items.filter(jumlah_ambil__gt=F('jumlah')).count()

        # HITUNG SKU GANTUNG - Menggunakan logika yang sama dengan unallocated_stock_list
        initial_needed_quantities_batchitem = batch_items.values('product_id').annotate(
            total_needed_batchitem=Sum('jumlah')
        )
        initial_needed_quantities_batchitem_map = {
            item['product_id']: item['total_needed_batchitem'] 
            for item in initial_needed_quantities_batchitem
        }

        # 1. Hitung total jumlah_ambil per produk di batch ini
        picked_quantities = batch_items.values('product_id').annotate(
            total_picked=Sum('jumlah_ambil')
        )
        picked_quantities_map = {
            item['product_id']: item['total_picked'] 
            for item in picked_quantities
        }

        # 2. Ambil semua id_pesanan yang READY TO PRINT di batch ini
        ready_to_print_ids = ReadyToPrint.objects.filter(batchlist=batch).values_list('id_pesanan', flat=True)

        # 3. Hitung total jumlah_dibutuhkan per produk dari order yang READY TO PRINT
        needed_quantities = Order.objects.filter(
            nama_batch=batch.nama_batch, 
            id_pesanan__in=ready_to_print_ids
        ).values('product_id').annotate(total_needed=Sum('jumlah'))

        needed_quantities_map = {
            item['product_id']: item['total_needed'] 
            for item in needed_quantities
        }

        # 4. Bandingkan picked vs needed untuk menemukan stok gantung
        product_ids_in_batch = set(picked_quantities_map.keys()).union(set(needed_quantities_map.keys()))
        
        unallocated_products_data = []
        for product_id in product_ids_in_batch:
            picked_qty = picked_quantities_map.get(product_id, 0)
            needed_qty = needed_quantities_map.get(product_id, 0)
            unallocated_qty = picked_qty - needed_qty

            if unallocated_qty > 0: # Hanya tampilkan jika ada surplus
                unallocated_products_data.append({
                    'product_id': product_id,
                    'unallocated_quantity': unallocated_qty,
                })

        # Total unique unallocated products (SKU Gantung)
        unallocated_sku_count = len(unallocated_products_data)

        # PERBAIKAN: Pastikan semua nilai ter-assign dengan benar
        batch.total_sku = total_sku_batch_items
        batch.sku_completed = completed_sku
        batch.unallocated_sku = unallocated_sku_count  # SKU GANTUNG
        batch.over_stock_count = over_stock_count # Assign nilai over_stock_count

        # NEW METRICS for expandable row (from readytoprint.html logic)
        # Total Order: Total unique id_pesanan for this batch
        batch_orders_qs = Order.objects.filter(nama_batch=batch.nama_batch).exclude(status_bundle='Y')
        batch.total_orders_in_batch = batch_orders_qs.values('id_pesanan').distinct().count()

        # Order to Pick (Ready to Pick): Count of unique id_pesanan in ReadyToPrint for this batch
        batch.orders_to_pick = ReadyToPrint.objects.filter(batchlist=batch).values_list('id_pesanan', flat=True).distinct().count()

        # Order Printed: Count of unique id_pesanan in ReadyToPrint where printed_at is not null
        batch.orders_printed = ReadyToPrint.objects.filter(batchlist=batch, printed_at__isnull=False).values_list('id_pesanan', flat=True).distinct().count()

        # Order Gantung (Not Ready to Pick): Count of unique id_pesanan in Order but NOT in ReadyToPrint
        batch.orders_gantung = len(get_not_ready_to_pick_ids(batch)) # get_not_ready_to_pick_ids already exists and returns a list
        
        # Hitung persentase pengambilan berdasarkan jumlah vs jumlah_ambil
        if total_sku_batch_items > 0:
            # Hitung total quantity yang dibutuhkan dan yang sudah diambil
            total_jumlah = batch_items.aggregate(total=Sum('jumlah'))['total'] or 0
            total_jumlah_ambil = batch_items.aggregate(total=Sum('jumlah_ambil'))['total'] or 0
            
            if total_jumlah > 0:
                percentage = min(100, (total_jumlah_ambil / total_jumlah) * 100)
                batch.status_pengambilan_display = f"{percentage:.0f}% ({total_jumlah_ambil}/{total_jumlah})"
            else:
                batch.status_pengambilan_display = "0% (0/0)"
        else:
            batch.status_pengambilan_display = "No Items"

    context = {
        'page_obj': page_obj,
        'summary_open_batches': {
            'total_batches': total_open_batches,
            'total_sku': total_sku_open,
            'total_sku_completed': total_sku_completed_open,
            'total_orders': total_orders_open,
            'total_orders_to_pick': total_orders_to_pick_open,
            'total_orders_printed': total_orders_printed_open,
            'total_orders_gantung': total_orders_gantung_all,  # Dari semua batch
            'total_unallocated_sku': total_unallocated_sku_all,  # Dari semua batch
            'total_over_stock': total_over_stock_all,  # Dari semua batch
        }
    }
    
    # Determine template berdasarkan device type
    is_mobile = get_device_type(request)
    if is_mobile:
        template_name = 'fullfilment/mobile_index.html'
    else:
        template_name = 'fullfilment/index.html'

    return render(request, template_name, context)

@login_required
def unique_brands(request):
    # Get all SKUs from orders
    skus = Order.objects.values_list('sku', flat=True)
    # Get unique brands from products with those SKUs
    brands = Product.objects.filter(sku__in=skus).values_list('brand', flat=True).distinct()
    brands = [b for b in brands if b]  # Remove empty/null brands
    return JsonResponse({'brands': brands})

@csrf_exempt
@require_POST
@login_required
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
@login_required
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
@login_required
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
      
@login_required
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

@login_required
@permission_required('fullfilment.view_batchlist', raise_exception=True)
def batchlist_check_duplicate(request):
    nama_batch = request.GET.get('nama_batch', '').strip()
    exists = False
    if nama_batch:
        exists = BatchList.objects.filter(nama_batch__iexact=nama_batch).exists()
    return JsonResponse({'exists': exists})

@login_required
@permission_required('fullfilment.view_batchlist', raise_exception=True)
def batchlist_list_open(request):
    # Ambil semua batch dengan status_batch 'open'
    batchlists = list(BatchList.objects.filter(status_batch='open').values_list('nama_batch', flat=True))
    return JsonResponse({'batchlists': batchlists})

@login_required
def batchpicking(request, nama_batch):
    # Permission check untuk desktop batchpicking
    from django.core.exceptions import PermissionDenied
    if not check_permission_by_device(request, 'batchpicking'):
        is_mobile = get_device_type(request)
        device_type = "mobile" if is_mobile else "desktop"
        raise PermissionDenied(f"Anda tidak memiliki akses ke {device_type} batchpicking")
    
    batch = get_object_or_404(BatchList, nama_batch=nama_batch)
    from orders.models import Order
    from products.models import Product

    # NEW: Auto-clean batchitems dengan jumlah = 0 dan jumlah_ambil = 0
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Cari dan hapus batchitem yang jumlah = 0 dan jumlah_ambil = 0
        empty_batchitems = BatchItem.objects.filter(
            batchlist=batch,
            jumlah=0,
            jumlah_ambil=0
        )
        
        deleted_count = empty_batchitems.count()
        if deleted_count > 0:
            # Log sebelum delete untuk audit trail
            logger.info(f"Auto-cleaning {deleted_count} empty batchitems from batch {nama_batch}")
            
            # Delete batchitems
            empty_batchitems.delete()
            
            logger.info(f"Successfully auto-deleted {deleted_count} empty batchitems from batch {nama_batch}")
        else:
            logger.debug(f"No empty batchitems found in batch {nama_batch}")
            
    except Exception as e:
        logger.error(f"Error auto-cleaning empty batchitems in batch {nama_batch}: {str(e)}")
        # Continue execution even if cleanup fails

    # --- 1. Pastikan semua BatchItem untuk batch ini sudah ada ---
    orders = Order.objects.filter(nama_batch=nama_batch).exclude(status_bundle='Y').order_by('id')
    order_jumlah_per_product = defaultdict(int)
    for o in orders:
        if o.product_id:
            order_jumlah_per_product[o.product_id] += o.jumlah

    for product_id, jumlah in order_jumlah_per_product.items():
        product = Product.objects.filter(id=product_id).first()
        if not product:
            continue
        batchitem, created = BatchItem.objects.get_or_create(
            batchlist=batch, 
            product=product, 
            defaults={
                'jumlah': jumlah,
                'jumlah_ambil': 0,
                'status_ambil': 'pending',
            }
        )
        if not created and batchitem.jumlah != jumlah:
            batchitem.jumlah = jumlah
            batchitem.save()

    # --- 2. HITUNG STATUS BERDASARKAN JUMLAH DAN JUMLAH_AMBIL ---
    items = BatchItem.objects.filter(batchlist=batch).select_related('product')
    
    for item in items:
        # Simpan status lama untuk perbandingan
        old_status = item.status_ambil
        
        # Hitung status berdasarkan perbandingan jumlah dan jumlah_ambil
        if item.jumlah_ambil == 0:
            item.status_ambil = 'pending'
        elif item.jumlah_ambil > 0 and item.jumlah_ambil < item.jumlah:
            item.status_ambil = 'partial'
        elif item.jumlah_ambil > item.jumlah:
            item.status_ambil = 'over_stock'
        elif item.jumlah_ambil == item.jumlah:
            item.status_ambil = 'completed'
        
        # Update status di database jika berubah
        if old_status != item.status_ambil:  # Jika ada perubahan
            item.save()

    # --- 3. Siapkan data untuk ditampilkan di template ---
    table_data = []
    # PERBAIKAN: Urutkan berdasarkan completed_at terbaru lebih dulu, lalu status (completed di atas)
    items = BatchItem.objects.filter(batchlist=batch).select_related('product').order_by('-completed_at', 'status_ambil')
    
    for item in items:
        product = item.product
        
        over_qty_display = None
        if item.status_ambil == 'over_stock':
            over_qty_display = item.jumlah_ambil - item.jumlah # Hitung selisih di view

        table_data.append({
            'id': item.id,
            'sku': product.sku if product else '',
            'barcode': product.barcode if product else '',
            'nama_produk': product.nama_produk if product else '',
            'variant_produk': product.variant_produk if product else '',
            'brand': product.brand if product else '',
            'rak': product.rak if product else '',
            'jumlah': item.jumlah,
            'jumlah_ambil': item.jumlah_ambil,
            'jumlah_transfer': getattr(item, 'jumlah_transfer', None),  # Kosongkan jika tidak ada
            'status_ambil': item.status_ambil,
            'photo_url': product.photo.url if product and product.photo else '',
            'count_one': item.one_count,
            'count_duo': item.duo_count,
            'count_tri': item.tri_count,
            'over_qty_display': over_qty_display, # Tambahkan nilai ini ke context
        })

    # --- 4. Hitung nilai summary lainnya ---
    total_completed = sum(1 for item in table_data if item['status_ambil'] == 'completed')
    
    # Hitung jumlah untuk setiap status
    status_counts = Counter(item['status_ambil'] for item in table_data if item['status_ambil'] != 'completed')
    total_pending = sum(status_counts.values()) # total_pending adalah semua yang belum completed

    sku_not_found_list, sku_not_found_count = get_sku_not_found(nama_batch)
    
    # --- 5. Tentukan template dan render ---
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    template = 'fullfilment/mobilebatchpicking.html' if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent else 'fullfilment/batchpicking.html'
        
    # NEW: Tambahkan info cleanup ke context untuk debugging
    cleanup_info = {
        'batch_name': nama_batch,
        'total_items_after_cleanup': len(table_data),
        'auto_cleanup_enabled': True
    }

    context = {
        'nama_picklist': batch.nama_batch,
        'details': table_data,
        'total_pending': total_pending,
        'total_completed': total_completed,
        'sku_not_found_count': sku_not_found_count,
        'sku_not_found_list': sku_not_found_list,
        'nama_batch': nama_batch,
        'status_counts': dict(status_counts), # DIUBAH: Konversi ke dict
        'cleanup_info': cleanup_info, # NEW: Info cleanup untuk debugging
    }
    return render(request, template, context)


@csrf_exempt
@require_POST
@login_required
def update_barcode_picklist(request, nama_batch):
    start_time = time.perf_counter()
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)
    try:
        import json
        from inventory.models import Stock
        t0 = time.perf_counter()
        data = json.loads(request.body)
        t1 = time.perf_counter()
        barcode = data.get('barcode')
        if not barcode:
            return JsonResponse({'success': False, 'error': 'Barcode tidak ditemukan.'})
        batch = BatchList.objects.filter(nama_batch=nama_batch).first()
        t2 = time.perf_counter()
        if not batch:
            return JsonResponse({'success': False, 'error': 'Batch tidak ditemukan.'})
        
        # --- TAMBAHAN BARU: Cek status batch ---
        if batch.status_batch == 'closed':
            return JsonResponse({'success': False, 'error': f"Batch '{nama_batch}' sudah ditutup. Tidak bisa melakukan update scan barcode."})
        # --- AKHIR TAMBAHAN BARU ---
        
        # Cek barcode utama
        product = Product.objects.filter(barcode=barcode).first()
        
        # JIKA TIDAK DITEMUKAN, CEK BARCODE TAMBAHAN
        if not product:
            extra_barcode_entry = ProductExtraBarcode.objects.filter(barcode=barcode).select_related('product').first()
            if extra_barcode_entry:
                product = extra_barcode_entry.product # Ambil produk dari relasi

        t3 = time.perf_counter()
        if not product:
            return JsonResponse({'success': False, 'error': 'Produk dengan barcode ini tidak ditemukan.'})
            
        batchitem = BatchItem.objects.filter(batchlist=batch, product=product).first()
        t4 = time.perf_counter()
        if not batchitem:
            return JsonResponse({'success': False, 'error': 'Item tidak ditemukan di batch.'})

        # PENANGANAN EKSPLISIT UNTUK ITEM YANG SUDAH SELESAI
        if batchitem.status_ambil == 'completed':
            # --- BLOK PERBAIKAN TIMEZONE ---
            if batchitem.completed_at:
                jakarta_tz = pytz.timezone('Asia/Jakarta')
                completed_at_jakarta = batchitem.completed_at.astimezone(jakarta_tz)
                completed_time = completed_at_jakarta.strftime('%d %b %Y, %H:%M:%S')
            else:
                completed_time = 'N/A'
            # --- AKHIR BLOK PERBAIKAN ---
            
            completed_user = batchitem.completed_by.username if batchitem.completed_by else 'N/A'
            logging.info(f"[PROFILING] update_barcode_picklist: total={time.perf_counter()-start_time:.4f}s | json={t1-t0:.4f}s | batch={t2-t1:.4f}s | product={t3-t2:.4f}s | batchitem={t4-t3:.4f}s | completed-early")
            return JsonResponse({
                'success': False, 
                'already_completed': True,
                'error': f"Item ini sudah selesai oleh <b>{completed_user}</b> pada <b>{completed_time}</b>."
            })

        if batchitem.jumlah_ambil < batchitem.jumlah:
            prev_jumlah_ambil = batchitem.jumlah_ambil
            batchitem.jumlah_ambil += 1
            t5 = time.perf_counter()
            # --- TAMBAHAN: Update quantity_locked ---
            stock = Stock.objects.filter(product=product).first()
            t6 = time.perf_counter()
            if stock:
                delta = batchitem.jumlah_ambil - prev_jumlah_ambil
                stock.quantity -= delta
                stock.quantity_locked -= delta
                stock.save(update_fields=['quantity', 'quantity_locked'])
            # Check if completed
            if batchitem.jumlah_ambil >= batchitem.jumlah:
                batchitem.status_ambil = 'completed'
                # SIMPAN DATA USER & WAKTU SAAT SELESAI
                batchitem.completed_at = timezone.now()
                if request.user.is_authenticated:
                    batchitem.completed_by = request.user
            batchitem.save()
            t7 = time.perf_counter()
            logging.info(f"[PROFILING] update_barcode_picklist: total={time.perf_counter()-start_time:.4f}s | json={t1-t0:.4f}s | batch={t2-t1:.4f}s | product={t3-t2:.4f}s | batchitem={t4-t3:.4f}s | stock={t6-t5:.4f}s | save={t7-t6:.4f}s | normal-exit")
            jakarta_tz = pytz.timezone('Asia/Jakarta')
            now_jakarta = timezone.now().astimezone(jakarta_tz)
            server_time = now_jakarta.strftime('%H:%M:%S')
            # Setelah update jumlah_ambil:
            # WebSocket update disabled - channels not configured
            # channel_layer = get_channel_layer()
            # async_to_sync(channel_layer.group_send)(
            #     f'batchpicking_{nama_batch}',
            #     {
            #         'type': 'send_update',
            #         'data': {
            #             'sku': product.sku,
            #             'barcode': product.barcode,
            #             'jumlah_ambil': batchitem.jumlah_ambil,
            #             'status_ambil': batchitem.status_ambil,
            #         }
            #     }
            # )
            BatchItemLog.objects.create(
                waktu=timezone.now(),
                user=request.user if request.user.is_authenticated else None,
                batch=batchitem.batchlist,
                product=batchitem.product,
                jumlah_input=1,
                jumlah_ambil=batchitem.jumlah_ambil
            )
            return JsonResponse({
                'success': True,
                'main_barcode': product.barcode,
                'jumlah_ambil': batchitem.jumlah_ambil,
                'jumlah': batchitem.jumlah,
                'status_ambil': batchitem.status_ambil,
                'completed': batchitem.jumlah_ambil >= batchitem.jumlah,
                'server_time': server_time,
                'product_info': {
                    'photo_url': product.photo.url if product.photo else '/static/icons/alfaicon.png',
                    'sku': product.sku,
                    'barcode': product.barcode,
                    'nama_produk': product.nama_produk,
                    'variant_produk': product.variant_produk or '',
                    'brand': product.brand or ''
                }
            })
        else:
            logging.info(f"[PROFILING] update_barcode_picklist: total={time.perf_counter()-start_time:.4f}s | fallback-exit")
            return JsonResponse({'success': False, 'error': 'Jumlah ambil sudah cukup.'})
    except Exception as e:
        logging.exception("[PROFILING] update_barcode_picklist: exception occurred")
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
@require_POST
@login_required
def update_barcode_picklist_to_rak(request, nama_batch):
    start_time = time.perf_counter()
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)
    
    try:
        import json
        from inventory.models import Stock, InventoryRakStock, InventoryRakStockLog
        from django.contrib.contenttypes.models import ContentType
        
        t0 = time.perf_counter()
        data = json.loads(request.body)
        t1 = time.perf_counter()
        
        barcode = data.get('barcode')
        selected_rak = data.get('selected_rak')  # Kode rak yang dipilih
        
        if not barcode:
            return JsonResponse({'success': False, 'error': 'Barcode tidak ditemukan.'})
        
        if not selected_rak:
            return JsonResponse({'success': False, 'error': 'Rak belum dipilih. Silakan pilih rak terlebih dahulu.'})
        
        # Cek batch exists
        batch = BatchList.objects.filter(nama_batch=nama_batch).first()
        t2 = time.perf_counter()
        if not batch:
            return JsonResponse({'success': False, 'error': 'Batch tidak ditemukan.'})
        
        # Cek status batch
        if batch.status_batch == 'closed':
            return JsonResponse({'success': False, 'error': f"Batch '{nama_batch}' sudah ditutup. Tidak bisa melakukan update scan barcode."})
        
        # Cek barcode utama atau extra barcode
        product = Product.objects.filter(barcode=barcode).first()
        if not product:
            extra_barcode_entry = ProductExtraBarcode.objects.filter(barcode=barcode).select_related('product').first()
            if extra_barcode_entry:
                product = extra_barcode_entry.product
        
        t3 = time.perf_counter()
        if not product:
            return JsonResponse({'success': False, 'error': 'Produk dengan barcode ini tidak ditemukan.'})
        
        # Cek batchitem exists
        batchitem = BatchItem.objects.filter(batchlist=batch, product=product).first()
        t4 = time.perf_counter()
        if not batchitem:
            return JsonResponse({'success': False, 'error': 'Item tidak ditemukan di batch.'})
        
        # Cek sudah completed atau belum
        if batchitem.status_ambil == 'completed':
            if batchitem.completed_at:
                jakarta_tz = pytz.timezone('Asia/Jakarta')
                completed_at_jakarta = batchitem.completed_at.astimezone(jakarta_tz)
                completed_time = completed_at_jakarta.strftime('%d %b %Y, %H:%M:%S')
            else:
                completed_time = 'N/A'
            
            completed_user = batchitem.completed_by.username if batchitem.completed_by else 'N/A'
            return JsonResponse({
                'success': False, 
                'already_completed': True,
                'error': f"Item ini sudah selesai oleh <b>{completed_user}</b> pada <b>{completed_time}</b>."
            })
        
        # Cek stok di rak yang dipilih
        try:
            rak = Rak.objects.get(kode_rak=selected_rak)
        except Rak.DoesNotExist:
            return JsonResponse({'success': False, 'error': f'Rak {selected_rak} tidak ditemukan.'})
        
        inventory_rak_stock = InventoryRakStock.objects.filter(product=product, rak=rak).first()
        
        # Jika stok di rak yang dipilih habis, cari rak lain yang masih ada stok
        if not inventory_rak_stock or inventory_rak_stock.quantity <= 0:
            # Cari rak lain yang masih ada stok untuk produk ini
            available_raks = InventoryRakStock.objects.filter(
                product=product, 
                quantity__gt=0
            ).select_related('rak').order_by('-quantity')
            
            if available_raks.exists():
                available_rak_list = [f"{rak.rak.kode_rak} ({rak.quantity})" for rak in available_raks[:3]]  # Ambil 3 rak teratas
                available_rak_str = ", ".join(available_rak_list)
                
                return JsonResponse({
                    'success': False, 
                    'error': f"Stok produk <b>{product.sku}</b> di rak <b>{selected_rak}</b> sudah habis. Tolong ambil dari rak: <b>{available_rak_str}</b>"
                })
            else:
                return JsonResponse({
                    'success': False, 
                    'error': f"Stok produk <b>{product.sku}</b> sudah habis di semua rak."
                })
        
        # Proses update jika stok mencukupi
        if batchitem.jumlah_ambil < batchitem.jumlah:
            prev_jumlah_ambil = batchitem.jumlah_ambil
            batchitem.jumlah_ambil += 1
            t5 = time.perf_counter()
            
            # Update Stock (quantity dan quantity_locked)
            stock = Stock.objects.filter(product=product).first()
            t6 = time.perf_counter()
            if stock:
                delta = batchitem.jumlah_ambil - prev_jumlah_ambil
                stock.quantity -= delta
                stock.quantity_locked -= delta
                stock.save(update_fields=['quantity', 'quantity_locked'])
            
            # Update InventoryRakStock (stok di rak spesifik)
            qty_awal_rak = inventory_rak_stock.quantity
            inventory_rak_stock.quantity -= 1
            qty_akhir_rak = inventory_rak_stock.quantity
            inventory_rak_stock.save()
            
            # Check if completed
            if batchitem.jumlah_ambil >= batchitem.jumlah:
                batchitem.status_ambil = 'completed'
                batchitem.completed_at = timezone.now()
                if request.user.is_authenticated:
                    batchitem.completed_by = request.user
            
            batchitem.save()
            t7 = time.perf_counter()
            
            # Create InventoryRakStockLog (log pergerakan stok di rak)
            InventoryRakStockLog.objects.create(
                produk=product,
                rak=rak,
                tipe_pergerakan='picking_keluar',
                qty=-1,  # Keluar (-1)
                qty_awal=qty_awal_rak,
                qty_akhir=qty_akhir_rak,
                content_type=ContentType.objects.get_for_model(BatchItem),
                object_id=batchitem.id,
                user=request.user if request.user.is_authenticated else None,
                catatan=f"Picking dari batch {nama_batch}"
            )
            
            # Create BatchItemLog (log batch picking)
            BatchItemLog.objects.create(
                waktu=timezone.now(),
                user=request.user if request.user.is_authenticated else None,
                batch=batchitem.batchlist,
                product=batchitem.product,
                jumlah_input=1,
                jumlah_ambil=batchitem.jumlah_ambil
            )
            
            # WebSocket update disabled - channels not configured
            # channel_layer = get_channel_layer()
            # async_to_sync(channel_layer.group_send)(
            #     f'batchpicking_{nama_batch}',
            #     {
            #         'type': 'send_update',
            #         'data': {
            #             'sku': product.sku,
            #             'barcode': product.barcode,
            #             'jumlah_ambil': batchitem.jumlah_ambil,
            #             'status_ambil': batchitem.status_ambil,
            #             'rak_asal': selected_rak,
            #         }
            #     }
            # )
            
            jakarta_tz = pytz.timezone('Asia/Jakarta')
            now_jakarta = timezone.now().astimezone(jakarta_tz)
            server_time = now_jakarta.strftime('%H:%M:%S')
            
            return JsonResponse({
                'success': True,
                'main_barcode': product.barcode,
                'jumlah_ambil': batchitem.jumlah_ambil,
                'jumlah': batchitem.jumlah,
                'status_ambil': batchitem.status_ambil,
                'completed': batchitem.jumlah_ambil >= batchitem.jumlah,
                'server_time': server_time,
                'rak_asal': selected_rak,
                'product_info': {
                    'photo_url': product.photo.url if product.photo else '/static/icons/alfaicon.png',
                    'sku': product.sku,
                    'barcode': product.barcode,
                    'nama_produk': product.nama_produk,
                    'variant_produk': product.variant_produk or '',
                    'brand': product.brand or ''
                }
            })
        else:
            return JsonResponse({'success': False, 'error': 'Jumlah ambil sudah cukup.'})
            
    except Exception as e:
        logging.exception("[PROFILING] update_barcode_picklist_to_rak: exception occurred")
        return JsonResponse({'success': False, 'error': f'Terjadi kesalahan: {str(e)}'}, status=500)

@csrf_exempt
@login_required
def update_manual(request, nama_batch):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)
    try:
        from inventory.models import Stock
        data = json.loads(request.body)
        barcode = data.get('barcode')
        jumlah_ambil = data.get('jumlah_ambil')
        if not barcode or jumlah_ambil is None:
            return JsonResponse({'success': False, 'error': 'Barcode dan jumlah_ambil wajib diisi.'})
        # Find the batch and batch item
        batch = BatchList.objects.filter(nama_batch=nama_batch).first()
        if not batch:
            return JsonResponse({'success': False, 'error': 'Batch tidak ditemukan.'})

        # --- TAMBAHAN BARU: Cek status batch ---
        if batch.status_batch == 'closed':
            return JsonResponse({'success': False, 'error': f"Batch '{nama_batch}' sudah ditutup. Tidak bisa melakukan update manual."})
        # --- AKHIR TAMBAHAN BARU ---
        
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
        # --- Tambahan: update stock ---
        prev_jumlah_ambil = batchitem.jumlah_ambil
        delta = jumlah_ambil - prev_jumlah_ambil
        if delta > 0:
            stock = Stock.objects.filter(product=product).first()
            if stock:
                if stock.quantity < delta:
                    # Tambahkan ke OpnameQueue jika belum ada yang pending
                    from inventory.models import OpnameQueue
                    if not OpnameQueue.objects.filter(product=batchitem.product, status='pending').exists():
                        OpnameQueue.objects.create(
                            product=batchitem.product,
                            lokasi='',
                            prioritas=1,
                            sumber_prioritas='outbound',
                            status='pending',
                            catatan='Stock tidak cukup saat picking batch (manual update)',
                        )
                    return JsonResponse({'success': False, 'error': f'Stok tidak cukup. Sisa stok di inventory: {stock.quantity}. Opname telah di-request.'})
                stock.quantity -= delta
                stock.save(update_fields=['quantity'])
        elif delta < 0:
            stock = Stock.objects.filter(product=product).first()
            if stock:
                stock.quantity -= delta
                stock.save(update_fields=['quantity'])
        
        # --- TAMBAHAN: Update quantity_locked ---
        if delta != 0:
            stock = Stock.objects.filter(product=product).first()
            if stock:
                # Jika delta positif (ambil lebih banyak), kurangi quantity_locked
                # Jika delta negatif (ambil lebih sedikit), tambah quantity_locked
                stock.quantity_locked = max(0, stock.quantity_locked - delta)
                stock.save(update_fields=['quantity_locked'])
        
        batchitem.jumlah_ambil = jumlah_ambil
        
        # Check if completed
        if batchitem.jumlah_ambil >= batchitem.jumlah:
            batchitem.status_ambil = 'completed'
            # SIMPAN DATA USER & WAKTU SAAT SELESAI
            batchitem.completed_at = timezone.now()
            if request.user.is_authenticated:
                batchitem.completed_by = request.user
        
        batchitem.save()
        
        BatchItemLog.objects.create(
            waktu=timezone.now(),
            user=request.user if request.user.is_authenticated else None,
            batch=batchitem.batchlist,
            product=batchitem.product,
            jumlah_input=jumlah_ambil,
            jumlah_ambil=batchitem.jumlah_ambil
        )
        
        return JsonResponse({
            'success': True, 
            'jumlah_ambil': batchitem.jumlah_ambil, 
            'status_ambil': batchitem.status_ambil,
            'completed': batchitem.jumlah_ambil >= batchitem.jumlah,
            'product_info': {
                'photo_url': product.photo.url if product.photo else '/static/icons/alfaicon.png',
                'sku': product.sku,
                'barcode': product.barcode,
                'nama_produk': product.nama_produk,
                'variant_produk': product.variant_produk or '',
                'brand': product.brand or ''
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# Ready to Print Table View
@login_required
@permission_required('fullfilment.view_readytoprint', raise_exception=True)
def ready_to_print_list(request):
    nama_batch = request.GET.get('nama_batch')
    search_query = request.GET.get('q', '') # Ambil query pencarian
    batchlist = None
    queryset = ReadyToPrint.objects.none()

    # Summary context initialization
    summary_context = {
        'total_order': 0,
        'ready_to_pick': 0,
        'sat_summary': 0,
        'prio_summary': 0,
        'brand_summary': 0,
        'mix_summary': 0,
        'printed_summary': 0,
        'nama_batch': nama_batch,
        'order_batal_count': 0,
        'cancelled_printed_count': 0,
        'cancelled_not_printed_count': 0,
        'already_returned_count': 0,
        'unallocated_stock_count': 0,
    }

    if nama_batch:
        batchlist = get_object_or_404(BatchList, nama_batch=nama_batch)
        
        # --- Panggil Logika Perhitungan dari file terpisah ---
        calculate_and_sync_ready_to_print(batchlist)
        # --- Logika Perhitungan Selesai ---

        # Queryset dasar untuk batch ini
        queryset = ReadyToPrint.objects.filter(batchlist=batchlist)

        # Terapkan filter pencarian jika ada
        if search_query:
            queryset = queryset.filter(id_pesanan__icontains=search_query)
        
        # Apply custom sorting: 'pending' (bernilai 1) akan selalu di atas 'printed' (bernilai 2)
        queryset = queryset.annotate(
            custom_order=Case(
                When(status_print='pending', then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            )
        ).order_by('custom_order', '-printed_at')

        # Tambahkan data order_type dan status_order dari tabel Order
        from django.db.models import Subquery, OuterRef
        queryset = queryset.annotate(
            order_type=Subquery(
                Order.objects.filter(
                    id_pesanan=OuterRef('id_pesanan')
                ).values('order_type')[:1]
            ),
            status_order=Subquery(
                Order.objects.filter(
                    id_pesanan=OuterRef('id_pesanan')
                ).values('status_order')[:1]
            ),
            status=Subquery(
                Order.objects.filter(
                    id_pesanan=OuterRef('id_pesanan')
                ).values('status')[:1]
            )
        )

        # Re-calculate summary data here
        orders = Order.objects.filter(nama_batch=nama_batch).exclude(status_bundle='Y')
        total_order = orders.values('id_pesanan').distinct().count()

        # Get ready_to_pick_ids from ReadyToPrint table for this batch
        ready_to_pick_ids = list(ReadyToPrint.objects.filter(batchlist=batchlist).values_list('id_pesanan', flat=True))
        
        # Calculate summary for unprinted orders - PERBAIKAN LOGIKA
        unprinted_ready_to_pick_ids = list(ReadyToPrint.objects.filter(
            batchlist=batchlist, 
            status_print='pending'  # Hanya yang pending
        ).values_list('id_pesanan', flat=True))
        
        # Hitung SAT summary: order SAT yang belum di-print
        sat_summary = Order.objects.filter(
            nama_batch=nama_batch,
            id_pesanan__in=unprinted_ready_to_pick_ids,
            order_type='1'
        ).values('id_pesanan').distinct().count()
        
        # Hitung PRIO summary: order PRIO yang belum di-print  
        prio_summary = Order.objects.filter(
            nama_batch=nama_batch,
            id_pesanan__in=unprinted_ready_to_pick_ids,
            order_type__in=['2', '3', '4']  # Semua order type selain '1'
        ).values('id_pesanan').distinct().count()
        
        # Hitung SAT SKU summary: SKU unik dari order SAT yang belum di-print
        sat_sku_summary = Order.objects.filter(
            nama_batch=nama_batch,
            id_pesanan__in=unprinted_ready_to_pick_ids,
            order_type='1'
        ).values('sku').distinct().count()
        
        # Hitung Brand summary: order dengan order_type '1' atau '4' yang belum di-print
        brand_summary = Order.objects.filter(
            nama_batch=nama_batch,
            id_pesanan__in=unprinted_ready_to_pick_ids,
            order_type__in=['1', '4']
        ).values('id_pesanan').distinct().count()
        
        mix_summary = len(unprinted_ready_to_pick_ids)
        printed_summary = ReadyToPrint.objects.filter(batchlist=batchlist, printed_at__isnull=False).count()

        # ========================================
        # LOGIKA PEMBEDAAN ORDER BATAL
        # ========================================
        
        # 1. AMBIL SEMUA ORDER BATAL/CANCEL DI BATCH INI
        order_batal_count = orders.filter(
            Q(status__icontains='batal') | Q(status__icontains='cancel')
        ).values('id_pesanan').distinct().count()
        
        # 2. CARI ORDER BATAL YANG SUDAH PRINTED
        # Cara: Order dengan status bayar 'batal'/'cancel' DAN status fulfillment 'printed'
        cancelled_printed_count = orders.filter(
            Q(status__icontains='batal') | Q(status__icontains='cancel')
        ).filter(
            status_order='printed'  # Status fulfillment = printed
        ).values('id_pesanan').distinct().count()
        
        # 3. CARI ORDER BATAL YANG BELUM PRINTED  
        # Cara: Order dengan status bayar 'batal'/'cancel' DAN status fulfillment 'pending' atau kosong
        cancelled_not_printed_count = orders.filter(
            Q(status__icontains='batal') | Q(status__icontains='cancel')
        ).filter(
            Q(status_order='pending') | Q(status_order__isnull=True) | Q(status_order='')
        ).values('id_pesanan').distinct().count()
        
        # 4. HITUNG ORDER BATAL YANG SUDAH DI-RETUR
        # Cara: Dari order batal yang sudah printed, cek mana yang status_retur='Y'
        already_returned_count = orders.filter(
            Q(status__icontains='batal') | Q(status__icontains='cancel')
        ).filter(
            status_order='printed'  # Status fulfillment = printed
        ).filter(
            status_retur='Y'  # Status retur = Y (sudah di-retur)
        ).values('id_pesanan').distinct().count()
        
        # 5. HITUNG STOK GANTUNG (UNALLOCATED STOCK)
        # Stok Gantung = Total Di-Pick - Total Dibutuhkan (oleh order Ready to Print)
        picked_quantities = BatchItem.objects.filter(batchlist=batchlist).values('product_id').annotate(total_picked=Sum('jumlah_ambil'))
        picked_quantities_map = {item['product_id']: item['total_picked'] for item in picked_quantities}

        needed_quantities = Order.objects.filter(nama_batch=nama_batch, id_pesanan__in=ready_to_pick_ids).values('product_id').annotate(total_needed=Sum('jumlah'))
        needed_quantities_map = {item['product_id']: item['total_needed'] for item in needed_quantities}
        
        unallocated_stock_count = 0
        product_ids_in_batch = set(picked_quantities_map.keys()).union(set(needed_quantities_map.keys()))
        for product_id in product_ids_in_batch:
            picked_qty = picked_quantities_map.get(product_id, 0)
            needed_qty = needed_quantities_map.get(product_id, 0)
            unallocated_qty = picked_qty - needed_qty
            if unallocated_qty > 0:
                unallocated_stock_count += unallocated_qty
        
        # ========================================
        # DEBUG INFO (bisa dihapus setelah testing)
        # print(f"DEBUG - Batch: {nama_batch}")
        # print(f"DEBUG - Total order batal: {order_batal_count}")
        # print(f"DEBUG - Batal yang sudah printed: {cancelled_printed_count}")
        # print(f"DEBUG - Batal yang belum printed: {cancelled_not_printed_count}")
        # print(f"DEBUG - Batal printed yang sudah di-retur: {already_returned_count}")
        
        summary_context['order_batal_count'] = order_batal_count
        summary_context['cancelled_printed_count'] = cancelled_printed_count
        summary_context['cancelled_not_printed_count'] = cancelled_not_printed_count
        summary_context['already_returned_count'] = already_returned_count
        summary_context['unallocated_stock_count'] = unallocated_stock_count

        summary_context.update({
            'total_order': total_order,
            'ready_to_pick': len(ready_to_pick_ids),
            'sat_summary': sat_summary,
            'prio_summary': prio_summary,
            'sat_sku_summary': sat_sku_summary,
            'brand_summary': brand_summary,
            'mix_summary': mix_summary,
            'printed_summary': printed_summary,
            'ready_to_pick_ids': ready_to_pick_ids,
        })

    table = ReadyToPrintTable(queryset)
    RequestConfig(request, paginate={'per_page': 25}).configure(table) # Paginasi diatur ke 25

    # Buat dictionary untuk lookup order_type yang lebih efisien
    order_types = {}
    if nama_batch:
        orders = Order.objects.filter(nama_batch=nama_batch).exclude(status_bundle='Y')
        for order in orders:
            order_types[order.id_pesanan] = order.order_type

    context = {
        'table': table,
        'nama_batch': nama_batch,
        'orders': Order.objects.filter(nama_batch=nama_batch).exclude(status_bundle='Y') if nama_batch else Order.objects.none(),
        'search_query': search_query, # Kirim query ke template
    }
    context.update(summary_context)
    
    not_ready_to_pick_ids = get_not_ready_to_pick_ids(batchlist)
    context['not_ready_to_pick_ids'] = not_ready_to_pick_ids
    
    return render(request, 'fullfilment/readytoprint.html', context)

@csrf_exempt
@login_required
@permission_required('fullfilment.change_readytoprint', raise_exception=True)
def ready_to_print_print(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            ids = data.get('ids')
            if not ids:
                return JsonResponse({'success': False, 'error': 'No IDs provided'}, status=400)
            
            rtp_objects = ReadyToPrint.objects.filter(id__in=ids)

            # --- TAMBAHAN PROTEKSI ---
            # Cek status dari Order asli sebelum print
            order_ids_to_check = rtp_objects.values_list('id_pesanan', flat=True)
            canceled_orders = Order.objects.filter(
                id_pesanan__in=order_ids_to_check
            ).filter(
                Q(status__icontains='batal') | Q(status__icontains='cancel')
            ).values_list('id_pesanan', flat=True).distinct()

            if canceled_orders:
                return JsonResponse({
                    'success': False, 
                    'error': f"ERROR - Order berikut berstatus batal/cancel dan tidak bisa di-print: {', '.join(set(canceled_orders))}"
                }, status=400)
            # --- AKHIR PROTEKSI ---
            
            # Update status
            count = rtp_objects.count()
            rtp_objects.update(status_print='printed', printed_at=timezone.now(), printed_via='SELECTED')

            return JsonResponse({'success': True, 'message': f'{count} order(s) have been marked as printed.'})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
            
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

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

def update_ready_to_print():
    # This function might need to be re-evaluated or removed
    # as its logic was based on the deleted fields.
    # For now, let's comment it out to prevent errors.
    # orders = Order.objects.filter(order_type='1')
    # for order in orders:
    #     ReadyToPrint.objects.update_or_create(
    #         id_pesanan=order.id_pesanan,
    #         defaults={
    #             # 'brand': order.brand,  <- This was causing an error
    #             # 'order_type': order.order_type, <- This was causing an error
    #         }
    #     )
    pass # Function is now empty

def update_ready_to_print_sat():
    # This function might also need review
    pass

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

@login_required
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

@login_required
def print_sat_brand(request):
    brand = request.GET.get('brand')
    nama_batch = request.GET.get('nama_batch')
    if not brand or not nama_batch:
        return JsonResponse({'success': False, 'error': 'Batch dan brand harus diisi'})

    from orders.models import Order
    from .models import ReadyToPrint, BatchItem

    # 1. Ambil semua ID pesanan yang siap print di batch ini
    unprinted_ids = ReadyToPrint.objects.filter(
        batchlist__nama_batch=nama_batch,
        printed_at__isnull=True
    ).values_list('id_pesanan', flat=True)

    if not unprinted_ids:
        return JsonResponse({'success': False, 'error': 'Tidak ada order yang siap untuk ditandai.'})

    # 2. Filter ID tersebut untuk menemukan order SAT yang cocok dengan brand
    idpesanan_to_update = Order.objects.filter(
        id_pesanan__in=list(unprinted_ids),
        order_type='1',
        product__brand=brand
    ).values_list('id_pesanan', flat=True).distinct()

    if not idpesanan_to_update:
        return JsonResponse({'success': False, 'error': f'Tidak ada order SAT untuk brand {brand} yang siap print.'})

    # 3. Update status di ReadyToPrint
    now_jakarta = timezone.now().astimezone(pytz.timezone('Asia/Jakarta'))
    updated_count = ReadyToPrint.objects.filter(
        batchlist__nama_batch=nama_batch,
        id_pesanan__in=list(idpesanan_to_update)
    ).update(
        status_print='printed',
        printed_at=now_jakarta,
        printed_via='SAT BRAND',
        printed_by=request.user
    )

    if updated_count > 0:
        # 4. Update juga status_order di tabel Order
        Order.objects.filter(id_pesanan__in=list(idpesanan_to_update)).update(status_order='printed')
        
        # 5. UPDATE JUMLAH_TERPAKAI berdasarkan product dari order yang di-print
        batch = BatchList.objects.get(nama_batch=nama_batch)
        
        # Ambil semua order yang baru di-print
        printed_orders = Order.objects.filter(
            id_pesanan__in=list(idpesanan_to_update),
            order_type='1',
            product__brand=brand
        )
        
        # Hitung jumlah terpakai per product
        from collections import defaultdict
        product_usage = defaultdict(int)
        
        for order in printed_orders:
            if order.product_id:
                product_usage[order.product_id] += order.jumlah  # <- PERBAIKAN
        
        # Update jumlah_terpakai di BatchItem
        for product_id, usage_count in product_usage.items():
            try:
                batch_item = BatchItem.objects.get(
                    batchlist=batch,
                    product_id=product_id
                )
                batch_item.jumlah_terpakai += usage_count
                batch_item.save()
            except BatchItem.DoesNotExist:
                # Jika BatchItem tidak ditemukan, skip
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'{updated_count} order untuk brand {brand} telah ditandai sebagai printed dan jumlah_terpakai telah diupdate.'
        })
    else:
        return JsonResponse({'success': False, 'error': f'Tidak ada order yang berhasil diupdate untuk brand {brand}.'})

@login_required
def print_all_sat_brands(request):
    nama_batch = request.GET.get('nama_batch')
    if not nama_batch:
        return JsonResponse({'success': False, 'error': 'Batch harus diisi'})

    from orders.models import Order
    from .models import ReadyToPrint, BatchItem, BatchList

    # Temukan semua id_pesanan di ReadyToPrint batch ini yang belum pernah di-print
    rtp_qs = ReadyToPrint.objects.filter(batchlist__nama_batch=nama_batch, printed_at__isnull=True)
    idpesanan_set = set()
    rtp_ids_to_update = []

    for rtp in rtp_qs:
        orders = Order.objects.filter(id_pesanan=rtp.id_pesanan)
        if orders.exists() and orders.first().order_type == '1':
            idpesanan_set.add(rtp.id_pesanan)
            rtp_ids_to_update.append(rtp.id)

    if not rtp_ids_to_update:
        return JsonResponse({'success': False, 'error': 'Tidak ada order SAT yang siap print untuk semua brand.'})

    # Update status_print dan printed_at di ReadyToPrint
    from django.utils import timezone
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    now_jakarta = timezone.now().astimezone(jakarta_tz)
    updated_count = ReadyToPrint.objects.filter(
        id__in=rtp_ids_to_update
    ).update(status_print='printed', printed_at=now_jakarta, printed_via='SAT ALL', printed_by=request.user)

    # Update status_order di tabel Order
    if rtp_ids_to_update:
        Order.objects.filter(id_pesanan__in=idpesanan_set).update(status_order='printed')
        
        # UPDATE JUMLAH_TERPAKAI berdasarkan product dari order yang di-print
        batchlist = BatchList.objects.get(nama_batch=nama_batch)
        
        # Ambil semua order SAT yang baru di-print
        printed_orders = Order.objects.filter(
            id_pesanan__in=idpesanan_set,
            order_type='1'
        )
        
        # Hitung jumlah terpakai per product
        from collections import defaultdict
        product_usage = defaultdict(int)
        
        for order in printed_orders:
            if order.product_id:
                product_usage[order.product_id] += order.jumlah  # <- PERBAIKAN
        
        # Update jumlah_terpakai di BatchItem
        for product_id, usage_count in product_usage.items():
            try:
                batch_item = BatchItem.objects.get(
                    batchlist=batchlist,
                    product_id=product_id
                )
                batch_item.jumlah_terpakai += usage_count
                batch_item.save()
            except BatchItem.DoesNotExist:
                # Jika BatchItem tidak ditemukan, skip
                continue

    return JsonResponse({
        'success': True,
        'message': f'{updated_count} order dari semua brand telah ditandai sebagai printed dan jumlah_terpakai telah diupdate.'
    })

@login_required
def get_brand_data(request):
    nama_batch = request.GET.get('nama_batch')
    if not nama_batch:
        return JsonResponse({'success': False, 'error': 'Batch harus diisi'})

    from products.models import Product
    from orders.models import Order
    from .models import ReadyToPrint

    # Ambil semua brand dengan order_type 1 dan 4
    rtp_qs = ReadyToPrint.objects.filter(batchlist__nama_batch=nama_batch, printed_at__isnull=True)
    brand_to_idpesanan = {}

    for rtp in rtp_qs:
        orders = Order.objects.filter(id_pesanan=rtp.id_pesanan)
        order_type = None
        if orders.exists():
            order_type = orders.first().order_type
        if order_type in ['1', '4']:
            product_ids = orders.values_list('product_id', flat=True)
            brands_in_order = set()
            for pid in product_ids:
                if pid:
                    product = Product.objects.filter(id=pid).first()
                    if product:
                        brands_in_order.add(product.brand)
            for brand in brands_in_order:
                if brand not in brand_to_idpesanan:
                    brand_to_idpesanan[brand] = set()
                brand_to_idpesanan[brand].add(rtp.id_pesanan)

    # Hitung jumlah id_pesanan unik per brand
    brand_data = {brand: len(idpesanan_set) for brand, idpesanan_set in brand_to_idpesanan.items()}
    # Sort brands by total unique orders descending
    sorted_brands = sorted(brand_data.items(), key=lambda x: x[1], reverse=True)
    brands = [{'brand': b[0], 'totalOrders': b[1]} for b in sorted_brands]

    return JsonResponse({'success': True, 'brands': brands})
 

@login_required
def print_all_brands(request):
    nama_batch = request.GET.get('nama_batch')
    if not nama_batch:
        return JsonResponse({'success': False, 'error': 'Batch harus diisi'})

    from orders.models import Order
    from .models import ReadyToPrint, BatchItem, BatchList

    # Temukan semua id_pesanan di ReadyToPrint batch ini yang belum pernah di-print
    rtp_qs = ReadyToPrint.objects.filter(batchlist__nama_batch=nama_batch, printed_at__isnull=True)
    idpesanan_set = set()
    rtp_ids_to_update = []

    for rtp in rtp_qs:
        orders = Order.objects.filter(id_pesanan=rtp.id_pesanan)
        if orders.exists() and orders.first().order_type in ['1', '4']:
            idpesanan_set.add(rtp.id_pesanan)
            rtp_ids_to_update.append(rtp.id)

    if not rtp_ids_to_update:
        return JsonResponse({'success': False, 'error': 'Tidak ada order yang siap print untuk semua brand.'})

    # Update status_print dan printed_at di ReadyToPrint
    from django.utils import timezone
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    now_jakarta = timezone.now().astimezone(jakarta_tz)
    updated_count = ReadyToPrint.objects.filter(
        id__in=rtp_ids_to_update
    ).update(status_print='printed', printed_at=now_jakarta, printed_via='BRAND', printed_by=request.user)

    # Update status_order di tabel Order
    if rtp_ids_to_update:
        Order.objects.filter(id_pesanan__in=idpesanan_set).update(status_order='printed')
        
        # UPDATE JUMLAH_TERPAKAI berdasarkan product dari order yang di-print
        batchlist = BatchList.objects.get(nama_batch=nama_batch)
        
        # Ambil semua order yang baru di-print
        printed_orders = Order.objects.filter(
            id_pesanan__in=idpesanan_set,
            order_type__in=['1', '4']
        )
        
        # Hitung jumlah terpakai per product
        from collections import defaultdict
        product_usage = defaultdict(int)
        
        for order in printed_orders:
            if order.product_id:
                product_usage[order.product_id] += order.jumlah  # <- PERBAIKAN
        
        # Update jumlah_terpakai di BatchItem
        for product_id, usage_count in product_usage.items():
            try:
                batch_item = BatchItem.objects.get(
                    batchlist=batchlist,
                    product_id=product_id
                )
                batch_item.jumlah_terpakai += usage_count
                batch_item.save()
            except BatchItem.DoesNotExist:
                # Jika BatchItem tidak ditemukan, skip
                continue

    return JsonResponse({
        'success': True,
        'message': f'{updated_count} order dari semua brand telah ditandai sebagai printed dan jumlah_terpakai telah diupdate.'
    })

@login_required
def print_brands(request):
    brand = request.GET.get('brand')
    nama_batch = request.GET.get('nama_batch')
    if not brand or not nama_batch:
        return JsonResponse({'success': False, 'error': 'Batch dan brand harus diisi'})

    from orders.models import Order
    from products.models import Product
    from .models import ReadyToPrint, BatchItem, BatchList

    # 1. Ambil semua ID pesanan yang siap print di batch ini
    unprinted_ids = ReadyToPrint.objects.filter(
        batchlist__nama_batch=nama_batch,
        printed_at__isnull=True
    ).values_list('id_pesanan', flat=True)

    if not unprinted_ids:
        return JsonResponse({'success': False, 'error': 'Tidak ada order yang siap untuk ditandai.'})

    # 2. Filter ID tersebut untuk menemukan order yang cocok dengan brand
    idpesanan_to_update = Order.objects.filter(
        id_pesanan__in=list(unprinted_ids),
        product__brand=brand
    ).values_list('id_pesanan', flat=True).distinct()

    if not idpesanan_to_update:
        return JsonResponse({'success': False, 'error': f'Tidak ada order untuk brand {brand} yang siap print.'})

    # 3. Update status di ReadyToPrint
    now_jakarta = timezone.now().astimezone(pytz.timezone('Asia/Jakarta'))
    updated_count = ReadyToPrint.objects.filter(
        batchlist__nama_batch=nama_batch,
        id_pesanan__in=list(idpesanan_to_update)
    ).update(
        status_print='printed',
        printed_at=now_jakarta,
        printed_via='BRAND',
        printed_by=request.user
    )

    if updated_count > 0:
        # 4. Update juga status_order di tabel Order
        Order.objects.filter(id_pesanan__in=list(idpesanan_to_update)).update(status_order='printed')
        
        # 5. UPDATE JUMLAH_TERPAKAI berdasarkan product dari order yang di-print
        batch = BatchList.objects.get(nama_batch=nama_batch)
        
        # Ambil semua order yang baru di-print dengan brand tertentu
        printed_orders = Order.objects.filter(
            id_pesanan__in=list(idpesanan_to_update),
            product__brand=brand
        )
        
        # Hitung jumlah terpakai per product berdasarkan jumlah item yang dibutuhkan
        from collections import defaultdict
        product_usage = defaultdict(int)
        
        for order in printed_orders:
            if order.product_id:
                product_usage[order.product_id] += order.jumlah  # <- PERBAIKAN
        
        # Update jumlah_terpakai di BatchItem
        for product_id, usage_count in product_usage.items():
            try:
                batch_item = BatchItem.objects.get(
                    batchlist=batch,
                    product_id=product_id
                )
                batch_item.jumlah_terpakai += usage_count
                batch_item.save()
            except BatchItem.DoesNotExist:
                # Jika BatchItem tidak ditemukan, skip
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'{updated_count} order untuk brand {brand} telah ditandai sebagai printed dan jumlah_terpakai telah diupdate.'
        })
    else:
        return JsonResponse({'success': False, 'error': f'Tidak ada order yang berhasil diupdate untuk brand {brand}.'})


@require_POST
@csrf_exempt
@login_required
@permission_required('fullfilment.delete_batchlist', raise_exception=True)
def batchlist_delete(request, batch_id):
    """
    Tahap 2: Menghapus BatchList secara permanen.
    Hanya bisa dilakukan jika tidak ada lagi order yang terhubung.
    """
    batch = get_object_or_404(BatchList, id=batch_id)
    
    try:
        with transaction.atomic():
            if Order.objects.filter(nama_batch=batch.nama_batch).exists():
                messages.error(request, f"Batch '{batch.nama_batch}' tidak bisa dihapus karena masih ada order yang terhubung. Bersihkan batch terlebih dahulu.")
                return redirect('/fullfilment/')

            if BatchItem.objects.filter(batchlist=batch, jumlah_ambil__gt=0).exists():
                messages.error(request, f"Batch '{batch.nama_batch}' tidak bisa dihapus karena masih ada item yang sudah diambil. Harap kembalikan stok terlebih dahulu.")
                return redirect('/fullfilment/')

            BatchItem.objects.filter(batchlist=batch).delete()
            batch_name = batch.nama_batch
            batch.delete()
            
            messages.success(request, f"Batch '{batch_name}' berhasil dihapus secara permanen.")

    except Exception as e:
        messages.error(request, f"Terjadi kesalahan saat menghapus batch: {e}")

    return redirect('/fullfilment/')

@login_required
def batchpicking_sku_not_found_details(request, nama_batch):
    sku_not_found_list, _ = get_sku_not_found(nama_batch)
    return JsonResponse({'sku_not_found_list': sku_not_found_list})

@csrf_exempt
@login_required
def mix_count_api(request, nama_batch):
    """Return total order mix (id_pesanan unik) dengan printed_at IS NULL untuk batch tertentu."""
    if not nama_batch:
        return JsonResponse({'success': False, 'error': 'Missing batch name'})
    batchlist = BatchList.objects.filter(nama_batch=nama_batch).first()
    if not batchlist:
        return JsonResponse({'success': False, 'error': 'Batch not found'})
    # Ambil id_pesanan unik yang printed_at IS NULL di ReadyToPrint
    mix_count = ReadyToPrint.objects.filter(batchlist=batchlist, printed_at__isnull=True).values('id_pesanan').distinct().count()
    return JsonResponse({'success': True, 'mix_count': mix_count})

@login_required
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
@login_required
def batchitem_update_jumlah_ambil(request, nama_batch, pk):
    if request.method == 'POST':
        try:
            from inventory.models import Stock
            data = json.loads(request.body)
            jumlah_ambil = int(data.get('jumlah_ambil', 0))
            batchitem = get_object_or_404(BatchItem, pk=pk)
            if jumlah_ambil > batchitem.jumlah:
                return JsonResponse({'success': False, 'error': 'Jumlah ambil tidak boleh lebih dari jumlah'})
            # Hitung selisih ambil
            delta = jumlah_ambil - batchitem.jumlah_ambil
            if delta > 0:
                # Outbound stock
                stock = Stock.objects.filter(product=batchitem.product).first()
                if stock:
                    if stock.quantity < delta:
                        from inventory.models import OpnameQueue
                        if not OpnameQueue.objects.filter(product=batchitem.product, status='pending').exists():
                            OpnameQueue.objects.create(
                                product=batchitem.product,
                                lokasi='',
                                prioritas=1,
                                sumber_prioritas='outbound',
                                status='pending',
                                catatan='Stok tidak cukup saat picking batch (manual update)',
                            )
                        # Hitung stok yang tersisa setelah pengambilan
                        remaining_stock = stock.quantity - delta
                        return JsonResponse({
                            'success': False, 
                            'error': f'Stok tidak cukup. Sisa stok: {stock.quantity}, Butuh: {delta}, STOCK: {remaining_stock}. Opname telah di-request.'
                        })
                    stock.quantity -= delta
                    stock.save(update_fields=['quantity'])
            elif delta < 0:
                # Jika jumlah_ambil dikurangi (rollback), kembalikan stock
                stock = Stock.objects.filter(product=batchitem.product).first()
                if stock:
                    stock.quantity -= delta  # delta negatif, jadi tambah
                    stock.save(update_fields=['quantity'])
            batchitem.jumlah_ambil = jumlah_ambil
            # Auto update status_ambil jika sudah penuh
            if batchitem.jumlah_ambil >= batchitem.jumlah:
                batchitem.status_ambil = 'completed'
            else:
                batchitem.status_ambil = 'pending'
            batchitem.save()
            # --- TAMBAHAN: Update quantity_locked ---
            if delta != 0:
                stock = Stock.objects.filter(product=batchitem.product).first()
                if stock:
                    # Jika delta positif (ambil lebih banyak), kurangi quantity_locked
                    # Jika delta negatif (ambil lebih sedikit), tambah quantity_locked
                    stock.quantity_locked = max(0, stock.quantity_locked - delta)
                    stock.save(update_fields=['quantity_locked'])
            # Setelah update jumlah_ambil:
            # WebSocket update disabled - channels not configured
            # channel_layer = get_channel_layer()
            # async_to_sync(channel_layer.group_send)(
            #     f'batchpicking_{nama_batch}',
            #     {
            #         'type': 'send_update',
            #         'data': {
            #             'sku': batchitem.product.sku,
            #             'barcode': batchitem.product.barcode,
            #             'jumlah_ambil': batchitem.jumlah_ambil,
            #             'status_ambil': batchitem.status_ambil,
            #         }
            #     }
            # )
            BatchItemLog.objects.create(
                waktu=timezone.now(),
                user=request.user if request.user.is_authenticated else None,
                batch=batchitem.batchlist,
                product=batchitem.product,
                jumlah_input=delta,
                jumlah_ambil=batchitem.jumlah_ambil
            )
            return JsonResponse({'success': True, 'completed': batchitem.status_ambil == 'completed'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid method'})

from django.http import JsonResponse
from orders.models import Order

@login_required
def ajax_filter_options(request):
    filters = {
        'nama_toko': request.GET.getlist('nama_toko[]'),
        'brand': request.GET.getlist('brand[]'),
        'order_type': request.GET.getlist('order_type[]'),
        'kirim_sebelum': request.GET.getlist('kirim_sebelum[]'),
        'kurir': request.GET.getlist('kurir[]'),
        'id_pesanan': request.GET.getlist('id_pesanan[]'),
    }
    queryset = Order.objects.filter(status__iexact='Lunas')
    if filters['nama_toko']:
        queryset = queryset.filter(nama_toko__in=filters['nama_toko'])
    if filters['brand']:
        queryset = queryset.filter(product__brand__in=filters['brand'])
    if filters['order_type']:
        queryset = queryset.filter(order_type__in=filters['order_type'])
    if filters['kirim_sebelum']:
        queryset = queryset.filter(kirim_sebelum__in=filters['kirim_sebelum'])
    if filters['kurir']:
        queryset = queryset.filter(kurir__in=filters['kurir'])
    if filters['id_pesanan']:
        queryset = queryset.filter(id_pesanan__in=filters['id_pesanan'])
    options = {
        'nama_toko': sorted(set(queryset.exclude(nama_toko__isnull=True).exclude(nama_toko='').values_list('nama_toko', flat=True))),
        'brand': sorted(set(queryset.exclude(product__brand__isnull=True).exclude(product__brand='').values_list('product__brand', flat=True))),
        'order_type': sorted(set(queryset.exclude(order_type__isnull=True).exclude(order_type='').values_list('order_type', flat=True))),
        'kirim_sebelum': sorted(set(queryset.exclude(kirim_sebelum__isnull=True).exclude(kirim_sebelum='').values_list('kirim_sebelum', flat=True))),
        'kurir': sorted(set(queryset.exclude(kurir__isnull=True).exclude(kurir='').values_list('kurir', flat=True))),
        'id_pesanan': sorted(set(queryset.exclude(id_pesanan__isnull=True).exclude(id_pesanan='').values_list('id_pesanan', flat=True))),
    }
    return JsonResponse(options)

@login_required
def batchorder_view(request, nama_batch):
    """
    Menampilkan halaman daftar order dalam batch, dengan data untuk filter dropdown.
    """
    # Ambil data unik untuk filter dropdown, pastikan tidak ada nilai kosong
    base_queryset = Order.objects.filter(nama_batch=nama_batch)
    unique_tanggals = sorted([d for d in base_queryset.values_list('tanggal_pembuatan', flat=True).distinct() if d])
    unique_kirims = sorted([d for d in base_queryset.values_list('kirim_sebelum', flat=True).distinct() if d])
    
    # Ambil status batch untuk validasi
    try:
        batch = BatchList.objects.get(nama_batch=nama_batch)
        batch_status = batch.status_batch
    except BatchList.DoesNotExist:
        batch_status = 'unknown'

    context = {
        'nama_batch': nama_batch,
        'unique_tanggals': unique_tanggals,
        'unique_kirims': unique_kirims,
        'batch_status': batch_status,
    }
    return render(request, 'fullfilment/batchorder.html', context)

@csrf_exempt # Untuk menerima POST request dari DataTables (jika method POST)
@login_required
def batchorder_api(request, nama_batch):
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    
    queryset = Order.objects.filter(nama_batch=nama_batch).select_related('product')
    total_records = queryset.count()

    # --- INI BAGIAN PENTING UNTUK FILTER ---
    column_map_filter = {
        '0': 'id_pesanan__icontains',
        '1': 'tanggal_pembuatan',
        '2': 'kirim_sebelum',
        '3': 'sku__icontains',
        '4': 'product__barcode__icontains',
        '5': 'product__nama_produk__icontains',
        '6': 'product__variant_produk__icontains',
        '7': 'product__brand__icontains',
        '8': 'jumlah',
        '9': 'order_type__icontains',
        '10': 'status__icontains',
        '11': 'status_order__icontains',
    }
    for col_index, field_name in column_map_filter.items():
        search_value = request.GET.get(f'columns[{col_index}][search][value]', '').strip()
        if search_value:
            queryset = queryset.filter(**{field_name: search_value})

    # --- INI BAGIAN PENTING UNTUK SORTING ---
    order_column_index = int(request.GET.get('order[0][column]', 0))
    order_dir = request.GET.get('order[0][dir]', 'asc')
    column_map_sort = [
        'id_pesanan', 'tanggal_pembuatan', 'kirim_sebelum', 'sku', 'product__barcode',
        'product__nama_produk', 'product__variant_produk', 'product__brand', 'jumlah',
        'order_type', 'status', 'status_order', None
    ]
    order_field = column_map_sort[order_column_index]
    if order_field:
        sort_prefix = '-' if order_dir == 'desc' else ''
        queryset = queryset.order_by(f'{sort_prefix}{order_field}')

    filtered_records = queryset.count()

    # Terapkan paginasi
    queryset = queryset[start:start + length]

    data = []
    for order_item in queryset:
        product = order_item.product
        data.append([
            order_item.id_pesanan,
            order_item.tanggal_pembuatan,
            order_item.kirim_sebelum,
            order_item.sku,
            product.barcode if product else '',
            product.nama_produk if product else '',
            product.variant_produk if product else '',
            product.brand if product else '',
            order_item.jumlah,
            order_item.order_type,
            order_item.status if order_item.status else '',
            order_item.status_order,
            order_item.pk
        ])

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': filtered_records,
        'data': data,
    })

@login_required
def edit_order_batch_view(request, nama_batch, id_pesanan):
    """
    Menampilkan form untuk mengedit order spesifik di dalam batch.
    """
    batch_list = get_object_or_404(BatchList, nama_batch=nama_batch)
    
    # Validasi status batch: tidak boleh closed
    if batch_list.status_batch == 'closed':
        messages.error(request, f"Batch '{nama_batch}' sudah berstatus closed dan tidak dapat diedit.")
        return redirect('batchorder_view', nama_batch=nama_batch)
    
    # Ambil semua item Order yang terkait dengan id_pesanan ini di batch yang sama
    # Pastikan order item tersebut masih terhubung dengan batch ini
    order_items_in_batch = Order.objects.filter(
        id_pesanan=id_pesanan,
        nama_batch=nama_batch
    ).select_related('product', 'product__stock')

    if not order_items_in_batch.exists():
        messages.error(request, f"Order ID {id_pesanan} tidak ditemukan di batch {nama_batch}.")
        return redirect('batchorder_view', nama_batch=nama_batch)
    
    # Ambil detail order utama dari item pertama (untuk tanggal, customer, keterangan)
    first_order_item = order_items_in_batch.first()

    # Format data untuk detail_items yang akan di-render di template
    detail_items_for_template = []
    for item in order_items_in_batch:
        stok_info = 0
        if item.product and hasattr(item.product, 'stock') and item.product.stock is not None:
            stok_info = item.product.stock.quantity # Stok tersedia fisik

        detail_items_for_template.append({
            'order_pk': item.pk, # PK dari objek Order item itu sendiri
            'sku': item.sku,
            'barcode': getattr(item.product, 'barcode', '') if item.product else '',
            'nama_produk': getattr(item.product, 'nama_produk', '') if item.product else '',
            'variant': getattr(item.product, 'variant_produk', '') if item.product else '',
            'brand': getattr(item.product, 'brand', '') if item.product else '',
            'stok': stok_info,
            'jumlah': item.jumlah,
            'harga': item.harga_promosi,
        })
    
    context = {
        'nama_batch': nama_batch,
        'order': first_order_item, # Menggunakan first_order_item sebagai 'order' utama
        'detail_items': detail_items_for_template,
    }
    return render(request, 'fullfilment/editorderbatch.html', context)

@login_required
@require_POST
@csrf_exempt
def edit_order_batch_submit(request):
    """
    Menangani submit form dari editorderbatch.html untuk memperbarui, menghapus, atau menambah
    item order di dalam batch secara granular, tanpa menghapus semua.
    """
    try:
        data = json.loads(request.body)
        nama_batch = data.get('nama_batch')
        original_order_id_pesanan = data.get('original_order_id_pesanan')
        keterangan = data.get('keterangan')
        produk_data = data.get('produk_data', [])

        if not (nama_batch and original_order_id_pesanan and produk_data is not None):
            return JsonResponse({'success': False, 'error': 'Missing required parameters.'}, status=400)
        
        with transaction.atomic():
            batch_list = get_object_or_404(BatchList, nama_batch=nama_batch)

            # 1. Cek status batch: tidak boleh closed
            if batch_list.status_batch == 'closed':
                return JsonResponse({'success': False, 'error': 'Batch is closed and cannot be edited. Please contact administrator.'}, status=403)

            # BARU: Ambil status dan informasi lain dari Order yang sudah ada dengan id_pesanan yang sama
            # Ini akan digunakan untuk item Order baru agar statusnya konsisten
            original_order_example = Order.objects.filter(id_pesanan=original_order_id_pesanan).first()

            # Set default jika tidak ada original_order_example (seharusnya tidak terjadi di flow edit)
            parent_status = original_order_example.status if original_order_example else 'Lunas'
            parent_status_order = original_order_example.status_order if original_order_example else 'pending'
            parent_jenis_pesanan = original_order_example.jenis_pesanan if original_order_example else 'manual'
            parent_channel = original_order_example.channel if original_order_example else 'manual'
            parent_tanggal_pembuatan = original_order_example.tanggal_pembuatan if original_order_example else datetime.datetime.now()

            # 2. Ambil Kondisi Saat Ini (Existing Data)
            existing_order_items_qs = Order.objects.filter(
                id_pesanan=original_order_id_pesanan,
                nama_batch=nama_batch
            ).select_for_update() 

            existing_order_items_map = {item.sku: item for item in existing_order_items_qs}

            existing_batch_items_qs = BatchItem.objects.filter(
                batchlist=batch_list,
                product__sku__in=existing_order_items_map.keys() 
            ).select_for_update() 

            existing_batch_items_map = {item.product.sku: item for item in existing_batch_items_qs}
            
            # 3. Persiapkan Data Baru (Frontend Input)
            new_product_data_map = {item['sku']: item for item in produk_data}
            new_skus_set = set(new_product_data_map.keys())

            # 4. Proses Perubahan: Identifikasi dan Proses SKU yang Dihapus
            for sku, old_order_item in existing_order_items_map.items():
                if sku not in new_skus_set:
                    # SKU ini dihapus dari pesanan
                    product_obj = old_order_item.product 
                    if not product_obj:
                        logging.warning(f"Product not found for SKU {sku} of old order item {old_order_item.pk}. Skipping stock adjustment.")
                        continue

                    try:
                        product_stock = Stock.objects.select_for_update().get(product=product_obj)
                        product_stock.quantity_locked = max(0, product_stock.quantity_locked - old_order_item.jumlah)
                        product_stock.save(update_fields=['quantity_locked'])
                    except Stock.DoesNotExist:
                        logging.warning(f"Stock for product {product_obj.sku} not found during delete operation for order {old_order_item.id_pesanan}. Skipping stock adjustment.")
                    
                    old_batch_item = existing_batch_items_map.get(sku)
                    if old_batch_item:
                        old_batch_item.delete()
                    
                    old_order_item.delete()

            # 5. Proses Perubahan: Identifikasi dan Proses SKU yang Diperbarui atau Ditambahkan
            for sku, item_data in new_product_data_map.items():
                new_jumlah = int(item_data.get('jumlah'))
                new_harga = float(item_data.get('harga'))
                
                if new_jumlah <= 0:
                    continue

                product_obj = get_object_or_404(Product, sku=sku)

                if sku in existing_order_items_map:
                    # UPDATE ITEM LAMA
                    existing_order_item = existing_order_items_map[sku]
                    existing_batch_item = existing_batch_items_map.get(sku)

                    old_jumlah_order = existing_order_item.jumlah
                    qty_diff = new_jumlah - old_jumlah_order

                    try:
                        product_stock = Stock.objects.select_for_update().get(product=product_obj)
                        product_stock.quantity_locked += qty_diff
                        product_stock.quantity_locked = max(0, product_stock.quantity_locked)
                        product_stock.save(update_fields=['quantity_locked'])
                    except Stock.DoesNotExist:
                        logging.error(f"Stock for product {sku} not found when updating order {original_order_id_pesanan}. Cannot adjust stock.")
                        raise Exception(f"Stock for product {sku} not found. Cannot update order.")

                    # Update Order Item
                    existing_order_item.jumlah = new_jumlah
                    existing_order_item.harga_promosi = new_harga
                    existing_order_item.catatan_pembeli = keterangan
                    # Status Order, Status, Jenis Pesanan, Channel TIDAK di-update di sini
                    # diasumsikan tetap sama dengan nilai yang sudah ada di existing_order_item
                    existing_order_item.save(update_fields=['jumlah', 'harga_promosi', 'catatan_pembeli'])

                    # Update BatchItem
                    if existing_batch_item:
                        existing_batch_item.jumlah = new_jumlah

                        # Logika status_ambil (jumlah_ambil tidak diubah di sini)
                        if existing_batch_item.jumlah_ambil > new_jumlah:
                            existing_batch_item.status_ambil = 'over_stock'
                        elif new_jumlah == 0:
                            existing_batch_item.status_ambil = 'cancelled'
                        elif existing_batch_item.jumlah_ambil == new_jumlah and new_jumlah > 0:
                            existing_batch_item.status_ambil = 'completed'
                        elif existing_batch_item.jumlah_ambil > 0 and existing_batch_item.jumlah_ambil < new_jumlah:
                            existing_batch_item.status_ambil = 'partial'
                        elif existing_batch_item.jumlah_ambil == 0 and new_jumlah > 0:
                            existing_batch_item.status_ambil = 'pending'
                        # Jika tidak ada kondisi di atas yang terpenuhi, biarkan status_ambil seperti semula
                        
                        existing_batch_item.save(update_fields=['jumlah', 'status_ambil']) # jumlah_ambil tidak di-update disini
                    else:
                        # Ini seharusnya tidak terjadi jika data konsisten, tapi jika terjadi, buat baru
                        BatchItem.objects.create(
                            batchlist=batch_list,
                            product=product_obj,
                            jumlah=new_jumlah,
                            status_ambil='pending',
                            jumlah_ambil=0, # Ini hanya untuk item BatchItem yang baru dibuat
                        )

                else:
                    # TAMBAH ITEM BARU
                    Order.objects.create(
                        id_pesanan=original_order_id_pesanan,
                        tanggal_pembuatan=parent_tanggal_pembuatan,
                        sku=sku,
                        product=product_obj,
                        jumlah=new_jumlah,
                        harga_promosi=new_harga,
                        catatan_pembeli=keterangan, 
                        status=parent_status,
                        nama_batch=nama_batch,
                        jenis_pesanan=parent_jenis_pesanan,
                        channel=parent_channel,
                        status_order=parent_status_order,
                        status_cancel='N',
                        status_retur='N',
                        jumlah_ambil=0, # Jumlah_ambil default 0 untuk item Order baru
                        status_ambil='pending', 
                    )
                    
                    try:
                        product_stock = Stock.objects.select_for_update().get(product=product_obj)
                        product_stock.quantity_locked += new_jumlah
                        product_stock.save(update_fields=['quantity_locked'])
                    except Stock.DoesNotExist:
                        logging.error(f"Stock for product {sku} not found when adding new order item for batch {nama_batch}. Cannot adjust stock.")
                        raise Exception(f"Stock for product {sku} not found. Cannot add to batch.")
                    
                    BatchItem.objects.create(
                        batchlist=batch_list,
                        product=product_obj,
                        jumlah=new_jumlah,
                        status_ambil='pending',
                        jumlah_ambil=0, # Jumlah_ambil default 0 untuk BatchItem baru
                    )

            # 6. Hitung ulang order_type untuk semua item Order dengan id_pesanan yang sama
            current_order_items = Order.objects.filter(id_pesanan=original_order_id_pesanan).select_related('product')
            
            if current_order_items.count() == 0:
                new_order_type = None 
            elif current_order_items.count() == 1:
                single_item = current_order_items.first()
                if single_item.jumlah == 1:
                    new_order_type = '1'
                else:
                    new_order_type = '2'
            else:
                brands = set()
                for item in current_order_items:
                    if item.product and item.product.brand:
                        brands.add(item.product.brand.strip().upper())
                    else:
                        brands.add('')

                if len(brands) == 1 and list(brands)[0] != '':
                    new_order_type = '4'
                else:
                    new_order_type = '3'
            
            if new_order_type is not None:
                current_order_items.update(order_type=new_order_type)

            return JsonResponse({'success': True, 'message': 'Order batch updated successfully.'})

    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'One or more products (SKU) not found.'}, status=400)
    except BatchList.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Batch not found.'}, status=404)
    except Exception as e:
        logging.error(f"Error in edit_order_batch_submit: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': f'An unexpected error occurred: {str(e)}'}, status=500)

@login_required
def batchitem_detail_view(request, nama_batch, pk):
    batchitem = get_object_or_404(BatchItem, pk=pk)
    product = batchitem.product

    if request.method == 'POST':
        if 'photo' in request.FILES:
            try:
                photo_file = request.FILES['photo']
                img = Image.open(photo_file)
                img = img.convert('RGB')
                
                # --- TAMBAHAN BARU: Putar gambar berdasarkan data EXIF orientasi ---
                img = ImageOps.exif_transpose(img) 
                # --- AKHIR TAMBAHAN BARU ---
                
                # Kompresi Otomatis: Resize & Set Quality
                img.thumbnail((1024, 1024)) # Maksimal 1024x1024 piksel

                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=85) # Kualitas 85%
                image_content = ContentFile(buffer.getvalue(), name=photo_file.name)

                product.photo.save(photo_file.name, image_content)
                product.save()
                messages.success(request, "Foto produk berhasil diupload dan dikompres!")
                return redirect(request.path) # Redirect ke halaman yang sama untuk refresh
            except Exception as e:
                messages.error(request, f"Gagal upload foto: {e}")
                logging.error(f"Error uploading photo for batchitem {pk}: {e}")
                return redirect(request.path)
        # Handle other POST requests if any, e.g., for quantity update

    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
        template = 'fullfilment/mobile_batchitem_detail.html'
    else:
        template = 'fullfilment/batchitem_detail.html'

    return render(request, template, {
        'product': product,
        'jumlah': batchitem.jumlah,
        'jumlah_ambil': batchitem.jumlah_ambil,
        'batchitem': batchitem,
        'nama_batch': nama_batch,
    })

@require_POST
@login_required
def close_batch(request, batch_id):
    """
    Menutup batch dengan validasi ketat:
    1. Tidak boleh ada unallocated stock
    2. Tidak boleh ada order gantung (not ready to pick)
    3. Semua order_id harus sudah di print (status_order = 'printed')
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed. Use POST.'
        }, status=405)
    
    batch = get_object_or_404(BatchList, pk=batch_id)
    
    try:
        with transaction.atomic():
            # ✅ VALIDASI 1: Cek apakah batch sudah closed
            if batch.status_batch == 'closed':
                return JsonResponse({
                    'success': False, 
                    'error': f"Batch '{batch.nama_batch}' sudah berstatus closed!"
                })
            
            # ✅ VALIDASI 2: Cek apakah ada order gantung (not ready to pick)
            not_ready_ids = get_not_ready_to_pick_ids(batch)
            if not_ready_ids:
                return JsonResponse({
                    'success': False,
                    'error': f"Batch '{batch.nama_batch}' tidak bisa ditutup karena masih ada {len(not_ready_ids)} order yang belum ready to pick!"
                })
            
            # ✅ VALIDASI 3: Cek apakah ada unallocated stock
            # Hitung total picked quantities per produk
            picked_quantities = BatchItem.objects.filter(batchlist=batch) \
                .values('product_id') \
                .annotate(total_picked=Sum('jumlah_ambil'))

            picked_quantities_map = {item['product_id']: item['total_picked'] for item in picked_quantities}
            
            # Ambil ready to print IDs
            ready_to_print_ids = ReadyToPrint.objects.filter(batchlist=batch).values_list('id_pesanan', flat=True)
            
            # Hitung total needed quantities dari order yang ready to print
            needed_quantities = Order.objects.filter(nama_batch=batch.nama_batch, id_pesanan__in=ready_to_print_ids) \
                .values('product_id') \
                .annotate(total_needed=Sum('jumlah'))

            needed_quantities_map = {item['product_id']: item['total_needed'] for item in needed_quantities}
            
            # Cek unallocated stock
            unallocated_products = []  # ✅ DEFINE VARIABLE INI
            for picked in picked_quantities:
                product_id = picked['product_id']
                picked_qty = picked['total_picked']
                needed_qty = next((item['total_needed'] for item in needed_quantities if item['product_id'] == product_id), 0)
                unallocated_qty = picked_qty - needed_qty
                if unallocated_qty > 0:
                    product = Product.objects.get(id=product_id)
                    unallocated_products.append({
                        'sku': product.sku,
                        'unallocated_qty': unallocated_qty
                    })
            
            if unallocated_products:
                product_list = ', '.join([f"{p['sku']} ({p['unallocated_qty']} qty)" for p in unallocated_products])
                return JsonResponse({
                    'success': False,
                    'error': f"Batch '{batch.nama_batch}' tidak bisa ditutup karena masih ada unallocated stock: {product_list}"
                })
            
            # ✅ VALIDASI 4: Cek 3 case - status kosong, pending, wajib printed
            # Case 1: Status kosong atau NULL
            empty_status_orders = Order.objects.filter(
                nama_batch=batch.nama_batch
            ).filter(
                Q(status_order='') | Q(status_order__isnull=True)
            )

            # Case 2: Status pending
            pending_orders = Order.objects.filter(
                nama_batch=batch.nama_batch,
                status_order='pending'
            )

            # Case 3: Status bukan printed
            non_printed_orders = Order.objects.filter(
                nama_batch=batch.nama_batch
            ).exclude(
                status_order='printed'
            )

            # Gabungkan semua case
            all_unprinted = empty_status_orders | pending_orders | non_printed_orders

            if all_unprinted.exists():
                # Ambil contoh untuk ditampilkan
                sample_orders = all_unprinted.values('id_pesanan', 'status_order')[:5]
                order_list = []
                
                for order in sample_orders:
                    status = order['status_order'] or 'kosong'
                    order_list.append(f"{order['id_pesanan']} ({status})")
                
                if all_unprinted.count() > 5:
                    order_list.append(f"... dan {all_unprinted.count() - 5} order lainnya")
                
                return JsonResponse({
                    'success': False,
                    'error': f"Batch '{batch.nama_batch}' tidak bisa ditutup karena masih ada {all_unprinted.count()} order yang belum di print! Contoh: {', '.join(order_list)}"
                })
            
            # ✅ SEMUA VALIDASI BERHASIL - LANJUTKAN CLOSE BATCH
            
            # 1. Increment close_count
            batch.close_count += 1
            close_count = batch.close_count
            
            # 2. Ubah status batch menjadi 'closed'
            batch.status_batch = 'closed'
            batch.completed_at = timezone.now()
            batch.save(update_fields=['status_batch', 'completed_at', 'close_count'])

            # 3. Kelompokkan BatchItem berdasarkan product_id DAN batchlist_id
            batch_items = BatchItem.objects.filter(
                batchlist=batch
            ).exclude(
                jumlah_ambil=0 # Hanya proses item yang memiliki jumlah_ambil > 0
            ).select_related('product')

            # Kelompokkan berdasarkan product_id DAN batchlist_id
            product_batch_totals = {}
            for batch_item in batch_items:
                if not batch_item.product:
                    continue
                
                # Key untuk grouping: (product_id, batchlist_id)
                grouping_key = (batch_item.product.id, batch_item.batchlist.id)
                if grouping_key not in product_batch_totals:
                    product_batch_totals[grouping_key] = {
                        'product': batch_item.product,
                        'batchlist': batch_item.batchlist,
                        'total_jumlah_ambil': 0,
                        'batch_items': []
                    }
                product_batch_totals[grouping_key]['total_jumlah_ambil'] += batch_item.jumlah_ambil
                product_batch_totals[grouping_key]['batch_items'].append(batch_item)

            processed_items = 0
            for grouping_key, data in product_batch_totals.items():
                product = data['product']
                batchlist = data['batchlist']
                total_jumlah_ambil = data['total_jumlah_ambil']

                try:
                    stock = Stock.objects.select_for_update().get(product=product)
                    
                    # 4. Cek apakah ada perubahan quantity dari close batch sebelumnya
                    last_close_entry = StockCardEntry.objects.filter(
                        notes__contains=f"Batch {batch.nama_batch}",
                        product=product,
                        tipe_pergerakan='close_batch'
                    ).order_by('-waktu').first()
                    
                    # Jika tidak ada perubahan quantity, skip
                    if last_close_entry and last_close_entry.qty == -total_jumlah_ambil:
                        continue
                    
                    # PERBAIKAN: Hitung stock awal dan akhir dengan benar
                    qty_awal_fisik = stock.quantity + total_jumlah_ambil  # Stock awal = quantity saat ini + jumlah_ambil
                    qty_akhir_fisik = stock.quantity  # Stock akhir = quantity saat ini
                    
                    # Update quantity_locked
                    stock.quantity_locked -= total_jumlah_ambil
                    stock.quantity_locked = max(0, stock.quantity_locked)
                    stock.save(update_fields=['quantity_locked'])

                    # 5. Buat SATU entri StockCardEntry untuk perubahan quantity
                    StockCardEntry.objects.create(
                        product=product,
                        tipe_pergerakan='close_batch',
                        qty=-total_jumlah_ambil, # Pengurangan quantity (negatif)
                        qty_awal=qty_awal_fisik,  # Stock awal (quantity + jumlah_ambil)
                        qty_akhir=qty_akhir_fisik, # Stock akhir (quantity saat ini)
                        notes=f'Close Batch ke-{close_count} dari batch {batchlist.nama_batch}',
                        user=request.user,
                        reference=batchlist
                    )
                    
                    processed_items += 1

                except Stock.DoesNotExist:
                    continue
            
            return JsonResponse({
                'success': True,
                'message': f"Batch '{batch.nama_batch}' berhasil ditutup (Closed). {processed_items} produk diproses."
            })
    
    except Exception as e:
        logging.error(f"Error closing batch {batch_id}: {e}")
        return JsonResponse({
            'success': False,
            'error': f"Terjadi kesalahan saat menutup batch: {e}"
        })

@require_POST
@login_required
def reopen_batch(request, batch_id):
    try:
        with transaction.atomic():
            batch = get_object_or_404(BatchList, pk=batch_id)
            if batch.status_batch != 'closed':
                messages.error(request, "Hanya batch yang berstatus 'closed' yang bisa di Re-Open.")
                return redirect('/fullfilment/')

            # PERBAIKAN: Ubah status_batch menjadi 'open'
            batch.status_batch = 'open'
            batch.save(update_fields=['status_batch'])

            # PERBAIKAN: Gunakan jumlah_ambil untuk item yang sudah di-pick
            batch_items = BatchItem.objects.filter(batchlist=batch).exclude(jumlah_ambil=0)
            processed_items = 0
            
            for batch_item in batch_items:
                try:
                    stock = Stock.objects.select_for_update().get(product=batch_item.product)
                    
                    # PERBAIKAN: Kembalikan (tambahkan) jumlah_ambil ke quantity_locked
                    stock.quantity_locked += batch_item.jumlah_ambil
                    stock.save(update_fields=['quantity_locked'])
                    
                    processed_items += 1

                except Stock.DoesNotExist:
                    messages.warning(request, f"Stok untuk produk {batch_item.product.sku} tidak ditemukan saat Re-Open Batch.")
                    continue

            messages.success(request, f"Batch '{batch.nama_batch}' berhasil dibuka kembali. {processed_items} item diproses.")
            return redirect('/fullfilment/')
    
    except Exception as e:
        logging.error(f"Error reopening batch {batch_id}: {e}")
        messages.error(request, f"Terjadi kesalahan saat membuka kembali batch: {e}")
        return redirect('/fullfilment/')

@login_required
def scanpicking_list_view(request):
    """Menampilkan halaman daftar order yang siap untuk dipicking."""
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = any(x in user_agent for x in ['android', 'iphone', 'ipad', 'ipod', 'blackberry', 'iemobile', 'opera mini'])

    if is_mobile:
        if not request.user.has_perm('fullfilment.view_mobile_picking_module'):
            raise PermissionDenied
    else:
        if not request.user.has_perm('fullfilment.view_desktop_picking_module'):
            raise PermissionDenied
            
    return render(request, 'fullfilment/scanpicking_list.html')

@login_required
def scanpicking_list_api(request):
    """API untuk DataTables daftar order yang siap untuk dipicking."""
    if not (
        request.user.has_perm('fullfilment.view_desktop_picking_module') or
        request.user.has_perm('fullfilment.view_mobile_picking_module')
    ):
        raise PermissionDenied

    draw = int(request.GET.get('draw', 0))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 25))
    search_value = request.GET.get('search[value]', '')

    # Queryset dasar
    base_queryset = Order.objects.filter(status_order='printed')

    # Hitung total record unik
    total_records = base_queryset.values('id_pesanan').distinct().count()

    # Terapkan filter pencarian jika ada
    if search_value:
        base_queryset = base_queryset.filter(
            Q(id_pesanan__icontains=search_value) |
            Q(nama_batch__icontains=search_value)
        )
    
    # Hitung record unik setelah difilter
    filtered_records = base_queryset.values('id_pesanan').distinct().count()

    # Ambil data unik, ambil nilai pertama untuk kolom lain
    unique_orders_queryset = base_queryset.values(
        'id_pesanan'
    ).annotate(
        tanggal_pembuatan=Min('tanggal_pembuatan'),
        nama_batch=Min('nama_batch'),
        status_order=Min('status_order'),
    ).order_by('-tanggal_pembuatan')

    # Terapkan paginasi
    data = list(unique_orders_queryset[start:start + length])

    # Format data (tambahkan 'pk' dan format tanggal)
    for item in data:
        item['pk'] = item['id_pesanan'] # Tambahkan pk untuk checkbox
        tanggal = item.get('tanggal_pembuatan')
        # PASTIKAN hanya format jika tipenya adalah datetime
        if isinstance(tanggal, datetime.datetime):
            item['tanggal_pembuatan'] = tanggal.strftime('%Y-%m-%d %H:%M')

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': filtered_records,
        'data': data,
    })

@require_POST
@csrf_exempt
@login_required
def print_selected_ready_to_pick(request):
    """
    Menandai item-item yang dipilih dari tabel 'Ready to Print' sebagai tercetak.
    Menggantikan logika lama yang mengunduh Excel dengan respons JSON.
    """
    ids = request.POST.getlist('ids[]')
    if not ids:
        return JsonResponse({'success': False, 'error': 'Tidak ada item yang dipilih.'})

    # Temukan item ReadyToPrint yang sesuai dengan ID yang dipilih
    # dan pastikan mereka belum di-print sebelumnya.
    items_to_update = ReadyToPrint.objects.filter(pk__in=ids, printed_at__isnull=True)

    if not items_to_update:
        return JsonResponse({'success': False, 'error': 'Item yang dipilih sudah di-print sebelumnya atau tidak valid.'})

    order_ids = list(items_to_update.values_list('id_pesanan', flat=True).distinct())

    # Lakukan update massal
    now_jakarta = timezone.now().astimezone(pytz.timezone('Asia/Jakarta'))
    updated_count = items_to_update.update(
        status_print='printed',
        printed_at=now_jakarta,
        printed_via='SELECTED', # Menandakan ini dari aksi 'print selected'
        printed_by=request.user
    )

    # Update juga status di tabel Order utama
    if updated_count > 0:
        Order.objects.filter(id_pesanan__in=order_ids).update(status_order='printed')
        
        # UPDATE JUMLAH_TERPAKAI berdasarkan product dari order yang di-print
        from collections import defaultdict
        
        # Ambil semua order yang baru di-print
        printed_orders = Order.objects.filter(
            id_pesanan__in=order_ids
        )
        
        # Hitung jumlah terpakai per product
        product_usage = defaultdict(int)
        
        for order in printed_orders:
            if order.product_id:
                product_usage[order.product_id] += order.jumlah  # <- PERBAIKAN
        
        # Update jumlah_terpakai di BatchItem untuk setiap batch yang terlibat
        batch_ids = items_to_update.values_list('batchlist_id', flat=True).distinct()
        
        for batch_id in batch_ids:
            batchlist = BatchList.objects.get(id=batch_id)
            
            # Update jumlah_terpakai di BatchItem
            for product_id, usage_count in product_usage.items():
                try:
                    batch_item = BatchItem.objects.get(
                        batchlist=batchlist,
                        product_id=product_id
                    )
                    batch_item.jumlah_terpakai += usage_count
                    batch_item.save()
                except BatchItem.DoesNotExist:
                    # Jika BatchItem tidak ditemukan, skip
                    continue
        
        return JsonResponse({'success': True, 'message': f'{updated_count} item berhasil ditandai sebagai printed dan jumlah_terpakai telah diupdate.'})
    
    return JsonResponse({'success': False, 'error': 'Tidak ada item yang berhasil diupdate.'})

     
@login_required
def orders_packing_view(request):
    """
    Menampilkan halaman untuk scan packing order.
    """
    # ... existing code ...
    return response

@login_required
@permission_required('fullfilment.view_scanpacking', raise_exception=True)
def scanpacking(request):
    # ... existing code ...
    context = {
        'total_packers_today': len(user_scores)
    }
    return render(request, 'fullfilment/scanpacking.html', context)

@login_required
def ready_to_ship(request):
    """Menampilkan daftar order yang siap untuk dikirim."""
    last_10_shipping = OrderHandoverHistory.objects.select_related('user', 'order').order_by('-waktu_ho')[:10]

    # Inisialisasi timezone Jakarta
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    
    # Proses setiap item untuk melokalisasi waktu
    processed_shipping_history = []
    for item in last_10_shipping:
        if item.waktu_ho: # Hanya lokalisasi jika bukan None
            item.waktu_ho = item.waktu_ho.astimezone(jakarta_tz)
        processed_shipping_history.append(item)

    context = {
        'last_10_shipping': processed_shipping_history
    }
    return render(request, 'fullfilment/scanshipping.html', context)

def dashboard(request):
    """Menampilkan halaman dashboard fulfillment."""
    return dashboard_view(request)

@login_required
def scanbatch(request, nama_batch):
    context = {
        'nama_batch': nama_batch,
    }
    return render(request, 'fullfilment/scanbatch.html', context)



@csrf_exempt
@require_POST
@login_required
def upload_batchitem_photo(request, pk):
    batchitem = get_object_or_404(BatchItem, pk=pk)
    photo = request.FILES.get('photo')
    if not photo:
        return JsonResponse({'success': False, 'error': 'No photo uploaded'})
    product = batchitem.product
    product.photo.save(photo.name, photo)
    product.save()
    return JsonResponse({'success': True, 'photo_url': product.photo.url})

@csrf_exempt
@require_POST
@login_required
def delete_batchitem_photo(request, pk):
    try:
        batchitem = get_object_or_404(BatchItem, pk=pk)
        product = batchitem.product

        if product.photo:
            # Pastikan product.photo ada sebelum mencoba menghapus
            # Jika Anda ingin menghapus file lama dari disk, pastikan settings.py atau model sudah diatur (misalnya dengan django-cleanup)
            # Django defaultnya tidak menghapus file dari disk saat field di-clear, hanya referensinya.
            product.photo.delete(save=True) # Ini akan menghapus file dari storage dan set field ke None
            messages.success(request, "Foto produk berhasil dihapus!")
            
            # --- PERBAIKAN DI SINI: Gunakan nama URL 'batchitem_detail_view' ---
            nama_batch_for_redirect = batchitem.batchlist.nama_batch
            return redirect('batchitem_detail_view', nama_batch=nama_batch_for_redirect, pk=batchitem.pk)
        else:
            messages.warning(request, "Tidak ada foto untuk dihapus pada produk ini.")
            # Tetap redirect ke halaman detail yang sama
            nama_batch_for_redirect = batchitem.batchlist.nama_batch
            return redirect('batchitem_detail_view', nama_batch=nama_batch_for_redirect, pk=batchitem.pk)
    except Exception as e:
        messages.error(request, f"Gagal menghapus foto: {e}")
        logging.error(f"Error deleting photo for batchitem {pk}: {e}")
        # Jika terjadi error saat proses hapus (bukan karena URL salah), maka akan redirect ke /fullfilment/
        # Ini adalah fallback agar aplikasi tidak crash dan user tetap bisa kembali ke halaman utama.
        return redirect('/fullfilment/')

@login_required
def download_batchitem_pdf(request, nama_batch):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    batch = BatchList.objects.filter(nama_batch=nama_batch).first()
    if not batch:
        return HttpResponse("Batch tidak ditemukan.", status=404)
    items = BatchItem.objects.filter(batchlist=batch).select_related('product').order_by('product__brand', '-one_count')

    styles = getSampleStyleSheet()
    styleN = styles['Normal']
    styleN.fontSize = 8

    # Siapkan data tabel
    data = [
        ["No", "SKU", "Barcode", "Nama Produk", "Varian Produk", "Brand", "Rak", "Qty", "Sat"]
    ]
    for idx, item in enumerate(items, 1):
        product = item.product
        data.append([
            idx,
            Paragraph(str(getattr(product, 'sku', '')), styleN),
            Paragraph(str(getattr(product, 'barcode', '')), styleN),
            Paragraph(str(getattr(product, 'nama_produk', '')), styleN),
            Paragraph(str(getattr(product, 'variant_produk', '')), styleN),
            Paragraph(str(getattr(product, 'brand', '')), styleN),
            Paragraph(str(getattr(product, 'rak', '')), styleN),
            item.jumlah,
            item.one_count,
        ])

    # Siapkan response PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="batchitem_{nama_batch}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=20)
    # Lebar kolom disesuaikan agar tidak saling timpa
    table = Table(
        data,
        colWidths=[22, 45, 60, 250, 60, 55, 25, 20, 20]
    )
    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#e3f0ff")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#1769aa")),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('ALIGN', (0,1), (0,-1), 'CENTER'),  # No
        ('ALIGN', (1,1), (2,-1), 'LEFT'),    # SKU, Barcode
        ('ALIGN', (3,1), (5,-1), 'LEFT'),    # Nama, Varian, Brand
        ('ALIGN', (6,1), (8,-1), 'CENTER'),  # Rak, Jumlah, One Count
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),

        # PERBAIKAN: Menonjolkan kolom Qty (kolom ke-8, index 7)
        ('FONTNAME', (7, 0), (7, -1), 'Helvetica-Bold'), # Membuat seluruh kolom Qty tebal
        ('FONTSIZE', (7, 0), (7, -1), 10),              # Memperbesar font seluruh kolom Qty
        ('TEXTCOLOR', (7, 1), (7, -1), colors.black),   # Warna teks data Qty menjadi hitam
    ])
    table.setStyle(style)

    elements = []
    elements.append(Paragraph(f"<b>Batch: {nama_batch}</b>", styles['Title']))
    elements.append(Spacer(1, 12))
    elements.append(table)

    doc.build(elements)
    return response

@login_required
def batchitemlogs(request, nama_batch):
    # Queryset dasar, diurutkan berdasarkan waktu terbaru
    logs_queryset = BatchItemLog.objects.filter(batch__nama_batch=nama_batch).select_related('product').order_by('-waktu')

    # Tambahkan paginasi
    paginator = Paginator(logs_queryset, 20)  # 20 log per halaman
    page_number = request.GET.get('page')
    logs_page_obj = paginator.get_page(page_number)

    # Deteksi user agent untuk mobile
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent

    context = {
        'logs': logs_page_obj,
        'nama_batch': nama_batch,
    }

    if is_mobile:
        template_name = 'fullfilment/mobile_batchitem_logs.html'
    else:
        template_name = 'fullfilment/batchitemlogs.html' # Ini adalah template desktop yang ada

    return render(request, template_name, context)

@login_required
@permission_required('fullfilment.generate_batch', raise_exception=True)
def printed_list(request):
    """Menampilkan riwayat item yang sudah di-print, dengan paginasi server-side dan statistik akurat."""
    
    base_qs = ReadyToPrint.objects.filter(printed_at__isnull=False)

    total_sessions = base_qs.values('printed_at').distinct().count()
    total_orders_printed = base_qs.count()
    handed_over_sessions = base_qs.filter(handed_over_at__isnull=False).values('printed_at').distinct().count()
    pending_sessions = total_sessions - handed_over_sessions
    
    print_groups_qs = base_qs.values('printed_at', 'printed_via', 'printed_by__username') \
        .annotate(total_printed=Count('id')) \
        .order_by('-printed_at')

    paginator = Paginator(print_groups_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    grouped_prints_data = []
    for group in page_obj:
        first_item = ReadyToPrint.objects.filter(printed_at=group['printed_at']).first()
        is_handed_over = first_item.handed_over_at is not None if first_item else False
        is_copied = first_item.copied_at is not None if first_item else False
        
        grouped_prints_data.append({
            'printed_at': group['printed_at'],
            'total_printed': group['total_printed'],
            'printed_via': group['printed_via'],
            'printed_by': group['printed_by__username'] or 'N/A',
            'is_handed_over': is_handed_over,
            'is_copied': is_copied,
        })
        
    context = {
        'page_obj': page_obj,
        'grouped_prints': grouped_prints_data,
        'total_sessions': total_sessions,
        'total_orders_printed': total_orders_printed,
        'handed_over_sessions': handed_over_sessions,
        'pending_sessions': pending_sessions,
    }
    return render(request, 'fullfilment/printedlist.html', context)

@login_required
@permission_required('fullfilment.generate_batch', raise_exception=True)
def get_printed_session_details(request):
    """API endpoint untuk mengambil daftar ID pesanan dari sesi print tertentu."""
    printed_at_iso = request.GET.get('printed_at')
    if not printed_at_iso:
        return JsonResponse({'success': False, 'error': 'Missing printed_at parameter'}, status=400)

    try:
        # Perbaikan: Membuat parsing string tanggal lebih fleksibel
        # Mengganti spasi di akhir (jika ada) dengan '+' untuk format iso yang valid
        if ' ' in printed_at_iso:
            parts = printed_at_iso.rsplit(' ', 1)
            if ':' in parts[1]:
                printed_at_iso = f"{parts[0]}+{parts[1]}"

        printed_at_dt = datetime.datetime.fromisoformat(printed_at_iso)
        
        orders = ReadyToPrint.objects.filter(printed_at=printed_at_dt).values_list('id_pesanan', flat=True).order_by('id_pesanan')
# Standar library
        order_list = list(orders)

        return JsonResponse({'success': True, 'orders': order_list})
    except Exception as e:
        error_message = f"Invalid isoformat string: '{request.GET.get('printed_at')}'"
        return JsonResponse({'success': False, 'error': error_message}, status=500)

@require_POST
@csrf_exempt
@login_required
@permission_required('fullfilment.generate_batch', raise_exception=True)
def mark_as_handed_over(request):
    try:
        data = json.loads(request.body)
        printed_at_str = data.get('printed_at')
        if not printed_at_str:
            return JsonResponse({'success': False, 'error': 'Missing printed_at parameter'}, status=400)

        # Perbaikan: Membuat parsing string tanggal lebih fleksibel
        if ' ' in printed_at_str:
            parts = printed_at_str.rsplit(' ', 1)
            if ':' in parts[1]:
                printed_at_str = f"{parts[0]}+{parts[1]}"
        
        printed_at_dt = datetime.datetime.fromisoformat(printed_at_str)

        # Update semua item yang di-print pada waktu yang sama persis
        items_updated = ReadyToPrint.objects.filter(
            printed_at=printed_at_dt,
            handed_over_at__isnull=True # Hanya update yang belum diserahkan
        ).update(handed_over_at=timezone.now())

        if items_updated > 0:
            return JsonResponse({'success': True, 'message': f'{items_updated} item ditandai sudah diserahkan.'})
        else:
            return JsonResponse({'success': False, 'error': 'Sesi print ini sudah ditandai sebelumnya atau tidak ditemukan.'})

    except Exception as e:
        error_message = f"Error processing timestamp: {str(e)}"
        return JsonResponse({'success': False, 'error': error_message}, status=400)

@login_required
def get_sat_skus(request):
    nama_batch = request.GET.get('nama_batch')
    if not nama_batch:
        return JsonResponse({'success': False, 'error': 'Parameter nama_batch is required.'}, status=400)

    try:
        batchlist = get_object_or_404(BatchList, nama_batch=nama_batch)
        
        unprinted_ready_to_pick_ids = list(ReadyToPrint.objects.filter(
            batchlist=batchlist,
            status_print='pending'
        ).values_list('id_pesanan', flat=True))

        sat_orders = Order.objects.filter(
            order_type='1',
            id_pesanan__in=unprinted_ready_to_pick_ids,
            product__isnull=False
        ).select_related('product')

        # Hitung jumlah order unik per SKU
        sku_order_counts = Counter(o.product.sku for o in sat_orders.distinct('id_pesanan'))
        
        # Ambil produk unik berdasarkan SKU yang ditemukan
        unique_skus = sku_order_counts.keys()
        products_by_sku = {p.sku: p for p in Product.objects.filter(sku__in=unique_skus)}

        skus_data = []
        for sku, total_orders in sku_order_counts.items():
            product = products_by_sku.get(sku)
            if product:
                skus_data.append({
                    'sku': sku,
                    'nama_produk': product.nama_produk,
                    'variant_produk': product.variant_produk,
                    'brand': product.brand,
                    'barcode': product.barcode,
                    'photo_url': product.photo.url if product.photo else None,
                    'totalOrders': total_orders
                })
        
        skus_data.sort(key=lambda x: x['totalOrders'], reverse=True)

        return JsonResponse({'success': True, 'skus': skus_data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def print_sat_sku(request):
    sku = request.GET.get('sku')
    nama_batch = request.GET.get('nama_batch')

    if not sku or not nama_batch:
        return JsonResponse({'success': False, 'error': 'Parameter sku dan nama_batch dibutuhkan.'}, status=400)

    try:
        batchlist = get_object_or_404(BatchList, nama_batch=nama_batch)
        
        unprinted_ready_to_pick_ids = list(ReadyToPrint.objects.filter(
            batchlist=batchlist, printed_at__isnull=True
        ).values_list('id_pesanan', flat=True))

        orders_to_print = Order.objects.filter(
            sku=sku,
            order_type='1',
            id_pesanan__in=unprinted_ready_to_pick_ids
        )

        if not orders_to_print.exists():
            return JsonResponse({'success': False, 'error': f"Tidak ada order SAT yang siap cetak untuk SKU {sku}."}, status=404)
        
        printed_order_ids = orders_to_print.values_list('id_pesanan', flat=True).distinct()
        now_jakarta = timezone.now().astimezone(pytz.timezone('Asia/Jakarta'))
        updated_count = ReadyToPrint.objects.filter(
            batchlist=batchlist, 
            id_pesanan__in=printed_order_ids,
            status_print='pending' # Hanya update yang masih pending
        ).update(
            status_print='printed', 
            printed_at=now_jakarta, 
            printed_via='SAT SKU',
            printed_by=request.user
        )

        if updated_count > 0:
            Order.objects.filter(id_pesanan__in=printed_order_ids).update(status_order='printed')
            
            # UPDATE JUMLAH_TERPAKAI berdasarkan product dari order yang di-print
            from collections import defaultdict
            
            # Ambil semua order SAT SKU yang baru di-print
            printed_orders = Order.objects.filter(
                id_pesanan__in=printed_order_ids,
                sku=sku,
                order_type='1'
            )
            
            # Hitung jumlah terpakai per product
            product_usage = defaultdict(int)
            
            for order in printed_orders:
                if order.product_id:
                    product_usage[order.product_id] += order.jumlah  # <- PERBAIKAN
            
            # Update jumlah_terpakai di BatchItem
            for product_id, usage_count in product_usage.items():
                try:
                    batch_item = BatchItem.objects.get(
                        batchlist=batchlist,
                        product_id=product_id
                    )
                    batch_item.jumlah_terpakai += usage_count
                    batch_item.save()
                except BatchItem.DoesNotExist:
                    # Jika BatchItem tidak ditemukan, skip
                    continue
            
            return JsonResponse({'success': True, 'message': f'{updated_count} order untuk SKU {sku} telah ditandai dan jumlah_terpakai telah diupdate.'})
        else:
            return JsonResponse({'success': False, 'error': f'Tidak ada order yang perlu diupdate untuk SKU {sku}.'})

    except BatchList.DoesNotExist:
        return JsonResponse({'success': False, 'error': f"Batch dengan nama {nama_batch} tidak ditemukan."}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Terjadi error: {str(e)}"}, status=500)

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

@login_required
@require_POST
@csrf_exempt
def print_prio(request, nama_batch):
    """
    Menandai semua order PRIO (bukan order_type '1') yang siap cetak dalam satu batch sebagai 'printed'.
    Tidak menghasilkan file Excel, hanya update database.
    """
    if not nama_batch:
        return JsonResponse({'success': False, 'error': 'Parameter nama_batch wajib diisi.'}, status=400)

    try:
        batchlist = get_object_or_404(BatchList, nama_batch=nama_batch)

        # 1. Ambil semua ID pesanan yang belum di-print dari batch ini
        unprinted_ids = ReadyToPrint.objects.filter(
            batchlist=batchlist,
            printed_at__isnull=True
        ).values_list('id_pesanan', flat=True)

        if not unprinted_ids:
            return JsonResponse({'success': False, 'error': 'Tidak ada order yang siap untuk ditandai.'})

        # 2. Filter ID tersebut untuk menemukan mana yang merupakan order PRIO (bukan tipe '1')
        prio_order_ids = Order.objects.filter(
            id_pesanan__in=unprinted_ids,
            nama_batch=nama_batch
        ).exclude(order_type='1').values_list('id_pesanan', flat=True).distinct()

        if not prio_order_ids:
            return JsonResponse({'success': False, 'error': 'Tidak ada order PRIO yang ditemukan untuk ditandai.'})
        
        # 3. Update status di ReadyToPrint untuk semua order PRIO yang ditemukan
        now_jakarta = timezone.now().astimezone(pytz.timezone('Asia/Jakarta'))
        updated_count = ReadyToPrint.objects.filter(
            batchlist=batchlist,
            id_pesanan__in=list(prio_order_ids)
        ).update(
            status_print='printed',
            printed_at=now_jakarta,
            printed_via='PRIO',
            printed_by=request.user
        )

        # 4. Update status_order di tabel Order
        if updated_count > 0:
            Order.objects.filter(id_pesanan__in=list(prio_order_ids)).update(status_order='printed')
            
            # 5. UPDATE JUMLAH_TERPAKAI berdasarkan product dari order yang di-print
            from collections import defaultdict
            
            # Ambil semua order PRIO yang baru di-print
            printed_orders = Order.objects.filter(
                id_pesanan__in=list(prio_order_ids)
            ).exclude(order_type='1')
            
            # Hitung jumlah terpakai per product berdasarkan jumlah item yang dibutuhkan
            product_usage = defaultdict(int)
            
            for order in printed_orders:
                if order.product_id:
                    product_usage[order.product_id] += order.jumlah  # <- PERBAIKAN: gunakan order.jumlah
            
            # Update jumlah_terpakai di BatchItem
            for product_id, usage_count in product_usage.items():
                try:
                    batch_item = BatchItem.objects.get(
                        batchlist=batchlist,
                        product_id=product_id
                    )
                    batch_item.jumlah_terpakai += usage_count
                    batch_item.save()
                except BatchItem.DoesNotExist:
                    # Jika BatchItem tidak ditemukan, skip
                    continue
            
            return JsonResponse({
                'success': True, 
                'message': f'{updated_count} order PRIO berhasil ditandai sebagai printed dan jumlah_terpakai telah diupdate.'
            })
        else:
            return JsonResponse({'success': False, 'error': 'Tidak ada order PRIO yang berhasil diupdate.'})

    except BatchList.DoesNotExist:
        return JsonResponse({'success': False, 'error': f"Batch '{nama_batch}' tidak ditemukan."}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_POST
@csrf_exempt
@login_required
@permission_required('fullfilment.generate_batch', raise_exception=True)
def mark_as_copied(request):
    try:
        data = json.loads(request.body)
        printed_at_str = data.get('printed_at')
        if not printed_at_str:
            return JsonResponse({'success': False, 'error': 'Missing printed_at parameter'}, status=400)

        if ' ' in printed_at_str:
            parts = printed_at_str.rsplit(' ', 1)
            if ':' in parts[1]:
                printed_at_str = f"{parts[0]}+{parts[1]}"
        
        printed_at_dt = datetime.datetime.fromisoformat(printed_at_str)

        items_updated = ReadyToPrint.objects.filter(
            printed_at=printed_at_dt,
            copied_at__isnull=True
        ).update(copied_at=timezone.now())

        if items_updated > 0:
            return JsonResponse({'success': True, 'message': f'{items_updated} item ditandai sudah dicopy.'})
        else:
            return JsonResponse({'success': False, 'error': 'Sesi print ini sudah dicopy sebelumnya atau tidak ditemukan.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@csrf_exempt
@require_POST
def print_mix(request, nama_batch):
    """
    Menandai SEMUA sisa order yang belum tercetak dalam satu batch sebagai 'printed'.
    Ini berfungsi sebagai tombol sapu bersih (catch-all).
    """
    try:
        batchlist = get_object_or_404(BatchList, nama_batch=nama_batch)

        # 1. Ambil QuerySet semua item yang belum di-print di batch ini
        items_to_update = ReadyToPrint.objects.filter(
            batchlist=batchlist,
            printed_at__isnull=True
        )

        # Ambil daftar ID pesanan SEBELUM diupdate untuk keperluan update tabel Order
        order_ids_to_update = list(items_to_update.values_list('id_pesanan', flat=True).distinct())

        if not order_ids_to_update:
            return JsonResponse({'success': False, 'error': 'Semua order sudah ditandai. Tidak ada yang perlu di-print sebagai MIX.'})

        # 2. Update semua item tersebut sebagai 'MIX'
        now_jakarta = timezone.now().astimezone(pytz.timezone('Asia/Jakarta'))
        updated_count = items_to_update.update(
            status_print='printed',
            printed_at=now_jakarta,
            printed_via='MIX',
            printed_by=request.user
        )

        # 3. Update juga status di tabel Order utama
        if updated_count > 0:
            Order.objects.filter(id_pesanan__in=order_ids_to_update).update(status_order='printed')
            
            # 4. UPDATE JUMLAH_TERPAKAI berdasarkan product dari order yang di-print
            from collections import defaultdict
            
            # Ambil semua order yang baru di-print
            printed_orders = Order.objects.filter(
                id_pesanan__in=order_ids_to_update
            )
            
            # Hitung jumlah terpakai per product berdasarkan jumlah item yang dibutuhkan
            product_usage = defaultdict(int)
            
            for order in printed_orders:
                if order.product_id:
                    product_usage[order.product_id] += order.jumlah  # <- PERBAIKAN: gunakan order.jumlah
            
            # Update jumlah_terpakai di BatchItem
            for product_id, usage_count in product_usage.items():
                try:
                    batch_item = BatchItem.objects.get(
                        batchlist=batchlist,
                        product_id=product_id
                    )
                    batch_item.jumlah_terpakai += usage_count
                    batch_item.save()
                except BatchItem.DoesNotExist:
                    # Jika BatchItem tidak ditemukan, skip
                    continue
            
            return JsonResponse({'success': True, 'message': f'{updated_count} sisa order berhasil ditandai sebagai MIX dan jumlah_terpakai telah diupdate.'})
        else:
            # Kondisi ini seharusnya jarang terjadi jika pengecekan di atas lolos
            return JsonResponse({'success': False, 'error': 'Tidak ada order yang berhasil diupdate.'})

    except BatchList.DoesNotExist:
        return JsonResponse({'success': False, 'error': f"Batch '{nama_batch}' tidak ditemukan."}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Terjadi kesalahan: {str(e)}'}, status=500)

@login_required
def mobilebatchpicking(request, nama_batch):
    """
    View untuk menampilkan batchpicking (desktop & mobile)
    """
    from fullfilment.models import BatchList, BatchItem
    from products.models import Product
    from inventory.models import Rak # Import model Rak from inventory

    batch = get_object_or_404(BatchList, nama_batch=nama_batch)

    # NEW: Auto-clean batchitems dengan jumlah = 0 dan jumlah_ambil = 0
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Cari dan hapus batchitem yang jumlah = 0 dan jumlah_ambil = 0
        empty_batchitems = BatchItem.objects.filter(
            batchlist=batch,
            jumlah=0,
            jumlah_ambil=0
        )
        
        deleted_count = empty_batchitems.count()
        if deleted_count > 0:
            # Log sebelum delete untuk audit trail
            logger.info(f"Auto-cleaning {deleted_count} empty batchitems from batch {nama_batch}")
            
            # Delete batchitems
            empty_batchitems.delete()
            
            logger.info(f"Successfully auto-deleted {deleted_count} empty batchitems from batch {nama_batch}")
        else:
            logger.debug(f"No empty batchitems found in batch {nama_batch}")
            
    except Exception as e:
        logger.error(f"Error auto-cleaning empty batchitems in batch {nama_batch}: {str(e)}")
        # Continue execution even if cleanup fails

    # Ambil item pending dengan urutan khusus
    pending_items = BatchItem.objects.filter(
        batchlist=batch, status_ambil='pending'
    ).select_related('product').order_by('product__brand', '-one_count')

    # Ambil item over_stock dengan urutan standar
    over_stock_items = BatchItem.objects.filter(
        batchlist=batch, status_ambil='over_stock'
    ).select_related('product').order_by('product__brand', '-one_count')

    # Ambil item completed dengan urutan standar
    completed_items = BatchItem.objects.filter(
        batchlist=batch, status_ambil='completed'
    ).select_related('product', 'completed_by').order_by('-completed_at')

    # Gabungkan semua untuk diproses
    all_items = list(pending_items) + list(over_stock_items) + list(completed_items)
    
    # --- UPDATE STATUS BERDASARKAN JUMLAH DAN JUMLAH_AMBIL ---
    for item in all_items:
        # Simpan status lama untuk perbandingan
        old_status = item.status_ambil
        
        # Hitung status berdasarkan perbandingan jumlah dan jumlah_ambil
        if item.jumlah_ambil == 0:
            item.status_ambil = 'pending'
        elif item.jumlah_ambil > 0 and item.jumlah_ambil < item.jumlah:
            item.status_ambil = 'pending'  # Tetap pending jika belum selesai
        elif item.jumlah_ambil > item.jumlah:
            item.status_ambil = 'over_stock'
        elif item.jumlah_ambil == item.jumlah:
            item.status_ambil = 'completed'
        
        # Update status di database jika berubah
        if old_status != item.status_ambil:  # Jika ada perubahan
            item.save()

    details = []
    for item in all_items:
        product = item.product
        photo_url = product.photo.url if hasattr(product, 'photo') and product.photo else None
        details.append({
            'id': item.id,
            'sku': product.sku,
            'nama_produk': product.nama_produk,
            'variant_produk': product.variant_produk,
            'brand': product.brand,
            'barcode': product.barcode,
            'rak': getattr(product, 'rak', ''),
            'jumlah': item.jumlah,
            'jumlah_ambil': item.jumlah_ambil,
            'status_ambil': item.status_ambil,
            'photo_url': photo_url,
            'completed_at': item.completed_at,
            'completed_by': item.completed_by.username if item.completed_by else None,
            'one_count': item.one_count,
        })
    
    # Ambil rak yang memiliki produk yang dibutuhkan oleh batchitem (BELUM COMPLETED)
    from inventory.models import InventoryRakStock
    
    # Dapatkan semua product_id yang ada di batchitem (SEMUA, termasuk completed)
    product_ids_in_batch = [
        item.product.id for item in all_items
    ]
    
    # Ambil rak yang memiliki stok produk yang ada di batch (SEMUA produk)
    raks_with_stock = InventoryRakStock.objects.filter(
        product_id__in=product_ids_in_batch,
        quantity__gt=0  # Hanya rak yang memiliki stok > 0
    ).select_related('rak', 'product').order_by('rak__kode_rak')
    
    # Group by rak dan hitung total produk yang dibutuhkan
    rak_summary = {}
    for rak_stock in raks_with_stock:
        rak_key = rak_stock.rak.kode_rak
        if rak_key not in rak_summary:
            rak_summary[rak_key] = {
                'kode_rak': rak_stock.rak.kode_rak,
                'nama_rak': rak_stock.rak.nama_rak,
                'products': [],
                'total_products': 0,
                'total_stock': 0,
                'total_one_count': 0  # NEW: Tambahkan field untuk total one_count
            }
        
        # Cari batchitem yang membutuhkan produk ini (SEMUA, termasuk completed)
        batchitem_needed = next(
            (item for item in all_items 
             if item.product.id == rak_stock.product.id), 
            None
        )
        if batchitem_needed:
            rak_summary[rak_key]['products'].append({
                'sku': rak_stock.product.sku,
                'nama_produk': rak_stock.product.nama_produk,
                'brand': rak_stock.product.brand,
                'stock_available': rak_stock.quantity,
                'needed_qty': batchitem_needed.jumlah - batchitem_needed.jumlah_ambil
            })
            rak_summary[rak_key]['total_products'] += 1
            rak_summary[rak_key]['total_stock'] += rak_stock.quantity
            rak_summary[rak_key]['total_one_count'] += batchitem_needed.one_count  # NEW: Tambahkan one_count
    
    raks_data = list(rak_summary.values())

    # NEW: Tambahkan info cleanup ke context untuk debugging
    cleanup_info = {
        'batch_name': nama_batch,
        'total_items_after_cleanup': len(details),
        'auto_cleanup_enabled': True
    }

    # Hitung status counts untuk filter buttons
    from collections import Counter
    status_counts = Counter(item['status_ambil'] for item in details if item['status_ambil'] != 'completed')
    total_completed = sum(1 for item in details if item['status_ambil'] == 'completed')
    total_items = len(details)

    # Permission check untuk mobile vs desktop batchpicking menggunakan helper function
    from django.core.exceptions import PermissionDenied
    if not check_permission_by_device(request, 'batchpicking'):
        is_mobile = get_device_type(request)
        device_type = "mobile" if is_mobile else "desktop"
        raise PermissionDenied(f"Anda tidak memiliki akses ke {device_type} batchpicking")
    
    # Determine template berdasarkan device type
    is_mobile = get_device_type(request)
    if is_mobile:
        template_name = 'fullfilment/mobilebatchpicking.html'
    else:
        template_name = 'fullfilment/batchpicking.html'
    
    return render(request, template_name, {
        'nama_picklist': nama_batch,
        'nama_batch': nama_batch,  # NEW: Add nama_batch for template compatibility
        'details': details,
        'raks': raks_data, # Tambahkan data rak ke konteks
        'cleanup_info': cleanup_info, # NEW: Info cleanup untuk debugging
        'status_counts': status_counts,
        'total_completed': total_completed,
        'total_items': total_items,
    })

# mobile_batchpicking_v2 view dihapus karena tidak digunakan

@login_required
def get_order_details_api(request, id_pesanan):
    """
    API endpoint untuk mengambil detail item dari id_pesanan tertentu.
    """
    if not id_pesanan:
        return JsonResponse({'success': False, 'error': 'id_pesanan dibutuhkan'}, status=400)

    order_items = Order.objects.filter(id_pesanan=id_pesanan).select_related('product')

    if not order_items.exists():
        return JsonResponse({'success': False, 'error': 'Pesanan tidak ditemukan'}, status=404)
    
    details = []
    for item in order_items:
        product = item.product
        details.append({
            'order_id': item.id_pesanan,
            'sku': product.sku if product else item.sku,
            'barcode': product.barcode if product else 'N/A',
            'nama_produk': product.nama_produk if product else 'Produk tidak ditemukan',
            'variant_produk': product.variant_produk or '' if product else '',
            'brand': product.brand or '' if product else '',
            'jumlah': item.jumlah,
        })

    return JsonResponse({'success': True, 'details': details, 'id_pesanan': id_pesanan})

def get_not_ready_to_pick_ids(batchlist):
    # Ambil semua id_pesanan di batch
    all_ids = set(Order.objects.filter(nama_batch=batchlist.nama_batch).exclude(status_bundle='Y').values_list('id_pesanan', flat=True))
    # Ambil id_pesanan yang sudah masuk ReadyToPrint
    ready_ids = set(ReadyToPrint.objects.filter(batchlist=batchlist).values_list('id_pesanan', flat=True))
    # Sisakan yang belum masuk ReadyToPrint
    return list(all_ids - ready_ids)

@login_required
def not_ready_to_pick_details(request, nama_batch):
    """
    Menampilkan halaman baru berisi daftar detail semua item
    dari order yang statusnya "not ready to pick" dalam sebuah batch.
    """
    batchlist = get_object_or_404(BatchList, nama_batch=nama_batch)
    not_ready_ids = get_not_ready_to_pick_ids(batchlist)

    enriched_order_items = []
    total_items_count = 0

    if not not_ready_ids:
        order_items_qs = Order.objects.none()
    else:
        # Ambil semua baris order yang relevan
        # Prefetch related product to avoid N+1 queries
        order_items_qs = Order.objects.filter(id_pesanan__in=not_ready_ids).select_related('product').order_by('id_pesanan')

        # Get all BatchItems for the current batchlist for efficient lookup
        batch_items = BatchItem.objects.filter(batchlist=batchlist).select_related('product')
        batch_item_quantities = defaultdict(int)
        for bi in batch_items:
            if bi.product_id:
                batch_item_quantities[bi.product_id] += bi.jumlah_ambil

        # Get current stock quantities for products in these orders
        product_ids_in_not_ready_orders = set(order_items_qs.values_list('product_id', flat=True))
        current_stocks = {str(s.product_id): s.quantity for s in Stock.objects.filter(product_id__in=product_ids_in_not_ready_orders)}


        for item in order_items_qs:
            product_id = item.product_id
            # Ensure product_id is treated as string if Stock.product_id is char/UUID
            picked_quantity_for_product_in_batch = batch_item_quantities.get(product_id, 0)
            current_stock_for_product = current_stocks.get(str(product_id), 0)

            # Determine if this individual product for this order is *potentially* short
            # based on total picked for this product in the batch vs. this order item's demand.
            # This is a simplification but helps the user quickly see the numbers.
            is_short_for_this_item = item.jumlah > picked_quantity_for_product_in_batch

            enriched_order_items.append({
                'order_item': item,
                'picked_quantity_for_product_in_batch': picked_quantity_for_product_in_batch,
                'current_stock_for_product': current_stock_for_product,
                'is_short_for_this_item': is_short_for_this_item,
            })
            total_items_count += 1

    context = {
        'nama_batch': nama_batch,
        'order_items': enriched_order_items,
        'total_orders': len(not_ready_ids),
        'total_items': total_items_count,
    }
    return render(request, 'fullfilment/not_ready_to_pick_details.html', context)

@login_required
@require_POST
@csrf_exempt
def remove_order_item_from_batch(request):
    """
    Melepaskan satu baris item Order dari batch-nya.
    """
    try:
        data = json.loads(request.body)
        order_pk = data.get('order_pk')

        with transaction.atomic():
            # Kunci baris order yang mau diubah
            order_item = Order.objects.select_for_update().get(pk=order_pk)
            
            if not order_item.nama_batch or not order_item.product_id:
                return JsonResponse({'success': False, 'error': 'Item ini tidak terikat pada batch atau produk.'})

            batch = get_object_or_404(BatchList, nama_batch=order_item.nama_batch)
            
            # Kurangi kebutuhan di BatchItem
            try:
                batch_item = BatchItem.objects.get(batchlist=batch, product=order_item.product)
                batch_item.jumlah = max(0, batch_item.jumlah - order_item.jumlah)
                if batch_item.jumlah == 0 and batch_item.jumlah_ambil == 0:
                    batch_item.delete()
                else:
                    batch_item.save(update_fields=['jumlah'])
            except BatchItem.DoesNotExist:
                # Jika item tidak ada (seharusnya tidak terjadi), lewati saja
                pass

            # Lepaskan order item dari batch
            order_item.nama_batch = None
            order_item.save(update_fields=['nama_batch'])

            return JsonResponse({'success': True, 'message': 'Item berhasil dilepaskan dari batch.'})

    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Order item tidak ditemukan.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def unallocated_stock_list(request, nama_batch):
    """
    Menampilkan daftar produk yang di-pick berlebihan (stok gantung)
    dalam suatu batch.
    """
    batchlist = get_object_or_404(BatchList, nama_batch=nama_batch)

    # 0. Hitung total jumlah (yang dibutuhkan) per produk di BatchItem
    initial_needed_quantities_batchitem = BatchItem.objects.filter(batchlist=batchlist) \
        .values('product_id') \
        .annotate(total_needed_batchitem=Sum('jumlah'))

    initial_needed_quantities_batchitem_map = {item['product_id']: item['total_needed_batchitem'] for item in initial_needed_quantities_batchitem}

    # 1. Hitung total jumlah_ambil per produk di batch ini
    picked_quantities = BatchItem.objects.filter(batchlist=batchlist) \
        .values('product_id') \
        .annotate(total_picked=Sum('jumlah_ambil'))

    picked_quantities_map = {item['product_id']: item['total_picked'] for item in picked_quantities}

    # 2. Ambil semua id_pesanan yang READY TO PRINT di batch ini
    ready_to_print_ids = ReadyToPrint.objects.filter(batchlist=batchlist).values_list('id_pesanan', flat=True)

    # 3. Hitung total jumlah_dibutuhkan per produk dari order yang READY TO PRINT
    needed_quantities = Order.objects.filter(nama_batch=nama_batch, id_pesanan__in=ready_to_print_ids) \
        .values('product_id') \
        .annotate(total_needed=Sum('jumlah'))

    needed_quantities_map = {item['product_id']: item['total_needed'] for item in needed_quantities}

    unallocated_products_data = []

    # 4. Bandingkan picked vs needed untuk menemukan stok gantung
    product_ids_in_batch = set(picked_quantities_map.keys()).union(set(needed_quantities_map.keys()))
    
    # Ambil data produk untuk tampilan
    products = Product.objects.filter(id__in=product_ids_in_batch)
    products_map = {p.id: p for p in products}
    current_stocks_map = {str(s.product_id): s.quantity for s in Stock.objects.filter(product_id__in=product_ids_in_batch)}

    for product_id in product_ids_in_batch:
        picked_qty = picked_quantities_map.get(product_id, 0)
        needed_qty = needed_quantities_map.get(product_id, 0)
        initial_batch_item_qty = initial_needed_quantities_batchitem_map.get(product_id, 0)
        
        unallocated_qty = picked_qty - needed_qty
        sisa_butuh_qty = initial_batch_item_qty - picked_qty 

        if unallocated_qty > 0: # Hanya tampilkan jika ada surplus
            product = products_map.get(product_id)
            current_stock = current_stocks_map.get(str(product_id), 0)
            
            unallocated_products_data.append({
                'product_id': product_id,
                'sku': product.sku if product else 'N/A',
                'nama_produk': product.nama_produk if product else 'N/A',
                'variant_produk': product.variant_produk if product else 'N/A',
                'barcode': product.barcode if product else 'N/A',
                'initial_batch_item_quantity': initial_batch_item_qty,
                'total_picked_in_batch': picked_qty,
                'sisa_butuh': sisa_butuh_qty, 
                'total_needed_for_ready_orders': needed_qty,
                'unallocated_quantity': unallocated_qty,
                'current_physical_stock': current_stock,
            })
    
    # Urutkan berdasarkan unallocated_quantity terbesar
    unallocated_products_data.sort(key=lambda x: x['unallocated_quantity'], reverse=True)

    context = {
        'nama_batch': nama_batch,
        'unallocated_products': unallocated_products_data,
        'total_unallocated_items': sum(item['unallocated_quantity'] for item in unallocated_products_data),
        'total_unique_unallocated_products': len(unallocated_products_data),
    }

    return render(request, 'fullfilment/unallocated_stock_list.html', context)

@login_required
@require_POST
@csrf_exempt
def cancel_order(request):
    try:
        # Baca JSON body
        data = json.loads(request.body)
        id_pesanan = data.get('id_pesanan')
        if not id_pesanan:
            return JsonResponse({'success': False, 'error': 'Parameter id_pesanan dibutuhkan.'}, status=400)

        with transaction.atomic():
            orders = Order.objects.filter(id_pesanan=id_pesanan)
            if not orders.exists():
                return JsonResponse({'success': False, 'error': 'Order tidak ditemukan.'}, status=404)

            # === VALIDASI: ORDER HARUS SUDAH DI LUAR BATCH ===
            first_order = orders.first()
            if first_order.nama_batch:
                return JsonResponse({
                    'success': False, 
                    'error': f"Order {id_pesanan} masih berada di dalam batch '{first_order.nama_batch}'. Wajib dihapus dari batch terlebih dahulu sebelum di-cancel."
                }, status=403)

            # Update status dan status_order
            orders.update(status='cancel', status_order='cancel')

        return JsonResponse({'success': True, 'message': f'Order {id_pesanan} berhasil dibatalkan.'})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': f'Terjadi kesalahan: {str(e)}'}, status=500)

@login_required
@require_POST
@csrf_exempt
def erase_order_from_batch(request):
    """
    Menghapus SEMUA item dari sebuah id_pesanan dari batch-nya.
    """
    try:
        id_pesanan_to_erase = request.POST.get('id_pesanan')
        if not id_pesanan_to_erase:
            return JsonResponse({'status': 'error', 'message': 'ID Pesanan tidak ditemukan.'}, status=400)

        with transaction.atomic():
            orders_to_erase = Order.objects.filter(id_pesanan=id_pesanan_to_erase)
            if not orders_to_erase.exists():
                return JsonResponse({'status': 'error', 'message': 'Order tidak ditemukan.'}, status=404)
            
            # === VALIDASI STATUS BATCH ===
            first_order = orders_to_erase.first()
            if first_order.nama_batch:
                try:
                    batch = BatchList.objects.get(nama_batch=first_order.nama_batch)
                    if batch.status_batch == 'closed':
                        return JsonResponse({
                            'status': 'error', 
                            'message': f"Tidak dapat menghapus order dari batch '{first_order.nama_batch}' karena batch sudah berstatus closed."
                        }, status=403)
                except BatchList.DoesNotExist:
                    pass
            
            # === VALIDASI STATUS ORDER ===
            current_status = first_order.status_order.lower() if first_order.status_order else 'pending'
            
            # Validasi: Jika sudah printed, harus lewat scan return cancelled order
            if current_status == 'printed':
                return JsonResponse({
                    'status': 'error', 
                    'message': f"Order {id_pesanan_to_erase} sudah printed. Harus di-cancel lewat 'Scan Return Cancelled Order' di Ready to Print List."
                }, status=403)
            
            # Validasi: Jika sudah picked/packed/shipped, harus lewat return session
            forbidden_statuses = ['picked', 'packed', 'shipped']
            if current_status in forbidden_statuses:
                return JsonResponse({
                    'status': 'error', 
                    'message': f"Order {id_pesanan_to_erase} sudah melalui proses fulfillment (status: {current_status}). Wajib lewat Return Session di Return List."
                }, status=403)
            # === AKHIR VALIDASI ===
            
            nama_batch_lama = first_order.nama_batch
            if not nama_batch_lama:
                return JsonResponse({'status': 'success', 'message': 'Order sudah tidak ada di dalam batch.'})

            # Get batch object untuk logging
            try:
                batch_obj = BatchList.objects.get(nama_batch=nama_batch_lama)
            except BatchList.DoesNotExist:
                batch_obj = None

            for order in orders_to_erase:
                batchitem = BatchItem.objects.filter(batchlist__nama_batch=nama_batch_lama, product=order.product).first()
                if batchitem:
                    # Hitung sisa locked yang bisa dikembalikan
                    sisa_locked = min(order.jumlah, max(0, batchitem.jumlah - batchitem.jumlah_ambil))
                    batchitem.jumlah -= order.jumlah
                    if batchitem.jumlah <= 0 and (batchitem.jumlah_ambil == 0 or batchitem.jumlah_ambil is None):
                        batchitem.delete()
                    else:
                        batchitem.save(update_fields=['jumlah'])

                    # Kembalikan quantity_locked ke inventory
                    stock = Stock.objects.filter(product=order.product).first()
                    if stock and sisa_locked > 0:
                        stock.quantity_locked = max(0, stock.quantity_locked - sisa_locked)
                        stock.save(update_fields=['quantity_locked'])
                
                # Logging: Catat ke BatchOrderLog
                BatchOrderLog.objects.create(
                    user=request.user,
                    action_type='ERASE',
                    batch_source=batch_obj,
                    id_pesanan=order.id_pesanan,
                    product=order.product,
                    sku=order.sku,
                    product_name=order.product.nama_produk if order.product else 'N/A',
                    quantity=order.jumlah,
                    notes=f"Order dihapus dari batch '{nama_batch_lama}' dengan status '{current_status}'"
                )

            # Unlink dari batch
            orders_to_erase.update(nama_batch=None)

        return JsonResponse({'status': 'success', 'message': f'Semua item dari {id_pesanan_to_erase} berhasil dihapus dari batch dan stok terkunci dikembalikan.'})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'status': 'error', 'message': f'Terjadi kesalahan: {str(e)}'}, status=500)


@login_required
@require_POST
@csrf_exempt
def transfer_order_item(request):
    try:
        id_pesanan_to_transfer = request.POST.get('id_pesanan')
        target_batch_name = request.POST.get('target_batch')

        logging.info(f"[{request.user.username}] Starting transfer_order_item for id_pesanan: {id_pesanan_to_transfer}, target_batch: {target_batch_name}")

        if not id_pesanan_to_transfer or not target_batch_name:
            logging.error(f"[{request.user.username}] Missing parameters: id_pesanan={id_pesanan_to_transfer}, target_batch={target_batch_name}")
            return JsonResponse({'status': 'error', 'message': 'Parameter tidak lengkap.'}, status=400)

        with transaction.atomic():
            # Menggunakan select_for_update untuk mencegah race condition
            orders_to_transfer = Order.objects.select_for_update().filter(id_pesanan=id_pesanan_to_transfer)
            if not orders_to_transfer.exists():
                logging.error(f"[{request.user.username}] Order {id_pesanan_to_transfer} not found.")
                return JsonResponse({'status': 'error', 'message': 'Order tidak ditemukan.'}, status=404)

            source_batch_name = orders_to_transfer.first().nama_batch
            logging.info(f"[{request.user.username}] Source batch: {source_batch_name}, Target batch: {target_batch_name}")

            if source_batch_name == target_batch_name:
                logging.error(f"[{request.user.username}] Source and target batches are the same: {source_batch_name}")
                return JsonResponse({'status': 'error', 'message': 'Batch asal dan tujuan tidak boleh sama.'}, status=400)

            # === VALIDASI STATUS BATCH ASAL ===
            source_batch_obj = None
            if source_batch_name:
                source_batch_obj = BatchList.objects.filter(nama_batch=source_batch_name).first()
                if source_batch_obj and source_batch_obj.status_batch == 'closed':
                    return JsonResponse({
                        'status': 'error', 
                        'message': f"Tidak dapat mentransfer order dari batch '{source_batch_name}' karena batch sudah berstatus closed."
                    }, status=403)
                if not source_batch_obj:
                    logging.warning(f"[{request.user.username}] Source batch object not found for name: {source_batch_name}")


            target_batch, created_target_batch = BatchList.objects.get_or_create(
                nama_batch=target_batch_name,
                defaults={'status_batch': 'open'}
            )
            logging.info(f"[{request.user.username}] Target batch object: {target_batch.nama_batch}, Created: {created_target_batch}")


            for order in orders_to_transfer:
                logging.info(f"[{request.user.username}] Processing order item - ID Pesanan: {order.id_pesanan}, SKU: {order.sku}, Jumlah: {order.jumlah}")
                
                if not order.product:
                    logging.warning(f"[{request.user.username}] Product for order item {order.pk} (SKU: {order.sku}) is None during transfer. Skipping this item.")
                    continue

                # 1. Kurangi jumlah di batch asal (jika ada batch asal)
                if source_batch_obj:
                    try:
                        batchitem_asal = BatchItem.objects.select_for_update().get(batchlist=source_batch_obj, product=order.product)
                        logging.info(f"[{request.user.username}] Found source batch item for SKU {order.sku}: current_jumlah={batchitem_asal.jumlah}, current_jumlah_ambil={batchitem_asal.jumlah_ambil}")
                        
                        batchitem_asal.jumlah -= order.jumlah
                        
                        if batchitem_asal.jumlah <= 0 and batchitem_asal.jumlah_ambil == 0:
                            logging.info(f"[{request.user.username}] Deleting source batch item for SKU {order.sku} as jumlah is 0 and not picked.")
                            batchitem_asal.delete()
                        else:
                            logging.info(f"[{request.user.username}] Updating source batch item for SKU {order.sku}: new_jumlah={batchitem_asal.jumlah}")
                            batchitem_asal.save(update_fields=['jumlah'])
                    except BatchItem.DoesNotExist:
                        logging.info(f"[{request.user.username}] Source BatchItem for SKU {order.sku} in batch {source_batch_name} not found. Skipping reduction.")
                        pass # Item tidak ada di batch asal, tidak perlu dilakukan apa-apa

                # 2. Tambah jumlah di batch tujuan
                batch_item_target, created_target_item = BatchItem.objects.select_for_update().get_or_create(
                    batchlist=target_batch,
                    product=order.product,
                    defaults={
                        'jumlah': order.jumlah,
                        'jumlah_ambil': 0, # Default untuk item baru
                        'jumlah_transfer': 0, # Default untuk item baru
                        'jumlah_terpakai': 0, # Default untuk item baru
                        'status_ambil': 'pending' # Default untuk item baru
                    }
                )
                if not created_target_item:
                    logging.info(f"[{request.user.username}] Found existing target batch item for SKU {order.sku}: current_jumlah={batch_item_target.jumlah}, Adding {order.jumlah}")
                    batch_item_target.jumlah += order.jumlah
                    logging.info(f"[{request.user.username}] New target batch item jumlah for SKU {order.sku}: {batch_item_target.jumlah}")
                    batch_item_target.save(update_fields=['jumlah'])
                else:
                    logging.info(f"[{request.user.username}] Created new target batch item for SKU {order.sku} with jumlah: {order.jumlah}")
                
                # 3. LOGGING: Catat perubahan ke BatchOrderLog
                BatchOrderLog.objects.create(
                    user=request.user,
                    id_pesanan=order.id_pesanan,
                    product=order.product,
                    quantity=order.jumlah,  # Mengubah 'jumlah' menjadi 'quantity'
                    action_type='TRANSFER', # Mengubah 'action' menjadi 'action_type' dengan nilai 'TRANSFER'
                    sku=order.sku, # Menambahkan field sku
                    product_name=order.product.nama_produk if order.product else '', # Menambahkan field product_name
                    batch_source=source_batch_obj,
                    batch_destination=target_batch,
                    notes=f"Item ditransfer dari '{source_batch_name or 'N/A'}' ke '{target_batch_name}'"
                )
                logging.info(f"[{request.user.username}] Logged transfer for order {order.id_pesanan} ({order.sku}) to BatchOrderLog.")

            # 4. Pindahkan semua order item ke batch tujuan
            orders_to_transfer.update(nama_batch=target_batch_name)
            logging.info(f"[{request.user.username}] All orders for {id_pesanan_to_transfer} updated to target batch {target_batch_name}.")


        logging.info(f"[{request.user.username}] Successfully transferred items for {id_pesanan_to_transfer} to {target_batch_name}.")
        return JsonResponse({'status': 'success', 'message': f'Semua item dari {id_pesanan_to_transfer} berhasil ditransfer ke batch {target_batch_name}.'})
    except Exception as e:
        import traceback
        logging.error(f"[{request.user.username}] Error in transfer_order_item: {e}", exc_info=True) # Tambahkan logging
        print(traceback.format_exc()) # Ini akan mencetak ke console server
        return JsonResponse({'status': 'error', 'message': f'Terjadi kesalahan saat transfer: {str(e)}'}, status=500)

@login_required
@require_POST
@csrf_exempt
def transfer_batch_pending(request):
    """
    Transfer order yang "not ready to pick" dari source_batch ke target_batch.
    jumlah_transfer = sisa jumlah_ambil yang belum terpakai (jumlah_ambil - jumlah_terpakai)
    """
    try:
        data = json.loads(request.body)
        source_batch = data.get('source_batch', '').strip()
        target_batch = data.get('target_batch', '').strip()
        transfer_type = data.get('transfer_type', 'existing')  # 'new' atau 'existing'
        
        if not source_batch or not target_batch:
            return JsonResponse({
                'success': False, 
                'error': 'Source batch dan target batch harus diisi'
            })
        
        if source_batch == target_batch:
            return JsonResponse({
                'success': False, 
                'error': 'Source batch dan target batch tidak boleh sama'
            })
        
        with transaction.atomic():
            # A. Ambil batch sumber
            source_batchlist = get_object_or_404(BatchList, nama_batch=source_batch)
            
            # B. Handle target batch berdasarkan transfer_type
            if transfer_type == "new":
                # Buat BatchList baru
                if BatchList.objects.filter(nama_batch__iexact=target_batch).exists():
                    return JsonResponse({
                        'success': False,
                        'error': f'Batch "{target_batch}" sudah ada'
                    })
                target_batchlist = BatchList.objects.create(
                    nama_batch=target_batch,
                    status_batch='open'
                )
            else:  # transfer_type == "existing"
                # Ambil batch existing
                target_batchlist = get_object_or_404(BatchList, nama_batch=target_batch)
                if target_batchlist.status_batch != 'open':
                    return JsonResponse({
                        'success': False,
                        'error': f'Batch tujuan "{target_batch}" harus berstatus open'
                    })
            
            # C. Ambil order yang "not ready to pick" menggunakan fungsi yang sudah ada
            not_ready_ids = get_not_ready_to_pick_ids(source_batchlist)
            
            if not not_ready_ids:
                return JsonResponse({
                    'success': False,
                    'error': 'Tidak ada order "not ready to pick" yang ditemukan di batch sumber'
                })
            
            # D. Ambil semua order yang not ready to pick
            not_ready_orders = Order.objects.filter(
                id_pesanan__in=not_ready_ids,
                nama_batch=source_batch,
                product__isnull=False
            )
            
            transferred_count = 0
            
            # E. Transfer setiap order not ready to pick
            for order in not_ready_orders:
                # Update Order.nama_batch ke batch tujuan
                order.nama_batch = target_batch
                order.save(update_fields=['nama_batch'])
                transferred_count += 1
                
                # F. Handle BatchItem - kurangi dari source, tambah ke target
                source_batchitem = BatchItem.objects.filter(
                    batchlist=source_batchlist,
                    product=order.product
                ).first()
                
                # Hitung sisa yang bisa ditransfer
                source_jumlah_ambil = source_batchitem.jumlah_ambil if source_batchitem else 0
                source_jumlah_terpakai = source_batchitem.jumlah_terpakai if source_batchitem else 0
                jumlah_transfer = max(0, source_jumlah_ambil - source_jumlah_terpakai)
                
                if source_batchitem:
                    # Kurangi jumlah dari BatchItem sumber
                    source_batchitem.jumlah -= order.jumlah
                    if source_batchitem.jumlah <= 0:
                        source_batchitem.delete()
                    else:
                        source_batchitem.save(update_fields=['jumlah'])
                
                # Tambah ke BatchItem target dengan jumlah_transfer = sisa yang belum terpakai
                target_batchitem, created = BatchItem.objects.get_or_create(
                    batchlist=target_batchlist,
                    product=order.product,
                    defaults={
                        'jumlah': order.jumlah,
                        'jumlah_ambil': 0,
                        'jumlah_transfer': jumlah_transfer,  # Sisa jumlah_ambil - jumlah_terpakai
                        'jumlah_terpakai': 0,  # Reset karena batch baru
                        'status_ambil': 'pending'
                    }
                )
                
                if not created:
                    # Jika sudah ada, tambahkan jumlah dan jumlah_transfer
                    target_batchitem.jumlah += order.jumlah
                    target_batchitem.jumlah_transfer += jumlah_transfer
                    target_batchitem.save(update_fields=['jumlah', 'jumlah_transfer'])
                
                # G. Logging
                BatchItemLog.objects.create(
                    waktu=timezone.now(),
                    user=request.user if request.user.is_authenticated else None,
                    batch=target_batchlist,
                    product=order.product,
                    jumlah_input=order.jumlah,
                    jumlah_ambil=0
                )
            
            return JsonResponse({
                'success': True,
                'message': f'Berhasil transfer {transferred_count} order "not ready to pick" dari "{source_batch}" ke "{target_batch}"',
                'transferred_count': transferred_count,
                'target_batch': target_batch
            })
            
    except BatchList.DoesNotExist as e:
        return JsonResponse({
            'success': False,
            'error': f'Batch tidak ditemukan: {str(e)}'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Terjadi kesalahan: {str(e)}'
        })

@login_required
def transfer_summary(request):
    """
    Ambil data summary untuk transfer: order gantung dan stock gantung
    """
    batch_name = request.GET.get('batch_name', '').strip()
    if not batch_name:
        return JsonResponse({'error': 'Batch name required'})
    
    try:
        batchlist = get_object_or_404(BatchList, nama_batch=batch_name)
        
        # Ambil order gantung (not ready to pick)
        not_ready_ids = get_not_ready_to_pick_ids(batchlist)
        pending_orders_count = len(not_ready_ids)
        
        # Ambil stock gantung (unallocated stock)
        # Gunakan logic dari unallocated_stock_list
        picked_quantities = BatchItem.objects.filter(batchlist=batchlist) \
            .values('product_id') \
            .annotate(total_picked=Sum('jumlah_ambil'))
        
        ready_to_print_ids = ReadyToPrint.objects.filter(batchlist=batchlist).values_list('id_pesanan', flat=True)
        
        needed_quantities = Order.objects.filter(nama_batch=batch_name, id_pesanan__in=ready_to_print_ids) \
            .values('product_id') \
            .annotate(total_needed=Sum('jumlah'))
        
        unallocated_stock_count = 0
        for picked in picked_quantities:
            product_id = picked['product_id']
            picked_qty = picked['total_picked']
            needed_qty = next((item['total_needed'] for item in needed_quantities if item['product_id'] == product_id), 0)
            unallocated_qty = picked_qty - needed_qty
            if unallocated_qty > 0:
                unallocated_stock_count += 1
        
        return JsonResponse({
            'pending_orders_count': pending_orders_count,
            'unallocated_stock_count': unallocated_stock_count
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)})

@login_required
def download_batchitem_excel(request, nama_batch):
    """Download batch item dalam format Excel"""
    batch = BatchList.objects.filter(nama_batch=nama_batch).first()
    if not batch:
        return HttpResponse("Batch tidak ditemukan.", status=404)
    
    items = BatchItem.objects.filter(batchlist=batch).select_related('product').order_by('product__brand', '-one_count')

    # Buat workbook Excel
    wb = Workbook()
    ws = wb.active
    ws.title = f"Batch {nama_batch}"

    # Header
    headers = ["No", "SKU", "Barcode", "Nama Produk", "Varian Produk", "Brand", "Rak", "Qty", "Sat"]
    ws.append(headers)

    # Data
    for idx, item in enumerate(items, 1):
        product = item.product
        ws.append([
            idx,
            getattr(product, 'sku', ''),
            getattr(product, 'barcode', ''),
            getattr(product, 'nama_produk', ''),
            getattr(product, 'variant_produk', ''),
            getattr(product, 'brand', ''),
            getattr(product, 'rak', ''),
            item.jumlah,
            item.one_count,
        ])

    # Atur lebar kolom
    column_widths = [5, 20, 15, 50, 20, 15, 10, 10, 10]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[chr(64 + i)].width = width

    # Simpan ke buffer
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    # Response
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="batchitem_{nama_batch}.xlsx"'
    return response

@login_required
def batchitem_table_view(request):
    """View untuk menampilkan data batchitem dalam format tabel per batch"""
    from django.core.paginator import Paginator
    
    nama_batch = request.GET.get('nama_batch')
    if nama_batch:
        queryset = BatchItem.objects.filter(batchlist__nama_batch=nama_batch)
    else:
        queryset = BatchItem.objects.none()  # atau tampilkan pesan "Pilih batch dulu"
    
    # Pagination
    paginator = Paginator(queryset, 50)  # 50 item per halaman
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Siapkan data untuk template
    table_data = []
    for item in page_obj:
        product = item.product
        batchlist = item.batchlist
        
        # Hitung status berdasarkan jumlah dan jumlah_ambil
        if item.jumlah_ambil == 0:
            status_ambil = 'pending'
        elif item.jumlah_ambil > 0 and item.jumlah_ambil < item.jumlah:
            status_ambil = 'partial'
        elif item.jumlah_ambil > item.jumlah:
            status_ambil = 'over_stock'
        elif item.jumlah_ambil == item.jumlah:
            status_ambil = 'completed'
        else:
            status_ambil = item.status_ambil
        
        table_data.append({
            'id': item.id,
            'batch_name': batchlist.nama_batch if batchlist else '',
            'batch_created': batchlist.created_at if batchlist else None,
            'sku': product.sku if product else '',
            'barcode': product.barcode if product else '',
            'nama_produk': product.nama_produk if product else '',
            'variant_produk': product.variant_produk if product else '',
            'brand': product.brand if product else '',
            'rak': product.rak if product else '',
            'jumlah': item.jumlah,
            'jumlah_ambil': item.jumlah_ambil,
            'jumlah_transfer': getattr(item, 'jumlah_transfer', 0),
            'jumlah_terpakai': getattr(item, 'jumlah_terpakai', 0),
            'status_ambil': status_ambil,
            'completed_at': item.completed_at,
            'completed_by': item.completed_by.username if item.completed_by else '',
            'count_one': item.one_count,
            'count_duo': item.duo_count,
            'count_tri': item.tri_count,
        })
    
    context = {
        'page_obj': page_obj,
        'table_data': table_data,
        'total_items': paginator.count,
        'title': f"BatchItem Table - {nama_batch}",
        'nama_batch': nama_batch,
    }
    
    return render(request, 'fullfilment/batchitem_table.html', context)



# mobile_batchpicking_v3 view dihapus karena tidak digunakan

@login_required
@permission_required('fullfilment.change_batchlist', raise_exception=True)
def batch_order_logs_view(request, nama_batch=None):
    queryset = BatchItemLog.objects.all().order_by('-waktu')
    if nama_batch:
        queryset = queryset.filter(batch__nama_batch=nama_batch)

    paginator = Paginator(queryset, 20)  # 20 log per halaman
    page_number = request.GET.get('page')
    logs_page_obj = paginator.get_page(page_number)

    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent

    context = {
        'logs': logs_page_obj,
        'nama_batch': nama_batch,
    }

    if is_mobile:
        template_name = 'fullfilment/batch_order_logs.html'
    else:
        template_name = 'fullfilment/batch_order_logs.html' # Asumsi ini template desktop
    
    return render(request, template_name, context)

@login_required
def mobile_clickpicking_view(request, order_id=None):
    context = {
        'order_id': order_id,
        'show_tables': False,
    }

    if not order_id:
        order_id = request.GET.get('order_id')

    if order_id:
        packing_history = OrderPackingHistory.objects.filter(order__id_pesanan=order_id).select_related('user').first()
        if packing_history:
            context.update({
                'is_already_packed': True,
                'packed_at': packing_history.waktu_pack.strftime('%d %b %Y, %H:%M'),
                'packed_by': packing_history.user.username if packing_history.user else 'N/A',
            })
            
        orders = Order.objects.filter(id_pesanan=order_id).exclude(status_bundle='Y').select_related('product')
        if orders.exists():
            first_order = orders.first()
            status = (first_order.status_order or '').lower()
            if 'batal' in status or 'cancel' in status:
                context['error'] = f"ERROR - Order ini berstatus '{first_order.status_order}' dan tidak bisa diproses."
            elif not status or status == 'pending':
                context['error'] = "ERROR - Order ini belum di Proses Batchpicking 'Printed'"
            elif status == 'picked':
                context['error'] = "Order sudah pernah di `Picked` sekarang lanjut proses `Packed` nya"
            elif status == 'printed':
                def build_rows_for_clickpicking(qs_list):
                    rows = []
                    for o in qs_list:
                        p = o.product
                        if o.jumlah_ambil == o.jumlah and o.jumlah > 0:
                            status_ambil = 'completed'
                        elif o.jumlah_ambil > 0:
                            status_ambil = 'partial'
                        else:
                            status_ambil = 'pending'
                        rows.append({
                            'id': o.id,
                            'sku': o.sku,
                            'barcode': p.barcode if p else '',
                            'nama_produk': p.nama_produk if p else '',
                            'variant_produk': p.variant_produk if p else '',
                            'brand': p.brand if p else '',
                            'jumlah': o.jumlah,
                            'jumlah_ambil': o.jumlah_ambil,
                            'status_ambil': status_ambil,
                            'photo_url': p.photo.url if p and p.photo else ''
                        })
                    return rows
                
                # Order by id (ascending) for "from bottom to top" display
                pending = orders.filter(jumlah_ambil__lt=F('jumlah')).order_by('id')
                completed = orders.filter(jumlah_ambil=F('jumlah'), jumlah__gt=0).order_by('id')
                context.update({
                    'show_tables': True,
                    'order_id': order_id,
                    'pending_orders': build_rows_for_clickpicking(pending),
                    'completed_orders': build_rows_for_clickpicking(completed),
                })
            elif status == 'packed':
                context['error'] = "ERROR - Order ini sudah pernah di 'Packed'"
            elif status == 'shipped':
                context['error'] = "ERROR - Order ini sudah pernah di 'Shipped'"
            else:
                context['error'] = f"ERROR - Status order tidak valid: '{first_order.status_order}'"
        else:
            context['error'] = 'Order ID tidak ditemukan.'
            
    return render(request, 'fullfilment/mobile_clickpicking.html', context)

# mobile_batchpicking_v4 view dihapus karena tidak digunakan


# mobile_batchpicking_api_v4 views dihapus karena tidak digunakan

def get_fulfillment_user_display(fulfillment_data):
    """
    Helper function to format fulfillment user display based on status
    """
    if not fulfillment_data:
        return None
    
    # Parse the fulfillment data (it's a dict with status_order and user__username)
    status_order = fulfillment_data.get('status_order', '')
    username = fulfillment_data.get('user__username', '')
    
    if not username:
        return None
    
    # Map status to prefix
    status_prefix_map = {
        'picked': 'Picker',
        'packed': 'Packer', 
        'shipped': 'Shipper',
        'printed': 'User'
    }
    
    prefix = status_prefix_map.get(status_order, 'User')
    return f"{prefix}: {username}"

@login_required
def order_cancel_log_view(request):
    import re
    from django.db.models import Q, F, Subquery, OuterRef, Window
    from django.db.models.functions import RowNumber
    from orders.models import Order
    from .models import ReturnSourceLog
    
    # Mobile detection
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = re.search(r'mobile|android|iphone', user_agent)
    
    # Subquery to get the status_retur from the Order model for OrderCancelLog
    order_status_retur_subquery = Order.objects.filter(
        id_pesanan=OuterRef('order_id_scanned')
    ).values('status_retur')[:1]
    
    # Subquery to get the return user from ReturnSourceLog
    return_user_subquery = ReturnSourceLog.objects.filter(
        order_id=OuterRef('order_id_scanned')
    ).order_by('-created_at').values('created_by__username')[:1]
    
    # Subquery to get the scanner user from ReturnSourceLog (user yang scan barcode di return session)
    scanner_user_subquery = ReturnSourceLog.objects.filter(
        order_id=OuterRef('order_id_scanned')
    ).order_by('-created_at').values('created_by__username')[:1]
    
    # Subquery to get the latest fulfillment status from Order model
    latest_fulfillment_subquery = Order.objects.filter(
        id_pesanan=OuterRef('order_id_scanned')
    ).order_by('-id').values('status_order')[:1]
    
    # Query untuk Order Cancel Belum Return (By User) - mirip returnlist
    order_cancel_by_user_belum_return = OrderCancelLog.objects.annotate(
        linked_order_status_retur=Subquery(order_status_retur_subquery),
        return_user=Subquery(return_user_subquery),
        scanner_user=Subquery(scanner_user_subquery),
        latest_fulfillment_data=Subquery(latest_fulfillment_subquery)
    ).filter(
        Q(linked_order_status_retur='N') | Q(linked_order_status_retur='') | Q(linked_order_status_retur__isnull=True)
    ).annotate(
        row_num=Window(
            expression=RowNumber(),
            partition_by=[F('order_id_scanned')],
            order_by=[F('scan_time').desc()]
        )
    ).filter(row_num=1).select_related('user').order_by('-scan_time')
    
    # Query untuk Order Cancel Sudah Return (By User)
    order_cancel_by_user_sudah_return = OrderCancelLog.objects.annotate(
        linked_order_status_retur=Subquery(order_status_retur_subquery),
        return_user=Subquery(return_user_subquery),
        scanner_user=Subquery(scanner_user_subquery),
        latest_fulfillment_data=Subquery(latest_fulfillment_subquery)
    ).filter(
        Q(linked_order_status_retur='Y')
    ).annotate(
        row_num=Window(
            expression=RowNumber(),
            partition_by=[F('order_id_scanned')],
            order_by=[F('scan_time').desc()]
        )
    ).filter(row_num=1).select_related('user').order_by('-scan_time')
    
    # Get filter parameter
    filter_type = request.GET.get('filter', 'all')
    
    # Apply filter
    if filter_type == 'belum_return':
        logs = order_cancel_by_user_belum_return
    elif filter_type == 'sudah_return':
        logs = order_cancel_by_user_sudah_return
    else:  # 'all'
        logs = OrderCancelLog.objects.annotate(
            linked_order_status_retur=Subquery(order_status_retur_subquery),
            return_user=Subquery(return_user_subquery),
            scanner_user=Subquery(scanner_user_subquery),
            latest_fulfillment_data=Subquery(latest_fulfillment_subquery)
        ).annotate(
            row_num=Window(
                expression=RowNumber(),
                partition_by=[F('order_id_scanned')],
                order_by=[F('scan_time').desc()]
            )
        ).filter(row_num=1).select_related('user').order_by('-scan_time')
    
    context = {
        'logs': logs,
        'order_cancel_by_user_belum_return': order_cancel_by_user_belum_return,
        'order_cancel_by_user_sudah_return': order_cancel_by_user_sudah_return,
        'filter_type': filter_type,
        'is_mobile': is_mobile,
        'total_belum_return': order_cancel_by_user_belum_return.count(),
        'total_sudah_return': order_cancel_by_user_sudah_return.count(),
        'total_all': logs.count() if filter_type == 'all' else logs.count(),
        'get_fulfillment_user_display': get_fulfillment_user_display
    }
    
    template_name = 'fullfilment/order_cancel_log_mobile.html' if is_mobile else 'fullfilment/order_cancel_log.html'
    return render(request, template_name, context)

@login_required
@require_GET
def order_cancel_log_data_api(request):
    """
    API endpoint untuk mendapatkan data order cancel log dalam format JSON
    """
    try:
        from django.db.models import Q, F, Subquery, OuterRef, Window
        from django.db.models.functions import RowNumber
        from orders.models import Order
        from .models import ReturnSourceLog
        
        # Subquery to get the status_retur from the Order model for OrderCancelLog
        order_status_retur_subquery = Order.objects.filter(
            id_pesanan=OuterRef('order_id_scanned')
        ).values('status_retur')[:1]
        
        # Subquery to get the return user from ReturnSourceLog (user yang melakukan return session)
        return_user_subquery = ReturnSourceLog.objects.filter(
            order_id=OuterRef('order_id_scanned')
        ).order_by('-created_at').values('created_by__username')[:1]
        
        # Subquery to get the scanner user from ReturnSourceLog (user yang scan barcode di return session)
        scanner_user_subquery = ReturnSourceLog.objects.filter(
            order_id=OuterRef('order_id_scanned')
        ).order_by('-created_at').values('created_by__username')[:1]
        
        # Subquery to get the latest fulfillment status from Order model
        latest_fulfillment_subquery = Order.objects.filter(
            id_pesanan=OuterRef('order_id_scanned')
        ).order_by('-id').values('status_order')[:1]
        
        # Get filter parameter
        filter_type = request.GET.get('filter', 'all')
        
        # Apply same logic as desktop view
        if filter_type == 'belum_return':
            logs = OrderCancelLog.objects.annotate(
                linked_order_status_retur=Subquery(order_status_retur_subquery),
                return_user=Subquery(return_user_subquery),
                scanner_user=Subquery(scanner_user_subquery),
                latest_fulfillment_data=Subquery(latest_fulfillment_subquery)
            ).filter(
                Q(linked_order_status_retur='N') | Q(linked_order_status_retur='') | Q(linked_order_status_retur__isnull=True)
            ).annotate(
                row_num=Window(
                    expression=RowNumber(),
                    partition_by=[F('order_id_scanned')],
                    order_by=[F('scan_time').desc()]
                )
            ).filter(row_num=1).select_related('user').order_by('-scan_time')
        elif filter_type == 'sudah_return':
            logs = OrderCancelLog.objects.annotate(
                linked_order_status_retur=Subquery(order_status_retur_subquery),
                return_user=Subquery(return_user_subquery),
                scanner_user=Subquery(scanner_user_subquery),
                latest_fulfillment_data=Subquery(latest_fulfillment_subquery)
            ).filter(
                Q(linked_order_status_retur='Y')
            ).annotate(
                row_num=Window(
                    expression=RowNumber(),
                    partition_by=[F('order_id_scanned')],
                    order_by=[F('scan_time').desc()]
                )
            ).filter(row_num=1).select_related('user').order_by('-scan_time')
        else:  # 'all'
            logs = OrderCancelLog.objects.annotate(
                linked_order_status_retur=Subquery(order_status_retur_subquery),
                return_user=Subquery(return_user_subquery),
                scanner_user=Subquery(scanner_user_subquery),
                latest_fulfillment_data=Subquery(latest_fulfillment_subquery)
            ).annotate(
                row_num=Window(
                    expression=RowNumber(),
                    partition_by=[F('order_id_scanned')],
                    order_by=[F('scan_time').desc()]
                )
            ).filter(row_num=1).select_related('user').order_by('-scan_time')
        
        logs_data = []
        for log in logs:
            # Use linked_order_status_retur if available, otherwise fallback to status_retur
            status_retur = log.linked_order_status_retur if hasattr(log, 'linked_order_status_retur') and log.linked_order_status_retur else log.status_retur
            
            # Format fulfillment user - gunakan user dari OrderCancelLog
            fulfillment_user = log.user.username if log.user else 'N/A'
            
            # Hanya tampilkan return_user jika status_retur = 'Y' (Sudah Return)
            # return_user adalah user yang melakukan return session (dari ReturnSourceLog.created_by)
            return_user_display = '-'
            if status_retur == 'Y' and hasattr(log, 'return_user') and log.return_user:
                return_user_display = log.return_user
            
            # Format scanner user - hanya tampilkan jika ada data dari ReturnSourceLog
            scanner_user_display = None
            if hasattr(log, 'scanner_user') and log.scanner_user:
                scanner_user_display = log.scanner_user
            
            logs_data.append({
                'order_id': log.order_id_scanned,
                'user': log.user.username if log.user else 'N/A',
                'scanner_user': scanner_user_display,
                'return_user': return_user_display,
                'fulfillment_user': fulfillment_user or '-',
                'scan_time': log.scan_time.strftime('%d %b %Y, %H:%M:%S') if log.scan_time else 'N/A',
                'payment_status': log.status_pembayaran_at_scan or '-',
                'fulfillment_status': log.status_fulfillment_at_scan or '-',
                'status_retur': status_retur or 'N'
            })
        
        return JsonResponse({
            'success': True,
            'data': logs_data,
            'total_logs': len(logs_data),
            'filter_type': filter_type
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
@csrf_exempt
@login_required
def clean_batch_orders(request, batch_id):
    """
    Tahap 1: Membersihkan batch dari order yang belum diproses.
    - Melepaskan order dengan status 'pending', 'printed', atau kosong.
    - Menghapus ReadyToPrint yang terkait.
    - Menghitung ulang BatchItem.jumlah.
    - Menghapus BatchItem yang menjadi kosong.
    - Menghitung ulang Stock.quantity_locked.
    """
    batch = get_object_or_404(BatchList, id=batch_id)
    
    try:
        with transaction.atomic():
            # 1. Identifikasi order yang akan dilepas (termasuk status kosong atau NULL)
            orders_to_release_qs = Order.objects.filter(nama_batch=batch.nama_batch).filter(
                Q(status_order__in=['pending', 'printed', '']) | Q(status_order__isnull=True)
            )
            
            id_pesanan_to_release = list(orders_to_release_qs.values_list('id_pesanan', flat=True).distinct())
            products_to_recalculate = defaultdict(int) # product_id: total_jumlah_dilepas
            
            # Kumpulkan berapa jumlah yang harus dikembalikan ke locked_stock per produk
            for order in orders_to_release_qs:
                if order.product_id:
                    products_to_recalculate[order.product_id] += order.jumlah

            # 2. Hapus ReadyToPrint yang terkait dengan order yang dilepas
            if id_pesanan_to_release:
                ReadyToPrint.objects.filter(
                    batchlist=batch, 
                    id_pesanan__in=id_pesanan_to_release
                ).delete()

            # 3. Lepaskan order dengan mengubah nama_batch menjadi None
            released_count = orders_to_release_qs.update(nama_batch=None, status_order='pending')

            # 4. Hitung ulang BatchItem dan Stock
            for product_id, jumlah_dilepas in products_to_recalculate.items():
                batch_item = BatchItem.objects.filter(batchlist=batch, product_id=product_id).first()
                if batch_item:
                    batch_item.jumlah -= jumlah_dilepas
                    
                    if batch_item.jumlah <= 0 and batch_item.jumlah_ambil == 0:
                        batch_item.delete()
                    else:
                        batch_item.jumlah = max(0, batch_item.jumlah) 
                        batch_item.save(update_fields=['jumlah'])
                
                stock = Stock.objects.filter(product_id=product_id).first()
                if stock:
                    stock.quantity_locked = max(0, stock.quantity_locked - jumlah_dilepas)
                    stock.save(update_fields=['quantity_locked'])
            
            if released_count > 0:
                messages.success(request, f"{released_count} baris order berhasil dilepaskan dari batch '{batch.nama_batch}'.")
            else:
                messages.info(request, f"Tidak ada order yang bisa dilepaskan dari batch '{batch.nama_batch}'.")

    except Exception as e:
        messages.error(request, f"Terjadi kesalahan saat membersihkan batch: {e}")

    return redirect('/fullfilment/')

@login_required
@permission_required('fullfilment.view_scanretur', raise_exception=True)
def scanretur_view(request, returnlist_id=None): # Parameter returnlist_id tetap untuk kompatibilitas URL
    # Dapatkan ReturnSession berdasarkan ID atau buat yang baru jika tidak ada ID
    return_session = None
    if returnlist_id:
        return_session = get_object_or_404(ReturnSession, id=returnlist_id) # Diperbarui: ReturnList -> ReturnSession, return_list -> return_session

    if not return_session:
        # Jika tidak ada ReturnSession yang diberikan, redirect ke dashboard untuk membuat yang baru
        messages.info(request, "Pilih Return Session atau buat yang baru untuk memulai proses scan retur.")
        return redirect('returnlist_dashboard')

    # Ambil ReturnItem yang terkait dengan ReturnSession ini
    return_items = ReturnItem.objects.filter(session=return_session).select_related('product') # Diperbarui: ReturnStockItem -> ReturnItem, return_items -> return_items, returnlist -> session

    context = {
        'return_session': return_session, # Diperbarui: return_list -> return_session
        'return_items': return_items,
    }
    return render(request, 'fullfilment/scanretur.html', context)

@login_required
@require_POST
@permission_required('fullfilment.add_returnlist', raise_exception=True)
def create_returnlist(request):
    """
    Membuat ReturnSession baru dari sumber (order cancel atau overstock batch).
    """
    try:
        source_type = request.POST.get('source_type')
        source_value = request.POST.get('source_value')
        notes = request.POST.get('notes', '')

        if not all([source_type, source_value]):
            messages.error(request, "Tipe sumber dan nilai sumber wajib diisi.")
            return redirect('returnlist_dashboard')

        with transaction.atomic():
            # Buat ReturnSession baru
            return_session = ReturnSession.objects.create( # Diperbarui: returnlist -> return_session, ReturnList -> ReturnSession
                kode=f"RTN-{timezone.now().strftime('%Y%m%d%H%M%S')}", # Kode otomatis
                created_by=request.user,
                created_at=timezone.now(),
                status='open',
                notes=notes
            )

            # Tambahkan item awal ke ReturnSession
            if source_type == 'order_cancel':
                orders_to_return = Order.objects.filter(id_pesanan=source_value)
                if not orders_to_return.exists():
                    messages.error(request, f"Order ID {source_value} tidak ditemukan.")
                    return redirect('returnlist_dashboard')
                for order_item in orders_to_return:
                    if order_item.product:
                        ReturnItem.objects.create( # Diperbarui: ReturnStockItem -> ReturnItem
                            session=return_session, # Diperbarui: returnlist -> session
                            product=order_item.product,
                            qty_target=order_item.jumlah, # Diperbarui: qty_return -> qty_target
                            qc_status='pending' # Diperbarui: status -> qc_status
                        )
                    # Update OrderCancelLog status_retur menjadi 'Y'
                    OrderCancelLog.objects.filter(order_id_scanned=source_value).update(status_retur='Y')
                    # Update Order status_retur menjadi 'Y'
                    orders_to_return.update(status_retur='Y')
                message = f"Return Session dari Order ID {source_value} berhasil dibuat."

            elif source_type == 'overstock_batch':
                batch_items_overstock = BatchItem.objects.filter(
                    batchlist__id=source_value,
                    jumlah_ambil__gt=F('jumlah')
                ).select_related('product')

                if not batch_items_overstock.exists():
                    messages.error(request, "Batch tidak memiliki item overstock.")
                    return redirect('returnlist_dashboard')
                for batch_item in batch_items_overstock:
                    overstock_qty = batch_item.jumlah_ambil - batch_item.jumlah
                    if overstock_qty > 0 and batch_item.product:
                        ReturnItem.objects.create( # Diperbarui: ReturnStockItem -> ReturnItem
                            session=return_session, # Diperbarui: returnlist -> session
                            product=batch_item.product,
                            qty_target=overstock_qty, # Diperbarui: qty_return -> qty_target
                            qc_status='pending' # Diperbarui: status -> qc_status
                        )
                message = f"Return Session dari Batch ID {source_value} berhasil dibuat."
            else:
                messages.error(request, "Tipe sumber tidak valid.")
                return redirect('returnlist_dashboard')

            messages.success(request, message)
            return redirect('scanretur_view', returnlist_id=return_session.id) # Diperbarui: returnlist_id -> return_session.id
    except Exception as e:
        messages.error(request, f"Terjadi kesalahan: {str(e)}")
        return redirect('returnlist_dashboard')

@login_required
@permission_required('fullfilment.view_scanretur', raise_exception=True)
def scanretur_view(request, returnlist_id=None): # Parameter returnlist_id tetap untuk kompatibilitas URL
    # Dapatkan ReturnSession berdasarkan ID atau buat yang baru jika tidak ada ID
    return_session = None
    if returnlist_id:
        return_session = get_object_or_404(ReturnSession, id=returnlist_id) # Diperbarui: ReturnList -> ReturnSession, return_list -> return_session

    if not return_session:
        # Jika tidak ada ReturnSession yang diberikan, redirect ke dashboard untuk membuat yang baru
        messages.info(request, "Pilih Return Session atau buat yang baru untuk memulai proses scan retur.")
        return redirect('returnlist_dashboard')

    # Ambil ReturnItem yang terkait dengan ReturnSession ini
    return_items = ReturnItem.objects.filter(session=return_session).select_related('product') # Diperbarui: ReturnStockItem -> ReturnItem, return_items -> return_items, returnlist -> session

    context = {
        'return_session': return_session, # Diperbarui: return_list -> return_session
        'return_items': return_items,
    }
    return render(request, 'fullfilment/scanretur.html', context)

@login_required
@require_GET
def get_batch_order_ids_api(request, nama_batch):
    """
    API untuk mengambil daftar Order ID yang terkait dengan Batch tertentu.
    """
    try:
        # Validasi batch
        batch_obj = get_object_or_404(BatchList, nama_batch=nama_batch)
        
        # Mengambil order_id unik dari model Order yang berelasi dengan nama_batch
        order_ids_qs = Order.objects.filter(
            nama_batch=nama_batch 
        ).values_list('id_pesanan', flat=True).distinct().order_by('id_pesanan')

        # Tidak perlu paginasi atau pencarian di sini jika modal hanya menampilkan semua
        # Jika Anda ingin pencarian dan paginasi di modal, kode ini perlu disesuaikan dengan versi sebelumnya.
        # Untuk kasus "simple", kita hanya ambil semua.
        order_ids_list = list(order_ids_qs)

        return JsonResponse({
            'success': True,
            'order_ids': order_ids_list,
        })

    except BatchList.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Batch tidak ditemukan.'}, status=404)
    except Exception as e:
        logging.exception(f"Error getting order IDs for batch {nama_batch}")
        return JsonResponse({'success': False, 'message': f'Terjadi kesalahan saat memuat Order IDs: {str(e)}'}, status=500)

@login_required
@require_GET
def download_batch_order_ids(request, nama_batch):
    """
    Mengunduh daftar Order ID unik dari batch tertentu sebagai file .txt.
    """
    try:
        batch = get_object_or_404(BatchList, nama_batch=nama_batch)
        
        # Mengambil order_id unik dari model Order yang berelasi dengan nama_batch
        order_ids = Order.objects.filter(
            nama_batch=nama_batch
        ).values_list('id_pesanan', flat=True).distinct().order_by('id_pesanan')

        # Gabungkan semua order_id menjadi satu string dengan setiap ID di baris baru
        content = "\n".join(order_ids)

        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename=\"order_ids_{nama_batch}.txt\"'
        return response

    except BatchList.DoesNotExist:
        messages.error(request, f"Batch '{nama_batch}' tidak ditemukan.")
        return redirect('fullfilment_index') 
    except Exception as e:
        logging.exception(f"Error downloading order IDs for batch {nama_batch}")
        messages.error(request, f"Terjadi kesalahan saat mengunduh Order IDs: {str(e)}")
        return redirect('fullfilment_index')

@login_required
def scan_return_cancelled_order_view(request, nama_batch):
    """
    View untuk menampilkan order yang dibatalkan tapi sudah printed
    dan form untuk scan order_id untuk update status_retur
    """
    # Ambil order dari batch yang sama dengan status bayar 'batal'/'cancel' 
    # DAN status fulfillment 'printed' (sudah printed)
    cancelled_orders = Order.objects.filter(
        nama_batch=nama_batch
    ).filter(
        Q(status__icontains='batal') | Q(status__icontains='cancel')
    ).filter(
        status_order='printed'  # Hanya yang sudah printed
    ).order_by(
        Case(
            When(status_retur='Y', then=Value(2)),
            When(status_retur='N', then=Value(1)),
            default=Value(0),
            output_field=IntegerField()
        ),
        'id_pesanan'
    )

    # Hitung statistik
    total_cancelled = cancelled_orders.count()
    already_returned = cancelled_orders.filter(status_retur='Y').count()
    pending_return = cancelled_orders.filter(status_retur='N').count()

    context = {
        'nama_batch': nama_batch,
        'cancelled_orders': cancelled_orders,
        'total_cancelled': total_cancelled,
        'already_returned': already_returned,
        'pending_return': pending_return,
    }
    
    return render(request, 'fullfilment/scan_return_cancelled_order.html', context)

@login_required
@require_POST
def scan_return_cancelled_order_scan(request, nama_batch):
    """
    API endpoint untuk scan order_id dan update status_retur
    """
    try:
        data = json.loads(request.body)
        scanned_order_id = data.get('order_id', '').strip()
        
        if not scanned_order_id:
            return JsonResponse({
                'success': False,
                'error': 'Order ID tidak boleh kosong'
            })
        
        # Cari order yang sesuai dengan kriteria:
        # 1. Dari nama batch yang sama
        # 2. Status bayar mengandung 'batal' atau 'cancel'
        # 3. status_retur = 'N' (belum di-retur)
        order = Order.objects.filter(
            id_pesanan=scanned_order_id,
            nama_batch=nama_batch
        ).filter(
            Q(status_retur='N') | Q(status_retur__isnull=True) | Q(status_retur='')
        ).filter(
            Q(status__icontains='batal') | Q(status__icontains='cancel')
        ).first()
        
        if not order:
            return JsonResponse({
                'success': False,
                'error': f'Order {scanned_order_id} tidak ditemukan atau tidak memenuhi kriteria (sudah di-return atau bukan order batal)'
            })
        
        # Update status_retur menjadi 'Y'
        order.status_retur = 'Y'
        order.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Order {scanned_order_id} berhasil di-mark sebagai returned',
            'order_id': scanned_order_id,
            'order_status': order.status
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Terjadi kesalahan: {str(e)}'
        })

@login_required
@require_POST
@csrf_exempt
def scan_hapus_order_printed(request, nama_batch):
    """
    API untuk menghapus order yang sudah printed dari batch
    Logic: Status order = 'printed' DAN status tidak mengandung 'cancel'/'batal'
    """
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id', '').strip()
        
        if not order_id:
            return JsonResponse({'success': False, 'error': 'Order ID tidak boleh kosong'}, status=400)
        
        with transaction.atomic():
            # Cari order dalam batch yang sama
            orders_to_erase = Order.objects.filter(
                nama_batch=nama_batch,
                id_pesanan=order_id
            )
            
            if not orders_to_erase.exists():
                return JsonResponse({
                    'success': False, 
                    'error': f'Order {order_id} tidak ditemukan dalam batch {nama_batch}'
                }, status=404)
            
            first_order = orders_to_erase.first()
            
            # Validasi: Status order harus 'printed'
            if first_order.status_order != 'printed':
                return JsonResponse({
                    'success': False,
                    'error': f'Order {order_id} status order bukan "printed" (current: {first_order.status_order})'
                }, status=400)
            
            # Validasi: Status tidak boleh mengandung 'cancel' atau 'batal'
            order_status = (first_order.status or '').lower()
            if 'cancel' in order_status or 'batal' in order_status:
                return JsonResponse({
                    'success': False,
                    'error': f'Order {order_id} status sudah dibatalkan (status: {first_order.status}). Gunakan fitur "Scan Return Cancelled Order" untuk order yang dibatalkan.'
                }, status=400)
            
            # Validasi: Batch tidak boleh closed
            try:
                batch = BatchList.objects.get(nama_batch=nama_batch)
                if batch.status_batch == 'closed':
                    return JsonResponse({
                        'success': False,
                        'error': f'Tidak dapat menghapus order dari batch "{nama_batch}" karena batch sudah berstatus closed'
                    }, status=403)
            except BatchList.DoesNotExist:
                pass
            
            # Proses hapus dari batch (mirip dengan erase_order_from_batch)
            for order in orders_to_erase:
                batchitem = BatchItem.objects.filter(batchlist__nama_batch=nama_batch, product=order.product).first()
                if batchitem:
                    # Hitung sisa locked yang bisa dikembalikan
                    sisa_locked = min(order.jumlah, max(0, batchitem.jumlah - batchitem.jumlah_ambil))
                    batchitem.jumlah -= order.jumlah
                    if batchitem.jumlah <= 0 and (batchitem.jumlah_ambil == 0 or batchitem.jumlah_ambil is None):
                        batchitem.delete()
                    else:
                        batchitem.save(update_fields=['jumlah'])

                    # Kembalikan quantity_locked ke inventory
                    stock = Stock.objects.filter(product=order.product).first()
                    if stock and sisa_locked > 0:
                        stock.quantity_locked = max(0, stock.quantity_locked - sisa_locked)
                        stock.save(update_fields=['quantity_locked'])
                
                # Logging: Catat ke BatchOrderLog
                try:
                    batch_obj = BatchList.objects.get(nama_batch=nama_batch)
                except BatchList.DoesNotExist:
                    batch_obj = None
                
                BatchOrderLog.objects.create(
                    user=request.user,
                    action_type='ERASE',
                    batch_source=batch_obj,
                    id_pesanan=order.id_pesanan,
                    product=order.product,
                    sku=order.sku,
                    product_name=order.product.nama_produk if order.product else 'N/A',
                    quantity=order.jumlah,
                    notes=f"Order printed dihapus dari batch '{nama_batch}' via Scan Hapus Order Printed"
                )

            # Unlink dari batch
            orders_to_erase.update(nama_batch=None)
            
            return JsonResponse({
                'success': True,
                'message': f'Order {order_id} berhasil dihapus dari batch. Semua item telah dihapus dan stok terkunci dikembalikan.'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logging.exception(f"Error in scan_hapus_order_printed: {str(e)}")
        return JsonResponse({'success': False, 'error': f'Terjadi kesalahan: {str(e)}'}, status=500)

 
