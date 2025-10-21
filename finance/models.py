from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal

# Create your models here.

class AccountType(models.Model):
    """Chart of Accounts Type"""
    TYPE_CHOICES = [
        ('ASSET', 'Asset'),
        ('LIABILITY', 'Liability'),
        ('EQUITY', 'Equity'),
        ('REVENUE', 'Revenue'),
        ('EXPENSE', 'Expense'),
        ('COST_OF_SALES', 'Cost of Sales'),
    ]
    
    code = models.CharField(max_length=20, unique=True, help_text="Kode tipe akun (contoh: 1, 2, 3)")
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['code']
        verbose_name = 'Account Type'
        verbose_name_plural = 'Account Types'
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Account(models.Model):
    """Chart of Accounts"""
    BALANCE_TYPE_CHOICES = [
        ('DEBIT', 'Debit'),
        ('CREDIT', 'Credit'),
    ]
    
    code = models.CharField(max_length=20, unique=True, db_index=True, help_text="Kode akun (contoh: 1-1000, 2-2000)")
    name = models.CharField(max_length=200)
    account_type = models.ForeignKey(AccountType, on_delete=models.PROTECT, related_name='accounts')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', help_text="Parent account untuk hierarki")
    
    balance_type = models.CharField(max_length=10, choices=BALANCE_TYPE_CHOICES, help_text="Tipe saldo normal")
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False, help_text="Akun sistem (tidak bisa dihapus)")
    
    description = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['code']
        verbose_name = 'Account'
        verbose_name_plural = 'Chart of Accounts'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['account_type']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def current_balance(self):
        """Hitung saldo akun saat ini"""
        from django.db.models import Sum, Q
        
        # Hitung total debit dan credit
        debit_total = self.journal_items.filter(
            journal_entry__status='posted',
            debit__gt=0
        ).aggregate(Sum('debit'))['debit__sum'] or Decimal('0')
        
        credit_total = self.journal_items.filter(
            journal_entry__status='posted',
            credit__gt=0
        ).aggregate(Sum('credit'))['credit__sum'] or Decimal('0')
        
        # Tentukan saldo berdasarkan balance_type
        if self.balance_type == 'DEBIT':
            return debit_total - credit_total
        else:
            return credit_total - debit_total
    
    @property
    def formatted_balance(self):
        """Format saldo dengan pemisah ribuan"""
        balance = self.current_balance
        return f"Rp {balance:,.0f}".replace(',', '.')


class JournalEntry(models.Model):
    """Journal Entry - Buku Besar"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('reversed', 'Reversed'),
        ('cancelled', 'Cancelled'),
    ]
    
    entry_number = models.CharField(max_length=50, unique=True, db_index=True)
    entry_date = models.DateField(default=timezone.now, db_index=True)
    reference = models.CharField(max_length=100, blank=True, null=True, help_text="No. referensi (PO, Invoice, dll)")
    description = models.TextField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    
    # Link ke module lain (optional)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='journal_entries_created'
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journal_entries_posted'
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-entry_date', '-id']
        verbose_name = 'Journal Entry'
        verbose_name_plural = 'Journal Entries'
        indexes = [
            models.Index(fields=['entry_date']),
            models.Index(fields=['status']),
            models.Index(fields=['entry_number']),
        ]
    
    def __str__(self):
        return f"{self.entry_number} - {self.entry_date} - {self.description[:50]}"
    
    def save(self, *args, **kwargs):
        if not self.entry_number:
            # Auto-generate entry number
            date_str = timezone.now().strftime('%Y%m%d')
            last_entry = JournalEntry.objects.filter(
                entry_number__startswith=f'JE-{date_str}'
            ).order_by('-entry_number').first()
            
            if last_entry:
                last_id = int(last_entry.entry_number.split('-')[-1])
                new_id = last_id + 1
            else:
                new_id = 1
            
            self.entry_number = f"JE-{date_str}-{new_id:04d}"
        
        super().save(*args, **kwargs)
    
    @property
    def total_debit(self):
        """Total debit dari semua items"""
        return sum(item.debit for item in self.items.all())
    
    @property
    def total_credit(self):
        """Total credit dari semua items"""
        return sum(item.credit for item in self.items.all())
    
    @property
    def is_balanced(self):
        """Cek apakah debit = credit"""
        return self.total_debit == self.total_credit
    
    def post(self, user):
        """Post journal entry"""
        if not self.is_balanced:
            raise ValueError("Journal entry tidak balance (debit != credit)")
        
        if self.status != 'draft':
            raise ValueError("Hanya draft journal entry yang bisa di-post")
        
        self.status = 'posted'
        self.posted_by = user
        self.posted_at = timezone.now()
        self.save()
    
    def reverse(self, user):
        """Reverse journal entry"""
        if self.status != 'posted':
            raise ValueError("Hanya posted journal entry yang bisa di-reverse")
        
        # Create reversal entry
        reversal = JournalEntry.objects.create(
            entry_date=timezone.now().date(),
            reference=f"REV-{self.entry_number}",
            description=f"Reversal of {self.entry_number}: {self.description}",
            created_by=user,
            status='posted'
        )
        
        # Copy items with reversed debit/credit
        for item in self.items.all():
            JournalEntryItem.objects.create(
                journal_entry=reversal,
                account=item.account,
                debit=item.credit,  # Reversed
                credit=item.debit,  # Reversed
                description=item.description
            )
        
        self.status = 'reversed'
        self.save()
        
        return reversal


class JournalEntryItem(models.Model):
    """Journal Entry Item - Detail transaksi"""
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='items')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='journal_items')
    
    debit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Jumlah debit (Rp)"
    )
    credit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Jumlah credit (Rp)"
    )
    
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['id']
        verbose_name = 'Journal Entry Item'
        verbose_name_plural = 'Journal Entry Items'
    
    def __str__(self):
        return f"{self.journal_entry.entry_number} - {self.account.code} - Debit:{self.debit} Credit:{self.credit}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        # Pastikan salah satu debit atau credit harus > 0
        if self.debit == 0 and self.credit == 0:
            raise ValidationError("Salah satu debit atau credit harus > 0")
        # Pastikan tidak keduanya > 0
        if self.debit > 0 and self.credit > 0:
            raise ValidationError("Tidak boleh debit dan credit keduanya > 0")


class CashFlow(models.Model):
    """Cash Flow - Arus Kas"""
    CATEGORY_CHOICES = [
        ('OPERATING', 'Operating Activities'),
        ('INVESTING', 'Investing Activities'),
        ('FINANCING', 'Financing Activities'),
    ]
    
    FLOW_TYPE_CHOICES = [
        ('INFLOW', 'Cash Inflow (+)'),
        ('OUTFLOW', 'Cash Outflow (-)'),
    ]
    
    transaction_date = models.DateField(default=timezone.now, db_index=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    flow_type = models.CharField(max_length=10, choices=FLOW_TYPE_CHOICES)
    
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='cash_flows')
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))]
    )
    
    description = models.TextField()
    reference = models.CharField(max_length=100, blank=True, null=True)
    
    # Link ke module lain (optional)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='cash_flows_created'
    )
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-transaction_date', '-id']
        verbose_name = 'Cash Flow'
        verbose_name_plural = 'Cash Flows'
        indexes = [
            models.Index(fields=['transaction_date']),
            models.Index(fields=['category']),
            models.Index(fields=['flow_type']),
        ]
    
    def __str__(self):
        flow_sign = '+' if self.flow_type == 'INFLOW' else '-'
        return f"{self.transaction_date} - {flow_sign} {self.amount} - {self.description[:50]}"
    
    @property
    def signed_amount(self):
        """Amount dengan tanda +/-"""
        return self.amount if self.flow_type == 'INFLOW' else -self.amount


class Budget(models.Model):
    """Budget - Anggaran"""
    PERIOD_CHOICES = [
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('YEARLY', 'Yearly'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='budgets')
    period_type = models.CharField(max_length=20, choices=PERIOD_CHOICES)
    period_start = models.DateField()
    period_end = models.DateField()
    
    budget_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))]
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='budgets_created'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='budgets_approved'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-period_start', '-id']
        verbose_name = 'Budget'
        verbose_name_plural = 'Budgets'
        indexes = [
            models.Index(fields=['period_start', 'period_end']),
            models.Index(fields=['status']),
            models.Index(fields=['account']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.account.code} - {self.period_start} to {self.period_end}"
    
    @property
    def actual_amount(self):
        """Hitung actual spending untuk periode budget ini"""
        from django.db.models import Sum
        
        # Sum journal entries untuk account ini dalam periode budget
        actual = self.account.journal_items.filter(
            journal_entry__status='posted',
            journal_entry__entry_date__gte=self.period_start,
            journal_entry__entry_date__lte=self.period_end
        ).aggregate(
            actual_debit=Sum('debit'),
            actual_credit=Sum('credit')
        )
        
        # Tentukan actual berdasarkan balance_type account
        if self.account.balance_type == 'DEBIT':
            return (actual['actual_debit'] or Decimal('0')) - (actual['actual_credit'] or Decimal('0'))
        else:
            return (actual['actual_credit'] or Decimal('0')) - (actual['actual_debit'] or Decimal('0'))
    
    @property
    def variance(self):
        """Selisih budget vs actual"""
        return self.budget_amount - self.actual_amount
    
    @property
    def variance_percentage(self):
        """Persentase variance"""
        if self.budget_amount == 0:
            return 0
        return (self.variance / self.budget_amount) * 100
    
    @property
    def utilization_percentage(self):
        """Persentase penggunaan budget"""
        if self.budget_amount == 0:
            return 0
        return (self.actual_amount / self.budget_amount) * 100


class FinancialReport(models.Model):
    """Financial Report - Laporan Keuangan"""
    REPORT_TYPE_CHOICES = [
        ('PROFIT_LOSS', 'Profit & Loss Statement'),
        ('BALANCE_SHEET', 'Balance Sheet'),
        ('CASH_FLOW', 'Cash Flow Statement'),
        ('TRIAL_BALANCE', 'Trial Balance'),
        ('GENERAL_LEDGER', 'General Ledger'),
    ]
    
    PERIOD_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('YEARLY', 'Yearly'),
        ('CUSTOM', 'Custom Period'),
    ]
    
    report_name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    period_type = models.CharField(max_length=20, choices=PERIOD_CHOICES)
    
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Generated report data (JSON)
    report_data = models.JSONField(null=True, blank=True)
    
    # File export
    pdf_file = models.FileField(upload_to='financial_reports/', blank=True, null=True)
    excel_file = models.FileField(upload_to='financial_reports/', blank=True, null=True)
    
    # Status
    is_generated = models.BooleanField(default=False)
    generated_at = models.DateTimeField(null=True, blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='financial_reports_generated'
    )
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-period_end', '-id']
        verbose_name = 'Financial Report'
        verbose_name_plural = 'Financial Reports'
        indexes = [
            models.Index(fields=['report_type']),
            models.Index(fields=['period_start', 'period_end']),
            models.Index(fields=['is_generated']),
        ]
    
    def __str__(self):
        return f"{self.report_name} - {self.period_start} to {self.period_end}"


class FinanceSettings(models.Model):
    """Finance Settings - Pengaturan Finance"""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = 'Finance Setting'
        verbose_name_plural = 'Finance Settings'
    
    def __str__(self):
        return f"{self.key} = {self.value}"
