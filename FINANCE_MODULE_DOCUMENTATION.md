# Finance Module Documentation

## Overview
Finance Module adalah modul keuangan lengkap untuk ERP ALFA yang mencakup Chart of Accounts, Journal Entries, Cash Flow Management, Budget Management, dan Financial Reports.

## Features

### 1. Chart of Accounts
- **Account Types**: Asset, Liability, Equity, Revenue, Expense, Cost of Sales
- **Account Hierarchy**: Support parent-child relationship
- **Balance Types**: Debit dan Credit
- **Real-time Balance**: Otomatis menghitung saldo akun dari journal entries

### 2. Journal Entries
- **Dual Entry System**: Debit = Credit (balanced)
- **Auto-numbering**: JE-YYYYMMDD-XXXX
- **Status Management**: Draft → Posted → Reversed
- **Link to Other Modules**: Generic Foreign Key untuk link ke Purchase, Order, dll
- **Validation**: Auto-check balance sebelum posting

### 3. Cash Flow Management
- **Categories**: Operating, Investing, Financing
- **Flow Types**: Inflow (+) dan Outflow (-)
- **Period Tracking**: Filter by date range
- **Summary Reports**: Total inflow, outflow, net cash flow

### 4. Budget Management
- **Period Types**: Monthly, Quarterly, Yearly
- **Status Workflow**: Draft → Approved → Active → Closed
- **Variance Tracking**: Budget vs Actual
- **Utilization Percentage**: Persentase penggunaan budget
- **Auto-calculation**: Actual amount dari journal entries

### 5. Financial Reports
- **Trial Balance**: Daftar saldo semua akun
- **Profit & Loss Statement**: Revenue, COS, Expenses, Net Income
- **Balance Sheet**: Assets = Liabilities + Equity
- **Date Range Filter**: Custom period reporting

## Models

### AccountType
```python
- code: Kode tipe akun (contoh: 1, 2, 3)
- name: Nama tipe akun
- type: ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE, COST_OF_SALES
- is_active: Boolean
```

### Account
```python
- code: Kode akun (contoh: 1-1000, 2-2000)
- name: Nama akun
- account_type: ForeignKey ke AccountType
- parent: ForeignKey ke Account (untuk hierarki)
- balance_type: DEBIT atau CREDIT
- is_active: Boolean
- is_system: Boolean (untuk akun sistem)
```

### JournalEntry
```python
- entry_number: Auto-generated (JE-YYYYMMDD-XXXX)
- entry_date: Tanggal entry
- reference: No. referensi (PO, Invoice, dll)
- description: Keterangan
- status: draft, posted, reversed, cancelled
- content_type, object_id: Generic FK untuk link ke transaksi lain
- created_by, posted_by: User tracking
```

### JournalEntryItem
```python
- journal_entry: ForeignKey ke JournalEntry
- account: ForeignKey ke Account
- debit: Jumlah debit (Rp)
- credit: Jumlah credit (Rp)
- description: Keterangan item
```

### CashFlow
```python
- transaction_date: Tanggal transaksi
- category: OPERATING, INVESTING, FINANCING
- flow_type: INFLOW atau OUTFLOW
- account: ForeignKey ke Account
- amount: Jumlah (Rp)
- description: Keterangan
- reference: No. referensi
```

### Budget
```python
- name: Nama budget
- account: ForeignKey ke Account
- period_type: MONTHLY, QUARTERLY, YEARLY
- period_start, period_end: Periode budget
- budget_amount: Jumlah budget (Rp)
- status: draft, approved, active, closed
- approved_by: User yang approve
```

### FinancialReport
```python
- report_name: Nama report
- report_type: PROFIT_LOSS, BALANCE_SHEET, CASH_FLOW, TRIAL_BALANCE, GENERAL_LEDGER
- period_type: DAILY, WEEKLY, MONTHLY, QUARTERLY, YEARLY, CUSTOM
- period_start, period_end: Periode report
- report_data: JSON data
- pdf_file, excel_file: File export
- is_generated: Boolean
```

## URLs

### Dashboard
- `/finance/` - Finance Dashboard

### Chart of Accounts
- `/finance/accounts/` - Chart of Accounts List
- `/finance/accounts/<id>/` - Account Detail

### Journal Entries
- `/finance/journal-entries/` - Journal Entry List
- `/finance/journal-entries/create/` - Create Journal Entry
- `/finance/journal-entries/<id>/` - Journal Entry Detail
- `/finance/journal-entries/<id>/post/` - Post Journal Entry
- `/finance/journal-entries/<id>/reverse/` - Reverse Journal Entry

### Cash Flow
- `/finance/cash-flow/` - Cash Flow List
- `/finance/cash-flow/create/` - Create Cash Flow

### Budget
- `/finance/budget/` - Budget List
- `/finance/budget/create/` - Create Budget
- `/finance/budget/<id>/` - Budget Detail
- `/finance/budget/<id>/approve/` - Approve Budget

### Financial Reports
- `/finance/reports/` - Financial Reports List
- `/finance/reports/trial-balance/` - Trial Balance
- `/finance/reports/profit-loss/` - Profit & Loss Statement
- `/finance/reports/balance-sheet/` - Balance Sheet

## Usage

### 1. Setup Chart of Accounts

Pertama, buat Account Types di Admin:
1. Login ke Django Admin
2. Go to Finance > Account Types
3. Create account types: Asset, Liability, Equity, Revenue, Expense, Cost of Sales

Kemudian, buat Accounts:
1. Go to Finance > Accounts
2. Create accounts berdasarkan Account Types
3. Set balance_type (DEBIT untuk Asset/Expense, CREDIT untuk Liability/Equity/Revenue)

### 2. Create Journal Entry

```python
from finance.models import JournalEntry, JournalEntryItem
from accounts.models import Account

# Create journal entry
entry = JournalEntry.objects.create(
    entry_date='2024-01-15',
    description='Pembelian barang',
    created_by=request.user
)

# Add items
JournalEntryItem.objects.create(
    journal_entry=entry,
    account=Account.objects.get(code='1-1000'),  # Cash
    debit=1000000,
    credit=0,
    description='Kas keluar'
)

JournalEntryItem.objects.create(
    journal_entry=entry,
    account=Account.objects.get(code='5-1000'),  # Inventory
    debit=0,
    credit=1000000,
    description='Inventory masuk'
)

# Post journal entry
entry.post(request.user)
```

### 3. Create Cash Flow

```python
from finance.models import CashFlow

CashFlow.objects.create(
    transaction_date='2024-01-15',
    category='OPERATING',
    flow_type='OUTFLOW',
    account=Account.objects.get(code='1-1000'),
    amount=1000000,
    description='Pembayaran supplier',
    created_by=request.user
)
```

### 4. Create Budget

```python
from finance.models import Budget

Budget.objects.create(
    name='Budget Marketing Januari 2024',
    account=Account.objects.get(code='6-1000'),  # Marketing Expense
    period_type='MONTHLY',
    period_start='2024-01-01',
    period_end='2024-01-31',
    budget_amount=5000000,
    status='draft',
    created_by=request.user
)

# Approve budget
budget.status = 'approved'
budget.approved_by = request.user
budget.save()
```

### 5. Generate Financial Reports

Akses via web interface:
- Trial Balance: `/finance/reports/trial-balance/?date_to=2024-01-31`
- P&L Statement: `/finance/reports/profit-loss/?date_from=2024-01-01&date_to=2024-01-31`
- Balance Sheet: `/finance/reports/balance-sheet/?date=2024-01-31`

## Integration with Other Modules

### Link Journal Entry to Purchase
```python
from finance.models import JournalEntry
from purchasing.models import Purchase

purchase = Purchase.objects.get(nomor_purchase='PUR-20240101-0001')

# Create journal entry linked to purchase
entry = JournalEntry.objects.create(
    entry_date=purchase.tanggal_purchase,
    reference=purchase.nomor_purchase,
    description=f'Goods receipt: {purchase.nomor_purchase}',
    content_type=ContentType.objects.get_for_model(Purchase),
    object_id=purchase.id,
    created_by=request.user
)

# Add items...
```

### Link Cash Flow to Purchase Payment
```python
from finance.models import CashFlow
from purchasing.models import PurchasePayment

payment = PurchasePayment.objects.get(id=1)

CashFlow.objects.create(
    transaction_date=payment.payment_date,
    category='OPERATING',
    flow_type='OUTFLOW',
    account=Account.objects.get(code='1-1000'),  # Cash
    amount=payment.paid_amount,
    description=f'Payment to {payment.supplier.nama_supplier}',
    reference=payment.purchase.nomor_purchase,
    content_type=ContentType.objects.get_for_model(PurchasePayment),
    object_id=payment.id,
    created_by=request.user
)
```

### Purchasing Journal Flow (Accurate style)

| Step | Scenario | Debit | Credit | Notes |
|---|---|---|---|---|
| Receive | Goods received (no vendor invoice yet) | Inventory (1303001) | GRNI – Goods Received Not Invoiced (2103xxx) | Stock increases; AP not booked |
| Verify | Got Tax Invoice | GRNI (2103xxx) = DPP; Deferred Input VAT (1206002) = VAT | Accounts Payable (2103001) = DPP + VAT | AP booked; VAT parked |
| Verify | No Tax Invoice | GRNI (2103xxx) | Accounts Payable (2103001) | AP booked without VAT |
| Tax Invoice Received | Reclass VAT | Input VAT (1206001) | Deferred Input VAT (1206002) | Move VAT from deferred to claimable |
| Payment | Pay supplier | Accounts Payable (2103001) | Cash/Bank (1110001) + Purchase Discount (5103001) if any | Split discount if applicable |

Catatan:
- GRNI selalu menutup nilai DPP saat Verify.
- Reklas VAT hanya berlaku jika saat Verify menggunakan Deferred Input VAT.

## Permissions

Finance module menggunakan Django's built-in permission system. Tambahkan permissions di admin:

```python
# Contoh permissions
('finance_view', 'Can view Finance Module'),
('finance_create_journal', 'Can create Journal Entry'),
('finance_post_journal', 'Can post Journal Entry'),
('finance_create_budget', 'Can create Budget'),
('finance_approve_budget', 'Can approve Budget'),
('finance_view_reports', 'Can view Financial Reports'),
```

## Best Practices

1. **Always Post Journal Entries**: Jangan biarkan journal entry di status draft terlalu lama
2. **Check Balance**: Pastikan debit = credit sebelum posting
3. **Use References**: Selalu isi reference untuk tracking
4. **Link Transactions**: Gunakan Generic FK untuk link ke transaksi lain
5. **Regular Reports**: Generate financial reports secara berkala
6. **Budget Monitoring**: Monitor budget utilization untuk kontrol

## Troubleshooting

### Trial Balance Tidak Balance
- Cek apakah ada journal entry yang debit != credit
- Cek apakah ada journal entry yang belum di-post
- Cek apakah ada account yang balance_type salah

### Budget Variance Besar
- Review actual spending vs budget
- Cek apakah ada expense yang tidak terduga
- Update budget jika perlu

### Cash Flow Negative
- Review cash outflow vs inflow
- Cek apakah ada payment yang besar
- Monitor payment schedule

## Future Enhancements

1. **Auto Journal Entry**: Auto-create journal entry dari Purchase/Order
2. **Budget Alerts**: Alert jika budget sudah 80% terpakai
3. **Export to Excel/PDF**: Export reports ke Excel/PDF
4. **Dashboard Widgets**: Custom dashboard widgets
5. **Multi-currency**: Support multiple currencies
6. **Tax Calculation**: Auto-calculate PPN, PPh, dll
7. **Bank Reconciliation**: Reconcile bank statements
8. **Financial Forecasting**: Budget vs forecast comparison

## Support

Untuk pertanyaan atau issues, hubungi tim development.

---

**Created**: January 2024  
**Version**: 1.0.0  
**Author**: ERP ALFA Development Team




