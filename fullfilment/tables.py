import django_tables2 as tables
from .models import BatchItem
from products.models import Product
from django.utils.html import format_html
from orders.models import Order

class BatchItemTable(tables.Table):
    sku = tables.Column(verbose_name='SKU', accessor='product.sku', orderable=True)
    barcode = tables.Column(verbose_name='Barcode', accessor='product.barcode', orderable=True)
    nama_produk = tables.Column(verbose_name='Nama Produk', accessor='product.nama_produk', orderable=True)
    variant_produk = tables.Column(verbose_name='Variant Produk', accessor='product.variant_produk', orderable=True)
    brand = tables.Column(verbose_name='Brand', accessor='product.brand', orderable=True)
    rack = tables.Column(verbose_name='Rack', accessor='product.rak', orderable=True)
    jumlah = tables.Column(verbose_name='Jumlah', orderable=True)
    jumlah_ambil = tables.Column(verbose_name='Jumlah Ambil', orderable=True)
    status_ambil = tables.Column(verbose_name='Status Ambil', orderable=True)

    class Meta:
        model = BatchItem
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'rack', 'jumlah', 'jumlah_ambil', 'status_ambil')
        attrs = {'class': 'table table-hover align-middle'}

class ReadyToPrintTable(tables.Table):
    select = tables.CheckBoxColumn(accessor='pk', attrs={"th__input": {"id": "selectAll"}}, orderable=False, verbose_name='')
    id = tables.Column(verbose_name='ID')
    batchlist_id = tables.Column(verbose_name='Batchlist ID')
    id_pesanan = tables.Column(verbose_name='ID Pesanan')
    status_print = tables.Column(verbose_name='Status Print')
    printed_at = tables.Column(verbose_name='Printed At')

    class Meta:
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('select', 'id', 'batchlist_id', 'id_pesanan', 'status_print', 'printed_at')
        attrs = {'class': 'table table-hover align-middle'}

class GenerateBatchOrderTable(tables.Table):
    check_stock = tables.Column(empty_values=(), verbose_name='Check Stock', orderable=False)
    status_stock = tables.Column(verbose_name='Status Stock')
    product_id = tables.Column(accessor='product.id', verbose_name='Product ID')
    tanggal_pembuatan = tables.Column(verbose_name='Tanggal Pembuatan')
    channel = tables.Column(verbose_name='Channel')
    nama_toko = tables.Column(verbose_name='Nama Toko')
    id_pesanan = tables.Column(verbose_name='ID Pesanan')
    sku = tables.Column(verbose_name='SKU')
    nama_produk = tables.Column(accessor='product.nama_produk', verbose_name='Nama Produk')
    variant_produk = tables.Column(accessor='product.variant_produk', verbose_name='Variant Produk')
    brand = tables.Column(accessor='product.brand', verbose_name='Brand')
    jumlah = tables.Column(verbose_name='Jumlah')
    kurir = tables.Column(verbose_name='Kurir')
    metode_pengiriman = tables.Column(verbose_name='Metode Pengiriman')
    kirim_sebelum = tables.Column(verbose_name='Kirim Sebelum')
    order_type = tables.Column(verbose_name='Order Type')
    nama_batch = tables.Column(verbose_name='Batch')

    def render_check_stock(self, record):
        # You can customize the display here, e.g. a button or icon
        return ''

    class Meta:
        model = Order
        template_name = 'django_tables2/bootstrap4.html'
        fields = (
            'check_stock', 'status_stock', 'product_id', 'tanggal_pembuatan', 'channel', 'nama_toko',
            'id_pesanan', 'sku', 'nama_produk', 'variant_produk', 'brand', 'jumlah',
            'kurir', 'metode_pengiriman', 'kirim_sebelum', 'order_type', 'nama_batch'
        )
        attrs = {'class': 'table table-hover align-middle'}
