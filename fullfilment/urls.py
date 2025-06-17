from django.urls import path
from . import views
from . import viewdemo
from . import generatebatch_views
from . import orderschecking
from . import mobile_views

urlpatterns = [
    path('', views.index, name='fullfilment_index'),
    path('unique_brands/', views.unique_brands, name='unique_brands'),
    path('check_stock_for_orders/', views.check_stock_for_orders, name='check_stock_for_orders'),
    path('edit_row/', views.edit_row, name='edit_row'),
    path('delete_row/', views.delete_row, name='delete_row'),
    path('orders/data/', views.orders_data, name='orders_data'), 
    path('batchlist/check_duplicate/', views.batchlist_check_duplicate, name='batchlist_check_duplicate'),
    path('batchlist/list_open/', views.batchlist_list_open, name='batchlist_list_open'),
    path('batchpicking/<str:nama_batch>/', views.batchpicking, name='batchpicking'),
    path('batchpicking/<str:nama_batch>/update_barcode/', views.update_barcode_picklist, name='update_barcode_picklist'),
    path('batchpicking/<str:nama_batch>/update_manual/', views.update_manual, name='update_manual'),
    path('readytoprint/', views.ready_to_print_list, name='ready_to_print_list'),
    path('readytoprint/print/', views.ready_to_print_print, name='ready_to_print_print'),
    path('batchpickingdemo/<str:nama_batch>/', viewdemo.batchpickingdemo, name='batchpickingdemo'),
    path('get_sat_brands/', views.get_sat_brands, name='get_sat_brands'),
    path('print_sat_brand/', views.print_sat_brand, name='print_sat_brand'),
    path('print_all_sat_brands/', views.print_all_sat_brands, name='print_all_sat_brands'),
    path('get_brand_data/', views.get_brand_data, name='get_brand_data'),
    path('print_all_brands/', views.print_all_brands, name='print_all_brands'),
    path('print_brand/', views.print_brand, name='print_brand'),
    path('batchpicking/<str:nama_batch>/print_mix/', views.print_mix, name='print_mix'), 
    path('batchitem/<int:pk>/detail/', views.batchitem_detail_view, name='batchitem_detail_view'),
    path('batchlist/<int:batch_id>/delete/', views.batchlist_delete, name='batchlist_delete'),
    path('generatebatch/', generatebatch_views.generatebatch, name='fullfilment-generatebatch'),
    path('generatebatch/data/', generatebatch_views.generatebatch_data, name='fullfilment-generatebatch-data'),
    path('generatebatch/check_stock/', generatebatch_views.generatebatch_check_stock, name='fullfilment-generatebatch-check-stock'),
    path('generatebatch/update_batchlist/', generatebatch_views.generatebatch_update_batchlist, name='fullfilment-generatebatch-update-batchlist'),
    path('orders_checking/<str:nama_batch>/', orderschecking.orders_checking, name='orders_checking'),
    path('orders_checking/<str:nama_batch>/scan-barcode/', orderschecking.orders_checking_scan_barcode, name='orders_checking_scan_barcode'),
    path('batchpicking/<str:nama_batch>/sku_not_found_details/', views.batchpicking_sku_not_found_details, name='batchpicking_sku_not_found_details'),
    path('batchpicking/<str:nama_batch>/mix_count/', views.mix_count_api, name='batchpicking_mix_count'),
    path('api/idpesanan_in_batch/', views.api_idpesanan_in_batch, name='api_idpesanan_in_batch'),
    path('mobile/', mobile_views.mobile_batch_index, name='mobile_batch_index'),
    path('batchitem/<int:pk>/update_jumlah_ambil/', views.batchitem_update_jumlah_ambil, name='batchitem_update_jumlah_ambil'),
]
