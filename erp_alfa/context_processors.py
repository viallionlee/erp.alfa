from django.db.models import Count, Sum, Q
from inventory.models import Stock, OpnameQueue, RakTransferSession
from fullfilment.models import BatchList, ReturnSession, ReturnItem, ReadyToPrint
from purchasing.models import Purchase, PurchasePayment, PurchaseTaxInvoice


def purchasing_permissions(request):
    """
    Context processor untuk menyediakan purchasing permissions ke semua template
    """
    context = {}
    
    if request.user.is_authenticated:
        context['purchasing_po_view'] = request.user.has_perm('purchasing.po_view')
        context['purchasing_po_marketing'] = request.user.has_perm('purchasing.po_marketing')
        context['purchasing_purchase_view'] = request.user.has_perm('purchasing.purchase_view')
        context['purchasing_purchase_warehouse'] = request.user.has_perm('purchasing.purchase_warehouse')
        context['purchasing_purchase_finance'] = request.user.has_perm('purchasing.purchase_finance')
    else:
        context['purchasing_po_view'] = False
        context['purchasing_po_marketing'] = False
        context['purchasing_purchase_view'] = False
        context['purchasing_purchase_warehouse'] = False
        context['purchasing_purchase_finance'] = False
    
    return context


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
        
        # Return List badges
        # Jumlah session return yang masih open
        return_session_open_count = ReturnSession.objects.filter(status='open').count()
        context['return_session_open_count'] = return_session_open_count
        
        # Jumlah SKU dalam session yang belum di putaway
        return_sku_pending_putaway = ReturnItem.objects.filter(
            session__status='open',
            putaway_status__in=['pending', 'partial']
        ).values('product').distinct().count()
        context['return_sku_pending_putaway'] = return_sku_pending_putaway
        
        # Ready to Print List badges
        # Jumlah order yang sudah di-print tapi belum diserahkan
        ready_to_print_not_handed_over = ReadyToPrint.objects.filter(
            status_print='printed',
            handed_over_at__isnull=True
        ).count()
        context['ready_to_print_not_handed_over'] = ready_to_print_not_handed_over
        
        # Purchase Verify badges
        # Jumlah purchase yang sudah received tapi belum di-verify
        purchase_verify_pending_count = Purchase.objects.filter(status='received').count()
        context['purchase_verify_pending_count'] = purchase_verify_pending_count
        
        # Purchase Tax Invoice badges
        # Jumlah purchase yang sudah verified tapi has_tax_invoice=True dan belum ada tax invoice (pending)
        # Count purchases that need tax invoice but don't have one yet
        purchase_taxinvoice_pending_count = Purchase.objects.filter(
            status='verified',
            has_tax_invoice=True
        ).exclude(
            tax_invoice__status__in=['received', 'verified']
        ).count()
        context['purchase_taxinvoice_pending_count'] = purchase_taxinvoice_pending_count
        
        # Purchase Payment badges
        # Jumlah payment yang belum lunas (unpaid, partial, overdue)
        purchase_payment_unpaid_count = PurchasePayment.objects.filter(
            status__in=['unpaid', 'partial', 'overdue']
        ).count()
        context['purchase_payment_unpaid_count'] = purchase_payment_unpaid_count
        
    except Exception as e:
        # Jika ada error, set default values
        context['putaway_count'] = 0
        context['putaway_quantity'] = 0
        context['regular_putaway_count'] = 0
        context['transfer_putaway_count'] = 0
        context['opname_queue_count'] = 0
        context['batch_open_count'] = 0
        context['return_session_open_count'] = 0
        context['return_sku_pending_putaway'] = 0
        context['ready_to_print_not_handed_over'] = 0
        context['purchase_verify_pending_count'] = 0
        context['purchase_taxinvoice_pending_count'] = 0
        context['purchase_payment_unpaid_count'] = 0
    
    return context
