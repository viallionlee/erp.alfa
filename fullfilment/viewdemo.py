from django.shortcuts import render, get_object_or_404
from .models import BatchList, BatchItem
from orders.models import Order
from collections import defaultdict

def batchpickingdemo(request, nama_batch):
    batch = get_object_or_404(BatchList, nama_batch=nama_batch)
    from orders.models import Order
    from products.models import Product
    # --- Sinkronisasi BatchItem dari orders_order ---
    orders = Order.objects.filter(nama_batch=nama_batch)
    from collections import defaultdict
    order_jumlah_per_product = defaultdict(int)
    for o in orders:
        if o.product_id:
            order_jumlah_per_product[o.product_id] += o.jumlah
    for product_id, jumlah in order_jumlah_per_product.items():
        product = Product.objects.filter(id=product_id).first()
        if not product:
            continue
        batchitem, created = BatchItem.objects.get_or_create(batchlist=batch, product=product, defaults={
            'jumlah': jumlah,
            'jumlah_ambil': 0,
            'status_ambil': 'pending',
        })
        if not created and batchitem.jumlah != jumlah:
            batchitem.jumlah = jumlah
            batchitem.save()
    items = BatchItem.objects.filter(batchlist=batch).select_related('product')

    table_data = []
    for item in items:
        product = item.product
        table_data.append({
            'sku': product.sku if product else '',
            'barcode': product.barcode if product else '',
            'nama_produk': product.nama_produk if product else '',
            'variant_produk': product.variant_produk if product else '',
            'brand': product.brand if product else '',
            'rack': product.rak if product else '',
            'jumlah': item.jumlah,
            'jumlah_ambil': item.jumlah_ambil,
            'status_ambil': item.status_ambil,
        })
    total_pending = sum(1 for item in table_data if item['status_ambil'] != 'completed')
    total_completed = sum(1 for item in table_data if item['status_ambil'] == 'completed')

    # Logic ready_to_pick sama seperti batchpicking
    orders = Order.objects.filter(nama_batch=nama_batch).order_by('id')
    batchitems = BatchItem.objects.filter(batchlist=batch)
    batchitem_fifo = defaultdict(int)
    for bi in batchitems:
        batchitem_fifo[bi.product_id] += bi.jumlah_ambil
    orders_per_pesanan = defaultdict(list)
    for o in orders:
        orders_per_pesanan[o.id_pesanan].append(o)
    ready_to_pick_ids = []
    for id_pesanan, order_items in orders_per_pesanan.items():
        order_needs = defaultdict(int)
        for item in order_items:
            order_needs[item.product_id] += item.jumlah
        all_ready = True
        temp_fifo = batchitem_fifo.copy()
        for product_id, jumlah_needed in order_needs.items():
            if temp_fifo[product_id] < jumlah_needed:
                all_ready = False
                break
            temp_fifo[product_id] -= jumlah_needed
        if all_ready:
            for product_id, jumlah_needed in order_needs.items():
                batchitem_fifo[product_id] -= jumlah_needed
            ready_to_pick_ids.append(id_pesanan)
    ready_to_pick = len(ready_to_pick_ids)
    total_order = len(orders_per_pesanan)

    # --- Hitung virtual column satuan & gabungan per item (per SKU/Product) ---
    # satuan: jumlah id_pesanan yang butuh product_id/sku tsb dengan order_type=1
    # gabungan: jumlah id_pesanan yang butuh product_id/sku tsb dengan order_type!=1
    sku_to_satuan = defaultdict(int)
    sku_to_gabungan = defaultdict(int)
    # Ambil semua order di batch
    orders = Order.objects.filter(nama_batch=nama_batch)
    for o in orders:
        if o.sku:
            if o.order_type == '1':
                sku_to_satuan[o.sku] += 1
            else:
                sku_to_gabungan[o.sku] += 1
    # Tambahkan ke table_data
    for row in table_data:
        row['satuan'] = sku_to_satuan.get(row['sku'], 0)
        row['gabungan'] = sku_to_gabungan.get(row['sku'], 0)

    return render(request, 'fullfilment/batchpickingdemo.html', {
        'nama_picklist': batch.nama_batch,
        'details': table_data,
        'total_pending': total_pending,
        'total_completed': total_completed,
        'total_order': total_order,
        'ready_to_pick': ready_to_pick,
        'ready_to_pick_ids': ready_to_pick_ids,
    })
