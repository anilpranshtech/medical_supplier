from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth import get_user_model
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import PasswordResetForm as DjangoPasswordResetForm

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