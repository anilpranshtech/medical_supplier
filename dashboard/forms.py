from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth import get_user_model
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import PasswordResetForm as DjangoPasswordResetForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from .models import *


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)

    class Meta:
        fields = []  # To be set dynamically

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        profile_type = kwargs.pop('profile_type')
        super().__init__(*args, **kwargs)
        self.fields['first_name'].initial = user.first_name
        self.fields['last_name'].initial = user.last_name

        if profile_type == 'retailer':
            self.Meta.model = RetailProfile
            self.Meta.fields = ['age', 'medical_needs']
        elif profile_type == 'wholesaler':
            self.Meta.model = WholesaleBuyerProfile
            self.Meta.fields = ['phone', 'company_name', 'department']
        elif profile_type == 'supplier':
            self.Meta.model = SupplierProfile
            self.Meta.fields = ['company_name']

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            profile.save()
        return profile


class AddressForm(forms.ModelForm):
    class Meta:
        model = CustomerBillingAddress
        fields = [
            'address_title', 'customer_address1', 'customer_address2',
            'customer_city', 'customer_state', 'customer_postal_code',
            'customer_country', 'phone', 'is_default'
        ]


# class CustomerBillingAddressForm(forms.ModelForm):
#     class Meta:
#         model = CustomerBillingAddress
#         fields = [
#             'address_title', 'customer_name', 'customer_address1', 'customer_address2',
#             'phone', 'customer_city', 'customer_state', 'customer_postal_code',
#             'customer_country', 'customer_country_code', 'is_default'
#         ]
#         widgets = {
#             'address_title': forms.TextInput(attrs={'placeholder': 'e.g., Home, Office', 'class': 'kt-input'}),
#             'customer_name': forms.TextInput(attrs={'placeholder': 'Card Holder Name', 'class': 'kt-input'}),
#             'customer_address1': forms.TextInput(attrs={'placeholder': 'Street Address', 'class': 'kt-input'}),
#             'customer_address2': forms.TextInput(attrs={'placeholder': 'Apartment, Suite, etc.', 'class': 'kt-input'}),
#             'phone': forms.TextInput(attrs={'placeholder': '+1234567890', 'class': 'kt-input'}),
#             'customer_city': forms.TextInput(attrs={'placeholder': 'City', 'class': 'kt-input'}),
#             'customer_state': forms.TextInput(attrs={'placeholder': 'State', 'class': 'kt-input'}),
#             'customer_postal_code': forms.TextInput(attrs={'placeholder': 'Postal Code', 'class': 'kt-input'}),
#             'customer_country': forms.TextInput(attrs={'placeholder': 'Country', 'class': 'kt-input'}),
#             'customer_country_code': forms.TextInput(attrs={'placeholder': 'Country Code (e.g., US)', 'class': 'kt-input'}),
#             'is_default': forms.CheckboxInput(),
#         }
#
#     def __init__(self, *args, **kwargs):
#         self.user = kwargs.pop('user', None)
#         super().__init__(*args, **kwargs)
#
#     def clean(self):
#         cleaned_data = super().clean()
#         required_fields = ['customer_address1', 'customer_city', 'customer_state', 'customer_postal_code', 'customer_country', 'customer_country_code', 'phone']
#         for field in required_fields:
#             if not cleaned_data.get(field):
#                 self.add_error(field, 'This field is required.')
#         return cleaned_data
#
#     def save(self, commit=True):
#         instance = super().save(commit=False)
#         instance.user = self.user
#         if commit:
#             instance.save()
#         return instance


class EmailForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email']

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exclude(id=self.instance.id).exists():
            raise forms.ValidationError("This email address is already in use.")
        return email


class PhoneForm(forms.ModelForm):
    class Meta:
        model = CustomerBillingAddress
        fields = ['phone']


class RetailProfileForm(forms.ModelForm):
    class Meta:
        model = RetailProfile
        fields = ['profile_picture', 'current_position', 'workplace', 'nationality', 'residency', 'country_code', 'speciality',]
        widgets = {
            'profile_picture': forms.FileInput(),
            'current_position': forms.NumberInput(attrs={'placeholder': 'Enter your age'}),
            'workplace': forms.Textarea(attrs={'placeholder': 'Enter medical needs'}),
        }


class WholesaleBuyerProfileForm(forms.ModelForm):
    class Meta:
        model = WholesaleBuyerProfile
        fields = ['profile_picture', 'company_name', 'gst_number', 'department', 'purchase_capacity']
        widgets = {
            'profile_picture': forms.FileInput(),
            'company_name': forms.TextInput(attrs={'placeholder': 'Enter company name'}),
            'gst_number': forms.TextInput(attrs={'placeholder': 'Enter GST number'}),
            'department': forms.TextInput(attrs={'placeholder': 'Enter department'}),
            'purchase_capacity': forms.NumberInput(attrs={'placeholder': 'Enter monthly purchase capacity'}),
        }


class SupplierProfileForm(forms.ModelForm):
    class Meta:
        model = SupplierProfile
        fields = ['profile_picture', 'company_name', 'license_number']
        widgets = {
            'profile_picture': forms.FileInput(),
            'company_name': forms.TextInput(attrs={'placeholder': 'Enter company name'}),
            'license_number': forms.TextInput(attrs={'placeholder': 'Enter license number'}),
        }


class EmailOnlyLoginForm(AuthenticationForm):
    username = forms.CharField(label="Email") 

    def clean_username(self):
        username = self.cleaned_data['username']
        User = get_user_model()
        if '@' not in username:
            raise ValidationError("Please enter a valid email address")
        try:
            user = User.objects.get(email=username)
            return user.username  
        except User.DoesNotExist:
            raise ValidationError("No account found with this email")
        

class CustomPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        label='Email',
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'kt-input w-full mt-2',
            'placeholder': 'you@example.com',
            'required': 'required'
        })
    )


class CustomSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label='New password',
        widget=forms.PasswordInput(attrs={
            'class': 'kt-input w-full mt-2',
            'placeholder': 'Enter new password',
            'required': 'required'
        }),
    )
    new_password2 = forms.CharField(
        label='Confirm new password',
        widget=forms.PasswordInput(attrs={
            'class': 'kt-input w-full mt-2',
            'placeholder': 'Confirm new password',
            'required': 'required'
        }),
    )


class PaymentForm(forms.Form):
    name = forms.CharField(max_length=100)
    amount = forms.IntegerField(min_value=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            'name',
            'amount',
            Submit('submit', 'Buy', css_class='button white btn-block btn-primary'),
        )


class RFQRequestForm(forms.ModelForm):
    class Meta:
        model = RFQRequest
        fields = ['product', 'quantity', 'company_name', 'message']

class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['full_name', 'email', 'phone', 'subject', 'message']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'w-full p-3 border rounded'}),
            'email': forms.EmailInput(attrs={'class': 'w-full p-3 border rounded'}),
            'phone': forms.TextInput(attrs={'class': 'w-full p-3 border rounded'}),
            'subject': forms.TextInput(attrs={'class': 'w-full p-3 border rounded'}),
            'message': forms.Textarea(attrs={'class': 'w-full p-3 border rounded', 'rows': 5}),
        }