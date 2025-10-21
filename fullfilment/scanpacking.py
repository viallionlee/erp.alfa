import json
import random
from importlib import import_module
from django.shortcuts import render
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Q, F, Count, Window, Min
from django.db.models.functions import RowNumber
from django.utils import timezone
from django.contrib.auth.decorators import login_required, permission_required
from orders.models import Order, OrderPackingHistory, OrderHandoverHistory
import datetime
from django.core.exceptions import PermissionDenied

def get_motivational_message_list(rank, total_packers):
    """
    Secara dinamis mengimpor daftar pesan motivasi berdasarkan peringkat.
    - Menangani kasus khusus untuk peringkat terakhir dan kedua terakhir.
    - Rank 1-5: Menggunakan file spesifik.
    - Rank 6 hingga sebelum 2 terakhir: Menggunakan file umum (rank_umum.py).
    - Rank > 20 (jika tidak ada kasus lain): Menggunakan file default.
    """
    module_name = ""
    
    # Prioritas utama: Cek peringkat khusus dari bawah.
    # Hanya aktif jika ada cukup peserta agar tidak tumpang tindih dengan rank 1-5.
    if total_packers > 5 and rank == total_packers:
        module_name = 'rank_terakhir'
    elif total_packers > 5 and rank == total_packers - 1:
        module_name = 'rank_2_terakhir'
    # Logika peringkat reguler dari atas
    elif 1 <= rank <= 5:
        module_name = f'rank_{rank}'
    # Logika untuk peringkat "umum" di tengah
    elif rank > 5:
        module_name = 'rank_umum'
    # Fallback untuk kasus yang tidak terduga
    else:
        module_name = 'default'
    
    try:
        module_path = f'fullfilment.motivasi.{module_name}'
        motivation_module = import_module(module_path)
        return motivation_module.MESSAGES
    except (ImportError, AttributeError):
        # Fallback jika file spesifik (misal, rank_5 atau rank_umum) belum dibuat.
        from fullfilment.motivasi import default
        return default.MESSAGES

@login_required
def scanpacking(request):
    """
    Menampilkan halaman Ready to Packed dan memproses update status via AJAX.
    """
    # Deteksi User Agent untuk menentukan permission yang relevan
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = any(x in user_agent for x in ['android', 'iphone', 'ipad', 'ipod', 'blackberry', 'iemobile', 'opera mini'])

    # Cek permission berdasarkan platform
    if is_mobile:
        if not request.user.has_perm('fullfilment.view_mobile_packing_module'):
            raise PermissionDenied
    else: # Desktop
        if not request.user.has_perm('fullfilment.view_desktop_packing_module'):
            raise PermissionDenied
            
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            scan_input = data.get('order_id', '').strip()

            if not scan_input:
                return JsonResponse({'success': False, 'message': 'Input tidak boleh kosong.'})
            
            with transaction.atomic():
                orders = Order.objects.filter(
                    Q(id_pesanan__iexact=scan_input) | Q(awb_no_tracking__iexact=scan_input)
                )

                if not orders.exists():
                    return JsonResponse({'success': False, 'message': f"Order dengan ID atau Resi '{scan_input}' tidak ditemukan."})

                # NEW: Validasi status pembayaran atau status fulfillment adalah 'batal'/'cancel'
                first_order = orders.first()
                if 'batal' in (first_order.status or '').lower() or \
                   'cancel' in (first_order.status or '').lower() or \
                   'batal' in (first_order.status_order or '').lower() or \
                   'cancel' in (first_order.status_order or '').lower():
                    from .models import OrderCancelLog # Import here to avoid circular dependency if placed at top
                    # RE-ADDED: Cek apakah OrderCancelLog sudah ada untuk Order ID ini
                    if not OrderCancelLog.objects.filter(order_id_scanned=scan_input).exists():
                        OrderCancelLog.objects.create(
                            order_id_scanned=scan_input,
                            user=request.user if request.user.is_authenticated else None,
                            status_pembayaran_at_scan=first_order.status,
                            status_fulfillment_at_scan=first_order.status_order
                        )
                    return JsonResponse({
                        'success': False,
                        'message': f"Halo {request.user.username} , Orderan ini {scan_input} sudah dibatalkan customer , tolong di retur ke tim retur , Terima Kasih , Semangat terus!"
                    })

                current_status = first_order.status_order.lower()

                if current_status == 'picked':
                    updated_count = orders.update(status_order='packed')
                    history_entries = [
                        OrderPackingHistory(order=order, user=request.user) for order in orders
                    ]
                    OrderPackingHistory.objects.bulk_create(history_entries)
                    
                    # --- Start of Scan Counter Logic ---
                    scan_count = request.session.get('scan_count_for_message', 0) + 1
                    request.session['scan_count_for_message'] = scan_count
                    
                    if scan_count >= 10:
                        request.session.pop('motivational_message', None)
                        request.session.pop('last_rank', None)
                        request.session['scan_count_for_message'] = 0
                    # --- End of Scan Counter Logic ---

                    return JsonResponse({
                        'success': True,
                        'message': f"Berhasil! {updated_count} item untuk pesanan '{scan_input}' telah diubah menjadi 'Packed'."
                    })
                elif current_status == 'packed':
                    last_packing = OrderPackingHistory.objects.filter(order=orders.first()).order_by('-waktu_pack').first()
                    message = f"Pesanan '{scan_input}' sudah di-PACKED oleh {last_packing.user.username} pada {last_packing.waktu_pack.strftime('%d-%m-%Y %H:%M')}." if last_packing else f"Pesanan '{scan_input}' sudah di-PACKED sebelumnya."
                elif current_status == 'shipped':
                    last_ship = OrderHandoverHistory.objects.filter(order=orders.first()).order_by('-waktu_ho').first()
                    message = f"Pesanan '{scan_input}' sudah di-SHIPPED oleh {last_ship.user.username} pada {last_ship.waktu_ho.strftime('%d-%m-%Y %H:%M')}. Tolong kembalikan kertas ini ke admin." if last_ship else f"Pesanan '{scan_input}' sudah di-SHIPPED. Tolong kembalikan kertas ini ke admin."
                elif current_status == 'printed':
                    message = f"Pesanan '{scan_input}' belum di-pick. Silakan lakukan proses picking terlebih dahulu."
                else:
                    message = f"Status pesanan '{scan_input}' tidak valid untuk proses packing."
                
                return JsonResponse({'success': False, 'message': message})

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Format request tidak valid.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Terjadi error internal: {str(e)}'}, status=500)
    
    today = timezone.now().date()
    current_user = request.user

    user_scores = OrderPackingHistory.objects.filter(
        waktu_pack__date=today
    ).values('user_id').annotate(
        total_packs=Count('order__id_pesanan', distinct=True)
    ).order_by('-total_packs')

    total_packers_today = len(user_scores)
    user_packs_today = 0
    user_rank_today = 0
    
    for i, score in enumerate(user_scores):
        if score['user_id'] == current_user.id:
            user_rank_today = i + 1
            user_packs_today = score['total_packs']
            break
            
    if user_rank_today == 0:
        user_rank_today = total_packers_today + 1

    # --- Motivational Message Logic with 10-Scan Cycle ---
    stored_message = request.session.get('motivational_message')
    stored_rank = request.session.get('last_rank')
    
    new_message_needed = (stored_message is None) or (user_rank_today != stored_rank)

    if new_message_needed:
        message_list = get_motivational_message_list(user_rank_today, total_packers_today)
        specific_message = random.choice(message_list)
        motivational_message = f"Hi, <strong>{current_user.username}</strong>! {specific_message}"
        
        request.session['motivational_message'] = motivational_message
        request.session['last_rank'] = user_rank_today
    else:
        motivational_message = stored_message

    now = timezone.now()
    start_of_work = now.replace(hour=9, minute=0, second=0, microsecond=0)
    packs_per_hour = 0.0 

    if now > start_of_work:
        duration_seconds = (now - start_of_work).total_seconds()
        if duration_seconds > 60:
            duration_hours = duration_seconds / 3600
            packs_per_hour = user_packs_today / duration_hours
        else:
            packs_per_hour = float(user_packs_today)
            
    last_10_packing = OrderPackingHistory.objects.annotate(
        row_num=Window(
            expression=RowNumber(),
            partition_by=[F('order__id_pesanan')],
            order_by=F('waktu_pack').desc()
        )
    ).filter(row_num=1).select_related('user', 'order').order_by('-waktu_pack')[:10]
    
    template_name = 'fullfilment/mobile_scanpacking.html' if is_mobile else 'fullfilment/scanpacking.html'

    total_batched = Order.objects.filter(nama_batch__isnull=False).values('id_pesanan').distinct().count()
    total_packed = Order.objects.filter(nama_batch__isnull=False, status_order='packed').values('id_pesanan').distinct().count()

    context = {
        'last_10_packing': last_10_packing,
        'user_packs_today': user_packs_today,
        'user_rank_today': user_rank_today,
        'total_packers_today': total_packers_today,
        'packs_per_hour': packs_per_hour,
        'motivational_message': motivational_message,
        'total_batched': total_batched,
        'total_packed': total_packed,
    }
    return render(request, template_name, context)

@login_required
@permission_required('fullfilment.view_scanpacking', raise_exception=True)
def scanpacking_list_view(request):
    return render(request, 'fullfilment/scanpacking_list.html')

@login_required
@permission_required('fullfilment.view_scanpacking', raise_exception=True)
def scanpacking_list_api(request):
    draw = int(request.GET.get('draw', 0))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 25))
    search_value = request.GET.get('search[value]', '')

    # Queryset dasar: hanya order yang sudah 'picked'
    base_queryset = Order.objects.filter(status_order='picked')

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
        if isinstance(tanggal, datetime.datetime):
            item['tanggal_pembuatan'] = tanggal.strftime('%Y-%m-%d %H:%M')

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': filtered_records,
        'data': data,
    }) 

@login_required
def order_packing_list_view(request):
    """Menampilkan halaman daftar order packing dengan pagination server-side."""
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = any(x in user_agent for x in ['android', 'iphone', 'ipad', 'ipod', 'blackberry', 'iemobile', 'opera mini'])

    if is_mobile:
        if not request.user.has_perm('fullfilment.view_mobile_packing_module'):
            raise PermissionDenied
    else:
        if not request.user.has_perm('fullfilment.view_desktop_packing_module'):
            raise PermissionDenied
            
    template_name = 'fullfilment/mobile_order_packing_list.html' if is_mobile else 'fullfilment/order_packing_list.html'
    
    return render(request, template_name)

@login_required
def order_packing_list_api(request):
    """API untuk DataTables daftar order packing dengan pagination per 25."""
    if not (
        request.user.has_perm('fullfilment.view_desktop_packing_module') or 
        request.user.has_perm('fullfilment.view_mobile_packing_module')
    ):
        raise PermissionDenied

    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 25))  # Pagination per 25
    search_value = request.GET.get('search[value]', '').strip()

    # Mendefinisikan urutan kolom
    order_column_index = int(request.GET.get('order[0][column]', 1))
    order_dir = request.GET.get('order[0][dir]', 'desc')
    
    column_mapping = ['id', 'waktu_pack', 'order__id_pesanan', 'user__username', 'order__nama_toko']
    order_column_name = column_mapping[order_column_index]
    
    sort_prefix = '-' if order_dir == 'desc' else ''
    order_by = f'{sort_prefix}{order_column_name}'

    # Queryset dasar
    queryset = OrderPackingHistory.objects.select_related('order', 'user').all()

    # Total record sebelum filter
    total_records = queryset.count()

    # Terapkan filter pencarian
    if search_value:
        queryset = queryset.filter(
            Q(order__id_pesanan__icontains=search_value) |
            Q(user__username__icontains=search_value) |
            Q(order__nama_toko__icontains=search_value)
        )

    # Total record setelah filter
    filtered_records = queryset.count()
    
    # Terapkan pengurutan dan paginasi
    queryset = queryset.order_by(order_by)[start:start + length]

    # Format data untuk JSON response
    import pytz
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    data = []
    for history in queryset:
        waktu_pack_localized = history.waktu_pack.astimezone(jakarta_tz).strftime('%d-%m-%Y %H:%M:%S') if history.waktu_pack else 'N/A'
        data.append({
            'id': history.id,
            'waktu_pack': waktu_pack_localized,
            'order_id_pesanan': history.order.id_pesanan if history.order else 'N/A',
            'nama_toko': history.order.nama_toko if history.order else 'N/A',
            'user': history.user.username if history.user else 'N/A',
            'status_order': history.order.status_order if history.order else 'N/A',
            'nama_batch': history.order.nama_batch if history.order else 'N/A',
            'kurir': history.order.kurir if history.order else 'N/A'
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': filtered_records,
        'data': data,
    }) 