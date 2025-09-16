from django import forms
from dashboard.models import RFQRequest,SupplierProfile,ProductCategory
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


class UserInformationForm(forms.ModelForm):
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    profile_picture = forms.ImageField(required=True)
    phone = forms.CharField(required=True)
    job_title = forms.CharField(required=True)
    supplier_type = forms.CharField(required=True)
    are_you_buyer_b2b = forms.ChoiceField(
        choices=[('yes', 'Yes'), ('no', 'No')],
        required=True,

    )
    selling_for = forms.CharField(required=True)
    meta_description = forms.CharField(required=True, widget=forms.Textarea)
    meta_keywords = forms.CharField(required=True, widget=forms.Textarea)

    class Meta:
        model = SupplierProfile
        fields = [
            "profile_picture",
            "phone",
            "job_title",
            "supplier_type",
            "are_you_buyer_b2b",
            "selling_for",
            "meta_description",
            "meta_keywords",
        ]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial = user.last_name
            self.fields["email"].initial = user.email


class BusinessInformationForm(forms.ModelForm):
    class Meta:
        model = SupplierProfile
        fields = [
            "business_name",
            "company_logo",
            "registration_number",
            "company_commercial_license",
            "authorized_person_name",
            "iso_certificate",
            "export_import_license",
        ]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True
            
class BankDetailsForm(forms.ModelForm):
    class Meta:
        model = SupplierProfile
        fields = [
            "account_holder_name",
            "account_number",
            "iban_code",
            "iban_certificate",
            "bank_name",
            "swift_code",
        ]
class SellingCategoriesForm(forms.ModelForm):
    selling_categories = forms.ModelMultipleChoiceField(
        queryset=ProductCategory.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = SupplierProfile
        fields = ["selling_categories"]


class SupplierDescriptionForm(forms.ModelForm):
    class Meta:
        model = SupplierProfile
        fields = [
            "facebook", "instagram", "twitter", "google_page", "linkedin",
            "short_description", "shipping_and_payment_terms",
            "return_policy", "banner"
        ]

class PickupandShipping(forms.ModelForm):
    class Meta:
        model = SupplierProfile
        fields = [
            "country", "state", "city", "zip_code", "support_pickup"
        ]
        widgets = {
            "country": forms.Select(attrs={"class": "form-control"}),
            "state": forms.Select(attrs={"class": "form-control"}),
            "city": forms.Select(attrs={"class": "form-control"}),
            "zip_code": forms.TextInput(attrs={"class": "form-control"}),
            "support_pickup": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

class SupplierDocumentsForm(forms.ModelForm):
    class Meta:
        model = SupplierProfile
        fields = [
            "signature_authority_doc",
            "memorandum_of_association",
            "ce_certificate",
            "fda_certificate",
            "other_certificate_1",
            "other_certificate_2",
            "other_supporting_doc_1",
            "other_supporting_doc_2",
            "other_supporting_doc_3",
        ]
class SupplierStatusForm(forms.ModelForm):
    class Meta:
        model = SupplierProfile
        fields = ['current_status', 'request_for', 'equest_reason'] 
        widgets = {
            'current_status': forms.Select(attrs={'class': 'form-control'}),
            'request_for': forms.Select(attrs={'class': 'form-control'}),
            'equest_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
