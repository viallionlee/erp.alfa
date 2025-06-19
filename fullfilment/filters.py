import django_filters
from orders.models import Order
from django.db.models import Q

def filtered_order_queryset():
    return Order.objects.filter(status__iexact='Lunas').filter(Q(nama_batch__isnull=True) | Q(nama_batch=''))

class GenerateBatchOrderFilter(django_filters.FilterSet):
    nama_toko = django_filters.MultipleChoiceFilter(
        choices=lambda: sorted(filtered_order_queryset().values_list('nama_toko', 'nama_toko').distinct(), key=lambda x: (x[0] or '').lower()),
        label='Nama Toko',
        conjoined=False
    )
    brand = django_filters.MultipleChoiceFilter(
        field_name='product__brand',
        choices=lambda: sorted(
            filtered_order_queryset().filter(order_type__in=['1', '4'])
                .exclude(product__brand__isnull=True)
                .exclude(product__brand='')
                .values_list('product__brand', 'product__brand').distinct(),
            key=lambda x: (x[0] or '').lower()
        ),
        label='Brand',
        conjoined=False
    )
    order_type = django_filters.MultipleChoiceFilter(
        choices=lambda: sorted(filtered_order_queryset().values_list('order_type', 'order_type').distinct(), key=lambda x: (x[0] or '')),
        label='Order Type',
        conjoined=False
    )
    tanggal_pembuatan = django_filters.DateFilter(field_name='tanggal_pembuatan', lookup_expr='exact', label='Tanggal Pembuatan (YYYY-MM-DD)')
    kurir = django_filters.MultipleChoiceFilter(
        choices=lambda: sorted(filtered_order_queryset().exclude(kurir__isnull=True).exclude(kurir='').values_list('kurir', 'kurir').distinct(), key=lambda x: (x[0] or '').lower()),
        label='Kurir',
        conjoined=False
    )
    kirim_sebelum = django_filters.MultipleChoiceFilter(
        choices=lambda: sorted(filtered_order_queryset().exclude(kirim_sebelum__isnull=True).exclude(kirim_sebelum='').values_list('kirim_sebelum', 'kirim_sebelum').distinct(), key=lambda x: (x[0] or '')),
        label='Kirim Sebelum',
        conjoined=False
    )
    id_pesanan = django_filters.MultipleChoiceFilter(
        choices=lambda: sorted(filtered_order_queryset().exclude(id_pesanan__isnull=True).exclude(id_pesanan='').values_list('id_pesanan', 'id_pesanan').distinct(), key=lambda x: (x[0] or '')),
        label='ID Pesanan',
        conjoined=False
    )

    def filter_queryset(self, queryset):
        qs = super().filter_queryset(queryset)
        brand_val = self.data.getlist('brand') if hasattr(self.data, 'getlist') else self.data.get('brand')
        if brand_val:
            qs = qs.filter(order_type__in=['1', '4'])
        return qs

    class Meta:
        model = Order
        fields = ['nama_toko', 'brand', 'order_type', 'tanggal_pembuatan', 'kurir', 'kirim_sebelum', 'id_pesanan']
