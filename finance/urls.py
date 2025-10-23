from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    # Dashboard
    path('', views.finance_dashboard, name='dashboard'),
    
    # Account Types
    path('account-types/', views.account_type_list, name='account_type_list'),
    path('account-types/create/', views.account_type_create, name='account_type_create'),
    path('account-types/<int:account_type_id>/', views.account_type_detail, name='account_type_detail'),
    path('account-types/<int:account_type_id>/edit/', views.account_type_edit, name='account_type_edit'),
    
    # Chart of Accounts
    path('coa/', views.chart_of_accounts, name='chart_of_accounts'),  # Main URL
    path('accounts/create/', views.account_create, name='account_create'),
    path('accounts/<int:account_id>/', views.account_detail, name='account_detail'),
    path('accounts/<int:account_id>/edit/', views.account_edit, name='account_edit'),
    
    # Journal Entries
    path('journal-entries/', views.journal_entry_list, name='journal_entry_list'),
    path('journal-entries/create/', views.journal_entry_create, name='journal_entry_create'),
    path('journal-entries/<int:entry_id>/', views.journal_entry_detail, name='journal_entry_detail'),
    path('journal-entries/<int:entry_id>/edit/', views.journal_entry_edit, name='journal_entry_edit'),
    path('journal-entries/<int:entry_id>/post/', views.journal_entry_post, name='journal_entry_post'),
    path('journal-entries/<int:entry_id>/reverse/', views.journal_entry_reverse, name='journal_entry_reverse'),
    
    # Cash Flow
    path('cash-flow/', views.cash_flow_list, name='cash_flow_list'),
    path('cash-flow/create/', views.cash_flow_create, name='cash_flow_create'),
    
    # Budget
    path('budget/', views.budget_list, name='budget_list'),
    path('budget/create/', views.budget_create, name='budget_create'),
    path('budget/<int:budget_id>/', views.budget_detail, name='budget_detail'),
    path('budget/<int:budget_id>/approve/', views.budget_approve, name='budget_approve'),
    
    # Financial Reports
    path('reports/', views.financial_reports, name='financial_reports'),
    path('reports/trial-balance/', views.trial_balance, name='trial_balance'),
    path('reports/profit-loss/', views.profit_loss_statement, name='profit_loss_statement'),
    path('reports/balance-sheet/', views.balance_sheet, name='balance_sheet'),
]

