from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal

from finance.models import AccountType, Account


class Command(BaseCommand):
    help = "Seed Account Types and Chart of Accounts starter pack (inspired by Accurate)."

    @transaction.atomic
    def handle(self, *args, **options):
        # Account Type seeds (code follows common numbering)
        type_specs = [
            {"code": "1", "name": "Assets", "type": "ASSET"},
            {"code": "2", "name": "Liabilities", "type": "LIABILITY"},
            {"code": "3", "name": "Equity", "type": "EQUITY"},
            {"code": "4", "name": "Revenue", "type": "REVENUE"},
            {"code": "5", "name": "Cost of Sales", "type": "COST_OF_SALES"},
            {"code": "6", "name": "Expenses", "type": "EXPENSE"},
        ]

        code_to_type = {}
        for spec in type_specs:
            obj, created = AccountType.objects.get_or_create(
                code=spec["code"],
                defaults={
                    "name": spec["name"],
                    "type": spec["type"],
                    "is_active": True,
                },
            )
            if not created:
                # keep existing name/type but ensure active
                obj.is_active = True
                obj.save(update_fields=["is_active"])
            code_to_type[spec["type"]] = obj

        # Chart of Accounts starter pack (simplified Accurate style)
        # balance_type: Assets/Expenses/Cost of Sales => DEBIT; Liabilities/Equity/Revenue => CREDIT
        accounts = [
            # Assets
            ("1000", "Cash", "ASSET", "DEBIT"),
            ("1010", "Bank", "ASSET", "DEBIT"),
            ("1100", "Accounts Receivable", "ASSET", "DEBIT"),
            ("1200", "Inventory", "ASSET", "DEBIT"),
            ("1300", "Prepaid Expenses", "ASSET", "DEBIT"),

            # Liabilities
            ("2000", "Accounts Payable", "LIABILITY", "CREDIT"),
            ("2100", "Tax Payable", "LIABILITY", "CREDIT"),
            ("2200", "Accrued Expenses", "LIABILITY", "CREDIT"),

            # Equity
            ("3000", "Owner's Equity", "EQUITY", "CREDIT"),
            ("3100", "Retained Earnings", "EQUITY", "CREDIT"),

            # Revenue
            ("4000", "Sales Revenue", "REVENUE", "CREDIT"),
            ("4100", "Other Income", "REVENUE", "CREDIT"),

            # Cost of Sales
            ("5000", "Cost of Goods Sold", "COST_OF_SALES", "DEBIT"),

            # Expenses (operating)
            ("6000", "Rent Expense", "EXPENSE", "DEBIT"),
            ("6100", "Utilities Expense", "EXPENSE", "DEBIT"),
            ("6200", "Salary Expense", "EXPENSE", "DEBIT"),
            ("6300", "Office Supplies Expense", "EXPENSE", "DEBIT"),
            ("6400", "Depreciation Expense", "EXPENSE", "DEBIT"),
        ]

        created_count = 0
        for code, name, atype, bal_type in accounts:
            account_type_obj = code_to_type[atype]
            acc, created = Account.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "account_type": account_type_obj,
                    "balance_type": bal_type,
                    "is_active": True,
                    "is_system": True,
                },
            )
            if created:
                created_count += 1
            else:
                # ensure mapping is consistent if it already exists
                changed = False
                if acc.account_type_id != account_type_obj.id:
                    acc.account_type = account_type_obj
                    changed = True
                if acc.balance_type != bal_type:
                    acc.balance_type = bal_type
                    changed = True
                if not acc.is_system:
                    acc.is_system = True
                    changed = True
                if changed:
                    acc.save()

        self.stdout.write(self.style.SUCCESS(
            f"Starter pack seeded. Account types: {len(type_specs)}, accounts created: {created_count}."
        ))




