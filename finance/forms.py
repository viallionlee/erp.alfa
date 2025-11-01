from django import forms
from django.core.exceptions import ValidationError
from .models import AccountType, Account, JournalEntry


class AccountTypeForm(forms.ModelForm):
    """Form for Account Type"""
    
    class Meta:
        model = AccountType
        fields = ['code', 'name', 'type', 'description', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 1, 2, 3'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Current Assets, Revenue Accounts'
            }),
            'type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Detailed description of this account type...'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.strip().upper()
            # Check for duplicates
            queryset = AccountType.objects.filter(code=code)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise ValidationError('Account type with this code already exists.')
        return code
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
        return name


class AccountForm(forms.ModelForm):
    """Form for Account"""
    
    class Meta:
        model = Account
        fields = ['code', 'name', 'account_type', 'parent', 'balance_type', 'description', 'notes', 'is_active', 'is_system']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 1-1000, 2-2000'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Cash, Accounts Receivable'
            }),
            'account_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'parent': forms.Select(attrs={
                'class': 'form-control'
            }),
            'balance_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Detailed description of this account...'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional notes...'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_system': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter parent accounts to exclude self and inactive accounts
        if self.instance.pk:
            self.fields['parent'].queryset = Account.objects.filter(
                is_active=True
            ).exclude(pk=self.instance.pk).order_by('code')
        else:
            self.fields['parent'].queryset = Account.objects.filter(
                is_active=True
            ).order_by('code')
        
        # Only show active account types
        self.fields['account_type'].queryset = AccountType.objects.filter(
            is_active=True
        ).order_by('code')
    
    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.strip().upper()
            # Check for duplicates
            queryset = Account.objects.filter(code=code)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise ValidationError('Account with this code already exists.')
        return code
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
        return name
    
    def clean(self):
        cleaned_data = super().clean()
        parent = cleaned_data.get('parent')
        account_type = cleaned_data.get('account_type')
        
        # Validate parent-child relationship
        if parent and account_type:
            if parent.account_type != account_type:
                raise ValidationError('Parent account must be of the same type.')
        
        return cleaned_data


class JournalEntryForm(forms.ModelForm):
    """Form for Journal Entry"""
    
    class Meta:
        model = JournalEntry
        fields = ['entry_date', 'reference', 'description', 'notes', 'status']
        widgets = {
            'entry_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'reference': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'PO, Invoice, etc.'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe the transaction...'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional notes...'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            })
        }
    
    def clean_description(self):
        description = self.cleaned_data.get('description')
        if description:
            description = description.strip()
        return description
    
    def clean_reference(self):
        reference = self.cleaned_data.get('reference')
        if reference:
            reference = reference.strip()
        return reference


class JournalEntryItemForm(forms.ModelForm):
    """Form for Journal Entry Item"""
    
    class Meta:
        model = JournalEntryItem
        fields = ['account', 'debit', 'credit', 'description']
        widgets = {
            'account': forms.Select(attrs={
                'class': 'form-control'
            }),
            'debit': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'credit': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Item description'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active accounts
        self.fields['account'].queryset = Account.objects.filter(
            is_active=True
        ).order_by('code')
    
    def clean(self):
        cleaned_data = super().clean()
        debit = cleaned_data.get('debit', 0)
        credit = cleaned_data.get('credit', 0)
        
        # Validate that only one of debit or credit is filled
        if debit > 0 and credit > 0:
            raise ValidationError('Cannot have both debit and credit amounts.')
        
        if debit == 0 and credit == 0:
            raise ValidationError('Either debit or credit must be greater than 0.')
        
        return cleaned_data


# Formset for Journal Entry Items
JournalEntryItemFormSet = forms.formset_factory(
    JournalEntryItemForm,
    extra=2,
    min_num=2,
    validate_min=True,
    can_delete=True
)



