from django.urls import path
from . import views 
from . import generatebatch_views
from . import orderschecking
from . import mobile_views
from . import tables
from . import scanpacking
from . import scanshipping

from .models import BatchOrderLog
from django.views.decorators.http import require_POST
from django.db import transaction
from .models import BatchItem, BatchItemLog
import json
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Case, When, Value, IntegerField
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from .models import OrderCancelLog
from .returnlist import (
    returnlist_dashboard, create_returnlist_new, get_returnlists_for_dropdown,
    process_return_scan, scanordercancel_view, scanordercancel_scan_barcode, scanordercancel_submit_return,
    returnsession_detail, get_return_session_order_ids, get_return_session_items_api, get_return_session_history,
    scanretur_view, get_overstock_batch_data_api, submit_batch_overstock_return,
    get_batch_overstock_detail, putaway_return_session, process_putaway_return, process_putaway_return_item,
    close_return_session, update_return_session
)
from .models import ReturnSession, ReturnItem
from django.contrib.auth.decorators import login_required
# Mengimpor get_batch_order_ids_api dari views.py
from .views import get_batch_order_ids_api, download_batch_order_ids # SANGAT PENTING: Pastikan kedua fungsi ini diimpor dari views.py
from django.db.models import Q
from .models import ReturnSourceLog
from django.utils.dateformat import format as date_format

# Import dashboard views
from .dashboard import dashboard, get_dashboard_api_data


urlpatterns = [
    path('', views.index, name='fullfilment_index'),
    path('ajax/filter-options/', views.ajax_filter_options, name='ajax_filter_options'),
    path('api/idpesanan_in_batch/', views.api_idpesanan_in_batch, name='api_idpesanan_in_batch'),
    path('batchitem/<int:pk>/detail/', views.batchitem_detail_view, name='batchitem_detail_view'),
    path('batchitem/<int:pk>/update_jumlah_ambil/', views.batchitem_update_jumlah_ambil, name='batchitem_update_jumlah_ambil'),
    path('batchlist/check_duplicate/', views.batchlist_check_duplicate, name='batchlist_check_duplicate'),
    path('batchlist/list_open/', views.batchlist_list_open, name='batchlist_list_open'),
    path('batchlist/<int:batch_id>/delete/', views.batchlist_delete, name='batchlist_delete'),
    path('batchlist/<int:batch_id>/clean/', views.clean_batch_orders, name='clean_batch_orders'), # <-- TAMBAHKAN INI
    path('batchlist/<int:batch_id>/close/', views.close_batch, name='close_batch'),
    path('batchlist/<int:batch_id>/reopen/', views.reopen_batch, name='reopen_batch'),
    path('batchorder/<str:nama_batch>/', views.batchorder_view, name='batchorder_view'),
    path('batchorder/<str:nama_batch>/api/', views.batchorder_api, name='batchorder_api'), # URL baru ini
    path('batchorder/<str:nama_batch>/edit-order/<str:id_pesanan>/', views.edit_order_batch_view, name='edit_order_batch_view'), # URL baru untuk edit order di batch
    path('edit_order_batch_submit/', views.edit_order_batch_submit, name='edit_order_batch_submit'), # URL untuk submit form edit order batch
    path('erase_order_from_batch/', views.erase_order_from_batch, name='erase_order_from_batch'),
    path('batchpicking/<str:nama_batch>/', views.mobilebatchpicking, name='batchpicking'),
    path('batchpicking/<str:nama_batch>/mix_count/', views.mix_count_api, name='batchpicking_mix_count'),
    path('batchpicking/<str:nama_batch>/print_mix/', views.print_mix, name='print_mix'),
    path('batchpicking/<str:nama_batch>/sku_not_found_details/', views.batchpicking_sku_not_found_details, name='batchpicking_sku_not_found_details'),
    path('batchpicking/<str:nama_batch>/update_barcode/', views.update_barcode_picklist, name='update_barcode_picklist'),
    path('batchpicking/<str:nama_batch>/update_barcode_to_rak/', views.update_barcode_picklist_to_rak, name='update_barcode_picklist_to_rak'),
    path('batchpicking/<str:nama_batch>/update_manual/', views.update_manual, name='update_manual'),
    path('check_stock_for_orders/', views.check_stock_for_orders, name='check_stock_for_orders'),
    path('delete_row/', views.delete_row, name='delete_row'),
    path('edit_row/', views.edit_row, name='edit_row'),
    path('generatebatch/', generatebatch_views.generatebatch, name='fullfilment-generatebatch'),
    path('generatebatch/check_stock/', generatebatch_views.generatebatch_check_stock, name='fullfilment-generatebatch-check-stock'),
    path('generatebatch/data/', generatebatch_views.generatebatch_data, name='fullfilment-generatebatch-data'),
    path('generatebatch/filter_selected/', generatebatch_views.filter_selected, name='filter_selected'),
    path('generatebatch/update_batchlist/', generatebatch_views.generatebatch_update_batchlist, name='fullfilment-generatebatch-update-batchlist'),
    path('get_brand_data/', views.get_brand_data, name='get_brand_data'),
    path('get_sat_brands/', views.get_sat_brands, name='get_sat_brands'),
    path('get_sat_skus/', views.get_sat_skus, name='get_sat_skus'),
    path('orders/data/', views.orders_data, name='orders_data'),
    
    # URLS for Picking/Checking
    path('scanpicking/list/', views.scanpicking_list_view, name='scanpicking_list'),
    path('scanpicking/list/api/', views.scanpicking_list_api, name='scanpicking_list_api'),
    path('order-checking-list/', orderschecking.orders_checking_history, name='order_checking_list'),
    path('scanpicking/', orderschecking.orders_checking, name='scanpicking_index'),
    path('scanpicking/history/', orderschecking.orders_checking_history, name='scanpicking_history'),
    path('scanpicking/<str:order_id>/', orderschecking.orders_checking, name='scanpicking_detail'),
    path('scanpicking/<str:order_id>/scan-barcode/', orderschecking.orders_checking_scan_barcode, name='scanpicking_scan_barcode'),
    
    path('print_all_brands/', views.print_all_brands, name='print_all_brands'),
    path('print_all_sat_brands/', views.print_all_sat_brands, name='print_all_sat_brands'),
    path('print_brand/', views.print_brands, name='print_brand'),
    path('print_prio/<str:nama_batch>/', views.print_prio, name='print_prio'),
    path('print_sat_brand/', views.print_sat_brand, name='print_sat_brand'),
    path('print_sat_sku/', views.print_sat_sku, name='print_sat_sku'),
    path('print_selected_ready_to_pick/', views.print_selected_ready_to_pick, name='print_selected_ready_to_pick'),
    path('readytoprint/', views.ready_to_print_list, name='ready_to_print_list'),
    path('readytoprint/print/', views.ready_to_print_print, name='ready_to_print_print'),
    path('unique_brands/', views.unique_brands, name='unique_brands'),
    path('batchpicking/<path:nama_batch>/batchitem/<int:pk>/detail/', views.batchitem_detail_view, name='batchitem_detail_view'),
    path('batchpicking/<path:nama_batch>/batchitem/<int:pk>/update_jumlah_ambil/', views.batchitem_update_jumlah_ambil, name='batchitem_update_jumlah_ambil'),

    # Standardized Picking, Packing, Shipping URLs
    path('scanpacking/', scanpacking.scanpacking, name='scanpacking'),
    path('scanshipping/', scanshipping.scanshipping, name='scanshipping'),
    path('shipping-history/', scanshipping.shipping_history_view, name='shipping_history'),
    path('api/shipping-history/', scanshipping.shipping_history_api, name='shipping_history_api'),
    path('shipping-history/data/', scanshipping.shipping_history_data_api, name='shipping_history_data_api'),
    path('order-shipping-list/', scanshipping.order_shipping_list_view, name='order_shipping_list'),
    path('api/order-shipping-list/', scanshipping.order_shipping_list_api, name='order_shipping_list_api'),
    path('order-shipping-report/', scanshipping.order_shipping_report_view, name='order_shipping_report'),
    path('order-shipping-report/download-excel/', scanshipping.order_shipping_report_download_excel, name='order_shipping_report_download_excel'),
    path('order-shipping-report/download-pdf/', scanshipping.order_shipping_report_download_pdf, name='order_shipping_report_download_pdf'),
    path('order-shipping-detail/', scanshipping.order_shipping_detail_view, name='order_shipping_detail'),
    path('api/order-shipping-detail/', scanshipping.order_shipping_detail_api, name='order_shipping_detail_api'),
    path('scanpacking/list/', scanpacking.scanpacking_list_view, name='scanpacking_list'),
    path('scanpacking/list/api/', scanpacking.scanpacking_list_api, name='scanpacking_list_api'),
    path('order-packing-list/', scanpacking.order_packing_list_view, name='order_packing_list'),
    path('api/order-packing-list/', scanpacking.order_packing_list_api, name='order_packing_list_api'),
    path('scanbatch/<str:nama_batch>/', views.scanbatch, name='scanbatch'),

    path('fullfilment/batchitem/<int:pk>/upload_photo/', views.upload_batchitem_photo, name='upload_batchitem_photo'),
    path('fullfilment/batchitem/<int:pk>/delete_photo/', views.delete_batchitem_photo, name='delete_batchitem_photo'),
    path('download_batchitem_pdf/<str:nama_batch>/', views.download_batchitem_pdf, name='download_batchitem_pdf'),
    path('download_batchitem_excel/<str:nama_batch>/', views.download_batchitem_excel, name='download_batchitem_excel'),
    path('batchitemlogs/<str:nama_batch>/', views.batchitemlogs, name='batchitemlogs'),
    path('printedlist/', views.printed_list, name='printed_list'),
    path('printedlist/details/', views.get_printed_session_details, name='get_printed_session_details'),
    path('printedlist/mark-copied/', views.mark_as_copied, name='mark_as_copied'),
    path('printedlist/mark-handed-over/', views.mark_as_handed_over, name='mark_as_handed_over'),
    # Mobile batchpicking v1 URL dihapus karena sudah menggunakan URL utama batchpicking/<nama_batch>/
    path('api/order_details/<str:id_pesanan>/', views.get_order_details_api, name='get_order_details_api'),
    path('not_ready_details/<str:nama_batch>/', views.not_ready_to_pick_details, name='not_ready_to_pick_details'),
    path('unallocated_stock/<str:nama_batch>/', views.unallocated_stock_list, name='unallocated_stock_list'),
    path('remove_order_item/', views.remove_order_item_from_batch, name='remove_order_item_from_batch'),
    path('transfer_batch_pending/', views.transfer_batch_pending, name='transfer_batch_pending'),
    path('batchitem-table/', views.batchitem_table_view, name='batchitem_table_view'),
    path('cancel_order/', views.cancel_order, name='cancel_order'),
    path('transfer_order_item/', views.transfer_order_item, name='transfer_order_item'),
    path('batch-order-logs/', views.batch_order_logs_view, name='batch_order_logs'),
    path('batch-order-logs/<str:nama_batch>/', views.batch_order_logs_view, name='batch_order_logs_specific'),
    path('mobile/scanpicking/', orderschecking.orders_checking, name='mobile_scanpicking'),
    path('mobile/scanpicking/<str:order_id>/', orderschecking.orders_checking, name='mobile_scanpicking_order'),

    # New URL for Batch Order IDs Modal
    path('api/batch/<str:nama_batch>/order-ids/', get_batch_order_ids_api, name='api_batch_order_ids'),
    # NEW: URL untuk mengunduh Order IDs dalam format TXT
    path('download/batch/<str:nama_batch>/order-ids.txt', download_batch_order_ids, name='download_batch_order_ids'),

    # New URLS for Mobile Click Picking - pointing to the new view
    path('clickpicking/', views.mobile_clickpicking_view, name='mobile_clickpicking'),
    path('clickpicking/<str:order_id>/', views.mobile_clickpicking_view, name='mobile_clickpicking_order'),
    path('clickpicking/<str:order_id>/update-by-click/', orderschecking.update_by_click, name='update_by_click'),

    # URL untuk V4 API-based picker dihapus karena tidak digunakan

    # URL untuk Batch Item Logs (Riwayat Scan Lengkap)
    path('batchitemlogs/<str:nama_batch>/', views.batchitemlogs, name='batchitem_logs_view'),
    path('order-cancel-log/', views.order_cancel_log_view, name='order_cancel_log_view'),
    path('order-cancel-log/data/', views.order_cancel_log_data_api, name='order_cancel_log_data_api'),
    path('returnlist/', returnlist_dashboard, name='returnlist_dashboard'),
    path('api/create-returnlist-new/', create_returnlist_new, name='create_returnlist_new'), # URL baru
    path('api/get-returnlists/', get_returnlists_for_dropdown, name='get_returnlists_for_dropdown'), # URL baru
    path('return/session/<int:session_id>/detail/', returnsession_detail, name='returnsession_detail'),
    path('api/return/session/<int:session_id>/order-ids/', get_return_session_order_ids, name='api_return_session_order_ids'),
    path('api/return/session/<int:session_id>/items/', get_return_session_items_api, name='api_return_session_items'), # Memastikan get_return_session_items_api menggunakan path yang benar

    # URLS UNTUK PROSES RETURN BARU (LEBIH RAPI)
    # URL untuk Return Order Cancel
    path('return/session/<int:return_session_id>/ordercancel/', scanordercancel_view, name='return_ordercancel_initial_scan'), # Untuk akses awal tanpa order_id
    path('return/session/<int:return_session_id>/ordercancel/<str:order_id>/', scanordercancel_view, name='return_ordercancel_scan'), # Untuk akses dengan order_id
    path('api/return/session/<int:return_session_id>/ordercancel/<str:order_id>/scan-barcode/', scanordercancel_scan_barcode, name='api_return_ordercancel_scan_barcode'),
    path('api/return/session/<int:return_session_id>/ordercancel/<str:order_id>/submit-return/', scanordercancel_submit_return, name='api_return_ordercancel_submit_return'),

    # URL untuk Return Batch Overstock
    path('return/session/<int:return_session_id>/overstock/', scanretur_view, name='return_overstock_scan'),
    path('return/session/<int:return_session_id>/overstock/data/', get_overstock_batch_data_api, name='api_return_overstock_data'),
    path('return/session/<int:return_session_id>/batch-overstock-submit/', submit_batch_overstock_return, name='submit_batch_overstock_return'),
    path('api/return/session/<int:session_id>/history/', get_return_session_history, name='api_return_session_history'),
    path('api/batch/<int:batch_id>/overstock-detail/', get_batch_overstock_detail, name='api_batch_overstock_detail'),

    # URL untuk Putaway Return Session
    path('return/session/<int:session_id>/putaway/', putaway_return_session, name='putaway_return_session'),
    path('api/return/session/<int:session_id>/putaway/', process_putaway_return, name='process_putaway_return'),
    path('api/return/item/<int:item_id>/putaway/', process_putaway_return_item, name='process_putaway_return_item'),
    
    # URL untuk Close Return Session
    path('api/return/session/<int:session_id>/close/', close_return_session, name='close_return_session'),
    
    # URL untuk Update Return Session
    path('api/return/session/<int:session_id>/update/', update_return_session, name='update_return_session'),
    
    # Tambahkan URL untuk kompatibilitas dengan scanretur lama
    path('scanretur/<int:returnlist_id>/', scanretur_view, name='scanretur_view'),
    # Dashboard URLs
    path('dashboard/', dashboard, name='fullfilment_dashboard'),
    path('api/dashboard/', get_dashboard_api_data, name='dashboard_api'),
    
    
    # URL untuk scan return cancelled order
    path('scan_return_cancelled_order/<str:nama_batch>/', views.scan_return_cancelled_order_view, name='scan_return_cancelled_order'),
    path('api/scan_return_cancelled_order/<str:nama_batch>/scan/', views.scan_return_cancelled_order_scan, name='scan_return_cancelled_order_scan'),
    
    # URL untuk scan hapus order printed
    path('api/scan_hapus_order_printed/<str:nama_batch>/scan/', views.scan_hapus_order_printed, name='scan_hapus_order_printed'),
]
