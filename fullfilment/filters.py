import django_filters
from orders.models import Order
from django.db.models import Q
from django import forms

def filtered_order_queryset():
    return Order.objects.filter(status__iexact='Lunas').filter(Q(nama_batch__isnull=True) | Q(nama_batch=''))

# --- FUNGSI BARU UNTUK SORTING KURIR PRIORITAS ---
def sort_courier_priority(courier_tuple):
    """
    Mengurutkan kurir dengan prioritas: Instant/Gojek/Grab/Same Day di atas, sisanya di bawah.
    """
    courier_name = (courier_tuple[0] or '').lower()
    
    # Kata kunci prioritas (case insensitive)
    priority_keywords = ['instant', 'gojek', 'grab', 'same day', 'sameday']
    
    # Cek apakah kurir mengandung kata kunci prioritas
    for keyword in priority_keywords:
        if keyword in courier_name:
            return (0, courier_name)  # Prioritas tinggi (0 = paling atas)
    
    return (1, courier_name)  # Prioritas rendah (1 = di bawah)

class GenerateBatchOrderFilter(django_filters.FilterSet):
    nama_toko = django_filters.MultipleChoiceFilter(
        choices=lambda: sorted(filtered_order_queryset().values_list('nama_toko', 'nama_toko').distinct(), key=lambda x: (x[0] or '').lower()),
        label='Nama Toko',
        conjoined=False,
        widget=forms.SelectMultiple(attrs={'size': '8'})
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
        conjoined=False,
        widget=forms.SelectMultiple(attrs={'size': '8'})
    )
    order_type = django_filters.MultipleChoiceFilter(
        choices=lambda: sorted(filtered_order_queryset().values_list('order_type', 'order_type').distinct(), key=lambda x: (x[0] or '')),
        label='Order Type',
        conjoined=False,
        widget=forms.SelectMultiple(attrs={'size': '8'})
    )
    tanggal_pembuatan = django_filters.DateFilter(field_name='tanggal_pembuatan', lookup_expr='exact', label='Tanggal Pembuatan (YYYY-MM-DD)')
    kurir = django_filters.MultipleChoiceFilter(
        # PERBAIKAN DI BAGIAN CHOICES
        choices=lambda: sorted(filtered_order_queryset().values_list('kurir', 'kurir').distinct(), key=sort_courier_priority),  # 3. Gunakan fungsi sorting kustom
        label='Kurir',
        conjoined=False,
        widget=forms.SelectMultiple(attrs={'size': '8'})
    )
    kirim_sebelum = django_filters.MultipleChoiceFilter(
        choices=lambda: sorted(filtered_order_queryset().exclude(kirim_sebelum__isnull=True).exclude(kirim_sebelum='').values_list('kirim_sebelum', 'kirim_sebelum').distinct(), key=lambda x: (x[0] or '')),
        label='Kirim Sebelum',
        conjoined=False,
        widget=forms.SelectMultiple(attrs={'size': '8'})
    )
    id_pesanan = django_filters.MultipleChoiceFilter(
        choices=lambda: sorted(filtered_order_queryset().order_by('-id').values_list('id_pesanan', 'id_pesanan').distinct(), key=lambda x: (x[0] or '').lower()),
        label='ID Pesanan',
        conjoined=False,
        widget=forms.SelectMultiple(attrs={'size': '8'})
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