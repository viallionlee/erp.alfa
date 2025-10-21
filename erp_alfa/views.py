from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Sum, Q
from django.core.cache import cache
from django.views.static import serve
from django.conf import settings
from inventory.models import Stock, OpnameQueue
from fullfilment.models import BatchList, ReturnSession, ReturnItem, ReadyToPrint
import re
import time
import os
from django.contrib.auth import views as auth_views

def invalidate_notification_cache():
    """
    Invalidate notification counts cache
    Dipanggil ketika ada perubahan data yang mempengaruhi notification counts
    """
    cache.delete('notification_counts')

class CustomLoginView(auth_views.LoginView):
    template_name = 'registration/login.html'
    
    def get_template_names(self):
        # Deteksi User-Agent untuk mobile
        user_agent = self.request.META.get('HTTP_USER_AGENT', '').lower()
        is_mobile = re.search(r'mobile|android|iphone|ipad|ipod|blackberry|windows phone', user_agent)
        
        if is_mobile:
            return ['registration/login_mobile.html']
        else:
            return ['registration/login.html']

def home(request):
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
        return redirect('mobile_home')
    return render(request, 'home.html')

def favicon(request):
    """
    Serve favicon to prevent 404 warnings
    """
    try:
        # Path ke file favicon di static folder
        favicon_path = os.path.join(settings.BASE_DIR, 'static', 'icons', 'alfaicon.png')
        
        if os.path.exists(favicon_path):
            with open(favicon_path, 'rb') as f:
                return HttpResponse(f.read(), content_type='image/png')
        else:
            # Return empty response jika file tidak ditemukan
            return HttpResponse(status=204)
    except Exception:
        return HttpResponse(status=204)

def api_notification_counts(request):
    """
    API endpoint untuk mendapatkan jumlah notifikasi
    Digunakan untuk auto-refresh notification counts di frontend
    """
    start_time = time.time()
    
    # Cache key untuk notification counts
    cache_key = 'notification_counts'
    cache_timeout = 30  # 30 detik cache
    
    # Coba ambil dari cache dulu
    cached_data = cache.get(cache_key)
    if cached_data:
        cached_data['cached'] = True  # Mark as cached response
        cached_data['response_time'] = round((time.time() - start_time) * 1000, 2)  # ms
        return JsonResponse(cached_data)
    
    try:
        from inventory.models import RakTransferSession
        
        # Jumlah produk yang perlu di-putaway (regular putaway)
        putaway_summary = Stock.objects.filter(quantity_putaway__gt=0).aggregate(
            total_items=Count('product'),
            total_quantity=Sum('quantity_putaway')
        )
        regular_putaway_count = putaway_summary['total_items'] or 0
        regular_putaway_quantity = putaway_summary['total_quantity'] or 0
        
        # Jumlah transfer rak yang siap putaway
        transfer_putaway_count = RakTransferSession.objects.filter(
            status='ready_for_putaway', 
            mode='transfer_putaway'
        ).count()
        
        # Total putaway count (regular + transfer)
        total_putaway_count = regular_putaway_count + transfer_putaway_count
        total_putaway_quantity = regular_putaway_quantity
        
        # Jumlah opname queue yang pending
        opname_queue_count = OpnameQueue.objects.filter(status='pending').count()
        
        # Jumlah batch yang open
        batch_open_count = BatchList.objects.filter(status_batch='open').count()
        
        # Return List badges
        # Jumlah session return yang masih open
        return_session_open_count = ReturnSession.objects.filter(status='open').count()
        
        # Jumlah SKU dalam session yang belum di putaway
        return_sku_pending_putaway = ReturnItem.objects.filter(
            session__status='open',
            putaway_status__in=['pending', 'partial']
        ).values('product').distinct().count()
        
        # Ready to Print List badges
        # Jumlah order yang sudah di-print tapi belum diserahkan
        ready_to_print_not_handed_over = ReadyToPrint.objects.filter(
            status_print='printed',
            handed_over_at__isnull=True
        ).count()
        
        response_data = {
            'success': True,
            'putaway_count': total_putaway_count,  # Total dari regular + transfer
            'putaway_quantity': total_putaway_quantity,
            'regular_putaway_count': regular_putaway_count,
            'transfer_putaway_count': transfer_putaway_count,
            'opname_queue_count': opname_queue_count,
            'batch_open_count': batch_open_count,
            'return_session_open_count': return_session_open_count,
            'return_sku_pending_putaway': return_sku_pending_putaway,
            'ready_to_print_not_handed_over': ready_to_print_not_handed_over,
            'cached': False,
            'response_time': round((time.time() - start_time) * 1000, 2)  # ms
        }
        
        # Simpan ke cache
        cache.set(cache_key, response_data, cache_timeout)
        
        return JsonResponse(response_data)
        
    except Exception as e:
        error_data = {
            'success': False,
            'error': str(e),
            'putaway_count': 0,
            'putaway_quantity': 0,
            'regular_putaway_count': 0,
            'transfer_putaway_count': 0,
            'opname_queue_count': 0,
            'batch_open_count': 0,
            'return_session_open_count': 0,
            'return_sku_pending_putaway': 0,
            'ready_to_print_not_handed_over': 0,
            'cached': False,
            'response_time': round((time.time() - start_time) * 1000, 2)  # ms
        }
        
        # Cache error response juga untuk menghindari spam
        cache.set(cache_key, error_data, 60)  # Cache error lebih lama
        
        return JsonResponse(error_data, status=500)
