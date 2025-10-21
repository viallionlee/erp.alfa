from django.urls import path
from . import views
from . import rak_views
from . import opname_views
from . import transfer_views
from . import rakcapacity

app_name = 'inventory'

urlpatterns = [
    path('', views.index, name='index'),
    path('export/', views.export_stock, name='export_stock'),
    path('import/', views.import_stock, name='import_stock'),
    path('template-import-stock/', views.download_template_import_stock, name='template_import_stock'),
    path('inbound/', views.inbound_list, name='inbound'),
    path('inbound/tambah/', views.inbound_tambah, name='inbound_tambah'),
    path('inbound/<int:pk>/', views.inbound_detail, name='inbound_detail'),
    path('inbound/<int:pk>/edit/', views.inbound_edit, name='inbound_edit'),
    path('inbound/<int:pk>/delete/', views.inbound_delete, name='inbound_delete'),
    path('inbound/import/', views.inbound_import_massal, name='inbound_import_massal'),
    path('inbound/data/', views.inbound_data, name='inbound_data'),
    path('inbound/template/', views.download_template_inbound, name='download_template_inbound'),
    path('produk-lookup/', views.produk_lookup, name='produk_lookup'),
    path('data/', views.stock_data, name='stock_data'),
    path('add_supplier/', views.add_supplier, name='add_supplier'),
    path('search_supplier/', views.search_supplier, name='search_supplier'),
    path('daftar_supplier/', views.daftar_supplier, name='daftar_supplier'),
    path('supplier/data/', views.supplier_data, name='supplier_data'),
    path('supplier/add/', views.supplier_add, name='supplier_add'),
    path('supplier/<int:pk>/', views.supplier_detail, name='supplier_detail'),
    path('supplier/<int:pk>/edit/', views.supplier_edit, name='supplier_edit'),
    path('supplier/<int:pk>/delete/', views.supplier_delete, name='supplier_delete'),
    path('brand_list/', views.brand_list, name='brand_list'),
    path('opname/queue/', views.opnamequeue_list, name='opnamequeue_list'),
    path('opname/history/', views.opnamehistory_list, name='opnamehistory_list'),
    path('opname/input/<int:queue_id>/', views.opname_input, name='opname_input'),
    path('stock_card/', views.stock_card_view, name='stock_card'),
    path('stock_card/data/', views.stock_card_data, name='stock_card_data'),
    path('putaway/', views.putaway_list, name='putaway'),
    path('putaway/scan/', views.putaway_scan, name='putaway_scan'),
    path('putaway/scan-rak/', views.putaway_scan_rak, name='putaway_scan_rak'),
    path('putaway/scan-product/', views.putaway_scan_product, name='putaway_scan_product'),
    path('transfer-putaway/scan-product/', transfer_views.transfer_putaway_scan_product, name='transfer_putaway_scan_product'),
    path('transfer-putaway/save/', transfer_views.transfer_putaway_save, name='transfer_putaway_save'),
    path('rak/<int:rak_id>/items/', views.rak_items_data, name='rak_items_data'),
    path('putaway/list-data/', views.putaway_list_data_api, name='putaway_list_data_api'),
    path('putaway/get-product-id/', views.get_product_id_by_sku, name='get_product_id_by_sku'),
    path('putaway/save/', views.putaway_save, name='putaway_save'),
    path('putaway/history/', views.putaway_history, name='putaway_history'),
    path('putaway/history/data/', views.putaway_history_data, name='putaway_history_data'),
    
    # Slotting Putaway
    path('slotting/options/', views.slotting_options, name='slotting_options'),
    path('slotting/update/', views.update_slotting, name='update_slotting'),
    path('slotting/auto/', views.auto_slotting, name='auto_slotting'),
    path('slotting/history/', views.slotting_history, name='slotting_history'),
    path('slotting/history/data/', views.slotting_history_data, name='slotting_history_data'),
    
    # Picking Rak
    path('pickingrak/', views.picking_scan_view, name='pickingrak_scan'),
    path('api/picking/scan_rak/', views.api_scan_rak_for_picking, name='api_picking_scan_rak'),
    path('api/picking/scan_product/', views.api_scan_product_for_picking, name='api_picking_scan_product'),
    path('api/picking/save_transaction/', views.api_save_picking_transaction, name='api_picking_save_transaction'),
    
                    # Opname Rak
                path('opname-rak/', opname_views.opname_rak_list, name='opname_rak_list'),
                path('opname-rak/create/', opname_views.opname_rak_create, name='opname_rak_create'),
                path('opname-rak/partial/create/', opname_views.partial_opname_create, name='partial_opname_create'),
                path('opname-rak/<int:session_id>/work/', opname_views.opname_rak_work, name='opname_rak_work'),
                path('opname-rak/<int:session_id>/detail/', opname_views.opname_rak_detail, name='opname_rak_detail'),
                path('opname-rak/<int:session_id>/cancel/', opname_views.opname_rak_cancel, name='opname_rak_cancel'),
                path('api/product-autocomplete/', opname_views.product_autocomplete, name='product_autocomplete'),
                path('api/opname-summary/', opname_views.opname_rak_summary, name='opname_rak_summary'),
                
                # Full Opname Session
                path('full-opname/', opname_views.full_opname_list, name='full_opname_list'),
                path('full-opname/create/', opname_views.full_opname_create, name='full_opname_create'),
                path('full-opname/<int:session_id>/', opname_views.full_opname_detail, name='full_opname_detail'),
                path('full-opname/<int:session_id>/complete/', opname_views.full_opname_complete, name='full_opname_complete'),
                path('full-opname/<int:session_id>/delete/', opname_views.full_opname_delete, name='full_opname_delete'),
                path('api/full-opname-sessions/', opname_views.full_opname_sessions_api, name='full_opname_sessions_api'),
                path('api/full-opname/<int:full_session_id>/raks/', opname_views.full_opname_rak_list, name='full_opname_rak_list'),
                path('full-opname/<int:full_session_id>/rak/<int:rak_session_id>/work/', opname_views.full_opname_rak_work, name='full_opname_rak_work'),
    
    # Transfer Rak
    path('transfer-rak/', transfer_views.transfer_rak_list, name='transfer_rak_list'),
    path('transfer-rak/create/', transfer_views.transfer_rak_create, name='transfer_rak_create'),
    path('transfer-rak/<int:session_id>/work/', transfer_views.transfer_rak_work, name='transfer_rak_work'),
    path('transfer-rak/<int:session_id>/detail/', transfer_views.transfer_rak_detail, name='transfer_rak_detail'),
    path('transfer-rak/<int:session_id>/cancel/', transfer_views.transfer_rak_cancel, name='transfer_rak_cancel'),
    path('transfer-rak/<int:session_id>/putaway/', transfer_views.transfer_rak_putaway, name='transfer_rak_putaway'),
    path('transfer-rak/<int:session_id>/source-stock/', transfer_views.transfer_rak_source_stock, name='transfer_rak_source_stock'),
    path('transfer-rak/<int:session_id>/items-data/', transfer_views.transfer_rak_items_data, name='transfer_rak_items_data'),
    path('transfer-rak/<int:session_id>/finish/', transfer_views.transfer_rak_finish, name='transfer_rak_finish'),
    path('transfer-rak/<int:session_id>/statistics/', transfer_views.transfer_rak_statistics, name='transfer_rak_statistics'),
    path('transfer-rak/item/<int:item_id>/update/', transfer_views.transfer_rak_update_item, name='transfer_rak_update_item'),
    path('transfer-rak/item/<int:item_id>/delete/', transfer_views.transfer_rak_delete_item, name='transfer_rak_delete_item'),
    path('transfer-rak/<int:session_id>/add-item/', transfer_views.transfer_rak_add_item, name='transfer_rak_add_item'),
    path('transfer-rak/<int:session_id>/scan-product/', transfer_views.transfer_rak_scan_product, name='transfer_rak_scan_product'),
    path('api/transfer-summary/', transfer_views.transfer_rak_summary, name='transfer_rak_summary'),
    path('transfer-rak/putaway-history/', transfer_views.putaway_history_list, name='putaway_history_list'),
    
    # Rak Management
    path('rak-capacity/', rakcapacity.rak_capacity_view, name='rak_capacity'),
    path('rak-capacity/update/', rakcapacity.update_rak_capacity, name='update_rak_capacity'),
    path('rak-capacity/update-single/', rakcapacity.update_single_rak_capacity, name='update_single_rak_capacity'),
    path('rak-capacity/detail/', rakcapacity.rak_detail_data, name='rak_detail_data'),
    path('rak-capacity/update-dimensions/', rakcapacity.update_rak_dimensions, name='update_rak_dimensions'),
    path('rak/', rak_views.rak_list, name='rak_list'),
    path('rak/add/', rak_views.rak_add, name='rak_add'),
    path('rak/<int:rak_id>/edit/', rak_views.rak_edit, name='rak_edit'),
    path('rak/<int:rak_id>/delete/', rak_views.rak_delete, name='rak_delete'),
    path('rak/data/', rak_views.rak_data, name='rak_data'),
    path('rak/<int:rak_id>/stock/', rak_views.rak_stock_detail, name='rak_stock_detail'),
    path('rak/stock/', rak_views.rak_stock, name='rak_stock'),
    path('rak/stock/data/', rak_views.rak_stock_data, name='rak_stock_data'),
    path('rak/stock/summary/', rak_views.rak_stock_summary, name='rak_stock_summary'),
    path('api/rak/log/data/all/', rak_views.api_rak_stock_log_data_all, name='api_rak_stock_log_data_all'),
    path('api/rak/<int:rak_id>/log/data/', rak_views.api_rak_stock_log_data, name='api_rak_stock_log_data'),
    path('stock-position/', rak_views.stock_position_view, name='stock_position_view'),
    path('api/stock-position-summary/', rak_views.stock_position_summary, name='stock_position_summary'),
    path('api/stock-position-data/', rak_views.stock_position_data, name='stock_position_data'),
    
    # Product Dimensions
    path('product/<str:sku>/dimensions/', views.get_product_dimensions, name='get_product_dimensions'),
    path('product/update-dimensions/', views.update_product_dimensions, name='update_product_dimensions'),
    
    # Putaway Product Data
    path('putaway/get-product-data/', views.get_product_data_for_putaway, name='get_product_data_for_putaway'),

    # URL untuk API Inbound Mobile (Lazy Loading)
    path('api/inbound-mobile/', views.inbound_list_api, name='inbound_list_api'),
    
    # Mobile Inventory View
    path('mobile/', views.mobile_inventory, name='mobile_inventory'),
]
