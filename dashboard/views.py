from django.http import HttpResponse
from django.shortcuts import render,redirect
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from .forms import EmailOnlyLoginForm

def page(request):    
    return HttpResponse("Hello from home")

class CustomLoginView(LoginView):
    form_class = EmailOnlyLoginForm
    template_name = 'dashboard/login.html' 

    def get_success_url(self):
        return reverse_lazy('page')


 
   
