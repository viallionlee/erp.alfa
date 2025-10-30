from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.index, name='index'),
    path('add/', views.add_product, name='add_product'),
    path('import/', views.import_products, name='products_import'),
    path('export/', views.export_products, name='products_export'),
    path('delete/<int:product_id>/', views.delete_product, name='delete_product'),
    path('edit/<int:product_id>/', views.edit_product, name='edit_product'),
    path('deactivate/<int:product_id>/', views.deactivate_product, name='deactivate_product'),
    path('update/<int:product_id>/', views.update_product, name='update_product'),
    path('import-history/delete/<int:history_id>/', views.delete_import_history, name='delete_import_history'),
    path('import-history/', views.import_history_view, name='import_history'),
    path('data/', views.products_data, name='products_data'),
    path('import-progress/', views.import_progress, name='import_progress'),
    path('autocomplete/', views.products_autocomplete, name='products_autocomplete'),
    path('unique_brands/', views.unique_brands, name='unique_brands'),
    path('unique_raks/', views.unique_raks, name='unique_raks'),
    path('sku_bundling/', views.sku_bundling_list, name='sku_bundling_list'),
    path('sku_bundling/add/', views.sku_bundling_add, name='sku_bundling_add'),
    path('sku_bundling/edit/<int:pk>/', views.sku_bundling_edit, name='sku_bundling_edit'),
    path('sku_bundling/delete/<int:pk>/', views.sku_bundling_delete, name='sku_bundling_delete'),
    path('sku_bundling/import/', views.import_sku_bundling, name='import_sku_bundling'),
    path('sku_bundling/download-template/', views.download_sku_bundling_template, name='download_sku_bundling_template'),
    path('download-template/', views.download_template, name='download_template'),
    path('extrabarcode/', views.extrabarcode_view, name='extrabarcode_view'),
    path('extrabarcode/add/', views.extrabarcode_add_view, name='extrabarcode_add'),
    path('extrabarcode/delete/<int:barcode_id>/', views.delete_extra_barcode, name='delete_extra_barcode'),
    path('extrabarcode/data/', views.extrabarcode_data, name='extrabarcode_data'),
    
    # URL API baru untuk Extra Barcode
    path('api/extra-barcodes/<int:product_id>/', views.get_product_extra_barcodes, name='api_get_extra_barcodes'),
    path('api/add-extra-barcode/', views.add_extra_barcode, name='api_add_extra_barcode'),
    path('api/delete-extra-barcode/<int:barcode_id>/', views.api_delete_extra_barcode, name='api_delete_extra_barcode'),
    
    # URL API untuk Photo Upload
    path('api/upload-photo/<int:product_id>/', views.upload_product_photo, name='api_upload_product_photo'),
    
    path('add_history/', views.add_history_view, name='add_history'),

    # Dashboard Stok Produk per Rak
    
    path('api/product-stock-by-rak/', views.api_get_product_rak_stock, name='api_get_product_rak_stock'), # URL API
    
    # Product Edit Logs
    path('edit-logs/', views.product_edit_logs, name='product_edit_logs'),
    path('edit-logs/<int:product_id>/', views.product_edit_logs, name='product_edit_logs_detail'),
    
    # Product Dimension
    path('dimension/', views.product_dimension_view, name='product_dimension'),
    path('dimension/data/', views.product_dimension_data, name='product_dimension_data'),
    path('update-dimensions/', views.update_product_dimensions, name='update_product_dimensions'),
    
    # Price History
    path('price-history/', views.price_history_all, name='price_history_all'),
    path('price-history/api/', views.price_history_api, name='price_history_api'),
]
