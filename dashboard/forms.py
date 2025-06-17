from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from django import forms
from django.core.exceptions import ValidationError

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
        
