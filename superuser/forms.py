from django import forms
from supplier.models import Banner  
from django import forms
from django.utils import timezone
from dashboard.models import RFQRequest

from dashboard.models import Notification
from django.contrib.auth.models import User
class BannerForm(forms.ModelForm):
    class Meta:
        model = Banner
        fields = ['title', 'image', 'link', 'is_active', 'order']

    def clean_order(self):
        order = self.cleaned_data.get('order')
        # Exclude the current instance (useful when editing)
        qs = Banner.objects.filter(order=order)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError(f"A banner with order {order} already exists. Please choose a different order.")
        return order


class SuperuserRFQQuotationForm(forms.ModelForm):
    class Meta:
        model = RFQRequest
        fields = [
            'quoted_price',
            'quote_delivery_date',
            'supplier_notes',
            'quote_attached_file',
        ]
        widgets = {
            'quote_delivery_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-lg form-control-solid'}),
            'supplier_notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control form-control-lg form-control-solid'}),
            'quote_attached_file': forms.ClearableFileInput(attrs={'class': 'form-control form-control-lg form-control-solid'}),
            'quoted_price': forms.NumberInput(attrs={'class': 'form-control form-control-lg form-control-solid', 'step': '0.01'}),
        }
        labels = {
            'quoted_price': 'Quoted Price',
            'quote_delivery_date': 'Expected Delivery Date',
            'supplier_notes': 'Notes',
            'quote_attached_file': 'Attachment (Optional)',
        }

    def clean_quote_delivery_date(self):
        delivery_date = self.cleaned_data['quote_delivery_date']
        if delivery_date and delivery_date < timezone.localdate():
            raise forms.ValidationError("Delivery date cannot be in the past.")
        return delivery_date


class NotificationForm(forms.ModelForm):
    class Meta:
        model = Notification
        fields = ["send_to", "recipient", "title", "message"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['recipient'].queryset = User.objects.all()
        self.fields['recipient'].required = False
