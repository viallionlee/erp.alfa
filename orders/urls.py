from django.urls import path
from . import views
from .views import unique_order_filters, import_status_view
from .extract_sku import extract_sku, extract_bundling

urlpatterns = [
    path('', views.index, name='orders_index'),
    path('datatable/', views.orders_datatable, name='orders_datatable'),  # AG Grid endpoint
    path('import/', views.import_orders, name='import_orders'),
    path('import/history/', views.orderimport_history, name='orderimport_history'),
    path('unique-filters/', unique_order_filters, name='orders_unique_filters'),
    path('import-status/', import_status_view, name='orders_import_status'),
    path('add/', views.add_order, name='orders_add'),
    path('search_customer/', views.search_customer, name='orders_search_customer'),
    path('add_customer/', views.add_customer, name='orders_add_customer'),
    path('list/', views.orders_list, name='orders_list'),
    path('list/<path:id_pesanan>/', views.orders_listdetail, name='orders_listdetail'),
    path('list/<path:id_pesanan>/edit/', views.orders_listedit, name='orders_listedit'),
    path('download-orders/', views.download_orders, name='download_orders'),
    path('extract-sku/', extract_sku, name='extract_sku'),
    path('extract-bundling/', extract_bundling, name='extract_bundling'),
]
