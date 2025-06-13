from django.http import HttpResponse
from django.shortcuts import render,redirect
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from .forms import EmailOnlyLoginForm
from django.views import View
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from .models import DoctorProfile, MedicalSupplierProfile, CorporateProfile
from django.contrib import messages
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.hashers import make_password
from .models import RetailProfile, WholesaleBuyerProfile, SupplierProfile
from django.contrib.auth import authenticate, login
from django.views.generic.edit import FormView



class HomeView(TemplateView):
    template_name = 'dashboard/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context


class CustomLoginView(FormView):
    form_class = EmailOnlyLoginForm
    template_name = 'dashboard/login.html'
    
    def form_valid(self, form):
        email = form.cleaned_data['username'] 
        password = form.cleaned_data['password']
        user_type = self.request.POST.get('user_type') 
        buyer_type = self.request.POST.get('buyer_type') 
        

        user = authenticate(username=email, password=password)
        
        if user is not None:
            if user_type == 'supplier':
                if not hasattr(user, 'supplierprofile'):
                    form.add_error(None, "This account is not registered as a supplier.")
                    return self.form_invalid(form)
            elif user_type == 'buyer':
                if buyer_type == 'retailer' and not hasattr(user, 'retailprofile'):
                    form.add_error(None, "This account is not registered as a retailer.")
                    return self.form_invalid(form)
                elif buyer_type == 'wholesaler' and not hasattr(user, 'wholesalebuyerprofile'):
                    form.add_error(None, "This account is not registered as a wholesaler.")
                    return self.form_invalid(form)

            login(self.request, user)
            if user_type == 'supplier':
                self.request.session['user_role'] = 'supplier'
            else:
                self.request.session['user_role'] = buyer_type 
            
            return redirect(self.get_success_url())
        else:
            form.add_error(None, "Invalid email or password.")
            return self.form_invalid(form)
    
    def get_success_url(self):
        return reverse_lazy('home')
import requests
class RegistrationView(View):
    template_name = "dashboard/register.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):

    
        recaptcha_response = request.POST.get('g-recaptcha-response')
        recaptcha_secret = '6LdTHV8rAAAAAIgLr2wdtdtWExTS6xJpUpD8qEzh' 

        recaptcha_result = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': recaptcha_secret,
                'response': recaptcha_response
            }
        ).json()

        if not recaptcha_result.get('success'):
            messages.error(request, 'Invalid reCAPTCHA. Please try again.')
            return render(request, self.template_name)
        
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type')  
        buyer_type = request.POST.get('buyer_type')

        try:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            # Supplier
            if user_type == 'supplier':
                company_name = request.POST.get('supplier_company_name')
                license_number = request.POST.get('license_number')
                SupplierProfile.objects.create(
                    user=user,
                    company_name=company_name,
                    license_number=license_number
                )
                messages.success(request, "Supplier account created successfully.")

            # Retail buyer
            elif buyer_type == 'retailer':
                try:
                    age = int(request.POST.get('age') or 0)
                except ValueError:
                    age = 0
                medical_needs = request.POST.get('medical_needs') or ''
                RetailProfile.objects.create(
                    user=user,
                    age=age,
                    medical_needs=medical_needs
                )
                messages.success(request, "Retailer user created. Please update your profile.")

            # Wholesale buyer
            elif user_type == 'wholesale' or buyer_type == 'wholesaler':
                company_name = request.POST.get('company_name')
                gst_number = request.POST.get('gst_number')
                department = request.POST.get('department')
                purchase_capacity = request.POST.get('purchase_capacity')
                WholesaleBuyerProfile.objects.create(
                    user=user,
                    company_name=company_name,
                    gst_number=gst_number,
                    department=department,
                    purchase_capacity=purchase_capacity
                )
                messages.success(request, "Wholesaler account created successfully.")

            else:
                messages.error(request, "Invalid user type.")
                user.delete()
                return render(request, self.template_name)

            return redirect('login')

        except Exception as e:
            messages.error(request, f"An error occurred: {e}")
            return render(request, self.template_name)
        
class UserProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        profile = None
        profile_type = None

        if hasattr(user, 'supplierprofile'):
            profile = user.supplierprofile
            profile_type = 'supplier'
        elif hasattr(user, 'retailprofile'):
            profile = user.retailprofile
            profile_type = 'retailer'
        elif hasattr(user, 'wholesalebuyerprofile'):
            profile = user.wholesalebuyerprofile
            profile_type = 'wholesaler'

        context['user'] = user
        context['profile'] = profile
        context['profile_type'] = profile_type
        return context


class UploadProfilePictureView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        profile = None

        if hasattr(request.user, 'supplierprofile'):
            profile = request.user.supplierprofile
        elif hasattr(request.user, 'retailprofile'):
            profile = request.user.retailprofile
        elif hasattr(request.user, 'wholesalebuyerprofile'):
            profile = request.user.wholesalebuyerprofile

        if profile and 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']
            profile.save()

        return redirect('profile')
