from django.shortcuts import render
from django.http import JsonResponse
from .models import Order, OrderImportHistory, Customer, OrdersList
from products.models import Product, ProductsBundling
from django.db.models import Q, Func, Sum, F, Max, Min
import os
import pandas as pd
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_POST, require_GET
from django.http import JsonResponse, HttpResponse
from .excel_header_rules import validate_orders_excel_header
from django.urls import reverse
from django.contrib import messages
from django.db import models
from django.utils.encoding import smart_str
import io
import openpyxl
import traceback
import logging
from fullfilment.utils import get_sku_not_found
from django.core.cache import cache
import uuid
from django.db.models import Count
from django.db import transaction
from django.utils.dateparse import parse_datetime
import datetime
from erp_alfa.decorators import custom_auth_and_permission_required
import json

@login_required
@permission_required('orders.view_order', raise_exception=True)
def index(request):
    # Logika view Anda yang bersih tanpa pemeriksaan otentikasi/izin manual
    qs = Order.objects.filter(
        status__iexact='Lunas'
    ).filter(
        Q(nama_batch__isnull=True) | Q(nama_batch='')
    ).select_related('product').order_by('-id')[:100]  # tampilkan 100 saja
    data = []
    for order in qs:
        # Ambil info produk jika ada
        photo_url = None # Default value
        if order.product:
            nama_produk = order.product.nama_produk or ''
            variant_produk = getattr(order.product, 'variant_produk', '')
            brand = getattr(order.product, 'brand', '')
            product_id = order.product.id
            if order.product.photo:
                photo_url = order.product.photo.url
        else:
            nama_produk = ''
            variant_produk = ''
            brand = ''
            product_id = ''
        sku = getattr(order, 'sku', '') or ''
        data.append([
            order.tanggal_pembuatan,                 # 0
            order.status,                            # 1
            order.jenis_pesanan,                     # 2
            order.channel,                           # 3
            order.nama_toko,                         # 4
            order.id_pesanan,                        # 5
            sku,                                     # 6 (SKU di posisi ke-7)
            nama_produk,                             # 7
            variant_produk,                          # 8
            brand,                                   # 9
            product_id,                              # 10
            order.jumlah,                            # 11
            order.harga_promosi,                     # 12
            order.catatan_pembeli or '',             # 13
            order.kurir,                             # 14
            order.awb_no_tracking,                   # 15
            order.metode_pengiriman,                 # 16
            order.kirim_sebelum,                     # 17
            order.order_type,                        # 18
            order.nama_batch or '',                  # 19
            order.jumlah_ambil,                      # 20
            order.status_ambil or '',                # 21
            order.status_order,                      # 22
            order.status_cancel,                     # 23
            order.status_retur,                      # 24
            order.status_bundle or '',               # 25 (Status Bundle di posisi ke-26)
            photo_url                                # 26 (Photo URL baru ditambahkan)
        ])
    # Hitung valid order sesuai rules
    valid_order = Order.objects.filter(status__iexact='Lunas').filter(Q(nama_batch__isnull=True) | Q(nama_batch='')).values('id_pesanan').distinct().count() or 0

    # Calculate total SKU not found for orders with status 'Lunas' dan nama_batch kosong/null, exclude status_bundle='Y'
    lunas_orders = Order.objects.filter(status__iexact='Lunas').filter(Q(nama_batch__isnull=True) | Q(nama_batch='')).exclude(status_bundle='Y')
    order_skus = set(sku.upper() for sku in lunas_orders.values_list('sku', flat=True) if sku)
    master_skus = set(sku.upper() for sku in Product.objects.values_list('sku', flat=True) if sku)
    sku_not_found_list = sorted(order_skus - master_skus)
    sku_not_found_count = len(sku_not_found_list)

    # BARU: Hitung SKU yang ada di master tapi tidak punya nama produk
    no_name_orders_query = Order.objects.filter(
        status__iexact='Lunas',
        product__isnull=False,  # Pastikan produk sudah terhubung
        product__nama_produk__in=['', None] # Cek jika nama produk kosong atau NULL
    ).filter(
        Q(nama_batch__isnull=True) | Q(nama_batch='')
    ).exclude(
        status_bundle='Y'
    )
    sku_no_name_list = sorted(list(no_name_orders_query.values_list('sku', flat=True).distinct()))
    sku_no_name_count = len(sku_no_name_list)

    # SKU No Product: Order yang belum terhubung ke master product
    orders_no_product = Order.objects.filter(
        status__iexact='Lunas',
        product__isnull=True
    ).exclude(
        status_bundle='Y'
    ).filter(
        Q(nama_batch__isnull=True) | Q(nama_batch='')
    )
    no_product_skus_in_orders = sorted(list(orders_no_product.values_list('sku', flat=True).distinct()))
    no_product_skus_in_orders_count = len(no_product_skus_in_orders)

    return render(request, 'orders/index.html', {
        'data': data,
        'valid_order': valid_order,
        'sku_not_found_count': sku_not_found_count,
        'sku_not_found_list': sku_not_found_list,
        'sku_no_name_count': sku_no_name_count,
        'sku_no_name_list': sku_no_name_list,
        'no_product_skus_in_orders': no_product_skus_in_orders,
        'no_product_skus_in_orders_count': no_product_skus_in_orders_count,
    })

@login_required
@permission_required('orders.view_order', raise_exception=True)
def orders_table_data(request):
    # DataTables server-side processing for Orders
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '')

    # Per-column filters (harus sama urutan & jumlah dg kolom tabel)
    filter_fields = [
        'tanggal_pembuatan', 'status', 'jenis_pesanan', 'channel', 'nama_toko',
        'id_pesanan', 'product__nama_produk', 'product__variant_produk', 'product__brand',
        'jumlah', 'harga_promosi', 'catatan_pembeli', 'kurir',
        'awb_no_tracking', 'metode_pengiriman', 'kirim_sebelum', 'order_type',
        'nama_batch', 'jumlah_ambil', 'status_ambil', 'status_order',
        'status_cancel', 'status_retur',
    ]
    filters = {}
    for idx, field in enumerate(filter_fields):
        value = request.GET.get(f'columns[{idx}][search][value]', '').strip()
        if value:
            if field in ['jumlah', 'jumlah_ambil', 'harga_promosi']:
                try:
                    filters[field] = float(value) if '.' in value else int(value)
                except Exception:
                    continue
            else:
                filters[field + '__icontains'] = value

    qs = Order.objects.select_related('product').all()
    if search_value:
        q = Q()
        for field in filter_fields:
            q |= Q(**{f"{field}__icontains": search_value})
        qs = qs.filter(q)
    for k, v in filters.items():
        qs = qs.filter(**{k: v})

    total_count = Order.objects.count()
    filtered_count = qs.count()
    qs = qs.order_by('-id')[start:start+length]

    data = []
    for order in qs:
        # Ambil nama_produk, variant_produk, brand dari Product berdasarkan SKU
        product_obj = None
        if hasattr(order, 'sku') and order.sku:
            product_obj = Product.objects.filter(sku__iexact=order.sku).first()
        if product_obj:
            nama_produk = product_obj.nama_produk or ''
            variant_produk = getattr(product_obj, 'variant_produk', '')
            brand = getattr(product_obj, 'brand', '')
            product_id = product_obj.id
        else:
            nama_produk = ''
            variant_produk = ''
            brand = ''
            product_id = ''
        sku = getattr(order, 'sku', '') or ''
        data.append([
            order.tanggal_pembuatan,  # 0
            order.status,             # 1
            order.jenis_pesanan,      # 2
            order.channel,            # 3
            order.nama_toko,          # 4
            order.id_pesanan,         # 5
            sku,                      # 6 (SKU ditambahkan di sini)
            nama_produk,              # 7
            variant_produk,           # 8
            brand,                    # 9
            product_id,               # 10 (NEW)
            order.jumlah,             # 11
            order.harga_promosi,      # 12
            order.catatan_pembeli or '', # 13
            order.kurir,              # 14
            order.awb_no_tracking,    # 15
            order.metode_pengiriman,  # 16
            order.kirim_sebelum,      # 17
            order.order_type,         # 18
            order.nama_batch or '',    # 19 (ganti dari order.batchlist)
            order.jumlah_ambil,       # 20
            order.status_ambil or '', # 21
            order.status_order,       # 22
            order.status_cancel,      # 23
            order.status_retur,       # 24
        ])

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_count,
        'recordsFiltered': filtered_count,
        'data': data,
    })

class ToDate(Func):
    """
    Custom database function to convert a char field to a date,
    assuming a specific format. For PostgreSQL's TO_DATE.
    """
    function = 'TO_DATE'
    template = "%(function)s(%(expressions)s, 'DD-MM-YYYY')"


@login_required
@permission_required('orders.view_order', raise_exception=True)
def orderimport_history(request):
    history_records = OrderImportHistory.objects.all().order_by('-import_time')
    return render(request, 'orders/orderimport_history.html', {'history_records': history_records})

@login_required
@permission_required('orders.add_order', raise_exception=True)
def import_orders(request):
    import os
    import pandas as pd
    from django.db import transaction
    import traceback
    try:
        if request.method != 'POST' or 'file' not in request.FILES:
            return JsonResponse({'error': 'Invalid request'}, status=400)
        
        file = request.FILES['file']
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in ['.xls', '.xlsx']:
            return JsonResponse({'error': 'File harus Excel (.xls/.xlsx)'}, status=400)
        file.seek(0)
        df = pd.read_excel(file)
        df = df.loc[:, [c for c in df.columns if c.strip().lower() != 'no.']]
        header_map = {
            'Tanggal Pembuatan': 'tanggal_pembuatan',
            'Status': 'status',
            'Jenis Pesanan': 'jenis_pesanan',
            'Channel': 'channel',
            'Nama Toko': 'nama_toko',
            'ID Pesanan': 'id_pesanan',
            'SKU': 'sku',
            'Jumlah': 'jumlah',
            'Harga Promosi': 'harga_promosi',
            'Catatan Pembeli': 'catatan_pembeli',
            'Kurir': 'kurir',
            'AWB/No. Tracking': 'awb_no_tracking',
            'Metode Pengiriman': 'metode_pengiriman',
            'Kirim Sebelum': 'kirim_sebelum',
        }
        def normalize_header(h):
            return h.strip().replace('.', '').replace('/', '').replace('-', '').replace('_', '').replace('  ', ' ').lower()
        norm_header_map = {normalize_header(k): v for k, v in header_map.items()}
        df.rename(columns=lambda c: norm_header_map.get(normalize_header(c), c), inplace=True)
        # NORMALIZE id_pesanan and sku for deduplication and DB query
        df['id_pesanan'] = df['id_pesanan'].astype(str).str.strip()  # Hanya strip, tidak lower
        df['sku'] = df['sku'].astype(str).str.strip().str.upper()  # SKU tetap upper agar konsisten
        grouped = df.groupby(['id_pesanan', 'sku'], as_index=False).agg({**{col: 'first' for col in df.columns if col not in ['id_pesanan', 'sku', 'jumlah']}, 'jumlah': 'sum'})
        updated, created, skipped = 0, 0, 0
        failed_notes = []
        orders_to_create = []
        # --- OPTIMIZED BULK UPDATE & CREATE LOGIC ---
        # 1. Kumpulkan semua kombinasi id_pesanan+sku dari data import
        update_map = {}
        for _, row in grouped.iterrows():
            id_pesanan = row['id_pesanan']
            sku = row['sku']
            status = row['status'] if 'status' in row else ''
            update_map[(id_pesanan, sku)] = status
        # 2. Ambil semua order yang sudah ada di DB untuk kombinasi tsb (PASTIKAN NORMALISASI SAMA)
        q_objs = [Q(id_pesanan=idp, sku=sku) for (idp, sku) in update_map.keys()]
        if q_objs:
            query = q_objs.pop()
            for q in q_objs:
                query |= q
            existing_orders = Order.objects.filter(query)
        else:
            existing_orders = Order.objects.none()
        # 3. Siapkan list untuk bulk_update
        orders_to_update = []
        existing_keys = set((order.id_pesanan, order.sku) for order in existing_orders)
        # 4. Query semua SKU unik dari grouped, ambil product sekaligus
        sku_set = set(grouped['sku'])
        products_map = {p.sku.upper(): p for p in Product.objects.filter(sku__in=sku_set)}
        # 5. Loop sekali saja untuk create & update
        for _, row in grouped.iterrows():
            id_pesanan = row['id_pesanan']
            sku = row['sku']
            key = (id_pesanan, sku)
            product_obj = products_map.get(sku.upper())
            # --- update ---
            if key in existing_keys:
                order = next((o for o in existing_orders if o.id_pesanan == id_pesanan and o.sku == sku), None)
                if order:
                    new_status = row['status'] if 'status' in row else ''
                    if new_status and order.status != new_status:
                        order.status = new_status
                        orders_to_update.append(order)
                        updated += 1
                    else:
                        skipped += 1
                continue
            # --- create ---
            same_id = grouped[grouped['id_pesanan'] == id_pesanan]
            try:
                if len(same_id) == 1:
                    if row['jumlah'] == 1:
                        order_type = '1'
                    else:
                        order_type = '2'
                else:
                    brands = set()
                    for _, r in same_id.iterrows():
                        sku_lookup = str(r['sku']).strip().upper()
                        prod = products_map.get(sku_lookup)
                        if prod and prod.brand:
                            brands.add(prod.brand.strip().upper())
                        else:
                            brands.add('')
                    if len(brands) == 1 and list(brands)[0] != '':
                        order_type = '4'
                    else:
                        order_type = '3'
            except Exception as e:
                failed_notes.append(f"Error determining order_type for {id_pesanan}: {str(e)}")
                order_type = '3'
            def safe_str(val, default=''):
                return str(val).strip() if pd.notna(val) and str(val).strip() else default
            def safe_int(val, default=0):
                try:
                    return int(val) if pd.notna(val) and str(val).strip() else default
                except Exception:
                    return default
            def safe_float(val, default=0.0):
                try:
                    return float(val) if pd.notna(val) and str(val).strip() else default
                except Exception:
                    return default
            order_kwargs = {
                'tanggal_pembuatan': safe_str(row.get('tanggal_pembuatan')),
                'status': safe_str(row.get('status')),
                'jenis_pesanan': safe_str(row.get('jenis_pesanan')),
                'channel': safe_str(row.get('channel')),
                'nama_toko': safe_str(row.get('nama_toko')),
                'id_pesanan': safe_str(id_pesanan),
                'sku': safe_str(sku),
                'jumlah': safe_int(row.get('jumlah'), 0),
                'harga_promosi': safe_float(row.get('harga_promosi'), 0.0),
                'catatan_pembeli': row.get('catatan_pembeli') if pd.notna(row.get('catatan_pembeli')) else '',
                'kurir': safe_str(row.get('kurir')),
                'awb_no_tracking': safe_str(row.get('awb_no_tracking'), ''),
                'metode_pengiriman': safe_str(row.get('metode_pengiriman')),
                'kirim_sebelum': safe_str(row.get('kirim_sebelum')),
                'order_type': order_type,
                'status_order': safe_str(row.get('status_order'), 'pending'),
                'status_cancel': safe_str(row.get('status_cancel'), 'N'),
                'status_retur': safe_str(row.get('status_retur'), 'N'),
                'jumlah_ambil': safe_int(row.get('jumlah_ambil'), 0),
            }
            from django.forms.models import model_to_dict
            order_fields = [f.name for f in Order._meta.get_fields() if f.concrete and not f.auto_created and f.name != 'id']
            for f in order_fields:
                if f not in order_kwargs:
                    if f in ['jumlah', 'jumlah_ambil']:
                        order_kwargs[f] = 0
                    elif f == 'harga_promosi':
                        order_kwargs[f] = 0.0
                    elif f == 'nama_batch':
                        order_kwargs[f] = ''
                    elif f == 'import_history' or f == 'product':
                        order_kwargs[f] = None
                    else:
                        order_kwargs[f] = ''
            if product_obj:
                order_kwargs['product'] = product_obj
            try:
                if not order_kwargs['id_pesanan'] or not order_kwargs['sku'] or order_kwargs['jumlah'] is None:
                    if not order_kwargs['sku']:
                        failed_notes.append(f"Row {id_pesanan}/(SKU kosong) dilewati: SKU wajib diisi.")
                    else:
                        failed_notes.append(f"Row {id_pesanan}/{sku} dilewati: id_pesanan, sku, dan jumlah wajib diisi.")
                    continue
                if 'jumlah_ambil' not in order_kwargs or order_kwargs['jumlah_ambil'] is None:
                    order_kwargs['jumlah_ambil'] = 0
                orders_to_create.append(Order(**order_kwargs))
            except Exception as e:
                failed_notes.append(f"Row {id_pesanan}/{sku} failed: {str(e)}")
        # --- BULK UPDATE ---
        if orders_to_update:
            Order.objects.bulk_update(orders_to_update, ['status'])
        # --- BULK CREATE SEKALI SAJA ---
        if orders_to_create:
            try:
                Order.objects.bulk_create(orders_to_create, batch_size=2000)
                created += len(orders_to_create)
            except Exception as e:
                failed_notes.append(f"Bulk create error: {str(e)}")
        # --- Import history ---
        summary = f"Created: {created}, Updated: {updated}, Skipped: {skipped}, Failed: {len(failed_notes)}"
        
        # Gabungkan ringkasan dengan detail error jika ada
        notes_for_history = summary
        if failed_notes:
            notes_for_history += "\nDetails: " + '; '.join(failed_notes)

        import_history = OrderImportHistory.objects.create(
            file_name=file.name,
            notes=notes_for_history,
            imported_by=request.user if request.user.is_authenticated else None
        )
        
        # Update import_history pada order yang baru dibuat
        if created > 0:
            # Update berdasarkan kombinasi unik id_pesanan dan sku dari data yang diimport
            update_q = Q()
            for _, row in grouped.iterrows():
                update_q |= Q(id_pesanan=row['id_pesanan'], sku=row['sku'])
            if update_q:
                Order.objects.filter(import_history__isnull=True).filter(update_q).update(import_history=import_history)
        # Kumpulkan info SKU not found
        sku_not_found_list = []
        for note in failed_notes:
            if note.startswith("SKU ") and "is not in table products" in note:
                sku = note.split()[1]
                sku_not_found_list.append(sku)
        sku_not_found_count = len(sku_not_found_list)
        task_id = request.POST.get('task_id') or str(uuid.uuid4())
        return JsonResponse({
            'created': created,
            'updated': updated,
            'skipped': skipped,
            'sku_not_found_count': sku_not_found_count,
            'sku_not_found_list': sku_not_found_list,
            'failed_notes': failed_notes,
            'status': 'Import selesai',
            'success': True,
            'task_id': task_id
        })
    except Exception as e:
        tb = traceback.format_exc()
        return JsonResponse({'error': str(e), 'traceback': tb}, status=500)

@login_required
@permission_required('orders.view_order', raise_exception=True)
def unique_order_filters(request):
    status = list(Order.objects.values_list('status', flat=True).distinct())
    jenis_pesanan = list(Order.objects.values_list('jenis_pesanan', flat=True).distinct())
    order_type = list(Order.objects.values_list('order_type', flat=True).distinct())
    return JsonResponse({
        'status': [s for s in status if s],
        'jenis_pesanan': [j for j in jenis_pesanan if j],
        'order_type': [o for o in order_type if o],
    })

# Simulasi status import (untuk demo, ganti dengan logic real sesuai kebutuhan)
import_status = {'status': 'done', 'progress': 1.0}

@login_required
@permission_required('orders.view_order', raise_exception=True)
def import_status_view(request):
    # Ganti dengan logic real: cek status import dari database, cache, atau file
    # Contoh: return JsonResponse({'status': 'processing', 'progress': 0.5})
    return JsonResponse(import_status)

@csrf_exempt
@login_required
@permission_required('orders.view_order', raise_exception=True)
def orders_datatable(request):
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 2000))  # AG Grid fetches all rows by default
    search_value = request.GET.get('search[value]', '')

    filter_fields = [
        'tanggal_pembuatan', 'status', 'jenis_pesanan', 'channel', 'nama_toko',
        'id_pesanan', 'product__nama_produk', 'product__variant_produk', 'product__brand',
        'jumlah', 'harga_promosi', 'catatan_pembeli', 'kurir',
        'awb_no_tracking', 'metode_pengiriman', 'kirim_sebelum', 'order_type',
        'nama_batch', 'jumlah_ambil', 'status_ambil', 'status_order',
        'status_cancel', 'status_retur',
    ]
    filters = {}
    for idx, field in enumerate(filter_fields):
        value = request.GET.get(f'columns[{idx}][search][value]', '').strip()
        if value:
            if field in ['jumlah', 'jumlah_ambil', 'harga_promosi']:
                try:
                    filters[field] = float(value) if '.' in value else int(value)
                except Exception:
                    continue
            else:
                filters[field + '__icontains'] = value

    qs = Order.objects.select_related('product').all()
    if search_value:
        q = Q()
        for field in filter_fields:
            q |= Q(**{f"{field}__icontains": search_value})
        qs = qs.filter(q)
    for k, v in filters.items():
        qs = qs.filter(**{k: v})

    total_count = Order.objects.count()
    filtered_count = qs.count()
    qs = qs.order_by('-id')[start:start+length]

    data = []
    for order in qs:
        # Ambil nama_produk, variant_produk, brand dari Product berdasarkan SKU
        product_obj = None
        if hasattr(order, 'sku') and order.sku:
            product_obj = Product.objects.filter(sku__iexact=order.sku).first()
        if product_obj:
            nama_produk = product_obj.nama_produk or ''
            variant_produk = getattr(product_obj, 'variant_produk', '')
            brand = getattr(product_obj, 'brand', '')
            product_id = product_obj.id
        else:
            nama_produk = ''
            variant_produk = ''
            brand = ''
            product_id = ''
        sku = getattr(order, 'sku', '') or ''
        data.append([
            order.tanggal_pembuatan,  # 0
            order.status,             # 1
            order.jenis_pesanan,      # 2
            order.channel,            # 3
            order.nama_toko,          # 4
            order.id_pesanan,         # 5
            sku,                      # 6 (SKU ditambahkan di sini)
            nama_produk,              # 7
            variant_produk,           # 8
            brand,                    # 9
            product_id,               # 10 (NEW)
            order.jumlah,             # 11
            order.harga_promosi,      # 12
            order.catatan_pembeli or '', # 13
            order.kurir,              # 14
            order.awb_no_tracking,    # 15
            order.metode_pengiriman,  # 16
            order.kirim_sebelum,      # 17
            order.order_type,         # 18
            order.nama_batch or '',    # 19 (ganti dari order.batchlist)
            order.jumlah_ambil,       # 20
            order.status_ambil or '', # 21
            order.status_order,       # 22
            order.status_cancel,      # 23
            order.status_retur,       # 24
        ])

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_count,
        'recordsFiltered': filtered_count,
        'data': data,
    })

@csrf_exempt
@login_required
@permission_required('orders.add_order', raise_exception=True)
def add_order(request):
    if request.method == 'POST':
        # Ambil data dari POST request
        id_pesanan = request.POST.get('id_pesanan')
        tanggal_pembuatan_str = request.POST.get('tanggal_pembuatan')
        nama_customer = request.POST.get('nama_customer')
        keterangan = request.POST.get('keterangan')

        # Convert tanggal
        try:
            # Format: dd-mm-yyyy hh:mm
            tanggal_pembuatan = datetime.datetime.strptime(tanggal_pembuatan_str, '%d-%m-%Y %H:%M')
        except (ValueError, TypeError):
            messages.error(request, 'Format tanggal pembuatan tidak valid.')
            return redirect('add_order')

        with transaction.atomic():
            # 1. Dapatkan atau buat Customer
            customer, created = Customer.objects.get_or_create(
                nama_customer=nama_customer
            )

            # 2. Buat entri di OrdersList
            try:
                order_list = OrdersList.objects.create(
                    id_pesanan=id_pesanan,
                    customer=customer,
                    tanggal_pembuatan=tanggal_pembuatan,
                    keterangan=keterangan,
                )
            except Exception as e:
                messages.error(request, f"Gagal menyimpan order list: {e}")
                transaction.set_rollback(True)
                return redirect('add_order')

            # 3. Proses setiap item produk dari form
            skus = request.POST.getlist('produk_sku[]')
            jumlahs = request.POST.getlist('produk_qty[]')
            hargas = request.POST.getlist('produk_harga[]')

            if not skus:
                messages.error(request, "Tidak ada produk yang ditambahkan.")
                transaction.set_rollback(True)
                return redirect('add_order')

            # Hitung order_type berdasarkan karakteristik order
            order_type = calculate_order_type(skus, jumlahs)

            for i in range(len(skus)):
                sku = skus[i]
                try:
                    jumlah = int(jumlahs[i])
                    harga = float(hargas[i])
                except (ValueError, IndexError):
                    messages.error(request, f"Data jumlah atau harga tidak valid untuk SKU {sku}.")
                    transaction.set_rollback(True)
                    return redirect('add_order')

                # Cari produk berdasarkan SKU
                product = Product.objects.filter(sku=sku).first()
                if not product:
                    messages.error(request, f'Produk dengan SKU {sku} tidak ditemukan.')
                    transaction.set_rollback(True)
                    return redirect('add_order')

                # Buat entri di Order (tabel detail) dengan order_type
                Order.objects.create(
                    id_pesanan=id_pesanan,
                    tanggal_pembuatan=tanggal_pembuatan_str,
                    sku=sku,
                    product=product,
                    jumlah=jumlah,
                    harga_promosi=harga,
                    catatan_pembeli=keterangan,
                    status='Lunas',
                    order_type=order_type,  # Tambahkan order_type yang sudah dihitung
                    jenis_pesanan='manual',
                    channel='manual'
                )

        messages.success(request, f'Order {id_pesanan} berhasil dibuat dengan order_type: {order_type}.')
        return redirect('orders_list') # Redirect ke daftar order

    else:
        # Menampilkan form tambah order
        return render(request, 'orders/addorder.html')

def calculate_order_type(skus, jumlahs):
    """
    Menghitung order_type berdasarkan karakteristik order:
    - '1' = SAT (Single Article Type) - hanya 1 SKU dengan jumlah 1
    - '2' = PRIO (Priority) - multiple SKU atau jumlah > 1
    - '3' = REGULAR - order biasa
    - '4' = MIX - multiple SKU dengan berbagai brand
    """
    if not skus or not jumlahs:
        return '3'  # Default ke REGULAR
    
    # Hitung jumlah SKU unik
    unique_skus = len(set(skus))
    
    # Hitung total jumlah
    total_qty = sum(int(qty) for qty in jumlahs if qty)
    
    # Ambil data produk untuk analisis brand
    products = Product.objects.filter(sku__in=skus)
    unique_brands = len(set(p.brand for p in products if p.brand))
    
    # Logika penentuan order_type
    if unique_skus == 1 and total_qty == 1:
        return '1'  # SAT - Single Article Type
    elif unique_skus > 1 and unique_brands > 1:
        return '4'  # MIX - Multiple brands
    elif unique_skus > 1 or total_qty > 1:
        return '2'  # PRIO - Priority
    else:
        return '3'  # REGULAR - Default

@require_GET
def search_customer(request):
    q = request.GET.get('q', '').strip()
    qs = Customer.objects.all()
    if q:
        qs = qs.filter(nama_customer__icontains=q)
    data = [
        {
            'id': c.id,
            'nama_customer': c.nama_customer,
            'alamat_cust': c.alamat_cust,
            'kota': c.kota,
            'kode_pos': c.kode_pos,
            'level': c.level,
        } for c in qs[:20]
    ]
    return JsonResponse(data, safe=False)

@csrf_exempt
@login_required
def add_customer(request):
    if request.method == 'POST':
        nama = request.POST.get('nama_customer', '').strip()
        if not nama:
            return JsonResponse({'error': 'Nama customer wajib diisi!'}, status=400)
        cust = Customer.objects.create(
            nama_customer=nama,
            alamat_cust=request.POST.get('alamat_cust', ''),
            kota=request.POST.get('kota', ''),
            kode_pos=request.POST.get('kode_pos', ''),
            level=request.POST.get('level', 'normal'),
        )
        return JsonResponse({'id': cust.id, 'nama_customer': cust.nama_customer})
    return JsonResponse({'error': 'Invalid method'}, status=405)

def orders_list(request):
    order_lists = OrdersList.objects.select_related('customer').order_by('-created_at')
    data_for_template = []
    for o in order_lists:
        total_item = Order.objects.filter(id_pesanan=o.id_pesanan).count()
        data_for_template.append({
            'pk': o.pk,
            'id_pesanan': o.id_pesanan,
            'tanggal_pembuatan': o.tanggal_pembuatan,
            'nama_customer': o.customer.nama_customer if o.customer else 'N/A',
            'keterangan': o.keterangan,
            'total_item': total_item,
        })
    return render(request, 'orders/orders_list.html', {'orders': data_for_template})

@login_required
@permission_required('orders.view_order', raise_exception=True)
def orders_listdetail(request, id_pesanan):
    # Ambil info utama order dari OrdersList
    order = get_object_or_404(OrdersList, id_pesanan=id_pesanan)
    
    # Ambil semua item detail untuk order ini
    detail_items = Order.objects.filter(id_pesanan=id_pesanan).select_related('product', 'product__stock')
    
    # Hitung total item
    total_item = detail_items.aggregate(total=Sum('jumlah'))['total'] or 0
    
    # Ambil nama_batch dari item pertama (jika ada) untuk dikirim ke template
    nama_batch = detail_items.first().nama_batch if detail_items.exists() else None

    context = {
        'order': order,
        'detail_items': detail_items,
        'total_item': total_item,
        'nama_batch': nama_batch, # Kirim nama_batch ke template
    }
    return render(request, 'orders/orders_listdetail.html', context)

def orders_listedit(request, id_pesanan):
    from .models import OrdersList, Order, Customer
    from products.models import Product
    from django.utils.dateparse import parse_datetime
    from django.contrib import messages
    from django.shortcuts import redirect, render, get_object_or_404
    import datetime

    orderlist = get_object_or_404(OrdersList, id_pesanan=id_pesanan)
    
    if request.method == 'POST':
        # --- PROSES UPDATE DATA ---
        keterangan = request.POST.get('keterangan')
        produk_sku = request.POST.getlist('produk_sku[]')
        produk_qty = request.POST.getlist('produk_qty[]')
        produk_harga = request.POST.getlist('produk_harga[]')

        with transaction.atomic():
            Order.objects.filter(id_pesanan=id_pesanan).delete()

            # Hitung order_type berdasarkan data yang baru
            order_type = calculate_order_type(produk_sku, produk_qty)

            total_harga_baru = 0
            total_produk_baru = 0
            
            for i, sku in enumerate(produk_sku):
                qty = int(produk_qty[i]) if i < len(produk_qty) else 1
                harga = float(produk_harga[i]) if i < len(produk_harga) else 0
                product_obj = Product.objects.filter(sku=sku).first()
                
                Order.objects.create(
                    id_pesanan=id_pesanan,
                    sku=sku,
                    jumlah=qty,
                    harga_promosi=harga,
                    product=product_obj,
                    tanggal_pembuatan=orderlist.tanggal_pembuatan.strftime('%d-%m-%Y %H:%M'),
                    status='Lunas',
                    jenis_pesanan='manual',
                    channel='manual',
                    order_type=order_type  # Tambahkan order_type yang sudah dihitung
                )
                total_harga_baru += harga * qty
                total_produk_baru += qty

            orderlist.keterangan = keterangan
            orderlist.total_harga = total_harga_baru
            orderlist.total_produk = total_produk_baru
            orderlist.save()

        messages.success(request, f"Order {id_pesanan} berhasil diupdate dengan order_type: {order_type}.")
        return redirect('orders_list')

    # --- PERSIAPAN DATA UNTUK FORM EDIT (METHOD GET) ---
    detail_qs = Order.objects.filter(id_pesanan=id_pesanan).select_related('product')
    
    detail_items = []
    for d in detail_qs:
        stok_info = 0
        if d.product and hasattr(d.product, 'stock') and d.product.stock is not None:
            stok_info = d.product.stock.quantity_ready_virtual

        detail_items.append({
            'sku': d.sku,
            'barcode': getattr(d.product, 'barcode', ''),
            'nama_produk': getattr(d.product, 'nama_produk', ''),
            'variant': getattr(d.product, 'variant_produk', ''),
            'brand': getattr(d.product, 'brand', ''),
            'stok': stok_info,
            'jumlah': d.jumlah,
            'harga': d.harga_promosi,
        })
        
    context = {
        'order': orderlist,
        'detail_items': detail_items,
        'edit_mode': True,
    }
    # Render template 'addorder.html' dengan data yang ada
    return render(request, 'orders/addorder.html', context)

@login_required
@require_GET
def download_orders(request):
    # Pilihan limit: 1000, 5000, 10000 (default 1000, max 10000)
    try:
        limit = int(request.GET.get('limit', 1000))
    except Exception:
        limit = 1000
    if limit not in [1000, 5000, 10000]:
        limit = 1000
    # Ambil data terbaru
    orders = Order.objects.select_related('product').order_by('-id')[:limit]
    # Siapkan workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Orders'
    # Header
    headers = [
        'Tanggal Pembuatan', 'Status', 'Jenis Pesanan', 'Channel', 'Nama Toko',
        'ID Pesanan', 'SKU', 'Nama Produk', 'Variant Produk', 'Brand', 'Product ID',
        'Jumlah', 'Harga Promosi', 'Catatan Pembeli', 'Kurir', 'AWB/No. Tracking',
        'Metode Pengiriman', 'Kirim Sebelum', 'Order Type', 'Nama Batch', 'Jumlah Ambil',
        'Status Ambil', 'Status Order', 'Status Cancel', 'Status Retur',
    ]
    ws.append(headers)
    for order in orders:
        product = order.product if hasattr(order, 'product') else None
        ws.append([
            smart_str(order.tanggal_pembuatan),
            smart_str(order.status),
            smart_str(order.jenis_pesanan),
            smart_str(order.channel),
            smart_str(order.nama_toko),
            smart_str(order.id_pesanan),
            smart_str(order.sku),
            smart_str(product.nama_produk) if product else '',
            smart_str(getattr(product, 'variant_produk', '')) if product else '',
            smart_str(getattr(product, 'brand', '')) if product else '',
            product.id if product else '',
            order.jumlah,
            order.harga_promosi,
            smart_str(order.catatan_pembeli or ''),
            smart_str(order.kurir),
            smart_str(order.awb_no_tracking),
            smart_str(order.metode_pengiriman),
            smart_str(order.kirim_sebelum),
            smart_str(order.order_type),
            smart_str(order.nama_batch or ''),
            order.jumlah_ambil,
            smart_str(order.status_ambil or ''),
            smart_str(order.status_order),
            smart_str(order.status_cancel),
            smart_str(order.status_retur),
        ])
    # Simpan ke buffer
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"orders_latest_{limit}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    return response

@login_required
@permission_required('orders.delete_order', raise_exception=True)
def orders_delete(request, pk):
    # Dapatkan objek yang ingin dihapus, atau tampilkan 404 jika tidak ada
    order_to_delete = get_object_or_404(OrdersList, pk=pk)

    if request.method == 'POST':
        # Logika penghapusan hanya berjalan saat form di-submit
        id_pesanan_to_check = order_to_delete.id_pesanan

        # Cek apakah ada order terkait yang sudah masuk batch
        orders_in_batch = Order.objects.filter(
            id_pesanan=id_pesanan_to_check,
            nama_batch__isnull=False
        ).exclude(nama_batch='')

        if orders_in_batch.exists():
            # Ambil nama batch dari order pertama yang ditemukan
            batch_name = orders_in_batch.first().nama_batch
            # Jika sudah di-batch, tampilkan error dengan nama batch-nya
            messages.error(request, f"Order {id_pesanan_to_check} tidak bisa dihapus karena sudah masuk ke batch '{batch_name}'.")
            return redirect('orders_list')
        
        # Jika aman, lanjutkan penghapusan
        # Hapus dulu semua order detail
        Order.objects.filter(id_pesanan=id_pesanan_to_check).delete()
        # Hapus order list utama
        order_to_delete.delete()

        messages.success(request, f"Order {id_pesanan_to_check} berhasil dihapus.")
        return redirect('orders_list')

    # Jika method adalah GET, tampilkan halaman konfirmasi
    context = {
        'order': order_to_delete
    }
    return render(request, 'orders/orderlist_delete.html', context)

@login_required
@permission_required('orders.view_order', raise_exception=True)
def orders_detail(request, id_pesanan):
    """
    Detail order berdasarkan id_pesanan dari tabel Order (bukan OrdersList)
    """
    # Ambil semua order dengan id_pesanan yang sama
    orders = Order.objects.filter(id_pesanan=id_pesanan).select_related('product')
    
    if not orders.exists():
        messages.error(request, 'Order tidak ditemukan!')
        return redirect('orders-index')
    
    # Ambil info utama dari order pertama
    first_order = orders.first()
    
    # Siapkan detail items
    detail_items = []
    total_jumlah = 0
    
    for order in orders:
        # Ambil info produk jika ada
        if order.product:
            nama_produk = order.product.nama_produk or ''
            variant_produk = order.product.variant_produk or ''
            brand = order.product.brand or ''
            barcode = order.product.barcode or ''
            # Cek stok jika ada product
            stok = order.product.stock.quantity if hasattr(order.product, 'stock') and order.product.stock else 0
        else:
            nama_produk = ''
            variant_produk = ''
            brand = ''
            barcode = ''
            stok = 0
        
        detail_items.append({
            'sku': order.sku,
            'barcode': barcode,
            'nama_produk': nama_produk,
            'variant_produk': variant_produk,
            'brand': brand,
            'stok': stok,
            'jumlah': order.jumlah,
            'harga_promosi': order.harga_promosi or 0,
            'status_order': order.status_order,
            'nama_batch': order.nama_batch or '-',
            'jumlah_ambil': order.jumlah_ambil,
            'status_ambil': order.status_ambil or '-',
        })
        total_jumlah += order.jumlah
    
    context = {
        'id_pesanan': first_order.id_pesanan,
        'tanggal_pembuatan': first_order.tanggal_pembuatan,
        'status': first_order.status,
        'channel': first_order.channel,
        'nama_toko': first_order.nama_toko,
        'order_type': first_order.order_type,
        'status_order': first_order.status_order,
        'kurir': first_order.kurir,
        'metode_pengiriman': first_order.metode_pengiriman,
        'total_item': total_jumlah,
        'detail_items': detail_items,
    }
    
    return render(request, 'orders/orders_detail.html', context)

@login_required
@permission_required('orders.view_order', raise_exception=True)
def all_orders_view(request):
    """
    Menampilkan halaman tabel semua order.
    Kolom didefinisikan secara statis di template.
    """
    return render(request, 'orders/allorders.html')

@login_required
@permission_required('orders.view_order', raise_exception=True)
def all_orders_data(request):
    """
    Menyediakan data untuk DataTables. Dikelompokkan per id_pesanan.
    Default sort diubah menjadi berdasarkan ID internal terbaru, bukan alfabetis.
    """
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    
    # --- Logika Filter per Kolom ---
    queryset = Order.objects.all()
    # Menyesuaikan column_map_filter dengan kolom baru di frontend
    column_map_filter = [None, 'id_pesanan', 'tanggal_pembuatan', 'status', 'status_order', 'status_cancel', 'status_retur', 'status_bundle', 'nama_batch', 'channel', 'kurir', 'awb_no_tracking', None]
    for i, field_name in enumerate(column_map_filter):
        if field_name:
            col_search_value = request.GET.get(f'columns[{i}][search][value]', '').strip()
            if col_search_value:
                queryset = queryset.filter(**{f'{field_name}__icontains': col_search_value})
    
    # --- Logika Sorting Header ---
    order_column_index = int(request.GET.get('order[0][column]', 1)) # Default: ID Pesanan (indeks 1)
    order_dir = request.GET.get('order[0][dir]', 'desc')

    # Menyesuaikan column_map_sort dengan kolom baru di frontend
    column_map_sort = [None, 'id_pesanan', 'tanggal_pembuatan', 'status', 'status_order', 'status_cancel', 'status_retur', 'status_bundle', 'nama_batch', 'channel', 'kurir', 'awb_no_tracking', None]
    order_field = column_map_sort[order_column_index]

    # **KUNCI PERBAIKAN:**
    # Jika sort by ID Pesanan (default) atau Tanggal, gunakan ID internal terbaru.
    # Jika kolom lain, gunakan nilai pertamanya (Min).
    if order_field in ['id_pesanan', 'tanggal_pembuatan']:
        sort_annotation = Max('id')
    else:
        sort_annotation = Min(order_field)
    
    groups = queryset.values('id_pesanan').annotate(sort_key=sort_annotation)
    
    sort_direction = '-' if order_dir == 'desc' else ''
    sorted_groups_qs = groups.order_by(f'{sort_direction}sort_key')
    
    total_filtered = sorted_groups_qs.count()
    
    paginated_ids = [item['id_pesanan'] for item in sorted_groups_qs[start:start + length]]

    # --- Logika Pengambilan Data ---
    data = []
    if paginated_ids:
        orders_for_page = Order.objects.filter(id_pesanan__in=paginated_ids).order_by('-id')
        orders_map = {}
        for order in orders_for_page:
            if order.id_pesanan not in orders_map:
                orders_map[order.id_pesanan] = order

        for idp in paginated_ids:
            order = orders_map.get(idp)
            if order:
                data.append({
                    'id_pesanan': order.id_pesanan,
                    'tanggal_pembuatan': order.tanggal_pembuatan,
                    'status': order.status,
                    'status_order': order.status_order,
                    'status_cancel': order.status_cancel or '',  # Tambahan: pastikan field ini ada dan datanya dikirim
                    'status_retur': order.status_retur or '',    # Tambahan: pastikan field ini ada dan datanya dikirim
                    'status_bundle': order.status_bundle or '',  # Tambahan: field status_bundle
                    'nama_batch': order.nama_batch or '',
                    'channel': order.channel,
                    'kurir': order.kurir,
                    'awb_no_tracking': order.awb_no_tracking,
                })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': Order.objects.values('id_pesanan').distinct().count(),
        'recordsFiltered': total_filtered,
        'data': data,
    })

@login_required
@permission_required('orders.view_order', raise_exception=True)
def order_details_api(request):
    """
    API untuk mengambil detail item produk berdasarkan id_pesanan.
    """
    id_pesanan = request.GET.get('id_pesanan')
    if not id_pesanan:
        return JsonResponse({'data': []})
    
    order_items = Order.objects.filter(id_pesanan=id_pesanan).select_related('product')
    
    data = [
        {
            'sku': item.sku,
            'nama_produk': item.product.nama_produk if item.product else 'N/A',
            'variant_produk': item.product.variant_produk if item.product else '',
            'brand': item.product.brand if item.product else '',
            'barcode': item.product.barcode if item.product else '',
            'jumlah': item.jumlah,
            'harga_promosi': item.harga_promosi,
            'jumlah_ambil': item.jumlah_ambil,
        }
        for item in order_items
    ]
    
    return JsonResponse({'data': data})

@login_required
@permission_required('orders.change_order', raise_exception=True)
def edit_order_view(request, id_pesanan):
    """
    Menampilkan form untuk melihat detail order (read-only)
    atau mengedit status dan catatan pembeli.
    """
    # Pastikan Order model diimport di scope file jika belum ada.
    # from .models import Order
    # from django.contrib import messages
    # from django.shortcuts import redirect, render

    order_items = Order.objects.filter(id_pesanan=id_pesanan)
    if not order_items.exists():
        messages.error(request, f"Order dengan ID {id_pesanan} tidak ditemukan.")
        return redirect('orders_all')

    order_ref = order_items.first()

    # Hanya GET: render form edit, TANPA proses update di sini
    context = {
        'order_ref': order_ref,
        'detail_items': order_items,
    }
    return render(request, 'orders/editorder.html', context)


@login_required
@csrf_exempt
@require_POST
def update_order_status_and_notes(request):
    """
    Endpoint API untuk mengupdate hanya status pembayaran dan catatan pembeli order.
    Update ini tetap diperbolehkan meskipun order sudah 'packed' atau 'shipped'.
    """
    try:
        data = json.loads(request.body)
        id_pesanan = data.get('id_pesanan')
        new_status = data.get('status')
        new_catatan_pembeli = data.get('catatan_pembeli', '')

        if not id_pesanan or not new_status:
            return JsonResponse({'success': False, 'message': 'ID Pesanan dan Status baru harus disediakan.'})

        orders_to_update = Order.objects.filter(id_pesanan=id_pesanan)

        if not orders_to_update.exists():
            return JsonResponse({'success': False, 'message': 'Order tidak ditemukan.'})

        # HAPUS VALIDASI INI: Karena user ingin tetap bisa update status dan catatan
        # meskipun order sudah 'packed' atau 'shipped'.
        # if orders_to_update.filter(status_order__in=['packed', 'shipped']).exists():
        #     return JsonResponse({'success': False, 'message': "Order yang sudah 'packed' atau 'shipped' tidak boleh diedit status atau catatannya."})

        # Lakukan update pada field 'status' dan 'catatan_pembeli'
        orders_to_update.update(status=new_status, catatan_pembeli=new_catatan_pembeli)

        return JsonResponse({'success': True, 'message': f"Status dan catatan untuk Order {id_pesanan} berhasil diupdate."})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Format request tidak valid.'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'Terjadi error internal: {str(e)}'}, status=500)


@login_required
@csrf_exempt
@require_POST
def update_order_item(request):
    """
    Endpoint API untuk mengupdate satu item (baris) dalam order.
    Akan menolak update jika item tersebut sudah 'packed' atau 'shipped'.
    """
    try:
        data = json.loads(request.body)
        order_pk = data.get('order_pk') # Primary Key dari Order item yang akan diupdate
        new_sku = data.get('new_sku')
        new_jumlah = data.get('new_jumlah')
        new_harga = data.get('new_harga')

        if not all([order_pk, new_sku, new_jumlah, new_harga is not None]): # check all required fields
            return JsonResponse({'success': False, 'message': 'Data tidak lengkap untuk update item.'})
        
        try:
            new_jumlah = int(new_jumlah)
            new_harga = float(new_harga)
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Jumlah atau harga harus angka yang valid.'})

        if new_jumlah <= 0:
            return JsonResponse({'success': False, 'message': 'Jumlah harus lebih dari 0.'})

        # Cari objek Order item yang spesifik berdasarkan PK
        order_item = Order.objects.filter(pk=order_pk).first()

        if not order_item:
            return JsonResponse({'success': False, 'message': 'Item order tidak ditemukan.'})

        # Validasi: Tolak update item jika status_order sudah 'packed' atau 'shipped'
        if order_item.status_order in ['packed', 'shipped']:
            return JsonResponse({'success': False, 'message': 'Item order sudah di-packed/shipped dan tidak boleh diubah.'})

        # Cari objek Product yang sesuai dengan SKU baru
        new_product_obj = Product.objects.filter(sku__iexact=new_sku).first()
        if not new_product_obj:
            return JsonResponse({'success': False, 'message': f'Produk dengan SKU {new_sku} tidak ditemukan.'})

        # Lakukan update pada objek Order item yang spesifik
        order_item.sku = new_sku
        order_item.jumlah = new_jumlah
        order_item.harga_promosi = new_harga
        order_item.product = new_product_obj # Update relasi product jika SKU berubah
        order_item.save() # Simpan perubahan

        # Opsional: Hitung ulang order_type jika perubahan SKU/jumlah mempengaruhi
        # Ini bisa menjadi operasi mahal jika sering, pertimbangkan kebutuhan
        # order_type = calculate_order_type(...) # Anda perlu pass data order lainnya
        # orders_in_group = Order.objects.filter(id_pesanan=order_item.id_pesanan)
        # current_skus = list(orders_in_group.values_list('sku', flat=True))
        # current_jumlahs = list(orders_in_group.values_list('jumlah', flat=True))
        # new_order_type = calculate_order_type(current_skus, current_jumlahs)
        # orders_in_group.update(order_type=new_order_type)

        return JsonResponse({'success': True, 'message': f"Item order untuk {order_item.id_pesanan} berhasil diupdate."})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Format request tidak valid.'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'Terjadi error internal: {str(e)}'}, status=500)

@login_required
@csrf_exempt
@require_POST
@permission_required('orders.add_order', raise_exception=True)
def add_order_item(request):
    """
    Endpoint API untuk menambahkan item baru ke order yang sudah ada.
    Hanya diperbolehkan jika order belum 'packed' atau 'shipped' dan belum masuk batch.
    """
    try:
        data = json.loads(request.body)
        id_pesanan = data.get('id_pesanan')
        sku = data.get('sku')
        jumlah = data.get('jumlah')
        harga = data.get('harga')

        if not all([id_pesanan, sku, jumlah is not None, harga is not None]):
            return JsonResponse({'success': False, 'message': 'Data tidak lengkap untuk menambahkan item.'})
        
        try:
            jumlah = int(jumlah)
            harga = float(harga)
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Jumlah atau harga harus angka yang valid.'})

        if jumlah <= 0:
            return JsonResponse({'success': False, 'message': 'Jumlah harus lebih dari 0.'})

        # Ambil salah satu item order untuk mendapatkan status global order
        # Karena Order model adalah denormalisasi per item, kita ambil yang pertama saja
        existing_order_items = Order.objects.filter(id_pesanan=id_pesanan)
        if not existing_order_items.exists():
            return JsonResponse({'success': False, 'message': 'Order induk tidak ditemukan.'})
        
        order_ref = existing_order_items.first()

        # Validasi "locked" logic: Hanya bisa menambah jika status_order pending dan nama_batch kosong/null
        if order_ref.status_order != 'pending' or (order_ref.nama_batch is not None and order_ref.nama_batch != ''):
            return JsonResponse({'success': False, 'message': 'Order sudah dalam proses fulfillment (tidak pending atau sudah di-batch) dan tidak bisa ditambah item.'})

        product_obj = Product.objects.filter(sku__iexact=sku).first()
        if not product_obj:
            return JsonResponse({'success': False, 'message': f'Produk dengan SKU {sku} tidak ditemukan.'})
        
        # Buat item order baru
        Order.objects.create(
            id_pesanan=id_pesanan,
            tanggal_pembuatan=order_ref.tanggal_pembuatan, # Ambil dari order referensi
            status=order_ref.status, # Ambil status pembayaran dari order referensi
            jenis_pesanan=order_ref.jenis_pesanan,
            channel=order_ref.channel,
            nama_toko=order_ref.nama_toko,
            sku=sku,
            product=product_obj,
            jumlah=jumlah,
            harga_promosi=harga,
            catatan_pembeli=order_ref.catatan_pembeli,
            kurir=order_ref.kurir,
            awb_no_tracking=order_ref.awb_no_tracking,
            metode_pengiriman=order_ref.metode_pengiriman,
            kirim_sebelum=order_ref.kirim_sebelum,
            order_type=order_ref.order_type, # Order type mungkin perlu dihitung ulang, tapi untuk sementara pakai yang ada
            status_order=order_ref.status_order,
            status_cancel=order_ref.status_cancel,
            status_retur=order_ref.status_retur,
            nama_batch=order_ref.nama_batch,
            jumlah_ambil=order_ref.jumlah_ambil,
            status_ambil=order_ref.status_ambil,
        )

        return JsonResponse({'success': True, 'message': f'Item SKU {sku} berhasil ditambahkan ke order {id_pesanan}.'})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Format request tidak valid.'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'Terjadi error internal: {str(e)}'}, status=500)


@login_required
@csrf_exempt
@require_POST
def delete_order_item(request):
    """
    Endpoint API untuk menghapus satu item (baris) dari order berdasarkan PK.
    Hanya diperbolehkan jika order belum 'packed' atau 'shipped' dan belum masuk batch.
    """
    try:
        data = json.loads(request.body)
        order_pk = data.get('order_pk')

        if not order_pk:
            return JsonResponse({'success': False, 'message': 'Primary Key item order harus disediakan.'})
        
        order_item = Order.objects.filter(pk=order_pk).first()

        if not order_item:
            return JsonResponse({'success': False, 'message': 'Item order tidak ditemukan.'})
        
        # Validasi "locked" logic: Hanya bisa menghapus jika status_order pending dan nama_batch kosong/null
        if order_item.status_order != 'pending' or (order_item.nama_batch is not None and order_item.nama_batch != ''):
            return JsonResponse({'success': False, 'message': 'Item order sudah dalam proses fulfillment (tidak pending atau sudah di-batch) dan tidak bisa dihapus.'})

        # Untuk mencegah order menjadi kosong, periksa jumlah item sisa
        total_items_in_order = Order.objects.filter(id_pesanan=order_item.id_pesanan).count()
        if total_items_in_order <= 1:
            return JsonResponse({'success': False, 'message': 'Order harus memiliki setidaknya satu item. Gunakan fitur "Delete Order" jika ingin menghapus seluruh order.'})

        order_item.delete()

        return JsonResponse({'success': True, 'message': f'Item order dengan PK {order_pk} berhasil dihapus.'})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Format request tidak valid.'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'Terjadi error internal: {str(e)}'}, status=500)
