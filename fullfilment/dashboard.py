from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Sum, F, Case, When, Value, IntegerField
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
import pytz

from .models import (
    BatchList, BatchItem, ReadyToPrint, BatchItemLog, 
    BatchOrderLog, OrderCancelLog, ReturnSession, ReturnItem
)
from orders.models import Order, OrderPackingHistory, OrderHandoverHistory
from inventory.models import Stock

@login_required
def dashboard(request):
    """Dashboard utama fulfillment yang menampilkan informasi komprehensif"""
    # Set timezone ke Jakarta
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    now = timezone.now().astimezone(jakarta_tz)
    
    # Filter untuk batch yang masih open
    open_batches = BatchList.objects.filter(status_batch='open')
    
    # Get all statistics in one go
    context = {
        'dashboard_stats': get_main_statistics(open_batches),
        'status_stats': get_status_statistics(open_batches),
        'batch_performance': get_batch_performance(open_batches),
        'recent_activities': get_recent_activities(),
        'daily_progress': get_daily_progress(),
        'top_batches': get_top_performing_batches(open_batches),
        'alerts': get_alerts_and_issues(open_batches),
        'current_time': now,
        'open_batches_count': open_batches.count(),
    }
    
    return render(request, 'fullfilment/dashboard.html', context)

def get_main_statistics(open_batches):
    """Mendapatkan statistik utama dashboard"""
    batch_names = list(open_batches.values_list('nama_batch', flat=True))
    
    # Total orders di semua batch open
    total_orders = Order.objects.filter(
        nama_batch__in=batch_names
    ).exclude(status_bundle='Y').values('id_pesanan').distinct().count()
    
    # Orders ready to pick
    total_ready_to_pick = ReadyToPrint.objects.filter(
        batchlist__in=open_batches
    ).values('id_pesanan').distinct().count()
    
    # Orders printed
    total_printed = ReadyToPrint.objects.filter(
        batchlist__in=open_batches,
        printed_at__isnull=False
    ).values('id_pesanan').distinct().count()
    
    # Orders picked (dari BatchItemLog - ketika user melakukan picking)
    total_picked = BatchItemLog.objects.filter(
        batch__in=open_batches
    ).values('batch__nama_batch').distinct().count()
    
    # Orders packed (ada di OrderPackingHistory)
    total_packed = OrderPackingHistory.objects.filter(
        order__nama_batch__in=batch_names
    ).values('order__id_pesanan').distinct().count()
    
    # Orders shipped (ada di OrderHandoverHistory)
    total_shipped = OrderHandoverHistory.objects.filter(
        order__nama_batch__in=batch_names
    ).values('order__id_pesanan').distinct().count()
    
    # Orders cancelled hari ini
    total_cancelled = OrderCancelLog.objects.filter(
        scan_time__date=timezone.now().date()
    ).count()
    
    # Orders returned hari ini
    total_returned = ReturnItem.objects.filter(
        session__created_at__date=timezone.now().date()
    ).aggregate(total_qty=Sum('qty'))['total_qty'] or 0
    
    return {
        'total_orders': total_orders,
        'total_ready_to_pick': total_ready_to_pick,
        'total_printed': total_printed,
        'total_picked': total_picked,
        'total_packed': total_packed,
        'total_shipped': total_shipped,
        'total_cancelled': total_cancelled,
        'total_returned': total_returned,
    }

def get_status_statistics(open_batches):
    """Mendapatkan statistik berdasarkan status order"""
    stats = get_main_statistics(open_batches)
    total_orders = stats['total_orders']
    
    if total_orders == 0:
        return {
            'ready_to_pick_pct': 0,
            'printed_pct': 0,
            'picked_pct': 0,
            'packed_pct': 0,
            'shipped_pct': 0,
        }
    
    # Hitung percentage berdasarkan total orders yang ada
    return {
        'ready_to_pick_pct': round((stats['total_ready_to_pick'] / total_orders) * 100, 1) if total_orders > 0 else 0,
        'printed_pct': round((stats['total_printed'] / total_orders) * 100, 1) if total_orders > 0 else 0,
        'picked_pct': round((stats['total_picked'] / total_orders) * 100, 1) if total_orders > 0 else 0,
        'packed_pct': round((stats['total_packed'] / total_orders) * 100, 1) if total_orders > 0 else 0,
        'shipped_pct': round((stats['total_shipped'] / total_orders) * 100, 1) if total_orders > 0 else 0,
    }

def get_batch_performance(open_batches):
    """Mendapatkan performa batch"""
    batch_stats = []
    
    for batch in open_batches:
        # Total items di batch
        total_items = BatchItem.objects.filter(batchlist=batch).count()
        
        # Items yang sudah diambil
        picked_items = BatchItem.objects.filter(
            batchlist=batch,
            jumlah_ambil__gte=F('jumlah')
        ).count()
        
        # Total orders di batch
        total_orders = Order.objects.filter(
            nama_batch=batch.nama_batch
        ).exclude(status_bundle='Y').values('id_pesanan').distinct().count()
        
        # Orders yang sudah printed
        printed_orders = ReadyToPrint.objects.filter(
            batchlist=batch,
            printed_at__isnull=False
        ).values('id_pesanan').distinct().count()
        
        # Orders yang sudah picked
        picked_orders = OrderPackingHistory.objects.filter(
            order__nama_batch=batch.nama_batch
        ).values('order__id_pesanan').distinct().count()
        
        # Orders yang sudah shipped
        shipped_orders = OrderHandoverHistory.objects.filter(
            order__nama_batch=batch.nama_batch
        ).values('order__id_pesanan').distinct().count()
        
        # Hitung progress percentage
        item_progress = round((picked_items / total_items * 100) if total_items > 0 else 0, 1)
        order_progress = round((shipped_orders / total_orders * 100) if total_orders > 0 else 0, 1)
        
        batch_stats.append({
            'batch': batch,
            'total_items': total_items,
            'picked_items': picked_items,
            'item_progress': item_progress,
            'total_orders': total_orders,
            'printed_orders': printed_orders,
            'picked_orders': picked_orders,
            'shipped_orders': shipped_orders,
            'order_progress': order_progress,
            'created_at': batch.created_at,
        })
    
    # Sort berdasarkan progress tertinggi
    batch_stats.sort(key=lambda x: x['order_progress'], reverse=True)
    return batch_stats

def get_recent_activities():
    """Mendapatkan aktivitas terbaru"""
    activities = []
    
    # Recent batch activities
    recent_batch_logs = BatchItemLog.objects.select_related(
        'user', 'batch', 'product'
    ).order_by('-waktu')[:8]
    
    for log in recent_batch_logs:
        activities.append({
            'type': 'batch_pick',
            'user': log.user,
            'message': f"Picked {log.jumlah_ambil} {log.product.nama_produk} from {log.batch.nama_batch}",
            'time': log.waktu,
            'icon': 'bi-box-arrow-in-down',
            'color': 'success'
        })
    
    # Recent print activities
    recent_prints = ReadyToPrint.objects.select_related(
        'printed_by', 'batchlist'
    ).filter(
        printed_at__isnull=False
    ).order_by('-printed_at')[:4]
    
    for print_item in recent_prints:
        activities.append({
            'type': 'print',
            'user': print_item.printed_by,
            'message': f"Printed order {print_item.id_pesanan} from {print_item.batchlist.nama_batch}",
            'time': print_item.printed_at,
            'icon': 'bi-printer',
            'color': 'info'
        })
    
    # Recent shipping activities
    recent_shipping = OrderHandoverHistory.objects.select_related(
        'user', 'order'
    ).order_by('-waktu_ho')[:3]
    
    for shipping in recent_shipping:
        activities.append({
            'type': 'shipping',
            'user': shipping.user,
            'message': f"Shipped order {shipping.order.id_pesanan}",
            'time': shipping.waktu_ho,
            'icon': 'bi-truck',
            'color': 'primary'
        })
    
    # Sort semua activities berdasarkan waktu
    activities.sort(key=lambda x: x['time'], reverse=True)
    return activities[:12]

def get_daily_progress():
    """Mendapatkan progress harian"""
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    
    # Progress hari ini
    today_stats = get_main_statistics(BatchList.objects.filter(status_batch='open'))
    
    # Progress kemarin
    yesterday_orders = Order.objects.filter(
        tanggal_pembuatan__contains=yesterday.strftime('%Y-%m-%d')
    ).exclude(status_bundle='Y').values('id_pesanan').distinct().count()
    
    yesterday_shipped = OrderHandoverHistory.objects.filter(
        waktu_ho__date=yesterday
    ).values('order__id_pesanan').distinct().count()
    
    growth_rate = 0
    if yesterday_shipped > 0:
        growth_rate = round(((today_stats['total_shipped'] - yesterday_shipped) / yesterday_shipped * 100), 1)
    
    return {
        'today_orders': today_stats['total_orders'],
        'today_shipped': today_stats['total_shipped'],
        'yesterday_orders': yesterday_orders,
        'yesterday_shipped': yesterday_shipped,
        'growth_rate': growth_rate
    }

def get_top_performing_batches(open_batches):
    """Mendapatkan batch dengan performa terbaik"""
    batch_performance = get_batch_performance(open_batches)
    top_batches = batch_performance[:5]
    
    # Tambahkan ranking
    for i, batch in enumerate(top_batches, 1):
        batch['rank'] = i
        batch['rank_icon'] = get_rank_icon(i)
    
    return top_batches

def get_rank_icon(rank):
    """Mendapatkan icon untuk ranking"""
    icons = {
        1: 'bi-trophy-fill text-warning',
        2: 'bi-award-fill text-secondary',
        3: 'bi-award text-bronze',
        4: 'bi-star-fill text-info',
        5: 'bi-star text-muted'
    }
    return icons.get(rank, 'bi-star text-muted')

def get_alerts_and_issues(open_batches):
    """Mendapatkan alert dan issues"""
    alerts = []
    
    # Batch dengan progress rendah
    low_progress_batches = []
    for batch in open_batches:
        total_orders = Order.objects.filter(
            nama_batch=batch.nama_batch
        ).exclude(status_bundle='Y').values('id_pesanan').distinct().count()
        
        shipped_orders = OrderHandoverHistory.objects.filter(
            order__nama_batch=batch.nama_batch
        ).values('order__id_pesanan').distinct().count()
        
        if total_orders > 0:
            progress = (shipped_orders / total_orders) * 100
            if progress < 30:
                low_progress_batches.append({
                    'batch': batch,
                    'progress': round(progress, 1),
                    'total_orders': total_orders,
                    'shipped_orders': shipped_orders
                })
    
    if low_progress_batches:
        alerts.append({
            'type': 'warning',
            'icon': 'bi-exclamation-triangle',
            'title': 'Batch Progress Rendah',
            'message': f"{len(low_progress_batches)} batch memiliki progress di bawah 30%",
            'details': low_progress_batches[:3]
        })
    
    # Batch yang sudah lama tidak ada aktivitas
    inactive_batches = []
    for batch in open_batches:
        last_activity = BatchItemLog.objects.filter(
            batch=batch
        ).order_by('-waktu').first()
        
        if last_activity:
            hours_since_activity = (timezone.now() - last_activity.waktu).total_seconds() / 3600
            if hours_since_activity > 24:
                inactive_batches.append({
                    'batch': batch,
                    'hours_inactive': round(hours_since_activity, 1),
                    'last_activity': last_activity.waktu
                })
    
    if inactive_batches:
        alerts.append({
            'type': 'danger',
            'icon': 'bi-clock-history',
            'title': 'Batch Tidak Aktif',
            'message': f"{len(inactive_batches)} batch tidak ada aktivitas lebih dari 24 jam",
            'details': inactive_batches[:3]
        })
    
    # Stock issues
    stock_alerts = []
    for batch in open_batches:
        batch_items = BatchItem.objects.filter(batchlist=batch)
        for item in batch_items:
            if item.product:
                stock = Stock.objects.filter(product=item.product).first()
                if stock and stock.quantity_ready_virtual < item.jumlah:
                    stock_alerts.append({
                        'batch': batch,
                        'product': item.product,
                        'required': item.jumlah,
                        'available': stock.quantity_ready_virtual,
                        'shortage': item.jumlah - stock.quantity_ready_virtual
                    })
    
    if stock_alerts:
        alerts.append({
            'type': 'danger',
            'icon': 'bi-box-seam',
            'title': 'Stock Tidak Cukup',
            'message': f"{len(stock_alerts)} produk mengalami kekurangan stock",
            'details': stock_alerts[:3]
        })
    
    return alerts

def get_dashboard_api_data(request):
    """API endpoint untuk data dashboard (untuk AJAX refresh)"""
    open_batches = BatchList.objects.filter(status_batch='open')
    
    return {
        'main_stats': get_main_statistics(open_batches),
        'status_stats': get_status_statistics(open_batches),
        'alerts_count': len(get_alerts_and_issues(open_batches)),
        'last_updated': timezone.now().isoformat()
    }
