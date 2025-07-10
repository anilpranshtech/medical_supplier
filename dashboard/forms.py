from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth import get_user_model
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import PasswordResetForm as DjangoPasswordResetForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from .models import *


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