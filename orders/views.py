from django.shortcuts import render
from django.http import JsonResponse
from .models import Order, OrderImportHistory, Customer, OrdersList
from products.models import Product, ProductsBundling
from django.db.models import Q
import os
import pandas as pd
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
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

def index(request):
    qs = Order.objects.select_related('product').order_by('-id')[:100]  # tampilkan 100 saja
    data = []
    for order in qs:
        # Ambil info produk jika ada
        if order.product:
            nama_produk = order.product.nama_produk or ''
            variant_produk = getattr(order.product, 'variant_produk', '')
            brand = getattr(order.product, 'brand', '')
            product_id = order.product.id
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
        ])
    total_order = Order.objects.values('id_pesanan').distinct().count()

    # Calculate total SKU not found for orders with status 'Lunas' dan nama_batch kosong/null, exclude status_bundle='Y'
    lunas_orders = Order.objects.filter(status__iexact='Lunas').filter(Q(nama_batch__isnull=True) | Q(nama_batch='')).exclude(status_bundle='Y')
    order_skus = set(lunas_orders.values_list('sku', flat=True))
    master_skus = set(Product.objects.values_list('sku', flat=True))
    sku_not_found_list = sorted(order_skus - master_skus)
    sku_not_found_count = len(sku_not_found_list)

    return render(request, 'orders/index.html', {
        'data': data,
        'total_order': total_order,
        'sku_not_found_count': sku_not_found_count,
        'sku_not_found_list': sku_not_found_list,
    })

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

@login_required
def orderimport_history(request):
    history = OrderImportHistory.objects.all().order_by('-import_time')
    return render(request, 'orders/orderimport_history.html', {'history': history})

@csrf_exempt
@login_required
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
        df['id_pesanan'] = df['id_pesanan'].astype(str).str.strip().str.lower()
        df['sku'] = df['sku'].astype(str).str.strip().str.upper()
        grouped = df.groupby(['id_pesanan', 'sku'], as_index=False).agg({**{col: 'first' for col in df.columns if col not in ['id_pesanan', 'sku', 'jumlah']}, 'jumlah': 'sum'})
        updated, created, skipped = 0, 0, 0
        failed_notes = []
        orders_to_create = []
        # --- BULK UPDATE LOGIC ---
        # 1. Kumpulkan semua kombinasi id_pesanan+sku+status dari data import
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
        for order in existing_orders:
            new_status = update_map.get((order.id_pesanan, order.sku))
            if new_status and order.status != new_status:
                order.status = new_status
                orders_to_update.append(order)
                updated += 1
            else:
                skipped += 1
        if orders_to_update:
            Order.objects.bulk_update(orders_to_update, ['status'])
        # Build set of all existing (id_pesanan, sku) in DB to skip creation
        existing_keys = set((order.id_pesanan, order.sku) for order in existing_orders)
        # 4. Sisanya adalah data baru, proses seperti biasa
        for _, row in grouped.iterrows():
            id_pesanan = row['id_pesanan']
            sku = row['sku']
            if (id_pesanan, sku) in existing_keys:
                continue  # Sudah diupdate, skip
            product_obj = Product.objects.filter(sku__iexact=sku).first()
            if not product_obj:
                failed_notes.append(f"SKU {sku} (id_pesanan: {id_pesanan}) is not in table products yet, please check!")
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
                        sku_lookup = str(r['sku']).strip()
                        prod = Product.objects.filter(sku__iexact=sku_lookup).first()
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
            # Hapus key 'id' jika ada (prevent error)
            if 'id' in order_kwargs:
                del order_kwargs['id']
            # Otomatis isi semua field model Order yang tidak ada di Excel dengan '' (kecuali jumlah, jumlah_ambil, harga_promosi -> 0)
            from django.forms.models import model_to_dict
            order_fields = [f.name for f in Order._meta.get_fields() if f.concrete and not f.auto_created and f.name != 'id']
            for f in order_fields:
                if f not in order_kwargs:
                    if f in ['jumlah', 'jumlah_ambil']:
                        order_kwargs[f] = 0
                    elif f == 'harga_promosi':
                        order_kwargs[f] = 0.0
                    elif f == 'nama_batch':
                        order_kwargs[f] = ''  # Default kosong untuk nama_batch
                    elif f == 'import_history' or f == 'product':
                        order_kwargs[f] = None  # ForeignKey harus None jika tidak ada
                    else:
                        order_kwargs[f] = ''
            if product_obj:
                order_kwargs['product'] = product_obj
            try:
                # Validasi field wajib
                if not order_kwargs['id_pesanan'] or not order_kwargs['sku'] or order_kwargs['jumlah'] is None:
                    if not order_kwargs['sku']:
                        failed_notes.append(f"Row {id_pesanan}/(SKU kosong) dilewati: SKU wajib diisi.")
                    else:
                        failed_notes.append(f"Row {id_pesanan}/{sku} dilewati: id_pesanan, sku, dan jumlah wajib diisi.")
                    continue
                # Pastikan jumlah_ambil selalu 0 jika tidak ada
                if 'jumlah_ambil' not in order_kwargs or order_kwargs['jumlah_ambil'] is None:
                    order_kwargs['jumlah_ambil'] = 0
                orders_to_create.append(Order(**order_kwargs))
            except Exception as e:
                failed_notes.append(f"Row {id_pesanan}/{sku} failed: {str(e)}")
        if len(orders_to_create) >= 2000:
            try:
                Order.objects.bulk_create(orders_to_create, batch_size=2000)
                created += len(orders_to_create)
            except Exception as e:
                failed_notes.append(f"Bulk create error: {str(e)}")
            orders_to_create = []
        if orders_to_create:
            try:
                Order.objects.bulk_create(orders_to_create, batch_size=2000)
                created += len(orders_to_create)
            except Exception as e:
                failed_notes.append(f"Bulk create error: {str(e)}")
        import_history = OrderImportHistory.objects.create(
            file_name=file.name,
            notes='; '.join(failed_notes) if failed_notes else 'Import sukses',
            imported_by=request.user if request.user.is_authenticated else None
        )
        # Setelah import_history dibuat, update semua Order yang baru dibuat agar import_history-nya terisi
        if orders_to_create:
            for o in orders_to_create:
                o.import_history = import_history
            try:
                Order.objects.bulk_create(orders_to_create, batch_size=2000)
                created += len(orders_to_create)
            except Exception as e:
                failed_notes.append(f"Bulk create error: {str(e)}")
        if created > 0:
            Order.objects.filter(import_history__isnull=True, file_name=file.name).update(import_history=import_history)
        # Kumpulkan info SKU not found
        sku_not_found_list = []
        for note in failed_notes:
            if note.startswith("SKU ") and "is not in table products" in note:
                sku = note.split()[1]
                sku_not_found_list.append(sku)
        sku_not_found_count = len(sku_not_found_list)
        
        return JsonResponse({
            'created': created,
            'updated': updated,
            'skipped': skipped,
            'sku_not_found_count': sku_not_found_count,
            'sku_not_found_list': sku_not_found_list,
            'failed_notes': failed_notes,
            'status': 'Import selesai',
            'success': True
        })
    except Exception as e:
        tb = traceback.format_exc()
        return JsonResponse({'error': str(e), 'traceback': tb}, status=500)

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

def import_status_view(request):
    # Ganti dengan logic real: cek status import dari database, cache, atau file
    # Contoh: return JsonResponse({'status': 'processing', 'progress': 0.5})
    return JsonResponse(import_status)

@csrf_exempt
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

@login_required
@csrf_exempt
def add_order(request):
    if request.method == 'POST':
        data = request.POST
        id_pesanan = data.get('id_pesanan')
        tanggal_pembuatan = data.get('tanggal_pembuatan')
        nama_customer = data.get('nama_customer')
        keterangan = data.get('keterangan')
        produk_sku = data.getlist('produk_sku[]')
        produk_qty = data.getlist('produk_qty[]')
        produk_harga = data.getlist('produk_harga[]')
        if not produk_sku or not nama_customer:
            messages.error(request, 'Nama customer dan minimal 1 produk wajib diisi!')
            return render(request, 'orders/addorder.html')
        customer_obj = Customer.objects.filter(nama_customer=nama_customer).first()
        # --- Tambah/Update OrdersList ---
        from django.utils.dateparse import parse_datetime
        import datetime
        # Normalisasi tanggal_pembuatan ke string dd-mm-yyyy HH:MM
        if not tanggal_pembuatan:
            tgl = datetime.datetime.now().replace(second=0, microsecond=0)
        else:
            try:
                tgl = datetime.datetime.strptime(tanggal_pembuatan, '%d-%m-%Y %H:%M')
            except ValueError:
                tgl = parse_datetime(tanggal_pembuatan)
                if not tgl:
                    tgl = datetime.datetime.now().replace(second=0, microsecond=0)
                else:
                    tgl = tgl.replace(second=0, microsecond=0)
        tanggal_pembuatan_str = tgl.strftime('%d-%m-%Y %H:%M')
        # Simpan ke OrdersList (DateTimeField)
        orderslist_obj, created = OrdersList.objects.update_or_create(
            id_pesanan=id_pesanan,
            defaults={
                'customer': customer_obj,
                'tanggal_pembuatan': tgl,
                'keterangan': keterangan or '',
            }
        )
        # --- Simpan detail ke Order ---
        # Hitung order_type otomatis seperti di import_orders
        brands = set()
        for sku in produk_sku:
            product_obj = Product.objects.filter(sku__iexact=sku).first()
            if product_obj and product_obj.brand:
                brands.add(product_obj.brand.strip().upper())
            else:
                brands.add('')
        if len(produk_sku) == 1:
            order_type = '1' if int(produk_qty[0]) == 1 else '2'
        else:
            if len(brands) == 1 and list(brands)[0] != '':
                order_type = '4'
            else:
                order_type = '3'
        # Hapus detail lama jika update order (opsional, bisa diaktifkan jika perlu)
        Order.objects.filter(id_pesanan=id_pesanan).delete()
        for idx, sku in enumerate(produk_sku):
            product_obj = Product.objects.filter(sku=sku).first()
            # Pastikan tidak pernah mengisi field 'id' secara manual!
            Order.objects.create(
                tanggal_pembuatan=tanggal_pembuatan_str,
                status='Lunas',
                jenis_pesanan='manual',
                channel='manual',
                nama_toko='manual',
                id_pesanan=id_pesanan,
                sku=sku,
                jumlah=int(produk_qty[idx]) if idx < len(produk_qty) else 1,
                harga_promosi=float(produk_harga[idx]) if idx < len(produk_harga) else 0,
                catatan_pembeli='',
                kurir='',
                awb_no_tracking='',
                metode_pengiriman='',
                kirim_sebelum='',
                order_type=order_type,
                status_order='pending',
                status_cancel='N',
                status_retur='N',
                nama_batch='',
                jumlah_ambil=0,
                status_ambil='',
                product=product_obj
            )
        messages.success(request, 'Order berhasil ditambahkan!')
        return redirect(reverse('orders_list'))
    return render(request, 'orders/addorder.html')

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

@login_required
def orders_list(request):
    # Ambil semua OrdersList, hitung total item per order
    orders = OrdersList.objects.all().order_by('-tanggal_pembuatan')
    data = []
    for o in orders:
        # Hitung total item dengan query ke Order berdasarkan id_pesanan
        total_item = Order.objects.filter(id_pesanan=o.id_pesanan).aggregate(total=models.Sum('jumlah'))['total'] or 0
        # Ambil nama customer dari relasi customer
        nama_customer = o.customer.nama_customer if hasattr(o, 'customer') else ''
        data.append({
            'id_pesanan': o.id_pesanan,
            'tanggal_pembuatan': o.tanggal_pembuatan,
            'nama_customer': nama_customer,
            'keterangan': o.keterangan,
            'total_item': total_item,
        })
    return render(request, 'orders/orders_list.html', {'orders': data})

@login_required
def orders_listdetail(request, id_pesanan):
    # Ambil info utama order dari OrdersList
    orderlist = OrdersList.objects.filter(id_pesanan=id_pesanan).first()
    if not orderlist:
        messages.error(request, 'Order tidak ditemukan!')
        return redirect('orders_list')
    # Ambil detail produk dari Order
    detail_qs = Order.objects.filter(id_pesanan=id_pesanan)
    detail_items = []
    for d in detail_qs:
        # Ambil info produk jika ada
        nama_produk = d.product.nama_produk if d.product else ''
        variant_produk = d.product.variant_produk if d.product else ''
        brand = d.product.brand if d.product else ''
        barcode = d.product.barcode if d.product else ''
        # Cek stok jika ada product
        stok = d.product.stock.quantity if hasattr(d.product, 'stock') and d.product.stock else ''
        detail_items.append({
            'sku': d.sku,
            'barcode': barcode,
            'nama_produk': nama_produk,
            'variant_produk': variant_produk,
            'brand': brand,
            'stok': stok,
            'jumlah': d.jumlah,
            'harga_promosi': d.harga_promosi,
        })
    total_item = detail_qs.aggregate(total=models.Sum('jumlah'))['total'] or 0
    context = {
        'id_pesanan': orderlist.id_pesanan,
        'tanggal_pembuatan': orderlist.tanggal_pembuatan,
        'nama_customer': orderlist.customer.nama_customer if orderlist.customer else '',
        'keterangan': orderlist.keterangan,
        'total_item': total_item,
        'detail_items': detail_items,
    }
    return render(request, 'orders/orders_listdetail.html', context)

@login_required
def orders_listedit(request, id_pesanan):
    from .models import OrdersList, Order, Customer, Product
    from django.utils.dateparse import parse_datetime
    from django.contrib import messages
    from django.shortcuts import redirect, render
    import datetime
    orderlist = OrdersList.objects.filter(id_pesanan=id_pesanan).first()
    if not orderlist:
        messages.error(request, 'Order tidak ditemukan!')
        return redirect('orders_list')
    detail_qs = Order.objects.filter(id_pesanan=id_pesanan)
    if request.method == 'POST':
        # Update data utama
        tanggal_pembuatan = request.POST.get('tanggal_pembuatan')
        nama_customer = request.POST.get('nama_customer')
        keterangan = request.POST.get('keterangan')
        produk_sku = request.POST.getlist('produk_sku[]')
        produk_qty = request.POST.getlist('produk_qty[]')
        produk_harga = request.POST.getlist('produk_harga[]')
        customer_obj = Customer.objects.filter(nama_customer=nama_customer).first()
        tgl = parse_datetime(tanggal_pembuatan) if tanggal_pembuatan else datetime.datetime.now()
        orderlist.customer = customer_obj
        orderlist.tanggal_pembuatan = tgl
        orderlist.keterangan = keterangan
        orderlist.save()
        # Hitung order_type otomatis
        brands = set()
        for sku in produk_sku:
            product_obj = Product.objects.filter(sku__iexact=sku).first()
            if product_obj and product_obj.brand:
                brands.add(product_obj.brand.strip().upper())
            else:
                brands.add('')
        if len(produk_sku) == 1:
            order_type = '1' if int(produk_qty[0]) == 1 else '2'
        else:
            if len(brands) == 1 and list(brands)[0] != '':
                order_type = '4'
            else:
                order_type = '3'
        # Hapus detail lama
        Order.objects.filter(id_pesanan=id_pesanan).delete()
        # Hapus detail lama
        from django.db import transaction
        try:
            with transaction.atomic():
                Order.objects.filter(id_pesanan=id_pesanan).delete()
                for idx, sku in enumerate(produk_sku):
                    product_obj = Product.objects.filter(sku=sku).first()
                    print(f"DEBUG: Akan membuat order untuk SKU={sku}, product_obj={product_obj}")
                    Order.objects.create(
                        tanggal_pembuatan=tgl.strftime('%d-%m-%Y %H:%M'),
                        status='Lunas',
                        jenis_pesanan='manual',
                        channel='manual',
                        nama_toko='manual',
                        id_pesanan=id_pesanan,
                        sku=sku,
                        jumlah=int(produk_qty[idx]) if idx < len(produk_qty) else 1,
                        harga_promosi=float(produk_harga[idx]) if idx < len(produk_harga) else 0,
                        catatan_pembeli='',
                        kurir='',
                        awb_no_tracking='',
                        metode_pengiriman='',
                        kirim_sebelum='',
                        order_type=order_type,
                        status_order='pending',
                        status_cancel='N',
                        status_retur='N',
                        nama_batch='',
                        jumlah_ambil=0,
                        status_ambil='',
                        product=product_obj
                    )
                    print(f"DEBUG: Order untuk SKU={sku} berhasil dibuat")
        except Exception as e:
            print(f"ERROR: Gagal membuat order: {e}")
        messages.success(request, f"Order {id_pesanan} berhasil diupdate.")
        return redirect('orders_list')
    # Siapkan data untuk form edit (seperti add_order, tapi readonly id_pesanan)
    detail_items = []
    for d in detail_qs:
        nama_produk = d.product.nama_produk if d.product else ''
        variant_produk = d.product.variant_produk if d.product else ''
        brand = d.product.brand if d.product else ''
        barcode = d.product.barcode if d.product else ''
        stok = d.product.stock.quantity if hasattr(d.product, 'stock') and d.product.stock else ''
        detail_items.append({
            'sku': d.sku,
            'barcode': barcode,
            'nama_produk': nama_produk,
            'variant_produk': variant_produk,
            'brand': brand,
            'stok': stok,
            'jumlah': d.jumlah,
            'harga_promosi': d.harga_promosi,
        })
    total_item = detail_qs.aggregate(total=models.Sum('jumlah'))['total'] or 0
    context = {
        'id_pesanan': orderlist.id_pesanan,
        'tanggal_pembuatan': orderlist.tanggal_pembuatan,
        'nama_customer': orderlist.customer.nama_customer if orderlist.customer else '',
        'keterangan': orderlist.keterangan,
        'total_item': total_item,
        'detail_items': detail_items,
        'edit_mode': True,
    }
    return render(request, 'orders/orders_listdetail.html', context)

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
