from django.shortcuts import render, get_object_or_404
from fullfilment.models import BatchList, BatchItem
from fullfilment.utils import get_sku_not_found
from products.models import Product
from inventory.models import Stock
from django.utils import timezone

def batchpicking_v2(request, nama_batch):
    batch = get_object_or_404(BatchList, nama_batch=nama_batch)
    items = BatchItem.objects.filter(batchlist=batch).select_related('product')

    # Siapkan data untuk template (mirip batchpicking lama)
    table_data = []
    for item in items:
        product = item.product
        table_data.append({
            'id': item.id,
            'sku': product.sku if product else '',
            'barcode': product.barcode if product else '',
            'nama_produk': product.nama_produk if product else '',
            'variant_produk': product.variant_produk if product else '',
            'brand': product.brand if product else '',
            'rak': product.rak if product else '',
            'jumlah': item.jumlah,
            'jumlah_ambil': item.jumlah_ambil,
            'status_ambil': item.status_ambil,
            'photo_url': product.photo.url if product and product.photo else '',
            'count_one': item.one_count,
            'count_duo': item.duo_count,
            'count_tri': item.tri_count,
        })

    total_pending = sum(1 for item in table_data if item['status_ambil'] != 'completed')
    total_completed = sum(1 for item in table_data if item['status_ambil'] == 'completed')
    sku_not_found_list, sku_not_found_count = get_sku_not_found(nama_batch)

    return render(request, 'fullfilment/batchpicking_v2.html', {
        'nama_picklist': batch.nama_batch,
        'details': table_data,
        'total_pending': total_pending,
        'total_completed': total_completed,
        'sku_not_found_count': sku_not_found_count,
        'sku_not_found_list': sku_not_found_list,
    })


# --- LOGIC UNTUK CONSUMER WEBSOCKET (dipanggil dari consumer, bukan dari view) ---

def update_barcode_ws(nama_batch, barcode, user):
    """
    Logic update scan barcode via WebSocket.
    Return dict hasil update (untuk dikirim ke client).
    """
    batch = get_object_or_404(BatchList, nama_batch=nama_batch)
    product = Product.objects.filter(barcode=barcode).first()
    if not product:
        return {'success': False, 'error': 'Produk dengan barcode ini tidak ditemukan.'}
    batchitem = BatchItem.objects.filter(batchlist=batch, product=product).first()
    if not batchitem:
        return {'success': False, 'error': 'Item tidak ditemukan di batch.'}

    if batchitem.status_ambil == 'completed':
        return {
            'success': False,
            'already_completed': True,
            'error': 'Item ini sudah selesai.'
        }

    if batchitem.jumlah_ambil < batchitem.jumlah:
        prev_jumlah_ambil = batchitem.jumlah_ambil
        batchitem.jumlah_ambil += 1
        # Update stock
        stock = Stock.objects.filter(product=product).first()
        if stock:
            delta = batchitem.jumlah_ambil - prev_jumlah_ambil
            stock.quantity -= delta
            stock.quantity_locked -= delta
            stock.save(update_fields=['quantity', 'quantity_locked'])
        # Check if completed
        if batchitem.jumlah_ambil >= batchitem.jumlah:
            batchitem.status_ambil = 'completed'
            batchitem.completed_at = timezone.now()
            if user and user.is_authenticated:
                batchitem.completed_by = user
        batchitem.save()
        return {
            'success': True,
            'item': {
                'sku': product.sku,
                'barcode': product.barcode,
                'jumlah_ambil': batchitem.jumlah_ambil,
                'status_ambil': batchitem.status_ambil,
            }
        }
    else:
        return {'success': False, 'error': 'Jumlah ambil sudah cukup.'}


def update_manual_ws(nama_batch, barcode, jumlah_ambil, user):
    """
    Logic update manual qty via WebSocket.
    Return dict hasil update (untuk dikirim ke client).
    """
    batch = get_object_or_404(BatchList, nama_batch=nama_batch)
    product = Product.objects.filter(barcode=barcode).first()
    if not product:
        return {'success': False, 'error': 'Produk dengan barcode ini tidak ditemukan.'}
    batchitem = BatchItem.objects.filter(batchlist=batch, product=product).first()
    if not batchitem:
        return {'success': False, 'error': 'Item tidak ditemukan di batch.'}
    try:
        jumlah_ambil = int(jumlah_ambil)
    except Exception:
        return {'success': False, 'error': 'Jumlah ambil tidak valid.'}
    if jumlah_ambil < 0 or jumlah_ambil > batchitem.jumlah:
        return {'success': False, 'error': 'Jumlah ambil di luar batas.'}
    prev_jumlah_ambil = batchitem.jumlah_ambil
    batchitem.jumlah_ambil = jumlah_ambil
    # Update stock
    stock = Stock.objects.filter(product=product).first()
    if stock:
        delta = batchitem.jumlah_ambil - prev_jumlah_ambil
        stock.quantity -= delta
        stock.quantity_locked -= delta
        stock.save(update_fields=['quantity', 'quantity_locked'])
    # Update status
    if batchitem.jumlah_ambil >= batchitem.jumlah:
        batchitem.status_ambil = 'completed'
        batchitem.completed_at = timezone.now()
        if user and user.is_authenticated:
            batchitem.completed_by = user
    else:
        batchitem.status_ambil = 'pending'
        batchitem.completed_at = None
        batchitem.completed_by = None
    batchitem.save()
    return {
        'success': True,
        'item': {
            'sku': product.sku,
            'barcode': product.barcode,
            'jumlah_ambil': batchitem.jumlah_ambil,
            'status_ambil': batchitem.status_ambil,
        }
    }
