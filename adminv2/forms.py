from django import forms
from dashboard.models import RFQRequest
from .models import *

class SupplierRFQQuotationForm(forms.ModelForm):
    class Meta:
        model = RFQRequest
        fields = [
            'quoted_price',
            'quote_delivery_date',
            'supplier_notes',
            'quote_attached_file',
        ]
        widgets = {
            'quote_delivery_date': forms.DateInput(attrs={'type': 'date'}),
            'supplier_notes': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'quoted_price': 'Quoted Price',
            'quote_delivery_date': 'Expected Delivery Date',
            'supplier_notes': 'Additional Notes',
            'quote_attached_file': 'Attach Quotation File',
        }


class BannerForm(forms.ModelForm):
    class Meta:
        model = Banner
        fields = ['title', 'image', 'link', 'is_active', 'order']