from django import forms
from .models import Inbound, InboundItem
from products.models import Product

class InboundForm(forms.ModelForm):
    class Meta:
        model = Inbound
        fields = ['nomor_inbound', 'tanggal', 'keterangan']
        widgets = {
            'tanggal': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.initial.get('tanggal') and isinstance(self.initial['tanggal'], str) is False:
            self.initial['tanggal'] = self.initial['tanggal'].strftime('%Y-%m-%dT%H:%M')
        self.fields['tanggal'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S']

class InboundItemForm(forms.ModelForm):
    class Meta:
        model = InboundItem
        fields = ['product', 'quantity']

# Formset untuk banyak item
InboundItemFormSet = forms.modelformset_factory(
    InboundItem,
    form=InboundItemForm,
    extra=0,
)
