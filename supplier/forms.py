from django import forms
from dashboard.models import RFQRequest,SupplierProfile,ProductCategory
from .models import *
import re

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
    profile_picture = forms.ImageField(
        required=True,
        widget=forms.FileInput(attrs={"class": "form-control"})  
    )
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
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})

    def clean_first_name(self):
        first_name = self.cleaned_data.get("first_name")
        if not re.match(r'^[A-Za-z]+$', first_name):
            raise forms.ValidationError("First name should only contain letters.")
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get("last_name")
        if not re.match(r'^[A-Za-z]+$', last_name):
            raise forms.ValidationError("Last name should only contain letters.")
        return last_name

    def clean_job_title(self):
        job_title = self.cleaned_data.get("job_title")
        if not re.match(r'^[A-Za-z ]+$', job_title): 
            raise forms.ValidationError("Job title should only contain letters.")
        return job_title
    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if not phone.isdigit():
            raise forms.ValidationError("Phone number should only contain digits.")
        return phone



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

        # Add CSS class for all inputs
        for field_name, field in self.fields.items():
            field.widget.attrs.update({"class": "form-control"})
            
    def clean_registration_number(self):
        value = self.cleaned_data.get("registration_number")
        if not value.isdigit():
            raise forms.ValidationError("Registration number must contain digits only.")
        return value
    def clean_registration_number(self):
        value = self.cleaned_data.get("registration_number")

        if not value.isdigit():
            raise forms.ValidationError("Registration number must contain digits only.")

        if "0" in value:
            raise forms.ValidationError("Registration number cannot contain 0.")

        return value
            
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
        widgets = {
            "iban_certificate": forms.FileInput(attrs={"class": "form-control"}),  # 👈 override here
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({"class": "form-control"})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.required = True
            field.widget.attrs.update({"class": "form-control"})
    def clean_account_holder_name(self):
        value = self.cleaned_data.get("account_holder_name", "").strip()
        if not re.match(r"^[A-Za-z\s]+$", value):
            raise forms.ValidationError("Account holder name must contain only letters.")
        return value
    def clean_bank_name(self):
        value = self.cleaned_data.get("bank_name", "").strip()
        if not re.match(r"^[A-Za-z\s]+$", value):
            raise forms.ValidationError("Bank name must contain only letters.")
        return value
    def clean_account_number(self):
        value = self.cleaned_data.get("account_number", "")
        if not value.isdigit():
            raise forms.ValidationError("Account number must contain digits only.")
        if "0" in value:
            raise forms.ValidationError("Account number cannot contain 0.")
        return value
    def clean_iban_code(self):
        value = self.cleaned_data.get("iban_code", "")
        if not value.isdigit():
            raise forms.ValidationError("IBAN code must contain digits only.")
        if "0" in value:
            raise forms.ValidationError("IBAN code cannot contain 0.")
        return value

    def clean_swift_code(self):
        value = self.cleaned_data.get("swift_code", "")
        if not value.isdigit():
            raise forms.ValidationError("Swift code must contain digits only.")
        if "0" in value:
            raise forms.ValidationError("Swift code cannot contain 0.")
        return value

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
        widgets = {
            "banner": forms.FileInput(attrs={"class": "form-control"}), 
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({"class": "form-control"})

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.required = True
    def clean_zip_code(self):
        value = self.cleaned_data.get("zip_code", "").strip()
        if not value.isdigit():
            raise forms.ValidationError("Zip code must contain digits only.")
        if value == "0":
           raise forms.ValidationError("Zip code cannot be 0.")
        return value

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
        widgets = {
            "signature_authority_doc": forms.FileInput(attrs={"class": "form-control"}),
            "memorandum_of_association": forms.FileInput(attrs={"class": "form-control"}),
            "ce_certificate": forms.FileInput(attrs={"class": "form-control"}),
            "fda_certificate": forms.FileInput(attrs={"class": "form-control"}),
            "other_certificate_1": forms.FileInput(attrs={"class": "form-control"}),
            "other_certificate_2": forms.FileInput(attrs={"class": "form-control"}),
            "other_supporting_doc_1": forms.FileInput(attrs={"class": "form-control"}),
            "other_supporting_doc_2": forms.FileInput(attrs={"class": "form-control"}),
            "other_supporting_doc_3": forms.FileInput(attrs={"class": "form-control"}),
        }
            
class SupplierStatusForm(forms.ModelForm):
    class Meta:
        model = SupplierProfile
        fields = ['current_status', 'request_for', 'equest_reason'] 
        widgets = {
            'current_status': forms.Select(attrs={'class': 'form-control'}),
            'request_for': forms.Select(attrs={'class': 'form-control'}),
            'equest_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
