from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from .models import Product, ProductImportHistory, ProductsBundling
from django.contrib.auth.decorators import login_required
import csv, io, os
from django.utils import timezone
from django.contrib.auth import get_user
import pandas as pd
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from .tasks import import_products_task
from django.views.decorators.http import require_GET
from django.core.paginator import Paginator
from django_tables2.views import SingleTableView
from django.db.models import Q
from django.contrib import messages
import io
import xlsxwriter

def index(request):
    brands = Product.objects.values_list('brand', flat=True).distinct().order_by('brand')
    raks = Product.objects.values_list('rak', flat=True).distinct().order_by('rak')
    variants = Product.objects.values_list('variant_produk', flat=True).distinct().order_by('variant_produk')
    products = Product.objects.all()
    import_history = ProductImportHistory.objects.order_by('-import_time')[:20]
    return render(request, 'products/index.html', {
        'products': products,
        'import_history': import_history,
        'brands': brands,
        'raks': raks,
        'variants': variants,
    })


def import_products(request):
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        filename = file.name
        ext = os.path.splitext(filename)[1].lower()
        rows = []
        if ext == '.csv':
            decoded = file.read().decode('utf-8-sig')  # hilangkan BOM
            reader = csv.DictReader(io.StringIO(decoded))
            rows = list(reader)
        elif ext in ['.xls', '.xlsx']:
            df = pd.read_excel(file, dtype=str)  # baca semua kolom sebagai string
            df = df.fillna('')  # ganti NaN dengan string kosong
            rows = df.to_dict(orient='records')
        else:
            return redirect('/products/')
        # Hanya field yang valid di model Product
        valid_fields = ['sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'rak']
        total = len(rows)
        inserted = 0
        failed = 0
        failed_notes = []
        batch_size = 500
        for i in range(0, total, batch_size):
            batch = rows[i:i+batch_size]
            products = []
            duplicate_sku = set(Product.objects.filter(sku__in=[str(row.get('sku') or '').strip() for row in batch]).values_list('sku', flat=True))
            duplicate_barcode = set(Product.objects.filter(barcode__in=[str(row.get('barcode') or '').strip() for row in batch]).values_list('barcode', flat=True))
            for idx, row in enumerate(batch):
                clean_row = {k.strip().replace('\ufeff', ''): (v if v not in [None, 'nan', 'NaN', '[null]'] else '') for k, v in row.items() if k and k.strip().replace('\ufeff', '') in valid_fields}
                sku = str(clean_row.get('sku') or '').strip()
                barcode = str(clean_row.get('barcode') or '').strip()
                if sku in duplicate_sku or barcode in duplicate_barcode:
                    failed += 1
                    failed_notes.append(f"Row {i+idx+1}: Duplicate SKU/barcode: {sku}/{barcode}")
                    continue
                try:
                    products.append(Product(**clean_row))
                except Exception as e:
                    failed += 1
                    failed_notes.append(f"Row {i+idx+1}: {e}")
            Product.objects.bulk_create(products, ignore_conflicts=True)
            inserted += len(products)
            # Simpan progress ke session
            request.session['import_progress'] = int((inserted + failed) / total * 100)
        request.session['import_progress'] = 100
        # Simpan ke ProductImportHistory
        ProductImportHistory.objects.create(
            file_name=filename,
            notes='\n'.join(failed_notes) if failed_notes else 'Berhasil',
            success_count=inserted,
            failed_count=failed,
            imported_by=request.user if request.user.is_authenticated else None
        )
        return render(request, 'products/import_status.html', {'status': 'Import selesai. Semua data telah diimpor.'})
    return redirect('/products/')

def import_progress(request):
    progress = request.session.get('import_progress', 0)
    return JsonResponse({'progress': progress})

def download_template(request):
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet()
    headers = ['sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'rak']
    for col_num, header in enumerate(headers):
        worksheet.write(0, col_num, header)
    workbook.close()
    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=template_import_produk.xlsx'
    return response


def export_products(request):
    products = Product.objects.all().values('sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'rak')
    df = pd.DataFrame(list(products))
    # Pastikan urutan kolom sama dengan template import
    df = df[['sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'rak']]
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=products.xlsx'
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Products')
    return response

def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.delete()
    return redirect('products:index')

def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        product.sku = request.POST.get('sku', product.sku)
        product.barcode = request.POST.get('barcode', product.barcode)
        product.nama_produk = request.POST.get('nama_produk', product.nama_produk)
        product.variant_produk = request.POST.get('variant_produk', product.variant_produk)
        product.brand = request.POST.get('brand', product.brand)
        product.rak = request.POST.get('rak', product.rak)
        if request.FILES.get('photo') and hasattr(product, 'photo'):
            product.photo = request.FILES['photo']
        product.save()
        return redirect('products:index')
    return render(request, 'products/edit_product.html', {'product': product})

@csrf_exempt
def update_product(request, product_id):
    if request.method == 'POST':
        try:
            p = Product.objects.get(id=product_id)
            data = request.POST
            # Update only allowed fields
            for field in ['sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'rak']:
                if field in data:
                    setattr(p, field, data[field])
            p.save()
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'msg': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'msg': 'Invalid request'}, status=405)

@csrf_exempt
def delete_import_history(request, history_id):
    if request.method == 'DELETE':
        try:
            ProductImportHistory.objects.filter(id=history_id).delete()
            return JsonResponse({'message': 'Entri berhasil dihapus.'}, status=200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request method.'}, status=405)

def import_history_view(request):
    import_history = ProductImportHistory.objects.all().order_by('-import_time')
    return render(request, 'products/import_history.html', {'import_history': import_history})

def products_data(request):
    # DataTables server-side processing with per-column filter
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '')
    order_column_index = request.GET.get('order[0][column]', 0)
    order_dir = request.GET.get('order[0][dir]', 'asc')

    columns = ['id', 'sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'rak']
    order_column = columns[int(order_column_index)] if int(order_column_index) < len(columns) else 'id'
    if order_dir == 'desc':
        order_column = '-' + order_column

    queryset = Product.objects.all()
    total_count = queryset.count()

    # Per-column search
    from django.db.models import Q
    import re
    filter_q = Q()
    for idx, col in enumerate(columns):
        col_search = request.GET.get(f'columns[{idx}][search][value]', '').strip()
        if col_search:
            # If filter is regex like ^SOMETHING$, use iexact
            m = re.match(r'^\^(.*)\$$', col_search)
            if m:
                filter_q &= Q(**{f"{col}__iexact": m.group(1)})
            else:
                filter_q &= Q(**{f"{col}__icontains": col_search})
    if search_value:
        filter_q &= (
            Q(sku__icontains=search_value) |
            Q(barcode__icontains=search_value) |
            Q(nama_produk__icontains=search_value) |
            Q(variant_produk__icontains=search_value) |
            Q(brand__icontains=search_value) |
            Q(rak__icontains=search_value)
        )
    queryset = queryset.filter(filter_q)
    filtered_count = queryset.count()

    # Handle DataTables 'View All' (length=-1) safely
    MAX_EXPORT_ROWS = 5000
    if length == -1 or length > MAX_EXPORT_ROWS:
        length = MAX_EXPORT_ROWS
        if filtered_count > MAX_EXPORT_ROWS:
            return JsonResponse({
                'draw': draw,
                'recordsTotal': total_count,
                'recordsFiltered': filtered_count,
                'data': [],
                'error': f"Terlalu banyak data untuk ditampilkan sekaligus (> {MAX_EXPORT_ROWS}). Silakan filter data atau ekspor saja."
            })

    queryset = queryset.order_by(order_column)[start:start+length]

    data = [
        {
            'id': p.id,
            'sku': p.sku,
            'barcode': p.barcode,
            'nama_produk': p.nama_produk,
            'variant_produk': p.variant_produk,
            'brand': p.brand,
            'rak': p.rak,
        }
        for p in queryset
    ]
    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_count,
        'recordsFiltered': filtered_count,
        'data': data,
    })

def viewall(request):
    products = Product.objects.all()
    return render(request, 'products/viewall.html', {'products': products})

def aggrid_data(request):
    # AG Grid: server-side filter, sort, pagination
    from django.db.models import Q
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 100))
    sort_field = request.GET.get('sort_field', 'id')
    sort_dir = request.GET.get('sort_dir', 'asc')
    # Filter fields
    filter_fields = ['sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'rak']
    filter_q = Q()
    for field in filter_fields:
        val = request.GET.get(f'filter_{field}', '').strip()
        if val:
            filter_q &= Q(**{f"{field}__icontains": val})
    queryset = Product.objects.filter(filter_q)
    # Sorting
    if sort_field in filter_fields + ['id']:
        if sort_dir == 'desc':
            queryset = queryset.order_by(f'-{sort_field}')
        else:
            queryset = queryset.order_by(sort_field)
    else:
        queryset = queryset.order_by('id')
    # Pagination
    total = queryset.count()
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    data = []
    for p in page_obj.object_list:
        data.append({
            'id': p.id,
            'sku': p.sku,
            'barcode': p.barcode,
            'nama_produk': p.nama_produk,
            'variant_produk': p.variant_produk or '',
            'brand': p.brand or '',
            'rak': p.rak or '',
            'photo': p.photo.url if p.photo else '',
        })
    return JsonResponse({
        'results': data,
        'total': total
    })

def products_autocomplete(request):
    q = request.GET.get('q', '').strip()
    page = int(request.GET.get('page', 1))
    page_size = 20
    if not q:
        return JsonResponse({'results': [], 'has_more': False}, safe=False)
    qs = Product.objects.filter(
        Q(sku__icontains=q) |
        Q(barcode__icontains=q) |
        Q(nama_produk__icontains=q) |
        Q(variant_produk__icontains=q) |
        Q(brand__icontains=q)
    )
    total = qs.count()
    start = (page - 1) * page_size
    end = start + page_size
    qs = qs[start:end]
    data = [
        {
            'sku': p.sku or '',
            'barcode': p.barcode or '',
            'nama_produk': p.nama_produk or '',
            'variant_produk': p.variant_produk or '',
            'brand': p.brand or '',
        } for p in qs
    ]
    has_more = end < total
    return JsonResponse({'results': data, 'has_more': has_more}, safe=False)

@require_GET
def unique_brands(request):
    brands = Product.objects.values_list('brand', flat=True).distinct().order_by('brand')
    return JsonResponse({'brands': list(brands)})

@require_GET
def unique_raks(request):
    raks = Product.objects.values_list('rak', flat=True).distinct().order_by('rak')
    return JsonResponse({'raks': list(raks)})

def sku_bundling_list(request):
    bundlings = ProductsBundling.objects.all().order_by('-id')
    return render(request, 'products/sku_bundling.html', {'bundlings': bundlings})

def sku_bundling_add(request):
    if request.method == 'POST':
        sku_bundling = request.POST.get('sku_bundling', '').strip()
        sku_items_json = request.POST.get('sku_items_json', '[]')
        try:
            items = json.loads(sku_items_json)
        except Exception:
            items = []
        errors = []
        if not sku_bundling:
            errors.append('SKU Bundling wajib diisi.')
        if not items:
            errors.append('Minimal 1 produk harus dipilih.')
        # Compose sku_list: "sku1:jumlah1,sku2:jumlah2,..."
        sku_list = ','.join(f"{item['sku']}:{item['jumlah']}" for item in items if item.get('sku') and item.get('jumlah'))
        if not sku_list:
            errors.append('SKU dan jumlah produk tidak valid.')
        # Cek duplikat
        from .models import ProductsBundling
        if ProductsBundling.objects.filter(sku_bundling=sku_bundling).exists():
            errors.append('SKU Bundling sudah ada.')
        if errors:
            return render(request, 'products/sku_bundling_form.html', {'error': '\n'.join(errors)})
        ProductsBundling.objects.create(sku_bundling=sku_bundling, sku_list=sku_list)
        return redirect('products:sku_bundling_list')
    return render(request, 'products/sku_bundling_form.html')

def sku_bundling_edit(request, pk):
    from .models import ProductsBundling
    bundling = get_object_or_404(ProductsBundling, pk=pk)
    if request.method == 'POST':
        sku_bundling = request.POST.get('sku_bundling', '').strip()
        sku_items_json = request.POST.get('sku_items_json', '[]')
        try:
            items = json.loads(sku_items_json)
        except Exception:
            items = []
        errors = []
        if not sku_bundling:
            errors.append('SKU Bundling wajib diisi.')
        if not items:
            errors.append('Minimal 1 produk harus dipilih.')
        sku_list = ','.join(f"{item['sku']}:{item['jumlah']}" for item in items if item.get('sku') and item.get('jumlah'))
        if not sku_list:
            errors.append('SKU dan jumlah produk tidak valid.')
        if ProductsBundling.objects.filter(sku_bundling=sku_bundling).exclude(pk=pk).exists():
            errors.append('SKU Bundling sudah ada.')
        if errors:
            return render(request, 'products/sku_bundling_form.html', {
                'error': '\n'.join(errors),
                'bundling': bundling,
                'sku_items_json': sku_items_json
            })
        bundling.sku_bundling = sku_bundling
        bundling.sku_list = sku_list
        bundling.save()
        return redirect('products:sku_bundling_list')
    # GET: parse sku_list to items for JS
    items = []
    if bundling.sku_list:
        for s in bundling.sku_list.split(','):
            if ':' in s:
                sku, jumlah = s.split(':', 1)
                items.append({'sku': sku, 'jumlah': int(jumlah)})
    return render(request, 'products/sku_bundling_form.html', {
        'bundling': bundling,
        'sku_items_json': json.dumps(items)
    })

def sku_bundling_delete(request, pk):
    from .models import ProductsBundling
    bundling = get_object_or_404(ProductsBundling, pk=pk)
    if request.method == 'POST':
        bundling.delete()
        return redirect('products:sku_bundling_list')
    # Optional: konfirmasi hapus
    return render(request, 'products/sku_bundling_delete_confirm.html', {'bundling': bundling})
