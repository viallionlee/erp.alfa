from django.shortcuts import render
from .models import BatchList
from django.db.models import Count, Q

def mobile_home(request):
    return render(request, 'mobile_home.html')

def mobile_batch_index(request):
    # Get all batches and annotate with required fields
    batchlists = list(BatchList.objects.all())
    # Sort: pending first, then completed, then others
    def status_order(batch):
        if batch.status_batch == 'pending':
            return 0
        elif batch.status_batch == 'completed':
            return 1
        else:
            return 2
    batchlists.sort(key=status_order)
    # Annotate each batch with total_sku, sku_pending, sku_completed
    from .models import BatchItem
    for batch in batchlists:
        batch.total_sku = BatchItem.objects.filter(batchlist=batch).count()
        batch.sku_pending = BatchItem.objects.filter(batchlist=batch, status_ambil='pending').count()
        batch.sku_completed = BatchItem.objects.filter(batchlist=batch, status_ambil='completed').count()
    return render(request, 'fullfilment/mobile_index.html', {'batchlists': batchlists})
