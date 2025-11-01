from django.urls import path
from . import views
from .views import unique_order_filters, import_status_view, update_order_status_and_notes, update_order_item, add_order_item, delete_order_item
from .extract_sku import extract_sku, extract_bundling

# Tidak ada app_name, semua URL bersifat global.

urlpatterns = [
    # Halaman utama & form tambah
    path('', views.index, name='orders-index'),
    path('add/', views.add_order, name='add_order'),

    # Daftar Order Manual & Aksinya
    # URUTAN PENTING: URL yang lebih spesifik (seperti 'edit') harus ada SEBELUM URL yang lebih umum.
    path('list/', views.orders_list, name='orders_list'),
    path('list/<str:id_pesanan>/edit/', views.orders_listedit, name='orders_listedit'),
    path('list/<str:id_pesanan>/', views.orders_listdetail, name='orders_listdetail'),
    path('list/delete/<int:pk>/', views.orders_delete, name='orders_delete'),

    # Semua Order (dengan DataTables)
    path('all/', views.all_orders_view, name='orders_all'),
    path('all/data/', views.all_orders_data, name='all_orders_data'),
    path('all/details/', views.order_details_api, name='order_details_api'), # URL baru
    
    path('edit-order/<str:id_pesanan>/', views.edit_order_view, name='edit_order_view'),
    # NEW: URL untuk update status dan catatan via AJAX
    path('api/update-order-status-notes/', update_order_status_and_notes, name='update_order_status_and_notes'),
    # NEW: URL untuk update item order via AJAX
    path('api/update-order-item/', update_order_item, name='update_order_item'),
    # NEW: URL untuk menambah item order via AJAX
    path('api/add-order-item/', add_order_item, name='add_order_item'),
    # NEW: URL untuk menghapus item order via AJAX
    path('api/delete-order-item/', delete_order_item, name='delete_order_item'),

    # Endpoint API & Data
    path('data/', views.orders_table_data, name='orders_table_data'),  # For main orders list page
    path('datatable/', views.orders_datatable, name='orders_datatable'),
    path('download-orders/', views.download_orders, name='download_orders'),
    path('unique-filters/', unique_order_filters, name='orders_unique_filters'),

    # Endpoint Helper & AJAX
    path('add_customer/', views.add_customer, name='orders_add_customer'),
    path('search_customer/', views.search_customer, name='orders_search_customer'),
    path('extract-bundling/', extract_bundling, name='extract_bundling'),
    path('extract-sku/', extract_sku, name='extract_sku'),

    # Fitur Import
    path('import/', views.import_orders, name='import_orders'),
    path('import/history/', views.orderimport_history, name='orderimport_history'),
    path('import-status/', import_status_view, name='orders_import_status'),

    # URL lama (jika masih dipakai)
    path('detail/<str:id_pesanan>/', views.orders_detail, name='orders_detail'),
]
