from django.urls import path
from . import views 

app_name = 'products'

urlpatterns = [
    path('', views.index, name='index'),
    path('aggrid-data/', views.aggrid_data, name='products_aggrid_data'),
    # path('tabulator/', views.tabulator_view, name='products_tabulator'),
    path('import/', views.import_products, name='products_import'),
    path('export/', views.export_products, name='products_export'),
    path('delete/<int:product_id>/', views.delete_product, name='products_delete'),
    path('edit/<int:product_id>/', views.edit_product, name='products_edit'),
    path('update/<int:product_id>/', views.update_product, name='products_update'),
    path('import-history/delete/<int:history_id>/', views.delete_import_history, name='delete_import_history'),
    path('import-history/', views.import_history_view, name='import_history'),
    path('data/', views.products_data, name='products_data'),
    path('import-progress/', views.import_progress, name='import_progress'),
    path('viewall/', views.viewall, name='products_viewall'),
    path('autocomplete/', views.products_autocomplete, name='products_autocomplete'),
    path('unique_brands/', views.unique_brands, name='unique_brands'),
    path('unique_raks/', views.unique_raks, name='unique_raks'),
    path('sku_bundling/', views.sku_bundling_list, name='sku_bundling_list'),
    path('sku_bundling/add/', views.sku_bundling_add, name='sku_bundling_add'),
    path('sku_bundling/edit/<int:pk>/', views.sku_bundling_edit, name='sku_bundling_edit'),
    path('sku_bundling/delete/<int:pk>/', views.sku_bundling_delete, name='sku_bundling_delete'),
    path('download-template/', views.download_template, name='download_template'),
]
