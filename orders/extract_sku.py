from orders.models import Order
from products.models import ProductsBundling, Product
from django.db.models import Q
import logging
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db import transaction

def extract_sku():
    logging.info('extract_sku: mulai proses')
    orders = Order.objects.filter(
        status__iexact='Lunas',
        product__isnull=True
    ).filter(Q(product_id__isnull=True) | Q(product_id='') | Q(product=''))
    logging.info(f'extract_sku: total orders ditemukan = {orders.count()}')
    extracted_count = 0
    skipped_null_id = 0
    for order in orders:
        logging.debug(f'Proses order: id_pesanan={order.id_pesanan}, sku={order.sku}')
        if not order.sku or not order.id_pesanan:
            skipped_null_id += 1
            logging.warning(f'SKIP: id_pesanan/sku kosong (id_pesanan={order.id_pesanan}, sku={order.sku})')
            continue
        bundling = ProductsBundling.objects.filter(sku_bundling=order.sku).first()
        if not bundling or not bundling.sku_list:
            logging.warning(f'SKIP: Tidak ada bundling/sku_list untuk sku={order.sku}')
            continue
        sku_qty_pairs = []
        for pair in bundling.sku_list.split(','):
            if ':' in pair:
                sku_child, qty_child = pair.split(':')
                sku_child = sku_child.strip().upper()
                try:
                    qty_child = int(qty_child)
                except Exception:
                    logging.error(f'Gagal konversi qty_child: {qty_child} untuk sku_child={sku_child}, default=1')
                    qty_child = 1
                sku_qty_pairs.append((sku_child, qty_child))
        for sku_child, qty_child in sku_qty_pairs:
            product_obj = Product.objects.filter(sku__iexact=sku_child).first()
            if not product_obj:
                logging.warning(f"Extract SKU: SKU child '{sku_child}' tidak ditemukan di tabel Product untuk order {order.id_pesanan}")
            # Pastikan tidak pernah mengisi field 'id' secara manual!
            order_kwargs = dict(
                tanggal_pembuatan=order.tanggal_pembuatan,
                status=order.status,
                jenis_pesanan=order.jenis_pesanan,
                channel=order.channel,
                nama_toko=order.nama_toko,
                id_pesanan=order.id_pesanan,
                sku=sku_child,
                jumlah=order.jumlah * qty_child,
                harga_promosi=order.harga_promosi,
                catatan_pembeli=order.catatan_pembeli,
                kurir=order.kurir,
                awb_no_tracking=order.awb_no_tracking,
                metode_pengiriman=order.metode_pengiriman,
                kirim_sebelum=order.kirim_sebelum,
                order_type=order.order_type,
                nama_batch=order.nama_batch,
                jumlah_ambil=order.jumlah_ambil,
                status_ambil=order.status_ambil,
                status_order=order.status_order,
                status_cancel=order.status_cancel,
                status_retur=order.status_retur,
                status_bundle='Y',
                product=product_obj
            )
            # Hapus key 'id' jika ada (prevent error)
            if 'id' in order_kwargs:
                del order_kwargs['id']
            Order.objects.create(**order_kwargs)
            logging.info(f'Order child dibuat: id_pesanan={order.id_pesanan}, sku_child={sku_child}, qty={qty_child}')
            extracted_count += 1
    logging.info(f'extract_sku: selesai. extracted_count={extracted_count}, skipped_null_id={skipped_null_id}')
    return extracted_count, skipped_null_id

@csrf_exempt
@require_POST
def extract_bundling(request):
    extracted_count = 0
    failed = []
    try:
        with transaction.atomic():
            parents = Order.objects.filter(
                status__iexact='Lunas'
            ).exclude(
                status_bundle__iexact='Y'
            )
            for parent in parents:
                sku = (parent.sku or '').strip().upper()
                jumlah = parent.jumlah or 0
                id_pesanan = parent.id_pesanan
                status = parent.status
                # Cari product berdasarkan SKU
                product_obj = Product.objects.filter(sku__iexact=sku).first()
                if product_obj:
                    parent.product = product_obj
                    parent.save(update_fields=['product'])
                    continue
                # Cek di products_productbundling
                bundling = ProductsBundling.objects.filter(sku_bundling=sku).first()
                if not bundling or not bundling.sku_list:
                    failed.append(sku)
                    parent.status_bundle = 'N'
                    parent.save(update_fields=['status_bundle'])
                    continue
                sku_qty_pairs = []
                for pair in bundling.sku_list.split(','):
                    if ':' in pair:
                        sku_child, qty_child = pair.split(':')
                        sku_child = sku_child.strip().upper()
                        try:
                            qty_child = int(qty_child)
                        except Exception:
                            qty_child = 1
                        sku_qty_pairs.append((sku_child, qty_child))
                for sku_child, qty_child in sku_qty_pairs:
                    product_child = Product.objects.filter(sku__iexact=sku_child).first()
                    Order.objects.create(
                        sku=sku_child,
                        jumlah=jumlah * qty_child,
                        id_pesanan=id_pesanan,
                        status=parent.status,
                        tanggal_pembuatan=parent.tanggal_pembuatan,
                        jenis_pesanan=parent.jenis_pesanan,
                        channel=parent.channel,
                        nama_toko=parent.nama_toko,
                        catatan_pembeli=parent.catatan_pembeli,
                        kurir=parent.kurir,
                        awb_no_tracking=parent.awb_no_tracking,
                        metode_pengiriman=parent.metode_pengiriman,
                        kirim_sebelum=parent.kirim_sebelum,
                        status_order=parent.status_order,
                        status_cancel=parent.status_cancel,
                        status_retur=parent.status_retur,
                        order_type='3',
                        product=product_child
                    )
                    extracted_count += 1
                parent.status_bundle = 'Y'
                parent.order_type = ''
                parent.save(update_fields=['status_bundle', 'order_type'])
        return JsonResponse({'success': True, 'extracted_count': extracted_count, 'failed': failed})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
