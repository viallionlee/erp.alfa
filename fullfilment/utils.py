from orders.models import Order
from typing import List, Tuple

def get_sku_not_found(nama_batch: str) -> Tuple[List[str], int]:
    """
    Return (sku_not_found_list, sku_not_found_count) for a given batch name.
    SKU not found = order di batch dengan product_id null, exclude status_bundle='Y'.
    """
    orders_not_found = Order.objects.filter(nama_batch=nama_batch, product_id__isnull=True).exclude(status_bundle='Y')
    sku_not_found_set = set(orders_not_found.values_list('sku', flat=True))
    return sorted(sku_not_found_set), len(sku_not_found_set)
