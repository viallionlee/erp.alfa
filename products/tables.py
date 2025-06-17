import django_tables2 as tables
from .models import Product

class ProductTable(tables.Table):
    nama_produk = tables.Column(attrs={
        "td": {"class": "column-nama_produk"},
        "th": {"class": "column-nama_produk"},
    })
    variant_produk = tables.Column(attrs={
        "td": {"class": "column-variant_produk"},
        "th": {"class": "column-variant_produk"},
    })
    aksi = tables.TemplateColumn(
        template_code='''
        <a href="/products/edit/{{ record.id }}/" class="btn btn-sm btn-primary">Edit</a>
        <a href="/products/delete/{{ record.id }}/" class="btn btn-sm btn-danger" onclick="return confirm('Yakin hapus?')">Delete</a>
        ''',
        orderable=False, verbose_name='Aksi', exclude_from_export=True
    )
    class Meta:
        model = Product
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('id', 'sku', 'barcode', 'nama_produk', 'variant_produk', 'brand', 'rak', 'photo', 'aksi')
        per_page = 100
