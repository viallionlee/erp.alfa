"""
Management command to setup Chart of Accounts for Purchase flow
"""
from django.core.management.base import BaseCommand
from finance.models import AccountType, Account


class Command(BaseCommand):
    help = 'Setup Chart of Accounts for Purchase flow'

    def handle(self, *args, **options):
        self.stdout.write('Setting up Chart of Accounts for Purchase flow...')
        
        # Create Account Types
        account_types = [
            {'code': '1', 'name': 'Aset', 'type': 'ASSET'},
            {'code': '2', 'name': 'Kewajiban', 'type': 'LIABILITY'},
            {'code': '6', 'name': 'Biaya', 'type': 'EXPENSE'},
        ]
        
        for acc_type_data in account_types:
            acc_type, created = AccountType.objects.get_or_create(
                code=acc_type_data['code'],
                defaults=acc_type_data
            )
            if created:
                self.stdout.write(f'Created account type: {acc_type}')
            else:
                self.stdout.write(f'Account type already exists: {acc_type}')
        
        # Create Accounts for Purchase flow
        accounts = [
            # Asset accounts
            {'code': '1-1100', 'name': 'Kas', 'account_type_code': '1', 'balance_type': 'DEBIT'},
            {'code': '1-1200', 'name': 'Persediaan Barang', 'account_type_code': '1', 'balance_type': 'DEBIT'},
            
            # Liability accounts
            {'code': '2-2000', 'name': 'Hutang Usaha', 'account_type_code': '2', 'balance_type': 'CREDIT'},
            {'code': '2-2100', 'name': 'Pajak Terutang', 'account_type_code': '2', 'balance_type': 'CREDIT'},
            
            # Expense accounts
            {'code': '6-6000', 'name': 'Biaya Pajak', 'account_type_code': '6', 'balance_type': 'DEBIT'},
        ]
        
        for acc_data in accounts:
            account_type = AccountType.objects.get(code=acc_data['account_type_code'])
            account, created = Account.objects.get_or_create(
                code=acc_data['code'],
                defaults={
                    'name': acc_data['name'],
                    'account_type': account_type,
                    'balance_type': acc_data['balance_type'],
                    'is_system': True
                }
            )
            if created:
                self.stdout.write(f'Created account: {account}')
            else:
                self.stdout.write(f'Account already exists: {account}')
        
        self.stdout.write(
            self.style.SUCCESS('Successfully setup Chart of Accounts for Purchase flow!')
        )


