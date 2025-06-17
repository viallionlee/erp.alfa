from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse, FileResponse
from .models import Stock, HistoryImportStock, Inbound, Outbound, InboundItem
from products.models import Product
import pandas as pd
import io
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q
from django.views.decorators.http import require_GET
from django.db import transaction
from django.db.models import F
import xlsxwriter
import tempfile

def index(request):
    # Ambil semua produk, join ke stock jika ada
    products = Product.objects.all().select_related()
    stock_qs = Stock.objects.all()
    stock_map = {s.product_id: s for s in stock_qs}
    product_list = []
    for p in products:
        stock = stock_map.get(p.id)
        quantity = stock.quantity if stock else 0
        quantity_locked = stock.quantity_locked if stock else 0
        # Hitung quantity_ready hanya untuk tampilan
        quantity_ready = quantity - quantity_locked
        product_list.append({
            'sku': p.sku,
            'barcode': p.barcode,
            'nama_produk': p.nama_produk,
            'variant_produk': p.variant_produk,
            'brand': p.brand,
            'quantity': quantity,
            'quantity_locked': quantity_locked,
            'quantity_ready': quantity_ready,
        })
    return render(request, 'inventory/index.html', {'product_list': product_list})

@login_required
def export_stock(request):
    # Export all products with stock info to Excel
    products = Product.objects.all().select_related()
    stock_map = {s.product_id: s for s in Stock.objects.all()}
    data = []
    for p in products:
        stock = stock_map.get(p.id)
        data.append({
            'SKU': p.sku,
            'Barcode': p.barcode,
            'Nama Produk': p.nama_produk,
            'Variant': p.variant_produk,
            'Brand': p.brand,
            'Quantity': stock.quantity if stock else 0,
            'Quantity Locked': stock.quantity_locked if stock else 0,
            'Quantity Ready': stock.quantity_ready if stock else 0,
        })
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Stock')
    output.seek(0)
    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=template_import_stock.xlsx'
    return response

@login_required
@csrf_exempt
def import_stock(request):
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        ext = file.name.split('.')[-1].lower()
        try:
            if ext in ['xls', 'xlsx']:
                df = pd.read_excel(file)
            elif ext == 'csv':
                df = pd.read_csv(file)
            else:
                messages.error(request, 'Format file tidak didukung.')
                return redirect('inventory:index')
            required_cols = ['SKU', 'Barcode', 'Nama Produk', 'Variant', 'Brand', 'Quantity', 'Quantity Locked']
            for col in required_cols:
                if col not in df.columns:
                    messages.error(request, f'Kolom {col} wajib ada di file.')
                    return redirect('inventory:index')
            success, failed = 0, 0
            notes = []
            for _, row in df.iterrows():
                sku = str(row['SKU']).strip()
                try:
                    product = Product.objects.get(sku=sku)
                    stock, _ = Stock.objects.get_or_create(product=product)
                    stock.quantity = int(row['Quantity'])
                    stock.quantity_locked = int(row['Quantity Locked'])
                    stock.save()
                    success += 1
                except Exception as e:
                    failed += 1
                    notes.append(f"SKU {sku}: {e}")
            HistoryImportStock.objects.create(
                imported_by=str(request.user),
                file_name=file.name,
                notes='\n'.join(notes) if notes else 'Berhasil',
                success_count=success,
                failed_count=failed
            )
            messages.success(request, f'Import selesai. Sukses: {success}, Gagal: {failed}')
        except Exception as e:
            messages.error(request, f'Gagal import: {e}')
        return redirect('inventory:index')
    return redirect('inventory:index')

def inbound_list(request):
    inbounds = Inbound.objects.all().order_by('-tanggal', '-id')
    return render(request, 'inventory/inbound.html', {'inbound_list': inbounds})

def outbound_list(request):
    outbounds = Outbound.objects.all().order_by('-tanggal', '-id')
    return render(request, 'inventory/outbound.html', {'outbound_list': outbounds})

def get_next_inbound_id():
    last = Inbound.objects.order_by('-id').first()
    return (last.id + 1) if last else 1

@login_required
def inbound_tambah(request):
    from datetime import datetime
    if request.method == 'POST':
        nomor_inbound = request.POST.get('nomor_inbound')
        tanggal = request.POST.get('tanggal')
        keterangan = request.POST.get('keterangan')
        produk_sku = request.POST.getlist('produk_sku[]')
        produk_qty = request.POST.getlist('produk_qty[]')
        if nomor_inbound and tanggal and produk_sku and produk_qty:
            inbound = Inbound.objects.create(
                nomor_inbound=nomor_inbound,
                tanggal=tanggal,
                keterangan=keterangan
            )
            for sku, qty in zip(produk_sku, produk_qty):
                try:
                    product = Product.objects.get(sku=sku)
                    InboundItem.objects.create(
                        inbound=inbound,
                        product=product,
                        quantity=int(qty)
                    )
                    # Update/insert ke tabel Stock
                    stock, _ = Stock.objects.get_or_create(product=product)
                    stock.quantity = (stock.quantity or 0) + int(qty)
                    stock.save()
                except Product.DoesNotExist:
                    continue
            messages.success(request, 'Data inbound dan item berhasil ditambahkan.')
            return redirect('inventory:inbound')
        else:
            messages.error(request, 'Nomor inbound, tanggal, dan produk wajib diisi.')
    else:
        # Generate default nomor_inbound dan tanggal
        next_id = get_next_inbound_id()
        now = timezone.localtime()
        nomor_inbound = f"INV/{now.strftime('%d-%m-%Y')}/{next_id}"
        tanggal = now.strftime('%Y-%m-%dT%H:%M')
    return render(request, 'inventory/inbound_tambah.html', {
        'default_nomor_inbound': nomor_inbound,
        'default_tanggal': tanggal
    })

@login_required
def produk_lookup(request):
    q = request.GET.get('q', '').strip()
    mode = request.GET.get('mode', '')
    if mode == 'manual':
        # Search by SKU, Barcode, Nama Produk, Variant, Brand (case-insensitive, contains)
        produk_qs = Product.objects.filter(
            Q(sku__icontains=q) |
            Q(barcode__icontains=q) |
            Q(nama_produk__icontains=q) |
            Q(variant_produk__icontains=q) |
            Q(brand__icontains=q)
        ).order_by('nama_produk')
        # Hilangkan paginasi, ambil semua data
        data = [
            {
                'sku': p.sku,
                'barcode': p.barcode,
                'nama': p.nama_produk,
                'variant': p.variant_produk or '',
                'brand': p.brand or ''
            } for p in produk_qs
        ]
        return JsonResponse(data, safe=False)
    # Default: scan barcode/sku exact
    produk = Product.objects.filter(Q(barcode=q) | Q(sku=q)).first()
    if produk:
        return JsonResponse({
            'sku': produk.sku,
            'barcode': produk.barcode,
            'nama': produk.nama_produk,
            'variant': produk.variant_produk or '',
            'brand': produk.brand or ''
        })
    return JsonResponse({'error': 'Produk tidak ditemukan'}, status=404)

@login_required
def inbound_detail(request, pk):
    inbound = Inbound.objects.get(pk=pk)
    items = InboundItem.objects.filter(inbound=inbound).select_related('product')
    return render(request, 'inventory/inbound_detail.html', {
        'inbound': inbound,
        'items': items
    })

@login_required
def inbound_delete(request, pk):
    inbound = Inbound.objects.get(pk=pk)
    if request.method == 'POST':
        with transaction.atomic():
            items = InboundItem.objects.filter(inbound=inbound).select_related('product')
            # Kumpulkan perubahan stok per SKU
            stock_update_map = {}
            for item in items:
                sku = item.product.sku
                stock_update_map[sku] = stock_update_map.get(sku, 0) - item.quantity
            # Bulk update stok dengan F() expression
            for sku, qty in stock_update_map.items():
                Stock.objects.filter(product__sku=sku).update(quantity=F('quantity') + qty)
                # Pastikan tidak minus
                Stock.objects.filter(product__sku=sku, quantity__lt=0).update(quantity=0)
            # Bulk delete semua InboundItem
            items.delete()
            inbound.delete()
        messages.success(request, 'Data inbound berhasil dihapus dan stok dikoreksi.')
        return redirect('inventory:inbound')
    return render(request, 'inventory/inbound_confirm_delete.html', {'inbound': inbound})

@login_required
@csrf_exempt
def inbound_import_massal(request):
    import pandas as pd
    from django.utils import timezone
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        ext = file.name.split('.')[-1].lower()
        try:
            if ext in ['xls', 'xlsx']:
                df = pd.read_excel(file)
            elif ext == 'csv':
                df = pd.read_csv(file)
            else:
                messages.error(request, 'Format file tidak didukung.')
                return redirect('inventory:inbound')
            # Hanya kolom SKU dan Quantity
            df = df.loc[:, [c for c in df.columns if str(c).strip().lower() in ['sku', 'quantity']]]
            df.columns = [c.strip().upper() for c in df.columns]
            required_cols = ['SKU', 'QUANTITY']
            for col in required_cols:
                if col not in df.columns:
                    messages.error(request, f'Kolom {col} wajib ada di file.')
                    return redirect('inventory:inbound')
            now = timezone.localtime()
            nomor_inbound = f"IMP/{now.strftime('%d-%m-%Y')}/{now.strftime('%H%M%S')}"
            inbound = Inbound.objects.create(
                nomor_inbound=nomor_inbound,
                tanggal=now,
                keterangan='import'
            )
            success, failed = 0, 0
            notes = []
            batch = []
            BATCH_SIZE = 2500
            # Kumpulkan perubahan stok dalam dict agar update massal
            stock_update_map = {}
            product_map = {}
            for _, row in df.iterrows():
                sku = str(row['SKU']).strip()
                try:
                    qty = int(row['QUANTITY'])
                except Exception:
                    failed += 1
                    notes.append(f"SKU {sku}: quantity tidak valid")
                    continue
                try:
                    product = Product.objects.get(sku=sku)
                    product_map[sku] = product
                    batch.append(InboundItem(
                        inbound=inbound,
                        product=product,
                        quantity=qty
                    ))
                    # Kumpulkan perubahan stok
                    if sku in stock_update_map:
                        stock_update_map[sku] += qty
                    else:
                        stock_update_map[sku] = qty
                    if len(batch) >= BATCH_SIZE:
                        InboundItem.objects.bulk_create(batch, batch_size=BATCH_SIZE)
                        success += len(batch)
                        batch = []
                except Product.DoesNotExist:
                    failed += 1
                    notes.append(f"SKU {sku}: produk tidak ditemukan")
                except Exception as e:
                    failed += 1
                    notes.append(f"SKU {sku}: {e}")
            if batch:
                InboundItem.objects.bulk_create(batch, batch_size=BATCH_SIZE)
                success += len(batch)
            # Update stok secara massal
            stock_objs = Stock.objects.select_for_update().filter(product__sku__in=stock_update_map.keys())
            stock_objs_map = {s.product.sku: s for s in stock_objs}
            new_stocks = []
            for sku, qty in stock_update_map.items():
                product = product_map.get(sku)
                if not product:
                    continue
                stock = stock_objs_map.get(sku)
                if stock:
                    stock.quantity = (stock.quantity or 0) + qty
                    stock.save()
                else:
                    new_stocks.append(Stock(product=product, quantity=qty))
            if new_stocks:
                Stock.objects.bulk_create(new_stocks, batch_size=BATCH_SIZE)
            messages.success(request, f'Impor selesai. Sukses: {success}, Gagal: {failed}')
            if notes:
                messages.warning(request, '\n'.join(notes))
        except Exception as e:
            messages.error(request, f'Gagal import: {e}')
        return redirect('inventory:inbound')
    return redirect('inventory:inbound')

@login_required
@require_GET
def stock_data(request):
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '')
    order_column_index = int(request.GET.get('order[0][column]', 0))
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'quantity', 'quantity_locked', 'quantity_ready']
    order_column = columns[order_column_index] if order_column_index < len(columns) else 'sku'
    if order_dir == 'desc':
        order_column = '-' + order_column

    queryset = Product.objects.all().select_related()
    # Join ke Stock
    stock_map = {s.product_id: s for s in Stock.objects.all()}
    total_count = queryset.count()

    # Per-column search
    from django.db.models import Q
    filter_q = Q()
    for idx, col in enumerate(columns):
        col_search = request.GET.get(f'columns[{idx}][search][value]', '').strip()
        if col_search:
            filter_q &= Q(**{f"{col}__icontains": col_search})
    if search_value:
        filter_q &= (
            Q(sku__icontains=search_value) |
            Q(barcode__icontains=search_value) |
            Q(nama_produk__icontains=search_value) |
            Q(variant_produk__icontains=search_value) |
            Q(brand__icontains=search_value)
        )
    queryset = queryset.filter(filter_q)
    filtered_count = queryset.count()

    queryset = queryset.order_by(order_column)[start:start+length]

    data = []
    for p in queryset:
        stock = stock_map.get(p.id)
        data.append({
            'sku': p.sku,
            'barcode': p.barcode,
            'nama_produk': p.nama_produk,
            'variant_produk': p.variant_produk,
            'brand': p.brand,
            'quantity': stock.quantity if stock else 0,
            'quantity_locked': stock.quantity_locked if stock else 0,
            'quantity_ready': stock.quantity_ready if stock else 0,
        })
    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_count,
        'recordsFiltered': filtered_count,
        'data': data,
    })

@login_required
@require_GET
def inbound_data(request):
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '')
    order_column_index = int(request.GET.get('order[0][column]', 0))
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id', 'nomor_inbound', 'tanggal', 'keterangan']
    order_column = columns[order_column_index] if order_column_index < len(columns) else 'id'
    if order_dir == 'desc':
        order_column = '-' + order_column

    queryset = Inbound.objects.all()
    total_count = queryset.count()

    # Per-column search
    from django.db.models import Q
    filter_q = Q()
    for idx, col in enumerate(columns):
        col_search = request.GET.get(f'columns[{idx}][search][value]', '').strip()
        if col_search:
            filter_q &= Q(**{f"{col}__icontains": col_search})
    if search_value:
        filter_q &= (
            Q(id__icontains=search_value) |
            Q(nomor_inbound__icontains=search_value) |
            Q(tanggal__icontains=search_value) |
            Q(keterangan__icontains=search_value)
        )
    queryset = queryset.filter(filter_q)
    filtered_count = queryset.count()

    queryset = queryset.order_by(order_column)[start:start+length]

    data = []
    for inbound in queryset:
        data.append({
            'id': inbound.id,
            'nomor_inbound': inbound.nomor_inbound,
            'tanggal': inbound.tanggal.strftime('%d-%m-%Y %H:%M'),
            'keterangan': inbound.keterangan or '',
            'aksi': f'<a href="/inventory/inbound/{inbound.id}/" class="btn btn-sm btn-info">Open</a> '
                    f'<a href="/inventory/inbound/{inbound.id}/delete/" class="btn btn-sm btn-danger" onclick="return confirm(\'Yakin hapus data ini?\')">Delete</a>'
        })
    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_count,
        'recordsFiltered': filtered_count,
        'data': data,
    })

def download_template_inbound(request):
    # Template hanya kolom SKU dan Quantity
    output = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    workbook = xlsxwriter.Workbook(output.name)
    worksheet = workbook.add_worksheet()
    headers = ['SKU', 'Quantity']
    for col_num, header in enumerate(headers):
        worksheet.write(0, col_num, header)
    workbook.close()
    output.seek(0)
    response = FileResponse(open(output.name, 'rb'), as_attachment=True, filename='template_import_inbound.xlsx')
    return response
