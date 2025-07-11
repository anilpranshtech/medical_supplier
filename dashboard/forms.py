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

        if profile_type == 'doctor':
            self.Meta.model = DoctorProfile
            self.Meta.fields = ['phone_number', 'speciality', 'current_position', 'workplace']
        elif profile_type == 'medical_supplier':
            self.Meta.model = MedicalSupplierProfile
            self.Meta.fields = ['phone_details', 'company_name', 'workplace']
        elif profile_type == 'corporate':
            self.Meta.model = CorporateProfile
            self.Meta.fields = ['phone', 'company_name', 'department']
        elif profile_type == 'retailer':
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
            'customer_address1', 'customer_address2',
            'customer_city', 'customer_state', 'customer_postal_code',
            'customer_country'
        ]


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

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if not phone.startswith('+'):
            raise forms.ValidationError("Phone number must start with '+' followed by country code.")
        return phone


class RetailProfileForm(forms.ModelForm):
    class Meta:
        model = RetailProfile
        fields = ['profile_picture', 'age', 'medical_needs']
        widgets = {
            'profile_picture': forms.FileInput(),
            'age': forms.NumberInput(attrs={'placeholder': 'Enter your age'}),
            'medical_needs': forms.Textarea(attrs={'placeholder': 'Enter medical needs'}),
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