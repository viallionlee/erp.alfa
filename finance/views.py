from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Q, F, Count
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from datetime import datetime, timedelta
from decimal import Decimal
import json

from .models import (
    AccountType, Account, JournalEntry, JournalEntryItem,
    CashFlow, Budget, FinancialReport, FinanceSettings
)
# from .forms import AccountTypeForm, AccountForm, JournalEntryForm


# ==================== DASHBOARD ====================

@login_required
def finance_dashboard(request):
    """Dashboard Keuangan - Ringkasan keuangan perusahaan"""
    
    # Get current month
    today = timezone.now().date()
    month_start = today.replace(day=1)
    
    # Calculate balances from journal entries instead of using current_balance property
    from django.db.models import Sum, Q
    
    # Total Assets (calculate from journal entries)
    asset_accounts = Account.objects.filter(account_type__type='ASSET', is_active=True)
    total_assets = Decimal('0')
    for account in asset_accounts:
        total_assets += account.current_balance
    
    # Total Liabilities
    liability_accounts = Account.objects.filter(account_type__type='LIABILITY', is_active=True)
    total_liabilities = Decimal('0')
    for account in liability_accounts:
        total_liabilities += account.current_balance
    
    # Total Equity
    equity_accounts = Account.objects.filter(account_type__type='EQUITY', is_active=True)
    total_equity = Decimal('0')
    for account in equity_accounts:
        total_equity += account.current_balance
    
    # Revenue this month
    revenue_accounts = Account.objects.filter(account_type__type='REVENUE', is_active=True)
    revenue_this_month = Decimal('0')
    for account in revenue_accounts:
        revenue_this_month += account.current_balance
    
    # Expense this month
    expense_accounts = Account.objects.filter(account_type__type='EXPENSE', is_active=True)
    expense_this_month = Decimal('0')
    for account in expense_accounts:
        expense_this_month += account.current_balance
    
    # Net Income
    net_income = revenue_this_month - expense_this_month
    
    # Cash Flow this month
    cash_inflow = CashFlow.objects.filter(
        transaction_date__gte=month_start,
        transaction_date__lte=today,
        flow_type='INFLOW'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    cash_outflow = CashFlow.objects.filter(
        transaction_date__gte=month_start,
        transaction_date__lte=today,
        flow_type='OUTFLOW'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    net_cash_flow = cash_inflow - cash_outflow
    
    # Recent Journal Entries
    recent_entries = JournalEntry.objects.filter(
        status='posted'
    ).order_by('-entry_date', '-id')[:10]
    
    # Budget Status
    active_budgets = Budget.objects.filter(
        status='active',
        period_start__lte=today,
        period_end__gte=today
    )
    
    budget_data = []
    for budget in active_budgets:
        budget_data.append({
            'name': budget.name,
            'account': budget.account.code,
            'budget': budget.budget_amount,
            'actual': budget.actual_amount,
            'utilization': budget.utilization_percentage,
            'variance': budget.variance
        })
    
    # Top Expenses this month
    top_expenses = Account.objects.filter(
        account_type__type='EXPENSE',
        is_active=True
    ).annotate(
        expense_amount=Sum('journal_items__debit', filter=Q(
            journal_items__journal_entry__status='posted',
            journal_items__journal_entry__entry_date__gte=month_start
        ))
    ).filter(expense_amount__gt=0).order_by('-expense_amount')[:5]
    
    context = {
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'total_equity': total_equity,
        'revenue_this_month': revenue_this_month,
        'expense_this_month': expense_this_month,
        'net_income': net_income,
        'cash_inflow': cash_inflow,
        'cash_outflow': cash_outflow,
        'net_cash_flow': net_cash_flow,
        'recent_entries': recent_entries,
        'active_budgets': active_budgets,
        'budget_data': budget_data,
        'top_expenses': top_expenses,
        'hide_navbar': False,  # Ensure navbar is visible
    }
    
    return render(request, 'finance/dashboard.html', context)


# ==================== CHART OF ACCOUNTS ====================

@login_required
def chart_of_accounts(request):
    """Chart of Accounts - Daftar Akun dengan fitur lengkap"""
    
    # Get filters
    type_filter = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    # Get account types with their accounts
    account_types = AccountType.objects.filter(is_active=True).order_by('code')
    
    accounts_by_type = {}
    for acc_type in account_types:
        accounts = Account.objects.filter(
            account_type=acc_type
        ).order_by('code')
        
        # Apply filters
        if type_filter and str(acc_type.id) != type_filter:
            continue
            
        if status_filter:
            if status_filter == 'active':
                accounts = accounts.filter(is_active=True)
            elif status_filter == 'inactive':
                accounts = accounts.filter(is_active=False)
        
        if search:
            accounts = accounts.filter(
                Q(code__icontains=search) | 
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        if accounts.exists():
            accounts_by_type[acc_type] = accounts
    
    # Calculate summary statistics
    all_accounts = Account.objects.all()
    total_accounts = all_accounts.count()
    active_accounts = all_accounts.filter(is_active=True).count()
    
    # Calculate total balance
    total_balance = 0
    for account in all_accounts:
        if account.balance_type == 'DEBIT':
            total_balance += float(account.current_balance or 0)
        else:
            total_balance -= float(account.current_balance or 0)
    
    context = {
        'accounts_by_type': accounts_by_type,
        'account_types': account_types,
        'total_accounts': total_accounts,
        'active_accounts': active_accounts,
        'total_balance': total_balance,
    }
    
    return render(request, 'finance/chart_of_accounts.html', context)


@login_required
def account_detail(request, account_id):
    """Account Detail - Detail akun dengan history"""
    
    account = get_object_or_404(Account, id=account_id)
    
    # Get journal entries for this account
    journal_items = JournalEntryItem.objects.filter(
        account=account,
        journal_entry__status='posted'
    ).select_related('journal_entry').order_by('-journal_entry__entry_date', '-id')
    
    # Paginate
    paginator = Paginator(journal_items, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get date range filter
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if date_from and date_to:
        journal_items = journal_items.filter(
            journal_entry__entry_date__gte=date_from,
            journal_entry__entry_date__lte=date_to
        )
    
    context = {
        'account': account,
        'page_obj': page_obj,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'finance/account_detail.html', context)


# ==================== JOURNAL ENTRIES ====================

@login_required
def journal_entry_list(request):
    """Journal Entry List"""
    
    entries = JournalEntry.objects.all().order_by('-entry_date', '-id')
    
    # Filters
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('search', '')
    
    if status_filter:
        entries = entries.filter(status=status_filter)
    
    if date_from:
        entries = entries.filter(entry_date__gte=date_from)
    
    if date_to:
        entries = entries.filter(entry_date__lte=date_to)
    
    if search:
        entries = entries.filter(
            Q(entry_number__icontains=search) |
            Q(description__icontains=search) |
            Q(reference__icontains=search)
        )
    
    # Paginate
    paginator = Paginator(entries, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search': search,
    }
    
    return render(request, 'finance/journal_entry_list.html', context)


@login_required
def journal_entry_create(request):
    """Create Journal Entry"""
    
    if request.method == 'POST':
        try:
            # Create journal entry
            entry = JournalEntry.objects.create(
                entry_date=request.POST.get('entry_date'),
                reference=request.POST.get('reference', ''),
                description=request.POST.get('description'),
                created_by=request.user,
                status='draft'
            )
            
            # Process items
            accounts = request.POST.getlist('account')
            debits = request.POST.getlist('debit')
            credits = request.POST.getlist('credit')
            descriptions = request.POST.getlist('item_description')
            
            for i in range(len(accounts)):
                if accounts[i]:
                    JournalEntryItem.objects.create(
                        journal_entry=entry,
                        account_id=accounts[i],
                        debit=Decimal(debits[i] or 0),
                        credit=Decimal(credits[i] or 0),
                        description=descriptions[i]
                    )
            
            messages.success(request, f'Journal Entry {entry.entry_number} berhasil dibuat')
            return redirect('finance:journal_entry_detail', entry_id=entry.id)
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    accounts = Account.objects.filter(is_active=True).order_by('code')
    
    context = {
        'accounts': accounts,
    }
    
    return render(request, 'finance/journal_entry_create.html', context)


@login_required
def journal_entry_detail(request, entry_id):
    """Journal Entry Detail"""
    
    entry = get_object_or_404(JournalEntry, id=entry_id)
    
    # Calculate difference for template
    difference = entry.total_debit - entry.total_credit
    
    context = {
        'entry': entry,
        'difference': difference,
    }
    
    return render(request, 'finance/journal_entry_detail.html', context)


@login_required
@require_http_methods(["POST"])
def journal_entry_post(request, entry_id):
    """Post Journal Entry"""
    
    entry = get_object_or_404(JournalEntry, id=entry_id)
    
    try:
        entry.post(request.user)
        messages.success(request, f'Journal Entry {entry.entry_number} berhasil di-post')
    except ValueError as e:
        messages.error(request, str(e))
    
    return redirect('finance:journal_entry_detail', entry_id=entry.id)


@login_required
@require_http_methods(["POST"])
def journal_entry_reverse(request, entry_id):
    """Reverse Journal Entry"""
    
    entry = get_object_or_404(JournalEntry, id=entry_id)
    
    try:
        reversal = entry.reverse(request.user)
        messages.success(request, f'Journal Entry {entry.entry_number} berhasil di-reverse. Reversal: {reversal.entry_number}')
    except ValueError as e:
        messages.error(request, str(e))
    
    return redirect('finance:journal_entry_detail', entry_id=entry.id)


# ==================== CASH FLOW ====================

@login_required
def cash_flow_list(request):
    """Cash Flow List"""
    
    cash_flows = CashFlow.objects.all().order_by('-transaction_date', '-id')
    
    # Filters
    category_filter = request.GET.get('category', '')
    flow_type_filter = request.GET.get('flow_type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if category_filter:
        cash_flows = cash_flows.filter(category=category_filter)
    
    if flow_type_filter:
        cash_flows = cash_flows.filter(flow_type=flow_type_filter)
    
    if date_from:
        cash_flows = cash_flows.filter(transaction_date__gte=date_from)
    
    if date_to:
        cash_flows = cash_flows.filter(transaction_date__lte=date_to)
    
    # Paginate
    paginator = Paginator(cash_flows, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Summary
    total_inflow = cash_flows.filter(flow_type='INFLOW').aggregate(total=Sum('amount'))['total'] or Decimal('0')
    total_outflow = cash_flows.filter(flow_type='OUTFLOW').aggregate(total=Sum('amount'))['total'] or Decimal('0')
    net_flow = total_inflow - total_outflow
    
    context = {
        'page_obj': page_obj,
        'category_filter': category_filter,
        'flow_type_filter': flow_type_filter,
        'date_from': date_from,
        'date_to': date_to,
        'total_inflow': total_inflow,
        'total_outflow': total_outflow,
        'net_flow': net_flow,
    }
    
    return render(request, 'finance/cash_flow_list.html', context)


@login_required
def cash_flow_create(request):
    """Create Cash Flow"""
    
    if request.method == 'POST':
        try:
            CashFlow.objects.create(
                transaction_date=request.POST.get('transaction_date'),
                category=request.POST.get('category'),
                flow_type=request.POST.get('flow_type'),
                account_id=request.POST.get('account'),
                amount=Decimal(request.POST.get('amount')),
                description=request.POST.get('description'),
                reference=request.POST.get('reference', ''),
                created_by=request.user
            )
            
            messages.success(request, 'Cash Flow berhasil ditambahkan')
            return redirect('finance:cash_flow_list')
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    accounts = Account.objects.filter(
        account_type__type__in=['ASSET', 'LIABILITY'],
        is_active=True
    ).order_by('code')
    
    context = {
        'accounts': accounts,
    }
    
    return render(request, 'finance/cash_flow_create.html', context)


# ==================== BUDGET ====================

@login_required
def budget_list(request):
    """Budget List"""
    
    budgets = Budget.objects.all().order_by('-period_start', '-id')
    
    # Filters
    status_filter = request.GET.get('status', '')
    period_type_filter = request.GET.get('period_type', '')
    
    if status_filter:
        budgets = budgets.filter(status=status_filter)
    
    if period_type_filter:
        budgets = budgets.filter(period_type=period_type_filter)
    
    # Paginate
    paginator = Paginator(budgets, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'period_type_filter': period_type_filter,
    }
    
    return render(request, 'finance/budget_list.html', context)


@login_required
def budget_create(request):
    """Create Budget"""
    
    if request.method == 'POST':
        try:
            Budget.objects.create(
                name=request.POST.get('name'),
                description=request.POST.get('description', ''),
                account_id=request.POST.get('account'),
                period_type=request.POST.get('period_type'),
                period_start=request.POST.get('period_start'),
                period_end=request.POST.get('period_end'),
                budget_amount=Decimal(request.POST.get('budget_amount')),
                status='draft',
                created_by=request.user
            )
            
            messages.success(request, 'Budget berhasil dibuat')
            return redirect('finance:budget_list')
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    accounts = Account.objects.filter(is_active=True).order_by('code')
    
    context = {
        'accounts': accounts,
    }
    
    return render(request, 'finance/budget_create.html', context)


@login_required
def budget_detail(request, budget_id):
    """Budget Detail"""
    
    budget = get_object_or_404(Budget, id=budget_id)
    
    context = {
        'budget': budget,
    }
    
    return render(request, 'finance/budget_detail.html', context)


@login_required
@require_http_methods(["POST"])
def budget_approve(request, budget_id):
    """Approve Budget"""
    
    budget = get_object_or_404(Budget, id=budget_id)
    
    budget.status = 'approved'
    budget.approved_by = request.user
    budget.approved_at = timezone.now()
    budget.save()
    
    messages.success(request, f'Budget {budget.name} berhasil di-approve')
    return redirect('finance:budget_detail', budget_id=budget.id)


# ==================== FINANCIAL REPORTS ====================

@login_required
def financial_reports(request):
    """Financial Reports List"""
    
    reports = FinancialReport.objects.all().order_by('-period_end', '-id')
    
    # Paginate
    paginator = Paginator(reports, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    
    return render(request, 'finance/financial_reports.html', context)


@login_required
def trial_balance(request):
    """Trial Balance Report"""
    
    # Get date range
    date_to = request.GET.get('date_to', timezone.now().date().isoformat())
    
    # Get all active accounts
    accounts = Account.objects.filter(is_active=True).order_by('code')
    
    trial_balance_data = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')
    
    for account in accounts:
        # Get balance up to date_to
        debit_total = JournalEntryItem.objects.filter(
            account=account,
            journal_entry__status='posted',
            journal_entry__entry_date__lte=date_to,
            debit__gt=0
        ).aggregate(total=Sum('debit'))['total'] or Decimal('0')
        
        credit_total = JournalEntryItem.objects.filter(
            account=account,
            journal_entry__status='posted',
            journal_entry__entry_date__lte=date_to,
            credit__gt=0
        ).aggregate(total=Sum('credit'))['total'] or Decimal('0')
        
        # Calculate balance
        if account.balance_type == 'DEBIT':
            balance = debit_total - credit_total
        else:
            balance = credit_total - debit_total
        
        if balance != 0:  # Only show accounts with balance
            trial_balance_data.append({
                'account': account,
                'debit': balance if account.balance_type == 'DEBIT' else Decimal('0'),
                'credit': balance if account.balance_type == 'CREDIT' else Decimal('0'),
            })
            
            if account.balance_type == 'DEBIT':
                total_debit += balance
            else:
                total_credit += balance
    
    context = {
        'trial_balance_data': trial_balance_data,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'date_to': date_to,
    }
    
    return render(request, 'finance/trial_balance.html', context)


@login_required
def profit_loss_statement(request):
    """Profit & Loss Statement"""
    
    # Get date range
    date_from = request.GET.get('date_from', timezone.now().date().replace(day=1).isoformat())
    date_to = request.GET.get('date_to', timezone.now().date().isoformat())
    
    # Revenue
    revenue_accounts = Account.objects.filter(
        account_type__type='REVENUE',
        is_active=True
    ).order_by('code')
    
    revenue_total = Decimal('0')
    revenue_details = []
    
    for account in revenue_accounts:
        credit_total = JournalEntryItem.objects.filter(
            account=account,
            journal_entry__status='posted',
            journal_entry__entry_date__gte=date_from,
            journal_entry__entry_date__lte=date_to,
            credit__gt=0
        ).aggregate(total=Sum('credit'))['total'] or Decimal('0')
        
        if credit_total > 0:
            revenue_details.append({
                'account': account,
                'amount': credit_total
            })
            revenue_total += credit_total
    
    # Cost of Sales
    cos_accounts = Account.objects.filter(
        account_type__type='COST_OF_SALES',
        is_active=True
    ).order_by('code')
    
    cos_total = Decimal('0')
    cos_details = []
    
    for account in cos_accounts:
        debit_total = JournalEntryItem.objects.filter(
            account=account,
            journal_entry__status='posted',
            journal_entry__entry_date__gte=date_from,
            journal_entry__entry_date__lte=date_to,
            debit__gt=0
        ).aggregate(total=Sum('debit'))['total'] or Decimal('0')
        
        if debit_total > 0:
            cos_details.append({
                'account': account,
                'amount': debit_total
            })
            cos_total += debit_total
    
    # Gross Profit
    gross_profit = revenue_total - cos_total
    
    # Expenses
    expense_accounts = Account.objects.filter(
        account_type__type='EXPENSE',
        is_active=True
    ).order_by('code')
    
    expense_total = Decimal('0')
    expense_details = []
    
    for account in expense_accounts:
        debit_total = JournalEntryItem.objects.filter(
            account=account,
            journal_entry__status='posted',
            journal_entry__entry_date__gte=date_from,
            journal_entry__entry_date__lte=date_to,
            debit__gt=0
        ).aggregate(total=Sum('debit'))['total'] or Decimal('0')
        
        if debit_total > 0:
            expense_details.append({
                'account': account,
                'amount': debit_total
            })
            expense_total += debit_total
    
    # Net Income
    net_income = gross_profit - expense_total
    
    context = {
        'date_from': date_from,
        'date_to': date_to,
        'revenue_details': revenue_details,
        'revenue_total': revenue_total,
        'cos_details': cos_details,
        'cos_total': cos_total,
        'gross_profit': gross_profit,
        'expense_details': expense_details,
        'expense_total': expense_total,
        'net_income': net_income,
    }
    
    return render(request, 'finance/profit_loss_statement.html', context)


@login_required
def balance_sheet(request):
    """Balance Sheet"""
    
    # Get date
    date = request.GET.get('date', timezone.now().date().isoformat())
    
    # Assets
    asset_accounts = Account.objects.filter(
        account_type__type='ASSET',
        is_active=True
    ).order_by('code')
    
    assets_total = Decimal('0')
    assets_details = []
    
    for account in asset_accounts:
        balance = account.current_balance
        if balance != 0:
            assets_details.append({
                'account': account,
                'balance': balance
            })
            assets_total += balance
    
    # Liabilities
    liability_accounts = Account.objects.filter(
        account_type__type='LIABILITY',
        is_active=True
    ).order_by('code')
    
    liabilities_total = Decimal('0')
    liabilities_details = []
    
    for account in liability_accounts:
        balance = account.current_balance
        if balance != 0:
            liabilities_details.append({
                'account': account,
                'balance': balance
            })
            liabilities_total += balance
    
    # Equity
    equity_accounts = Account.objects.filter(
        account_type__type='EQUITY',
        is_active=True
    ).order_by('code')
    
    equity_total = Decimal('0')
    equity_details = []
    
    for account in equity_accounts:
        balance = account.current_balance
        if balance != 0:
            equity_details.append({
                'account': account,
                'balance': balance
            })
            equity_total += balance
    
    # Total Liabilities & Equity
    total_liabilities_equity = liabilities_total + equity_total
    
    context = {
        'date': date,
        'assets_details': assets_details,
        'assets_total': assets_total,
        'liabilities_details': liabilities_details,
        'liabilities_total': liabilities_total,
        'equity_details': equity_details,
        'equity_total': equity_total,
        'total_liabilities_equity': total_liabilities_equity,
    }
    
    return render(request, 'finance/balance_sheet.html', context)


# ==================== ACCOUNT TYPES ====================

@login_required
def account_type_list(request):
    """Account Type List"""
    
    account_types = AccountType.objects.all().order_by('code')
    
    # Get stats
    active_count = account_types.filter(is_active=True).count()
    total_accounts = Account.objects.filter(is_active=True).count()
    # Note: current_balance is a property, not a database field, so we can't aggregate it directly
    # We'll calculate it in the template or use a different approach
    total_balance = Decimal('0')  # Placeholder for now
    
    context = {
        'account_types': account_types,
        'active_count': active_count,
        'total_accounts': total_accounts,
        'total_balance': total_balance,
    }
    
    return render(request, 'finance/account_type_list.html', context)


@login_required
def account_type_create(request):
    """Create Account Type"""
    
    if request.method == 'POST':
        try:
            account_type = AccountType.objects.create(
                code=request.POST.get('code'),
                name=request.POST.get('name'),
                type=request.POST.get('type'),
                description=request.POST.get('description', ''),
                is_active=request.POST.get('is_active') == 'on'
            )
            messages.success(request, f'Account Type {account_type.name} berhasil dibuat')
            return redirect('finance:account_type_detail', account_type_id=account_type.id)
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    context = {}
    
    return render(request, 'finance/account_type_create.html', context)


@login_required
def account_type_detail(request, account_type_id):
    """Account Type Detail"""
    
    account_type = get_object_or_404(AccountType, id=account_type_id)
    
    context = {
        'account_type': account_type,
    }
    
    return render(request, 'finance/account_type_detail.html', context)


@login_required
def account_type_edit(request, account_type_id):
    """Edit Account Type"""
    
    account_type = get_object_or_404(AccountType, id=account_type_id)
    
    if request.method == 'POST':
        try:
            account_type.code = request.POST.get('code')
            account_type.name = request.POST.get('name')
            account_type.type = request.POST.get('type')
            account_type.description = request.POST.get('description', '')
            account_type.is_active = request.POST.get('is_active') == 'on'
            account_type.save()
            messages.success(request, f'Account Type {account_type.name} berhasil diupdate')
            return redirect('finance:account_type_detail', account_type_id=account_type.id)
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    context = {
        'account_type': account_type,
    }
    
    return render(request, 'finance/account_type_edit.html', context)


# ==================== ACCOUNTS ====================

@login_required
def account_create(request):
    """Create Account"""
    
    if request.method == 'POST':
        try:
            account = Account.objects.create(
                code=request.POST.get('code'),
                name=request.POST.get('name'),
                account_type_id=request.POST.get('account_type'),
                parent_id=request.POST.get('parent') or None,
                balance_type=request.POST.get('balance_type'),
                description=request.POST.get('description', ''),
                notes=request.POST.get('notes', ''),
                is_active=request.POST.get('is_active') == 'on',
                is_system=request.POST.get('is_system') == 'on'
            )
            messages.success(request, f'Account {account.name} berhasil dibuat')
            return redirect('finance:account_detail', account_id=account.id)
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    account_types = AccountType.objects.filter(is_active=True).order_by('code')
    parent_accounts = Account.objects.filter(is_active=True).order_by('code')
    
    context = {
        'account_types': account_types,
        'parent_accounts': parent_accounts,
    }
    
    return render(request, 'finance/account_create.html', context)


@login_required
def account_edit(request, account_id):
    """Edit Account"""
    
    account = get_object_or_404(Account, id=account_id)
    
    if request.method == 'POST':
        try:
            account.code = request.POST.get('code')
            account.name = request.POST.get('name')
            account.account_type_id = request.POST.get('account_type')
            account.parent_id = request.POST.get('parent') or None
            account.balance_type = request.POST.get('balance_type')
            account.description = request.POST.get('description', '')
            account.notes = request.POST.get('notes', '')
            account.is_active = request.POST.get('is_active') == 'on'
            if not account.is_system:  # Only allow editing if not system account
                account.is_system = request.POST.get('is_system') == 'on'
            account.save()
            messages.success(request, f'Account {account.name} berhasil diupdate')
            return redirect('finance:account_detail', account_id=account.id)
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    account_types = AccountType.objects.filter(is_active=True).order_by('code')
    parent_accounts = Account.objects.filter(is_active=True).exclude(id=account_id).order_by('code')
    
    context = {
        'account': account,
        'account_types': account_types,
        'parent_accounts': parent_accounts,
    }
    
    return render(request, 'finance/account_edit.html', context)


@login_required
def account_detail(request, account_id):
    """Account Detail - Enhanced version"""
    
    account = get_object_or_404(Account, id=account_id)
    
    # Get journal entries for this account
    journal_items = JournalEntryItem.objects.filter(
        account=account,
        journal_entry__status='posted'
    ).select_related('journal_entry').order_by('-journal_entry__entry_date', '-id')
    
    # Get date range filter
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if date_from and date_to:
        journal_items = journal_items.filter(
            journal_entry__entry_date__gte=date_from,
            journal_entry__entry_date__lte=date_to
        )
    
    # Paginate
    paginator = Paginator(journal_items, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'account': account,
        'page_obj': page_obj,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'finance/account_detail.html', context)


# ==================== JOURNAL ENTRIES - ENHANCED ====================

@login_required
def journal_entry_create(request):
    """Create Journal Entry - Enhanced version"""
    
    if request.method == 'POST':
        try:
            entry = JournalEntry.objects.create(
                entry_date=request.POST.get('entry_date'),
                reference=request.POST.get('reference', ''),
                description=request.POST.get('description'),
                notes=request.POST.get('notes', ''),
                status=request.POST.get('status', 'draft'),
                created_by=request.user
            )
            
            # Process items
            accounts = request.POST.getlist('account')
            debits = request.POST.getlist('debit')
            credits = request.POST.getlist('credit')
            descriptions = request.POST.getlist('item_description')
            
            for i in range(len(accounts)):
                if accounts[i]:
                    JournalEntryItem.objects.create(
                        journal_entry=entry,
                        account_id=accounts[i],
                        debit=Decimal(debits[i] or 0),
                        credit=Decimal(credits[i] or 0),
                        description=descriptions[i]
                    )
            
            messages.success(request, f'Journal Entry {entry.entry_number} berhasil dibuat')
            return redirect('finance:journal_entry_detail', entry_id=entry.id)
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    accounts = Account.objects.filter(is_active=True).order_by('code')
    accounts_json = json.dumps([{
        'id': account.id,
        'code': account.code,
        'name': account.name
    } for account in accounts])
    
    context = {
        'accounts': accounts,
        'accounts_json': accounts_json,
    }
    
    return render(request, 'finance/journal_entry_create.html', context)


@login_required
def journal_entry_edit(request, entry_id):
    """Edit Journal Entry"""
    
    entry = get_object_or_404(JournalEntry, id=entry_id)
    
    if request.method == 'POST':
        try:
            entry.entry_date = request.POST.get('entry_date')
            entry.reference = request.POST.get('reference', '')
            entry.description = request.POST.get('description')
            entry.notes = request.POST.get('notes', '')
            if entry.status == 'draft':  # Only allow status change for draft entries
                entry.status = request.POST.get('status', 'draft')
            entry.save()
            
            # Clear existing items
            entry.items.all().delete()
            
            # Process new items
            accounts = request.POST.getlist('account')
            debits = request.POST.getlist('debit')
            credits = request.POST.getlist('credit')
            descriptions = request.POST.getlist('item_description')
            
            for i in range(len(accounts)):
                if accounts[i]:
                    JournalEntryItem.objects.create(
                        journal_entry=entry,
                        account_id=accounts[i],
                        debit=Decimal(debits[i] or 0),
                        credit=Decimal(credits[i] or 0),
                        description=descriptions[i]
                    )
            
            messages.success(request, f'Journal Entry {entry.entry_number} berhasil diupdate')
            return redirect('finance:journal_entry_detail', entry_id=entry.id)
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    accounts = Account.objects.filter(is_active=True).order_by('code')
    accounts_json = json.dumps([{
        'id': account.id,
        'code': account.code,
        'name': account.name
    } for account in accounts])
    
    existing_items = entry.items.all()
    existing_items_json = json.dumps([{
        'id': item.id,
        'account_id': item.account.id,
        'debit': float(item.debit),
        'credit': float(item.credit),
        'description': item.description or ''
    } for item in existing_items])
    
    context = {
        'entry': entry,
        'accounts': accounts,
        'accounts_json': accounts_json,
        'existing_items_json': existing_items_json,
    }
    
    return render(request, 'finance/journal_entry_edit.html', context)
