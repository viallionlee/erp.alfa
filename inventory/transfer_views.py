from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q, Count, Sum
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

from .models import (
    RakTransferSession,
    RakTransferItem,
    Rak,
    InventoryRakStock,
    InventoryRakStockLog,
)
from products.models import Product


@login_required
@permission_required('inventory.view_raktransfer', raise_exception=True)
def transfer_rak_list(request):
    """
    Halaman daftar sesi transfer rak
    """
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Handle DataTables AJAX request
        draw = int(request.GET.get('draw', 1))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 25))
        search_value = request.GET.get('search[value]', '')
        
        # Filter parameters
        status_filter = request.GET.get('status', '')
        rak_asal_filter = request.GET.get('rak_asal', '')
        rak_tujuan_filter = request.GET.get('rak_tujuan', '')
        date_filter = request.GET.get('date', '')
        
        # Base queryset
        queryset = RakTransferSession.objects.select_related(
            'rak_asal', 'rak_tujuan', 'created_by'
        ).prefetch_related('items')
        
        # Apply filters
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if rak_asal_filter:
            queryset = queryset.filter(rak_asal_id=rak_asal_filter)
        if rak_tujuan_filter:
            queryset = queryset.filter(rak_tujuan_id=rak_tujuan_filter)
        if date_filter:
            queryset = queryset.filter(tanggal_transfer__date=date_filter)
        
        # Apply search
        if search_value:
            queryset = queryset.filter(
                Q(session_code__icontains=search_value) |
                Q(rak_asal__kode_rak__icontains=search_value) |
                Q(rak_asal__nama_rak__icontains=search_value) |
                Q(rak_tujuan__kode_rak__icontains=search_value) |
                Q(rak_tujuan__nama_rak__icontains=search_value) |
                Q(created_by__username__icontains=search_value)
            )
        
        # Get total count before pagination
        total_records = queryset.count()
        
        # Apply ordering and pagination
        queryset = queryset.order_by('-tanggal_transfer')[start:start + length]
        
        # Prepare data for DataTables
        data = []
        for session in queryset:
            data.append({
                'id': session.id,
                'session_code': session.session_code,
                'rak_asal_lokasi': f"{session.rak_asal.lokasi} ({session.rak_asal.kode_rak})",
                'rak_tujuan_lokasi': f"{session.rak_tujuan.lokasi} ({session.rak_tujuan.kode_rak})",
                'status': session.status,
                'total_items': session.items.count(),
                'total_qty': session.items.aggregate(total=Sum('qty_transfer'))['total'] or 0,
                'created_by_username': session.created_by.username if session.created_by else '-',
                'tanggal_transfer': session.tanggal_transfer.strftime('%Y-%m-%d %H:%M'),
            })
        
        return JsonResponse({
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': total_records,
            'data': data
        })
    
    # Regular page request
    return render(request, 'inventory/transfer_rak_list.html')


@login_required
@permission_required('inventory.add_raktransfer', raise_exception=True)
@require_http_methods(["POST"])
def transfer_rak_create(request):
    """
    Membuat sesi transfer rak baru (AJAX only)
    """
    try:
        rak_asal_id = request.POST.get('rak_asal_id')
        rak_tujuan_id = request.POST.get('rak_tujuan_id')
        catatan = request.POST.get('catatan', '')
        # Default ke transfer_putaway agar penyelesaian sesi selalu menuju proses putaway
        mode = request.POST.get('mode', 'transfer_putaway')
        
        if not rak_asal_id or not rak_tujuan_id:
            return JsonResponse({
                'success': False,
                'message': 'Rak asal dan rak tujuan harus dipilih'
            })
        
        if rak_asal_id == rak_tujuan_id:
            return JsonResponse({
                'success': False,
                'message': 'Rak asal dan rak tujuan tidak boleh sama'
            })
        
        # Get rak objects
        rak_asal = get_object_or_404(Rak, id=rak_asal_id)
        rak_tujuan = get_object_or_404(Rak, id=rak_tujuan_id)
        
        # Check if there's already a draft session for these raks
        existing_draft = RakTransferSession.objects.filter(
            Q(rak_asal=rak_asal) | Q(rak_tujuan=rak_asal) |
            Q(rak_asal=rak_tujuan) | Q(rak_tujuan=rak_tujuan),
            status='draft'
        ).first()
        
        if existing_draft:
            return JsonResponse({
                'success': False,
                'message': f'Sudah ada sesi draft yang menggunakan rak {rak_asal.kode_rak} atau {rak_tujuan.kode_rak}'
            })
        
        # Create transfer session
        with transaction.atomic():
            session = RakTransferSession.objects.create(
                rak_asal=rak_asal,
                rak_tujuan=rak_tujuan,
                catatan=catatan,
                mode=mode if mode in ['direct', 'transfer_putaway'] else 'direct',
                created_by=request.user
            )
            
            # Create log entry
            # You can add logging here if needed
        
        return JsonResponse({
            'success': True,
            'message': f'Sesi transfer berhasil dibuat: {session.session_code}',
            'redirect_url': f'/inventory/transfer-rak/{session.id}/work/'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Terjadi kesalahan: {str(e)}'
        })


@login_required
@permission_required('inventory.view_raktransfer', raise_exception=True)
def transfer_rak_summary(request):
    """
    API untuk mendapatkan summary data transfer rak
    """
    try:
        # Get summary data
        sesi_draft = RakTransferSession.objects.filter(status='draft').count()
        sesi_berlangsung = RakTransferSession.objects.filter(status='in_progress').count()
        sesi_selesai = RakTransferSession.objects.filter(status='selesai').count()
        
        # Calculate total transfer quantity
        total_transfer = RakTransferItem.objects.filter(
            session__status='selesai'
        ).aggregate(total=Sum('qty_transfer'))['total'] or 0
        
        return JsonResponse({
            'sesi_draft': sesi_draft,
            'sesi_berlangsung': sesi_berlangsung,
            'sesi_selesai': sesi_selesai,
            'total_transfer': total_transfer
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


@login_required
@permission_required('inventory.change_raktransfer', raise_exception=True)
def transfer_rak_work(request, session_id):
    """
    Halaman kerja transfer rak
    """
    session = get_object_or_404(RakTransferSession, id=session_id)
    
    if session.status != 'draft':
        messages.error(request, 'Sesi transfer ini tidak dapat diedit')
        return redirect('inventory:transfer_rak_list')
    
    context = {
        'session': session,
        'rak_asal': session.rak_asal,
        'rak_tujuan': session.rak_tujuan,
    }
    
    return render(request, 'inventory/transfer_rak_work.html', context)


@login_required
@permission_required('inventory.view_raktransfer', raise_exception=True)
def transfer_rak_source_stock(request, session_id):
    """
    Data stok dari Rak Asal untuk ditampilkan di halaman kerja transfer.
    Mengambil dari InventoryRakStock untuk rak asal saja, hanya qty > 0.
    """
    session = get_object_or_404(RakTransferSession, id=session_id)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        draw = int(request.GET.get('draw', 1))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 25))
        search_value = request.GET.get('search[value]', '')

        queryset = (
            InventoryRakStock.objects.select_related('product', 'rak')
            .filter(rak=session.rak_asal, quantity__gt=0)
        )

        if search_value:
            queryset = queryset.filter(
                Q(product__sku__icontains=search_value)
                | Q(product__nama_produk__icontains=search_value)
            )

        total_records = queryset.count()
        stocks = queryset.order_by('product__nama_produk')[start : start + length]

        data = []
        for s in stocks:
            data.append(
                {
                    'id': s.id,
                    'product_id': s.product_id,
                    'product_name': getattr(s.product, 'nama_produk', str(s.product)),
                    'variant_produk': getattr(s.product, 'variant_produk', ''),
                    'sku': getattr(s.product, 'sku', ''),
                    'barcode': getattr(s.product, 'barcode', ''),
                    'brand': getattr(s.product, 'brand', ''),
                    'qty_asal': s.quantity,
                }
            )

        return JsonResponse(
            {
                'draw': draw,
                'recordsTotal': total_records,
                'recordsFiltered': total_records,
                'data': data,
            }
        )

    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
@permission_required('inventory.view_raktransfer', raise_exception=True)
def transfer_rak_detail(request, session_id):
    """
    Halaman detail transfer rak
    """
    session = get_object_or_404(RakTransferSession, id=session_id)
    
    # Calculate total quantity
    total_qty = session.items.aggregate(total=Sum('qty_transfer'))['total'] or 0
    
    context = {
        'session': session,
        'rak_asal': session.rak_asal,
        'rak_tujuan': session.rak_tujuan,
        'items': session.items.select_related('product').all(),
        'total_qty': total_qty
    }
    
    return render(request, 'inventory/transfer_rak_detail.html', context)


@login_required
@permission_required('inventory.delete_raktransfer', raise_exception=True)
def transfer_rak_cancel(request, session_id):
    """
    Halaman pembatalan transfer rak
    """
    session = get_object_or_404(RakTransferSession, id=session_id)
    
    if session.status != 'draft':
        messages.error(request, 'Sesi transfer ini tidak dapat dibatalkan')
        return redirect('inventory:transfer_rak_list')
    
    if request.method == 'POST':
        alasan = request.POST.get('alasan', '')
        
        with transaction.atomic():
            session.status = 'dibatalkan'
            session.save()
            
            # Add log entry if needed
            messages.success(request, f'Sesi transfer {session.session_code} berhasil dibatalkan')
            return redirect('inventory:transfer_rak_list')
    
    # Calculate total quantity
    total_qty = session.items.aggregate(total=Sum('qty_transfer'))['total'] or 0
    
    context = {
        'session': session,
        'rak_asal': session.rak_asal,
        'rak_tujuan': session.rak_tujuan,
        'items': session.items.select_related('product').all(),
        'total_qty': total_qty
    }
    
    return render(request, 'inventory/transfer_rak_cancel.html', context)


@login_required
def transfer_rak_items_data(request, session_id):
    """
    DataTables sumber data untuk daftar item yang dipilih pada sesi transfer.
    Juga mendukung request non-DataTables untuk putaway.
    """
    session = get_object_or_404(RakTransferSession, id=session_id)

    # Jika request dari putaway (non-DataTables)
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        queryset = session.items.select_related('product').order_by('product__nama_produk')
        data = []
        for it in queryset:
            data.append({
                'id': it.id,  # ID dari RakTransferItem
                'product_id': it.product.id,  # ID dari Product (ini yang penting!)
                'product_name': getattr(it.product, 'nama_produk', str(it.product)),
                'nama_produk': getattr(it.product, 'nama_produk', str(it.product)),
                'variant_produk': getattr(it.product, 'variant_produk', ''),
                'sku': getattr(it.product, 'sku', ''),
                'barcode': getattr(it.product, 'barcode', ''),
                'brand': getattr(it.product, 'brand', ''),
                'stok_asal': it.qty_asal_sebelum,
                'qty_transfer': it.qty_transfer,
                'stok_setelah': it.qty_asal_sesudah,
            })
        
        return JsonResponse({
            'success': True,
            'items': data
        })

    # Jika request dari DataTables
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 25))

    queryset = session.items.select_related('product').order_by('product__nama_produk')
    total_records = queryset.count()
    items = queryset[start : start + length]

    data = []
    for it in items:
        data.append({
            'id': it.id,  # ID dari RakTransferItem
            'product_id': it.product.id,  # ID dari Product
            'product_name': getattr(it.product, 'nama_produk', str(it.product)),
            'variant_produk': getattr(it.product, 'variant_produk', ''),
            'sku': getattr(it.product, 'sku', ''),
            'barcode': getattr(it.product, 'barcode', ''),
            'brand': getattr(it.product, 'brand', ''),
            'stok_asal': it.qty_asal_sebelum,
            'qty_transfer': it.qty_transfer,
            'stok_setelah': it.qty_asal_sesudah,
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data,
    })


@login_required
@require_http_methods(["POST"])
def transfer_rak_add_item(request, session_id):
    """
    Tambah atau akumulasi item ke sesi transfer dari rak asal.
    Body: product_id, qty (default 1)
    """
    session = get_object_or_404(RakTransferSession, id=session_id)
    product_id = request.POST.get('product_id')
    qty = int(request.POST.get('qty', '1') or '1')

    if not product_id:
        return JsonResponse({'success': False, 'message': 'product_id wajib diisi'})
    if qty <= 0:
        return JsonResponse({'success': False, 'message': 'Qty harus > 0'})

    stock_asal = (
        InventoryRakStock.objects.select_related('product')
        .filter(rak=session.rak_asal, product_id=product_id)
        .first()
    )
    if not stock_asal or stock_asal.quantity <= 0:
        return JsonResponse({'success': False, 'message': 'Stok rak asal kosong'})

    # Batasi qty tidak melebihi stok asal
    qty = min(qty, max(0, stock_asal.quantity))

    stock_tujuan = (
        InventoryRakStock.objects.filter(rak=session.rak_tujuan, product_id=product_id)
        .first()
    )
    qty_tujuan_awal = stock_tujuan.quantity if stock_tujuan else 0

    with transaction.atomic():
        item, created = RakTransferItem.objects.select_for_update().get_or_create(
            session=session,
            product_id=product_id,
            defaults={
                'qty_transfer': 0,
                'qty_asal_sebelum': stock_asal.quantity,
                'qty_asal_sesudah': stock_asal.quantity,
                'qty_tujuan_sebelum': qty_tujuan_awal,
                'qty_tujuan_sesudah': qty_tujuan_awal,
            },
        )

        new_qty_transfer = item.qty_transfer + qty
        if new_qty_transfer > stock_asal.quantity:
            return JsonResponse(
                {
                    'success': False,
                    'message': 'Qty melebihi stok rak asal',
                }
            )

        item.qty_transfer = new_qty_transfer
        item.qty_asal_sebelum = stock_asal.quantity
        item.qty_asal_sesudah = stock_asal.quantity - new_qty_transfer
        item.qty_tujuan_sebelum = qty_tujuan_awal
        item.qty_tujuan_sesudah = qty_tujuan_awal + new_qty_transfer
        item.save()

    return JsonResponse({'success': True, 'message': 'Item ditambahkan/diupdate'})


@login_required
@require_http_methods(["POST"])
def transfer_rak_update_item(request, item_id):
    """
    Update qty item pada sesi transfer (overwrite qty_transfer).
    Body: qty
    """
    item = get_object_or_404(RakTransferItem.objects.select_related('session', 'product'), id=item_id)
    qty = int(request.POST.get('qty', '0') or '0')
    if qty <= 0:
        return JsonResponse({'success': False, 'message': 'Qty harus > 0'})

    # Ambil stok saat ini dari rak asal & tujuan
    stock_asal = (
        InventoryRakStock.objects.filter(rak=item.session.rak_asal, product=item.product).first()
    )
    stock_tujuan = (
        InventoryRakStock.objects.filter(rak=item.session.rak_tujuan, product=item.product).first()
    )
    qty_asal_awal = stock_asal.quantity if stock_asal else 0
    qty_tujuan_awal = stock_tujuan.quantity if stock_tujuan else 0

    if qty > qty_asal_awal:
        return JsonResponse({'success': False, 'message': 'Qty melebihi stok rak asal'})

    with transaction.atomic():
        item.qty_transfer = qty
        item.qty_asal_sebelum = qty_asal_awal
        item.qty_asal_sesudah = qty_asal_awal - qty
        item.qty_tujuan_sebelum = qty_tujuan_awal
        item.qty_tujuan_sesudah = qty_tujuan_awal + qty
        item.save()

    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def transfer_rak_delete_item(request, item_id):
    item = get_object_or_404(RakTransferItem, id=item_id)
    item.delete()
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def transfer_rak_finish(request, session_id):
    """
    Commit transfer: update InventoryRakStock rak asal & tujuan dan buat log InventoryRakStockLog.
    """
    session = get_object_or_404(RakTransferSession, id=session_id)

    if session.status != 'draft':
        return JsonResponse({'success': False, 'message': 'Sesi tidak dalam status draft'})

    with transaction.atomic():
        items = list(session.items.select_related('product'))
        for it in items:
            # Update stok rak asal (keluar)
            stock_asal, _ = InventoryRakStock.objects.select_for_update().get_or_create(
                rak=session.rak_asal, product=it.product, defaults={'quantity': 0}
            )
            if it.qty_transfer > stock_asal.quantity:
                transaction.set_rollback(True)
                return JsonResponse({'success': False, 'message': f'Stok {it.product.sku} tidak mencukupi'})

            qty_awal = stock_asal.quantity
            stock_asal.quantity = qty_awal - it.qty_transfer
            stock_asal.save()

            InventoryRakStockLog.objects.create(
                produk=it.product,
                rak=session.rak_asal,
                tipe_pergerakan='transfer_keluar',
                qty=-it.qty_transfer,
                qty_awal=qty_awal,
                qty_akhir=stock_asal.quantity,
                referensi=session,
                user=request.user,
                catatan=f'Transfer ke {session.rak_tujuan.kode_rak}',
            )

            # Selalu arahkan ke putaway: tambah ke Stock.quantity_putaway (pusat)
            from .models import Stock
            stock_global, _ = Stock.objects.select_for_update().get_or_create(
                product=it.product,
                defaults={'quantity': 0, 'quantity_locked': 0, 'quantity_putaway': 0},
            )
            stock_global.quantity_putaway += it.qty_transfer
            stock_global.save()

        # Tandai sesi siap putaway dan set mode
        session.status = 'ready_for_putaway'
        if session.mode != 'transfer_putaway':
            session.mode = 'transfer_putaway'
        session.save()

    return JsonResponse({'success': True, 'message': 'Transfer selesai'})


@login_required
def transfer_rak_statistics(request, session_id):
    session = get_object_or_404(RakTransferSession, id=session_id)
    total_items = session.items.count()
    total_qty = session.items.aggregate(total=Sum('qty_transfer'))['total'] or 0

    # progress percent berbasis jumlah item bertanda qty > 0 dari total baris stok asal (approx)
    total_source_products = (
        InventoryRakStock.objects.filter(rak=session.rak_asal, quantity__gt=0).count()
    )
    progress_percent = 0
    if total_source_products:
        progress_percent = int(min(100, (total_items / total_source_products) * 100))

    return JsonResponse(
        {
            'total_items': total_items,
            'total_qty': total_qty,
            'progress_percent': f'{progress_percent}%',
        }
    )


@login_required
def transfer_rak_putaway(request, session_id):
    """
    Halaman putaway untuk sesi transfer rak
    """
    import re
    
    transfer_session = get_object_or_404(RakTransferSession, id=session_id)
    
    if transfer_session.status != 'ready_for_putaway':
        messages.error(request, 'Sesi transfer tidak siap untuk putaway')
        return redirect('inventory:putaway')
    
    # Mobile detection
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = re.search(r'mobile|android|iphone', user_agent)
    
    template_name = 'inventory/transfer_putaway_mobile.html' if is_mobile else 'inventory/transfer_putaway.html'
    
    context = {
        'transfer_session': transfer_session,
        'is_mobile': is_mobile,
    }
    return render(request, template_name, context)


@login_required
@require_http_methods(["GET"])
def transfer_putaway_scan_product(request):
    """
    AJAX endpoint untuk scan barcode produk di transfer putaway
    """
    barcode = request.GET.get('barcode', '').strip()
    session_id = request.GET.get('session_id')
    
    if not barcode:
        return JsonResponse({'error': 'Barcode tidak boleh kosong'}, status=400)
    
    if not session_id:
        return JsonResponse({'error': 'Session ID tidak boleh kosong'}, status=400)
    
    try:
        session = RakTransferSession.objects.get(id=session_id)
        
        if session.status != 'ready_for_putaway':
            return JsonResponse({'error': 'Sesi transfer tidak siap untuk putaway'}, status=400)
        
        # Cari produk berdasarkan barcode
        product = Product.objects.filter(barcode=barcode).first()
        if not product:
            return JsonResponse({'error': f'Produk dengan barcode "{barcode}" tidak ditemukan'}, status=404)
        
        # Cek apakah produk ada di transfer session
        transfer_item = RakTransferItem.objects.filter(
            session=session,
            product=product
        ).first()
        
        if not transfer_item:
            return JsonResponse({'error': f'Produk {product.nama_produk} tidak ada dalam sesi transfer ini'}, status=400)
        
        return JsonResponse({
            'success': True,
            'product': {
                'id': product.id,
                'sku': product.sku,
                'barcode': product.barcode,
                'nama_produk': product.nama_produk,
                'variant_produk': product.variant_produk or '',
                'brand': product.brand or '',
                'qty_transfer': transfer_item.qty_transfer,
            }
        })
    except RakTransferSession.DoesNotExist:
        return JsonResponse({'error': 'Sesi transfer tidak ditemukan'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Terjadi kesalahan: {str(e)}'}, status=500)

@login_required
@require_http_methods(["POST"])
def transfer_rak_scan_product(request, session_id):
    """
    Scan barcode/SKU untuk menambah item ke transfer rak
    """
    session = get_object_or_404(RakTransferSession, id=session_id)
    
    if session.status != 'draft':
        return JsonResponse({'success': False, 'message': 'Sesi tidak dalam status draft'})
    
    barcode = request.POST.get('barcode', '').strip()
    qty = int(request.POST.get('qty', 1))
    
    if not barcode:
        return JsonResponse({'success': False, 'message': 'Barcode/SKU tidak boleh kosong'})
    
    if qty <= 0:
        return JsonResponse({'success': False, 'message': 'Quantity harus lebih dari 0'})
    
    try:
        # Cari produk berdasarkan barcode atau SKU
        product = Product.objects.filter(
            Q(barcode__iexact=barcode) | 
            Q(sku__iexact=barcode) |
            Q(extra_barcodes__barcode__iexact=barcode)
        ).distinct().first()
        
        if not product:
            return JsonResponse({'success': False, 'message': f'Produk dengan barcode/SKU "{barcode}" tidak ditemukan'})
        
        # Cek apakah produk ada stok di rak asal
        stock_asal = InventoryRakStock.objects.filter(
            rak=session.rak_asal,
            product=product
        ).first()
        
        if not stock_asal or stock_asal.quantity <= 0:
            return JsonResponse({'success': False, 'message': f'Produk {product.sku} tidak ada stok di rak asal ({session.rak_asal.kode_rak})'})
        
        if stock_asal.quantity < qty:
            return JsonResponse({'success': False, 'message': f'Stok tidak mencukupi. Tersedia: {stock_asal.quantity}, Diminta: {qty}'})
        
        # Cek apakah item sudah ada di transfer
        existing_item = RakTransferItem.objects.filter(
            session=session,
            product=product
        ).first()
        
        if existing_item:
            # Update quantity jika sudah ada
            new_qty = existing_item.qty_transfer + qty
            if new_qty > stock_asal.quantity:
                return JsonResponse({'success': False, 'message': f'Total quantity ({new_qty}) melebihi stok tersedia ({stock_asal.quantity})'})
            
            existing_item.qty_transfer = new_qty
            existing_item.qty_asal_sesudah = stock_asal.quantity - new_qty
            existing_item.save()
            
            return JsonResponse({
                'success': True, 
                'message': f'Quantity {product.sku} diperbarui menjadi {new_qty}',
                'product_name': product.nama_produk
            })
        else:
            # Buat item baru
            RakTransferItem.objects.create(
                session=session,
                product=product,
                qty_asal_sebelum=stock_asal.quantity,
                qty_transfer=qty,
                qty_asal_sesudah=stock_asal.quantity - qty,
                qty_tujuan_sebelum=0,  # Default 0 karena belum ada di rak tujuan
                qty_tujuan_sesudah=qty  # Setelah transfer akan ada qty di rak tujuan
            )
            
            return JsonResponse({
                'success': True, 
                'message': f'Item {product.sku} berhasil ditambahkan',
                'product_name': product.nama_produk
            })
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Terjadi kesalahan: {str(e)}'})

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def transfer_putaway_save(request):
    """
    Menyimpan data transfer putaway
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Transfer putaway save request received: {request.body}")
        data = json.loads(request.body)
        session_id = data.get('session_id')
        rak_id = data.get('rak_id')
        items_to_putaway = data.get('items', [])
        
        logger.info(f"Parsed data: session_id={session_id}, rak_id={rak_id}, items_count={len(items_to_putaway)}")
        
        if not session_id:
            return JsonResponse({'success': False, 'error': 'Session ID wajib diisi.'}, status=400)
        
        if not rak_id:
            return JsonResponse({'success': False, 'error': 'Rak tujuan wajib diisi.'}, status=400)
        
        if not items_to_putaway:
            return JsonResponse({'success': False, 'error': 'Tidak ada item untuk diputaway.'}, status=400)
        
        # Get transfer session
        transfer_session = RakTransferSession.objects.get(id=session_id)
        if transfer_session.status != 'ready_for_putaway':
            return JsonResponse({'success': False, 'error': 'Sesi transfer tidak siap untuk putaway.'}, status=400)
        
        # Get rak tujuan
        rak = Rak.objects.get(id=rak_id)
        if rak.id != transfer_session.rak_tujuan.id:
            return JsonResponse({'success': False, 'error': 'Rak tujuan tidak sesuai dengan sesi transfer.'}, status=400)
        
        # Use centralized PutawayService
        from .putaway import PutawayService
        
        result = PutawayService.process_putaway(
            request=request,
            rak_id=rak_id,
            items_to_putaway=items_to_putaway,
            putaway_type='transfer',
            session_id=session_id
        )
        
        if result['success']:
            return JsonResponse({'success': True, 'message': result['message']})
        else:
            return JsonResponse({'success': False, 'error': result['error']}, status=400)
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return JsonResponse({'success': False, 'error': 'Format data JSON tidak valid.'}, status=400)
    except (RakTransferSession.DoesNotExist, Rak.DoesNotExist, Product.DoesNotExist, RakTransferItem.DoesNotExist) as e:
        logger.error(f"Model not found error: {e}")
        return JsonResponse({'success': False, 'error': f'Item tidak ditemukan: {str(e)}'}, status=404)
    except Exception as e:
        logger.error(f"Unexpected error in transfer_putaway_save: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': f'Terjadi kesalahan server: {str(e)}'}, status=500)


@login_required
def putaway_history_list(request):
    """
    API endpoint untuk DataTables - history putaway dari transfer rak
    """
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        draw = int(request.GET.get('draw', 1))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 25))
        search_value = request.GET.get('search[value]', '')
        
        # Ambil sesi transfer yang sudah selesai (status = 'selesai')
        queryset = RakTransferSession.objects.filter(
            status='selesai',
            mode='transfer_putaway'
        ).select_related('rak_asal', 'rak_tujuan').prefetch_related('items')
        
        # Apply search
        if search_value:
            queryset = queryset.filter(
                Q(session_code__icontains=search_value) |
                Q(rak_asal__kode_rak__icontains=search_value) |
                Q(rak_asal__nama_rak__icontains=search_value) |
                Q(rak_tujuan__kode_rak__icontains=search_value) |
                Q(rak_tujuan__nama_rak__icontains=search_value)
            )
        
        # Get total count before pagination
        total_records = queryset.count()
        
        # Apply ordering and pagination
        queryset = queryset.order_by('-tanggal_transfer')[start:start + length]
        
        # Prepare data for DataTables
        data = []
        for session in queryset:
            total_qty = session.items.aggregate(total=Sum('qty_transfer'))['total'] or 0
            data.append({
                'id': session.id,
                'session_code': session.session_code,
                'rak_asal_lokasi': f"{session.rak_asal.lokasi} ({session.rak_asal.kode_rak})",
                'rak_tujuan_lokasi': f"{session.rak_tujuan.lokasi} ({session.rak_tujuan.kode_rak})",
                'total_items': session.items.count(),
                'total_qty': total_qty,
                'tanggal_transfer': session.tanggal_transfer.strftime('%Y-%m-%d %H:%M'),
            })
        
        return JsonResponse({
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': total_records,
            'data': data
        })
    
    # Regular page request - redirect to main transfer list
    return redirect('inventory:transfer_rak_list')
