# fullfilment/returnlist.py

from django.shortcuts import render, get_object_or_404 # Tambahkan get_object_or_404
from .models import ReturnSession, OrderCancelLog, BatchList, BatchItem, ReturnItem, ReturnSourceLog # Tambahkan ReturnSourceLog
from orders.models import Order, OrderShippingHistory # Tambahkan OrderShippingHistory
from inventory.models import Stock, StockCardEntry # Tambahkan Stock dan StockCardEntry
from products.models import Product, ProductExtraBarcode # Tambahkan Product dan ProductExtraBarcode
from django.db.models import Count, Q, F, Window, OuterRef, Subquery, Sum, Min, Case, When, Value, IntegerField, BooleanField # Tambahkan Sum, Min, OuterRef, Subquery, Case, When, Value, IntegerField, BooleanField
from django.db.models.functions import RowNumber

# Tambahkan impor yang diperlukan untuk fungsi baru
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.utils import timezone
import json
import re # Tambahkan import re untuk mobile detection
# from .models import ReturnItem # Sudah ada di atas
from django.views.decorators.csrf import csrf_exempt # Tambahkan csrf_exempt
import logging # Tambahkan logging
from django.contrib import messages # Tambahkan messages
from django.shortcuts import redirect # Tambahkan redirect
from django.core.paginator import Paginator # NEW
from django.utils.dateformat import format as date_format
import pytz

# FUNGSI HELPER untuk mengelompokkan kurir
def group_courier(courier_name):
    if not courier_name:
        return 'Lainnya'
    
    courier_name_lower = courier_name.lower()
    
    if 'shopee' in courier_name_lower or 'spx' in courier_name_lower:
        return 'Shopee Xpress'
    elif 'j&t' in courier_name_lower or 'jnt' in courier_name_lower:
        return 'J&T Express'
    elif 'jne' in courier_name_lower:
        return 'JNE'
    elif 'lex' in courier_name_lower:
        return 'LEX'
    elif 'ninja' in courier_name_lower:
        return 'Ninja'
    elif 'gtl' in courier_name_lower:
        return 'GTL'
    elif 'cargo' in courier_name_lower:
        return 'CARGO'
    elif 'instant' in courier_name_lower:
        return 'Instant'
    else:
        return courier_name # Jika tidak ada yang cocok, kembalikan nama asli

@login_required
@permission_required('fullfilment.view_returnlist', raise_exception=True)
def returnlist_dashboard(request):
    # Dapatkan ID pesanan yang sudah ada di OrderCancelLog dan belum direturn (digunakan untuk eksklusi)
    order_ids_in_user_log_and_pending_return = OrderCancelLog.objects.filter(
        Q(status_retur='N') | Q(status_retur='') | Q(status_retur__isnull=True)
    ).values_list('order_id_scanned', flat=True).distinct()

    # Query untuk Order Cancel Belum Return (By System, tahap Picking/Packing/Printed)
    # Gunakan distinct('id_pesanan') untuk mendapatkan Order ID yang unique
    order_cancel_by_system_belum_return = Order.objects.filter(
        (Q(status_cancel__icontains='batal') | Q(status_cancel__icontains='cancel') |
         Q(status__icontains='batal') | Q(status__icontains='cancel')),
        Q(status_order__in=['picked', 'packed', 'printed']),
        (Q(status_retur='N') | Q(status_retur='') | Q(status_retur__isnull=True))
    ).exclude(
        id_pesanan__in=order_ids_in_user_log_and_pending_return
    ).order_by('id_pesanan', '-id').distinct('id_pesanan')

    # Subquery to get the status_retur from the Order model for OrderCancelLog
    order_status_retur_subquery = Order.objects.filter(
        id_pesanan=OuterRef('order_id_scanned')
    ).values('status_retur')[:1]

    # Query untuk Order Cancel Belum Return (By User)
    order_cancel_by_user_belum_return = OrderCancelLog.objects.annotate(
        linked_order_status_retur=Subquery(order_status_retur_subquery)
    ).filter(
        Q(linked_order_status_retur='N') | Q(linked_order_status_retur='') | Q(linked_order_status_retur__isnull=True),
        # Filter: Order masih ada di orders_order (jika order sudah di-delete, tidak muncul di list)
        Q(order_id_scanned__in=Order.objects.values_list('id_pesanan', flat=True))
    ).annotate(
        row_num=Window(
            expression=RowNumber(),
            partition_by=[F('order_id_scanned')],
            order_by=[F('scan_time').desc()]
        )
    ).filter(row_num=1).select_related('user')

    # Order Cancel Belum Return (Tahap Shipping)
    # Subquery untuk mendapatkan record history shipping terbaru untuk setiap order
    latest_shipping_history_subquery = OrderShippingHistory.objects.filter(
        order=OuterRef('pk')
    ).order_by('-waktu_ship')

    order_cancel_shipping_qs = Order.objects.filter(
        (Q(status__icontains='batal') | Q(status__icontains='cancel') | Q(status_cancel__icontains='Y')) &
        Q(status_order='shipped') &
        (Q(status_retur='N') | Q(status_retur='') | Q(status_retur__isnull=True))
    ).exclude(
        id_pesanan__in=order_ids_in_user_log_and_pending_return
    ).annotate(
        shipping_time=Subquery(latest_shipping_history_subquery.values('waktu_ship')[:1]),
        shipping_scanner_username=Subquery(latest_shipping_history_subquery.values('user__username')[:1])  # Menambahkan username
    ).order_by('id_pesanan', '-id').distinct('id_pesanan')

    # Tambahkan nama ekspedisi yang dikelompokkan dan waktu shipping ke setiap objek order
    order_cancel_shipping_belum_return_with_details = []
    for order in order_cancel_shipping_qs:
        order.grouped_courier_name = group_courier(order.kurir)
        order_cancel_shipping_belum_return_with_details.append(order)

    # Dapatkan daftar ekspedisi unik yang dikelompokkan dari hasil query shipping
    unique_couriers_in_shipping_cancel = order_cancel_shipping_qs.values_list('kurir', flat=True).distinct()
    grouped_expeditions = sorted(list(set(group_courier(name) for name in unique_couriers_in_shipping_cancel)))

    # Query untuk Overstock Batch Belum Return
    # Dapatkan batch IDs yang memiliki overstock
    batch_ids_with_overstock = BatchItem.objects.filter(
        jumlah_ambil__gt=F('jumlah')
    ).values_list('batchlist_id', flat=True).distinct()
    
    # Ambil BatchList objects dengan annotation
    overstock_batch_belum_return = BatchList.objects.filter(
        id__in=batch_ids_with_overstock
    ).annotate(
        total_sku=Count('items__product', distinct=True),
        total_qty=Sum(F('items__jumlah_ambil') - F('items__jumlah'))
    ).order_by('-created_at')

    # Query untuk Daftar ReturnList - Sort: open di atas, closed di bawah, lalu by created_at
    # Tambahkan annotation untuk mengecek apakah semua item sudah completed putaway
    return_sessions = ReturnSession.objects.annotate(
        jumlah_item=Count('items'),
        # Hitung jumlah item yang belum completed putaway
        pending_putaway_count=Count('items', filter=Q(items__putaway_status__in=['pending', 'partial'])),
        # Hitung jumlah item yang sudah completed putaway
        completed_putaway_count=Count('items', filter=Q(items__putaway_status='completed')),
        # Cek apakah semua item sudah completed (pending_putaway_count = 0)
        all_items_putaway_completed=Case(
            When(pending_putaway_count=0, then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        )
    ).order_by(
        Case(
            When(status='open', then=Value(0)),
            When(status='closed', then=Value(1)),
            default=Value(2),
            output_field=IntegerField()
        ),
        '-created_at'
    ) # Diperbarui: returnlists -> return_sessions, ReturnList -> ReturnSession

    # Hitung jumlah unik untuk ditampilkan di judul
    order_cancel_by_system_count = order_cancel_by_system_belum_return.count()
    order_cancel_by_user_count = order_cancel_by_user_belum_return.count()
    order_cancel_shipping_count = order_cancel_shipping_qs.count() # Gunakan order_cancel_shipping_qs

    # NEW: Tambahkan hitungan untuk ReturnList dan Overstock Batch
    return_sessions_count = return_sessions.count() # Diperbarui: returnlists_count -> return_sessions_count
    overstock_batch_belum_return_count = overstock_batch_belum_return.count()

    context = {
        'order_cancel_by_system_belum_return': order_cancel_by_system_belum_return,
        'order_cancel_by_system_count': order_cancel_by_system_count,
        'order_cancel_by_user_belum_return': order_cancel_by_user_belum_return,
        'order_cancel_by_user_count': order_cancel_by_user_count,
        'order_cancel_shipping_belum_return': order_cancel_shipping_belum_return_with_details,
        'order_cancel_shipping_count': order_cancel_shipping_count,
        'grouped_expeditions_shipping': grouped_expeditions,
        'overstock_batch_belum_return': overstock_batch_belum_return,
        'overstock_batch_belum_return_count': overstock_batch_belum_return_count, # NEW
        'return_sessions': return_sessions, # Diperbarui: returnlists -> return_sessions
        'return_sessions_count': return_sessions_count, # NEW # Diperbarui: returnlists_count -> return_sessions_count
    }
    # Detect mobile user agent and use appropriate template
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = re.search(r'mobile|android|iphone', user_agent)
    
    template_name = 'fullfilment/returnlist_mobile.html' if is_mobile else 'fullfilment/returnlist.html'
    
    return render(request, template_name, context)

@login_required
@require_POST
@permission_required('fullfilment.add_returnlist', raise_exception=True)
def create_returnlist_new(request): # Nama fungsi tetap, tapi akan memproses ReturnSession
    """
    API untuk membuat ReturnList baru berdasarkan input nama/kode dari frontend.
    """
    try:
        data = json.loads(request.body)
        kode = data.get('kode', '').strip()

        if not kode:
            return JsonResponse({'success': False, 'message': 'Kode Return List tidak boleh kosong.'}, status=400)

        with transaction.atomic():
            # Cek apakah kode sudah ada untuk menghindari duplikasi
            if ReturnSession.objects.filter(kode__iexact=kode).exists(): # Diperbarui: ReturnList -> ReturnSession
                return JsonResponse({'success': False, 'message': 'Kode Return List ini sudah ada, gunakan nama lain.'}, status=400)

            return_session = ReturnSession.objects.create( # Diperbarui: returnlist -> return_session, ReturnList -> ReturnSession
                kode=kode,
                # sumber='manual', # Default 'manual' untuk pembuatan dari UI ini (Dihapus karena sumber sudah di ReturnSourceLog)
                created_by=request.user,
                created_at=timezone.now(),
                #status='open' # Dihapus: Pengaturan status awal akan ditangani oleh logic putaway
            )
        return JsonResponse({'success': True, 'message': 'Return List berhasil dibuat!', 'returnlist_id': return_session.id}) # Diperbarui: returnlist_id -> return_session.id
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Terjadi kesalahan: {str(e)}'}, status=500)

@login_required
@require_GET
def get_batch_overstock_detail(request, batch_id):
    """
    API untuk menampilkan detail SKU overstock dari batch tertentu.
    """
    try:
        batch = get_object_or_404(BatchList, id=batch_id)
        
        # Ambil item overstock dari batch
        overstock_items = BatchItem.objects.filter(
            batchlist=batch,
            jumlah_ambil__gt=F('jumlah')  # jumlah_ambil > jumlah
        ).select_related('product').order_by('product__sku')
        
        # Format data untuk response
        overstock_data = []
        for item in overstock_items:
            overstock_qty = item.jumlah_ambil - item.jumlah
            overstock_data.append({
                'sku': item.product.sku,
                'product_name': item.product.nama_produk,
                'barcode': item.product.barcode,
                'variant_produk': item.product.variant_produk or '-',
                'brand': item.product.brand or '-',
                'photo_url': item.product.photo.url if item.product.photo else None,
                'needed_qty': item.jumlah,
                'picked_qty': item.jumlah_ambil,
                'overstock_qty': overstock_qty
            })
        
        return JsonResponse({
            'success': True,
            'batch_name': batch.nama_batch,
            'overstock_items': overstock_data,
            'total_items': len(overstock_data)
        })
        
    except BatchList.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Batch tidak ditemukan.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Terjadi kesalahan: {str(e)}'}, status=500)

@login_required
@require_GET
@permission_required('fullfilment.view_returnlist', raise_exception=True)
def get_returnlists_for_dropdown(request): # Nama fungsi tetap, tapi akan memproses ReturnSession
    """
    API untuk mengambil daftar ReturnList yang sudah ada (status 'open' atau lainnya)
    untuk ditampilkan di dropdown.
    """
    try:
        # Ambil ReturnList yang statusnya 'open' atau yang belum 'validated'
        # Sesuaikan filter sesuai kebutuhan Anda (misal: hanya yang 'open')
        return_sessions = ReturnSession.objects.filter(Q(status='open') | Q(status='pending')).order_by(
            Case(
                When(status='open', then=Value(0)),
                When(status='pending', then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
            ),
            '-created_at'
        ) # Diperbarui: returnlists -> return_sessions, ReturnList -> ReturnSession
        
        data = [{'id': rlist.id, 'kode': rlist.kode} for rlist in return_sessions] # Diperbarui: returnlists -> return_sessions
        return JsonResponse({'success': True, 'returnlists': data}) # Key 'returnlists' tetap untuk kompatibilitas frontend
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Terjadi kesalahan: {str(e)}'}, status=500)

@login_required
@require_POST
@permission_required('fullfilment.change_returnlist', raise_exception=True)
def process_return_scan(request, returnlist_id): # Parameter returnlist_id tetap untuk kompatibilitas URL
    """
    API untuk memproses scan Order ID atau pemilihan Batch Overstock
    dan menambahkan/memperbarui ReturnItem untuk ReturnSession yang diberikan. # Diperbarui: ReturnStockItem -> ReturnItem, ReturnList -> ReturnSession
    """
    try:
        data = json.loads(request.body)
        source_type = data.get('source_type') # 'order_id_scan' atau 'batch_overstock_scan'
        source_value = data.get('source_value') # Nilai Order ID atau Batch ID
        force_return = data.get('force_return', False) # Tambahkan flag force_return

        if not all([source_type, source_value, returnlist_id]):
            return JsonResponse({'success': False, 'message': 'Parameter tidak lengkap.'}, status=400)

        return_session = get_object_or_404(ReturnSession, id=returnlist_id) # Diperbarui: return_list -> return_session, ReturnList -> ReturnSession

        items_to_add = [] # List untuk menampung item yang akan ditambahkan/diupdate
        
        with transaction.atomic():
            if source_type == 'order_id_scan':
                # Ambil semua item dari order ini
                orders_to_return_qs = Order.objects.filter(id_pesanan=source_value).select_related('product')

                if not orders_to_return_qs.exists():
                    return JsonResponse({'success': False, 'message': 'Order ID tidak ditemukan atau tidak memiliki item.'}, status=404)

                # Validasi Status Order untuk Order Cancel
                is_cancelled = orders_to_return_qs.filter(
                    Q(status__icontains='batal') | Q(status__icontains='cancel') |
                    Q(status_order__icontains='batal') | Q(status_order__icontains='cancel')
                ).exclude(
                    Q(status_retur='Y') # Exclude jika sudah berstatus Y (sudah diretur)
                ).exists() # Cek apakah ada setidaknya satu order item yang memenuhi kriteria cancel
                
                is_retur_status_N = orders_to_return_qs.filter(
                    Q(status_retur='N') | Q(status_retur__isnull=True) | Q(status_retur='')
                ).exists()

                # Jika tidak dibatalkan ATAU status_retur bukan 'N'/'', dan tidak ada force_return
                if (not is_cancelled or not is_retur_status_N) and not force_return:
                    return JsonResponse({
                        'success': False,
                        'confirm': True,
                        'message': 'Order ID ini tidak dibatalkan atau sudah diretur. Apakah Anda yakin ingin tetap memprosesnya sebagai return?'
                    }, status=200) # Menggunakan 200 OK karena ini bukan error tapi konfirmasi

                # Jika validasi lolos atau force_return
                for order_item in orders_to_return_qs:
                    if not order_item.product:
                        continue
                    
                    # Update Stock - Return menambah stok siap dijual dan putaway queue
                    from inventory.models import Stock, StockCardEntry
                    stock, created = Stock.objects.get_or_create(
                        product=order_item.product,
                        defaults={'quantity': 0, 'quantity_locked': 0, 'quantity_putaway': 0}
                    )
                    
                    qty_awal = stock.quantity
                    stock.quantity += order_item.jumlah  # Stok siap dijual bertambah
                    stock.quantity_putaway += order_item.jumlah  # Masuk ke putaway queue
                    stock.save(update_fields=['quantity', 'quantity_putaway'])
                    
                    # Buat StockCardEntry untuk audit trail
                    StockCardEntry.objects.create(
                        product=order_item.product,
                        tipe_pergerakan='return_stock',
                        qty=order_item.jumlah,
                        qty_awal=qty_awal,
                        qty_akhir=stock.quantity,
                        notes=f'Return dari Order {source_value}',
                        user=request.user,
                        waktu=timezone.now()
                    )
                    
                    r_item, created = ReturnItem.objects.get_or_create( # Diperbarui: ReturnStockItem -> ReturnItem
                        session=return_session, # Diperbarui: returnlist -> session, return_list -> return_session
                        product=order_item.product,
                        defaults={
                            'qty': order_item.jumlah, # Diperbarui: qty_return -> qty
                            'qc_status': 'pending', # Diperbarui: status -> qc_status
                        }
                    )
                    if not created:
                        r_item.qty += order_item.jumlah # Diperbarui: qty_return -> qty
                        r_item.save(update_fields=['qty']) # Diperbarui: qty_return -> qty
                    
                    items_to_add.append(r_item) # Tambahkan ke list untuk dikembalikan
                
                message = f'{len(items_to_add)} item dari Order ID {source_value} berhasil ditambahkan ke Return List.'

            elif source_type == 'batch_overstock_scan':
                batch_items_overstock = BatchItem.objects.filter(
                    batchlist_id=source_value,
                    jumlah_ambil__gt=F('jumlah')
                ).select_related('product')

                if not batch_items_overstock.exists():
                    return JsonResponse({'success': False, 'message': 'Batch tidak memiliki item overstock.'}, status=404)

                for batch_item in batch_items_overstock:
                    if not batch_item.product:
                        continue
                    
                    overstock_qty = batch_item.jumlah_ambil - batch_item.jumlah
                    if overstock_qty <= 0:
                        continue

                    r_item, created = ReturnItem.objects.get_or_create( # Diperbarui: ReturnStockItem -> ReturnItem
                        session=return_session, # Diperbarui: returnlist -> session, return_list -> return_session
                        product=batch_item.product,
                        defaults={
                            'qty': overstock_qty, # Diperbarui: qty_return -> qty
                            'qc_status': 'pending', # Diperbarui: status -> qc_status
                        }
                    )
                    if not created:
                        r_item.qty += overstock_qty # Diperbarui: qty_return -> qty
                        r_item.save(update_fields=['qty']) # Diperbarui: qty_return -> qty
                    
                    items_to_add.append(r_item) # Tambahkan ke list untuk dikembalikan
                
                message = f'{len(items_to_add)} item overstock dari Batch ID {source_value} berhasil ditambahkan ke Return List.'

            else:
                return JsonResponse({'success': False, 'message': 'Tipe sumber scan tidak valid.'}, status=400)
        
        # Siapkan data ReturnItem untuk dikirim ke frontend # Diperbarui: ReturnStockItem -> ReturnItem
        # Ambil semua ReturnItem untuk ReturnSession yang aktif # Diperbarui: ReturnStockItem -> ReturnItem, ReturnList -> ReturnSession
        return_items = ReturnItem.objects.filter(session=return_session).select_related('product') # Diperbarui: return_stock_items -> return_items, returnlist -> session, return_list -> return_session
        items_data = []
        for item in return_items: # Diperbarui: return_stock_items -> return_items
            items_data.append({
                'id': item.id,
                'product_sku': item.product.sku if item.product else 'N/A',
                'product_name': item.product.nama_produk if item.product else 'N/A',
                'product_variant': item.product.variant_produk if item.product else 'N/A',
                'product_brand': item.product.brand if item.product else 'N/A',
                'qty_target': item.qty, # Diperbarui: qty_return -> qty
                'qc_status': item.qc_status, # Diperbarui: status -> qc_status
            })

        return JsonResponse({
            'success': True,
            'message': message,
            'items_added_count': len(items_to_add),
            'return_items': items_data # Kirim data item kembali ke frontend # Diperbarui: return_stock_items -> return_items
        })
    except BatchList.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Batch tidak ditemukan.'}, status=404)
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Order ID tidak ditemukan.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Terjadi kesalahan saat memproses scan: {str(e)}'}, status=500)

@login_required
def scanordercancel_view(request, return_session_id, order_id=None):
    return_session = get_object_or_404(ReturnSession, id=return_session_id)
    
    # Check if mobile user agent
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = re.search(r'mobile|android|iphone', user_agent)
    
    show_tables = False
    error_message = None

    pending_items_for_template = []
    completed_items_for_template = []

    if order_id:
        print(f"\n--- DEBUG: Memulai proses untuk order_id: {order_id} ---")
        order_items_qs = Order.objects.filter(id_pesanan=order_id)
        print(f"DEBUG: Ditemukan {order_items_qs.count()} item di orders_order untuk ID {order_id}")

        if not order_items_qs.exists():
            error_message = f"Order ID '{order_id}' tidak ditemukan."
            print("DEBUG: Gagal, order_items_qs tidak ada.")
        else:
            # Check if any item in the order has a 'batal' or 'cancel' status
            is_cancelled_any_item = order_items_qs.filter(
                Q(status__icontains='batal') | Q(status__icontains='cancel') |
                Q(status_order__icontains='batal') | Q(status_order__icontains='cancel')
            ).exists()
            print(f"DEBUG: Ada item dengan status 'batal'/'cancel'? -> {is_cancelled_any_item}")

            # Check if any item is still pending return
            has_pending_return_items = order_items_qs.exclude(status_retur='Y').exists()
            print(f"DEBUG: Ada item yang status_retur != 'Y'? -> {has_pending_return_items}")

            # --- NEW LOGIC: Auto-complete return for 'pending' or 'printed' canceled orders ---
            is_pre_picking_cancel = order_items_qs.filter(
                Q(status_order='pending') | Q(status_order='printed')
            ).exists()

            if is_cancelled_any_item and is_pre_picking_cancel and has_pending_return_items:
                # This is the specific case: canceled, pending/printed status_order, and not fully returned yet
                with transaction.atomic():
                    for order_item in order_items_qs:
                        order_item.status_retur = 'Y'
                        order_item.save(update_fields=['status_retur'])

                        # Buat atau update ReturnItem dengan qty 0 (jika memang tidak ada jumlah_ambil)
                        # Ini penting agar ada catatan ReturnItem untuk sesi ini
                        ReturnItem.objects.update_or_create(
                            session=return_session,
                            product=order_item.product,
                            defaults={'qty': 0} # Qty 0 karena tidak ada fisik yang diretur dari awal
                        )

                        # Buat ReturnSourceLog untuk menandai retur otomatis
                        ReturnSourceLog.objects.create(
                            return_item=ReturnItem.objects.get(session=return_session, product=order_item.product),
                            session=return_session,
                            order_id=order_id,
                            qty=0, # Qty 0 karena ini hanya pencatatan log otomatis
                            notes=f"Retur otomatis Order Cancel: ID {order_id} (Status Order: {order_item.status_order}, Status: {order_item.status}).",
                            created_by=request.user,
                        )
                    
                    # Update status ReturnSession menjadi 'qc_done' atau 'closed'
                    #return_session.status = 'closed' # atau 'qc_done' # Dihapus: Pengaturan status akan ditangani oleh logic putaway
                    #return_session.save(update_fields=['status']) # Dihapus: Pengaturan status akan ditangani oleh logic putaway

                # Redirect to returnlist dashboard after auto-completion
                messages.success(request, f"Order ID '{order_id}' berhasil di-autocompleted sebagai retur karena dibatalkan sebelum picking.")
                return redirect('returnlist_dashboard') # Menggunakan redirect untuk kembali

            # --- END NEW LOGIC ---

            # Existing validation logic (if not auto-completed)
            if not is_cancelled_any_item:
                error_message = f"Order ID '{order_id}' tidak memiliki status 'batal' atau 'cancel'."
                print("DEBUG: Gagal, validasi status 'batal' tidak lolos.")
            elif not has_pending_return_items:
                # Semua item sudah diretur, cari info dari ReturnSourceLog
                log = ReturnSourceLog.objects.filter(order_id=order_id).order_by('-created_at').first()
                if log:
                    user = log.created_by.username if log.created_by else 'Unknown'
                    waktu = log.created_at.strftime('%Y-%m-%d %H:%M')
                    error_message = f"Semua item pada Order ID '{order_id}' sudah pernah diretur oleh <b>{user}</b> pada <b>{waktu}</b>."
                else:
                    error_message = f"Semua item pada Order ID '{order_id}' sudah pernah diretur."
                print("DEBUG: Gagal, semua item sudah berstatus retur 'Y'.")
        
        if not error_message:
            print("DEBUG: Validasi lolos, akan menampilkan tabel.")
            show_tables = True
            
            order_items_to_display = order_items_qs.select_related('product').exclude(
                Q(status_bundle='Y') | Q(jumlah_ambil__lte=0) | Q(status_retur='Y')
            )
            print(f"DEBUG: Ditemukan {order_items_to_display.count()} item yang akan ditampilkan (setelah filter bundle, jumlah_ambil, status_retur).")

            for order_item in order_items_to_display:
                print(f"  -> Memproses item: SKU {order_item.product.sku if order_item.product else 'N/A'}, Jumlah Ambil: {order_item.jumlah_ambil}")
                if order_item.product:
                    ReturnItem.objects.update_or_create(
                        session=return_session,
                        product=order_item.product,
                        defaults={'qty': order_item.jumlah_ambil}
                    )

                    photo_url = order_item.product.photo.url if order_item.product.photo and hasattr(order_item.product.photo, 'url') else None
                    
                    item_data = {
                        'id': order_item.id,
                        'sku': order_item.product.sku,
                        'barcode': order_item.product.barcode,
                        'nama_produk': order_item.product.nama_produk,
                        'variant_produk': order_item.product.variant_produk,
                        'brand': order_item.product.brand,
                        'photo_url': photo_url,
                        'jumlah_ambil': order_item.jumlah_ambil,
                    }
                    pending_items_for_template.append(item_data)
        
        print(f"--- DEBUG: Selesai. Error: {error_message}. Jumlah item di pending_items_for_template: {len(pending_items_for_template)} ---")

    context = {
        'return_session': return_session,
        'order_id': order_id,
        'show_tables': show_tables,
        'pending_orders': pending_items_for_template,
        'completed_orders': completed_items_for_template,
        'error': error_message,
    }
    
    # Choose template based on device type
    template_name = 'fullfilment/scanordercancel_mobile.html' if is_mobile else 'fullfilment/scanordercancel.html'
    return render(request, template_name, context)

@login_required
@require_POST
@csrf_exempt
def scanordercancel_scan_barcode(request, return_session_id, order_id):
    try:
        data = json.loads(request.body)
        barcode = data.get('barcode')

        if not barcode:
            return JsonResponse({'success': False, 'message': 'Barcode tidak boleh kosong.'})

        return_session = get_object_or_404(ReturnSession, id=return_session_id)

        # Cari produk berdasarkan barcode
        product = Product.objects.filter(barcode=barcode).first()
        if not product:
            extra_barcode_entry = ProductExtraBarcode.objects.filter(barcode=barcode).select_related('product').first()
            if extra_barcode_entry:
                product = extra_barcode_entry.product
        
        if not product:
            return JsonResponse({'success': False, 'message': 'Produk dengan barcode ini tidak ditemukan.'})
        
        # Cari ReturnItem yang terkait dengan ReturnSession dan produk ini
        return_item = ReturnItem.objects.filter(
            session=return_session,
            product=product
        ).first()

        if not return_item:
            # Jika ReturnItem tidak ada untuk produk ini dalam sesi retur ini, mungkin ini produk yang salah.
            return JsonResponse({'success': False, 'message': f'Produk {product.nama_produk} ({product.sku}) tidak diharapkan dalam sesi retur ini.'})

        # Cek apakah sudah melebihi qty
        if return_item.qty_scanned >= return_item.qty: # Diperbarui: qty_target -> qty
            return JsonResponse({'success': False, 'message': f'Jumlah scan untuk {product.nama_produk} ({product.sku}) sudah mencapai target {return_item.qty}.'}, status=400) # Diperbarui: qty_target -> qty

        # Update qty_scanned (secara "in-memory" untuk respons AJAX)
        # PENTING: Perubahan ini TIDAK disimpan ke database di sini.
        # Database akan diupdate saat tombol submit ditekan.
        return_item.qty_scanned += 1
        
        # Catat user yang melakukan scan barcode (untuk tracking return user)
        # Simpan di session untuk digunakan saat submit
        session_key = f"return_scan_user_{return_session_id}_{order_id}"
        request.session[session_key] = request.user.id
        
        # Tentukan status QC berdasarkan scan terbaru
        if return_item.qty_scanned >= return_item.qty: # Diperbarui: qty_target -> qty
            return_item.qc_status = 'pass'
        elif return_item.qty_scanned > 0 and return_item.qty_scanned < return_item.qty: # Diperbarui: qty_target -> qty
            return_item.qc_status = 'partial'
        else:
            return_item.qc_status = 'pending' # Seharusnya tidak tercapai jika sudah discan 1x

        # Siapkan data untuk dikirim kembali ke frontend
        # Ambil semua ReturnItem lagi untuk update tabel di frontend
        all_return_items = ReturnItem.objects.filter(session=return_session).select_related('product')
        
        # Filter item untuk pending dan completed (berdasarkan data aktual dari database + perubahan in-memory)
        pending_items_data = []
        completed_items_data = []

        # Rekonstruksi data untuk frontend, dengan memasukkan perubahan in-memory untuk item yang discan
        for item in all_return_items:
            # Jika item ini adalah yang baru saja discan, gunakan qty_scanned in-memory
            current_qty_scanned = return_item.qty_scanned if item.id == return_item.id else item.qty_scanned
            current_qc_status = return_item.qc_status if item.id == return_item.id else item.qc_status

            photo_url = item.product.photo.url if item.product.photo and hasattr(item.product.photo, 'url') else '/static/icons/alfaicon.png'

            item_data = {
                'id': item.id,
                'product_sku': item.product.sku,
                'product_barcode': item.product.barcode,
                'product_name': item.product.nama_produk,
                'product_variant': item.product.variant_produk,
                'product_brand': item.product.brand,
                'product_photo_url': photo_url,
                'qty_target': item.qty, # Diperbarui: qty_target -> qty (untuk kompatibilitas frontend)
                'qty_scanned': current_qty_scanned,
                'qc_status': current_qc_status,
            }
            if current_qc_status == 'pass':
                completed_items_data.append(item_data)
            else:
                pending_items_data.append(item_data)
        
        # Urutkan item untuk tampilan yang konsisten di frontend
        pending_items_data.sort(key=lambda x: x['product_name'] if x['product_name'] else '')
        completed_items_data.sort(key=lambda x: x['product_name'] if x['product_name'] else '')

        return JsonResponse({
            'success': True,
            'message': 'Scan berhasil!',
            'sku': product.sku,
            'qty_scanned': return_item.qty_scanned,
            'qty_target': return_item.qty, # Diperbarui: qty_target -> qty
            'qc_status': return_item.qc_status,
            'pending_items': pending_items_data,
            'completed_items': completed_items_data,
        })

    except Exception as e:
        logging.exception(f"Error during scanordercancel_scan_barcode for session {return_session_id}, order {order_id}")
        return JsonResponse({'success': False, 'message': f'Terjadi kesalahan: {str(e)}'}, status=500)

@login_required
@require_POST
@csrf_exempt
def scanordercancel_submit_return(request, return_session_id, order_id):
    try:
        data = json.loads(request.body)
        items_to_update = data.get('items', [])

        return_session = get_object_or_404(ReturnSession, id=return_session_id)
        # Ambil semua order item dengan order_id ini (termasuk status_bundle 'Y')
        order_items = list(Order.objects.filter(id_pesanan=order_id))

        # --- Validasi status_retur ---
        if any(item.status_retur == 'Y' for item in order_items):
            return JsonResponse({'success': False, 'message': f'Order ID {order_id} sudah selesai diretur sebelumnya.'}, status=400)

        with transaction.atomic():
            total_items_processed = 0

            # 1. Update jumlah_ambil di orders_order (hanya untuk item yang dikirim dari frontend)
            for item_data in items_to_update:
                item_id = item_data.get('id')
                jumlah_check = int(item_data.get('jumlah_check', 0))
                product_sku = item_data.get('product_sku')

                # Temukan order_item yang sesuai (pastikan status_bundle != 'Y')
                order_item = next((oi for oi in order_items if oi.product and oi.product.sku == product_sku and oi.status_bundle != 'Y'), None)
                if order_item:
                    # Kurangi jumlah_ambil
                    order_item.jumlah_ambil = max(order_item.jumlah_ambil - jumlah_check, 0)
                    order_item.save(update_fields=['jumlah_ambil'])

                    # 2. Update/akumulasi qty di ReturnItem
                    return_item, _ = ReturnItem.objects.get_or_create(
                        session=return_session,
                        product=order_item.product,
                        defaults={'qty': 0, 'qty_scanned': 0, 'qc_status': 'pending'}
                    )
                    return_item.qty += jumlah_check
                    return_item.save(update_fields=['qty'])

                    # 3. Update/insert ke ReturnSourceLog
                    # Gunakan user yang scan barcode (dari session) sebagai created_by
                    session_key = f"return_scan_user_{return_session_id}_{order_id}"
                    scan_user_id = request.session.get(session_key)
                    scan_user = request.user  # fallback ke user yang submit
                    if scan_user_id:
                        from django.contrib.auth.models import User
                        try:
                            scan_user = User.objects.get(id=scan_user_id)
                        except User.DoesNotExist:
                            scan_user = request.user  # fallback
                    
                    return_source_log, created = ReturnSourceLog.objects.get_or_create(
                        return_item=return_item,
                        session=return_session,
                        order_id=order_id,
                        created_by=scan_user,  # User yang benar-benar scan barcode
                        defaults={
                            'qty': jumlah_check,
                            'notes': f"Retur dari Order Cancel ID: {order_id} (Initial Scan Submit)",
                        }
                    )
                    if not created:
                        return_source_log.qty = jumlah_check
                        return_source_log.save(update_fields=['qty'])

                    total_items_processed += 1

            # 4. Update semua status_retur di orders_order (termasuk status_bundle 'Y')
            for oi in order_items:
                oi.status_retur = 'Y'
                oi.save(update_fields=['status_retur'])

            # 5. Update status_retur di OrderCancelLog supaya tidak muncul lagi di returnlist
            OrderCancelLog.objects.filter(order_id_scanned=order_id).update(status_retur='Y')

            # 6. Update status ReturnSession jika semua item sudah completed # Dihapus: Pengaturan status akan ditangani oleh logic putaway
            all_items_in_session = ReturnItem.objects.filter(session=return_session)
            #if all_items_in_session.exists() and all(ri.qty > 0 for ri in all_items_in_session): # Dihapus: Pengaturan status akan ditangani oleh logic putaway
            #    return_session.status = 'qc_done' # Dihapus: Pengaturan status akan ditangani oleh logic putaway
            #    return_session.save(update_fields=['status']) # Dihapus: Pengaturan status akan ditangani oleh logic putaway
            #elif return_session.status == 'open' and all_items_in_session.exists(): # Dihapus: Pengaturan status akan ditangani oleh logic putaway
            #    return_session.status = 'in_progress' # Dihapus: Pengaturan status akan ditangani oleh logic putaway
            #    return_session.save(update_fields=['status']) # Dihapus: Pengaturan status akan ditangani oleh logic putaway

            return JsonResponse({'success': True, 'message': f'Return berhasil disubmit. {total_items_processed} item diperbarui.', 'return_session_id': return_session.id})

    except ReturnSession.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Return Session tidak ditemukan.'}, status=404)
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Order ID tidak ditemukan.'}, status=404)
    except Exception as e:
        logging.exception(f"Error during scanordercancel_submit_return for session {return_session_id}, order {order_id}")
        return JsonResponse({'success': False, 'message': f'Terjadi kesalahan saat submit retur: {str(e)}'}, status=500)

@login_required
def returnsession_detail(request, session_id):
    session = get_object_or_404(ReturnSession, id=session_id)
    items = ReturnItem.objects.filter(session=session).select_related('product')
    
    # Ambil ReturnSourceLog yang terkait dengan sesi ini
    source_logs = ReturnSourceLog.objects.filter(session=session).order_by('-created_at')

    context = {
        'session': session,
        'items': items,
        'source_logs': source_logs, # Tambahkan source_logs ke konteks
    }
    return render(request, 'fullfilment/returnsession_detail.html', context)

@login_required
@require_GET
def get_return_session_order_ids(request, session_id):
    """
    API untuk mengambil daftar Order ID yang terkait dengan ReturnSession tertentu
    beserta detailnya untuk ditampilkan di modal dengan pagination.
    """
    try:
        return_session = get_object_or_404(ReturnSession, id=session_id)
        
        # Ambil ReturnSourceLog yang terkait dengan sesi ini
        source_logs_qs = ReturnSourceLog.objects.filter(session=return_session).order_by('-created_at')

        # Tambahkan filter pencarian
        search_query = request.GET.get('search', '')
        if search_query:
            source_logs_qs = source_logs_qs.filter(
                Q(order_id__icontains=search_query) |
                Q(batch__nama_batch__icontains=search_query)
            )

        # Pagination
        page_number = request.GET.get('page', 1)
        limit = request.GET.get('limit', 50) # Default 50 item per halaman
        
        paginator = Paginator(source_logs_qs, limit)
        page_obj = paginator.get_page(page_number)

        data = []
        for log in page_obj:
            # Jika order_id null tapi ada batch, tampilkan batch info
            if not log.order_id and log.batch:
                data.append({
                    'order_id': f"Batch: {log.batch.nama_batch}",
                    'source_type': 'batch_overstock'
                })
            # Jika ada order_id, tampilkan order_id
            elif log.order_id:
                data.append({
                    'order_id': log.order_id,
                    'source_type': 'order_cancel'
                })
            # Jika keduanya null, skip (tidak ditampilkan)

        return JsonResponse({
            'success': True,
            'order_ids': data,
            'total_pages': paginator.num_pages,
            'current_page': page_obj.number,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        })

    except ReturnSession.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Return Session tidak ditemukan.'}, status=404)
    except Exception as e:
        logging.exception(f"Error getting return session order IDs for session {session_id}")
        return JsonResponse({'success': False, 'message': f'Terjadi kesalahan: {str(e)}'}, status=500)

@login_required
@require_GET
def get_return_session_items_api(request, session_id):
    """
    API untuk mengambil daftar ReturnItem yang terkait dengan ReturnSession tertentu
    dengan filter pencarian dan pagination.
    """
    try:
        return_session = get_object_or_404(ReturnSession, id=session_id)
        
        items_qs = ReturnItem.objects.filter(session=return_session).select_related('product').order_by('-id')

        search_query = request.GET.get('search', '')
        if search_query:
            items_qs = items_qs.filter(
                Q(product__sku__icontains=search_query) |
                Q(product__nama_produk__icontains=search_query) |
                Q(product__barcode__icontains=search_query) |
                Q(product__variant_produk__icontains=search_query) |
                Q(product__brand__icontains=search_query)
            )

        page_number = request.GET.get('page', 1)
        limit = request.GET.get('limit', 50)

        paginator = Paginator(items_qs, limit)
        page_obj = paginator.get_page(page_number)

        data = []
        for item in page_obj:
            data.append({
                'id': item.id,
                'sku': item.product.sku if item.product else 'N/A',
                'barcode': item.product.barcode if item.product else 'N/A',
                'nama_produk': item.product.nama_produk if item.product else 'N/A',
                'variant_produk': item.product.variant_produk if item.product else 'N/A',
                'brand': item.product.brand if item.product else 'N/A',
                'qty_target': item.qty,
                'qty_scanned': item.qty_scanned,
                'qc_status': item.qc_status,
            })

        return JsonResponse({
            'success': True,
            'items': data,
            'total_pages': paginator.num_pages,
            'current_page': page_obj.number,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        })

    except ReturnSession.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Return Session tidak ditemukan.'}, status=404)
    except Exception as e:
        logging.exception(f"Error getting return session items for session {session_id}")
        return JsonResponse({'success': False, 'message': f'Terjadi kesalahan: {str(e)}'}, status=500)

@login_required
@require_GET
def get_return_session_history(request, session_id):
    """
    API untuk mengambil history ReturnSourceLog untuk ReturnSession tertentu,
    dengan pagination dan pencarian.
    """
    try:
        return_session = get_object_or_404(ReturnSession, id=session_id)
        logs_qs = ReturnSourceLog.objects.filter(session=return_session).order_by('-created_at')

        # Debug: Log jumlah data yang ditemukan
        print(f"DEBUG: Found {logs_qs.count()} ReturnSourceLog records for session {session_id}")

        search_query = request.GET.get('search', '').strip()
        if search_query:
            logs_qs = logs_qs.filter(
                Q(order_id__icontains=search_query) |
                Q(notes__icontains=search_query) |
                Q(created_by__username__icontains=search_query) |
                Q(batch__nama_batch__icontains=search_query) |
                Q(return_item__product__sku__icontains=search_query) |
                Q(return_item__product__barcode__icontains=search_query) |
                Q(return_item__product__nama_produk__icontains=search_query)
            )
            print(f"DEBUG: After search filter '{search_query}': {logs_qs.count()} records")

        page_number = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 50))
        paginator = Paginator(logs_qs, limit)
        page_obj = paginator.get_page(page_number)

        jakarta_tz = pytz.timezone("Asia/Jakarta")
        data = []
        for log in page_obj:
            # Debug: Log setiap record yang diproses
            print(f"DEBUG: Processing log - Order ID: {log.order_id}, Qty: {log.qty}, Created: {log.created_at}")
            
            # Konversi created_at ke Asia/Jakarta
            created_at_jakarta = log.created_at.astimezone(jakarta_tz)
            product = log.return_item.product if log.return_item and log.return_item.product else None
            data.append({
                'order_id': log.order_id or '',
                'batch': log.batch.nama_batch if log.batch else '',
                'qty': log.qty,
                'notes': log.notes or '',
                'created_by': log.created_by.username if log.created_by else '',
                'created_at': created_at_jakarta.strftime('%Y-%m-%d %H:%M'),  # Gunakan created_at_jakarta, bukan log.created_at
                'sku': product.sku if product else '',
                'barcode': product.barcode if product else '',
                'nama_produk': product.nama_produk if product else '',
                'variant_produk': product.variant_produk if product else '',
            })

        print(f"DEBUG: Returning {len(data)} records to frontend")
        return JsonResponse({
            'success': True,
            'logs': data,
            'total_pages': paginator.num_pages,
            'current_page': page_obj.number,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        })
    except ReturnSession.DoesNotExist:
        print(f"DEBUG: ReturnSession with id {session_id} not found")
        return JsonResponse({'success': False, 'message': 'Return Session tidak ditemukan.'}, status=404)
    except Exception as e:
        import logging
        print(f"DEBUG: Error in get_return_session_history: {str(e)}")
        logging.exception(f"Error getting return session history for session {session_id}")
        return JsonResponse({'success': False, 'message': f'Terjadi kesalahan: {str(e)}'}, status=500)

# Tambahkan fungsi helper untuk batch overstock (dari scanretur.py)
def get_batchlist_with_overstock():
    """
    Helper function untuk mendapatkan daftar batch yang memiliki overstock
    """
    batch_ids = (
        BatchItem.objects
        .filter(jumlah_ambil__gt=F('jumlah'))
        .values_list('batchlist_id', flat=True)
        .distinct()
    )
    return BatchList.objects.filter(id__in=batch_ids)

# Tambahkan fungsi scanretur_view (dari scanretur.py)
@login_required
@permission_required('fullfilment.view_scanretur', raise_exception=True)
def scanretur_view(request, returnlist_id):
    """
    View untuk scan return batch overstock
    """
    return_session = get_object_or_404(ReturnSession, id=returnlist_id)
    
    # Ambil daftar batch dengan overstock
    batchlist_overstock = get_batchlist_with_overstock()
    
    # Tambahkan jumlah_overstock untuk setiap batch
    for batch in batchlist_overstock:
        overstock_count = BatchItem.objects.filter(
            batchlist=batch,
            jumlah_ambil__gt=F('jumlah')
        ).count()
        batch.jumlah_overstock = overstock_count
    
    # Cek apakah ada batch_id yang dipilih
    batch_id = request.GET.get('batch_id')
    selected_batch = None
    show_tables = False
    
    if batch_id:
        try:
            selected_batch = BatchList.objects.get(id=batch_id)
            show_tables = True
        except BatchList.DoesNotExist:
            pass
    
    context = {
        'return_list': return_session,  # Gunakan nama yang konsisten dengan template
        'batchlist_overstock': batchlist_overstock,
        'selected_batch': selected_batch,
        'show_tables': show_tables,
    }
    
    return render(request, 'fullfilment/scanretur.html', context)

# Tambahkan API untuk get overstock batch data (dari scanretur.py)
@login_required
@require_GET
def get_overstock_batch_data_api(request, return_session_id):
    """
    API untuk mengambil data item overstock dari batch yang dipilih
    """
    try:
        batch_id = request.GET.get('batch_id')
        if not batch_id:
            return JsonResponse({'success': False, 'error': 'Batch ID diperlukan'})
        
        # Ambil batch dan return session
        batch = get_object_or_404(BatchList, id=batch_id)
        return_session = get_object_or_404(ReturnSession, id=return_session_id)
        
        # Ambil item overstock dari BatchItem
        # Hitung jumlah_over = jumlah_ambil - jumlah
        batch_items = BatchItem.objects.filter(
            batchlist=batch,
            jumlah_ambil__gt=0  # Hanya item yang sudah diambil
        ).select_related('product')
        
        pending_items = []
        for item in batch_items:
            jumlah_over = item.jumlah_ambil - item.jumlah
            if jumlah_over > 0:  # Hanya item yang memiliki overstock
                pending_items.append({
                    'id': item.id,
                    'sku': item.product.sku,
                    'barcode': item.product.barcode,
                    'nama_produk': item.product.nama_produk,
                    'variant_produk': item.product.variant_produk,
                    'brand': item.product.brand,
                    'photo_url': item.product.photo.url if item.product.photo else None,
                    'jumlah_over': jumlah_over,
                })
        
        return JsonResponse({
            'success': True,
            'pending_items': pending_items,
            'batch_name': batch.nama_batch
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

# Tambahkan API untuk submit batch overstock return (dari scanretur.py)
@login_required
@require_POST
@csrf_exempt
def submit_batch_overstock_return(request, return_session_id):
    """
    API untuk submit return batch overstock
    """
    try:
        data = json.loads(request.body)
        batchlist_id = data.get('batchlist_id')
        items = data.get('items', [])
        
        if not batchlist_id or not items:
            return JsonResponse({
                'success': False,
                'error': 'Data batchlist_id dan items diperlukan'
            })
        
        # Ambil batch dan return session
        batch = get_object_or_404(BatchList, id=batchlist_id)
        return_session = get_object_or_404(ReturnSession, id=return_session_id)
        
        for item_data in items:
            item_id = item_data.get('item_id')
            jumlah_check = item_data.get('jumlah_check', 0)
            
            if item_id and jumlah_check > 0:
                # Ambil BatchItem
                batch_item = get_object_or_404(BatchItem, id=item_id, batchlist=batch)
                product = batch_item.product

                # 1. Kurangi jumlah_ambil
                batch_item.jumlah_ambil = max(0, batch_item.jumlah_ambil - jumlah_check)
                batch_item.save()

                # 2. Update Stock - Return menambah stok siap dijual dan putaway queue
                stock, created = Stock.objects.get_or_create(
                    product=product,
                    defaults={'quantity': 0, 'quantity_locked': 0, 'quantity_putaway': 0}
                )
                
                qty_awal = stock.quantity
                stock.quantity += jumlah_check  # Stok siap dijual bertambah
                stock.quantity_putaway += jumlah_check  # Masuk ke putaway queue
                stock.save(update_fields=['quantity', 'quantity_putaway'])
                
                # Buat StockCardEntry untuk audit trail
                StockCardEntry.objects.create(
                    product=product,
                    tipe_pergerakan='return_stock',
                    qty=jumlah_check,
                    qty_awal=qty_awal,
                    qty_akhir=stock.quantity,
                    notes=f'Return dari Batch Overstock {batch.nama_batch}',
                    user=request.user,
                    waktu=timezone.now()
                )

                # 3. Update atau create ReturnItem
                return_item, _ = ReturnItem.objects.get_or_create(
                    session=return_session,
                    product=product,
                    defaults={'qty': 0}
                )
                return_item.qty += jumlah_check
                return_item.save()

                # 4. Update ReturnSourceLog (catat sumber return)
                ReturnSourceLog.objects.create(
                    session=return_session,           # ForeignKey ke ReturnSession
                    return_item=return_item,          # ForeignKey ke ReturnItem
                    batch=batch,                      # ForeignKey ke BatchList (jika ada)
                    qty=jumlah_check,                 # Jumlah yang di-return
                    notes='Return dari batch overstock',  # Catatan/keterangan
                    created_by=request.user           # (opsional) user yang melakukan
                )
        
        return JsonResponse({
            'success': True,
            'message': f'Berhasil submit return untuk {len(items)} item'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@require_GET
def debug_return_source_logs(request):
    """
    Debug endpoint untuk mengecek data ReturnSourceLog di database
    """
    try:
        total_logs = ReturnSourceLog.objects.count()
        total_sessions = ReturnSession.objects.count()
        
        # Ambil beberapa sample data
        sample_logs = ReturnSourceLog.objects.select_related('session', 'return_item__product', 'created_by')[:5]
        sample_data = []
        
        for log in sample_logs:
            sample_data.append({
                'id': log.id,
                'session_id': log.session.id if log.session else None,
                'session_kode': log.session.kode if log.session else None,
                'order_id': log.order_id,
                'qty': log.qty,
                'created_at': log.created_at.strftime('%Y-%m-%d %H:%M'),
                'created_by': log.created_by.username if log.created_by else None,
                'product_sku': log.return_item.product.sku if log.return_item and log.return_item.product else None,
            })
        
        return JsonResponse({
            'success': True,
            'total_logs': total_logs,
            'total_sessions': total_sessions,
            'sample_data': sample_data
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def putaway_return_session(request, session_id):
    """
    View untuk menampilkan detail item ReturnSession sebelum putaway
    """
    return_session = get_object_or_404(ReturnSession, id=session_id)
    
    # Ambil semua ReturnItem dalam session ini
    return_items = ReturnItem.objects.filter(session=return_session).select_related('product')
    
    context = {
        'return_session': return_session,
        'return_items': return_items,
    }
    return render(request, 'fullfilment/putaway_return_session.html', context)

@login_required
@require_POST
@csrf_exempt
def process_putaway_return(request, session_id):
    """
    API untuk mengakui stock dari SEMUA ReturnItem dalam session (seperti proses inbound)
    TIDAK langsung putaway ke rak, hanya update Stock.quantity + Stock.quantity_putaway
    """
    try:
        return_session = get_object_or_404(ReturnSession, id=session_id)
        
        # Ambil semua ReturnItem dalam session yang belum selesai putaway
        return_items = ReturnItem.objects.filter(
            session=return_session,
            putaway_status__in=['pending', 'partial']
        ).select_related('product')
        
        if not return_items.exists():
            return JsonResponse({
                'success': False,
                'message': 'Tidak ada item yang perlu diputaway.'
            }, status=400)
        
        total_items_processed = 0
        
        with transaction.atomic():
            for return_item in return_items:
                if return_item.qty <= 0:
                    continue
                    
                qty_remaining = return_item.qty - return_item.qty_putaway
                if qty_remaining <= 0:
                    continue
                
                # 1. Update Stock (seperti proses inbound)
                stock, created = Stock.objects.get_or_create(
                    product=return_item.product,
                    defaults={
                        'quantity': 0,
                        'quantity_locked': 0,
                        'quantity_putaway': 0
                    }
                )
                
                qty_awal = stock.quantity
                stock.quantity += qty_remaining  # Tambah ke stock siap jual
                stock.quantity_putaway += qty_remaining  # Tambah ke putaway queue
                stock.save(update_fields=['quantity', 'quantity_putaway'])
                
                # 2. Buat StockCardEntry untuk audit trail
                StockCardEntry.objects.create(
                    product=return_item.product,
                    tipe_pergerakan='return_stock',
                    qty=qty_remaining,
                    qty_awal=qty_awal,
                    qty_akhir=stock.quantity,
                    notes=f'Return from Session: {return_session.kode}',
                    user=request.user
                )
                
                # 3. Update ReturnItem.qty_putaway (mark as processed)
                return_item.qty_putaway = return_item.qty  # Mark all as processed
                return_item.putaway_status = 'completed'
                return_item.save(update_fields=['qty_putaway', 'putaway_status'])
                
                total_items_processed += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Stock berhasil diakui untuk {total_items_processed} item. Semua item masuk ke inventory dan putaway queue.',
            'items_processed': total_items_processed
        })
            
    except ReturnSession.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Return Session tidak ditemukan.'}, status=404)
    except Exception as e:
        logging.exception(f"Error during putaway return session {session_id}")
        return JsonResponse({'success': False, 'message': f'Terjadi kesalahan: {str(e)}'}, status=500)

@login_required
@require_POST
@csrf_exempt
def process_putaway_return_item(request, item_id):
    """
    API untuk mengakui stock dari ReturnItem (seperti proses inbound)
    TIDAK langsung putaway ke rak, hanya update Stock.quantity + Stock.quantity_putaway
    """
    try:
        return_item = get_object_or_404(ReturnItem, id=item_id)
        
        # Hitung qty yang belum diputaway
        qty_remaining = return_item.qty - return_item.qty_putaway
        if qty_remaining <= 0:
            return JsonResponse({'success': False, 'message': 'Item sudah selesai diputaway.'}, status=400)
        
        with transaction.atomic():
            # 1. Update Stock (seperti proses inbound)
            stock, created = Stock.objects.get_or_create(
                product=return_item.product,
                defaults={
                    'quantity': 0,
                    'quantity_locked': 0,
                    'quantity_putaway': 0
                }
            )
            
            qty_awal = stock.quantity
            stock.quantity += qty_remaining  # Tambah ke stock siap jual
            stock.quantity_putaway += qty_remaining  # Tambah ke putaway queue
            stock.save(update_fields=['quantity', 'quantity_putaway'])
            
            # 2. Buat StockCardEntry untuk audit trail
            StockCardEntry.objects.create(
                product=return_item.product,
                tipe_pergerakan='return_stock',
                qty=qty_remaining,
                qty_awal=qty_awal,
                qty_akhir=stock.quantity,
                notes=f'Return from ReturnItem ID: {return_item.id}',
                user=request.user
            )
            
            # 3. Update ReturnItem.qty_putaway (mark as processed)
            return_item.qty_putaway = return_item.qty  # Mark all as processed
            return_item.putaway_status = 'completed'
            return_item.save(update_fields=['qty_putaway', 'putaway_status'])
            
        return JsonResponse({
            'success': True, 
            'message': f'Stock berhasil diakui untuk {return_item.product.nama_produk}. {qty_remaining} item masuk ke inventory dan putaway queue.',
            'product_name': return_item.product.nama_produk,
            'qty_processed': qty_remaining
        })
            
    except ReturnItem.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Return Item tidak ditemukan.'}, status=404)
    except Exception as e:
        logging.exception(f"Error during return item stock acknowledgment {item_id}")
        return JsonResponse({'success': False, 'message': f'Terjadi kesalahan: {str(e)}'}, status=500)

@login_required
@require_POST
@csrf_exempt
def close_return_session(request, session_id):
    """
    API untuk menutup ReturnSession
    """
    try:
        return_session = get_object_or_404(ReturnSession, id=session_id)
        
        # Validasi: hanya session yang status 'open' yang bisa ditutup
        if return_session.status != 'open':
            return JsonResponse({
                'success': False, 
                'message': f'Session {return_session.kode} sudah ditutup atau tidak dapat ditutup.'
            }, status=400)
        
        # Update status menjadi 'closed'
        return_session.status = 'closed'
        return_session.save(update_fields=['status'])
        
        return JsonResponse({
            'success': True,
            'message': f'Session {return_session.kode} berhasil ditutup.'
        })
        
    except ReturnSession.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Return Session tidak ditemukan.'}, status=404)
    except Exception as e:
        logging.exception(f"Error during close return session {session_id}")
        return JsonResponse({'success': False, 'message': f'Terjadi kesalahan: {str(e)}'}, status=500)


@login_required
@require_POST
@csrf_exempt
def update_return_session(request, session_id):
    """
    API untuk mengupdate ReturnSession
    """
    try:
        return_session = get_object_or_404(ReturnSession, id=session_id)
        
        # Parse JSON data
        data = json.loads(request.body)
        new_status = data.get('status')
        notes = data.get('notes', '')
        
        # Validasi status
        if new_status not in ['open', 'closed']:
            return JsonResponse({
                'success': False, 
                'message': 'Status tidak valid. Gunakan "open" atau "closed".'
            }, status=400)
        
        # Update session
        return_session.status = new_status
        if notes:
            return_session.catatan = notes
        return_session.save(update_fields=['status', 'catatan'])
        
        return JsonResponse({
            'success': True,
            'message': f'Session {return_session.kode} berhasil diperbarui.'
        })
        
    except ReturnSession.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Return Session tidak ditemukan.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Format data tidak valid.'}, status=400)
    except Exception as e:
        logging.exception(f"Error during update return session {session_id}")
        return JsonResponse({'success': False, 'message': f'Terjadi kesalahan: {str(e)}'}, status=500)