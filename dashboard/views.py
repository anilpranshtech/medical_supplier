from django.http import HttpResponse, JsonResponse
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


class HomeView(TemplateView):
    template_name = 'dashboard/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['brands'] = [
            ('Nike', '1'), ('Adidas', '2'), ('Puma', '3'), ('New Balance', '4'),
            ('Converse', '5'), ('Reebok', '6'), ('Skechers', '7')
        ]
        context['new_arrivals'] = [
            {'name': 'Cloud Shift Lightweight Runner Pro Edition', 'img_num': '8', 'rating': '5.0', 'price': '$99.00'},
            {'name': 'Wave Strike Dynamic Boost Sneaker', 'img_num': '9', 'rating': '4.7', 'price': '$120.00'},
            {'name': 'Titan Edge High Impact Stability Lightweight Trainers', 'img_num': '5', 'rating': '3.5',
             'price': '$65.99'},
            {'name': 'Velocity Boost Xtreme High Shock Absorbers', 'img_num': '10', 'rating': '4.9', 'price': '$110.00'}
        ]
        context['popular_sneakers'] = [
            {'name': 'Cloud Shift Lightweight Runner Pro Edition', 'img_num': '11', 'rating': '5.0', 'price': '$99.00'},
            {'name': 'Titan Edge High Impact Stability Lightweight Trainers', 'img_num': '12', 'rating': '3.5',
             'price': '$65.99'},
            {'name': 'Wave Strike Dynamic Boost Sneaker', 'img_num': '13', 'rating': '4.7', 'price': '$120.00'},
            {'name': 'Velocity Boost Xtreme High Shock Absorbers', 'img_num': '14', 'rating': '4.9', 'price': '$110.00'}
        ]
        context['deals'] = [
            {'name': 'Cloud Shift Lightweight Runner Pro Edition', 'img_num': '3', 'rating': '5.0', 'price': '$99.00',
             'original_price': '$140.00'},
            {'name': 'Titan Edge High Impact Stability Lightweight Trainers', 'img_num': '4', 'rating': '3.5',
             'price': '$46.00', 'original_price': '$110.00'},
            {'name': 'Wave Strike Dynamic Boost Sneaker', 'img_num': '15', 'rating': '4.7', 'price': '$140.00',
             'original_price': '$179.00'},
            {'name': 'Velocity Boost Xtreme High Shock Absorbers', 'img_num': '2', 'rating': '4.9', 'price': '$315.00',
             'original_price': '$280.00'}
        ]
        context['features'] = [
            {'title': 'Free Delivery', 'description': 'No extra shipping costs', 'icon': 'delivery-time',
             'icon_color': 'primary', 'stroke_color': 'primary', 'fill_color': 'primary'},
            {'title': '24/7 Support', 'description': 'Help anytime, anywhere', 'icon': 'messages',
             'icon_color': 'green', 'stroke_color': 'success', 'fill_color': 'success'},
            {'title': 'Discounts', 'description': 'Save big on top deals', 'icon': 'discount', 'icon_color': 'violet',
             'stroke_color': 'info', 'fill_color': 'info'},
            {'title': 'Money-Back', 'description': 'Full refund, no risk', 'icon': 'credit-cart',
             'icon_color': 'yellow', 'stroke_color': 'yellow', 'fill_color': 'warning'}
        ]
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


class UserProfile(TemplateView):
    template_name = 'pages/user_profile.html'


VERIFY_URL = "https://api.textdrip.com/api/v1/email-otp"


class SignUpView(View):
    def get(self, request):
        return render(request, 'userdashboard/auth/sign-up.html')

    def post(self, request):
        email = request.POST.get('user_email')
        password = request.POST.get('user_password')
        confirm_password = request.POST.get('confirm_password')
        phone = request.POST.get('phone')

        # Validate passwords match
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('dashboard:user_signup')

        # Check if user already exists
        if User.objects.filter(username=email).exists():
            messages.error(request, "An account with this email already exists.")
            return redirect('dashboard:user_signup')

        # Send OTP
        otp_response = send_phone_otp(phone, TEXTDRIP_OTP_TOKEN)
        if "error" in otp_response:
            messages.error(request, otp_response["error"])
            return redirect('dashboard:user_signup')

        # Store signup data in session
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
            # Double-check user doesn't exist
            if User.objects.filter(username=signup_data['email']).exists():
                messages.error(request, "An account with this email already exists.")
                request.session.pop('signup_data', None)
                return redirect('dashboard:user_signup')

            try:
                User.objects.create_user(
                    username=signup_data['email'],
                    email=signup_data['email'],
                    password=signup_data['password']
                )
                request.session.pop('signup_data', None)
                messages.success(request, "Account created successfully.")
                return redirect('dashboard:user_signin')
            except Exception as e:
                messages.error(request, f"Error creating account: {str(e)}")
                return redirect('dashboard:user_signup')
        else:
            messages.error(request, result.get("message", "OTP verification failed."))
            return redirect('dashboard:verify_otp')


class ResendOTPView(View):
    def post(self, request):
        signup_data = request.session.get('signup_data')
        if not signup_data:
            return JsonResponse({'message': 'Session expired. Please sign up again.'}, status=400)

        phone = signup_data['phone']
        otp_response = send_phone_otp(phone, TEXTDRIP_OTP_TOKEN)
        if "error" in otp_response:
            return JsonResponse({'message': otp_response["error"]}, status=400)
        return JsonResponse({'message': 'OTP resent successfully!'})


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
    success_url = reverse_lazy('dashboard:password_reset_complete')

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
            return redirect('dashboard:home')
        else:
            messages.error(request, 'Invalid email or password.')
            return redirect('dashboard:user_signin')