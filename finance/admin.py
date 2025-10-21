from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    AccountType, Account, JournalEntry, JournalEntryItem,
    CashFlow, Budget, FinancialReport, FinanceSettings
)

# Register your models here.

@admin.register(AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'type', 'is_active', 'account_count']
    list_filter = ['type', 'is_active']
    search_fields = ['code', 'name']
    ordering = ['code']
    
    def account_count(self, obj):
        return obj.accounts.count()
    account_count.short_description = 'Jumlah Akun'


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'account_type', 'balance_type', 'current_balance_display', 'is_active', 'is_system']
    list_filter = ['account_type', 'balance_type', 'is_active', 'is_system']
    search_fields = ['code', 'name']
    ordering = ['code']
    readonly_fields = ['current_balance_display', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Informasi Akun', {
            'fields': ('code', 'name', 'account_type', 'parent', 'balance_type', 'is_active', 'is_system')
        }),
        ('Detail', {
            'fields': ('description', 'notes')
        }),
        ('Saldo', {
            'fields': ('current_balance_display',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def current_balance_display(self, obj):
        balance = obj.current_balance
        color = 'green' if balance >= 0 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.formatted_balance
        )
    current_balance_display.short_description = 'Saldo Saat Ini'


class JournalEntryItemInline(admin.TabularInline):
    model = JournalEntryItem
    extra = 2
    fields = ['account', 'debit', 'credit', 'description']
    autocomplete_fields = ['account']


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ['entry_number', 'entry_date', 'reference', 'description_short', 'status', 'total_debit_display', 'total_credit_display', 'is_balanced_display', 'created_by', 'created_at']
    list_filter = ['status', 'entry_date', 'created_at']
    search_fields = ['entry_number', 'reference', 'description']
    ordering = ['-entry_date', '-id']
    readonly_fields = ['entry_number', 'total_debit_display', 'total_credit_display', 'is_balanced_display', 'created_at', 'updated_at', 'posted_at']
    autocomplete_fields = ['created_by', 'posted_by']
    inlines = [JournalEntryItemInline]
    
    fieldsets = (
        ('Informasi Entry', {
            'fields': ('entry_number', 'entry_date', 'reference', 'description', 'status')
        }),
        ('Link ke Transaksi Lain', {
            'fields': ('content_type', 'object_id'),
            'classes': ('collapse',)
        }),
        ('Tracking', {
            'fields': ('created_by', 'posted_by', 'posted_at')
        }),
        ('Detail', {
            'fields': ('notes',)
        }),
        ('Balance Check', {
            'fields': ('total_debit_display', 'total_credit_display', 'is_balanced_display'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['post_selected_entries', 'reverse_selected_entries']
    
    def description_short(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_short.short_description = 'Description'
    
    def total_debit_display(self, obj):
        return format_html('<span style="color: green; font-weight: bold;">Rp {:,}</span>', obj.total_debit)
    total_debit_display.short_description = 'Total Debit'
    
    def total_credit_display(self, obj):
        return format_html('<span style="color: red; font-weight: bold;">Rp {:,}</span>', obj.total_credit)
    total_credit_display.short_description = 'Total Credit'
    
    def is_balanced_display(self, obj):
        if obj.is_balanced:
            return format_html('<span style="color: green;">✓ Balanced</span>')
        else:
            return format_html('<span style="color: red;">✗ Not Balanced</span>')
    is_balanced_display.short_description = 'Balance Status'
    
    def post_selected_entries(self, request, queryset):
        count = 0
        for entry in queryset.filter(status='draft'):
            try:
                entry.post(request.user)
                count += 1
            except Exception as e:
                self.message_user(request, f'Error posting {entry.entry_number}: {str(e)}', level='error')
        
        if count > 0:
            self.message_user(request, f'{count} journal entries berhasil di-post')
    post_selected_entries.short_description = 'Post selected journal entries'
    
    def reverse_selected_entries(self, request, queryset):
        count = 0
        for entry in queryset.filter(status='posted'):
            try:
                entry.reverse(request.user)
                count += 1
            except Exception as e:
                self.message_user(request, f'Error reversing {entry.entry_number}: {str(e)}', level='error')
        
        if count > 0:
            self.message_user(request, f'{count} journal entries berhasil di-reverse')
    reverse_selected_entries.short_description = 'Reverse selected journal entries'


@admin.register(JournalEntryItem)
class JournalEntryItemAdmin(admin.ModelAdmin):
    list_display = ['journal_entry', 'account', 'debit', 'credit', 'description_short']
    list_filter = ['journal_entry__status', 'journal_entry__entry_date']
    search_fields = ['journal_entry__entry_number', 'account__code', 'account__name', 'description']
    autocomplete_fields = ['journal_entry', 'account']
    ordering = ['-journal_entry__entry_date', 'id']
    
    def description_short(self, obj):
        return obj.description[:50] + '...' if obj.description and len(obj.description) > 50 else (obj.description or '-')
    description_short.short_description = 'Description'


@admin.register(CashFlow)
class CashFlowAdmin(admin.ModelAdmin):
    list_display = ['transaction_date', 'category', 'flow_type_display', 'account', 'amount_display', 'description_short', 'reference', 'created_by']
    list_filter = ['category', 'flow_type', 'transaction_date']
    search_fields = ['description', 'reference', 'account__code', 'account__name']
    ordering = ['-transaction_date', '-id']
    autocomplete_fields = ['account', 'created_by']
    
    fieldsets = (
        ('Informasi Transaksi', {
            'fields': ('transaction_date', 'category', 'flow_type', 'account', 'amount')
        }),
        ('Detail', {
            'fields': ('description', 'reference')
        }),
        ('Link ke Transaksi Lain', {
            'fields': ('content_type', 'object_id'),
            'classes': ('collapse',)
        }),
        ('Tracking', {
            'fields': ('created_by', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def flow_type_display(self, obj):
        if obj.flow_type == 'INFLOW':
            return format_html('<span style="color: green;">+ Inflow</span>')
        else:
            return format_html('<span style="color: red;">- Outflow</span>')
    flow_type_display.short_description = 'Flow Type'
    
    def amount_display(self, obj):
        color = 'green' if obj.flow_type == 'INFLOW' else 'red'
        sign = '+' if obj.flow_type == 'INFLOW' else '-'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}{:,}</span>',
            color,
            sign,
            obj.amount
        )
    amount_display.short_description = 'Amount'
    
    def description_short(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_short.short_description = 'Description'


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['name', 'account', 'period_type', 'period_start', 'period_end', 'budget_amount_display', 'actual_amount_display', 'variance_display', 'utilization_percentage_display', 'status']
    list_filter = ['status', 'period_type', 'period_start', 'period_end']
    search_fields = ['name', 'account__code', 'account__name', 'description']
    ordering = ['-period_start', '-id']
    autocomplete_fields = ['account', 'created_by', 'approved_by']
    
    fieldsets = (
        ('Informasi Budget', {
            'fields': ('name', 'description', 'account', 'period_type', 'period_start', 'period_end', 'status')
        }),
        ('Amount', {
            'fields': ('budget_amount',)
        }),
        ('Tracking', {
            'fields': ('created_by', 'approved_by', 'approved_at')
        }),
        ('Detail', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'approved_at']
    
    def budget_amount_display(self, obj):
        return format_html('<span style="font-weight: bold;">Rp {:,}</span>', obj.budget_amount)
    budget_amount_display.short_description = 'Budget'
    
    def actual_amount_display(self, obj):
        return format_html('<span style="font-weight: bold;">Rp {:,}</span>', obj.actual_amount)
    actual_amount_display.short_description = 'Actual'
    
    def variance_display(self, obj):
        variance = obj.variance
        color = 'green' if variance >= 0 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">Rp {:,}</span>',
            color,
            variance
        )
    variance_display.short_description = 'Variance'
    
    def utilization_percentage_display(self, obj):
        percentage = obj.utilization_percentage
        color = 'green' if percentage <= 80 else 'orange' if percentage <= 100 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color,
            percentage
        )
    utilization_percentage_display.short_description = 'Usage'


@admin.register(FinancialReport)
class FinancialReportAdmin(admin.ModelAdmin):
    list_display = ['report_name', 'report_type', 'period_type', 'period_start', 'period_end', 'is_generated_display', 'generated_at', 'generated_by']
    list_filter = ['report_type', 'period_type', 'is_generated', 'period_start', 'period_end']
    search_fields = ['report_name', 'notes']
    ordering = ['-period_end', '-id']
    autocomplete_fields = ['generated_by']
    
    fieldsets = (
        ('Informasi Report', {
            'fields': ('report_name', 'report_type', 'period_type', 'period_start', 'period_end')
        }),
        ('Generated Data', {
            'fields': ('report_data', 'is_generated', 'generated_at', 'generated_by'),
            'classes': ('collapse',)
        }),
        ('Export Files', {
            'fields': ('pdf_file', 'excel_file'),
            'classes': ('collapse',)
        }),
        ('Detail', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['is_generated', 'generated_at', 'created_at', 'updated_at']
    
    def is_generated_display(self, obj):
        if obj.is_generated:
            return format_html('<span style="color: green;">✓ Generated</span>')
        else:
            return format_html('<span style="color: orange;">Pending</span>')
    is_generated_display.short_description = 'Status'


@admin.register(FinanceSettings)
class FinanceSettingsAdmin(admin.ModelAdmin):
    list_display = ['key', 'value_short', 'description', 'updated_at', 'updated_by']
    search_fields = ['key', 'value', 'description']
    ordering = ['key']
    autocomplete_fields = ['updated_by']
    
    fieldsets = (
        ('Setting', {
            'fields': ('key', 'value', 'description')
        }),
        ('Tracking', {
            'fields': ('updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['updated_at']
    
    def value_short(self, obj):
        return obj.value[:50] + '...' if len(obj.value) > 50 else obj.value
    value_short.short_description = 'Value'
