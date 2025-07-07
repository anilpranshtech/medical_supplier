from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.views import LoginView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, \
    PasswordResetCompleteView
from django.urls import reverse_lazy

from djapp.settings import TEXTDRIP_OTP_TOKEN
from utils.handle_textdrip_otp import send_phone_otp, verify_mobile_otp
from .forms import EmailOnlyLoginForm, CustomPasswordResetForm, CustomSetPasswordForm
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
from .models import *
from datetime import date
from django.db.models import F
import random


class HomeView(TemplateView):
    template_name = 'dashboard/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        today = date.today()

        # Special Offers
        special_offers = Product.objects.filter(
            offer_active=True,
            offer_percentage__gt=0,
            offer_start__lte=today,
            offer_end__gte=today,
            is_active=True
        ).order_by('-offer_percentage')[:3]

        for product in special_offers:
            main_img = ProductImage.objects.filter(product=product, is_main=True).first()
            product.main_image = main_img.image.url if main_img else None
        context['special_offers'] = special_offers

        # New Arrivals
        recent_products = Product.objects.filter(
            tag='recent',
            is_active=True
        ).order_by('-created_at')[:4]

        for product in recent_products:
            main_img = ProductImage.objects.filter(product=product, is_main=True).first()
            product.main_image = main_img.image.url if main_img else None

        context['recent_products'] = recent_products

         # ✅ Popular Medical Supplies
        popular_products = Product.objects.filter(
            tag='popular',
            is_active=True
        ).order_by('-created_at')[:4]
        for product in popular_products:
            main_img = ProductImage.objects.filter(product=product, is_main=True).first()
            product.main_image = main_img.image.url if main_img else None
        context['popular_products'] = popular_products

        # ✅ Limited-Time Deals
        limited_products = Product.objects.filter(
            tag='limited',
            is_active=True
        ).order_by('-created_at')[:4]
        for product in limited_products:
            main_img = ProductImage.objects.filter(product=product, is_main=True).first()
            product.main_image = main_img.image.url if main_img else None
        context['limited_products'] = limited_products

        
        # ✅ Featured Products - Random 7 each refresh
        all_ids = list(Product.objects.filter(is_active=True).values_list('id', flat=True))
        random_ids = random.sample(all_ids, min(len(all_ids), 7))
        featured_products = Product.objects.filter(id__in=random_ids)

        for product in featured_products:
            main_img = ProductImage.objects.filter(product=product, is_main=True).first()
            product.main_image = main_img.image.url if main_img else None
        context['featured_products'] = featured_products

         # Add wishlist info if user is authenticated
        if self.request.user.is_authenticated:
            context['user_wishlist_ids'] = list(
                WishlistProduct.objects.filter(user=self.request.user)
                .values_list('product_id', flat=True)
            )
        else:
            context['user_wishlist_ids'] = []
        
        

        return context

class CustomLoginView(FormView):
    form_class = EmailOnlyLoginForm
    template_name = 'auth/login.html'

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
    template_name = "auth/signup.html"

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


# ------------------------------------------------------------------------------------------------------------------------
class SearchResultsGridView(TemplateView):
    template_name = 'userdashboard/view/search-results-grid.html'


class SearchResultsListView(TemplateView):
    template_name = 'userdashboard/view/search-results-list.html'


class ProductDetailsView(TemplateView):
    template_name = 'userdashboard/view/product-details.html'


class ShoppingCartView(TemplateView):
    template_name = 'userdashboard/view/shopping-cart.html'


class WishlistView(TemplateView):
    template_name = 'userdashboard/view/wishlist.html'


class OrderSummaryView(TemplateView):
    template_name = 'userdashboard/view/order-summary.html'


class ShippingInfoView(TemplateView):
    template_name = 'userdashboard/view/shipping-info.html'


class PaymentMethodView(TemplateView):
    template_name = 'userdashboard/view/payment-method.html'


class OrderPlacedView(TemplateView):
    template_name = 'userdashboard/view/order-placed.html'


class MyOrdersView(TemplateView):
    template_name = 'userdashboard/view/my-orders.html'


class OrderReceiptView(TemplateView):
    template_name = 'userdashboard/view/order-receipt.html'



class UserProfile(LoginRequiredMixin, TemplateView):
    template_name = 'pages/user_profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user  
        context['user'] = user
        return context


VERIFY_URL = "https://api.textdrip.com/api/v1/email-otp"

class SignUpView(View):
    def get(self, request):
        return render(request, 'userdashboard/auth/sign-up.html')

    def post(self, request):
        email = request.POST.get('user_email')
        password = request.POST.get('user_password')
        confirm_password = request.POST.get('confirm_password')
        phone = request.POST.get('phone')  # You can add a phone field to the HTML

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('dashboard:user_signup')

        otp_response = send_phone_otp(phone, TEXTDRIP_OTP_TOKEN)
        if "error" in otp_response:
            messages.error(request, otp_response["error"])
            return redirect('dashboard:user_signup')

        request.session['signup_data'] = {
            'email': email,
            'password': password,
            'phone': phone
        }
        return redirect('dashboard:verify_otp')


class VerifyOTPView(View):
    def get(self, request):
        return render(request, 'userdashboard/auth/verify_otp.html')

    def post(self, request):
        otp = request.POST.get('otp')
        signup_data = request.session.get('signup_data')

        if not signup_data:
            messages.error(request, "Session expired. Please sign up again.")
            return redirect('dashboard:user_signup')

        phone = signup_data['phone']
        result = verify_mobile_otp(VERIFY_URL, TEXTDRIP_OTP_TOKEN, phone, otp)

        print("OTP VERIFICATION RESULT:", result)

        if result.get("success") or result.get("status") is True:
            from django.contrib.auth.models import User
            User.objects.create_user(
                username=signup_data['email'],
                email=signup_data['email'],
                password=signup_data['password']
            )
            messages.success(request, "Account created successfully.")
            return redirect('dashboard:user_signin')
        else:
            messages.error(request, result.get("message", "OTP verification failed."))
            return redirect('dashboard:verify_otp')


class CustomPasswordResetView(PasswordResetView):
    form_class = CustomPasswordResetForm
    template_name = 'userdashboard/auth/password_reset_form.html'
    email_template_name = 'userdashboard/auth/password_reset_email.html'
    subject_template_name = 'userdashboard/auth/password_reset_email.txt'
    success_url = reverse_lazy('dashboard:password_reset_done')

    def form_valid(self, form):
        messages.success(self.request, "Password reset link sent.")
        return super().form_valid(form)


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'userdashboard/auth/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    form_class = CustomSetPasswordForm
    template_name = 'userdashboard/auth/password_reset_confirm.html'
    success_url = reverse_lazy('userdashboard:password_reset_complete')

    def form_valid(self, form):
        messages.success(self.request, "Your password has been set.")
        return super().form_valid(form)


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'userdashboard/auth/password_reset_complete.html'


class SignInView(View):
    def get(self, request):
        return render(request, 'userdashboard/auth/sign-in.html')

    def post(self, request):
        email = request.POST.get('user_email')
        password = request.POST.get('user_password')

        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard:home')  # or wherever you want to go after login
        else:
            messages.error(request, 'Invalid email or password.')
            return redirect('dashboard:user_signin')