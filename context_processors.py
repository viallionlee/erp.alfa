from django.db.models import Count, Sum
from inventory.models import Stock, OpnameQueue, RakTransferSession
from fullfilment.models import BatchList


def notification_counts(request):
    """
    Context processor untuk menyediakan jumlah notifikasi ke semua template
    """
    context = {}
    
    try:
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
        
        context['putaway_count'] = total_putaway_count
        context['putaway_quantity'] = total_putaway_quantity
        context['regular_putaway_count'] = regular_putaway_count
        context['transfer_putaway_count'] = transfer_putaway_count
        
        # Jumlah opname queue yang pending
        opname_queue_count = OpnameQueue.objects.filter(status='pending').count()
        context['opname_queue_count'] = opname_queue_count
        
        # Jumlah batch yang open
        batch_open_count = BatchList.objects.filter(status_batch='open').count()
        context['batch_open_count'] = batch_open_count
        
    except Exception as e:
        # Jika ada error, set default values
        context['putaway_count'] = 0
        context['putaway_quantity'] = 0
        context['regular_putaway_count'] = 0
        context['transfer_putaway_count'] = 0
        context['opname_queue_count'] = 0
        context['batch_open_count'] = 0
    
    return context
