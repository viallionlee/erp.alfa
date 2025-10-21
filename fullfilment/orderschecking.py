# File khusus logic orders checking (scan order, tampil tabel, scan barcode, dsb)
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db.models import F
from orders.models import Order, OrderPackingHistory
from .models import ReadyToPrint, OrdersCheckingHistory
from products.models import Product  # Pastikan import model Product
from django.views.decorators.csrf import ensure_csrf_cookie
import json
from django.db import transaction
from .models import BatchItem, BatchItemLog
from inventory.models import Stock # Import model Stock


from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied


@login_required
def orders_checking(request, order_id=None):
    """
    View untuk mobile/desktop scanpicking
    Sederhana dan fokus: Mobile pakai mobile_scanpicking.html
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent
    
    # Check permissions
    if is_mobile:
        if not request.user.has_perm('fullfilment.view_mobile_picking_module'):
            raise PermissionDenied
    else:
        if not request.user.has_perm('fullfilment.view_desktop_picking_module'):
            raise PermissionDenied
    
    # Tentukan template berdasarkan mobile/desktop saja (SEDERHANA!)
    template = 'fullfilment/mobile_scanpicking.html' if is_mobile else 'fullfilment/scanpicking.html'
    
    # Jika tanpa order_id, render halaman input
    if order_id is None:
        return render(request, template)
    
    # Jika ada order_id, proses dan tampilkan data
    context = {
        'order_id': order_id,
        'show_tables': False,
    }
    
    # Cek apakah order ini sudah pernah di-pack sebelumnya
    packing_history = OrderPackingHistory.objects.filter(order__id_pesanan=order_id).select_related('user').first()
    if packing_history:
        context.update({
            'is_already_packed': True,
            'packed_at': packing_history.waktu_pack.strftime('%d %b %Y, %H:%M'),
            'packed_by': packing_history.user.username if packing_history.user else 'N/A',
        })
    
    # Query orders untuk order_id ini
    orders = Order.objects.filter(id_pesanan=order_id).exclude(status_bundle='Y').select_related('product')
    if orders.exists():
        first_order = orders.first()
        
        # Check jika order dibatalkan
        from .models import OrderCancelLog 
        
        if 'batal' in (first_order.status or '').lower() or \
           'cancel' in (first_order.status or '').lower() or \
           'batal' in (first_order.status_order or '').lower() or \
           'cancel' in (first_order.status_order or '').lower():
            # Cek apakah OrderCancelLog sudah ada untuk Order ID ini
            if not OrderCancelLog.objects.filter(order_id_scanned=order_id).exists():
                OrderCancelLog.objects.create(
                    order_id_scanned=order_id,
                    user=request.user if request.user.is_authenticated else None,
                    status_pembayaran_at_scan=first_order.status,
                    status_fulfillment_at_scan=first_order.status_order
                )
            context['error'] = f"Halo {request.user.username} , Orderan ini {order_id} sudah dibatalkan customer , tolong di retur ke tim retur , Terima Kasih , Semangat terus!"
            context['show_tables'] = False
            return render(request, template, context)
        
        # Check status order
        status = (first_order.status_order or '').lower()
        if 'batal' in status or 'cancel' in status:
            context['error'] = f"ERROR - Order ini berstatus '{first_order.status_order}' dan tidak bisa diproses."
        elif not status or status == 'pending':
            context['error'] = "ERROR - Order ini belum di Proses Batchpicking 'Printed'"
        elif status == 'picked':
            context['error'] = "Order sudah pernah di `Picked` sekarang lanjut proses `Packed` nya"
        elif status == 'printed':
            # Tampilkan tabel produk untuk dipicking
            def build_rows(qs):
                rows = []
                for o in qs:
                    p = o.product
                    if o.jumlah_ambil == o.jumlah and o.jumlah > 0:
                        status_ambil = 'completed'
                    elif o.jumlah_ambil > 0:
                        status_ambil = 'partial'
                    else:
                        status_ambil = 'pending'
                    rows.append({
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
            
            pending = orders.filter(jumlah_ambil__lt=F('jumlah'))
            completed = orders.filter(jumlah_ambil=F('jumlah'), jumlah__gt=0)
            context.update({
                'show_tables': True,
                'order_id': order_id,
                'pending_orders': build_rows(pending),
                'completed_orders': build_rows(completed),
            })
        elif status == 'packed':
            context['error'] = "ERROR - Order ini sudah pernah di 'Packed'"
        elif status == 'shipped':
            context['error'] = "ERROR - Order ini sudah pernah di 'Shipped'"
        else:
            context['error'] = f"ERROR - Status order tidak valid: '{first_order.status_order}'"
    else:
        context['error'] = 'Order ID tidak ditemukan.'
    return render(request, template, context)


def orders_checking_scan_barcode(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method.'}, status=405)
    try:
        data = json.loads(request.body)
        barcode = data.get('barcode')
        if not barcode:
            return JsonResponse({'success': False, 'error': 'Barcode required.'})
        # Cari product dengan barcode
        try:
            product = Product.objects.get(barcode=barcode)
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Barcode tidak ditemukan.'})
        # Cari order yang sesuai TANPA filter status_bundle
        try:
            order = Order.objects.get(id_pesanan=order_id, product=product)
        except Order.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Barcode tidak valid atau tidak ditemukan pada order ini.'})
        
        # RE-ADDED: Validasi status order pembayaran (dari frontend 'status')
        # Jika status pembayaran mengandung 'batal' atau 'cancel' (case-insensitive)
        if 'batal' in (order.status or '').lower() or \
           'cancel' in (order.status or '').lower() or \
           'batal' in (order.status_order or '').lower() or \
           'cancel' in (order.status_order or '').lower():
            from .models import OrderCancelLog # Import here to avoid circular dependency if placed at top
            # RE-ADDED: Cek apakah OrderCancelLog sudah ada untuk Order ID ini
            if not OrderCancelLog.objects.filter(order_id_scanned=order_id).exists():
                OrderCancelLog.objects.create(
                    order_id_scanned=order_id,
                    user=request.user if request.user.is_authenticated else None,
                    status_pembayaran_at_scan=order.status,
                    status_fulfillment_at_scan=order.status_order
                )
            return JsonResponse({
                'success': False,
                'message': f"Halo {request.user.username} , Orderan ini {order_id} sudah dibatalkan customer , tolong di retur ke tim retur , Terima Kasih , Semangat terus!"
            })

        # Validasi status_order harus 'printed'
        if order.status_order != 'printed':
            return JsonResponse({'success': False, 'error': f"Scan Gagal! Status order ini adalah '{order.status_order}', bukan 'printed'."})

        # Validasi wajib ada nama_batch
        if not order.nama_batch:
            return JsonResponse({'success': False, 'error': 'Scan Gagal! Order ini belum masuk ke dalam batch manapun.'})

        # Cek over input
        if order.jumlah_ambil >= order.jumlah:
            return JsonResponse({'success': False, 'error': 'Over input: Produk telah melewati batas input'})
        
        # Update jumlah_ambil jika masih kurang dari jumlah
        order.jumlah_ambil += 1
        order.save()
        
        # Tentukan status item yang BARU SAJA di-scan
        status_scanned_item = 'completed' if order.jumlah_ambil == order.jumlah else 'partial'

        # Buat entri log histori
        OrdersCheckingHistory.objects.create(
            id_pesanan=order_id,
            user=request.user if request.user.is_authenticated else None,
            barcode_scanned=barcode
        )

        # Ambil ulang data tabel, exclude status_bundle='Y'
        orders = Order.objects.filter(id_pesanan=order_id).exclude(status_bundle='Y').select_related('product')
        
        def build_rows(qs):
            rows = []
            for o in qs:
                p = o.product
                if o.jumlah_ambil == o.jumlah and o.jumlah > 0:
                    status_ambil_row = 'completed'
                elif o.jumlah_ambil > 0:
                    status_ambil_row = 'partial'
                else:
                    status_ambil_row = 'pending'
                rows.append({
                    'sku': o.sku,
                    'barcode': p.barcode if p else '',
                    'nama_produk': p.nama_produk if p else '',
                    'variant_produk': p.variant_produk if p else '',
                    'brand': p.brand if p else '',
                    'jumlah': o.jumlah,
                    'jumlah_ambil': o.jumlah_ambil,
                    'status_ambil': status_ambil_row,
                    'photo_url': p.photo.url if p and p.photo else ''
                })
            return rows

        pending = orders.filter(jumlah_ambil__lt=F('jumlah'))
        completed = orders.filter(jumlah_ambil=F('jumlah'), jumlah__gt=0)
        
        # Jika tidak ada lagi item yang pending, update status order menjadi 'picked'
        # Logika ini TETAP DIPERLUKAN untuk mengupdate status di database, 
        # hanya flag 'all_order_completed' yang dihapus dari respons.
        if not pending.exists() and completed.exists():
            Order.objects.filter(id_pesanan=order_id).update(status_order='picked')

        return JsonResponse({
            'success': True,
            'pending_orders': build_rows(pending),
            'completed_orders': build_rows(completed),
            'sku': order.sku,
            'status_ambil': status_scanned_item
            # 'all_order_completed' flag has been removed from the response
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def orders_checking_history(request):
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent

    if is_mobile:
        if not request.user.has_perm('fullfilment.view_mobile_picking_module'):
            raise PermissionDenied
    else:
        if not request.user.has_perm('fullfilment.view_desktop_picking_module'):
            raise PermissionDenied
            
    """
    Menampilkan halaman histori semua aktivitas order checking.
    """
    from django.core.paginator import Paginator
    from orders.models import Order
    from django.utils import timezone
    from datetime import datetime, time
    
    history_list = OrdersCheckingHistory.objects.all().order_by('-id')
    
    # Pagination
    paginator = Paginator(history_list, 50)  # 50 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Hitung sisa order printed (order dengan status_order='printed' tapi belum diserahkan)
    sisa_order_printed = Order.objects.filter(status_order='printed').count()
    
    # Hitung total aktivitas scan hari ini
    today = timezone.now().date()
    today_start = datetime.combine(today, time.min)
    today_end = datetime.combine(today, time.max)
    total_aktivitas_hari_ini = OrdersCheckingHistory.objects.filter(
        scan_time__range=(today_start, today_end)
    ).count()
    
    context = {
        'page_obj': page_obj,
        'history_list': page_obj.object_list,
        'sisa_order_printed': sisa_order_printed,
        'total_aktivitas_hari_ini': total_aktivitas_hari_ini
    }
    return render(request, 'fullfilment/scanpicking_history.html', context)


@csrf_exempt # Pastikan ini HANYA untuk development, gunakan CSRF token di produksi
@require_POST
def update_by_click_view(request, order_id):
    try:
        data = json.loads(request.body)
        order_item_id = data.get('order_item_id') # Ambil ID order item
        
        if not order_item_id:
            return JsonResponse({'success': False, 'error': 'Order Item ID is required.'})

        with transaction.atomic():
            try:
                # Cari Order item berdasarkan ID
                order_item = Order.objects.get(id=order_item_id, id_pesanan=order_id, status_bundle='N')
            except Order.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Order Item tidak ditemukan.'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': f'Error mencari Order Item: {str(e)}'})

            # Validasi status_order harus 'printed'
            if order_item.status_order != 'printed':
                return JsonResponse({'success': False, 'error': f"Update Gagal! Status order ini adalah '{order_item.status_order}', bukan 'printed'."})

            # Cek over input
            if order_item.jumlah_ambil >= order_item.jumlah:
                return JsonResponse({'success': False, 'error': 'Over input: Jumlah ambil sudah mencapai batas.'})

            # Update jumlah_ambil
            order_item.jumlah_ambil = F('jumlah_ambil') + 1
            order_item.save(update_fields=['jumlah_ambil']) # Hanya update field ini

            # Refresh data dari DB untuk mendapatkan nilai terbaru
            order_item.refresh_from_db()

            # Tentukan status item yang BARU SAJA di-click
            status_clicked_item = 'completed' if order_item.jumlah_ambil == order_item.jumlah else 'partial'
            
            # Re-fetch semua order item untuk order_id ini
            all_orders_for_current_id = Order.objects.filter(id_pesanan=order_id).exclude(status_bundle='Y').select_related('product')
            
            def build_rows_for_clickpicking(qs_list):
                rows = []
                for o in qs_list:
                    p = o.product
                    if o.jumlah_ambil == o.jumlah and o.jumlah > 0:
                        status_ambil_row = 'completed'
                    elif o.jumlah_ambil > 0:
                        status_ambil_row = 'partial'
                    else:
                        status_ambil_row = 'pending'
                    rows.append({
                        'id': o.id,
                        'sku': o.sku,
                        'barcode': p.barcode if p else '',
                        'nama_produk': p.nama_produk if p else '',
                        'variant_produk': p.variant_produk if p else '',
                        'brand': p.brand if p else '',
                        'jumlah': o.jumlah,
                        'jumlah_ambil': o.jumlah_ambil,
                        'status_ambil': status_ambil_row,
                        'photo_url': p.photo.url if p and p.photo else ''
                    })
                return rows

            # Order by id (ascending) for "from bottom to top" display
            pending = all_orders_for_current_id.filter(jumlah_ambil__lt=F('jumlah')).order_by('id')
            completed = all_orders_for_current_id.filter(jumlah_ambil=F('jumlah'), jumlah__gt=0).order_by('id')
            
            # Jika tidak ada lagi item yang pending, update status order menjadi 'picked'
            all_order_completed = False
            if not pending.exists() and completed.exists():
                Order.objects.filter(id_pesanan=order_id).update(status_order='picked')
                all_order_completed = True

            return JsonResponse({
                'success': True,
                'pending_orders': build_rows_for_clickpicking(pending),
                'completed_orders': build_rows_for_clickpicking(completed),
                'sku': order_item.sku, # Tetap kembalikan SKU dari item yang diupdate
                'status_ambil': status_clicked_item,
                'all_order_completed': all_order_completed
            })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def build_rows_for_clickpicking(order_id):
    # This function should exist from previous steps. 
    # It queries BatchItem and returns pending_orders and completed_orders lists.
    # If it doesn't exist, it needs to be created.
    # Assuming it exists and works.
    pending_orders = BatchItem.objects.filter(
        order__order_id=order_id, 
        status_ambil__in=['pending', 'partial']
    ).order_by('id').values(
        'id', 'sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 
        'photo_url', 'jumlah', 'jumlah_ambil', 'status_ambil'
    )
    completed_orders = BatchItem.objects.filter(
        order__order_id=order_id, 
        status_ambil='completed'
    ).order_by('id').values(
        'id', 'sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 
        'photo_url', 'jumlah', 'jumlah_ambil', 'status_ambil'
    )
    return list(pending_orders), list(completed_orders)


@require_POST
@csrf_exempt
def update_by_click(request, order_id): # order_id here is Order.id_pesanan (from URL)
    try:
        data = json.loads(request.body)
        order_item_id = data.get('order_item_id') # This is Order.id (from frontend payload)
        action = data.get('action', 'increment') # Default to increment if not provided
        
        if not order_item_id:
            return JsonResponse({'success': False, 'error': 'Order Item ID is required.'})

        with transaction.atomic():
            try:
                # 1. Get the specific Order object based on its primary key (id) and id_pesanan
                #    We use select_for_update to lock the row during the transaction.
                order_item_obj = Order.objects.select_for_update().get(
                    id=order_item_id, id_pesanan=order_id
                )
            except Order.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Order item tidak ditemukan.'}, status=404)
            except Exception as e:
                return JsonResponse({'success': False, 'error': f'Error mencari Order Item: {str(e)}'})

            # Validasi status_order harus 'printed'
            if order_item_obj.status_order != 'printed':
                return JsonResponse({'success': False, 'error': f"Update Gagal! Status order ini adalah '{order_item_obj.status_order}', bukan 'printed'."})

            original_jumlah_ambil = order_item_obj.jumlah_ambil

            if action == 'increment':
                if order_item_obj.jumlah_ambil >= order_item_obj.jumlah:
                    return JsonResponse({'success': False, 'error': 'Over input: Jumlah ambil sudah mencapai batas.'})
                order_item_obj.jumlah_ambil += 1
            elif action == 'decrement':
                if order_item_obj.jumlah_ambil <= 0:
                    return JsonResponse({'success': False, 'error': 'Jumlah ambil tidak bisa kurang dari nol.'})
                order_item_obj.jumlah_ambil -= 1
            else:
                return JsonResponse({'success': False, 'error': 'Invalid action specified.'})

            order_item_obj.save(update_fields=['jumlah_ambil'])
            order_item_obj.refresh_from_db() # Get updated value after save

            # Determine new status_ambil
            if order_item_obj.jumlah_ambil == order_item_obj.jumlah and order_item_obj.jumlah > 0:
                status_clicked_item = 'completed'
            elif order_item_obj.jumlah_ambil > 0:
                status_clicked_item = 'partial'
            else:
                status_clicked_item = 'pending'
            
            # Update status_ambil field if it changed
            if order_item_obj.status_ambil != status_clicked_item:
                order_item_obj.status_ambil = status_clicked_item
                order_item_obj.save(update_fields=['status_ambil'])

            OrdersCheckingHistory.objects.create(
                id_pesanan=order_id,
                user=request.user if request.user.is_authenticated else None,
                barcode_scanned=order_item_obj.product.barcode if order_item_obj.product else 'N/A' # Log barcode dari produk Order
            )

            # Re-fetch semua order item untuk order_id ini
            all_orders_for_current_id = Order.objects.filter(id_pesanan=order_id).exclude(status_bundle='Y').select_related('product')
            
            def build_rows_from_order(qs_list):
                rows = []
                for o in qs_list:
                    p = o.product
                    if o.jumlah_ambil == o.jumlah and o.jumlah > 0:
                        status_ambil_row = 'completed'
                    elif o.jumlah_ambil > 0:
                        status_ambil_row = 'partial'
                    else:
                        status_ambil_row = 'pending'
                    rows.append({
                        'id': o.id, # Penting: kembalikan Order.id
                        'sku': o.sku,
                        'barcode': p.barcode if p else '',
                        'nama_produk': p.nama_produk if p else '',
                        'variant_produk': p.variant_produk if p else '',
                        'brand': p.brand if p else '',
                        'jumlah': o.jumlah,
                        'jumlah_ambil': o.jumlah_ambil,
                        'status_ambil': status_ambil_row,
                        'photo_url': p.photo.url if p and p.photo else ''
                    })
                return rows

            pending = all_orders_for_current_id.filter(jumlah_ambil__lt=F('jumlah')).order_by('id')
            completed = all_orders_for_current_id.filter(jumlah_ambil=F('jumlah'), jumlah__gt=0).order_by('id')
            
            # Jika tidak ada lagi item yang pending, update status order menjadi 'picked'
            all_order_completed = False
            if not pending.exists() and completed.exists():
                Order.objects.filter(id_pesanan=order_id).update(status_order='picked')
                all_order_completed = True

            return JsonResponse({
                'success': True,
                'pending_orders': build_rows_from_order(pending),
                'completed_orders': build_rows_from_order(completed),
                'sku': order_item_obj.sku, # Tetap kembalikan SKU dari item yang diupdate
                'status_ambil': status_clicked_item,
                'all_order_completed': all_order_completed,
                'new_jumlah_ambil': order_item_obj.jumlah_ambil # Tambahkan ini untuk update modal
            })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)