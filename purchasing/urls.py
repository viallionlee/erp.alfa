from django.urls import path
from . import views

app_name = 'purchasing'

urlpatterns = [
    # Purchase Order views
    path('', views.po_list, name='po_list'),
    path('api/', views.po_list_api, name='po_list_api'),
    path('dashboard/', views.po_dashboard, name='po_dashboard'),
    path('create/', views.po_create, name='po_create'),
    path('<int:pk>/', views.po_detail, name='po_detail'),
    path('<int:pk>/json/', views.po_detail_json, name='po_detail_json'),
    path('<int:pk>/edit/', views.po_edit, name='po_edit'),
    path('<int:pk>/auto-save/', views.po_auto_save, name='po_auto_save'),
    path('<int:pk>/cancel/', views.po_cancel, name='po_cancel'),
    path('<int:pk>/delete/', views.po_delete, name='po_delete'),
    path('<int:pk>/receive/', views.po_receive, name='po_receive'),
    path('<int:pk>/print/', views.po_print, name='po_print'),
    path('<int:pk>/download-pdf/', views.po_download_pdf, name='po_download_pdf'),
    path('<int:pk>/download-excel/', views.po_download_excel, name='po_download_excel'),
    path('history/', views.po_history, name='po_history_global'),
    path('<int:pk>/history/', views.po_history, name='po_history'),
    path('price-history/', views.price_history, name='price_history'),
    
    # Purchase List views (Goods Receipt)
    path('purchase/', views.purchase_list, name='purchase_list'),
    path('purchase/api/', views.purchase_list_api, name='purchase_list_api'),
    path('purchase/create/', views.purchase_create, name='purchase_create'),
    path('purchase/create/<int:po_id>/', views.purchase_create, name='purchase_create_from_po'),
    path('purchase/<int:purchase_id>/', views.purchase_detail, name='purchase_detail'),
    path('purchase/<int:purchase_id>/print/', views.purchase_print, name='purchase_print'),
    path('purchase/<int:purchase_id>/download-pdf/', views.purchase_download_pdf, name='purchase_download_pdf'),
    path('purchase/<int:purchase_id>/download-excel/', views.purchase_download_excel, name='purchase_download_excel'),
    path('purchase/<int:purchase_id>/edit/', views.purchase_edit, name='purchase_edit'),
    path('purchase/<int:purchase_id>/auto-save/', views.purchase_auto_save, name='purchase_auto_save'),
    path('purchase/<int:purchase_id>/receive/', views.purchase_receive, name='purchase_receive'),
    path('purchase/<int:purchase_id>/verify/', views.purchase_verify, name='purchase_verify'),
    path('purchase/<int:purchase_id>/delete/', views.purchase_delete, name='purchase_delete'),
    path('purchase/<int:purchase_id>/cancel/', views.purchase_cancel, name='purchase_cancel'),
    
    # API endpoints
    path('data/', views.po_data, name='po_data'),
    path('search-product/', views.search_product, name='search_product'),
    path('search-supplier/', views.search_supplier, name='search_supplier'),
    path('add-supplier/', views.add_supplier, name='add_supplier'),
    
    # Purchase Payment
    path('purchase-payment/', views.payment_views.purchase_payment_list, name='purchase_payment_list'),
    path('purchase-payment/api/', views.payment_views.purchase_payment_api, name='purchase_payment_api'),
    path('purchase-payment/<int:payment_id>/update/', views.payment_views.purchase_payment_update, name='purchase_payment_update'),
    
    # Purchase Tax Invoice
    path('purchase-taxinvoice/', views.payment_views.purchase_taxinvoice_list, name='purchase_taxinvoice_list'),
    path('purchase-taxinvoice/api/', views.payment_views.purchase_taxinvoice_api, name='purchase_taxinvoice_api'),
    path('purchase-taxinvoice/<int:invoice_id>/update/', views.payment_views.purchase_taxinvoice_update, name='purchase_taxinvoice_update'),
    path('purchase-taxinvoice/download-excel/', views.payment_views.purchase_taxinvoice_download_excel, name='purchase_taxinvoice_download_excel'),
    path('purchase-taxinvoice/download-template/', views.payment_views.purchase_taxinvoice_download_template, name='purchase_taxinvoice_download_template'),
    path('purchase-taxinvoice/upload/', views.payment_views.purchase_taxinvoice_upload, name='purchase_taxinvoice_upload'),
    
    # Bank Management
    path('banks/', views.bank_views.bank_list, name='bank_list'),
    path('banks/create/', views.bank_views.bank_create, name='bank_create'),
    path('banks/<int:bank_id>/edit/', views.bank_views.bank_edit, name='bank_edit'),
    path('banks/<int:bank_id>/delete/', views.bank_views.bank_delete, name='bank_delete'),
    path('banks/api/', views.bank_views.bank_api, name='bank_api'),
    
    # Purchase Report
    path('purchase-report/', views.report_views.purchase_report, name='purchase_report'),
    path('purchase-report/preview/', views.report_views.purchase_report_preview, name='purchase_report_preview'),
    path('purchase-report/excel/', views.report_views.purchase_report_excel, name='purchase_report_excel'),
    path('purchase-report/pdf/', views.report_views.purchase_report_pdf, name='purchase_report_pdf'),
]

