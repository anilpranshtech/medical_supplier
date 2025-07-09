from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.views import LoginView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, \
    PasswordResetCompleteView
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from razorpay.errors import SignatureVerificationError
from .forms import PaymentForm
from.models import *
import razorpay
import stripe
from django.utils import timezone
import uuid
from djapp.settings import TEXTDRIP_OTP_TOKEN
from utils.handle_textdrip_otp import send_phone_otp, verify_mobile_otp, VERIFY_URL
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
import requests
from django.http import JsonResponse



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

         #  Popular Medical Supplies
        popular_products = Product.objects.filter(
            tag='popular',
            is_active=True
        ).order_by('-created_at')[:4]
        for product in popular_products:
            main_img = ProductImage.objects.filter(product=product, is_main=True).first()
            product.main_image = main_img.image.url if main_img else None
        context['popular_products'] = popular_products

        # Limited-Time Deals
        limited_products = Product.objects.filter(
            tag='limited',
            is_active=True
        ).order_by('-created_at')[:4]
        for product in limited_products:
            main_img = ProductImage.objects.filter(product=product, is_main=True).first()
            product.main_image = main_img.image.url if main_img else None
        context['limited_products'] = limited_products

        
        # Featured Products 
        all_ids = list(Product.objects.filter(is_active=True).values_list('id', flat=True))
        random_ids = random.sample(all_ids, min(len(all_ids), 7))
        featured_products = Product.objects.filter(id__in=random_ids)

        for product in featured_products:
            main_img = ProductImage.objects.filter(product=product, is_main=True).first()
            product.main_image = main_img.image.url if main_img else None
        context['featured_products'] = featured_products

         # wishlist 
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


class WishlistToggleView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        product_id = request.POST.get('product_id')
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Product not found'}, status=400)

        wishlist_item, created = WishlistProduct.objects.get_or_create(user=request.user, product=product)
        if not created:
            wishlist_item.delete()
            return JsonResponse({'status': 'removed'})
        return JsonResponse({'status': 'added'})

class WishlistClearView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        WishlistProduct.objects.filter(user=request.user).delete()
        return JsonResponse({'status': 'cleared'})


class WishlistView(LoginRequiredMixin, TemplateView):
    template_name = 'userdashboard/view/wishlist.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        wishlist_items = WishlistProduct.objects.filter(user=self.request.user).select_related('product')

        for item in wishlist_items:
            main_img = ProductImage.objects.filter(product=item.product, is_main=True).first()
            item.product.main_image = main_img.image if main_img else None

        context['wishlist_items'] = wishlist_items
        return context

class WishlistProductListView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        wishlist_items = WishlistProduct.objects.filter(user=request.user)
        data = [
            {  
                "id": item.product.id,
                "name": item.product.name,
                "price": f"${item.product.price}",
                "sku": item.product.supplier_sku,
                "image": item.product.productimage_set.first().image.url if item.product.productimage_set.exists() else None,
            }
            for item in wishlist_items
        ]
        return JsonResponse(data, safe=False)

class OrderSummaryView(TemplateView):
    template_name = 'userdashboard/view/order-summary.html'


class ShippingInfoView(TemplateView):
    template_name = 'userdashboard/view/shipping-info.html'


class PaymentMethodView(LoginRequiredMixin, View):
    template_name = 'userdashboard/view/payment-method.html'

    def get_stripe_key(self, request):
        return settings.STRIPE_PUBLISHABLE_KEY, settings.STRIPE_SECRET_KEY

    def get(self, request):
        public_key, _ = self.get_stripe_key(request)

        # Razorpay: Create Order
        amount_in_paise = 10000  # ₹100
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        razorpay_order = client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "payment_capture": "1"
        })

        billing = CustomerBillingAddress.objects.filter(user=request.user).first()
        return render(request, self.template_name, {
            "STRIPE_PUBLIC_KEY": public_key,
            "RAZORPAY_KEY_ID": settings.RAZORPAY_KEY_ID,
            "razorpay_amount_in_paise": amount_in_paise,
            "razorpay_order_id": razorpay_order['id'],
            "billing": billing
        })

    def post(self, request):
        payment_method = request.POST.get("payment_method")
        user = request.user

        if payment_method == "cod":
            payment = Payment.objects.create(
                name=user.get_full_name(),
                amount=100.00,
                payment_method="cod",
                paid=False
            )

            delivery_partner, _ = DeliveryPartner.objects.get_or_create(name="Delhivery")
            CODPayment.objects.create(
                user=request.user,
                name=user.get_full_name(),
                amount=100.00,
                paid=False,
                cod_tracking_id="COD123456",
                delivery_partner=delivery_partner
            )

            messages.success(request, "COD Order placed.")
            return redirect("dashboard:order_placed")

        elif payment_method == "stripe":
            _, stripe_secret = self.get_stripe_key(request)
            stripe.api_key = stripe_secret

            token = request.POST.get("stripeToken")
            crd_name = request.POST.get("crd_name")

            try:
                customer = stripe.Customer.create(
                    email=user.email,
                    name=crd_name,
                    source=token
                )
                charge = stripe.Charge.create(
                    customer=customer.id,
                    amount=10000,
                    currency="usd",
                    description="Product Payment"
                )

                payment = Payment.objects.create(
                    name=crd_name,
                    amount=100.00,
                    payment_method="stripe",
                    paid=True,
                    customer_id=customer.id
                )

                StripePayment.objects.create(
                    user=request.user,
                    name=crd_name,
                    amount=100.00,
                    paid=True,
                    customer_id=customer.id,
                    stripe_charge_id=charge.id,
                    stripe_customer_id=customer.id,
                    stripe_signature=charge.payment_method
                )

                card_details = charge.payment_method_details.get("card") if charge.payment_method_details else None

                CustomerBillingAddress.objects.update_or_create(
                    user=user,
                    defaults={
                        "customer_name": crd_name,
                        "customer_address1": request.POST.get("customer_address1"),
                        "customer_address2": request.POST.get("customer_address2"),
                        "customer_city": request.POST.get("customer_city"),
                        "customer_state": request.POST.get("customer_state"),
                        "customer_postal_code": request.POST.get("customer_postal_code"),
                        "customer_country": request.POST.get("customer_country"),
                        "customer_country_code": request.POST.get("customer_country_code"),
                        "is_old": True,
                        "old_card": json.dumps({
                            "brand": card_details.brand,
                            "last4": card_details.last4,
                            "exp_month": card_details.exp_month,
                            "exp_year": card_details.exp_year
                        }) if card_details else None
                    }
                )

                messages.success(request, "Stripe Payment successful.")
                return redirect("dashboard:order_placed")

            except Exception as e:
                messages.error(request, f"Stripe payment failed: {e}")
                return redirect("dashboard:payment_method")

        elif payment_method == "razorpay":
            razorpay_payment_id = request.POST.get("razorpay_payment_id")
            razorpay_order_id = request.POST.get("razorpay_order_id")
            razorpay_signature = request.POST.get("razorpay_signature")

            if not razorpay_payment_id:
                messages.error(request, "Razorpay payment failed.")
                return redirect("dashboard:payment_method")

            # ✅ Signature verification
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            params_dict = {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature
            }

            try:
                client.utility.verify_payment_signature(params_dict)
            except SignatureVerificationError:
                messages.error(request, "Signature verification failed.")
                return redirect("dashboard:payment_method")

            # ✅ Save only if verification succeeded
            payment = Payment.objects.create(
                name=user.get_full_name(),
                amount=100.00,
                payment_method="razorpay",
                paid=True
            )

            RazorpayPayment.objects.create(
                user=request.user,
                name=user.get_full_name(),
                amount=100.00,
                paid=True,
                razorpay_payment_id=razorpay_payment_id,
                razorpay_order_id=razorpay_order_id,
                razorpay_signature=razorpay_signature
            )

            messages.success(request, "Razorpay Payment successful.")
            return redirect("dashboard:order_placed")

        else:
            messages.error(request, "Invalid payment method.")
            return redirect("dashboard:payment_method")


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


class PaymentView(View):
    template_name = 'userdashboard/view/payment.html'

    def get(self, request):
        form = PaymentForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = PaymentForm(request.POST)
        response_payment = None
        if form.is_valid():
            name = form.cleaned_data['name']
            amount = int(form.cleaned_data['amount']) * 100

            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            response_payment = client.order.create(dict(amount=amount, currency='USD'))

            razorpay_order_id = response_payment['id']
            order_status = response_payment['status']

            if order_status == 'created':
                RazorpayPayment.objects.create(
                    user=request.user,
                    name=name,
                    amount=amount,
                    razorpay_order_id=razorpay_order_id
                )
                response_payment['name'] = name

        return render(request, self.template_name, {'form': form, 'payment': response_payment})


@method_decorator(csrf_exempt, name='dispatch')
class PaymentStatusView(View):
    template_name = 'userdashboard/view/payment_status.html'

    def post(self, request):
        required_fields = ['razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature']
        if not all(field in request.POST for field in required_fields):
            return render(request, self.template_name, {'status': False, 'error': 'Missing payment details'})

        params_dict = {
            'razorpay_order_id': request.POST['razorpay_order_id'],
            'razorpay_payment_id': request.POST['razorpay_payment_id'],
            'razorpay_signature': request.POST['razorpay_signature']
        }

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        try:
            client.utility.verify_payment_signature(params_dict)

            payment = RazorpayPayment.objects.get(razorpay_order_id=params_dict['razorpay_order_id'])
            payment.razorpay_payment_id = params_dict['razorpay_payment_id']
            payment.razorpay_signature = params_dict['razorpay_signature']
            payment.paid = True
            payment.save()

            return render(request, self.template_name, {'status': True})
        except SignatureVerificationError:
            return render(request, self.template_name, {'status': False, 'error': 'Signature verification failed'})