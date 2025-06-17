from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.index, name='index'),
    path('export/', views.export_stock, name='export_stock'),
    path('import/', views.import_stock, name='import_stock'),
    path('inbound/', views.inbound_list, name='inbound'),
    path('inbound/tambah/', views.inbound_tambah, name='inbound_tambah'),
    path('inbound/<int:pk>/', views.inbound_detail, name='inbound_detail'),
    path('inbound/<int:pk>/delete/', views.inbound_delete, name='inbound_delete'),
    path('inbound/import/', views.inbound_import_massal, name='inbound_import_massal'),
    path('inbound/data/', views.inbound_data, name='inbound_data'),
    path('inbound/template/', views.download_template_inbound, name='download_template_inbound'),
    path('outbound/', views.outbound_list, name='outbound'),
    path('produk-lookup/', views.produk_lookup, name='produk_lookup'),
    path('data/', views.stock_data, name='stock_data'),
]
