# Import yang penting dan relevan, diurutkan agar rapi
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.db import IntegrityError, transaction
from django.db.models import Q, ProtectedError, Count, Sum # Tambah Sum untuk agregasi total stok rak
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model # Ganti get_user menjadi get_user_model
import csv, io, os
import pandas as pd
import json
import xlsxwriter
import re # Diperlukan untuk deteksi mobile

# Import Models yang digunakan di views ini
from .models import Product, ProductImportHistory, ProductAddHistory, ProductsBundling, ProductExtraBarcode, EditProductLog
from inventory.models import InventoryRakStock # Diperlukan untuk rak_detail dan rak_data
from inventory.models import Rak # Rak sekarang ada di inventory
from inventory.models import Stock # Diperlukan untuk mendapatkan quantity_putaway dan quantity

# Import yang diperlukan untuk API log
from inventory.models import InventoryRakStockLog # Pastikan ini sudah diimpor
from django.utils import timezone as dj_timezone
from django.db.models import Q # Untuk pencarian

User = get_user_model() # Inisialisasi User model

# === PRODUK MANAGEMENT (Fungsi yang sudah ada) ===

def index(request):
    brands = Product.objects.values_list('brand', flat=True).distinct().order_by('brand')
    variants = Product.objects.values_list('variant_produk', flat=True).distinct().order_by('variant_produk')
    products = Product.objects.filter(is_active=True)
    import_history = ProductImportHistory.objects.order_by('-import_time')[:20]
    return render(request, 'products/index.html', {
        'products': products,
        'import_history': import_history,
        'brands': brands,
        'variants': variants,
    })

@login_required
@permission_required('products.add_product', raise_exception=True)
def import_products(request):
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        filename = file.name
        ext = os.path.splitext(filename)[1].lower()
        rows = []
        if ext == '.csv':
            decoded = file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(decoded))
            rows = list(reader)
        elif ext in ['.xls', '.xlsx']:
            df = pd.read_excel(file, dtype=str)
            df = df.fillna('')
            rows = df.to_dict(orient='records')
        else:
            return redirect('/products/')
        valid_fields = ['sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'panjang_cm', 'lebar_cm', 'tinggi_cm', 'berat_gram']
        total = len(rows)
        inserted = 0
        failed = 0
        failed_notes = []
        batch_size = 500
        created_products = []  # Untuk menyimpan produk yang berhasil dibuat
        
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
                    # Helper function untuk konversi decimal
                    def parse_decimal(value):
                        if value and value.strip():
                            try:
                                return float(value.strip())
                            except ValueError:
                                return None
                        return None
                    
                    # Parse field decimal
                    clean_row['panjang_cm'] = parse_decimal(clean_row.get('panjang_cm'))
                    clean_row['lebar_cm'] = parse_decimal(clean_row.get('lebar_cm'))
                    clean_row['tinggi_cm'] = parse_decimal(clean_row.get('tinggi_cm'))
                    clean_row['berat_gram'] = parse_decimal(clean_row.get('berat_gram'))
                    
                    products.append(Product(**clean_row))
                except Exception as e:
                    failed += 1
                    failed_notes.append(f"Row {i+idx+1}: {e}")
            
            # Bulk create products
            created_products_batch = Product.objects.bulk_create(products, ignore_conflicts=True)
            created_products.extend(created_products_batch)
            inserted += len(created_products_batch)
            request.session['import_progress'] = int((inserted + failed) / total * 100)
        
        # Create logs for all successfully imported products
        log_entries = []
        for product in created_products:
            log_entries.append(EditProductLog(
                product=product,
                edited_by=request.user if request.user.is_authenticated else None,
                field_name='CREATE',
                old_value='',
                new_value=f"Produk baru: {product.sku} - {product.nama_produk}",
                change_type='CREATE',
                notes=f"Produk diimpor dari file {filename}. SKU: {product.sku}, Barcode: {product.barcode}",
                product_sku=product.sku,
                product_name=product.nama_produk,
                product_barcode=product.barcode
            ))
        
        # Bulk create logs
        if log_entries:
            EditProductLog.objects.bulk_create(log_entries)
        
        request.session['import_progress'] = 100
        ProductImportHistory.objects.create(
            file_name=filename,
            notes='\n'.join(failed_notes) if failed_notes else 'Berhasil',
            success_count=inserted,
            failed_count=failed,
            imported_by=request.user if request.user.is_authenticated else None
        )
        return render(request, 'products/import_status.html', {'status': 'Import selesai. Semua data telah diimpor.'})
    return redirect('/products/')

@login_required
@permission_required('products.view_product', raise_exception=True)
def import_progress(request):
    progress = request.session.get('import_progress', 0)
    return JsonResponse({'progress': progress})

def download_template(request):
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet()
    headers = ['sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'rak', 'panjang_cm', 'lebar_cm', 'tinggi_cm', 'berat_gram']
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
    products = Product.objects.all().values('sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'rak', 'panjang_cm', 'lebar_cm', 'tinggi_cm', 'berat_gram')
    df = pd.DataFrame(list(products))
    df = df[['sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'rak', 'panjang_cm', 'lebar_cm', 'tinggi_cm', 'berat_gram']]
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=products.xlsx'
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Products')
    return response

@login_required
@permission_required('products.delete_product', raise_exception=True)
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    try:
        # Catat log delete sebelum menghapus produk
        EditProductLog.objects.create(
            product=product,
            edited_by=request.user if request.user.is_authenticated else None,
            field_name='product',
            old_value=f"SKU: {product.sku}, Nama: {product.nama_produk}, Barcode: {product.barcode}",
            new_value='DELETED',
            change_type='DELETE',
            notes=f"Produk {product.sku} ({product.nama_produk}) dihapus permanen",
            product_sku=product.sku,
            product_name=product.nama_produk,
            product_barcode=product.barcode
        )
        
        product.delete()
        messages.success(request, f"Produk {product.sku} berhasil dihapus permanen.", extra_tags='delete_success')
    except ProtectedError:
        error_message = f"Produk <strong>{product.sku}</strong> tidak dapat dihapus karena terikat dengan data transaksi (misalnya, Inbound atau Order). Untuk menyembunyikannya dari daftar, silakan gunakan opsi <strong>'Non-aktifkan'</strong>."
        messages.error(request, error_message, extra_tags='delete_protected_error')
    return redirect('products:index')

@login_required
@permission_required('products.change_product', raise_exception=True)
def deactivate_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.is_active = False
    product.save()
    messages.info(request, f"Produk {product.sku} telah dinonaktifkan.")
    return redirect('products:index')

@login_required
@permission_required('products.change_product', raise_exception=True)
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        # Helper function untuk konversi decimal
        def parse_decimal(value):
            if value and value.strip() and value.strip() != '':
                try:
                    # Handle comma as decimal separator
                    cleaned_value = value.strip().replace(',', '.')
                    return float(cleaned_value)
                except ValueError:
                    return None
            return None

        # Helper function untuk mencatat perubahan
        def log_field_change(field_name, old_value, new_value):
            if old_value != new_value:
                EditProductLog.objects.create(
                    product=product,
                    edited_by=request.user if request.user.is_authenticated else None,
                    field_name=field_name,
                    old_value=str(old_value) if old_value is not None else '',
                    new_value=str(new_value) if new_value is not None else '',
                    change_type='UPDATE',
                    notes=f"Field {field_name} diubah dari '{old_value}' menjadi '{new_value}'",
                    product_sku=product.sku,
                    product_name=product.nama_produk,
                    product_barcode=product.barcode
                )

        # Simpan nilai lama untuk perbandingan
        old_values = {
            'sku': product.sku,
            'barcode': product.barcode,
            'nama_produk': product.nama_produk,
            'variant_produk': product.variant_produk,
            'brand': product.brand,
            'panjang_cm': product.panjang_cm,
            'lebar_cm': product.lebar_cm,
            'tinggi_cm': product.tinggi_cm,
            'berat_gram': product.berat_gram,
            'posisi_tidur': product.posisi_tidur,
        }

        # Update nilai baru
        new_sku = request.POST.get('sku', product.sku)
        new_barcode = request.POST.get('barcode', product.barcode)
        new_nama_produk = request.POST.get('nama_produk', product.nama_produk)
        new_variant_produk = request.POST.get('variant_produk', product.variant_produk)
        new_brand = request.POST.get('brand', product.brand)
        new_panjang_cm = parse_decimal(request.POST.get('panjang_cm'))
        new_lebar_cm = parse_decimal(request.POST.get('lebar_cm'))
        new_tinggi_cm = parse_decimal(request.POST.get('tinggi_cm'))
        new_berat_gram = parse_decimal(request.POST.get('berat_gram'))
        new_posisi_tidur = request.POST.get('posisi_tidur') == 'on'

        # Log perubahan untuk setiap field
        log_field_change('sku', old_values['sku'], new_sku)
        log_field_change('barcode', old_values['barcode'], new_barcode)
        log_field_change('nama_produk', old_values['nama_produk'], new_nama_produk)
        log_field_change('variant_produk', old_values['variant_produk'], new_variant_produk)
        log_field_change('brand', old_values['brand'], new_brand)
        log_field_change('panjang_cm', old_values['panjang_cm'], new_panjang_cm)
        log_field_change('lebar_cm', old_values['lebar_cm'], new_lebar_cm)
        log_field_change('tinggi_cm', old_values['tinggi_cm'], new_tinggi_cm)
        log_field_change('berat_gram', old_values['berat_gram'], new_berat_gram)
        log_field_change('posisi_tidur', old_values['posisi_tidur'], new_posisi_tidur)

        # Update product
        product.sku = new_sku
        product.barcode = new_barcode
        product.nama_produk = new_nama_produk
        product.variant_produk = new_variant_produk
        product.brand = new_brand
        product.panjang_cm = new_panjang_cm
        product.lebar_cm = new_lebar_cm
        product.tinggi_cm = new_tinggi_cm
        product.berat_gram = new_berat_gram
        product.posisi_tidur = new_posisi_tidur
        
        if request.FILES.get('photo') and hasattr(product, 'photo'):
            product.photo = request.FILES['photo']
        product.save()
        
        # Update capacity untuk semua rak yang memiliki produk ini
        from inventory import rakcapacity
        success, message = rakcapacity.update_rak_capacity_for_product(product_id)
        if not success:
            messages.warning(request, f'Produk berhasil diupdate tapi gagal update capacity: {message}')
        else:
            messages.success(request, f'Produk berhasil diupdate. {message}')
        
        return redirect('products:index')
    return render(request, 'products/edit_product.html', {'product': product})

@csrf_exempt
@login_required
@permission_required('products.change_product', raise_exception=True)
def update_product(request, product_id):
    if request.method == 'POST':
        try:
            p = Product.objects.get(id=product_id)
            data = request.POST
            
            # Helper function untuk konversi decimal
            def parse_decimal(value):
                if value and value.strip():
                    try:
                        return float(value.strip())
                    except ValueError:
                        return None
                return None
            
            # Update field biasa
            for field in ['sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'rak']:
                if field in data:
                    setattr(p, field, data[field])
            
            # Update field decimal dengan parsing
            if 'panjang_cm' in data:
                p.panjang_cm = parse_decimal(data['panjang_cm'])
            if 'lebar_cm' in data:
                p.lebar_cm = parse_decimal(data['lebar_cm'])
            if 'tinggi_cm' in data:
                p.tinggi_cm = parse_decimal(data['tinggi_cm'])
            if 'berat_gram' in data:
                p.berat_gram = parse_decimal(data['berat_gram'])
                
            p.save()
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'msg': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'msg': 'Invalid request'}, status=405)

@csrf_exempt
@login_required
@permission_required('products.delete_product', raise_exception=True)
def delete_import_history(request, history_id):
    if request.method == 'DELETE':
        try:
            ProductImportHistory.objects.filter(id=history_id).delete()
            return JsonResponse({'message': 'Entri berhasil dihapus.'}, status=200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request method.'}, status=405)

@login_required
@permission_required('products.view_product', raise_exception=True)
def import_history_view(request):
    import_history = ProductImportHistory.objects.all().order_by('-import_time')
    return render(request, 'products/import_history.html', {'import_history': import_history})

def products_data(request):
    try:
        draw = int(request.GET.get('draw', 1))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 10))
        search_value = request.GET.get('search[value]', '')
        order_column_index = request.GET.get('order[0][column]', 0)
        order_dir = request.GET.get('order[0][dir]', 'asc')

        columns = ['id', 'photo', 'sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'harga_beli', 'hpp', 'rak_display', None, None]
        
        order_column_name = 'id'
        if int(order_column_index) < len(columns) and columns[int(order_column_index)] is not None:
            order_column_name = columns[int(order_column_index)]

        if order_dir == 'desc':
            order_column = '-' + order_column_name
        else:
            order_column = order_column_name

        queryset = Product.objects.all().annotate(
            extra_barcode_count=Count('extra_barcodes')
        ).distinct()
        total_count = queryset.count()

        import re
        filter_q = Q()
        for idx, col in enumerate(columns):
            if not col: continue
            col_search = request.GET.get(f'columns[{idx}][search][value]', '').strip()
            if col_search:
                # Handle rak_display filter - search in InventoryRakStock
                if col == 'rak_display':
                    # Remove regex pattern if present and use exact match for rak
                    clean_search = col_search.replace('^', '').replace('$', '')
                    if clean_search:
                        # Use exact match to ensure only products in specific rak are shown
                        filter_q &= Q(inventoryrakstock__rak__kode_rak__iexact=clean_search)
                else:
                    # Handle other columns with regex pattern
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
                Q(rak__icontains=search_value) |
                # Search in InventoryRakStock for rak codes
                Q(inventoryrakstock__rak__kode_rak__icontains=search_value)
            )
        
        if filter_q:
            queryset = queryset.filter(filter_q).distinct()
            
        filtered_count = queryset.count()
        
        # Debug logging untuk filter rak
        import logging
        logger = logging.getLogger(__name__)
        for idx, col in enumerate(columns):
            if col == 'rak_display':
                col_search = request.GET.get(f'columns[{idx}][search][value]', '').strip()
                if col_search:
                    clean_search = col_search.replace('^', '').replace('$', '')
                    logger.info(f"Rak filter: '{col_search}' -> clean: '{clean_search}' -> filtered count: {filtered_count}")
                    logger.info(f"Filter query: {filter_q}")
        


        products_page = queryset.order_by(order_column)[start:start+length]

        data = []
        for p in products_page:
            # Ambil data rak dari InventoryRakStock
            rak_stocks = InventoryRakStock.objects.filter(product=p, quantity__gt=0).select_related('rak')
            rak_locations = []
            rak_details = []
            
            for stock in rak_stocks:
                rak_locations.append(stock.rak.kode_rak)
                rak_details.append({
                    'kode_rak': stock.rak.kode_rak,
                    'nama_rak': stock.rak.nama_rak,
                    'quantity': stock.quantity,
                    'quantity_opname': stock.quantity_opname,
                    'lokasi': stock.rak.lokasi,
                    'dimensions': stock.rak.dimensions_display
                })
            
            # Format rak locations untuk display
            rak_display = ', '.join(rak_locations) if rak_locations else p.rak or '-'
            
            data.append({
                'id': p.id,
                'sku': p.sku,
                'barcode': p.barcode,
                'nama_produk': p.nama_produk,
                'variant_produk': p.variant_produk,
                'brand': p.brand,
                'harga_beli': str(p.harga_beli) if p.harga_beli else None,
                'hpp': str(p.hpp) if p.hpp else None,
                'rak': p.rak,  # Keep original rak field for backward compatibility
                'rak_display': rak_display,  # New field for display
                'rak_locations': rak_locations,  # List of rak codes
                'rak_details': rak_details,  # Detailed rak information
                'rak_count': len(rak_locations),  # Number of rak locations
                'panjang_cm': p.panjang_cm,
                'lebar_cm': p.lebar_cm,
                'tinggi_cm': p.tinggi_cm,
                'berat_gram': p.berat_gram,
                'photo': p.photo.url if p.photo else None,
                'has_extra_barcodes': p.extra_barcode_count > 0,
                'extra_barcode_count': p.extra_barcode_count
            })

        return JsonResponse({
            'draw': draw,
            'recordsTotal': total_count,
            'recordsFiltered': filtered_count,
            'data': data
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in products_data: {str(e)}")
        return JsonResponse({
            'draw': int(request.GET.get('draw', 1)),
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': [],
            'error': f'Terjadi kesalahan: {str(e)}'
        }, status=500)

def viewall(request):
    products = Product.objects.all()
    return render(request, 'products/viewall.html', {'products': products})

@login_required
def price_history_all(request):
    """View all price histories from all products"""
    return render(request, 'products/price_history_all.html')

@login_required
def price_history_api(request):
    """API endpoint for price history with pagination and filtering"""
    from purchasing.models import PriceHistory
    from django.db.models import Q, Count, Sum, Avg, F
    from datetime import datetime
    
    # Get pagination parameters
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 50))
    
    # Get filter parameters
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    sku_filter = request.GET.get('sku', '').strip()
    product_filter = request.GET.get('product', '').strip()
    supplier_filter = request.GET.get('supplier', '').strip()
    po_filter = request.GET.get('po', '').strip()
    
    # Build query
    queryset = PriceHistory.objects.select_related(
        'product', 
        'purchase_order', 
        'purchase_order__supplier',
        'supplier'
    ).order_by('-purchase_date')
    
    # Apply filters
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            queryset = queryset.filter(purchase_date__gte=date_from_obj)
        except:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            # To include the entire day, add one day and use __lt
            end_of_day = date_to_obj + datetime.timedelta(days=1)
            queryset = queryset.filter(purchase_date__lt=end_of_day)
        except:
            pass
    
    if sku_filter:
        queryset = queryset.filter(product__sku__icontains=sku_filter)
    if product_filter:
        queryset = queryset.filter(product__nama_produk__icontains=product_filter)
    if supplier_filter:
        queryset = queryset.filter(
            Q(supplier__nama_supplier__icontains=supplier_filter) |
            Q(purchase_order__supplier__nama_supplier__icontains=supplier_filter)
        )
    if po_filter:
        queryset = queryset.filter(purchase_order__nomor_po__icontains=po_filter)
    
    # Get total count
    total_count = queryset.count()
    
    # Pagination
    start = (page - 1) * page_size
    end = start + page_size
    price_histories = queryset[start:end]
    
    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size
    
    # Prepare data
    data = []
    for ph in price_histories:
        data.append({
            'purchase_date': ph.purchase_date.strftime('%d %b %Y'),
            'po_id': ph.purchase_order.id if ph.purchase_order else None,
            'po_nomor': ph.purchase_order.nomor_po if ph.purchase_order else None,
            'sku': ph.product.sku,
            'product_name': ph.product.nama_produk,
            'brand': ph.product.brand,
            'supplier': ph.supplier.nama_supplier if ph.supplier else (ph.purchase_order.supplier.nama_supplier if ph.purchase_order and ph.purchase_order.supplier else None),
            'quantity': ph.quantity,
            'price_formatted': f"{ph.price:,.0f}".replace(',', '.'),
            'subtotal_formatted': f"{ph.subtotal:,.0f}".replace(',', '.'),
        })
    
    # Calculate statistics - Find products with price changes
    # Get all unique SKUs in the filtered dataset
    unique_skus = queryset.values('product__sku').distinct()
    changed_products = 0
    total_change_percent = 0
    
    for sku_data in unique_skus:
        sku = sku_data['product__sku']
        sku_records = queryset.filter(product__sku=sku).order_by('purchase_date')
        
        if sku_records.count() > 1:
            # There are multiple price records for this SKU
            changed_products += 1
            
            # Calculate price change percentage
            first_price = float(sku_records.first().price)
            last_price = float(sku_records.last().price)
            
            if first_price > 0:
                change_percent = ((last_price - first_price) / first_price) * 100
                total_change_percent += change_percent
    
    # Calculate average change
    avg_change = (total_change_percent / changed_products) if changed_products > 0 else 0
    
    # Calculate HPP (Harga Pokok Penjualan) using Weighted Average Method
    # HPP = Total Cost / Total Quantity
    total_cost = queryset.aggregate(total_cost=Sum('subtotal'))['total_cost'] or 0
    total_quantity = queryset.aggregate(total_qty=Sum('quantity'))['total_qty'] or 0
    hpp_weighted_avg = (total_cost / total_quantity) if total_quantity > 0 else 0
    
    # Get min and max price from filtered data
    min_price = queryset.aggregate(min_price=Avg('price'))['min_price'] or 0
    max_price = queryset.aggregate(max_price=Avg('price'))['max_price'] or 0
    
    # Calculate simple average price (for comparison)
    avg_price = queryset.aggregate(avg_price=Avg('price'))['avg_price'] or 0
    
    stats = {
        'total_records': total_count,
        'changed_products': changed_products,
        'avg_change': round(avg_change, 1),
        'hpp_weighted_avg': round(hpp_weighted_avg, 0),
        'total_cost': round(total_cost, 0),
        'total_quantity': int(total_quantity),
        'avg_price': round(avg_price, 0),
    }
    
    return JsonResponse({
        'data': data,
        'total_pages': total_pages,
        'current_page': page,
        'stats': stats
    })

def aggrid_data(request):
    from django.db.models import Q
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 100))
    sort_field = request.GET.get('sort_field', 'id')
    sort_dir = request.GET.get('sort_dir', 'asc')
    filter_fields = ['sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'rak', 'panjang_cm', 'lebar_cm', 'tinggi_cm', 'berat_gram']
    filter_q = Q()
    for field in filter_fields:
        val = request.GET.get(f'filter_{field}', '').strip()
        if val:
            filter_q &= Q(**{f"{field}__icontains": val})
    queryset = Product.objects.filter(filter_q)
    if sort_field in filter_fields + ['id']:
        if sort_dir == 'desc':
            queryset = queryset.order_by(f'-{sort_field}')
        else:
            queryset = queryset.order_by(sort_field)
    else:
        queryset = queryset.order_by('id')
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
            'panjang_cm': p.panjang_cm,
            'lebar_cm': p.lebar_cm,
            'tinggi_cm': p.tinggi_cm,
            'berat_gram': p.berat_gram,
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
            'id': p.id,
            'sku': p.sku or '',
            'barcode': p.barcode or '',
            'nama_produk': p.nama_produk or '',
            'variant_produk': p.variant_produk or '',
            'brand': p.brand or '',
            'panjang_cm': p.panjang_cm,
            'lebar_cm': p.lebar_cm,
            'tinggi_cm': p.tinggi_cm,
            'berat_gram': p.berat_gram,
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

@login_required
@permission_required('products.view_product', raise_exception=True)
def sku_bundling_list(request):
    bundlings_list = ProductsBundling.objects.all().order_by('-id')

    sku_bundling_search = request.GET.get('sku_bundling_search', '').strip()
    sku_list_search = request.GET.get('sku_list_search', '').strip()
    detail_search = request.GET.get('detail_search', '').strip()
    valid_filter = request.GET.get('valid_filter', '')

    if sku_bundling_search:
        bundlings_list = bundlings_list.filter(sku_bundling__icontains=sku_bundling_search)
    if sku_list_search:
        bundlings_list = bundlings_list.filter(sku_list__icontains=sku_list_search)
    
    if detail_search:
        matching_products_skus = Product.objects.filter(
            Q(nama_produk__icontains=detail_search) |
            Q(variant_produk__icontains=detail_search) |
            Q(brand__icontains=detail_search) |
            Q(barcode__icontains=detail_search)
        ).values_list('sku', flat=True)
        
        if matching_products_skus:
            sku_regex = '|'.join(matching_products_skus)
            bundlings_list = bundlings_list.filter(sku_list__iregex=sku_regex)
        else:
            bundlings_list = bundlings_list.none()

    if valid_filter in ['Y', 'N']:
        all_valid_skus_lower = {p.sku.strip().lower() for p in Product.objects.all()}
        filtered_list = []
        for bundling in bundlings_list:
            if not bundling.sku_list:
                if valid_filter == 'N':
                    filtered_list.append(bundling)
                continue

            item_skus = [p.split(':')[0].strip().lower() for p in bundling.sku_list.split(',')]
            is_fully_valid = all(sku in all_valid_skus_lower for sku in item_skus)
            
            if valid_filter == 'Y' and is_fully_valid:
                filtered_list.append(bundling)
            elif valid_filter == 'N' and not is_fully_valid:
                filtered_list.append(bundling)
        
        paginator = Paginator(filtered_list, 100)
    else:
        paginator = Paginator(bundlings_list, 100)

    page = request.GET.get('page')

    try:
        bundlings = paginator.page(page)
    except PageNotAnInteger:
        bundlings = paginator.page(1)
    except EmptyPage:
        bundlings = paginator.page(paginator.num_pages)

    all_skus_on_page_lower = set()
    for bundling in bundlings:
        if bundling.sku_list:
            for item_str in bundling.sku_list.split(','):
                parts = item_str.split(':')
                sku_to_check = parts[0].strip().lower() if len(parts) >= 1 else ""
                if sku_to_check:
                    all_skus_on_page_lower.add(sku_to_check)

    if not all_skus_on_page_lower:
        products_on_page = []
    else:
        sku_regex = r'^(' + '|'.join(all_skus_on_page_lower) + r')$'
        products_on_page = Product.objects.filter(sku__iregex=sku_regex)

    products_map_lower = {p.sku.strip().lower(): p for p in products_on_page}


    for bundling in bundlings:
        parsed_items = []
        if bundling.sku_list:
            for item_str in bundling.sku_list.split(','):
                parts = item_str.split(':')
                item_sku = parts[0].strip()
                item_quantity = parts[1].strip() if len(parts) == 2 else '1'

                product_obj = products_map_lower.get(item_sku.lower())
                is_valid = product_obj is not None

                detail = {
                    'sku': item_sku,
                    'jumlah': item_quantity,
                    'is_valid': is_valid,
                    'product_details': {
                        'nama_produk': product_obj.nama_produk if product_obj else 'N/A',
                        'variant_produk': product_obj.variant_produk if product_obj else 'N/A',
                        'brand': product_obj.brand if product_obj else 'N/A',
                        'barcode': product_obj.barcode if product_obj else 'N/A',
                    } if is_valid else {}
                }
                parsed_items.append(detail)
        bundling.parsed_sku_items = parsed_items

    return render(request, 'products/sku_bundling.html', {
        'bundlings': bundlings,
        'sku_bundling_search': sku_bundling_search,
        'sku_list_search': sku_list_search,
        'detail_search': detail_search,
        'valid_filter': valid_filter,
    })

@login_required
@permission_required('products.add_product', raise_exception=True)
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
        sku_list = ','.join(f"{item['sku']}:{item['jumlah']}" for item in items if item.get('sku') and item.get('jumlah'))
        if not sku_list:
            errors.append('SKU dan jumlah produk tidak valid.')
        from .models import ProductsBundling
        if ProductsBundling.objects.filter(sku_bundling=sku_bundling).exists():
            errors.append('SKU Bundling sudah ada.')
        if errors:
            return render(request, 'products/sku_bundling_form.html', {'error': '\n'.join(errors)})
        ProductsBundling.objects.create(sku_bundling=sku_bundling, sku_list=sku_list)
        return redirect('products:sku_bundling_list')
    return render(request, 'products/sku_bundling_form.html')

@login_required
@permission_required('products.change_product', raise_exception=True)
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

@login_required
@permission_required('products.delete_product', raise_exception=True)
def sku_bundling_delete(request, pk):
    from .models import ProductsBundling
    bundling = get_object_or_404(ProductsBundling, pk=pk)
    if request.method == 'POST':
        bundling.delete()
        return redirect('products:sku_bundling_list')
    return render(request, 'products/sku_bundling_delete_confirm.html', {'bundling': bundling})

@login_required
@permission_required('products.add_product', raise_exception=True)
def add_product(request):
    if request.method == 'POST':
        sku = request.POST.get('sku', '').strip()
        barcode = request.POST.get('barcode', '').strip()

        if not sku:
            messages.error(request, "SKU wajib diisi.")
            return render(request, 'products/add_product.html', {'form_data': request.POST})
        
        if Product.objects.filter(sku=sku).exists():
            messages.error(request, f"Produk dengan SKU '{sku}' sudah ada.")
            return render(request, 'products/add_product.html', {'form_data': request.POST})

        if barcode and Product.objects.filter(barcode=barcode).exists():
            messages.error(request, f"Produk dengan Barcode '{barcode}' sudah ada.")
            return render(request, 'products/add_product.html', {'form_data': request.POST})

        # Helper function untuk konversi decimal
        def parse_decimal(value):
            if value and value.strip():
                try:
                    return float(value.strip())
                except ValueError:
                    return None
            return None

        new_product = Product(
            sku=sku,
            barcode=barcode,
            nama_produk=request.POST.get('nama_produk'),
            variant_produk=request.POST.get('variant_produk'),
            brand=request.POST.get('brand'),
            panjang_cm=parse_decimal(request.POST.get('panjang_cm')),
            lebar_cm=parse_decimal(request.POST.get('lebar_cm')),
            tinggi_cm=parse_decimal(request.POST.get('tinggi_cm')),
            berat_gram=parse_decimal(request.POST.get('berat_gram')),
            posisi_tidur=request.POST.get('posisi_tidur') == 'on',
        )
        if request.FILES.get('photo'):
            new_product.photo = request.FILES['photo']
        
        new_product.save()

        # Log pembuatan produk
        EditProductLog.objects.create(
            product=new_product,
            edited_by=request.user if request.user.is_authenticated else None,
            field_name='CREATE',
            old_value='',
            new_value=f"Produk baru: {sku} - {new_product.nama_produk}",
            change_type='CREATE',
            notes=f"Produk ditambahkan secara manual melalui form. SKU: {sku}, Barcode: {barcode}"
        )

        ProductAddHistory.objects.create(
            product=new_product,
            added_by=request.user if request.user.is_authenticated else None,
            notes=f"Produk ditambahkan secara manual melalui form. SKU: {sku}, Barcode: {barcode}"
        )

        messages.success(request, f"Produk '{new_product.sku}' berhasil ditambahkan.")
        return redirect('products:index')

    return render(request, 'products/add_product.html')

@login_required
@permission_required('products.view_product', raise_exception=True)
def extrabarcode_view(request):
    extra_barcodes = ProductExtraBarcode.objects.select_related('product').all().order_by('product__nama_produk', 'barcode')
    
    context = {
        'extra_barcodes': extra_barcodes,
    }
    return render(request, 'products/extrabarcode.html', context)

@login_required
@permission_required('products.add_product', raise_exception=True)
def extrabarcode_add_view(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        barcodes_from_form = list(set([
            v.strip() for k, v in request.POST.items() if k.startswith('barcode_') and v.strip()
        ]))

        product = None
        if product_id:
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                messages.error(request, "Produk yang dipilih tidak valid.")
                return render(request, 'products/extrabarcode_tambah.html')
        else:
            messages.error(request, "Produk harus dipilih terlebih dahulu.")
            return render(request, 'products/extrabarcode_tambah.html')

        if not barcodes_from_form:
            messages.error(request, "Minimal satu barcode tambahan harus diisi.")
            context = {'selected_product': product}
            return render(request, 'products/extrabarcode_tambah.html', context)

        existing_main_barcodes = set(Product.objects.filter(barcode__in=barcodes_from_form).values_list('barcode', flat=True))
        existing_extra_barcodes = set(ProductExtraBarcode.objects.filter(barcode__in=barcodes_from_form).values_list('barcode', flat=True))
        
        all_db_barcodes = existing_main_barcodes.union(existing_extra_barcodes)

        errors = []
        valid_barcodes_to_add = []
        for barcode in barcodes_from_form:
            if barcode in all_db_barcodes:
                errors.append(f"Barcode '{barcode}' sudah terdaftar di database.")
            else:
                valid_barcodes_to_add.append(barcode)

        if errors:
            for error in errors:
                messages.error(request, error)
            context = {
                'selected_product': product,
                'submitted_barcodes': barcodes_from_form
            }
            return render(request, 'products/extrabarcode_tambah.html', context)
        
        try:
            with transaction.atomic():
                for barcode in valid_barcodes_to_add:
                    ProductExtraBarcode.objects.create(product=product, barcode=barcode)
            messages.success(request, f"{len(valid_barcodes_to_add)} barcode tambahan berhasil disimpan untuk produk {product.sku}.")
            return redirect('products:extrabarcode_view')
        except IntegrityError as e:
            messages.error(request, f"Terjadi kesalahan database: {e}")
            context = {
                'selected_product': product,
                'submitted_barcodes': barcodes_from_form
            }
            return render(request, 'products/extrabarcode_tambah.html', context)

    return render(request, 'products/extrabarcode_tambah.html')

@require_POST
@login_required
@permission_required('products.delete_product', raise_exception=True)
def delete_extra_barcode(request, barcode_id):
    extra = get_object_or_404(ProductExtraBarcode, id=barcode_id)
    product_id = extra.product.id
    extra.delete()
    messages.success(request, "Extra barcode berhasil dihapus.")
    return redirect('products:extrabarcode_view')

@login_required
@permission_required('products.view_product', raise_exception=True)
def extrabarcode_data(request):
    try:
        draw = int(request.GET.get('draw', 1))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 10))
        search_value = request.GET.get('search[value]', '').strip()
        
        order_column_index = int(request.GET.get('order[0][column]', 0))
        order_dir = request.GET.get('order[0][dir]', 'asc')
        
        columns = ['id', 'product__sku', 'product__nama_produk', 'barcode']
        order_column_name = columns[order_column_index] if order_column_index < len(columns) else 'id'

        if order_dir == 'desc':
            order_column = f'-{order_column_name}'
        else:
            order_column = order_column_name

        queryset = ProductExtraBarcode.objects.select_related('product').all()
        total_count = queryset.count()

        from django.db.models import Q
        
        if search_value:
            queryset = queryset.filter(
                Q(product__sku__icontains=search_value) |
                Q(product__nama_produk__icontains=search_value) |
                Q(barcode__icontains=search_value)
            )

        for idx, col_name in enumerate(columns):
            col_search = request.GET.get(f'columns[{idx}][search][value]', '').strip()
            if col_search:
                queryset = queryset.filter(**{f'{col_name}__icontains': col_search})

        filtered_count = queryset.count()
        
        barcodes_page = queryset.order_by(order_column)[start:start + length]

        data = []
        for item in barcodes_page:
            data.append({
                'id': item.id,
                'product_sku': item.product.sku,
                'product_name': item.product.nama_produk,
                'barcode': item.barcode,
            })

        return JsonResponse({
            'draw': draw,
            'recordsTotal': total_count,
            'recordsFiltered': filtered_count,
            'data': data,
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in extrabarcode_data: {str(e)}")
        return JsonResponse({
            'draw': int(request.GET.get('draw', 1)),
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': [],
            'error': f'Terjadi kesalahan: {str(e)}'
        }, status=500)

@require_GET
@login_required
@permission_required('products.view_product', raise_exception=True)
def get_product_extra_barcodes(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
        extra_barcodes = ProductExtraBarcode.objects.filter(product=product).values('id', 'barcode') 
        return JsonResponse({'success': True, 'extra_barcodes': list(extra_barcodes)})
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Produk tidak ditemukan.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@permission_required('products.add_product', raise_exception=True)
def add_extra_barcode(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        # Support both JSON and Form POST
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            product_id = data.get('product_id')
            barcode_value = data.get('barcode_value')
        else:
            # Form POST - get product_id from query string (safe from formatting issues)
            product_id = request.GET.get('product_id') or request.POST.get('product_id')
            barcode_value = request.POST.get('barcode_value')
        
        # Clean product_id (remove any dots, commas, or non-digit characters)
        if product_id:
            product_id = str(product_id).replace('.', '').replace(',', '').strip()
            # Convert to int to validate it's a number
            try:
                product_id = int(product_id)
            except (ValueError, TypeError):
                error_msg = f'Product ID tidak valid: {product_id}'
                if request.content_type == 'application/json':
                    return JsonResponse({'success': False, 'error': error_msg}, status=400)
                else:
                    messages.error(request, error_msg)
                    return redirect('products:index')
        
        if barcode_value:
            barcode_value = barcode_value.strip()

        if not product_id or not barcode_value:
            if request.content_type == 'application/json':
                return JsonResponse({'success': False, 'error': 'Product ID dan Barcode diperlukan.'}, status=400)
            else:
                messages.error(request, 'Product ID dan Barcode diperlukan.')
                return redirect('products:edit_product', pk=product_id) if product_id else redirect('products:index')

        product = Product.objects.get(id=product_id)

        if Product.objects.filter(barcode=barcode_value).exists():
            error_msg = 'Barcode ini sudah menjadi barcode utama produk lain.'
            if request.content_type == 'application/json':
                return JsonResponse({'success': False, 'error': error_msg}, status=400)
            else:
                messages.error(request, error_msg)
                return redirect('products:edit_product', pk=product_id)

        if ProductExtraBarcode.objects.filter(barcode=barcode_value).exists(): 
            error_msg = 'Barcode ini sudah terdaftar sebagai extra barcode.'
            if request.content_type == 'application/json':
                return JsonResponse({'success': False, 'error': error_msg}, status=400)
            else:
                messages.error(request, error_msg)
                return redirect('products:edit_product', pk=product_id)

        ProductExtraBarcode.objects.create(product=product, barcode=barcode_value) 
        
        if request.content_type == 'application/json':
            return JsonResponse({'success': True, 'message': 'Extra barcode berhasil ditambahkan.'})
        else:
            messages.success(request, f'Extra barcode "{barcode_value}" berhasil ditambahkan!')
            return redirect('products:edit_product', pk=product_id)

    except Product.DoesNotExist:
        error_msg = 'Produk tidak ditemukan.'
        if request.content_type == 'application/json':
            return JsonResponse({'success': False, 'error': error_msg}, status=404)
        else:
            messages.error(request, error_msg)
            return redirect('products:index')
    except Exception as e:
        error_msg = str(e)
        if request.content_type == 'application/json':
            return JsonResponse({'success': False, 'error': error_msg}, status=500)
        else:
            messages.error(request, error_msg)
            return redirect('products:edit_product', pk=product_id) if product_id else redirect('products:index')

@login_required
@permission_required('products.delete_product', raise_exception=True)
def api_delete_extra_barcode(request, barcode_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        extra_barcode = ProductExtraBarcode.objects.get(id=barcode_id)
        product_id = extra_barcode.product.id
        barcode_value = extra_barcode.barcode
        extra_barcode.delete()
        
        if request.content_type == 'application/json':
            return JsonResponse({'success': True, 'message': 'Extra barcode berhasil dihapus.'})
        else:
            messages.success(request, f'Extra barcode "{barcode_value}" berhasil dihapus!')
            return redirect('products:edit_product', pk=product_id)
    except ProductExtraBarcode.DoesNotExist:
        error_msg = 'Extra barcode tidak ditemukan.'
        if request.content_type == 'application/json':
            return JsonResponse({'success': False, 'error': error_msg}, status=404)
        else:
            messages.error(request, error_msg)
            return redirect('products:index')
    except Exception as e:
        error_msg = str(e)
        if request.content_type == 'application/json':
            return JsonResponse({'success': False, 'error': error_msg}, status=500)
        else:
            messages.error(request, error_msg)
            return redirect('products:index')

def add_history_view(request):
    add_history = ProductAddHistory.objects.select_related('product', 'added_by').all().order_by('-added_at')
    
    paginator = Paginator(add_history, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'add_history': page_obj,
    }
    return render(request, 'products/add_history.html', context)

@login_required
@permission_required('products.add_product', raise_exception=True)
def import_sku_bundling(request):
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        filename = file.name
        ext = os.path.splitext(filename)[1].lower()
        
        if ext not in ['.xls', '.xlsx']:
            messages.error(request, "Format file tidak didukung. Harap unggah file .xls atau .xlsx.")
            return redirect('products:sku_bundling_list')

        try:
            df = pd.read_excel(file, dtype=str)
            df = df.fillna('')
            rows = df.to_dict(orient='records')
        except Exception as e:
            messages.error(request, f"Gagal membaca file Excel: {e}")
            return redirect('products:sku_bundling_list')

        total = len(rows)
        inserted = 0
        failed = 0
        failed_notes = []
        
        bundlings_to_create = []
        existing_sku_bundlings = set(ProductsBundling.objects.values_list('sku_bundling', flat=True))
        
        for idx, row in enumerate(rows):
            sku_bundling_name = row.get('sku_bundling', '').strip()
            
            if not sku_bundling_name:
                failed += 1
                failed_notes.append(f"Row {idx+1}: SKU Bundling nama kosong.")
                continue

            if sku_bundling_name in existing_sku_bundlings:
                failed += 1
                failed_notes.append(f"Row {idx+1}: SKU Bundling '{sku_bundling_name}' sudah ada.")
                continue
            
            sku_items = []
            for i in range(1, 11):
                sku_col = f'sku_item_{i}'
                qty_col = f'quantity_item_{i}'
                
                sku = row.get(sku_col, '').strip()
                qty = row.get(qty_col, '').strip()

                if sku and qty:
                    try:
                        qty_int = int(qty)
                        if qty_int <= 0:
                            raise ValueError("Quantity must be positive.")
                        sku_items.append(f"{sku}:{qty_int}")
                    except ValueError:
                        failed += 1
                        failed_notes.append(f"Row {idx+1}: Jumlah untuk SKU '{sku}' tidak valid.")
                        break
            
            if not sku_items and not any(f"Row {idx+1}" in note for note in failed_notes):
                failed += 1
                failed_notes.append(f"Row {idx+1}: Tidak ada SKU item yang valid ditemukan.")
                continue
            
            if not any(f"Row {idx+1}" in note for note in failed_notes):
                bundlings_to_create.append(
                    ProductsBundling(
                        sku_bundling=sku_bundling_name,
                        sku_list=','.join(sku_items)
                    )
                )
                existing_sku_bundlings.add(sku_bundling_name)

        try:
            with transaction.atomic():
                unique_bundlings = {}
                for bundle in bundlings_to_create:
                    if bundle.sku_bundling not in unique_bundlings:
                        unique_bundlings[bundle.sku_bundling] = bundle
                    else:
                        failed += 1
                        failed_notes.append(f"SKU Bundling '{bundle.sku_bundling}' adalah duplikat dalam file.")
                
                final_bundlings_to_create = list(unique_bundlings.values())
                
                ProductsBundling.objects.bulk_create(final_bundlings_to_create, ignore_conflicts=True)
                
                inserted = len(final_bundlings_to_create)

        except IntegrityError as e:
            messages.error(request, f"Terjadi kesalahan integritas database saat mengimpor: {e}")
            failed_notes.append(f"Kesalahan database: {e}")
            failed = total - inserted
        except Exception as e:
            messages.error(request, f"Terjadi kesalahan tidak terduga saat mengimpor: {e}")
            failed_notes.append(f"Kesalahan tidak terduga: {e}")
            failed = total - inserted


        ProductImportHistory.objects.create(
            file_name=filename,
            notes='\n'.join(failed_notes) if failed_notes else 'Berhasil',
            success_count=inserted,
            failed_count=failed,
            imported_by=request.user if request.user.is_authenticated else None
        )
        
        messages.success(request, f"Impor SKU Bundling selesai. Berhasil: {inserted}, Gagal: {failed}.")
        if failed_notes:
            messages.warning(request, "Beberapa entri gagal. Lihat catatan impor untuk detail.")
            
        return redirect('products:sku_bundling_list')
        
    return render(request, 'products/sku_bundling_import_form.html')


def download_sku_bundling_template(request):
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('SKU Bundling Template')

    headers = ['sku_bundling']
    for i in range(1, 11):
        headers.append(f'sku_item_{i}')
        headers.append(f'quantity_item_{i}')

    for col_num, header in enumerate(headers):
        worksheet.write(0, col_num, header)

    workbook.close()
    output.seek(0)

    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=template_import_sku_bundling.xlsx'
    return response
    """
    Menampilkan daftar rak
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = re.search(r'mobile|android|iphone', user_agent)
    
    template_name = 'products/rak_mobile.html' if is_mobile else 'products/rak_list.html'
    
    raks = Rak.objects.all().order_by('kode_rak')
    
    context = {
        'raks': raks,
        'total_raks': raks.count(),
    }
    return render(request, template_name, context)

@require_POST # Pastikan hanya menerima POST request
@csrf_exempt # Izinkan AJAX POST tanpa CSRF token jika diperlukan (tapi lebih baik kirim CSRF dari frontend)
def rak_add(request):
    """
    Tambah rak baru via AJAX.
    Mengembalikan JSON response.
    """
    try:
        # Ambil data dari request.POST
        # Gunakan get() dengan default None untuk field opsional
        kode_rak = request.POST.get('kode_rak', '').strip()
        nama_rak = request.POST.get('nama_rak', '').strip()
        panjang_cm = request.POST.get('panjang_cm')
        lebar_cm = request.POST.get('lebar_cm')
        tinggi_cm = request.POST.get('tinggi_cm')
        kapasitas_kg = request.POST.get('kapasitas_kg')
        lokasi = request.POST.get('lokasi', '').strip()
        keterangan = request.POST.get('keterangan', '').strip()
        
        # Validasi dasar
        if not kode_rak:
            return JsonResponse({'success': False, 'error': 'Kode rak wajib diisi!'}, status=400)
        if not nama_rak:
            return JsonResponse({'success': False, 'error': 'Nama rak wajib diisi!'}, status=400)
        
        # Cek duplikasi kode_rak
        if Rak.objects.filter(kode_rak__iexact=kode_rak).exists():
            return JsonResponse({'success': False, 'error': f'Kode rak "{kode_rak}" sudah ada.'}, status=400)

        # Convert to float/Decimal (biarkan None jika kosong)
        # Gunakan try-except untuk konversi agar tidak error jika input tidak valid
        try:
            panjang_cm = float(panjang_cm) if panjang_cm else None
            lebar_cm = float(lebar_cm) if lebar_cm else None
            tinggi_cm = float(tinggi_cm) if tinggi_cm else None
            kapasitas_kg = float(kapasitas_kg) if kapasitas_kg else None
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Dimensi atau kapasitas harus berupa angka.'}, status=400)
        
        # Buat objek Rak baru
        with transaction.atomic(): # Pastikan operasi ini atomik
            rak = Rak.objects.create(
                kode_rak=kode_rak,
                nama_rak=nama_rak,
                panjang_cm=panjang_cm,
                lebar_cm=lebar_cm,
                tinggi_cm=tinggi_cm,
                kapasitas_kg=kapasitas_kg,
                lokasi=lokasi,
                keterangan=keterangan,
            )
        
        # Mengembalikan response sukses
        return JsonResponse({'success': True, 'message': f'Rak {rak.kode_rak} berhasil ditambahkan.'})
            
    except Exception as e:
        # Menangkap error umum lainnya
        return JsonResponse({'success': False, 'error': f'Terjadi kesalahan: {str(e)}'}, status=500)

@csrf_exempt # Izinkan AJAX POST/GET tanpa CSRF token jika diperlukan (tapi lebih baik kirim CSRF dari frontend)
def rak_edit(request, rak_id):
    """
    Mengambil data rak untuk form edit (GET) atau menyimpan perubahan rak (POST) via AJAX.
    Mengembalikan JSON response.
    """
    rak = get_object_or_404(Rak, id=rak_id)

    if request.method == 'POST':
        try:
            # Ambil data dari request.POST
            kode_rak = request.POST.get('kode_rak', '').strip()
            nama_rak = request.POST.get('nama_rak', '').strip()
            panjang_cm = request.POST.get('panjang_cm')
            lebar_cm = request.POST.get('lebar_cm')
            tinggi_cm = request.POST.get('tinggi_cm')
            kapasitas_kg = request.POST.get('kapasitas_kg')
            lokasi = request.POST.get('lokasi', '').strip()
            keterangan = request.POST.get('keterangan', '').strip()

            # Validasi dasar
            if not kode_rak:
                return JsonResponse({'success': False, 'error': 'Kode rak wajib diisi!'}, status=400)
            if not nama_rak:
                return JsonResponse({'success': False, 'error': 'Nama rak wajib diisi!'}, status=400)

            # Cek duplikasi kode_rak, kecuali untuk rak yang sedang diedit
            if Rak.objects.filter(kode_rak__iexact=kode_rak).exclude(id=rak_id).exists():
                return JsonResponse({'success': False, 'error': f'Kode rak "{kode_rak}" sudah ada.'}, status=400)

            # Convert to float/Decimal (biarkan None jika kosong)
            try:
                panjang_cm = float(panjang_cm) if panjang_cm else None
                lebar_cm = float(lebar_cm) if lebar_cm else None
                tinggi_cm = float(tinggi_cm) if tinggi_cm else None
                kapasitas_kg = float(kapasitas_kg) if kapasitas_kg else None
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Dimensi atau kapasitas harus berupa angka yang valid.'}, status=400)

            with transaction.atomic():
                rak.kode_rak = kode_rak
                rak.nama_rak = nama_rak
                rak.panjang_cm = panjang_cm
                rak.lebar_cm = lebar_cm
                rak.tinggi_cm = tinggi_cm
                rak.kapasitas_kg = kapasitas_kg
                rak.lokasi = lokasi
                rak.keterangan = keterangan
                rak.save()

            return JsonResponse({'success': True, 'message': 'Rak berhasil diperbarui!'})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    # Untuk GET request: Kirim data Rak saat ini untuk diisi di form modal
    else:
        rak_data = {
            'id': rak.id,
            'kode_rak': rak.kode_rak,
            'nama_rak': rak.nama_rak,
            'panjang_cm': str(rak.panjang_cm) if rak.panjang_cm is not None else '',
            'lebar_cm': str(rak.lebar_cm) if rak.lebar_cm is not None else '',
            'tinggi_cm': str(rak.tinggi_cm) if rak.tinggi_cm is not None else '',
            'kapasitas_kg': str(rak.kapasitas_kg) if rak.kapasitas_kg is not None else '',
            'lokasi': rak.lokasi,
            'keterangan': rak.keterangan,
        }
        return JsonResponse({'success': True, 'rak': rak_data})

@require_POST # Pastikan hanya menerima POST request
@csrf_exempt # Izinkan AJAX POST tanpa CSRF token jika diperlukan
def rak_delete(request, rak_id):
    """
    Menghapus rak via AJAX.
    Mengembalikan JSON response.
    """
    rak = get_object_or_404(Rak, id=rak_id)
    try:
        with transaction.atomic():
            rak.delete()
        return JsonResponse({'success': True, 'message': 'Rak berhasil dihapus.'})
    except ProtectedError:
        return JsonResponse({'success': False, 'error': 'Rak tidak dapat dihapus karena masih terkait dengan stok atau transaksi lain.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def rak_detail(request, rak_id):
    """
    Menampilkan detail rak, termasuk daftar produk yang ada di rak tersebut.
    Ini akan menjadi halaman terpisah untuk melihat isi rak secara spesifik.
    """
    rak = get_object_or_404(Rak.objects.annotate(
        total_stok_di_rak=Sum('inventoryrakstock__quantity', distinct=True, default=0)
    ), id=rak_id)
    
    # Ambil semua stok di rak ini
    stok_di_rak = InventoryRakStock.objects.filter(rak=rak).select_related('product')

    context = {
        'rak': rak,
        'stok_di_rak': stok_di_rak,
    }
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = re.search(r'mobile|android|iphone', user_agent)
    template_name = 'products/rak_detail_mobile.html' if is_mobile else 'products/rak_detail.html'
    return render(request, template_name, context)

@require_GET
def rak_data(request):
    """
    Data rak untuk DataTables
    """
    try:
        draw = int(request.GET.get('draw', 1))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 10))
        search_value = request.GET.get('search[value]', '')
        
        queryset = Rak.objects.all()
        total_records = queryset.count()
        
        if search_value:
            queryset = queryset.filter(
                Q(kode_rak__icontains=search_value) |
                Q(nama_rak__icontains=search_value) |
                Q(lokasi__icontains=search_value)
            )
        
        filtered_records = queryset.count()
        
        order_column = request.GET.get('order[0][column]', '0')
        order_dir = request.GET.get('order[0][dir]', 'asc')
        
        order_fields = ['kode_rak', 'nama_rak', 'lokasi', 'created_at']
        if order_column.isdigit() and int(order_column) < len(order_fields):
            order_field = order_fields[int(order_column)]
            if order_dir == 'desc':
                order_field = f'-{order_field}'
            queryset = queryset.order_by(order_field)
        
        queryset = queryset[start:start + length]
        
        data = []
        for rak in queryset:
            total_stok = InventoryRakStock.objects.filter(rak=rak).aggregate(
                total=Sum('quantity')
            )['total'] or 0
            
            # Format kapasitas agar lebih mudah dibaca
            kapasitas_formatted = '-'
            if rak.kapasitas_kg:
                if rak.kapasitas_kg == int(rak.kapasitas_kg):
                    # Jika tidak ada desimal, tampilkan tanpa desimal
                    kapasitas_formatted = f"{int(rak.kapasitas_kg):,} kg"
                else:
                    # Jika ada desimal, tampilkan dengan desimal (tanpa trailing zeros)
                    kapasitas_formatted = f"{rak.kapasitas_kg:g} kg"
            
            data.append({
                'id': rak.id,
                'kode_rak': rak.kode_rak,
                'nama_rak': rak.nama_rak,
                'lokasi': rak.lokasi or '-',
                'dimensi': f"{rak.panjang_cm or '-'} x {rak.lebar_cm or '-'} x {rak.tinggi_cm or '-'} cm",
                'kapasitas': kapasitas_formatted,
                'total_stok': total_stok,
                'created_at': rak.created_at.strftime('%d-%m-%Y %H:%M'),
                'actions': f'''
                    <a href="{reverse('products:rak_stock_detail', args=[rak.id])}" class="btn btn-sm btn-info me-1">
                        <i class="bi bi-eye"></i> Detail
                    </a>
                    <button type="button" class="btn btn-sm btn-warning me-1" data-bs-toggle="modal" data-bs-target="#editRakModal" data-id="{rak.id}">
                        <i class="bi bi-pencil"></i> Edit
                    </button>
                    <button type="button" class="btn btn-sm btn-danger" data-id="{rak.id}" data-kode="{rak.kode_rak}">
                        <i class="bi bi-trash"></i> Delete
                    </button>
                '''
            })
        
        return JsonResponse({
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': filtered_records,
            'data': data,
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def rak_stock_detail(request, rak_id):
    """
    Menampilkan dashboard detail stok di rak spesifik.
    """
    rak = get_object_or_404(Rak, id=rak_id)
    
    # Ambil semua stok di rak ini
    stok_di_rak = InventoryRakStock.objects.filter(rak=rak).select_related('product').order_by('product__nama_produk')
    
    context = {
        'rak': rak,
        'stok_di_rak': stok_di_rak,
    }
    
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = re.search(r'mobile|android|iphone', user_agent)
    template_name = 'products/rak_stock_detail_mobile.html' if is_mobile else 'products/rak_stock_detail.html'
    
    return render(request, template_name, context)



@require_GET
def api_get_product_rak_stock(request):
    """
    API untuk mendapatkan data stok produk di berbagai rak berdasarkan SKU atau Barcode.
    """
    query = request.GET.get('query', '').strip()
    
    if not query:
        return JsonResponse({'success': False, 'error': 'SKU atau Barcode produk diperlukan.'}, status=400)
    
    try:
        # Cari produk berdasarkan SKU atau Barcode (termasuk extra barcodes)
        product = Product.objects.filter(
            Q(sku__iexact=query) | Q(barcode__iexact=query) | Q(extra_barcodes__barcode__iexact=query)
        ).distinct().first() # Gunakan .first() karena kita hanya butuh 1 produk

        if not product:
            return JsonResponse({'success': False, 'error': 'Produk tidak ditemukan.'}, status=404)
        
        # Ambil semua entri InventoryRakStock untuk produk ini
        rak_stock_items = InventoryRakStock.objects.filter(product=product).select_related('rak').order_by('rak__kode_rak')
        
        data = []
        total_qty_di_rak = 0
        for item in rak_stock_items:
            data.append({
                'rak_id': item.rak.id,
                'kode_rak': item.rak.kode_rak,
                'nama_rak': item.rak.nama_rak,
                'lokasi_rak': item.rak.lokasi or '-',
                'quantity': item.quantity,
            })
            total_qty_di_rak += item.quantity
        
        # Ambil juga total quantity_putaway dan quantity dari Stock model
        try:
            stock_data = Stock.objects.get(product=product)
            quantity_putaway = stock_data.quantity_putaway
            quantity_ready = stock_data.quantity
        except Stock.DoesNotExist:
            quantity_putaway = 0
            quantity_ready = 0

        return JsonResponse({
            'success': True,
            'product_info': {
                'id': product.id,
                'sku': product.sku,
                'nama_produk': product.nama_produk,
                'barcode': product.barcode,
                'quantity_putaway': quantity_putaway,
                'quantity_ready': quantity_ready,
                'total_qty_di_rak': total_qty_di_rak, # Total yang tersebar di rak
            },
            'rak_locations': data,
            'message': 'Data stok produk berhasil ditemukan.'
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Terjadi kesalahan: {str(e)}'}, status=500)

@require_GET
@login_required
@permission_required('products.view_product', raise_exception=True)
def api_rak_stock_log_data(request, rak_id):
    """
    Menyediakan data InventoryRakStockLog untuk DataTables (server-side processing).
    """
    try:
        draw = int(request.GET.get('draw', 0))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 25)) # Default 25 per halaman

        # Filter berdasarkan rak_id
        queryset = InventoryRakStockLog.objects.filter(rak_id=rak_id).select_related('produk', 'rak', 'user').all()

        total_records = queryset.count()

        # Search
        search_value = request.GET.get('search[value]', '')
        if search_value:
            queryset = queryset.filter(
                Q(produk__sku__icontains=search_value) |
                Q(produk__nama_produk__icontains=search_value) |
                Q(tipe_pergerakan__icontains=search_value) |
                Q(catatan__icontains=search_value) |
                Q(user__username__icontains=search_value)
            )
        
        # Column ordering
        order_column_index = request.GET.get('order[0][column]', '0')
        order_dir = request.GET.get('order[0][dir]', 'desc')

        # Mapping kolom DataTables ke field model
        column_mapping = {
            '0': 'waktu_buat',
            '1': 'produk__nama_produk',
            '2': 'produk__sku',
            '3': 'qty',
            '4': 'qty_awal',
            '5': 'qty_akhir',
            '6': 'tipe_pergerakan',
            '7': 'user__username',
            '8': 'catatan',
        }
        order_by_field = column_mapping.get(order_column_index, 'waktu_buat')
        if order_dir == 'desc':
            order_by_field = f'-{order_by_field}'
        
        queryset = queryset.order_by(order_by_field)

        filtered_records = queryset.count()

        # Pagination
        queryset = queryset[start:start + length]

        data = []
        jakarta_tz = dj_timezone.get_current_timezone()

        for log_entry in queryset:
            data.append({
                'waktu_buat': dj_timezone.localtime(log_entry.waktu_buat, jakarta_tz).strftime('%Y-%m-%d %H:%M:%S') if log_entry.waktu_buat else '',
                'produk__nama_produk': log_entry.produk.nama_produk if log_entry.produk else '',
                'produk__sku': log_entry.produk.sku if log_entry.produk else '',
                'qty': log_entry.qty,
                'qty_awal': log_entry.qty_awal,
                'qty_akhir': log_entry.qty_akhir,
                'tipe_pergerakan_display': log_entry.get_tipe_pergerakan_display(), # Menggunakan get_FOO_display() untuk choices
                'user__username': log_entry.user.username if log_entry.user else '-',
                'catatan': log_entry.catatan or '',
            })

        return JsonResponse({
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': filtered_records,
            'data': data,
        })

    except Exception as e:
        return JsonResponse({'draw': int(request.GET.get('draw', 0)), 'recordsTotal': 0, 'recordsFiltered': 0, 'data': [], 'error': str(e)}, status=500)

def rak_stock(request):
    """
    View untuk menampilkan tabel stok dari semua rak dan produk
    """
    return render(request, 'products/rak_stock.html')

@require_GET
def rak_stock_data(request):
    """
    API untuk mendapatkan data stok dari semua rak dan produk untuk DataTables (Server Side)
    """
    try:
        # Check if this is a request for rak options
        if request.GET.get('get_rak_options'):
            # Get all raks that have stock - simpler approach
            from inventory.models import Rak
            rak_options = Rak.objects.filter(
                inventoryrakstock__quantity__gt=0
            ).distinct().values('kode_rak', 'nama_rak').order_by('kode_rak')
            
            return JsonResponse({
                'rak_options': list(rak_options)
            })
        
        # DataTables parameters
        draw = int(request.GET.get('draw', 1))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 25))
        search_value = request.GET.get('search[value]', '')
        
        # Ordering
        order_column = request.GET.get('order[0][column]', '1')  # Default sort by kode_rak
        order_dir = request.GET.get('order[0][dir]', 'asc')
        
        # Column mapping
        columns = [
            'id', 'kode_rak', 'nama_rak', 'lokasi_rak', 
            'sku', 'barcode', 'brand', 'nama_produk', 'variant_produk',
            'quantity', 'quantity', 'last_updated'
        ]
        
        # Base queryset
        rak_stocks = InventoryRakStock.objects.select_related(
            'rak', 'product'
        ).filter(
            quantity__gt=0  # Hanya tampilkan yang ada stoknya
        )
        
        # Filter for specific rak
        rak_filter = request.GET.get('rak_filter', '')
        if rak_filter:
            rak_stocks = rak_stocks.filter(rak__kode_rak=rak_filter)
        
        # Filter for stock levels
        filter_type = request.GET.get('filter', '')
        if filter_type == 'low_stock':
            rak_stocks = rak_stocks.filter(quantity__lte=10)
        elif filter_type == 'medium_stock':
            rak_stocks = rak_stocks.filter(quantity__gt=10, quantity__lte=50)
        elif filter_type == 'high_stock':
            rak_stocks = rak_stocks.filter(quantity__gt=50)
        
        # Search functionality
        if search_value:
            rak_stocks = rak_stocks.filter(
                Q(rak__kode_rak__icontains=search_value) |
                Q(rak__nama_rak__icontains=search_value) |
                Q(rak__lokasi__icontains=search_value) |
                Q(product__sku__icontains=search_value) |
                Q(product__nama_produk__icontains=search_value) |
                Q(product__brand__icontains=search_value) |
                Q(product__barcode__icontains=search_value) |
                Q(product__variant_produk__icontains=search_value) |
                Q(quantity__icontains=search_value)
            )
        
        # Total records before filtering
        total_records = InventoryRakStock.objects.filter(quantity__gt=0).count()
        
        # Total records after filtering
        filtered_records = rak_stocks.count()
        
        # Ordering
        if order_column and order_column.isdigit():
            column_index = int(order_column)
            if column_index < len(columns):
                order_field = columns[column_index]
                if order_field == 'kode_rak':
                    order_field = 'rak__kode_rak'
                elif order_field == 'nama_rak':
                    order_field = 'rak__nama_rak'
                elif order_field == 'lokasi_rak':
                    order_field = 'rak__lokasi'
                elif order_field == 'sku':
                    order_field = 'product__sku'
                elif order_field == 'nama_produk':
                    order_field = 'product__nama_produk'
                elif order_field == 'brand':
                    order_field = 'product__brand'
                elif order_field == 'barcode':
                    order_field = 'product__barcode'
                elif order_field == 'variant_produk':
                    order_field = 'product__variant_produk'
                elif order_field == 'last_updated':
                    order_field = 'updated_at'
                
                if order_dir == 'desc':
                    order_field = '-' + order_field
                
                rak_stocks = rak_stocks.order_by(order_field)
        
        # Pagination
        rak_stocks = rak_stocks[start:start + length]
        
        # Prepare data
        data = []
        for stock in rak_stocks:
            data.append({
                'id': stock.id,
                'kode_rak': stock.rak.kode_rak if stock.rak else '-',
                'nama_rak': stock.rak.nama_rak if stock.rak else '-',
                'lokasi_rak': stock.rak.lokasi if stock.rak and stock.rak.lokasi else '-',
                'sku': stock.product.sku if stock.product else '-',
                'barcode': stock.product.barcode if stock.product else '-',
                'brand': stock.product.brand if stock.product else '-',
                'nama_produk': stock.product.nama_produk if stock.product else '-',
                'variant_produk': stock.product.variant_produk if stock.product else '-',
                'quantity': stock.quantity,
                'last_updated': stock.updated_at.strftime('%d/%m/%Y %H:%M') if stock.updated_at else '-',
            })
        
        return JsonResponse({
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': filtered_records,
            'data': data
        })
        
    except Exception as e:
        return JsonResponse({
            'draw': int(request.GET.get('draw', 1)),
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': [],
            'error': str(e)
        }, status=500)

@require_GET
def rak_stock_summary(request):
    """
    API untuk mendapatkan summary data stok rak
    """
    try:
        # Get all rak stocks with quantity > 0
        rak_stocks = InventoryRakStock.objects.select_related(
            'rak', 'product'
        ).filter(quantity__gt=0)
        
        # Calculate summary
        unique_raks = rak_stocks.values('rak__kode_rak').distinct().count()
        unique_products = rak_stocks.values('product__sku').distinct().count()
        total_stok = rak_stocks.aggregate(total=Sum('quantity'))['total'] or 0
        stok_rendah = rak_stocks.filter(quantity__lte=10).count()
        
        return JsonResponse({
            'success': True,
            'data': {
                'total_rak': unique_raks,
                'total_produk': unique_products,
                'total_stok': total_stok,
                'stok_rendah': stok_rendah
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@permission_required('products.view_product', raise_exception=True)
def product_edit_logs(request, product_id=None):
    """View untuk menampilkan log perubahan produk"""
    if product_id:
        # Log untuk produk tertentu
        product = get_object_or_404(Product, id=product_id)
        logs = EditProductLog.objects.filter(product=product).select_related('edited_by').order_by('-edited_at')
        context = {
            'product': product,
            'logs': logs,
            'show_product_info': True
        }
        return render(request, 'products/product_edit_logs.html', context)
    else:
        # Semua log perubahan
        logs = EditProductLog.objects.select_related('product', 'edited_by').order_by('-edited_at')
        
        # Pagination
        paginator = Paginator(logs, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'logs': page_obj,
            'show_product_info': False
        }
        return render(request, 'products/product_edit_logs.html', context)

@login_required
@permission_required('products.view_product', raise_exception=True)
def product_dimension_view(request):
    """
    View untuk menampilkan dimensi produk
    """
    return render(request, 'products/product_dimension.html')


@require_GET
@login_required
@permission_required('products.view_product', raise_exception=True)
def product_dimension_data(request):
    """
    API untuk DataTables - data dimensi produk
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"product_dimension_data called by user: {request.user}")
    
    try:
        draw = int(request.GET.get('draw', 1))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 10))
        search_value = request.GET.get('search[value]', '')
        
        # Query dasar
        queryset = Product.objects.filter(is_active=True)
        
        # Filter berdasarkan search
        if search_value:
            queryset = queryset.filter(
                Q(sku__icontains=search_value) |
                Q(barcode__icontains=search_value) |
                Q(nama_produk__icontains=search_value) |
                Q(variant_produk__icontains=search_value) |
                Q(brand__icontains=search_value)
            )
        
        # Total records sebelum filtering
        total_records = Product.objects.filter(is_active=True).count()
        
        # Total records setelah filtering
        filtered_records = queryset.count()
        
        # Handle sorting
        order_column_index = request.GET.get('order[0][column]')
        order_dir = request.GET.get('order[0][dir]', 'asc')
        
        if order_column_index is not None:
            try:
                order_column_index = int(order_column_index)
                # Define column mapping for sorting
                columns = [
                    'sku',                    # 0: SKU
                    'barcode',                # 1: Barcode
                    'nama_produk',            # 2: Nama Produk
                    'variant_produk',         # 3: Variant Produk
                    'brand',                  # 4: Brand
                    'panjang_cm',             # 5: Panjang
                    'lebar_cm',               # 6: Lebar
                    'tinggi_cm'               # 7: Tinggi
                ]
                
                if order_column_index < len(columns) and columns[order_column_index]:
                    order_column = columns[order_column_index]
                    if order_dir == 'desc':
                        order_column = '-' + order_column
                    queryset = queryset.order_by(order_column)
                else:
                    # Default sorting
                    queryset = queryset.order_by('sku')
            except (ValueError, IndexError):
                # Default sorting if there's an error
                queryset = queryset.order_by('sku')
        else:
            # Default sorting if no order specified
            queryset = queryset.order_by('sku')
        
        # Pagination
        queryset = queryset[start:start + length]
        
        # Format data untuk DataTables
        data = []
        for product in queryset:
            data.append({
                'id': product.id,
                'sku': product.sku or '-',
                'barcode': product.barcode or '-',
                'nama_produk': product.nama_produk or '-',
                'variant_produk': product.variant_produk or '-',
                'brand': product.brand or '-',
                'panjang_cm': product.panjang_cm or '-',
                'lebar_cm': product.lebar_cm or '-',
                'tinggi_cm': product.tinggi_cm or '-',
            })
        
        response_data = {
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': filtered_records,
            'data': data
        }
        
        logger.info(f"Returning {len(data)} records out of {total_records} total")
        logger.info(f"Sample data: {data[:2] if data else 'No data'}")
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'draw': int(request.GET.get('draw', 1)),
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': [],
            'error': str(e)
        }, status=500)


@require_POST
@login_required
@permission_required('products.change_product', raise_exception=True)
def upload_product_photo(request, product_id):
    """
    AJAX endpoint untuk upload foto produk secara otomatis
    """
    try:
        product = get_object_or_404(Product, id=product_id)
        
        if 'photo' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'Tidak ada file yang diupload'
            }, status=400)
        
        photo_file = request.FILES['photo']
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
        if photo_file.content_type not in allowed_types:
            return JsonResponse({
                'success': False,
                'error': 'Format file tidak didukung. Gunakan JPG, PNG, GIF, atau WEBP'
            }, status=400)
        
        # Validate file size (5MB)
        if photo_file.size > 5 * 1024 * 1024:
            return JsonResponse({
                'success': False,
                'error': 'Ukuran file maksimal 5MB'
            }, status=400)
        
        # Save old photo URL for logging
        old_photo_url = product.photo.url if product.photo else None
        
        # Update product photo
        product.photo = photo_file
        product.save()
        
        # Log the change
        EditProductLog.objects.create(
            product=product,
            edited_by=request.user,
            field_name='photo',
            old_value=old_photo_url or 'No photo',
            new_value=product.photo.url,
            change_type='UPDATE',
            notes=f'Foto produk diupload via AJAX. File: {photo_file.name}',
            product_sku=product.sku,
            product_name=product.nama_produk,
            product_barcode=product.barcode
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Foto produk berhasil diupload',
            'photo_url': product.photo.url
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Terjadi kesalahan: {str(e)}'
        }, status=500)

@require_POST
@csrf_exempt
@login_required
@permission_required('products.change_product', raise_exception=True)
def update_product_dimensions(request):
    """
    AJAX endpoint untuk update dimensi produk
    """
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        lebar_cm = data.get('lebar_cm')
        panjang_cm = data.get('panjang_cm')
        tinggi_cm = data.get('tinggi_cm')
        posisi_tidur = data.get('posisi_tidur', False)
        
        if not product_id:
            return JsonResponse({
                'success': False,
                'error': 'ID produk tidak boleh kosong'
            }, status=400)
        
        # Ambil produk
        product = get_object_or_404(Product, id=product_id)
        
        # Update dimensi
        if lebar_cm is not None:
            # Konversi koma ke titik untuk format float
            lebar_str = str(lebar_cm).replace(',', '.') if lebar_cm else None
            product.lebar_cm = float(lebar_str) if lebar_str else None
        if panjang_cm is not None:
            # Konversi koma ke titik untuk format float
            panjang_str = str(panjang_cm).replace(',', '.') if panjang_cm else None
            product.panjang_cm = float(panjang_str) if panjang_str else None
        if tinggi_cm is not None:
            # Konversi koma ke titik untuk format float
            tinggi_str = str(tinggi_cm).replace(',', '.') if tinggi_cm else None
            product.tinggi_cm = float(tinggi_str) if tinggi_str else None
        
        # Update posisi tidur
        product.posisi_tidur = posisi_tidur
        
        product.save()
        
        # Update rak capacity untuk semua rak yang memiliki produk ini
        from inventory import rakcapacity
        success, message = rakcapacity.update_rak_capacity_for_product(product_id)
        if not success:
            return JsonResponse({
                'success': False,
                'error': f'Berhasil update dimensi tapi gagal update capacity: {message}'
            }, status=500)
        
        return JsonResponse({
            'success': True,
            'message': f'Dimensi produk {product.sku} berhasil diupdate',
            'product_id': product_id,
            'new_dimensions': {
                'lebar_cm': float(product.lebar_cm) if product.lebar_cm else None,
                'panjang_cm': float(product.panjang_cm) if product.panjang_cm else None,
                'tinggi_cm': float(product.tinggi_cm) if product.tinggi_cm else None,
                'posisi_tidur': product.posisi_tidur
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Data JSON tidak valid'
        }, status=400)
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': f'Format angka tidak valid: {str(e)}'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Terjadi kesalahan: {str(e)}'
        }, status=500)
