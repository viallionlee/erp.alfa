from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.db import transaction
from django.db.models import Q, F, Sum, Count
from django.utils import timezone
import re
import json

from .models import Rak
from products.models import Product
from inventory.models import Stock, InventoryRakStock, InventoryRakStockLog

@login_required
@permission_required('inventory.view_rak', raise_exception=True)
def rak_list(request):
    """
    Menampilkan daftar rak
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = re.search(r'mobile|android|iphone', user_agent)
    
    template_name = 'inventory/rak_mobile.html' if is_mobile else 'inventory/rak_list.html'
    
    raks = Rak.objects.all().order_by('kode_rak')
    
    context = {
        'raks': raks,
        'total_raks': raks.count(),
    }
    return render(request, template_name, context)

@require_POST
@csrf_exempt
@login_required
@permission_required('inventory.add_rak', raise_exception=True)
def rak_add(request):
    """
    Tambah rak baru via AJAX.
    Mengembalikan JSON response.
    """
    try:
        kode_rak = request.POST.get('kode_rak', '').strip()
        nama_rak = request.POST.get('nama_rak', '').strip()
        barcode_rak = request.POST.get('barcode_rak', '').strip()
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
        
        # Cek duplikasi barcode_rak
        if barcode_rak and Rak.objects.filter(barcode_rak__iexact=barcode_rak).exists():
            return JsonResponse({'success': False, 'error': f'Barcode rak "{barcode_rak}" sudah ada.'}, status=400)

        # Convert to float/Decimal
        try:
            panjang_cm = float(panjang_cm) if panjang_cm else None
            lebar_cm = float(lebar_cm) if lebar_cm else None
            tinggi_cm = float(tinggi_cm) if tinggi_cm else None
            kapasitas_kg = float(kapasitas_kg) if kapasitas_kg else None
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Dimensi atau kapasitas harus berupa angka.'}, status=400)
        
        # Buat objek Rak baru
        with transaction.atomic():
            rak = Rak.objects.create(
                kode_rak=kode_rak,
                nama_rak=nama_rak,
                barcode_rak=barcode_rak,
                panjang_cm=panjang_cm,
                lebar_cm=lebar_cm,
                tinggi_cm=tinggi_cm,
                kapasitas_kg=kapasitas_kg,
                lokasi=lokasi,
                keterangan=keterangan,
            )
        
        return JsonResponse({'success': True, 'message': f'Rak {rak.kode_rak} berhasil ditambahkan.'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Terjadi kesalahan: {str(e)}'}, status=500)

@csrf_exempt
@login_required
@permission_required('inventory.change_rak', raise_exception=True)
def rak_edit(request, rak_id):
    """
    Mengambil data rak untuk form edit (GET) atau menyimpan perubahan rak (POST) via AJAX.
    """
    rak = get_object_or_404(Rak, id=rak_id)

    if request.method == 'POST':
        try:
            kode_rak = request.POST.get('kode_rak', '').strip()
            nama_rak = request.POST.get('nama_rak', '').strip()
            barcode_rak = request.POST.get('barcode_rak', '').strip()
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
            
            # Cek duplikasi kode_rak (kecuali rak yang sedang diedit)
            if Rak.objects.filter(kode_rak__iexact=kode_rak).exclude(id=rak_id).exists():
                return JsonResponse({'success': False, 'error': f'Kode rak "{kode_rak}" sudah ada.'}, status=400)
            
            # Cek duplikasi barcode_rak (kecuali rak yang sedang diedit)
            if barcode_rak and Rak.objects.filter(barcode_rak__iexact=barcode_rak).exclude(id=rak_id).exists():
                return JsonResponse({'success': False, 'error': f'Barcode rak "{barcode_rak}" sudah ada.'}, status=400)

            # Convert to float/Decimal
            try:
                panjang_cm = float(panjang_cm) if panjang_cm else None
                lebar_cm = float(lebar_cm) if lebar_cm else None
                tinggi_cm = float(tinggi_cm) if tinggi_cm else None
                kapasitas_kg = float(kapasitas_kg) if kapasitas_kg else None
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Dimensi atau kapasitas harus berupa angka.'}, status=400)
            
            # Update rak
            with transaction.atomic():
                rak.kode_rak = kode_rak
                rak.nama_rak = nama_rak
                rak.barcode_rak = barcode_rak
                rak.panjang_cm = panjang_cm
                rak.lebar_cm = lebar_cm
                rak.tinggi_cm = tinggi_cm
                rak.kapasitas_kg = kapasitas_kg
                rak.lokasi = lokasi
                rak.keterangan = keterangan
                rak.save()
            
            return JsonResponse({'success': True, 'message': f'Rak {rak.kode_rak} berhasil diperbarui.'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Terjadi kesalahan: {str(e)}'}, status=500)
    
    else:  # GET request
        # Mengembalikan data rak dalam format JSON
        rak_data = {
            'id': rak.id,
            'kode_rak': rak.kode_rak,
            'nama_rak': rak.nama_rak,
            'barcode_rak': rak.barcode_rak or '',
            'panjang_cm': str(rak.panjang_cm) if rak.panjang_cm else '',
            'lebar_cm': str(rak.lebar_cm) if rak.lebar_cm else '',
            'tinggi_cm': str(rak.tinggi_cm) if rak.tinggi_cm else '',
            'kapasitas_kg': str(rak.kapasitas_kg) if rak.kapasitas_kg else '',
            'lokasi': rak.lokasi or '',
            'keterangan': rak.keterangan or '',
        }
        return JsonResponse({'success': True, 'data': rak_data})

@require_POST
@csrf_exempt
@login_required
@permission_required('inventory.delete_rak', raise_exception=True)
def rak_delete(request, rak_id):
    """
    Hapus rak via AJAX.
    """
    try:
        rak = get_object_or_404(Rak, id=rak_id)
        
        # Cek apakah rak masih digunakan
        if InventoryRakStock.objects.filter(rak=rak).exists():
            return JsonResponse({'success': False, 'error': f'Rak {rak.kode_rak} masih memiliki stok dan tidak dapat dihapus.'}, status=400)
        
        # Tambahan validasi log
        if InventoryRakStockLog.objects.filter(rak=rak).exists():
            return JsonResponse({'success': False, 'error': f'Rak {rak.kode_rak} sudah pernah ada transaksi/log pergerakan, tidak dapat dihapus.'}, status=400)

        with transaction.atomic():
            rak.delete()
        
        return JsonResponse({'success': True, 'message': f'Rak {rak.kode_rak} berhasil dihapus.'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Terjadi kesalahan: {str(e)}'}, status=500)

@login_required
@permission_required('inventory.view_rak', raise_exception=True)
def rak_detail(request, rak_id):
    """
    Menampilkan detail rak
    """
    rak = get_object_or_404(Rak, id=rak_id)
    
    # Ambil stok di rak ini
    rak_stocks = InventoryRakStock.objects.filter(rak=rak).select_related('product')
    
    context = {
        'rak': rak,
        'rak_stocks': rak_stocks,
    }
    return render(request, 'inventory/rak_detail.html', context)

@require_GET
@login_required
@permission_required('inventory.view_rak', raise_exception=True)
def rak_data(request):
    """
    API untuk DataTables - daftar rak
    """
    # Check if this is a request for rak options (for dropdowns)
    if request.GET.get('get_rak_options'):
        raks = Rak.objects.all().order_by('lokasi')
        rak_options = []
        for rak in raks:
            # Hitung jumlah produk di rak ini
            item_count = InventoryRakStock.objects.filter(rak=rak, quantity__gt=0).count()
            
            rak_options.append({
                'id': rak.id,
                'kode_rak': rak.kode_rak,
                'nama_rak': rak.nama_rak,
                'barcode_rak': rak.barcode_rak or '',
                'lokasi': rak.lokasi or '-',
                'item_count': item_count
            })
        return JsonResponse({'rak_options': rak_options})
    
    # Ambil parameter dari DataTables
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '')
    
    # Query dasar
    queryset = Rak.objects.all()
    
    # Filter berdasarkan search
    if search_value:
        queryset = queryset.filter(
            Q(kode_rak__icontains=search_value) |
            Q(nama_rak__icontains=search_value) |
            Q(barcode_rak__icontains=search_value) |
            Q(lokasi__icontains=search_value)
        )
    
    # Total records sebelum filtering
    total_records = Rak.objects.count()
    
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
                'kode_rak',           # 0: Rak
                None,                       # 1: Photo (not sortable)
                'nama_rak',             # 2: Produk (SKU)
                'lokasi',                 # 3: Detail Produk
                'created_at'                # 4: Stok
            ]
            
            if order_column_index < len(columns) and columns[order_column_index]:
                order_column = columns[order_column_index]
                if order_dir == 'desc':
                    order_column = '-' + order_column
                queryset = queryset.order_by(order_column)
            else:
                # Default sorting if column is not sortable
                queryset = queryset.order_by('kode_rak')
        except (ValueError, IndexError):
            # Default sorting if there's an error
            queryset = queryset.order_by('kode_rak')
    else:
        # Default sorting if no order specified
        queryset = queryset.order_by('kode_rak')
    
    # Pagination - dilakukan setelah sorting
    queryset = queryset[start:start + length]
    
    # Format data untuk DataTables
    data = []
    for rak in queryset:
        # Hitung total stok untuk rak ini
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
            'barcode_rak': rak.barcode_rak or '-',
            'lokasi': rak.lokasi or '-',
            'dimensi': f"{rak.panjang_cm or '-'} x {rak.lebar_cm or '-'} x {rak.tinggi_cm or '-'} cm",
            'kapasitas': kapasitas_formatted,
            'total_stok': total_stok,
            'created_at': rak.created_at.strftime('%d/%m/%Y %H:%M'),
            'actions': f'''
                <div class="btn-group" role="group">
                    <button type="button" class="btn btn-sm btn-outline-primary" 
                            data-bs-toggle="modal" data-bs-target="#editRakModal" 
                            data-id="{rak.id}" title="Edit Rak">
                        <i class="bi bi-pencil"></i> Edit
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-danger" 
                            data-id="{rak.id}" data-kode="{rak.kode_rak}" title="Hapus Rak">
                        <i class="bi bi-trash"></i> Hapus
                    </button>
                </div>
            '''
        })
    
    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': filtered_records,
        'data': data
    })

@login_required
@permission_required('inventory.view_rak', raise_exception=True)
def rak_stock_detail(request, rak_id):
    """
    Menampilkan detail stok di rak tertentu
    """
    rak = get_object_or_404(Rak, id=rak_id)
    
    # Ambil stok di rak ini
    rak_stocks = InventoryRakStock.objects.filter(rak=rak).select_related('product')
    
    context = {
        'rak': rak,
        'rak_stocks': rak_stocks,
    }
    return render(request, 'inventory/rak_stock_detail.html', context)

@login_required
@permission_required('inventory.view_rak', raise_exception=True)
def rak_stock(request):
    """
    Menampilkan daftar stok per rak
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = re.search(r'mobile|android|iphone', user_agent)
    
    template_name = 'inventory/rak_stock_mobile.html' if is_mobile else 'inventory/rak_stock.html'
    
    return render(request, template_name)

@require_GET
def rak_stock_data(request):
    """
    API untuk DataTables - stok per rak
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"rak_stock_data called by user: {request.user}")
    
    try:
        # Menangani permintaan khusus untuk opsi filter rak
        if request.GET.get('get_rak_options'):
            logger.info("Processing get_rak_options request")
            
            # Ambil semua rak yang memiliki stok
            raks = Rak.objects.filter(
                inventoryrakstock__quantity__gt=0
            ).distinct().order_by('kode_rak')
            
            logger.info(f"Found {raks.count()} raks with stock")
            
            rak_options = []
            for rak in raks:
                rak_options.append({
                    'id': rak.id, 
                    'kode_rak': rak.kode_rak, 
                    'nama_rak': rak.nama_rak
                })
                logger.info(f"Added rak option: {rak.kode_rak} - {rak.nama_rak}")
            
            logger.info(f"Returning {len(rak_options)} rak options for filter")
            return JsonResponse({'rak_options': rak_options})

        draw = int(request.GET.get('draw', 1))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 10))
        search_value = request.GET.get('search[value]', '')
        rak_filter = request.GET.get('rak_filter', '')
        # Handle filter dari DataTables yang baru
        if not rak_filter:
            rak_filter = request.GET.get('rakFilterSelect', '')
        stock_filter = request.GET.get('filter', '')  # Tambahkan parameter filter untuk level stok
        
        logger.info(f"Rak filter: '{rak_filter}', Stock filter: '{stock_filter}', Search: '{search_value}'")
        
        # Query dasar - hanya tampilkan yang ada stoknya
        queryset = InventoryRakStock.objects.select_related('product', 'rak').filter(quantity__gt=0)
        
        # Filter berdasarkan rak jika ada
        if rak_filter and rak_filter != 'all':
            try:
                rak_id = int(rak_filter)
                queryset = queryset.filter(rak_id=rak_id)
            except (ValueError, TypeError):
                # Fallback ke filter berdasarkan kode_rak jika rak_filter bukan angka
                queryset = queryset.filter(rak__kode_rak=rak_filter)
        
        # Filter berdasarkan level stok
        if stock_filter:
            if stock_filter == 'low_stock':
                queryset = queryset.filter(quantity__lte=10)
            elif stock_filter == 'medium_stock':
                queryset = queryset.filter(quantity__gt=10, quantity__lte=50)
            elif stock_filter == 'high_stock':
                queryset = queryset.filter(quantity__gt=50)
            elif stock_filter == 'all':
                # 'all' means no quantity filter - show all stock
                pass  # Don't apply any quantity filter
        
        # Filter berdasarkan search
        if search_value:
            queryset = queryset.filter(
                Q(product__id__icontains=search_value) |
                Q(product__sku__icontains=search_value) |
                Q(product__nama_produk__icontains=search_value) |
                Q(product__barcode__icontains=search_value) |
                Q(product__variant_produk__icontains=search_value) |
                Q(product__brand__icontains=search_value) |
                Q(rak__kode_rak__icontains=search_value) |
                Q(rak__nama_rak__icontains=search_value) |
                Q(rak__lokasi__icontains=search_value)
            )
        
        # Total records sebelum filtering - hanya yang ada stoknya
        total_records = InventoryRakStock.objects.filter(quantity__gt=0).count()
        
        # Total records setelah filtering
        filtered_records = queryset.count()
        logger.info(f"Total records: {total_records}, Filtered records: {filtered_records}")
        
        # Handle sorting
        order_column_index = request.GET.get('order[0][column]')
        order_dir = request.GET.get('order[0][dir]', 'asc')
        
        if order_column_index is not None:
            try:
                order_column_index = int(order_column_index)
                # Define column mapping for sorting
                columns = [
                    'rak__kode_rak',           # 0: Rak
                    None,                       # 1: Photo (not sortable)
                    'product__sku',             # 2: Produk (SKU)
                    'product__nama_produk',     # 3: Detail Produk
                    'quantity',                 # 4: Stok
                    None,                       # 5: Terpakai (calculated, not sortable)
                    'updated_at'                # 6: Terakhir Update
                ]
                
                if order_column_index < len(columns) and columns[order_column_index]:
                    order_column = columns[order_column_index]
                    if order_dir == 'desc':
                        order_column = '-' + order_column
                    queryset = queryset.order_by(order_column)
                else:
                    # Default sorting if column is not sortable
                    queryset = queryset.order_by('rak__kode_rak', 'product__nama_produk')
            except (ValueError, IndexError):
                # Default sorting if there's an error
                queryset = queryset.order_by('rak__kode_rak', 'product__nama_produk')
        else:
            # Default sorting if no order specified
            queryset = queryset.order_by('rak__kode_rak', 'product__nama_produk')
        
        # Pagination
        queryset = queryset[start:start + length]
        
        # Format data untuk DataTables
        data = []
        for stock in queryset:
            try:
                # Get product photo URL
                photo_url = '/static/icons/box.png'  # Default fallback
                if stock.product and stock.product.photo:
                    try:
                        photo_url = stock.product.photo.url
                    except:
                        pass  # Keep default fallback
                
                # Safely get product data
                product_id = 0
                barcode = '-'
                sku = '-'
                nama_produk = '-'
                variant_produk = '-'
                brand = '-'
                
                if stock.product:
                    try:
                        product_id = stock.product.id
                    except:
                        pass
                    try:
                        barcode = stock.product.barcode or '-'
                    except:
                        pass
                    try:
                        sku = stock.product.sku or '-'
                    except:
                        pass
                    try:
                        nama_produk = stock.product.nama_produk or '-'
                    except:
                        pass
                    try:
                        variant_produk = stock.product.variant_produk or '-'
                    except:
                        pass
                    try:
                        brand = stock.product.brand or '-'
                    except:
                        pass
                
                # Safely get rak data
                kode_rak = '-'
                nama_rak = '-'
                lokasi_rak = '-'
                
                if stock.rak:
                    try:
                        kode_rak = stock.rak.kode_rak or '-'
                    except:
                        pass
                    try:
                        nama_rak = stock.rak.nama_rak or '-'
                    except:
                        pass
                    try:
                        lokasi_rak = stock.rak.lokasi or '-'
                    except:
                        pass
                
                # Safely get quantity and updated_at
                quantity = 0
                last_updated = '-'
                used_front = 0
                
                try:
                    quantity = stock.quantity
                except:
                    pass
                
                try:
                    last_updated = stock.updated_at.strftime('%d/%m/%Y %H:%M') if stock.updated_at else '-'
                except:
                    pass
                
                # Calculate used_front based on product width and quantity
                try:
                    if stock.product and stock.product.lebar_cm and quantity:
                        used_front = float(stock.product.lebar_cm) * quantity
                except:
                    used_front = 0
                
                # Safely get stock id
                stock_id = 0
                try:
                    stock_id = stock.id
                except:
                    pass
                
                data.append({
                    'id': stock_id,
                    'kode_rak': kode_rak,
                    'nama_rak': nama_rak,
                    'lokasi_rak': lokasi_rak,
                    'photo_url': photo_url,
                    'product_id': product_id,
                    'barcode': barcode,
                    'sku': sku,
                    'nama_produk': nama_produk,
                    'variant_produk': variant_produk,
                    'brand': brand,
                    'quantity': quantity,
                    'used_front': round(used_front, 1),
                    'last_updated': last_updated
                })
            except Exception as e:
                # Log error for individual record but continue processing
                print(f"Error processing stock record {stock.id}: {str(e)}")
                continue
        
        return JsonResponse({
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': filtered_records,
            'data': data
        })
        
    except Exception as e:
        # Log the full error for debugging
        import traceback
        print(f"Error in rak_stock_data: {str(e)}")
        print(traceback.format_exc())
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
    API untuk summary stok per rak
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"rak_stock_summary called by user: {request.user}")
    
    try:
        # Ambil parameter filter
        rak_filter = request.GET.get('rak_filter', '')
        stock_filter = request.GET.get('filter', '')
        
        # Query dasar untuk summary
        queryset = InventoryRakStock.objects.all()
        
        # Filter berdasarkan rak jika ada
        if rak_filter and rak_filter != 'all':
            try:
                rak_id = int(rak_filter)
                queryset = queryset.filter(rak_id=rak_id)
            except (ValueError, TypeError):
                queryset = queryset.filter(rak__kode_rak=rak_filter)
        
        # Filter berdasarkan level stok
        if stock_filter:
            if stock_filter == 'low_stock':
                queryset = queryset.filter(quantity__lte=10)
            elif stock_filter == 'medium_stock':
                queryset = queryset.filter(quantity__gt=10, quantity__lte=50)
            elif stock_filter == 'high_stock':
                queryset = queryset.filter(quantity__gt=50)
            elif stock_filter == 'all':
                # 'all' means no quantity filter - show all stock
                pass  # Don't apply any quantity filter
        
        # Hitung summary berdasarkan queryset yang sudah difilter
        total_raks = queryset.values('rak').distinct().count()
        total_products = queryset.values('product').distinct().count()
        total_stock = queryset.aggregate(total=Sum('quantity'))['total'] or 0
        low_stock = queryset.filter(quantity__lte=10).count()
        
        return JsonResponse({
            'success': True,
            'data': {
                'total_raks': total_raks,
                'total_products': total_products,
                'total_stock': total_stock,
                'low_stock': low_stock
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@require_GET
def api_rak_stock_log_data_all(request):
    """
    API untuk DataTables - semua log stok rak (tanpa filter rak)
    """
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '')
    rak_filter = request.GET.get('rak_filter', '')
    
    # Query dasar - semua log
    queryset = InventoryRakStockLog.objects.select_related('produk', 'user', 'rak')
    
    # Filter berdasarkan rak jika ada
    if rak_filter and rak_filter != 'all':
        try:
            rak_id = int(rak_filter)
            queryset = queryset.filter(rak_id=rak_id)
        except (ValueError, TypeError):
            # Fallback ke filter berdasarkan kode_rak jika rak_filter bukan angka
            queryset = queryset.filter(rak__kode_rak=rak_filter)
    
    # Filter berdasarkan search
    if search_value:
        queryset = queryset.filter(
            Q(produk__id__icontains=search_value) |
            Q(produk__sku__icontains=search_value) |
            Q(produk__nama_produk__icontains=search_value) |
            Q(produk__barcode__icontains=search_value) |
            Q(produk__variant_produk__icontains=search_value) |
            Q(produk__brand__icontains=search_value) |
            Q(rak__kode_rak__icontains=search_value) |
            Q(tipe_pergerakan__icontains=search_value)
        )
    
    # Total records sebelum filtering
    total_records = InventoryRakStockLog.objects.count()
    
    # Total records setelah filtering
    filtered_records = queryset.count()
    
    # Sorting - default by waktu_buat descending
    queryset = queryset.order_by('-waktu_buat')
    
    # Pagination
    queryset = queryset[start:start + length]
    
    # Format data untuk DataTables
    data = []
    for log in queryset:
        data.append({
            'id': log.id,
            'rak_kode_rak': log.rak.kode_rak if log.rak else '-',
            'product_sku': log.produk.sku if log.produk else '-',
            'product_nama_produk': log.produk.nama_produk if log.produk else '-',
            'product_barcode': log.produk.barcode if log.produk and log.produk.barcode else '-',
            'product_variant': log.produk.variant_produk if log.produk and log.produk.variant_produk else '-',
            'activity_type': log.tipe_pergerakan,
            'quantity_before': log.qty_awal,
            'quantity_after': log.qty_akhir,
            'quantity_change': log.qty,
            'user_username': log.user.username if log.user else '-',
            'created_at': log.waktu_buat.strftime('%d/%m/%Y %H:%M:%S')
        })
    
    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': filtered_records,
        'data': data
    })

@require_GET
def api_rak_stock_log_data(request, rak_id):
    """
    API untuk DataTables - log stok rak
    """
    rak = get_object_or_404(Rak, id=rak_id)
    
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '')
    
    # Query dasar
    queryset = InventoryRakStockLog.objects.filter(rak=rak).select_related('produk', 'user')
    
    # Filter berdasarkan search
    if search_value:
        queryset = queryset.filter(
            Q(produk__sku__icontains=search_value) |
            Q(produk__nama_produk__icontains=search_value) |
            Q(produk__barcode__icontains=search_value) |
            Q(produk__variant_produk__icontains=search_value) |
            Q(tipe_pergerakan__icontains=search_value)
        )
    
    # Total records sebelum filtering
    total_records = InventoryRakStockLog.objects.filter(rak=rak).count()
    
    # Total records setelah filtering
    filtered_records = queryset.count()
    
    # Sorting - default by waktu_buat descending
    queryset = queryset.order_by('-waktu_buat')
    
    # Pagination
    queryset = queryset[start:start + length]
    
    # Format data untuk DataTables
    data = []
    for log in queryset:
        data.append({
            'id': log.id,
            'rak_kode_rak': log.rak.kode_rak if log.rak else '-',
            'product_sku': log.produk.sku if log.produk else '-',
            'product_nama_produk': log.produk.nama_produk if log.produk else '-',
            'product_barcode': log.produk.barcode if log.produk and log.produk.barcode else '-',
            'product_variant': log.produk.variant_produk if log.produk and log.produk.variant_produk else '-',
            'activity_type': log.tipe_pergerakan,
            'quantity_before': log.qty_awal,
            'quantity_after': log.qty_akhir,
            'quantity_change': log.qty,
            'user_username': log.user.username if log.user else '-',
            'created_at': log.waktu_buat.strftime('%d/%m/%Y %H:%M:%S')
        })
    
    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': filtered_records,
        'data': data
    }) 

def stock_position_view(request):
    """Halaman sederhana untuk melihat posisi stock di rak dengan quantity dan quantity_opname"""
    
    import re
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = re.search(r'mobile|android|iphone', user_agent)

    template_name = 'inventory/stock_position_mobile.html' if is_mobile else 'inventory/stock_position.html'

    from .models import RakOpnameSession, RakOpnameItem
    
    # Get all rak stocks with related data
    rak_stocks = InventoryRakStock.objects.select_related(
        'product', 'rak'
    ).filter(
        Q(quantity__gt=0) | Q(quantity_opname__gt=0)
    ).order_by('rak__lokasi', 'rak__kode_rak', 'product__nama_produk')
    
    # Filter by rak if specified
    rak_filter = request.GET.get('rak_filter')
    if rak_filter:
        rak_stocks = rak_stocks.filter(rak_id=rak_filter)
    
    # Search filter
    search_query = request.GET.get('search')
    if search_query:
        rak_stocks = rak_stocks.filter(
            Q(product__sku__icontains=search_query) |
            Q(product__nama_produk__icontains=search_query) |
            Q(product__barcode__icontains=search_query) |
            Q(product__variant_produk__icontains=search_query) |
            Q(product__brand__icontains=search_query) |
            Q(rak__lokasi__icontains=search_query) |
            Q(rak__kode_rak__icontains=search_query)
        )
    
    # Get master stock data
    master_stocks = Stock.objects.select_related('product').filter(
        product__in=[rs.product for rs in rak_stocks]
    )
    master_stock_dict = {ms.product_id: ms.quantity for ms in master_stocks}
    
    # Get active opname sessions for each product
    active_opname_sessions = {}
    for rs in rak_stocks:
        if rs.quantity_opname > 0:
            # Get active opname sessions for this product
            opname_items = RakOpnameItem.objects.filter(
                product=rs.product,
                session__status='draft'
            ).select_related('session__rak')
            
            if opname_items.exists():
                active_opname_sessions[rs.product_id] = []
                for item in opname_items:
                    active_opname_sessions[rs.product_id].append({
                        'session_code': item.session.session_code,
                        'rak_lokasi': f"{item.session.rak.lokasi} ({item.session.rak.kode_rak})",
                        'qty_fisik': item.qty_fisik,
                        'created_at': item.session.tanggal_mulai.strftime('%d/%m/%Y %H:%M')
                    })
    
    # Prepare data for template
    stock_data = []
    for rs in rak_stocks:
        master_qty = master_stock_dict.get(rs.product_id, 0)
        total_qty = rs.quantity + rs.quantity_opname
        
        # Get opname info for this product
        opname_info = active_opname_sessions.get(rs.product_id, [])
        
        stock_data.append({
            'rak_lokasi': f"{rs.rak.lokasi} ({rs.rak.kode_rak})",
            'rak_id': rs.rak.id,
            'product_sku': rs.product.sku,
            'product_name': rs.product.nama_produk,
            'product_barcode': rs.product.barcode or '-',
            'product_variant': rs.product.variant_produk or '-',
            'product_brand': rs.product.brand or '-',
            'quantity': rs.quantity,
            'quantity_opname': rs.quantity_opname,
            'total_quantity': total_qty,
            'master_quantity': master_qty,
            'status': 'OK' if total_qty <= master_qty else 'OVERSTOCK',
            'last_updated': rs.updated_at.strftime('%d/%m/%Y %H:%M') if rs.updated_at else '-',
            'opname_sessions': opname_info,
            'has_active_opname': len(opname_info) > 0
        })
    
    # Get all raks for filter dropdown
    all_raks = Rak.objects.all().order_by('lokasi', 'kode_rak')
    
    # Summary statistics
    total_raks = rak_stocks.values('rak').distinct().count()
    total_products = rak_stocks.values('product').distinct().count()
    total_quantity = sum(rs.quantity for rs in rak_stocks)
    total_quantity_opname = sum(rs.quantity_opname for rs in rak_stocks)
    overstock_count = len([s for s in stock_data if s['status'] == 'OVERSTOCK'])
    products_with_opname = len([s for s in stock_data if s['has_active_opname']])
    
    summary = {
        'total_raks': total_raks,
        'total_products': total_products,
        'total_quantity': total_quantity,
        'total_quantity_opname': total_quantity_opname,
        'overstock_count': overstock_count,
        'products_with_opname': products_with_opname
    }
    
    context = {
        'stock_data': stock_data,
        'all_raks': all_raks,
        'selected_rak': rak_filter,
        'search_query': search_query,
        'summary': summary
    }
    
    return render(request, template_name, context)


@require_GET
def stock_position_summary(request):
    """API endpoint untuk mendapatkan ringkasan data posisi stock"""
    from .models import RakOpnameSession, RakOpnameItem
    
    # Get all rak stocks with related data
    rak_stocks = InventoryRakStock.objects.select_related(
        'product', 'rak'
    ).filter(
        Q(quantity__gt=0) | Q(quantity_opname__gt=0)
    )
    
    # Get master stock data
    master_stocks = Stock.objects.select_related('product').filter(
        product__in=[rs.product for rs in rak_stocks]
    )
    master_stock_dict = {ms.product_id: ms.quantity for ms in master_stocks}
    
    # Calculate summary statistics
    total_raks = rak_stocks.values('rak').distinct().count()
    total_products = rak_stocks.values('product').distinct().count()
    total_quantity = sum(rs.quantity for rs in rak_stocks)
    total_quantity_opname = sum(rs.quantity_opname for rs in rak_stocks)
    
    # Count overstock items
    overstock_count = 0
    products_with_opname = 0
    
    for rs in rak_stocks:
        master_qty = master_stock_dict.get(rs.product_id, 0)
        total_qty = rs.quantity + rs.quantity_opname
        
        if total_qty > master_qty:
            overstock_count += 1
        
        if rs.quantity_opname > 0:
            products_with_opname += 1
    
    summary = {
        'total_raks': total_raks,
        'total_products': total_products,
        'total_quantity': total_quantity,
        'total_quantity_opname': total_quantity_opname,
        'overstock_count': overstock_count,
        'products_with_opname': products_with_opname
    }
    
    return JsonResponse({
        'success': True,
        'data': summary
    })


@require_GET
def stock_position_data(request):
    """API endpoint untuk mendapatkan data posisi stock dengan filtering dan sorting"""
    from .models import RakOpnameSession, RakOpnameItem
    
    # Get all rak stocks with related data
    rak_stocks = InventoryRakStock.objects.select_related(
        'product', 'rak'
    ).filter(
        Q(quantity__gt=0) | Q(quantity_opname__gt=0)
    )
    
    # Apply filters
    rak_filter = request.GET.get('rak_filter')
    if rak_filter:
        rak_stocks = rak_stocks.filter(rak_id=rak_filter)
    
    status_filter = request.GET.get('status_filter')
    search_query = request.GET.get('search')
    
    if search_query:
        rak_stocks = rak_stocks.filter(
            Q(product__sku__icontains=search_query) |
            Q(product__nama_produk__icontains=search_query) |
            Q(product__barcode__icontains=search_query) |
            Q(product__variant_produk__icontains=search_query) |
            Q(product__brand__icontains=search_query) |
            Q(rak__lokasi__icontains=search_query) |
            Q(rak__kode_rak__icontains=search_query)
        )
    
    # Get master stock data
    master_stocks = Stock.objects.select_related('product').filter(
        product__in=[rs.product for rs in rak_stocks]
    )
    master_stock_dict = {ms.product_id: ms.quantity for ms in master_stocks}
    
    # Get active opname sessions for each product
    active_opname_sessions = {}
    for rs in rak_stocks:
        if rs.quantity_opname > 0:
            opname_items = RakOpnameItem.objects.filter(
                product=rs.product,
                session__status='draft'
            ).select_related('session__rak')
            
            if opname_items.exists():
                active_opname_sessions[rs.product_id] = []
                for item in opname_items:
                    active_opname_sessions[rs.product_id].append({
                        'session_code': item.session.session_code,
                        'rak_lokasi': f"{item.session.rak.lokasi} ({item.session.rak.kode_rak})",
                        'qty_fisik': item.qty_fisik,
                        'created_at': item.session.tanggal_mulai.strftime('%d/%m/%Y %H:%M')
                    })
    
    # Prepare data for response
    stock_data = []
    for rs in rak_stocks:
        master_qty = master_stock_dict.get(rs.product_id, 0)
        total_qty = rs.quantity + rs.quantity_opname
        
        # Apply status filter
        if status_filter:
            if status_filter == 'OK' and total_qty > master_qty:
                continue
            elif status_filter == 'OVERSTOCK' and total_qty <= master_qty:
                continue
        
        # Get opname info for this product
        opname_info = active_opname_sessions.get(rs.product_id, [])
        
        # Get product photo URL
        photo_url = ''
        if rs.product.photo:
            photo_url = rs.product.photo.url
        
        stock_data.append({
            'rak_lokasi': f"{rs.rak.lokasi} ({rs.rak.kode_rak})",
            'rak_id': rs.rak.id,
            'product_sku': rs.product.sku,
            'product_name': rs.product.nama_produk,
            'product_barcode': rs.product.barcode or '-',
            'product_variant': rs.product.variant_produk or '-',
            'product_brand': rs.product.brand or '-',
            'quantity': rs.quantity,
            'quantity_opname': rs.quantity_opname,
            'total_quantity': total_qty,
            'master_quantity': master_qty,
            'status': 'OK' if total_qty <= master_qty else 'OVERSTOCK',
            'last_updated': rs.updated_at.strftime('%d/%m/%Y %H:%M') if rs.updated_at else '-',
            'opname_sessions': opname_info,
            'has_active_opname': len(opname_info) > 0,
            'photo_url': photo_url
        })
    
    # Apply sorting
    order_column = request.GET.get('order[0][column]', '0')
    order_direction = request.GET.get('order[0][dir]', 'asc')
    
    # Map column index to field name
    column_map = {
        '0': 'rak_lokasi',
        '3': 'product_name',
        '8': 'total_quantity',
        '9': 'master_quantity',
        '10': 'status',
        '11': 'last_updated'
    }
    
    sort_field = column_map.get(order_column, 'rak_lokasi')
    
    # Sort the data
    reverse_sort = order_direction == 'desc'
    stock_data.sort(key=lambda x: x[sort_field], reverse=reverse_sort)
    
    return JsonResponse({
        'success': True,
        'data': stock_data
    }) 