"""
Accounting utilities for Purchase module
Handles automatic journal entries for purchase flow
"""
from django.db import transaction
from django.utils import timezone
from datetime import datetime
from decimal import Decimal
from finance.models import JournalEntry, JournalEntryItem, Account
from django.contrib.contenttypes.models import ContentType


def create_journal_entry_number(prefix="JE"):
    """Generate unique journal entry number"""
    from django.utils import timezone
    date_str = timezone.now().strftime('%Y%m%d')
    
    # Get next ID
    last_entry = JournalEntry.objects.filter(
        entry_number__startswith=f'{prefix}-{date_str}'
    ).order_by('-entry_number').first()
    
    if last_entry and last_entry.entry_number:
        try:
            last_id = int(last_entry.entry_number.split('-')[-1])
            new_id = last_id + 1
        except (ValueError, IndexError):
            new_id = 1
    else:
        new_id = 1
    
    return f"{prefix}-{date_str}-{new_id:04d}"


def get_or_create_account_by_code(code, name, account_type_code, balance_type):
    """Get or create account by code"""
    from finance.models import AccountType
    
    # Get or create account type
    account_type, created = AccountType.objects.get_or_create(
        code=account_type_code,
        defaults={
            'name': account_type_code,
            'type': 'ASSET' if account_type_code.startswith('1') else 
                   'LIABILITY' if account_type_code.startswith('2') else 'EXPENSE'
        }
    )
    
    # Get or create account
    account, created = Account.objects.get_or_create(
        code=code,
        defaults={
            'name': name,
            'account_type': account_type,
            'balance_type': balance_type,
            'is_system': True
        }
    )
    
    return account


def create_purchase_verify_journal_entry(purchase, user):
    """
    Create journal entry for Purchase Verify
    Debit: Inventory (based on purchase items)
    Credit: Accounts Payable
    """
    try:
        with transaction.atomic():
            # Get or create accounts
            inventory_account = get_or_create_account_by_code(
                code='1-1200',
                name='Persediaan Barang',
                account_type_code='1',
                balance_type='DEBIT'
            )
            
            accounts_payable_account = get_or_create_account_by_code(
                code='2-2000',
                name='Hutang Usaha',
                account_type_code='2',
                balance_type='CREDIT'
            )
            
            # Create journal entry
            journal_entry = JournalEntry.objects.create(
                entry_number=create_journal_entry_number("PV"),
                entry_date=purchase.tanggal_purchase or timezone.now().date(),
                reference=purchase.nomor_purchase,
                description=f"Verifikasi Purchase {purchase.nomor_purchase}",
                status='posted',
                content_type=ContentType.objects.get_for_model(purchase),
                object_id=purchase.id,
                created_by=user,
                posted_by=user,
                posted_at=timezone.now()
            )
            
            # Create journal entry items
            total_amount = Decimal(str(purchase.total_amount))
            
            # Debit: Inventory
            JournalEntryItem.objects.create(
                journal_entry=journal_entry,
                account=inventory_account,
                debit=total_amount,
                credit=Decimal('0'),
                description=f"Penerimaan barang dari {purchase.supplier.nama_supplier if purchase.supplier else 'Supplier'}"
            )
            
            # Credit: Accounts Payable
            JournalEntryItem.objects.create(
                journal_entry=journal_entry,
                account=accounts_payable_account,
                debit=Decimal('0'),
                credit=total_amount,
                description=f"Hutang ke {purchase.supplier.nama_supplier if purchase.supplier else 'Supplier'}"
            )
            
            return journal_entry
            
    except Exception as e:
        raise Exception(f"Error creating journal entry for purchase verify: {str(e)}")


def create_purchase_payment_journal_entry(purchase, payment_amount, bank_account, user, discount_amount=0):
    """
    Create journal entry for Purchase Payment
    Debit: Accounts Payable (total amount)
    Credit: Cash/Bank (payment amount)
    Credit: Discount Received (discount amount, if any)
    """
    try:
        with transaction.atomic():
            # Get or create accounts
            accounts_payable_account = get_or_create_account_by_code(
                code='2-2000',
                name='Hutang Usaha',
                account_type_code='2',
                balance_type='CREDIT'
            )
            
            # Use bank account if linked, otherwise create cash account
            if bank_account and bank_account.account:
                cash_bank_account = bank_account.account
            else:
                cash_bank_account = get_or_create_account_by_code(
                    code='1-1100',
                    name='Kas',
                    account_type_code='1',
                    balance_type='DEBIT'
                )
            
            # Create journal entry
            journal_entry = JournalEntry.objects.create(
                entry_number=create_journal_entry_number("PP"),
                entry_date=timezone.now().date(),
                reference=purchase.nomor_purchase,
                description=f"Pembayaran Purchase {purchase.nomor_purchase}",
                status='posted',
                content_type=ContentType.objects.get_for_model(purchase),
                object_id=purchase.id,
                created_by=user,
                posted_by=user,
                posted_at=timezone.now()
            )
            
            # Create journal entry items
            payment_decimal = Decimal(str(payment_amount))
            discount_decimal = Decimal(str(discount_amount))
            total_decimal = payment_decimal + discount_decimal
            
            # Debit: Accounts Payable (total amount = payment + discount)
            JournalEntryItem.objects.create(
                journal_entry=journal_entry,
                account=accounts_payable_account,
                debit=total_decimal,
                credit=Decimal('0'),
                description=f"Pembayaran hutang ke {purchase.supplier.nama_supplier if purchase.supplier else 'Supplier'}"
            )
            
            # Credit: Cash/Bank (actual payment amount)
            JournalEntryItem.objects.create(
                journal_entry=journal_entry,
                account=cash_bank_account,
                debit=Decimal('0'),
                credit=payment_decimal,
                description=f"Pembayaran dari {bank_account.nama_bank if bank_account else 'Kas'}"
            )
            
            # Credit: Discount Received (if discount exists)
            if discount_decimal > 0:
                discount_account = get_or_create_account_by_code(
                    code='4-4000',
                    name='Discount Received',
                    account_type_code='4',
                    balance_type='CREDIT'
                )
                JournalEntryItem.objects.create(
                    journal_entry=journal_entry,
                    account=discount_account,
                    debit=Decimal('0'),
                    credit=discount_decimal,
                    description=f"Discount received dari {purchase.supplier.nama_supplier if purchase.supplier else 'Supplier'}"
                )
            
            return journal_entry
            
    except Exception as e:
        raise Exception(f"Error creating journal entry for purchase payment: {str(e)}")


def create_purchase_taxinvoice_journal_entry(purchase, tax_amount, user):
    """
    Create journal entry for Purchase Tax Invoice
    Debit: Tax Expense (or Inventory if included in cost)
    Credit: Tax Payable
    """
    try:
        with transaction.atomic():
            # Get or create accounts
            tax_expense_account = get_or_create_account_by_code(
                code='6-6000',
                name='Biaya Pajak',
                account_type_code='6',
                balance_type='DEBIT'
            )
            
            tax_payable_account = get_or_create_account_by_code(
                code='2-2100',
                name='Pajak Terutang',
                account_type_code='2',
                balance_type='CREDIT'
            )
            
            # Create journal entry
            journal_entry = JournalEntry.objects.create(
                entry_number=create_journal_entry_number("PT"),
                entry_date=timezone.now().date(),
                reference=purchase.nomor_purchase,
                description=f"Pajak Invoice Purchase {purchase.nomor_purchase}",
                status='posted',
                content_type=ContentType.objects.get_for_model(purchase),
                object_id=purchase.id,
                created_by=user,
                posted_by=user,
                posted_at=timezone.now()
            )
            
            # Create journal entry items
            tax_decimal = Decimal(str(tax_amount))
            
            # Debit: Tax Expense
            JournalEntryItem.objects.create(
                journal_entry=journal_entry,
                account=tax_expense_account,
                debit=tax_decimal,
                credit=Decimal('0'),
                description=f"Biaya pajak dari {purchase.supplier.nama_supplier if purchase.supplier else 'Supplier'}"
            )
            
            # Credit: Tax Payable
            JournalEntryItem.objects.create(
                journal_entry=journal_entry,
                account=tax_payable_account,
                debit=Decimal('0'),
                credit=tax_decimal,
                description=f"Pajak terutang dari {purchase.supplier.nama_supplier if purchase.supplier else 'Supplier'}"
            )
            
            return journal_entry
            
    except Exception as e:
        raise Exception(f"Error creating journal entry for purchase tax invoice: {str(e)}")


def create_purchase_receive_journal_entry(purchase, user):
    """
    Create journal entry for Purchase Receive (if needed)
    This might be called when purchase status changes to 'received'
    """
    try:
        with transaction.atomic():
            # Get or create accounts
            inventory_account = get_or_create_account_by_code(
                code='1-1200',
                name='Persediaan Barang',
                account_type_code='1',
                balance_type='DEBIT'
            )
            
            accounts_payable_account = get_or_create_account_by_code(
                code='2-2000',
                name='Hutang Usaha',
                account_type_code='2',
                balance_type='CREDIT'
            )
            
            # Create journal entry
            journal_entry = JournalEntry.objects.create(
                entry_number=create_journal_entry_number("PR"),
                entry_date=purchase.tanggal_purchase or timezone.now().date(),
                reference=purchase.nomor_purchase,
                description=f"Penerimaan Purchase {purchase.nomor_purchase}",
                status='posted',
                content_type=ContentType.objects.get_for_model(purchase),
                object_id=purchase.id,
                created_by=user,
                posted_by=user,
                posted_at=timezone.now()
            )
            
            # Create journal entry items
            total_amount = Decimal(str(purchase.total_amount))
            
            # Debit: Inventory
            JournalEntryItem.objects.create(
                journal_entry=journal_entry,
                account=inventory_account,
                debit=total_amount,
                credit=Decimal('0'),
                description=f"Penerimaan barang dari {purchase.supplier.nama_supplier if purchase.supplier else 'Supplier'}"
            )
            
            # Credit: Accounts Payable
            JournalEntryItem.objects.create(
                journal_entry=journal_entry,
                account=accounts_payable_account,
                debit=Decimal('0'),
                credit=total_amount,
                description=f"Hutang ke {purchase.supplier.nama_supplier if purchase.supplier else 'Supplier'}"
            )
            
            return journal_entry
            
    except Exception as e:
        raise Exception(f"Error creating journal entry for purchase receive: {str(e)}")

