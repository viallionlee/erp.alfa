from collections import defaultdict
from .models import BatchList, BatchItem, ReadyToPrint
from orders.models import Order
from django.db.models import Q


def calculate_and_sync_ready_to_print(batchlist: BatchList):
    """
    Menghitung order mana saja dalam sebuah batch yang siap untuk di-pick
    berdasarkan stok yang tersedia dan menyinkronkan hasilnya ke model ReadyToPrint.

    Fungsi ini menerapkan sistem prioritas: order SAT dipenuhi terlebih dahulu.
    """
    if not batchlist:
        return

    # 1. Ambil semua order, kecualikan yang dibatalkan, dan pisahkan berdasarkan prioritas (SAT vs lainnya)
    all_orders_in_batch = Order.objects.filter(nama_batch=batchlist.nama_batch).exclude(
        Q(status__icontains='batal') | Q(status__icontains='cancel')
    ).order_by('id')
    sat_orders = all_orders_in_batch.filter(order_type='1')
    other_orders = all_orders_in_batch.exclude(order_type='1')

    # 2. Hitung total stok yang sudah diambil (picked) dari BatchItem
    batchitems = BatchItem.objects.filter(batchlist=batchlist)
    available_stock = defaultdict(int)
    for bi in batchitems:
        if bi.product_id:
            available_stock[bi.product_id] += bi.jumlah_ambil
    
    # Siapkan list untuk menampung ID yang siap dan stok berjalan untuk simulasi
    ready_to_pick_ids_list = []
    running_stock = available_stock.copy()

    # 3. PROSES PRIORITAS: Coba penuhi semua order SAT terlebih dahulu
    orders_per_pesanan_sat = defaultdict(list)
    for o in sat_orders:
        orders_per_pesanan_sat[o.id_pesanan].append(o)
    
    for id_pesanan, order_items in sorted(orders_per_pesanan_sat.items()):
        order_needs = defaultdict(int)
        for item in order_items:
            if item.product_id:
                order_needs[item.product_id] += item.jumlah
        
        can_fulfill = all(running_stock.get(pid, 0) >= j_needed for pid, j_needed in order_needs.items())
        
        if can_fulfill:
            for pid, j_needed in order_needs.items():
                running_stock[pid] -= j_needed
            ready_to_pick_ids_list.append(id_pesanan)

    # 4. PROSES REGULER: Gunakan sisa stok untuk order lainnya dengan urutan FIFO
    orders_per_pesanan_other = defaultdict(list)
    for o in other_orders:
        orders_per_pesanan_other[o.id_pesanan].append(o)

    for id_pesanan, order_items in sorted(orders_per_pesanan_other.items()):
        order_needs = defaultdict(int)
        for item in order_items:
            if item.product_id:
                order_needs[item.product_id] += item.jumlah
        
        can_fulfill = all(running_stock.get(pid, 0) >= j_needed for pid, j_needed in order_needs.items())
        
        if can_fulfill:
            for pid, j_needed in order_needs.items():
                running_stock[pid] -= j_needed
            ready_to_pick_ids_list.append(id_pesanan)

    # 5. Sinkronisasi hasil perhitungan ke tabel ReadyToPrint
    current_rtp_ids = set(ReadyToPrint.objects.filter(batchlist=batchlist).values_list('id_pesanan', flat=True))
    new_rtp_ids = set(ready_to_pick_ids_list)

    ids_to_add = new_rtp_ids - current_rtp_ids
    ids_to_remove = current_rtp_ids - new_rtp_ids

    if ids_to_remove:
        # Hanya hapus entri ReadyToPrint yang BELUM dicetak
        ReadyToPrint.objects.filter(batchlist=batchlist, id_pesanan__in=ids_to_remove, printed_at__isnull=True).delete()

    if ids_to_add:
        # Buat entri baru hanya untuk yang belum ada atau yang sebelumnya dihapus karena belum dicetak
        new_entries = [ReadyToPrint(batchlist=batchlist, id_pesanan=idp, status_print='pending') for idp in ids_to_add]
        ReadyToPrint.objects.bulk_create(new_entries, ignore_conflicts=True)

    # Debug: Print untuk melihat apa yang terjadi
    print(f"DEBUG: Batch {batchlist.nama_batch}")
    print(f"DEBUG: Total orders in batch: {len(all_orders_in_batch)}")
    print(f"DEBUG: Available stock: {dict(available_stock)}")
    print(f"DEBUG: Ready to pick IDs: {ready_to_pick_ids_list}")
    print(f"DEBUG: Current RTP IDs: {current_rtp_ids}")
    print(f"DEBUG: New RTP IDs: {new_rtp_ids}")
    print(f"DEBUG: IDs to add: {ids_to_add}")
    print(f"DEBUG: IDs to remove: {ids_to_remove}") 