from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Q, Count, Sum, Case, When, Value, IntegerField
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
import json
import uuid
from datetime import datetime, timedelta
from .models import Rak, RakOpnameSession, RakOpnameItem, RakOpnameLog, InventoryRakStock, Stock, OpnameQueue, InventoryRakStockLog, FullOpnameSession
from products.models import Product

User = get_user_model()


# ===== FULL OPNAME SESSION VIEWS =====

@login_required
@permission_required('inventory.view_opname', raise_exception=True)
def full_opname_list(request):
    """Daftar semua full opname session"""
    import re
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = re.search(r'mobile|android|iphone', user_agent)
    
    template_name = 'inventory/full_opname_list_mobile.html' if is_mobile else 'inventory/full_opname_list.html'
    
    full_sessions = FullOpnameSession.objects.all().order_by('-tanggal_mulai')

    with transaction.atomic():
        for full_session in full_sessions:
            rak_sessions = full_session.rak_opname_sessions.all()
            
            # Determine the effective status of the FullOpnameSession
            current_full_session_status = full_session.status
            new_full_session_status = current_full_session_status # Default to current

            if not rak_sessions.exists():
                # If no rak sessions, it's a draft
                if current_full_session_status != 'draft':
                    new_full_session_status = 'draft'
            else:
                # Check status counts of associated rak sessions
                draft_count = rak_sessions.filter(status='draft').count()
                in_progress_count = rak_sessions.filter(status='in_progress').count()
                completed_count = rak_sessions.filter(status='completed').count()
                cancelled_count = rak_sessions.filter(status='cancelled').count()
                
                total_rak_sessions_active = rak_sessions.exclude(status='cancelled').count()

                if total_rak_sessions_active == 0 and cancelled_count > 0:
                    pass # Keep current status or re-evaluate based on specific cancellation logic if needed later
                elif in_progress_count > 0 or (completed_count > 0 and completed_count < total_rak_sessions_active):
                    # If any are in progress OR some are completed but not all active ones
                    new_full_session_status = 'in_progress'
                elif completed_count == total_rak_sessions_active and total_rak_sessions_active > 0:
                    # If all active rak sessions are completed
                    new_full_session_status = 'completed'
                elif draft_count == total_rak_sessions_active:
                    # If all active rak sessions are still draft
                    new_full_session_status = 'draft'
                
            # Only update and save if the status has actually changed
            if new_full_session_status != current_full_session_status:
                full_session.status = new_full_session_status
                full_session.save()
            
            # Tambahkan atribut untuk kontrol tombol hapus
            # Bisa dihapus jika:
            # 1. FullOpnameSession statusnya 'draft'
            # 2. TIDAK ADA RakOpnameSession yang berstatus selain 'draft' (yaitu, semua 'draft' atau tidak ada sama sekali)
            full_session.can_delete_by_child_status = not rak_sessions.exclude(status='draft').exists()

            # Calculate statistics for each full session
            total_rak = rak_sessions.count()
            rak_selesai = rak_sessions.filter(status='completed').count()
            
            # Calculate total selisih from all completed rak sessions
            total_selisih = 0
            for rak_session in rak_sessions.filter(status='completed'):
                session_selisih = rak_session.items.aggregate(
                    total_selisih=Sum('qty_selisih')
                )['total_selisih'] or 0
                total_selisih += session_selisih
            
            # Calculate verification progress
            total_items = 0
            verified_items = 0
            for rak_session in rak_sessions:
                session_items = rak_session.items.count()
                session_verified = rak_session.items.filter(is_verified=True).count()
                total_items += session_items
                verified_items += session_verified
            
            progress_verifikasi = 0
            if total_items > 0:
                progress_verifikasi = (verified_items / total_items) * 100
            
            # Store statistics in a dictionary for each session
            full_session.stats = {
                'total_rak': total_rak,
                'rak_selesai': rak_selesai,
                'total_selisih': total_selisih,
                'progress_verifikasi': progress_verifikasi,
                'total_items': total_items,
                'verified_items': verified_items,
            }

    # Check if this is an AJAX request for DataTable
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        sessions_data = []
        for session in full_sessions:
            # Get rak list for display
            rak_list = []
            for rak_session in session.rak_opname_sessions.all():
                rak_list.append(rak_session.rak.kode_rak)
            
            sessions_data.append({
                'id': session.id,
                'session_code': session.session_code,
                'nama_opname': session.nama_opname,
                'rak_list': ', '.join(rak_list) if rak_list else '-',
                'status': session.get_status_display(),
                'total_items': session.stats['total_items'],
                'total_selisih': session.stats['total_selisih'],
                'created_by': session.created_by.username if session.created_by else '-',
                'created_at': session.tanggal_mulai.strftime('%d/%m/%Y %H:%M') if session.tanggal_mulai else '-',
            })
        
        return JsonResponse({
            'full_sessions': sessions_data
        })

    # Calculate summary stats for mobile view
    in_progress_count = full_sessions.filter(status='in_progress').count()
    completed_count = full_sessions.filter(status='completed').count()
    
    # Regular HTML response
    context = {
        'full_sessions': full_sessions,
        'in_progress_count': in_progress_count,
        'completed_count': completed_count,
    }
    return render(request, template_name, context)


@login_required
@permission_required('inventory.add_opname', raise_exception=True)
def full_opname_create(request):
    """Buat full opname session baru"""
    import re
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = re.search(r'mobile|android|iphone', user_agent)
    
    template_name = 'inventory/full_opname_create_mobile.html' if is_mobile else 'inventory/full_opname_create.html'
    if request.method == 'POST':
        try:
            nama_opname = request.POST.get('nama_opname')
            catatan = request.POST.get('catatan', '')
            supervisor_id = request.POST.get('supervisor')
            target_rak_ids = request.POST.getlist('target_raks')
            
            # Debug logging
            print(f"DEBUG: target_rak_ids received: {target_rak_ids}")
            print(f"DEBUG: target_rak_ids count: {len(target_rak_ids)}")
            
            if not nama_opname:
                messages.error(request, 'Nama opname wajib diisi')
                return redirect('inventory:full_opname_list')
            
            # Buat full opname session
            full_session = FullOpnameSession.objects.create(
                nama_opname=nama_opname,
                catatan=catatan,
                created_by=request.user,
                supervisor_id=supervisor_id if supervisor_id else None
            )
            
            # Tambahkan target rak jika ada
            if target_rak_ids:
                target_raks = Rak.objects.filter(id__in=target_rak_ids)
                print(f"DEBUG: target_raks found: {target_raks.count()}")
                print(f"DEBUG: target_raks IDs: {list(target_raks.values_list('id', flat=True))}")
                full_session.target_raks.set(target_raks)
                
                # Buat sesi opname rak dengan status draft untuk setiap rak target
                created_sessions_count = 0
                for rak in target_raks:
                    # Cek apakah sudah ada sesi draft untuk rak ini
                    existing_draft = RakOpnameSession.objects.filter(rak=rak, status='draft').first()
                    if not existing_draft:
                        # Gunakan timestamp dengan microsecond untuk memastikan unik
                        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]  # Hapus 3 digit terakhir microsecond
                        session_code = f"OPNAME-{rak.kode_rak}-{timestamp}"
                        
                        # Buat sesi opname rak
                        rak_session = RakOpnameSession.objects.create(
                            rak=rak,
                            session_code=session_code,
                            catatan=f"Auto-generated dari Full Opname Session: {nama_opname}",
                            created_by=request.user,
                            full_opname_session=full_session
                        )
                        
                        created_sessions_count += 1
                        
                        # Log pembuatan sesi
                        RakOpnameLog.objects.create(
                            session=rak_session,
                            action='create',
                            user=request.user,
                            details=f'Sesi opname otomatis dibuat untuk rak {rak.lokasi} dari Full Opname Session'
                        )
                        
                        # Ambil stok produk di rak ini
                        rak_stocks = InventoryRakStock.objects.filter(rak=rak, quantity__gt=0)
                        
                        # Buat item opname untuk setiap produk
                        for stock in rak_stocks:
                            RakOpnameItem.objects.create(
                                session=rak_session,
                                product=stock.product,
                                qty_sistem=stock.quantity,
                                qty_fisik=0  # Akan diisi saat opname
                            )
                    else:
                        # Jika sudah ada sesi draft, hubungkan ke full opname session
                        existing_draft.full_opname_session = full_session
                        existing_draft.save()
                        created_sessions_count += 1
            
            messages.success(request, f'Full opname session "{nama_opname}" berhasil dibuat dengan {created_sessions_count} sesi opname rak')
            return redirect('inventory:full_opname_detail', session_id=full_session.id)
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
            return redirect('inventory:full_opname_list')
    
    # GET request - tampilkan form
    supervisors = User.objects.filter(is_staff=True).order_by('username')
    all_raks = Rak.objects.all().order_by('lokasi', 'kode_rak')
    
    context = {
        'supervisors': supervisors,
        'all_raks': all_raks,
    }
    return render(request, template_name, context)


@login_required
@permission_required('inventory.view_opname', raise_exception=True)
def full_opname_detail(request, session_id):
    """Detail full opname session"""
    import re
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = re.search(r'mobile|android|iphone', user_agent)
    
    template_name = 'inventory/full_opname_detail_mobile.html' if is_mobile else 'inventory/full_opname_detail.html'
    
    full_session = get_object_or_404(FullOpnameSession, id=session_id)
    
    # Custom ordering for rak_sessions
    rak_sessions = full_session.rak_opname_sessions.all().annotate(
        status_order=Case(
            When(status='in_progress', then=Value(1)),
            When(status='draft', then=Value(2)),
            When(status='completed', then=Value(3)), # Menggunakan 'completed' sesuai definisi model
            When(status='cancelled', then=Value(4)), # Menggunakan 'cancelled' sesuai definisi model
            default=Value(99), # Untuk status lain yang mungkin ada
            output_field=IntegerField()
        )
    ).order_by('status_order', 'rak__lokasi', 'rak__kode_rak') # Urutkan berdasarkan urutan kustom, lalu lokasi/kode rak


    # Check if any rak session has been processed (status is not 'draft')
    # can_delete_full_opname = not full_session.rak_opname_sessions.exclude(status='draft').exists()
    can_delete_full_opname = not full_session.rak_opname_sessions.filter(Q(status='in_progress') | Q(status='completed')).exists() # Menggunakan 'completed'

    # Calculate statistics for dashboard
    total_rak = rak_sessions.count()
    rak_selesai = rak_sessions.filter(status='completed').count()
    
    # Calculate total selisih from all completed rak sessions
    total_selisih = 0
    for rak_session in rak_sessions.filter(status='completed'):
        # Sum all qty_selisih from items in this rak session
        session_selisih = rak_session.items.aggregate(
            total_selisih=Sum('qty_selisih')
        )['total_selisih'] or 0
        total_selisih += session_selisih
    
    # Calculate verification progress
    total_items = 0
    verified_items = 0
    for rak_session in rak_sessions:
        session_items = rak_session.items.count()
        session_verified = rak_session.items.filter(is_verified=True).count()
        total_items += session_items
        verified_items += session_verified
    
    progress_verifikasi = 0
    if total_items > 0:
        progress_verifikasi = (verified_items / total_items) * 100

    context = {
        'full_session': full_session,
        'rak_sessions': rak_sessions,
        'can_delete_full_opname': can_delete_full_opname,
        'total_rak': total_rak,
        'rak_selesai': rak_selesai,
        'total_selisih': total_selisih,
        'progress_verifikasi': progress_verifikasi,
        'total_items': total_items,
        'verified_items': verified_items,
    }
    return render(request, template_name, context)


@login_required
@permission_required('inventory.change_opname', raise_exception=True)
def full_opname_complete(request, session_id):
    """Selesai full opname session"""
    full_session = get_object_or_404(FullOpnameSession, id=session_id)
    
    # Cek apakah semua rak session sudah selesai (selesai atau completed)
    incomplete_sessions = full_session.rak_opname_sessions.exclude(
        Q(status='selesai') | Q(status='completed')
    )
    if incomplete_sessions.exists():
        messages.error(request, 'Tidak semua sesi opname rak telah selesai')
        return redirect('inventory:full_opname_detail', session_id=session_id)
    
    try:
        full_session.status = 'completed'
        full_session.tanggal_selesai = timezone.now()
        full_session.completed_by = request.user
        full_session.save()
        
        messages.success(request, f'Full opname session "{full_session.nama_opname}" telah selesai')
        
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    return redirect('inventory:full_opname_detail', session_id=session_id)


@login_required
@permission_required('inventory.delete_opname', raise_exception=True)
def full_opname_delete(request, session_id):
    """Hapus full opname session (hanya jika status draft)"""
    full_session = get_object_or_404(FullOpnameSession, id=session_id)
    
    if request.method != 'POST':
        messages.error(request, 'Method tidak diizinkan')
        return redirect('inventory:full_opname_list')
    
    # Cek apakah session masih draft
    if full_session.status != 'draft':
        messages.error(request, 'Hanya Full Opname Session dengan status Draft yang dapat dihapus')
        return redirect('inventory:full_opname_list')
    
    try:
        with transaction.atomic():
            # Hapus semua sesi opname rak yang terkait (hanya yang masih draft)
            draft_rak_sessions = full_session.rak_opname_sessions.filter(status='draft')
            deleted_rak_sessions_count = draft_rak_sessions.count()
            
            for rak_session in draft_rak_sessions:
                # Hapus semua item opname
                RakOpnameItem.objects.filter(session=rak_session).delete()
                # Hapus semua log
                RakOpnameLog.objects.filter(session=rak_session).delete()
                # Hapus sesi rak
                rak_session.delete()
            
            # Hapus full opname session
            session_name = full_session.nama_opname
            full_session.delete()
            
            messages.success(request, f'Full Opname Session "{session_name}" berhasil dihapus bersama {deleted_rak_sessions_count} sesi opname rak')
            
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan saat menghapus: {str(e)}')
    
    return redirect('inventory:full_opname_list')


# ===== EXISTING RAK OPNAME VIEWS =====

@login_required
@permission_required('inventory.view_opname', raise_exception=True)
def opname_rak_list(request):
    """Halaman daftar sesi opname rak"""
    import re
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = re.search(r'mobile|android|iphone', user_agent)
    
    # Check if this is an AJAX request for DataTables
    if (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
        request.GET.get('draw') or request.GET.get('start') or request.GET.get('length')):
        return opname_rak_list_ajax(request)
    
    sessions = RakOpnameSession.objects.select_related('rak', 'created_by').order_by('-tanggal_mulai')
    
    # Filter
    status_filter = request.GET.get('status')
    if status_filter:
        sessions = sessions.filter(status=status_filter)
    
    rak_filter = request.GET.get('rak')
    if rak_filter:
        sessions = sessions.filter(rak__lokasi__icontains=rak_filter)
    
    # Pagination
    paginator = Paginator(sessions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_choices': RakOpnameSession.STATUS_CHOICES,
        'raks': Rak.objects.all().order_by('lokasi'),
    }
    
    template_name = 'inventory/opname_rak_list_mobile.html' if is_mobile else 'inventory/opname_rak_list.html'
    return render(request, template_name, context)


def opname_rak_list_ajax(request):
    """API untuk DataTables opname rak list"""
    sessions = RakOpnameSession.objects.select_related('rak', 'created_by').order_by('-tanggal_mulai')
    
    # Filter
    status_filter = request.GET.get('status')
    if status_filter:
        sessions = sessions.filter(status=status_filter)
    
    rak_filter = request.GET.get('rak')
    if rak_filter:
        sessions = sessions.filter(rak__lokasi__icontains=rak_filter)
    
    # DataTables parameters
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 25))
    search_value = request.GET.get('search[value]', '')
    
    # Search
    if search_value:
        sessions = sessions.filter(
            Q(session_code__icontains=search_value) |
            Q(rak__lokasi__icontains=search_value) |
            Q(rak__kode_rak__icontains=search_value) |
            Q(created_by__username__icontains=search_value)
        )
    
    total_records = sessions.count()
    sessions = sessions[start:start + length]
    
    data = []
    for session in sessions:
        data.append({
            'id': session.id,
            'session_code': session.session_code,
            'rak_lokasi': f"{session.rak.lokasi} ({session.rak.kode_rak})",
            'tipe_session': session.tipe_session,
            'status': session.status,
            'total_items': session.total_items,
            'total_selisih': session.total_selisih,
            'created_by_username': session.created_by.username if session.created_by else '-',
            'tanggal_mulai': session.tanggal_mulai.strftime('%d/%m/%Y %H:%M') if session.tanggal_mulai else '-',
        })
    
    return JsonResponse({
        'draw': int(request.GET.get('draw', 1)),
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })


def opname_rak_summary(request):
    """API untuk summary data opname rak"""
    try:
        sesi_draft = RakOpnameSession.objects.filter(status='draft').count()
        sesi_berlangsung = RakOpnameSession.objects.filter(status='in_progress').count()
        sesi_selesai = RakOpnameSession.objects.filter(status='selesai').count()
        
        # Total selisih dari semua sesi selesai
        total_selisih = sum(
            session.total_selisih for session in 
            RakOpnameSession.objects.filter(status='selesai')
        )
        
        return JsonResponse({
            'sesi_draft': sesi_draft,
            'sesi_berlangsung': sesi_berlangsung,
            'sesi_selesai': sesi_selesai,
            'total_selisih': total_selisih
        })
    except Exception as e:
        return JsonResponse({
            'sesi_draft': 0,
            'sesi_berlangsung': 0,
            'sesi_selesai': 0,
            'total_selisih': 0,
            'error': str(e)
        })


def full_opname_sessions_api(request):
    """API untuk mendapatkan daftar full opname sessions yang aktif"""
    if request.method == 'GET':
        # Ambil full opname sessions yang masih draft atau in_progress
        full_sessions = FullOpnameSession.objects.filter(
            status__in=['draft', 'in_progress']
        ).order_by('-tanggal_mulai')
        
        sessions_data = []
        for session in full_sessions:
            sessions_data.append({
                'id': session.id,
                'session_code': session.session_code,
                'nama_opname': session.nama_opname,
                'status': session.status,
                'display_text': f"{session.session_code} - {session.nama_opname}"
            })
        
        return JsonResponse({
            'success': True,
            'full_sessions': sessions_data
        })
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

def full_opname_rak_list(request, full_session_id):
    """API endpoint untuk mendapatkan daftar rak dalam full opname session"""
    try:
        full_session = get_object_or_404(FullOpnameSession, id=full_session_id)
        raks_data = []
        
        for rak in full_session.target_raks.all():
            # Cari rak session yang terkait dengan full session ini
            rak_session = rak.rak_opname_sessions.filter(full_opname_session=full_session).first()
            
            rak_data = {
                'rak_id': rak.id,
                'kode_rak': rak.kode_rak,
                'nama_rak': rak.nama_rak if hasattr(rak, 'nama_rak') else rak.kode_rak,
                'lokasi': rak.lokasi,
                'status': 'belum_dimulai',
                'rak_session_id': None
            }
            
            if rak_session:
                rak_data['status'] = rak_session.status
                rak_data['rak_session_id'] = rak_session.id
            
            raks_data.append(rak_data)
        
        # Sort: belum dimulai first, selesai last
        status_order = {'belum_dimulai': 0, 'draft': 1, 'in_progress': 2, 'selesai': 3}
        raks_data.sort(key=lambda x: status_order.get(x['status'], 4))
        
        return JsonResponse({
            'success': True,
            'raks': raks_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def full_opname_rak_work(request, full_session_id, rak_session_id):
    """Redirect ke opname rak work dari full opname session"""
    try:
        # Validasi bahwa rak session memang terkait dengan full session
        rak_session = get_object_or_404(RakOpnameSession, 
                                       id=rak_session_id, 
                                       full_opname_session_id=full_session_id)
        
        # Redirect ke opname rak work
        return redirect('inventory:opname_rak_work', session_id=rak_session_id)
        
    except RakOpnameSession.DoesNotExist:
        messages.error(request, 'Sesi opname rak tidak ditemukan atau tidak terkait dengan full opname session ini.')
        return redirect('inventory:full_opname_detail', session_id=full_session_id)


@login_required
@permission_required('inventory.add_opname', raise_exception=True)
def opname_rak_create(request):
    """Buat sesi opname rak baru - untuk AJAX request dan direct access"""
    if request.method == 'GET':
        # Jika diakses langsung, redirect ke list page
        return redirect('inventory:opname_rak_list')
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method tidak diizinkan'})
    
    rak_id = request.POST.get('rak_id')
    catatan = request.POST.get('catatan', '')
    full_opname_session_id = request.POST.get('full_opname_session_id')
    tipe_session = request.POST.get('tipe_session', 'reguler_opname')  # Default ke reguler
    
    if not rak_id:
        return JsonResponse({'success': False, 'message': 'Rak harus dipilih'})
    
    rak = get_object_or_404(Rak, id=rak_id)
    
    # Cek apakah ada sesi draft untuk rak ini
    existing_draft = RakOpnameSession.objects.filter(rak=rak, status='draft').first()
    if existing_draft:
        return JsonResponse({
            'success': False, 
            'message': f'Sudah ada sesi draft untuk rak {rak.lokasi}. Gunakan sesi yang ada atau selesaikan terlebih dahulu.',
            'redirect_url': f'/inventory/opname-rak/{existing_draft.id}/work/'
        })
    
    # Buat sesi baru
    session_code = f"OPNAME-{rak.kode_rak}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    try:
        with transaction.atomic():
            session = RakOpnameSession.objects.create(
                rak=rak,
                session_code=session_code,
                catatan=catatan,
                created_by=request.user,
                full_opname_session_id=full_opname_session_id if full_opname_session_id else None,
                tipe_session=tipe_session
            )
            
            # Log pembuatan sesi
            RakOpnameLog.objects.create(
                session=session,
                action='create',
                user=request.user,
                details=f'Sesi opname dibuat untuk rak {rak.lokasi} (Tipe: {tipe_session})'
            )
            
            # Ambil stok produk di rak ini
            rak_stocks = InventoryRakStock.objects.filter(rak=rak, quantity__gt=0)
            
            # Buat item opname untuk setiap produk
            for stock in rak_stocks:
                # Untuk partial opname, set qty_fisik = qty_sistem dan is_verified = True
                if tipe_session == 'partial_opname':
                    RakOpnameItem.objects.create(
                        session=session,
                        product=stock.product,
                        qty_sistem=stock.quantity,
                        qty_fisik=stock.quantity,  # Set sama dengan sistem
                        qty_selisih=0,  # Tidak ada selisih
                        is_verified=True  # Otomatis terverifikasi
                    )
                else:
                    RakOpnameItem.objects.create(
                        session=session,
                        product=stock.product,
                        qty_sistem=stock.quantity,
                        qty_fisik=0  # Akan diisi saat opname
                    )
        
        return JsonResponse({
            'success': True,
            'message': f'Sesi opname berhasil dibuat untuk rak {rak.lokasi} (Tipe: {tipe_session})',
            'redirect_url': f'/inventory/opname-rak/{session.id}/work/'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Gagal membuat sesi: {str(e)}'})


@login_required
@permission_required('inventory.add_opname', raise_exception=True)
def partial_opname_create(request):
    """Buat sesi partial opname rak - untuk AJAX request"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method tidak diizinkan'})
    
    rak_id = request.POST.get('rak_id')
    catatan = request.POST.get('catatan', '')
    
    if not rak_id:
        return JsonResponse({'success': False, 'message': 'Rak harus dipilih'})
    
    rak = get_object_or_404(Rak, id=rak_id)
    
    # Cek apakah ada sesi draft untuk rak ini
    existing_draft = RakOpnameSession.objects.filter(rak=rak, status='draft', tipe_session='partial_opname').first()
    if existing_draft:
        return JsonResponse({
            'success': False, 
            'message': f'Sudah ada sesi partial opname draft untuk rak {rak.kode_rak}. Gunakan sesi yang ada atau selesaikan terlebih dahulu.',
            'redirect_url': f'/inventory/opname-rak/{existing_draft.id}/work/'
        })
    
    # Buat sesi baru
    session_code = f"PARTIAL-{rak.kode_rak}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    try:
        with transaction.atomic():
            session = RakOpnameSession.objects.create(
                rak=rak,
                session_code=session_code,
                catatan=catatan,
                created_by=request.user,
                tipe_session='partial_opname'
            )
            
            # Log pembuatan sesi
            RakOpnameLog.objects.create(
                session=session,
                action='create',
                user=request.user,
                details=f'Sesi partial opname dibuat untuk rak {rak.kode_rak}'
            )
            
            # Ambil stok produk di rak ini
            rak_stocks = InventoryRakStock.objects.filter(rak=rak, quantity__gt=0)
            
            # Buat item opname untuk setiap produk dengan qty_fisik = qty_sistem dan terverifikasi
            for stock in rak_stocks:
                RakOpnameItem.objects.create(
                    session=session,
                    product=stock.product,
                    qty_sistem=stock.quantity,
                    qty_fisik=stock.quantity,  # Set sama dengan sistem
                    qty_selisih=0,  # Tidak ada selisih
                    is_verified=True  # Otomatis terverifikasi
                )
        
        return JsonResponse({
            'success': True,
            'message': f'Sesi partial opname berhasil dibuat untuk rak {rak.kode_rak}',
            'redirect_url': f'/inventory/opname-rak/{session.id}/work/'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Gagal membuat sesi: {str(e)}'})


@login_required
@permission_required('inventory.change_opname', raise_exception=True)
def opname_rak_work(request, session_id):
    """Halaman kerja opname rak"""
    session = get_object_or_404(RakOpnameSession, id=session_id)
    
    # Izinkan sesi dengan status 'draft' atau 'in_progress' untuk diedit
    # Sesi dengan status 'selesai' atau 'dibatalkan' tidak bisa diedit.
    if session.status not in ['draft', 'in_progress']:
        messages.error(request, 'Sesi opname sudah tidak bisa diedit karena statusnya bukan Draft atau In Progress.')
        return redirect('inventory:opname_rak_list')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_item':
            return update_opname_item(request, session)
        elif action == 'add_item':
            return add_opname_item(request, session)
        elif action == 'delete_item':
            return delete_opname_item(request, session)
        elif action == 'verify_item':
            return verify_opname_item(request, session)
        elif action == 'selesai':
            return finish_opname_session(request, session)
    
    # GET request - tampilkan form opname
    # Sorting berdasarkan status verifikasi dan qty_fisik:
    # 1. qty_fisik > 0 dan belum verified (paling atas)
    # 2. qty_fisik = 0 dan belum verified (urutan kedua)
    # 3. sudah verified (paling bawah)
    from django.db.models import Case, When, Value, IntegerField
    
    items = session.items.select_related('product').annotate(
        sort_order=Case(
            # qty_fisik > 0 dan belum verified = 1 (paling atas)
            When(qty_fisik__gt=0, is_verified=False, then=Value(1)),
            # qty_fisik = 0 dan belum verified = 2 (urutan kedua)
            When(qty_fisik=0, is_verified=False, then=Value(2)),
            # sudah verified = 3 (paling bawah)
            When(is_verified=True, then=Value(3)),
            default=Value(2),  # fallback
            output_field=IntegerField(),
        )
    ).order_by('sort_order', 'product__nama_produk')
    
    # Hitung status verifikasi untuk UI
    total_items = items.count()
    verified_items = items.filter(is_verified=True).count()
    unverified_items = total_items - verified_items
    
    context = {
        'session': session,
        'items': items,
        'total_items': total_items,
        'verified_items': verified_items,
        'unverified_items': unverified_items,
        'all_verified': unverified_items == 0  # Allow empty session to be completed
    }
    return render(request, 'inventory/opname_rak_work.html', context)


def update_opname_item(request, session):
    """Update qty fisik item opname"""
    try:
        item_id = request.POST.get('item_id')
        qty_fisik = request.POST.get('qty_fisik')
        
        if not item_id or qty_fisik is None:
            return JsonResponse({'status': 'error', 'message': 'Data tidak lengkap'})
        
        item = get_object_or_404(RakOpnameItem, id=item_id, session=session)
        old_qty = item.qty_fisik
        
        # Get master stock
        try:
            master_stock = Stock.objects.get(product=item.product).quantity
        except Stock.DoesNotExist:
            master_stock = 0
        
        qty_fisik_int = int(float(qty_fisik) if qty_fisik else 0)
        
        # Get current rak stock
        rak_stock, created = InventoryRakStock.objects.get_or_create(
            product=item.product,
            rak=session.rak,
            defaults={'quantity': 0, 'quantity_opname': 0}
        )
        
        # Validasi individual qty fisik tidak boleh melebihi stok master
        if qty_fisik_int > master_stock:
            return JsonResponse({
                'status': 'error', 
                'message': f'Qty fisik ({qty_fisik_int}) melebihi stok master ({master_stock})'
            })
        
        # Validasi total quantity_opname dari semua rak tidak melebihi master stock
        # Hitung total quantity_opname yang sudah ada di semua rak (exclude rak saat ini)
        existing_total_opname_other_racks = InventoryRakStock.objects.filter(
            product=item.product
        ).exclude(rak=session.rak).aggregate(
            total=Sum('quantity_opname')
        )['total'] or 0
        
        # Hitung quantity_opname di rak saat ini (exclude yang akan diupdate)
        current_rak_opname = rak_stock.quantity_opname - old_qty
        
        # Projected total quantity_opname setelah update
        projected_total_opname = existing_total_opname_other_racks + current_rak_opname + qty_fisik_int
        
        if projected_total_opname > master_stock:
            return JsonResponse({
                'status': 'error', 
                'message': f'Total quantity_opname produk di semua rak ({projected_total_opname}) akan melebihi stok master ({master_stock})'
            })
        
        # Update quantity_opname di InventoryRakStock
        rak_stock.quantity_opname = rak_stock.quantity_opname - old_qty + qty_fisik_int
        rak_stock.save()
        
        # Update qty fisik
        item.qty_fisik = qty_fisik_int
        item.qty_selisih = item.qty_fisik - item.qty_sistem
        item.save()

        # Update session status if it's still draft
        if session.status == 'draft' and item.qty_fisik > 0:
            session.status = 'in_progress'
            session.save()

        # Log perubahan
        RakOpnameLog.objects.create(
            session=session,
            action='update_item',
            user=request.user,
            details=f'Update {item.product.sku}: {old_qty} → {item.qty_fisik}'
        )
        
        return JsonResponse({
            'status': 'success',
            'qty_selisih': float(item.qty_selisih),
            'message': 'Qty fisik berhasil diupdate',
            'session_status': session.get_status_display(), # Tambahkan status sesi
            'session_progress_percentage': float(session.progress_percentage), # Tambahkan progress sesi
            'total_items_in_session': session.total_items, # Tambahkan total item di sesi
            'completed_items_in_session': session.completed_items_count # Tambahkan completed items di sesi
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


def add_opname_item(request, session):
    """Tambah item baru ke sesi opname"""
    try:
        product_id = request.POST.get('product_id')
        qty_fisik = request.POST.get('qty_fisik', 0)
        
        if not product_id:
            return JsonResponse({'status': 'error', 'message': 'Produk harus dipilih'})
        
        product = get_object_or_404(Product, id=product_id)
        
        # Cek apakah produk sudah ada di sesi
        existing_item = session.items.filter(product=product).first()
        if existing_item:
            return JsonResponse({'status': 'error', 'message': 'Produk sudah ada di sesi opname'})
        
        # Get master stock
        try:
            master_stock = Stock.objects.get(product=product).quantity
        except Stock.DoesNotExist:
            master_stock = 0
        
        qty_fisik_int = int(float(qty_fisik) if qty_fisik else 0)
        
        # Get current rak stock (termasuk quantity_opname)
        rak_stock, created = InventoryRakStock.objects.get_or_create(
            product=product,
            rak=session.rak,
            defaults={'quantity': 0, 'quantity_opname': 0}
        )
        
        # Validasi: qty_fisik tidak boleh melebihi stok master
        if qty_fisik_int > master_stock:
            return JsonResponse({
                'status': 'error', 
                'message': f'Qty fisik ({qty_fisik_int}) melebihi stok master ({master_stock})'
            })
        
        # Validasi total quantity_opname dari semua rak tidak melebihi master stock
        # Hitung total quantity_opname yang sudah ada di semua rak (exclude rak saat ini)
        existing_total_opname_other_racks = InventoryRakStock.objects.filter(
            product=product
        ).exclude(rak=session.rak).aggregate(
            total=Sum('quantity_opname')
        )['total'] or 0
        
        # Hitung quantity_opname di rak saat ini
        current_rak_opname = rak_stock.quantity_opname
        
        # Projected total quantity_opname setelah menambah produk ini
        projected_total_opname = existing_total_opname_other_racks + current_rak_opname + qty_fisik_int
        
        if projected_total_opname > master_stock:
            return JsonResponse({
                'status': 'error', 
                'message': f'Total quantity_opname produk di semua rak ({projected_total_opname}) akan melebihi stok master ({master_stock})'
            })
        
        # Buat item baru
        item = RakOpnameItem.objects.create(
            session=session,
            product=product,
            qty_sistem=rak_stock.quantity,  # Quantity sistem saat ini
            qty_fisik=qty_fisik_int,
            qty_selisih=qty_fisik_int - rak_stock.quantity
        )

        # Update quantity_opname di InventoryRakStock
        rak_stock.quantity_opname += qty_fisik_int
        rak_stock.save()

        # Update session status if it's still draft
        if session.status == 'draft' and item.qty_fisik > 0:
            session.status = 'in_progress'
            session.save()

        # Log penambahan
        RakOpnameLog.objects.create(
            session=session,
            action='add_item',
            user=request.user,
            details=f'Tambah {product.sku}: {item.qty_fisik} (opname)'
        )

        # Get photo URL safely
        photo_url = ''
        try:
            if product.photo:
                photo_url = product.photo.url
        except ValueError:
            photo_url = ''

        return JsonResponse({
            'status': 'success',
            'message': f'Produk {product.sku} berhasil ditambahkan',
            'item': {
                'id': item.id,
                'sku': product.sku,
                'nama_produk': item.product.nama_produk,
                'variant_produk': item.product.variant_produk or '',
                'brand': item.product.brand or '',
                'barcode': item.product.barcode or '',
                'photo_url': photo_url,
                'qty_sistem': rak_stock.quantity,
                'qty_fisik': float(item.qty_fisik),
                'qty_selisih': float(item.qty_selisih)
            },
            'session_status': session.get_status_display(), # Tambahkan status sesi
            'session_progress_percentage': float(session.progress_percentage), # Tambahkan progress sesi
            'total_items_in_session': session.total_items, # Tambahkan total item di sesi
            'completed_items_in_session': session.completed_items_count # Tambahkan completed items di sesi
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


def delete_opname_item(request, session):
    """Hapus item dari sesi opname"""
    try:
        item_id = request.POST.get('item_id')
        
        if not item_id:
            return JsonResponse({'status': 'error', 'message': 'Item tidak ditemukan'})
        
        item = get_object_or_404(RakOpnameItem, id=item_id, session=session)
        product_sku = item.product.sku
        
        # Kurangi quantity_opname di InventoryRakStock
        rak_stock, created = InventoryRakStock.objects.get_or_create(
            product=item.product,
            rak=session.rak,
            defaults={'quantity': 0, 'quantity_opname': 0}
        )
        
        # Kurangi quantity_opname dengan qty_fisik yang dihapus
        rak_stock.quantity_opname -= item.qty_fisik
        rak_stock.save()
        
        # Log penghapusan
        RakOpnameLog.objects.create(
            session=session,
            action='delete_item',
            user=request.user,
            details=f'Hapus {product_sku} (qty: {item.qty_fisik})'
        )
        
        item.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Produk {product_sku} berhasil dihapus'
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


def verify_opname_item(request, session):
    """Verifikasi item opname (toggle is_verified)"""
    try:
        item_id = request.POST.get('item_id')
        
        if not item_id:
            return JsonResponse({'status': 'error', 'message': 'Item tidak ditemukan'})
        
        item = get_object_or_404(RakOpnameItem, id=item_id, session=session)
        
        # Toggle verification status
        if item.is_verified:
            # Unverify
            item.is_verified = False
            item.verified_by = None
            item.verified_at = None
            action_message = 'unverified'
        else:
            # Verify
            item.is_verified = True
            item.verified_by = request.user
            item.verified_at = timezone.now()
            action_message = 'verified'
        
        item.save()
        
        # Log verifikasi
        RakOpnameLog.objects.create(
            session=session,
            action='verify_item',
            user=request.user,
            details=f'{action_message.title()} {item.product.sku}'
        )
        
        # Hitung jumlah item yang belum diverifikasi
        unverified_count = session.items.filter(is_verified=False).count()
        total_items = session.items.count()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Item {item.product.sku} berhasil {action_message}',
            'is_verified': item.is_verified,
            'verified_by': item.verified_by.username if item.verified_by else None,
            'verified_at': item.verified_at.strftime('%Y-%m-%d %H:%M') if item.verified_at else None,
            'unverified_count': unverified_count,
            'total_items': total_items,
            'all_verified': unverified_count == 0
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


def finish_opname_session(request, session):
    """Selesai sesi opname dan update InventoryRakStock"""
    try:
        # Validasi: semua item harus sudah diverifikasi
        unverified_items = session.items.filter(is_verified=False)
        if unverified_items.exists():
            unverified_skus = [item.product.sku for item in unverified_items[:5]]  # Ambil 5 pertama
            message = f"Tidak bisa menyelesaikan opname. Masih ada {unverified_items.count()} item yang belum diverifikasi: {', '.join(unverified_skus)}"
            if unverified_items.count() > 5:
                message += f" dan {unverified_items.count() - 5} item lainnya"
            return JsonResponse({'status': 'error', 'message': message})
        
        with transaction.atomic():
            # Update setiap item opname
            for item in session.items.all():
                rak_stock, created = InventoryRakStock.objects.get_or_create(
                    product=item.product,
                    rak=session.rak,
                    defaults={'quantity': 0, 'quantity_opname': 0}
                )
                
                # Kurangi quantity_opname yang sudah ada
                rak_stock.quantity_opname -= item.qty_fisik
                
                # Update quantity dengan qty_fisik dari opname
                rak_stock.quantity = item.qty_fisik
                rak_stock.save()
                
                # Log perubahan
                InventoryRakStockLog.objects.create(
                    produk=item.product,
                    rak=session.rak,
                    tipe_pergerakan='koreksi',
                    qty=item.qty_selisih,
                    qty_awal=item.qty_sistem,
                    qty_akhir=item.qty_fisik,
                    user=request.user,
                    catatan=f'Opname session {session.session_code}'
                )
            
            # Update status session
            session.status = 'completed' # Menggunakan 'completed'
            session.tanggal_selesai = timezone.now()
            session.completed_by = request.user
            session.save()
            
            # Log penyelesaian
            RakOpnameLog.objects.create(
                session=session,
                action='selesai',
                user=request.user,
                details='Sesi opname selesai'
            )
            
            # Update capacity untuk rak yang diopname
            from . import rakcapacity
            success, message = rakcapacity.update_rak_capacity_for_rak(session.rak.kode_rak)
            if not success:
                # Log warning tapi tidak gagalkan opname
                print(f"Warning: Gagal update capacity setelah opname: {message}")
            
        return JsonResponse({
            'status': 'success',
            'message': 'Opname berhasil diselesaikan',
            'redirect_to_full_opname': session.full_opname_session_id is not None, # Tambahkan ini
            'full_opname_session_id': session.full_opname_session_id # Tambahkan ini
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


def opname_rak_detail(request, session_id):
    """Detail sesi opname"""
    import re
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = re.search(r'mobile|android|iphone', user_agent)
    
    session = get_object_or_404(RakOpnameSession, id=session_id)
    items = session.items.select_related('product').order_by('product__nama_produk')
    logs = session.logs.select_related('user').order_by('-timestamp')
    
    # Calculate summary statistics
    items_with_positive_selisih = items.filter(qty_selisih__gt=0).count()
    items_with_negative_selisih = items.filter(qty_selisih__lt=0).count()
    items_with_zero_selisih = items.filter(qty_selisih=0).count()
    
    context = {
        'session': session,
        'items': items,
        'logs': logs,
        'items_with_positive_selisih': items_with_positive_selisih,
        'items_with_negative_selisih': items_with_negative_selisih,
        'items_with_zero_selisih': items_with_zero_selisih,
    }
    
    if is_mobile:
        return render(request, 'inventory/opname_rak_detail_mobile.html', context)
    else:
        return render(request, 'inventory/opname_rak_detail.html', context)


def opname_rak_cancel(request, session_id):
    """Batalkan sesi opname"""
    session = get_object_or_404(RakOpnameSession, id=session_id)
    
    if session.status != 'draft':
        messages.error(request, 'Hanya sesi draft yang bisa dibatalkan')
        return redirect('inventory:opname_rak_list')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Kurangi quantity_opname untuk semua item dalam sesi
                for item in session.items.all():
                    rak_stock, created = InventoryRakStock.objects.get_or_create(
                        product=item.product,
                        rak=session.rak,
                        defaults={'quantity': 0, 'quantity_opname': 0}
                    )
                    
                    # Kurangi quantity_opname dengan qty_fisik yang dibatalkan
                    rak_stock.quantity_opname -= item.qty_fisik
                    rak_stock.save()
                    
                    # Log pembatalan item
                    RakOpnameLog.objects.create(
                        session=session,
                        action='delete_item',
                        user=request.user,
                        details=f'Batalkan {item.product.sku} (qty: {item.qty_fisik})'
                    )
                
                # Update status session
                session.status = 'cancelled' # Menggunakan 'cancelled'
                session.save()
                
                # Log pembatalan
                RakOpnameLog.objects.create(
                    session=session,
                    action='batal',
                    user=request.user,
                    details='Sesi opname dibatalkan'
                )
                
            messages.success(request, f'Sesi opname {session.session_code} berhasil dibatalkan')
            return redirect('inventory:opname_rak_list')
            
        except Exception as e:
            messages.error(request, f'Gagal membatalkan sesi: {str(e)}')
    
    context = {
        'session': session,
    }
    return render(request, 'inventory/opname_rak_cancel.html', context)


# API untuk autocomplete produk
@require_GET
def product_autocomplete(request):
    """API untuk autocomplete produk"""
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    products = Product.objects.filter(
        Q(sku__icontains=query) | 
        Q(nama_produk__icontains=query) |
        Q(barcode__icontains=query)
    )[:10]
    
    results = []
    for product in products:
        # Get photo URL safely
        photo_url = ''
        try:
            if product.photo:
                photo_url = product.photo.url
        except ValueError:
            photo_url = ''
        
        # Get stock master quantity
        try:
            stock = Stock.objects.get(product=product)
            stok_master = stock.quantity
        except Stock.DoesNotExist:
            stok_master = 0
        
        # Get existing locations (rak) where this product is stored
        rak_locations = InventoryRakStock.objects.filter(
            product=product,
            quantity__gt=0
        ).select_related('rak').values(
            'rak__lokasi',
            'rak__kode_rak', 
            'quantity'
        ).order_by('rak__lokasi')
        
        # Format rak information
        rak_info = []
        total_rak_qty = 0
        for rak in rak_locations:
            rak_info.append({
                'lokasi': rak['rak__lokasi'],
                'kode_rak': rak['rak__kode_rak'],
                'quantity': rak['quantity']
            })
            total_rak_qty += rak['quantity']
        
        # Create display text for existing locations
        rak_display = []
        for rak in rak_info:
            rak_display.append(f"{rak['lokasi']} ({rak['kode_rak']}): {rak['quantity']}")
        rak_display_text = ', '.join(rak_display) if rak_display else 'Belum ada di rak manapun'
        
        results.append({
            'id': product.id,
            'text': f"{product.sku} - {product.nama_produk}",
            'sku': product.sku,
            'nama_produk': product.nama_produk,
            'variant_produk': product.variant_produk or '',
            'brand': product.brand or '',
            'barcode': product.barcode or '',
            'photo_url': photo_url,
            'stok_master': stok_master,
            'total_rak_qty': total_rak_qty,
            'rak_locations': rak_info,
            'rak_display_text': rak_display_text
        })
    
    return JsonResponse({'results': results})
