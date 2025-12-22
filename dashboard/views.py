import uuid
from decimal import Decimal
from io import BytesIO
from django.utils.timezone import localtime
# import pm
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, \
    PasswordResetCompleteView
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.views.generic import TemplateView, FormView, UpdateView, ListView
from xhtml2pdf import pisa
from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.html import strip_tags
from django.utils.timezone import now, timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST
from razorpay.errors import SignatureVerificationError
from django.db.models import Count, Prefetch, F
from django.core.paginator import Paginator
from django.db.models import Q
from djapp.settings import TEXTDRIP_OTP_TOKEN
from utils.handle_textdrip_otp import send_phone_otp, verify_mobile_otp, VERIFY_URL
from utils.handle_user_profile import get_user_profile
from .forms import *
from .models import *
import razorpay
import stripe
from datetime import date, timedelta, datetime
import random
from django.db.models.functions import Coalesce
import re
import requests
from supplier.models import *
from django.http import JsonResponse
from datetime import date, timedelta
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Avg
from django.db.models import  ExpressionWrapper, DecimalField, Case, When
from decimal import Decimal
from django.db.models import Value
from utils.userlogs import *
import logging
from .forms import *
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from utils.logs import user_login_activity as supplier_login_activity
from utils.logs import user_failed_activity as supplier_failed_activity
from dashboard.models import UserActivityLog

# Retailer / Wholesaler logs
from utils.userlogs import user_login_activity as buyer_login_activity
from utils.userlogs import user_failed_activity as buyer_failed_activity

logger = logging.getLogger(__name__)


class HomeView(TemplateView):
    template_name = 'dashboard/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()

        def set_product_fields(product_queryset):
            """Helper to set image, rating, reviews, delivery date"""
            for product in product_queryset:
                # Main image
                main_img = ProductImage.objects.filter(product=product, is_main=True).first()
                product.main_image = main_img.image.url if main_img else None

                # Delivery date
                if product.delivery_time:
                    delivery_date = today + timedelta(days=product.delivery_time)
                    product.delivery_date = delivery_date.strftime('%a, %d %b')
                else:
                    product.delivery_date = 'N/A'

                # Rating & reviews
                reviews = RatingReview.objects.filter(product=product)
                total_reviews = reviews.count()
                avg_rating = reviews.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0.0
                product.rating = round(avg_rating, 1) if total_reviews > 0 else 0.0
                product.total_reviews = total_reviews
            return product_queryset

     
        categories = ProductCategory.objects.filter(
            product__last_category__isnull=False,
            product__is_active=True
        ).distinct().order_by('-created_at')
        context['categories'] = categories[:10] 
        context['has_more_categories'] = categories.count() > 10 

        # ---------------- Special Offers ---------------- #
        special_offers = Product.objects.filter(
            offer_active=True,
            offer_percentage__gt=0,
            offer_start__lte=today,
            offer_end__gte=today,
            is_active=True
        ).select_related('category', 'event').prefetch_related('images', 'reviews').order_by('-offer_percentage')[:3]
        context['special_offers'] = set_product_fields(special_offers)

        # ---------------- New Arrivals ---------------- #
        recent_products = Product.objects.filter(
            tag='recent', is_active=True
        ).select_related('category', 'event').prefetch_related('images', 'reviews').order_by('-created_at')[:4]
        context['recent_products'] = set_product_fields(recent_products)

        # ---------------- Popular Medical Supplies ---------------- #
        popular_products = Product.objects.filter(
            tag='popular', is_active=True
        ).select_related('category', 'event').prefetch_related('images', 'reviews').order_by('-created_at')[:4]
        context['popular_products'] = set_product_fields(popular_products)

        # ---------------- Limited-Time Deals ---------------- #
        limited_products = Product.objects.filter(
            tag='limited', is_active=True
        ).select_related('category', 'event').prefetch_related('images', 'reviews').order_by('-created_at')[:4]
        context['limited_products'] = set_product_fields(limited_products)

        # ---------------- Featured Products (exclude Conference, Webinar, Event) ---------------- #
        all_ids = list(
            Product.objects.filter(
                is_active=True
            ).exclude(
                category__name__in=['Conference', 'Webinar', 'Event']
            ).values_list('id', flat=True)
        )
        random_ids = random.sample(all_ids, min(len(all_ids), 6))
        featured_products = Product.objects.filter(
            id__in=random_ids
        ).select_related('category', 'event').prefetch_related('images', 'reviews')
        context['featured_products'] = set_product_fields(featured_products)

        # ---------------- Conference & Webinar Events ---------------- #
        conference_products = Product.objects.filter(
            category__name__in=['Conference', 'Webinar', 'Event'], is_active=True
        ).select_related('category', 'event').prefetch_related('images', 'reviews').order_by('-created_at')[:4]
        context['conference_products'] = set_product_fields(conference_products)

        # ---------------- Wishlist & Cart ---------------- #
        if self.request.user.is_authenticated:
            cart_items = CartProduct.objects.filter(user=self.request.user)
            context['user_cart_ids'] = list(cart_items.values_list('product_id', flat=True))
            context['user_cart_quantities'] = {item.product_id: item.quantity for item in cart_items}
            context['user_wishlist_ids'] = list(
                WishlistProduct.objects.filter(user=self.request.user).values_list('product_id', flat=True)
            )
            context['user_registered_event_ids'] = list(
                EventRegistration.objects.filter(user=self.request.user).values_list('product_id', flat=True)
            )

            # ---------------- Profile and Company Name ---------------- #
            user = self.request.user
            context['profile_type'] = None
            context['company_name'] = None
            context['profile'] = None

            # Check RetailProfile
            try:
                retail_profile = RetailProfile.objects.get(user=user)
                context['profile_type'] = 'retailer'
                context['profile'] = retail_profile
                # For retailers, company_name might not exist; use workplace or a fallback
                context['company_name'] = retail_profile.workplace or user.get_full_name() or user.username
            except RetailProfile.DoesNotExist:
                pass

            # Check WholesaleBuyerProfile
            try:
                wholesale_profile = WholesaleBuyerProfile.objects.get(user=user)
                context['profile_type'] = 'wholesaler'
                context['profile'] = wholesale_profile
                context['company_name'] = wholesale_profile.company_name
            except WholesaleBuyerProfile.DoesNotExist:
                pass

            # Check SupplierProfile
            try:
                supplier_profile = SupplierProfile.objects.get(user=user)
                context['profile_type'] = 'supplier'
                context['profile'] = supplier_profile
                context['company_name'] = supplier_profile.company_name
            except SupplierProfile.DoesNotExist:
                pass

        else:
            context['user_cart_ids'] = []
            context['user_cart_quantities'] = {}
            context['user_wishlist_ids'] = []
            context['user_registered_event_ids'] = []
            context['profile_type'] = None
            context['company_name'] = None
            context['profile'] = None

        # ---------------- Suppliers (Manufacturers / Distributors) ---------------- #
        active_suppliers = SupplierProfile.objects.filter(current_status='active').order_by('-id')  
        context['suppliers'] = active_suppliers[:10]
        context['has_more_suppliers'] = active_suppliers.count() > 10

        # ---------------- Banners ---------------- #
        context['banners'] = Banner.objects.filter(is_active=True)

        return context

        
class CategoryProductsView(TemplateView):
    template_name = 'userdashboard/view/category_products.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category_id = self.kwargs.get("pk")

        try:
            category = ProductCategory.objects.get(pk=category_id)
        except ProductCategory.DoesNotExist:
            context.update({'products': [], 'category': None})
            return context

        effective_price = ExpressionWrapper(
            F('price') * (1 - (F('offer_percentage') / Value(100, output_field=DecimalField()))),
            output_field=DecimalField(max_digits=10, decimal_places=2)
        )

        products = Product.objects.filter(category=category, is_active=True).annotate(
            effective_price=Case(
                When(offer_active=True, offer_percentage__isnull=False, then=effective_price),
                default=F('price'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )

        today = timezone.now().date()
        for product in products:
          
            main_img = ProductImage.objects.filter(product=product, is_main=True).first()
            product.main_image = main_img.image.url if main_img else None

        
            if product.delivery_time:
                delivery_date = today + timedelta(days=product.delivery_time)
                product.delivery_date = delivery_date.strftime('%a, %d %b')
            else:
                product.delivery_date = 'N/A'

     
            reviews = RatingReview.objects.filter(product=product)
            total_reviews = reviews.count()
            avg_rating = reviews.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0.0
            product.rating = round(avg_rating, 1) if total_reviews > 0 else 0.0
            product.total_reviews = total_reviews

            
            if product.offer_active and product.offer_percentage:
                product.discounted_price = product.price * (
                    Decimal(1) - Decimal(product.offer_percentage) / Decimal(100)
                )
            else:
                product.discounted_price = product.price

      
        if self.request.user.is_authenticated:
            context['user_cart_ids'] = list(
                CartProduct.objects.filter(user=self.request.user).values_list('product_id', flat=True)
            )
            context['user_wishlist_ids'] = list(
                WishlistProduct.objects.filter(user=self.request.user).values_list('product_id', flat=True)
            )
        else:
            context['user_cart_ids'] = []
            context['user_wishlist_ids'] = []

        context.update({'category': category, 'products': products})
        return context
    
class SupplierListView(TemplateView):
    template_name = "userdashboard/view/supplier_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['suppliers'] = SupplierProfile.objects.filter(current_status='active').order_by('-id')
        return context

class SupplierProductsView(TemplateView):
    template_name = "userdashboard/view/supplier_products.html"

    def _add_ratings(self, products):
        for product in products:
            reviews = product.reviews.all()

            if reviews.exists():
                total_reviews = reviews.count()
                avg_rating = reviews.aggregate(Avg("rating"))["rating__avg"]
                product.rating = round(avg_rating, 1)
                product.total_reviews = total_reviews
            else:
                product.rating = 0.0
                product.total_reviews = 0

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier_user_id = self.kwargs['user_id']

        try:
            supplier = SupplierProfile.objects.get(
                user__id=supplier_user_id,
                current_status='active'
            )

            products = Product.objects.filter(
                created_by__id=supplier_user_id,
                is_active=True
            ).order_by('-created_at')
            self._add_ratings(products)

            context['supplier'] = supplier
            context['products'] = products

        except SupplierProfile.DoesNotExist:
            context['supplier'] = None
            context['products'] = []

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

        # ❌ Invalid credentials
        if user is None:
            user_failed_activity(
                user=None,
                description=f"Failed login attempt for email: {email}"
            )
            form.add_error(None, f"Invalid credentials for {email}.")
            return self.form_invalid(form)

        # ❌ Role validation
        if user_type == 'supplier':
            if not hasattr(user, 'supplierprofile'):
                user_failed_activity(
                    user=user,
                    description=f"Login failed: {email} attempted supplier login without supplier profile"
                )
                form.add_error(None, f"{email} is not registered as a supplier.")
                return self.form_invalid(form)

        elif user_type == 'buyer':
            if buyer_type == 'retailer' and not hasattr(user, 'retailprofile'):
                user_failed_activity(
                    user=user,
                    description=f"Login failed: {email} attempted retailer login without retail profile"
                )
                form.add_error(None, f"{email} is not registered as a retailer.")
                return self.form_invalid(form)

            elif buyer_type == 'wholesaler' and not hasattr(user, 'wholesalebuyerprofile'):
                user_failed_activity(
                    user=user,
                    description=f"Login failed: {email} attempted wholesaler login without wholesaler profile"
                )
                form.add_error(None, f"{email} is not registered as a wholesaler.")
                return self.form_invalid(form)

        # ✅ Login success
        login(self.request, user)

        if user_type == 'supplier':
            self.request.session['user_role'] = 'supplier'
        else:
            self.request.session['user_role'] = buyer_type

        # ✅ Log successful login
        user_login_activity(user)

        messages.success(self.request, f"Welcome back, {email}!")
        return redirect(self.get_success_url())

    def get_success_url(self):
        user = self.request.user

        if user.is_superuser or user.is_staff:
            return reverse_lazy('superuser:superuser')
        elif hasattr(user, 'supplierprofile'):
            return reverse_lazy('supplier:user_information')
        elif hasattr(user, 'retailprofile'):
            return reverse_lazy('dashboard:home')
        elif hasattr(user, 'wholesalebuyerprofile'):
            return reverse_lazy('dashboard:home')

        return reverse_lazy('dashboard:home')


class RequestRoleView(LoginRequiredMixin, View):
    template_name = 'userdashboard/seller/request_role.html'
    success_url = reverse_lazy('dashboard:home')

    def get(self, request, *args, **kwargs):
        form = SupplierProfileForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = SupplierProfileForm(request.POST, request.FILES)

        # Check if already requested
        if RoleRequest.objects.filter(user=request.user, requested_role='supplier').exists():
            messages.error(request, "You already have a pending or approved supplier role request.")
            return render(request, self.template_name, {'form': form})

        if form.is_valid():
            # Create role request
            RoleRequest.objects.create(
                user=request.user,
                requested_role='supplier',
                status='pending'
            )

            # Save supplier profile
            SupplierProfile.objects.update_or_create(
                user=request.user,
                defaults=form.cleaned_data
            )

            messages.success(request, "Your supplier role request has been submitted successfully.")
            return redirect(self.success_url)

        messages.error(request, "Please correct the errors below.")
        return render(request, self.template_name, {'form': form})
    




    
#-------------------------------------------------------------------------------------------------------------------------------------------------
from django.urls import reverse
def generate_token():
        return uuid.uuid4().hex
        
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.contrib.auth import get_user_model


class RegistrationView(View):
    recaptcha_secret = '6LdTHV8rAAAAAIgLr2wdtdtWExTS6xJpUpD8qEzh'
    template_name = 'dashboard/register.html'

    def get(self, request):
        context = {
            'form_data': {},
            'nationalities': Country.objects.all().order_by('name'),
            # 'residencies': Residency.objects.all(),
            'country_codes': CountryCode.objects.all(),
            'specialities': Speciality.objects.all(),
        }
        return render(request, self.template_name, context)

    def post(self, request):
        step = request.POST.get("step")
        if step == "register":
            return self.handle_registration(request)
        elif step == "verify_otp":
            return self.handle_otp(request)
        return JsonResponse({"success": False, "errors": {"general": "Invalid step"}}, status=400)

    def handle_registration(self, request):
        errors = {}

        # reCAPTCHA validation
        recaptcha_response = request.POST.get('g-recaptcha-response')
        recaptcha_result = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={'secret': self.recaptcha_secret, 'response': recaptcha_response}
        ).json()
        if not recaptcha_result.get('success'):
            errors['recaptcha'] = 'Invalid reCAPTCHA.'

        # Collect form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        phone = request.POST.get('phone')
        user_type = request.POST.get('user_type')
        buyer_type = request.POST.get('buyer_type')

        # Basic validations
        if not first_name: errors['first_name'] = 'First name is required.'
        if not last_name: errors['last_name'] = 'Last name is required.'
        if not email: errors['email'] = 'Email is required.'
        if not phone: errors['phone'] = 'Phone number is required.'
        if not password: errors['password'] = 'Password is required.'
        if password != confirm_password: errors['confirm_password'] = 'Passwords do not match.'
        if email and User.objects.filter(username=email).exists():
            errors['email'] = 'Email already exists.'

        if errors:
            return JsonResponse({'success': False, 'errors': errors}, status=400)

        # Send OTP
        otp_response = send_phone_otp(phone, TEXTDRIP_OTP_TOKEN)
        if "error" in otp_response:
            return JsonResponse({'success': False, 'errors': {'phone': otp_response["error"]}}, status=400)

        # One token for OTP + Email
        token = uuid.uuid4().hex
        data = request.POST.dict()
        data['confirm_token'] = token

        try:
            PendingSignup.objects.create(token=token, data=json.dumps(data))
        except Exception as e:
            return JsonResponse({'success': False, 'errors': {'general': f'Error saving pending signup: {str(e)}'}}, status=500)

        return JsonResponse({'success': True, 'token': token})

    def handle_otp(self, request):
        token = request.POST.get('token')
        otp = request.POST.get('otp')

        try:
            pending = PendingSignup.objects.get(token=token)
        except PendingSignup.DoesNotExist:
            return JsonResponse({'success': False, 'errors': {'general': 'Invalid or expired token.'}}, status=400)

        if pending.is_expired():
            pending.delete()
            return JsonResponse({'success': False, 'errors': {'general': 'Token expired.'}}, status=400)

        try:
            data = json.loads(pending.data)
        except Exception:
            return JsonResponse({'success': False, 'errors': {'general': 'Corrupted signup data.'}}, status=500)

        phone = data.get('phone')
        result = verify_mobile_otp(VERIFY_URL, TEXTDRIP_OTP_TOKEN, phone, otp)
        if not (result.get("success") or result.get("status") is True):
            return JsonResponse({'success': False, 'errors': {'otp': result.get("message", "OTP verification failed.")}}, status=400)

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=data['email'],
                    email=data['email'],
                    password=data['password'],
                    first_name=data['first_name'],
                    last_name=data['last_name']
                )

                user_type = data.get('user_type')
                buyer_type = data.get('buyer_type')

                if user_type == 'supplier':
                    SupplierProfile.objects.create(
                        user=user,
                        phone=phone,
                        company_name=data.get('supplier_company_name', ''),
                        license_number=data.get('license_number', ''),
                        email_confirmed=False  # must confirm by email
                    )
                    from utils.logs import user_log_activity
                    user_log_activity(
                        user=user,
                        description=f"Supplier account created for {user.email} with company {data.get('supplier_company_name', 'N/A')}",
                        actions=UserActivityLog.ActionType.CREATED
                    )

                    # confirm_link = f"{settings.SITE_URL}/confirm-email/{token}/"
                    confirm_link = request.build_absolute_uri(
                        reverse('dashboard:confirm_email', args=[token])
                    )
                    html_message = render_to_string('dashboard/confirmation_email.html', {
                        'user_name': f"{data['first_name']} {data['last_name']}",
                        'confirm_link': confirm_link
                    })
                    send_mail(
                        'Confirm Your Account - Medical Supplierz',
                        strip_tags(html_message),
                        settings.DEFAULT_FROM_EMAIL,
                        [data['email']],
                        html_message=html_message,
                    )
                    # keep PendingSignup until email confirmed
                    return render(request, 'dashboard/register_success.html', {
                        'token': token,
                        'email': data['email']
                    })

                elif buyer_type == 'retailer':
                    nationality = Country.objects.filter(id=data.get('nationality')).first()
                    state = State.objects.filter(id=data.get('state')).first() if data.get('state') else None
                    city = City.objects.filter(id=data.get('city')).first() if data.get('city') else None
                    # residency = Residency.objects.filter(id=data.get('residency')).first()
                    country_code = CountryCode.objects.filter(id=data.get('country_code')).first()
                    speciality = Speciality.objects.filter(id=data.get('speciality')).first()
                    RetailProfile.objects.create(
                        user=user,
                        phone=phone,
                        current_position=data.get('current_position', ''),
                        workplace=data.get('workplace', ''),
                        nationality=nationality,
                        state=state,         
                        city=city,
                        # residency=residency,
                        country_code=country_code,
                        speciality=speciality,
                    )

                    user_created_activity(
                        user=user,
                        description=f"Retailer account created for {user.email} at {data.get('workplace', 'N/A')}"
                    )

                elif user_type == 'wholesale' or buyer_type == 'wholesaler':
                    WholesaleBuyerProfile.objects.create(
                        user=user,
                        phone=phone,
                        company_name=data.get('company_name', ''),
                        gst_number=data.get('gst_number', ''),
                        department=data.get('department', ''),
                        purchase_capacity=int(data.get('purchase_capacity') or 0)
                    )
                    user_created_activity(
                        user=user,
                        description=f"Wholesaler account created for {user.email} with company {data.get('company_name', 'N/A')}"
                    )

                else:
                    return JsonResponse({'success': False, 'errors': {'general': 'Invalid user type.'}}, status=400)

                pending.delete()
                return JsonResponse({'success': True, 'redirect': '/login/'})
        except Exception as e:
            return JsonResponse({'success': False, 'errors': {'general': f'Error creating account: {str(e)}'}}, status=500)

def get_states(request, country_id):
    states = State.objects.filter(country_id=country_id).order_by('name')
    data = [{'id': state.id, 'name': state.name} for state in states]
    return JsonResponse({'states': data})   

def get_cities(request, state_id):
    cities = City.objects.filter(state_id=state_id).order_by('name')
    data = [{'id': city.id, 'name': city.name} for city in cities]
    return JsonResponse({'cities': data})
def get_country_codes(request, country_id):
    """Fetch country codes based on selected nationality/country"""
    country_codes = CountryCode.objects.filter(country_id=country_id).order_by('code')
    data = [{'id': code.id, 'code': code.code, 'country': code.country.name if code.country else ''} for code in country_codes]
    return JsonResponse({'country_codes': data})
def check_email(request):
    email = request.POST.get('email')
    exists = User.objects.filter(email=email).exists()
    return JsonResponse({'exists': exists})
# class ConfirmEmailView(View):
#     def get(self, request, token):
#         try:
#             pending = PendingSignup.objects.get(token=token)
#             data = json.loads(pending.data)
#             email = data.get('email')

#             user = User.objects.filter(username=email).first()
#             if user and hasattr(user, 'supplierprofile'):
#                 user.supplierprofile.email_confirmed = True
#                 user.supplierprofile.save()

#             pending.delete()
#             return redirect('supplier:supplier')
#         except PendingSignup.DoesNotExist:
#             return JsonResponse({'message': 'Invalid or expired confirmation link.'}, status=400)
#         except Exception as e:
#             return JsonResponse({'message': f'Error confirming email: {str(e)}'}, status=500)
class ConfirmEmailView(View):
    def get(self, request, token):
        try:
            pending = PendingSignup.objects.get(token=token)
            data = json.loads(pending.data)
            email = data.get('email')

            user = User.objects.filter(username=email).first()
            if user and hasattr(user, 'supplierprofile'):
                user.supplierprofile.email_confirmed = True
                user.supplierprofile.save()

            pending.delete()
            return redirect('supplier:supplier')

        except PendingSignup.DoesNotExist:
            return render(request, "dashboard/token_expired.html", status=400)

        except Exception as e:
            return render(request, "dashboard/token_expired.html", {
                "error": f"Error confirming email: {str(e)}"
            }, status=500)


class ResendEmailView(View):
    def post(self, request):
        token = request.POST.get('token')
        email = request.POST.get('email')
        if not token or not email:
            return JsonResponse({'message': 'Token or email missing.'}, status=400)

        try:
            pending = PendingSignup.objects.get(token=token)
            data = json.loads(pending.data)
            if data.get('email') != email:
                return JsonResponse({'message': 'Invalid email for this token.'}, status=400)

            # confirm_link = f"{settings.SITE_URL}/confirm-email/{token}/"
            confirm_link = request.build_absolute_uri(
                reverse('dashboard:confirm_email', args=[token])
            )
            html_message = render_to_string('dashboard/confirmation_email.html', {
                'user_name': f"{data['first_name']} {data['last_name']}",
                'confirm_link': confirm_link
            })
            send_mail(
                'Confirm Your Account - Medical Supplierz',
                strip_tags(html_message),
                settings.DEFAULT_FROM_EMAIL,
                [email],
                html_message=html_message,
            )
            return JsonResponse({'message': 'Email resent successfully.'})
        except PendingSignup.DoesNotExist:
            return JsonResponse({'message': 'Invalid or expired token.'}, status=400)
        except Exception as e:
            return JsonResponse({'message': f'Failed to resend email: {str(e)}'}, status=500)


class ResendOTPView(View):
    def post(self, request):
        token = request.POST.get('token')
        if not token:
            return JsonResponse({'message': 'No token provided.'}, status=400)
        try:
            pending = PendingSignup.objects.get(token=token)
            data = json.loads(pending.data)
            phone = data.get('phone')
            otp_response = send_phone_otp(phone, TEXTDRIP_OTP_TOKEN)
            if "error" in otp_response:
                return JsonResponse({'message': otp_response["error"]}, status=400)
            return JsonResponse({'message': 'OTP resent successfully'})
        except PendingSignup.DoesNotExist:
            return JsonResponse({'message': 'Invalid or expired token'}, status=400)

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


class SearchSuggestionsView(View):
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '').strip()
        suggestions = []

        if query:
            query_terms = query.lower().split()
            keyword_queries = Q()
            for term in query_terms:
                keyword_queries |= Q(keywords__icontains=term)
            products = Product.objects.filter(keyword_queries).distinct()[:10]
            suggestions = [
                {'name': product.name, 'id': product.id}
                for product in products
            ]

        return JsonResponse({'suggestions': suggestions})
class CheckEmailView(View):
    def post(self, request):
        email = request.POST.get('email', '').strip()
        exists = User.objects.filter(username=email).exists()
        return JsonResponse({'exists': exists})

class SearchResultsGridView(TemplateView):
    template_name = 'userdashboard/view/search_results_grid.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        logger.debug(f"Context prepared: {context.keys()}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render_to_string(self.template_name, context, request=request)
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)
    def _add_delivery_dates(self, page_obj):
        if page_obj is None:
            return
        today = date.today()
        for product in page_obj:
            if getattr(product, "delivery_time", None):
                delivery = today + timedelta(days=product.delivery_time)
                product.delivery_date = delivery.strftime("%a, %d %b")
            else:
                product.delivery_date = "N/A"
        

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        logger.debug(f"Initial context: {context}")

        category_id = self.request.GET.get('category')
        sub_category_id = self.request.GET.get('sub_category')
        last_category_id = self.request.GET.get('last_category')
        sort_by = self.request.GET.get('sort_by')
        page = self.request.GET.get('page', 1)
        search_query = self.request.GET.get('q', '').strip()

        context['selected_category'] = None
        context['selected_sub_category'] = None
        context['selected_last_category'] = None
        context['page_obj'] = None
        context['total_products'] = 0
        context['search_query'] = search_query
        context['is_search_active'] = bool(search_query)

        # Define special categories
        special_category_names = ['Conference', 'Webinar', 'Event']
        logger.debug(f"special_category_names: {special_category_names}")

        # Get regular categories (excluding special categories)
        last_categories_with_products = ProductLastCategory.objects.annotate(
            product_count=Count('product', filter=Q(product__is_active=True))
        ).filter(product_count__gt=0)
        logger.debug(f"last_categories_with_products: {list(last_categories_with_products)}")

        valid_subcategory_ids = last_categories_with_products.values_list('sub_category_id', flat=True).distinct()
        subcategories_with_products = ProductSubCategory.objects.filter(
            id__in=valid_subcategory_ids
        ).prefetch_related('productlastcategory_set')
        logger.debug(f"subcategories_with_products: {list(subcategories_with_products)}")

        valid_category_ids = subcategories_with_products.values_list('category_id', flat=True).distinct()
        regular_categories = ProductCategory.objects.filter(
            id__in=valid_category_ids
        ).exclude(name__in=special_category_names).prefetch_related('productsubcategory_set')
        logger.debug(f"regular_categories: {list(regular_categories)}")

        # Get special categories with product counts
        special_categories = ProductCategory.objects.filter(
            name__in=special_category_names
        ).annotate(
            product_count=Count('product', filter=Q(product__is_active=True))
        ).filter(product_count__gt=0)
        logger.debug(
            f"special_categories type: {type(special_categories)}, value: {[f'ID: {c.id}, Name: {c.name}' for c in special_categories]}")

        # Fetch conference products
        conference_products = Product.objects.filter(
            category__name__in=special_category_names,
            is_active=True
        ).annotate(
            effective_price=Case(
                When(offer_active=True, offer_percentage__isnull=False, then=ExpressionWrapper(
                    F('price') * (1 - Coalesce(F('offer_percentage'), 0) / 100.0),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )),
                default=F('price'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
                ),
            avg_rating=Coalesce(
                Avg('reviews__rating'),
                Value(0.0),
                output_field=DecimalField(max_digits=3, decimal_places=1)
            )
        ).prefetch_related('images')[:4]
        logger.debug(
            f"conference_products: {[f'ID: {p.id}, Type: {type(p.id)}, Name: {p.name}, SKU: {p.supplier_sku}' for p in conference_products]}")

        context['regular_categories'] = regular_categories
        context['special_categories'] = special_categories
        context['conference_products'] = conference_products
        logger.debug(f"Context after setting categories: {context.keys()}")

        # Define effective price for sorting
        effective_price = ExpressionWrapper(
            F('price') * (1 - Coalesce(F('offer_percentage'), 0) / 100.0),
            output_field=DecimalField(max_digits=10, decimal_places=2)
        )
        products = Product.objects.annotate(
            effective_price=Case(
                When(offer_active=True, offer_percentage__isnull=False, then=effective_price),
                default=F('price'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
                   ),
            avg_rating=Coalesce(
                Avg('reviews__rating'),
                Value(0.0),
                output_field=DecimalField(max_digits=3, decimal_places=1)
            )
        ).prefetch_related('images')
   
        today = date.today()

        # Handle search query
        if search_query:
            search_terms = search_query.lower().split()
            query = Q()
            for term in search_terms:
                query |= Q(name__icontains=term) | Q(keywords__icontains=term)

            products = products.filter(query, is_active=True).distinct()

            if sort_by == '1':
                products = products.order_by('-effective_price')
            elif sort_by == '2':
                products = products.order_by('effective_price')
            else:
                products = products.order_by('-created_at')

            paginator = Paginator(products, 16)
            page_obj = paginator.get_page(page)
            self._add_delivery_dates(page_obj)
            

            context.update({
                'products': page_obj,
                'page_obj': page_obj,
                'paginator': paginator,
                'total_products': paginator.count,
            })

        elif last_category_id:
            try:
                last_category = ProductLastCategory.objects.get(id=last_category_id)
                context['selected_last_category'] = last_category
                context['selected_sub_category'] = last_category.sub_category
                context['selected_category'] = last_category.sub_category.category

                products = products.filter(
                    last_category=last_category,
                    is_active=True
                )

                if sort_by == '1':
                    products = products.order_by('-effective_price')
                elif sort_by == '2':
                    products = products.order_by('effective_price')
                elif sort_by == '3': 
                    products = products.order_by('-avg_rating')
                elif sort_by == '4':  
                    products = products.order_by('avg_rating')
                else:
                    products = products.order_by('-created_at')

                paginator = Paginator(products, 16)
                page_obj = paginator.get_page(page)
                self._add_delivery_dates(page_obj)

                context.update({
                    'products': page_obj,
                    'page_obj': page_obj,
                    'paginator': paginator,
                    'total_products': paginator.count,
                })
            except ProductLastCategory.DoesNotExist:
                context['products'] = []

        elif sub_category_id:
            try:
                sub_category = ProductSubCategory.objects.get(id=sub_category_id)
                context['last_categories'] = last_categories_with_products.filter(sub_category=sub_category)
                context['selected_sub_category'] = sub_category
                context['selected_category'] = sub_category.category
            except ProductSubCategory.DoesNotExist:
                context['last_categories'] = []

        elif category_id:
            try:
                try:
                    category_id_int = int(category_id)
                    category = ProductCategory.objects.get(id=category_id_int)
                except ValueError:
                    category = ProductCategory.objects.get(name=category_id)

                if category.name in special_category_names:
                    products = products.filter(category=category, is_active=True)
                    if sort_by == '1':
                        products = products.order_by('-effective_price')
                    elif sort_by == '2':
                        products = products.order_by('effective_price')
                    else:
                        products = products.order_by('-created_at')

                    paginator = Paginator(products, 16)
                    page_obj = paginator.get_page(page)
                    self._add_delivery_dates(page_obj)

                    context.update({
                        'products': page_obj,
                        'page_obj': page_obj,
                        'paginator': paginator,
                        'total_products': paginator.count,
                        'selected_category': category
                    })
                else:
                    subcategories = ProductSubCategory.objects.filter(category=category)
                    context['last_categories'] = last_categories_with_products.filter(sub_category__in=subcategories)
                    context['selected_category'] = category
            except ProductCategory.DoesNotExist:
                context['last_categories'] = []

        else:
            context['products'] = []

        if self.request.user.is_authenticated:
            cart_ids = CartProduct.objects.filter(user=self.request.user).values_list('product_id', flat=True)
            wishlist_ids = WishlistProduct.objects.filter(user=self.request.user).values_list('product_id', flat=True)
            context['user_cart_ids'] = list(cart_ids)
            context['user_wishlist_ids'] = list(wishlist_ids)
            context['user_registered_event_ids'] = list(
                EventRegistration.objects.filter(user=self.request.user).values_list('product_id', flat=True))
        else:
            context['user_cart_ids'] = []
            context['user_wishlist_ids'] = []
            context['user_registered_event_ids'] = []
        context['show_ratings'] = True
        logger.debug(f"Final context: {context.keys()}")
        logger.debug(f"Sample product rating: {context.get('products', [])[:1]}")
        return context

#-------------------------------------------------------------------------------------------------------------------------------------------


class SearchResultsListView(TemplateView):
    template_name = 'userdashboard/view/search_results_list.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        logger.debug(f"SearchResultsListView Context prepared: {context.keys()}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render_to_string(self.template_name, context, request=request)
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)
    
    def _add_delivery_dates(self, page_obj):
        if page_obj is None:
            return
        today = date.today()
        for product in page_obj:
            if getattr(product, "delivery_time", None) is not None:
                delivery = today + timedelta(days=product.delivery_time)
                product.delivery_date = delivery.strftime("%a, %d %b")
            else:
                product.delivery_date = "N/A"
        

    def get_context_data(self, **kwargs):
       
        context = super().get_context_data(**kwargs)

        category_id = self.request.GET.get('category')
        sub_category_id = self.request.GET.get('sub_category')
        last_category_id = self.request.GET.get('last_category')
        sort_by = self.request.GET.get('sort_by')
        page_number = self.request.GET.get('page', 1)
        search_query = self.request.GET.get('q', '').strip()

        # Base context
        context.update({
            'selected_category': None,
            'selected_sub_category': None,
            'selected_last_category': None,
            'page_obj': None,
            'total_products': 0,
            'search_query': search_query,
            'is_search_active': bool(search_query),
        })

        # Special categories
        special_category_names = ['Conference', 'Webinar', 'Event']

        # Last categories with products
        last_categories_with_products = ProductLastCategory.objects.annotate(
            product_count=Count('product', filter=Q(product__is_active=True))
        ).filter(product_count__gt=0)

        # Subcategories
        valid_subcategory_ids = last_categories_with_products.values_list('sub_category_id', flat=True).distinct()
        subcategories_with_products = ProductSubCategory.objects.filter(
            id__in=valid_subcategory_ids
        ).prefetch_related('productlastcategory_set')

        # Regular categories
        valid_category_ids = subcategories_with_products.values_list('category_id', flat=True).distinct()
        regular_categories = ProductCategory.objects.filter(
            id__in=valid_category_ids
        ).exclude(name__in=special_category_names).prefetch_related('productsubcategory_set')

        # Special categories with products
        special_categories = ProductCategory.objects.filter(
            name__in=special_category_names
        ).annotate(
            product_count=Count('product', filter=Q(product__is_active=True))
        ).filter(product_count__gt=0)

        # Conference products (limit 4)
        conference_products = Product.objects.filter(
            category__name__in=special_category_names,
            is_active=True
        ).annotate(
            effective_price=Case(
                When(offer_active=True, offer_percentage__isnull=False,
                     then=ExpressionWrapper(
                         F('price') * (1 - Coalesce(F('offer_percentage'), 0) / 100.0),
                         output_field=DecimalField(max_digits=10, decimal_places=2)
                     )),
                default=F('price'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).prefetch_related('images')[:4]

        # Attach category + last categories mapping
        category_last_map = {}
        for category in regular_categories:
            subcategories = subcategories_with_products.filter(category=category)
            last_cats = last_categories_with_products.filter(sub_category__in=subcategories)
            category_last_map[category.id] = last_cats

        # Add to context
        context['regular_categories'] = regular_categories
        context['special_categories'] = special_categories
        context['conference_products'] = conference_products
        context['category_last_map'] = category_last_map

        # Product queryset
        effective_price = ExpressionWrapper(
            F('price') * (1 - Coalesce(F('offer_percentage'), 0) / 100.0),
            output_field=DecimalField(max_digits=10, decimal_places=2)
        )
        products_qs = Product.objects.annotate(
            effective_price=Case(
                When(offer_active=True, offer_percentage__isnull=False, then=effective_price),
                default=F('price'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
                ),
            avg_rating=Coalesce(
                Avg('reviews__rating'),
                Value(0.0),
                output_field=DecimalField(max_digits=3, decimal_places=1)
            )
            
        ).prefetch_related('images')

        # Filtering + sorting
        if search_query:
            search_terms = search_query.lower().split()
            query = Q()
            for term in search_terms:
                query |= Q(name__icontains=term) | Q(keywords__icontains=term)
            products_qs = products_qs.filter(query, is_active=True).distinct()

            if sort_by == '1':
                products_qs = products_qs.order_by('-effective_price')
            elif sort_by == '2':
                products_qs = products_qs.order_by('effective_price')
            elif sort_by == '3':
                products_qs = products_qs.order_by('-avg_rating', '-created_at')  
            elif sort_by == '4':
                products_qs = products_qs.order_by('avg_rating', '-created_at')
            else:
                products_qs = products_qs.order_by('-created_at')

            paginator = Paginator(products_qs, 10)
            page_obj = paginator.get_page(page_number)
            self._add_delivery_dates(page_obj)
            context.update({
                'products': page_obj,
                'page_obj': page_obj,
                'paginator': paginator,
                'total_products': paginator.count,
            })

        elif last_category_id:
            try:
                last_category = ProductLastCategory.objects.get(id=last_category_id)
                products_qs = products_qs.filter(last_category=last_category, is_active=True)

                if sort_by == '1':
                    products_qs = products_qs.order_by('-effective_price')
                elif sort_by == '2':
                    products_qs = products_qs.order_by('effective_price')
                elif sort_by == '3':
                    products_qs = products_qs.order_by('-avg_rating', '-created_at')
                elif sort_by == '4':
                    products_qs = products_qs.order_by('avg_rating', '-created_at')
                else:
                    products_qs = products_qs.order_by('-created_at')

                paginator = Paginator(products_qs, 10)
                page_obj = paginator.get_page(page_number)
                self._add_delivery_dates(page_obj)

                context.update({
                    'products': page_obj,
                    'page_obj': page_obj,
                    'paginator': paginator,
                    'total_products': paginator.count,
                    'selected_last_category': last_category,
                    'selected_sub_category': last_category.sub_category,
                    'selected_category': last_category.sub_category.category,
                })
            except ProductLastCategory.DoesNotExist:
                context['products'] = []

        elif sub_category_id:
            try:
                sub_category = ProductSubCategory.objects.get(id=sub_category_id)
                context['last_categories'] = last_categories_with_products.filter(sub_category=sub_category)
                context['selected_sub_category'] = sub_category
                context['selected_category'] = sub_category.category
            except ProductSubCategory.DoesNotExist:
                context['last_categories'] = []

        elif category_id:
            try:
                try:
                    category_id_int = int(category_id)
                    category = ProductCategory.objects.get(id=category_id_int)
                except ValueError:
                    category = ProductCategory.objects.get(name=category_id)

                if category.name in special_category_names:
                    products_qs = products_qs.filter(category=category, is_active=True)
                    if sort_by == '1':
                        products_qs = products_qs.order_by('-effective_price')
                    elif sort_by == '2':
                        products_qs = products_qs.order_by('effective_price')
                    elif sort_by == '3':
                        products_qs = products_qs.order_by('-avg_rating', '-created_at')
                    elif sort_by == '4':
                        products_qs = products_qs.order_by('avg_rating', '-created_at')
                    else:
                        products_qs = products_qs.order_by('-created_at')

                    paginator = Paginator(products_qs, 10)
                    page_obj = paginator.get_page(page_number)
                    

                    context.update({
                        'products': page_obj,
                        'page_obj': page_obj,   
                        'paginator': paginator,
                        'total_products': paginator.count,
                        'selected_category': category
                    })
                else:
                    subcategories = ProductSubCategory.objects.filter(category=category)
                    context['last_categories'] = last_categories_with_products.filter(sub_category__in=subcategories)
                    context['selected_category'] = category
            except ProductCategory.DoesNotExist:
                context['last_categories'] = []

        else:
            context['products'] = []

        if self.request.user.is_authenticated:
            cart_ids = CartProduct.objects.filter(user=self.request.user).values_list('product_id', flat=True)
            wishlist_ids = WishlistProduct.objects.filter(user=self.request.user).values_list('product_id', flat=True)
            context['user_cart_ids'] = list(cart_ids)
            context['user_wishlist_ids'] = list(wishlist_ids)
            context['user_registered_event_ids'] = list(
                EventRegistration.objects.filter(user=self.request.user).values_list('product_id', flat=True))
        else:
            context['user_cart_ids'] = []
            context['user_wishlist_ids'] = []
            context['user_registered_event_ids'] = []
            context['show_ratings'] = True

        return context


# views.py - Updated ProductDetailsView

from django.views.generic import TemplateView
from django.core.paginator import Paginator
from django.db.models import Avg

class ProductDetailsView(TemplateView):
    template_name = 'userdashboard/view/product_details.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pk = self.kwargs.get('pk')

        if pk:
            try:
                product = Product.objects.select_related(
                    'category', 'sub_category', 'last_category', 'brand', 'event'
                ).get(id=pk)

                main_img = ProductImage.objects.filter(product=product, is_main=True).first()
                product.main_image = main_img.image.url if main_img else None
                other_images = ProductImage.objects.filter(product=product).exclude(id=main_img.id if main_img else None)

                # Reviews with pagination
                reviews_qs = RatingReview.objects.filter(product=product).order_by('-created_at')
                reviews_page_number = self.request.GET.get('rpage', 1)
                reviews_paginator = Paginator(reviews_qs, 3) 
                reviews_page = reviews_paginator.get_page(reviews_page_number)
                
                rating_counts = {i: reviews_qs.filter(rating=i).count() for i in range(1, 6)}
                total_reviews = reviews_qs.count()
                avg_rating = reviews_qs.aggregate(avg=Avg('rating'))['avg'] or 0

                stock_status = ""
                if product.stock_quantity == 0:
                    stock_status = "Out of Stock"
                elif product.stock_quantity < 5:
                    stock_status = f"Hurry, only {product.stock_quantity} available"
                elif product.stock_quantity < 10:
                    stock_status = "Only a few available"

                related_products = []
                if product.category and product.category.name.lower() not in ['event', 'webinar', 'conference']:
                    related_products = Product.objects.filter(
                        last_category=product.last_category
                    ).exclude(id=product.id).select_related('brand', 'last_category')[:4] 

                    for related_product in related_products:
                        main_img = ProductImage.objects.filter(product=related_product, is_main=True).first()
                        related_product.main_image = main_img.image.url if main_img else None

                # User-specific data
                user = self.request.user
                if user.is_authenticated:
                    user_cart_ids = list(CartProduct.objects.filter(user=user).values_list('product_id', flat=True))
                    user_cart_quantities = {
                        item.product.id: item.quantity
                        for item in CartProduct.objects.filter(user=user)
                    }
                    user_wishlist_ids = list(WishlistProduct.objects.filter(user=user).values_list('product_id', flat=True))
                else:
                    user_cart_ids = []
                    user_cart_quantities = {}
                    user_wishlist_ids = []
                
                event = product.event if hasattr(product, 'event') and product.event else None

                # Questions pagination
                questions_qs = (
                    Question.objects
                    .select_related('user')
                    .filter(product=product)
                    .order_by('-created_at')
                )
                page = self.request.GET.get("qpage", 1)
                paginator = Paginator(questions_qs, 5)
                questions_page = paginator.get_page(page)

                context.update({
                    'product': product,
                    'other_images': other_images,
                    'reviews': reviews_page, 
                    'rating_counts': rating_counts,
                    'total_reviews': total_reviews,
                    'average_rating': round(avg_rating, 1),
                    'user_cart_ids': user_cart_ids,
                    'user_cart_quantities': user_cart_quantities, 
                    'user_wishlist_ids': user_wishlist_ids,
                    'event': event,
                    "questions": questions_page, 
                    'stock_status': stock_status,
                    'related_products': related_products,  
                })

            except Product.DoesNotExist:
                context['product'] = None
                context['other_images'] = []
                context['event'] = None
                context['related_products'] = [] 

        return context

class EventRegistrationView(View):
    def post(self, request):
        product_id = request.POST.get('product_id')
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        message = request.POST.get('message')

        if not full_name or not email:
            messages.error(request, "Full name and email are required.")
            return redirect('dashboard:product_detail', pk=product_id)

        try:
            product = Product.objects.get(id=product_id)
            event = product.event
            EventRegistration.objects.create(
                product=product,
                event = event,
                full_name=full_name,
                email=email,
                message=message,
                user=request.user if request.user.is_authenticated else None
            )
            messages.success(request, "Successfully registered for the event!")
        except Product.DoesNotExist:
            messages.error(request, "Product not found.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

        return redirect('dashboard:product_detail', pk=product_id)


class EventRegisteredDataView(TemplateView):
    template_name = 'userdashboard/view/event_registered_data.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pk = self.kwargs.get('pk')

        try:
            product = Product.objects.select_related('event').get(id=pk)
            event = product.event if hasattr(product, 'event') and product.event else None
            registrations = EventRegistration.objects.filter(product=product).order_by('-registered_at')

            context.update({
                'product': product,
                'event': event,
                'registrations': registrations,
            })
        except Product.DoesNotExist:
            context.update({
                'product': None,
                'event': None,
                'registrations': [],
            })

        return context


# class OrderSummaryView(LoginRequiredMixin, TemplateView):
#     template_name = 'userdashboard/view/cart_summary.html'
#     login_url = 'dashboard:login'
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         cart_items = CartProduct.objects.filter(user=self.request.user).select_related('product')
#         total = sum(item.get_total_price() for item in cart_items)
#         context['cart_items'] = cart_items
#         context['total'] = total
#         return context


class CartAddView(LoginRequiredMixin, View):
    def get(self, request):
        cart_items = CartProduct.objects.filter(user=request.user).select_related('product')
        cart_data = []
        for item in cart_items:
            image = ''
            if item.product.images.exists():
                image = item.product.images.first().image.url

            cart_data.append({
                'id': item.product.id,
                'name': item.product.name,
                'price': str(item.product.price),
                'quantity': item.quantity,
                'image': image
            })

        return JsonResponse({'cart': cart_data})

    def post(self, request, *args, **kwargs):
        product_id = request.POST.get('product_id')
        quantity = int(request.POST.get('quantity', 1))
        product = get_object_or_404(Product, id=product_id)

        cart_item, created = CartProduct.objects.get_or_create(
            user=request.user,
            product=product
        )

        if not created:
            cart_item.quantity += quantity
        else:
            cart_item.quantity = quantity

        cart_item.save()
        return JsonResponse({'status': 'success', 'message': 'Product added to cart'})


class RemoveFromCartView(View):
    def post(self, request):
        item_id = request.POST.get('item_id')
        try:
            item = CartProduct.objects.get(product_id=item_id, user=request.user)

            item.delete()
            return JsonResponse({'status': 'success'})
        except CartProduct.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Item not found'})


def clearcart(request):
    if request.method == 'POST':
        user = request.user
        CartProduct.objects.filter(user=user).delete()
        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


class WishlistToggleView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        product_id = request.POST.get('product_id')
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return JsonResponse(
                {'status': 'error', 'message': 'Product not found'},
                status=400
            )
        wishlist_item, created = WishlistProduct.objects.get_or_create(
            user=request.user,
            product=product
        )
        if not created:
            wishlist_item.delete()
            user_deleted_activity(
                request.user,
                f"Removed {product.name} from wishlist"
            )
            return JsonResponse({'status': 'removed'})
        user_created_activity(
            request.user,
            f"Added {product.name} to wishlist"
        )
        return JsonResponse({'status': 'added'})

class WishlistClearView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        count = WishlistProduct.objects.filter(user=request.user).count()
        WishlistProduct.objects.filter(user=request.user).delete()

        if count:
            user_deleted_activity(
                request.user,
                f"Cleared wishlist ({count} items removed)"
            )

        return JsonResponse({'status': 'cleared'})
class WishlistView(LoginRequiredMixin, TemplateView):
    template_name = 'userdashboard/view/wishlist.html'
    login_url = 'dashboard:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        wishlist_items = WishlistProduct.objects.filter(
            user=self.request.user
        ).select_related('product')

        for item in wishlist_items:
            main_img = ProductImage.objects.filter(
                product=item.product,
                is_main=True
            ).first()
            item.product.main_image = main_img.image if main_img else None

        paginator = Paginator(wishlist_items, 5)
        page_obj = paginator.get_page(self.request.GET.get('page'))

        context['wishlist_items'] = page_obj
        context['page_obj'] = page_obj
        user_update_activity(
            self.request.user,
            "Viewed wishlist"
        )

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
                "image": item.product.get_main_image(),
                # "image": item.product.images.first().image.url if item.product.images.exists() else None,
            }
            for item in wishlist_items
        ]
        return JsonResponse(data, safe=False)


class ShoppingCartView(LoginRequiredMixin, TemplateView):
    template_name = 'userdashboard/view/shopping_cart.html'
    login_url = 'dashboard:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        cart_items = CartProduct.objects.filter(user=user).select_related('product')
        total = sum(item.get_total_price() for item in cart_items)

        discount_amount = Decimal('0.00')
        applied_coupon_data = None
        has_discount = False

        session_coupon = self.request.session.get('applied_coupon')

        if session_coupon:
            try:
                coupon = Coupon.objects.get(code__iexact=session_coupon['code'])

                if coupon.is_valid_now():
                    eligible_products = coupon.products.values_list('id', flat=True)
                    eligible_items = (
                        cart_items.filter(product_id__in=eligible_products)
                        if eligible_products.exists()
                        else cart_items
                    )

                    if eligible_items.exists():
                        eligible_total = sum(item.get_total_price() for item in eligible_items)

                        if eligible_total >= coupon.minimum_purchase_amount:
                            discount_amount = coupon.calculate_discount(Decimal(eligible_total))
                            applied_coupon_data = {
                                'code': coupon.code,
                                'discount_amount': f"{discount_amount:.2f}",
                            }
                            has_discount = discount_amount > Decimal('0.00')
                        else:
                            self.request.session.pop('applied_coupon', None)
            except Coupon.DoesNotExist:
                self.request.session.pop('applied_coupon', None)

        final_total = total - discount_amount

        paginator = Paginator(cart_items, 5)
        page_obj = paginator.get_page(self.request.GET.get('page'))

        context.update({
            'cart_items': page_obj,
            'subtotal': f"{total:.2f}",
            'discount_amount': f"{discount_amount:.2f}",
            'final_total': f"{final_total:.2f}",
            'applied_coupon': applied_coupon_data,
            'has_discount': has_discount,
        })

        return context

@require_POST
def apply_coupon(request):
    code = request.POST.get('coupon_code', '').strip()
    user = request.user
    cart_items = CartProduct.objects.filter(user=user)
    if not cart_items.exists():
        return JsonResponse({'status': 'error', 'message': 'Your cart is empty.'})

    total = sum(item.get_total_price() for item in cart_items)
    try:
        coupon = Coupon.objects.get(code__iexact=code)
    except Coupon.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Invalid coupon code.'})
    if not coupon.is_valid_now():
        return JsonResponse({'status': 'error', 'message': 'This coupon has expired.'})

    if coupon.client.exists() and user not in coupon.client.all():
        return JsonResponse({'status': 'error', 'message': 'You are not eligible for this coupon.'})

    eligible_product_ids = coupon.products.values_list('id', flat=True)

    if eligible_product_ids.exists():
        eligible_cart_items = cart_items.filter(product_id__in=eligible_product_ids)
        if not eligible_cart_items.exists():
            return JsonResponse({'status': 'error', 'message': 'This coupon does not apply to selected products in your cart.'})
    else:
        eligible_cart_items = cart_items 

    eligible_total = sum(item.get_total_price() for item in eligible_cart_items)

    if eligible_total < coupon.minimum_purchase_amount:
        return JsonResponse({
            'status': 'error',
            'message': f'Minimum purchase of ${coupon.minimum_purchase_amount:.2f} required to use this coupon.'
        })

    used_count = user.applied_coupons.filter(id=coupon.id).count()
    if used_count >= coupon.count_of_use:
        return JsonResponse({'status': 'error', 'message': 'You have reached the coupon usage limit.'})

    if coupon.filter_by_orders_amount and total < coupon.filter_by_orders_amount:
        return JsonResponse({'status': 'error', 'message': 'Your order does not meet the minimum required amount.'})
    discount_amount = coupon.calculate_discount(Decimal(eligible_total))
    new_total = total - discount_amount

    request.session['applied_coupon'] = {
        'code': coupon.code,
        'discount_amount': str(discount_amount),
        'new_total': str(new_total),
    }
    coupon.client.add(user)

    return JsonResponse({
        'status': 'success',
        'message': f'Coupon applied successfully! You saved ${discount_amount:.2f}.',
        'discount_amount': f'{discount_amount:.2f}',
        'new_total': f'{new_total:.2f}',
        'coupon_code': coupon.code,
    })
@require_POST
def remove_coupon(request):
    user = request.user
    if 'applied_coupon' in request.session:
        coupon_code = request.session['applied_coupon'].get('code')
        del request.session['applied_coupon']
        try:
            coupon = Coupon.objects.get(code__iexact=coupon_code)
            coupon.client.remove(user)
        except Coupon.DoesNotExist:
            pass
        cart_items = CartProduct.objects.filter(user=user)
        subtotal = sum(item.get_total_price() for item in cart_items) if cart_items.exists() else Decimal('0.00')
        
        return JsonResponse({
            'status': 'success',
            'message': 'Coupon removed successfully.',
            'subtotal': f'{subtotal:.2f}',
            'new_total': f'{subtotal:.2f}',
        })
    
    return JsonResponse({
        'status': 'error',
        'message': 'No coupon to remove.',
    })
@require_POST
@require_POST
def add_to_cart(request):
    product_id = request.POST.get('product_id')
    quantity_change = int(request.POST.get('quantity', 1))
    try:
        product = get_object_or_404(Product, id=product_id)

        # Check if product is out of stock
        if product.is_out_of_stock():
            return JsonResponse({
                'status': 'error',
                'message': 'This product is currently out of stock'
            }, status=400)

        cart_item, created = CartProduct.objects.get_or_create(
            user=request.user,
            product=product,
            defaults={'quantity': 0}
        )
        new_quantity = cart_item.quantity + quantity_change
        
        # Check if requested quantity exceeds available stock
        if new_quantity > product.available_stock():
            return JsonResponse({
                'status': 'error',
                'message': f'Only {product.available_stock()} units available in stock'
            }, status=400)
        
        if new_quantity <= 0:
            cart_item.delete()
            user_deleted_activity(
                request.user,
                f"Removed {product.name} from cart"
            )
            return JsonResponse({'status': 'removed'})
        
        cart_item.quantity = new_quantity
        cart_item.save()
        
        if created:
            user_created_activity(
                request.user,
                f"Added {product.name} to cart (Qty: {new_quantity})"
            )
        else:
            user_update_activity(
                request.user,
                f"Updated {product.name} quantity to {new_quantity}"
            )
        return JsonResponse({'status': 'success', 'quantity': new_quantity})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@require_POST
def update_cart_item(request):
    product_id = request.POST.get('product_id')
    quantity = int(request.POST.get('quantity', 1))
    try:
        cart_item = CartProduct.objects.get(
            user=request.user,
            product_id=product_id
        )
        product = cart_item.product
        product_name = product.name
        
        # Check if product is out of stock
        if product.is_out_of_stock():
            return JsonResponse({
                'status': 'error',
                'message': 'This product is currently out of stock'
            }, status=400)
        
        if quantity <= 0:
            cart_item.delete()
            user_deleted_activity(
                request.user,
                f"Removed {product_name} from cart"
            )
            return JsonResponse({'status': 'removed'})
        
        # Check if requested quantity exceeds available stock
        if quantity > product.available_stock():
            return JsonResponse({
                'status': 'error',
                'message': f'Only {product.available_stock()} units available in stock'
            }, status=400)
        
        cart_item.quantity = quantity
        cart_item.save()

        user_update_activity(
            request.user,
            f"Updated {product_name} quantity to {quantity}"
        )
        return JsonResponse({'status': 'success', 'quantity': quantity})
    except CartProduct.DoesNotExist:
        product = get_object_or_404(Product, id=product_id)
        
        # Check if product is out of stock
        if product.is_out_of_stock():
            return JsonResponse({
                'status': 'error',
                'message': 'This product is currently out of stock'
            }, status=400)
        
        # Check if requested quantity exceeds available stock
        if quantity > product.available_stock():
            return JsonResponse({
                'status': 'error',
                'message': f'Only {product.available_stock()} units available in stock'
            }, status=400)

        CartProduct.objects.create(
            user=request.user,
            product=product,
            quantity=quantity
        )
        user_created_activity(
            request.user,
            f"Added {product.name} to cart (Qty: {quantity})"
        )
        return JsonResponse({'status': 'success', 'quantity': quantity})


@require_POST
def remove_from_cart(request):
    item_id = request.POST.get('item_id')
    try:
        cart_item = get_object_or_404(
            CartProduct,
            product__id=item_id,
            user=request.user
        )
        product_name = cart_item.product.name
        cart_item.delete()

        user_deleted_activity(
            request.user,
            f"Removed {product_name} from cart"
        )
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
class ShippingInfoView(LoginRequiredMixin, TemplateView):
    template_name = 'userdashboard/view/shipping_info.html'
    login_url = 'dashboard:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['user'] = user

        profile_type = None
        try:
            profile = RetailProfile.objects.get(user=user)
            phone = profile.phone
            profile_type = 'retailer'
        except RetailProfile.DoesNotExist:
            try:
                profile = WholesaleBuyerProfile.objects.get(user=user)
                phone = profile.phone
                profile_type = 'wholesaler'
            except WholesaleBuyerProfile.DoesNotExist:
                try:
                    profile = SupplierProfile.objects.get(user=user)
                    phone = profile.phone
                    profile_type = 'supplier'
                except SupplierProfile.DoesNotExist:
                    phone = None

        context['phone'] = phone
        context['profile_type'] = profile_type
        addresses = CustomerBillingAddress.objects.filter(user=user, is_deleted=False)
        default_address = CustomerBillingAddress.objects.filter(
            user=user, is_default=True, is_deleted=False
        ).first()
        context['addresses'] = addresses
        context['default_address'] = default_address
        context['display_payment_button'] = bool(addresses and default_address)

        cart_items = CartProduct.objects.filter(user=user).select_related('product')
        subtotal = sum(item.get_total_price() for item in cart_items) or Decimal('0.00')
        shipping = Decimal('0.00')
        vat = Decimal('0.00')
        total = subtotal + shipping + vat

        context['cart_items'] = cart_items
        context['order_summary'] = {
            'subtotal': subtotal,
            'shipping': shipping,
            'vat': vat,
            'total': total,
            'discount_amount': Decimal('0.00'),
            'coupon_code': None,
        }
        applied_coupon = self.request.session.get('applied_coupon')

        if not applied_coupon or not cart_items.exists():
            self.request.session.pop('applied_coupon', None)
            return context

        try:
            coupon = Coupon.objects.get(code__iexact=applied_coupon.get('code'))
        except Coupon.DoesNotExist:

            self.request.session.pop('applied_coupon', None)
            return context
        previous_discount_total = Decimal(applied_coupon.get('new_total', '0.00'))
        current_subtotal = subtotal


        if not coupon.is_valid_now() or current_subtotal + shipping + vat != previous_discount_total + Decimal(applied_coupon.get('discount_amount', '0.00')):

            self.request.session.pop('applied_coupon', None)
            return context

        discount_amount = Decimal(applied_coupon.get('discount_amount', '0.00'))
        new_total = total - discount_amount

        context['order_summary']['discount_amount'] = discount_amount
        context['order_summary']['total'] = new_total
        context['order_summary']['coupon_code'] = coupon.code

        return context
class AddAddressView(LoginRequiredMixin, FormView):
    form_class = AddressForm
    template_name = 'userdashboard/view/add_address.html'
    success_url = reverse_lazy('dashboard:shipping_info')

    def form_valid(self, form):
        address = form.save(commit=False)
        address.user = self.request.user
        if address.is_default:
            CustomerBillingAddress.objects.filter(
                user=self.request.user,
                is_default=True
            ).update(is_default=False)
        address.save()
        user_created_activity(
            self.request.user,
            "Added a new billing/shipping address"
        )
        messages.success(self.request, "Address added successfully.")
        return super().form_valid(form)
    def form_invalid(self, form):
        messages.error(self.request, "Failed to add address. Please check the form.")
        return super().form_invalid(form)


class ManageAddressView(LoginRequiredMixin, FormView):
    form_class = AddressForm
    template_name = 'userdashboard/view/add_address.html'
    def form_valid(self, form):
        address = form.save(commit=False)
        address.user = self.request.user
        if address.is_default:
            CustomerBillingAddress.objects.filter(
                user=self.request.user, is_default=True
            ).update(is_default=False)
        address.save()
        user_created_activity(
            self.request.user,
            f"Added new address ID #{address.id}"
        )
        return JsonResponse({
            "status": "success",
            "message": "Address added successfully."
        })

    def form_invalid(self, form):
        return JsonResponse({
            "status": "error",
            "message": "Failed to add address",
            "errors": form.errors
        }, status=400)

class EditAddressView(LoginRequiredMixin, UpdateView):
    model = CustomerBillingAddress
    form_class = AddressForm
    template_name = 'userdashboard/view/edit_address.html'
    success_url = reverse_lazy('dashboard:shipping_info')
    def get_queryset(self):
        return CustomerBillingAddress.objects.filter(
            user=self.request.user,
            is_deleted=False
        )
    def form_valid(self, form):
        address = form.save(commit=False)

        if address.is_default:
            CustomerBillingAddress.objects.filter(
                user=self.request.user,
                is_default=True
            ).exclude(id=address.id).update(is_default=False)
        address.save()
        user_update_activity(
            self.request.user,
            f"Updated address ID #{address.id}"
        )
        user_update_activity(
            self.request.user,
            f"Updated address ID #{address.id}"
        )
        messages.success(self.request, "Address updated successfully.")
        return super().form_valid(form)
    def form_invalid(self, form):
        messages.error(self.request, "Failed to update address. Please check the form.")
        return super().form_invalid(form)
class RemoveAddressView(LoginRequiredMixin, View):
    def post(self, request, address_id):
        address = get_object_or_404(
            CustomerBillingAddress,
            id=address_id,
            user=request.user,
            is_deleted=False
        )
        address.is_deleted = True
        address.save()
        user_deleted_activity(
            request.user,
            f"Removed address ID #{address.id}"
        )
        user_deleted_activity(
            request.user,
            f"Removed address ID #{address.id}"
        )
        messages.success(self.request, "Address removed successfully.")
        return redirect('dashboard:shipping_info')

class SetDefaultAddressView(LoginRequiredMixin, View):
    def post(self, request):
        address_id = self.request.GET.get('address_id')
        address = get_object_or_404(CustomerBillingAddress, id=address_id, user=self.request.user, is_deleted=False)
        CustomerBillingAddress.objects.filter(user=self.request.user, is_default=True).update(is_default=False)
        address.is_default = True
        address.save()
        return JsonResponse({'status': 'success'})




class ManageEditAddressView(LoginRequiredMixin, UpdateView):
    model = CustomerBillingAddress
    form_class = AddressForm
    template_name = 'userdashboard/view/edit_address.html'
    success_url = reverse_lazy('dashboard:shipping_info')

    def get_queryset(self):
        return CustomerBillingAddress.objects.filter(user=self.request.user, is_deleted=False)

    def form_valid(self, form):
        address = form.save(commit=False)
        if address.is_default:
            CustomerBillingAddress.objects.filter(
                user=self.request.user,
                is_default=True
            ).exclude(id=address.id).update(is_default=False)
        address.save()

        return JsonResponse({
            "status": "success",
            "message": "Address updated successfully."
        })

    def form_invalid(self, form):
        return JsonResponse({
            "status": "error",
            "message": "Failed to update address",
            "errors": form.errors
        }, status=400)


class ManageRemoveAddressView(LoginRequiredMixin, View):
    def post(self, request, address_id):
        address = get_object_or_404(
            CustomerBillingAddress,
            id=address_id,
            user=request.user,
            is_deleted=False
        )
        address.is_deleted = True
        address.save()

        return JsonResponse({
            "status": "success",
            "message": "Address removed successfully."
        })


def generate_order_id():
    import uuid
    return f"X{uuid.uuid4().hex[:6].upper()}-S{timezone.now().strftime('%y')}"


def create_orders_from_cart(user, payment_type, payment_status, payment):
    try:
        print('create order from cart----------------------')
        cart_items = CartProduct.objects.filter(user=user).select_related('product')
        if not cart_items.exists():
            logger.error(f"No cart items found for user {user.id}")
            raise ValueError("Cart is empty")

        billing = CustomerBillingAddress.objects.filter(
            user=user, is_default=True, is_deleted=False
        ).first()

        if not billing:
            logger.error(f"No default billing address found for user {user.id}")
            raise ValueError("No default billing address found")

        subtotal = sum(item.get_total_price() for item in cart_items)
        shipping_fees = Decimal('00.00')
        total = subtotal + shipping_fees

        with transaction.atomic():

            # Create ORDER
            order = Order.objects.create(
                user=user,
                payment=payment,
                order_id=generate_order_id(),
                shipping_fees=shipping_fees,
                shipping_type='Standard Shipping',
                shipping_full_address=billing.customer_address1 + (
                    f", {billing.customer_address2}" if billing.customer_address2 else ""
                ),
                shipping_city=billing.customer_city,
                shipping_country=billing.customer_country,
                status='pending',
                created_at=timezone.now()
            )

            logger.info(f"Created Order {order.order_id} (ID: {order.id}) for user {user.id} with payment {payment.id}")

            # --------------------------
            # STOCK REDUCTION HERE 🔥
            # --------------------------
            for item in cart_items:
                product = item.product

                # 1. CHECK STOCK
                if product.stock_quantity < item.quantity:
                    raise ValueError(f"Not enough stock for {product.name}")

                # 2. REDUCE STOCK
                product.stock_quantity -= item.quantity

                # 3. LOW STOCK TAG UPDATE
                if product.stock_quantity <= product.low_stock_alert:
                    product.tag = "limited"

                # 4. SAVE PRODUCT
                product.save()

                # --------------------------
                # CREATE ORDER ITEM
                # --------------------------
                OrderItem.objects.create(
                    order=order,
                    order_by=user,
                    order_to=product.created_by,
                    product=product,
                    quantity=item.quantity,
                    price=product.discounted_price(),
                    payment_type=payment_type,
                    payment_status=payment_status,
                    payment_currency='USD' if payment_type in ['stripe', 'cod'] else 'INR',
                    phone_number=billing.phone,
                    status='pending'
                )

                logger.info(
                    f"Created OrderItem for product {product.id} (qty: {item.quantity}) in Order {order.order_id} "
                    f"and updated stock to {product.stock_quantity}"
                )

            # CLEAR CART
            cart_items.delete()
            logger.info(f"Cleared cart for user {user.id}")
            print('created order ----------------------')

            return order

    except Exception as e:
        logger.error(f"Failed to create order for user {user.id}: {str(e)}", exc_info=True)
        raise


class PaymentMethodView(LoginRequiredMixin, View):
    template_name = 'userdashboard/view/payment_method.html'
    login_url = 'dashboard:login'

    def get_stripe_key(self, request):
        return settings.STRIPE_PUBLISHABLE_KEY, settings.STRIPE_SECRET_KEY

    def get_context_data(self, request):
        cart_items = CartProduct.objects.filter(user=request.user).select_related('product')
        subtotal = sum(item.get_total_price() for item in cart_items) or Decimal('0.00')
        shipping = Decimal('00.00')
        vat = Decimal('0.00')
        coupon_discount = Decimal('0.00')
        if 'applied_coupon' in request.session:
            coupon_data = request.session.get('applied_coupon', {})
            if coupon_data and 'discount_amount' in coupon_data:
                coupon_discount = Decimal(str(coupon_data['discount_amount']))

  
        total = subtotal - coupon_discount + shipping + vat

        billing = CustomerBillingAddress.objects.filter(
            user=request.user, is_default=True, is_deleted=False
        ).first()

        return {
            'cart_items': cart_items,
            'order_summary': {
                'subtotal': subtotal,
                'shipping': shipping,
                'vat': vat,
                'coupon_discount': coupon_discount,
                'total': total
            },
            'billing': billing,
            'currency_symbol': 'USD'
        }


    def get(self, request):
        public_key, _ = self.get_stripe_key(request)
        context = self.get_context_data(request)
        total = context['order_summary']['total']
        amount_in_paise = int(total * 100)
        
       
        if amount_in_paise < 100:
            messages.error(request, "Your order total must be at least ₹1/$1. Please add items to your cart.")
            return redirect("dashboard:shopping_cart")

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        razorpay_order = client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "payment_capture": "1"
        })

        context.update({
            "STRIPE_PUBLIC_KEY": public_key,
            "RAZORPAY_KEY_ID": settings.RAZORPAY_KEY_ID,
            "razorpay_amount_in_paise": amount_in_paise,
            "razorpay_order_id": razorpay_order['id'],
        })
        return render(request, self.template_name, context)

    def post(self, request):
        context = self.get_context_data(request)
        total = context['order_summary']['total']
        user = request.user
        if not user or not user.is_authenticated:
            logger.error("Unauthenticated user attempted payment")
            messages.error(request, "You must be logged in to process payment.")
            return redirect("dashboard:login")

        if not context['billing']:
            logger.error(f"No billing address for user {user.id}")
            messages.error(request, "Please select a billing address.")
            return redirect("dashboard:shipping_info")

        MIN_ORDER_AMOUNT = Decimal('1.00')
        if total < MIN_ORDER_AMOUNT:
            logger.error(f"Order total {total} is less than minimum {MIN_ORDER_AMOUNT} for user {user.id}")
            messages.error(request, "Your order total must be at least $1. Please add more items to your cart.")
            return redirect("dashboard:shopping_cart")

        payment_method = request.POST.get("payment_method")
        logger.info(f"Processing {payment_method} payment for user {user.id}, total: {total}")
      

        try:
            with transaction.atomic():
                if payment_method == "cod":
                    payment = Payment.objects.create(
                        user=user,
                        name=user.get_full_name() or user.email,
                        amount=total,
                        payment_method="cod",
                        paid=False
                    )
                    logger.info(f"Created COD Payment {payment.id} for user {user.id}")

                    delivery_partner, _ = DeliveryPartner.objects.get_or_create(name="Delhivery")
                    CODPayment.objects.create(
                        user=user,
                        name=user.get_full_name() or user.email,
                        amount=total,
                        paid=False,
                        cod_tracking_id="COD123456",  
                        delivery_partner=delivery_partner
                    )

                    order = create_orders_from_cart(user, payment_type="cod", payment_status="unpaid", payment=payment)
                    user_purchase_activity(
                        user,
                        "Order placed using Cash on Delivery",
                        amount=total
                    )

                    messages.success(request, "Order Placed Successfully")
                    return redirect("dashboard:order_placed")

                elif payment_method == "stripe":
                    _, stripe_secret = self.get_stripe_key(request)
                    stripe.api_key = stripe_secret
                    token = request.POST.get("stripeToken")
                    crd_name = request.POST.get("crd_name")

                    customer = stripe.Customer.create(
                        email=user.email,
                        name=crd_name,
                    )

                    pm = stripe.PaymentMethod.create(
                        type="card",
                        card={"token": token}
                    )

                    stripe.PaymentMethod.attach(
                        pm.id,
                        customer=customer.id
                    )

                    stripe.Customer.modify(
                        customer.id,
                        invoice_settings={"default_payment_method": pm.id}
                    )

                    intent = stripe.PaymentIntent.create(
                        amount=int(total * 100),
                        currency="usd",
                        customer=customer.id,
                        payment_method=pm.id,
                        confirm=True,
                        off_session=True,
                        description="Product Payment",
                        automatic_payment_methods={
                            "enabled": True,
                            "allow_redirects": "never"
                        }
                    )

                    payment = Payment.objects.create(
                        user=user,
                        name=crd_name,
                        amount=total,
                        payment_method="stripe",
                        paid=True
                    )

                    stripe_payment, created = StripePayment.objects.update_or_create(
                        payment=payment,
                        defaults={
                            "user": user,
                            "name": crd_name,
                            "amount": total,
                            "paid": True,
                            "stripe_charge_id": intent.latest_charge,
                            "stripe_payment_intent_id": intent.id,
                            "stripe_customer_id": customer.id,
                            "stripe_signature": intent.payment_method,
                        }
                    )

                    order = create_orders_from_cart(user, payment_type="stripe", payment_status="paid", payment=payment)
                    user_purchase_activity(
                        user,
                        "Payment completed via Stripe",
                        amount=total
                    )

                    messages.success(request, "Payment Done Successfully.")
                    return redirect("dashboard:order_placed")

                elif payment_method == "razorpay":
                    razorpay_payment_id = request.POST.get("razorpay_payment_id")
                    razorpay_order_id = request.POST.get("razorpay_order_id")
                    razorpay_signature = request.POST.get("razorpay_signature")

                    if not razorpay_payment_id:
                        logger.error(f"Razorpay payment failed for user {user.id}: No payment ID")
                        messages.error(request, "Razorpay payment failed.")
                        return redirect("dashboard:payment_method")

                    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                    params_dict = {
                        "razorpay_order_id": razorpay_order_id,
                        "razorpay_payment_id": razorpay_payment_id,
                        "razorpay_signature": razorpay_signature
                    }

                    client.utility.verify_payment_signature(params_dict)

                    payment = Payment.objects.create(
                        user=user,
                        name=user.get_full_name() or user.email,
                        amount=total,
                        payment_method="razorpay",
                        paid=True
                    )
                    logger.info(f"Created Razorpay Payment {payment.id} for user {user.id}")

                    RazorpayPayment.objects.create(
                        user=user,
                        name=user.get_full_name() or user.email,
                        amount=total,
                        paid=True,
                        razorpay_payment_id=razorpay_payment_id,
                        razorpay_order_id=razorpay_order_id,
                        razorpay_signature=razorpay_signature
                    )

                    order = create_orders_from_cart(user, payment_type="razorpay", payment_status="paid", payment=payment)
                    user_purchase_activity(
                        user,
                        "Payment completed via Razorpay",
                        amount=total
                    )
                    messages.success(request, "Payment Done Successfully.")
                    return redirect("dashboard:order_placed")

                elif payment_method == "bank_transfer":
                    proof_image = request.FILES.get("proof_image")

                    payment = Payment.objects.create(
                        user=user,
                        name=user.get_full_name() or user.email,
                        amount=total,
                        payment_method="bank_transfer",
                        paid=False
                    )
                    logger.info(f"Created Bank Transfer Payment {payment.id} for user {user.id}")

                    BankTransferPayment.objects.create(
                        user=user,
                        name=user.get_full_name() or user.email,
                        amount=total,
                        paid=False,
                        proof_image=proof_image,
                        verified_by_admin=False,
                        admin_notes="Pending admin verification"
                    )

                    order = create_orders_from_cart(user, payment_type="bank_transfer", payment_status="unpaid", payment=payment)
                    user_purchase_activity(
                        user,
                        "Order placed via Bank Transfer (Pending verification)",
                        amount=total
                    )
                    messages.success(request, "Order Placed Successfully. Awaiting admin verification.")
                    return redirect("dashboard:order_placed")

                else:
                    logger.error(f"Invalid payment method {payment_method} for user {user.id}")
                    messages.error(request, "Invalid payment method.")
                    return redirect("dashboard:payment_method")

        except Exception as e:
            logger.error(f"Payment processing failed for user {user.id}: {str(e)}", exc_info=True)
            messages.error(request, f"Payment processing failed: {str(e)}")
            return redirect("dashboard:payment_method")


class OrderPlacedView(LoginRequiredMixin, TemplateView):
    template_name = 'userdashboard/view/order_placed.html'
    login_url = 'dashboard:login'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            logger.warning(f"Unauthenticated access attempt to OrderPlacedView")
            return redirect(self.login_url)

        payment = Payment.objects.filter(user=request.user).order_by('-created_at').first()
        if not payment:
            logger.error(f"No payment found for user {request.user.id}")
            messages.error(request, "No recent payment found.")
            return redirect('dashboard:shopping_cart')

        order_exists = Order.objects.filter(payment=payment, user=request.user).exists()
        if not order_exists:
            logger.error(
                f"No order found for payment {payment.id} (method: {payment.payment_method}, created: {payment.created_at}) and user {request.user.id}"
            )
            recent_order = Order.objects.filter(user=request.user).order_by('-created_at').first()
            if recent_order:
                logger.warning(
                    f"Fallback: Found recent order {recent_order.order_id} for user {request.user.id}, but not linked to payment {payment.id}"
                )
            all_orders = Order.objects.filter(user=request.user).values('id', 'order_id', 'payment_id', 'created_at')
            all_payments = Payment.objects.filter(user=request.user).values('id', 'payment_method', 'created_at')
            logger.debug(f"All orders for user {request.user.id}: {list(all_orders)}")
            logger.debug(f"All payments for user {request.user.id}: {list(all_payments)}")
            messages.error(request, "No recent order found.")
            return redirect('dashboard:shopping_cart')

        logger.info(f"Found order for payment {payment.id} and user {request.user.id}")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        payment = Payment.objects.filter(user=user).order_by('-created_at').first()
        if not payment:
            logger.error(f"No payment found for user {user.id} in get_context_data")
            context['error'] = "No payment found."
            return context

        main_image_prefetch = Prefetch(
            'items__product__images',
            queryset=ProductImage.objects.filter(is_main=True),
            to_attr='main_image'
        )

        order = Order.objects.filter(
            user=user,
            payment=payment
        ).select_related(
            'payment'
        ).prefetch_related(main_image_prefetch).first()

        if not order:
            logger.error(f"No order found for payment {payment.id} and user {user.id} in get_context_data")
            order = Order.objects.filter(user=user).order_by('-created_at').first()
            if order:
                logger.warning(f"Fallback: Using recent order {order.order_id} for user {user.id}, not linked to payment {payment.id}")
            else:
                context['error'] = "No order found for this payment."
                return context

        # 🧾 Order summary calculations
        subtotal = sum(item.price * item.quantity for item in order.items.all()) or Decimal('0.00')
        shipping = order.shipping_fees or Decimal('00.00')
        vat = Decimal('0.00')

        # ✅ Apply coupon only if user actually applied one
        coupon_discount = Decimal('0.00')
        if 'applied_coupon' in self.request.session:
            coupon_data = self.request.session.get('applied_coupon', {})
            if coupon_data and 'discount_amount' in coupon_data:
                coupon_discount = Decimal(str(coupon_data['discount_amount']))

        # ✅ Calculate total safely
        total = subtotal - coupon_discount + shipping + vat

        # Estimated delivery
        max_delivery_days = max(((item.product.delivery_time or 5) for item in order.items.all()), default=5)
        estimated_delivery = timezone.now().date() + timedelta(days=max_delivery_days)

        # Payment details
        time_window = payment.created_at + timedelta(minutes=10)
        payment_method = payment.payment_method
        payment_details = None

        if payment_method == "stripe":
            payment_details = StripePayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, time_window)
            ).order_by('-created_at').first()
        elif payment_method == "razorpay":
            payment_details = RazorpayPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, time_window)
            ).order_by('-created_at').first()
        elif payment_method == "cod":
            payment_details = CODPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, time_window)
            ).order_by('-created_at').first()
        elif payment_method == "bank_transfer":
            payment_details = BankTransferPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()

        billing = CustomerBillingAddress.objects.filter(
            user=user,
            is_default=True,
            is_deleted=False
        ).first()

        # Update context
        context.update({
            'payment': payment,
            'order': order,
            'order_items': order.items.all(),
            'order_summary': {
                'subtotal': subtotal,
                'shipping': shipping,
                'vat': vat,
                'coupon_discount': coupon_discount, 
                'total': total
            },
            'order_id': order.order_id,
            'order_date': payment.created_at,
            'estimated_delivery': estimated_delivery,
            'payment_method': payment_method,
            'payment_details': payment_details,
            'billing': billing,
            'currency_symbol': 'USD' if payment_method in ['stripe', 'cod'] else 'INR'
        })

        logger.info(f"Loaded order {order.order_id} for user {user.id} with payment {payment.id}, items: {order.items.count()}")
        return context



class MyOrdersView(LoginRequiredMixin, TemplateView):
    template_name = 'userdashboard/view/my_orders.html'
    login_url = 'dashboard:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        main_image_prefetch = Prefetch(
            'items__product__images',
            queryset=ProductImage.objects.filter(is_main=True),
            to_attr='main_image'
        )
        user_reviews_prefetch = Prefetch(
            'items__product__reviews',
            queryset=RatingReview.objects.filter(user=user),
            to_attr='user_reviews'
        )
        returns_prefetch = Prefetch(
            'items__returns',
            queryset=Return.objects.all(),
            to_attr='all_returns'
        )

        orders_qs = (
            Order.objects.filter(user=user)
            .select_related('payment')
            .prefetch_related(
                main_image_prefetch,
                user_reviews_prefetch,
                'items__product',
                returns_prefetch
            )
        )
        status = self.request.GET.get('status')
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        if status:
            orders_qs = orders_qs.filter(status=status.lower())

        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                orders_qs = orders_qs.filter(created_at__gte=start_date)
            except ValueError:
                pass

        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d')
                end_date = end_date.replace(hour=23, minute=59, second=59)
                orders_qs = orders_qs.filter(created_at__lte=end_date)
            except ValueError:
                pass

        orders_qs = orders_qs.order_by('-created_at')
        paginator = Paginator(orders_qs, 2)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        for order in page_obj.object_list:
            subtotal = sum(item.price * item.quantity for item in order.items.all())
            shipping = order.shipping_fees or Decimal('0.00')
            vat = Decimal('0.00')
            coupon_discount = Decimal('0.00')
            coupon_data = self.request.session.get('applied_coupon')

            if coupon_data and 'discount_amount' in coupon_data:
                coupon_discount = Decimal(str(coupon_data['discount_amount']))
            order.final_total = subtotal - coupon_discount + shipping + vat
            for item in order.items.all():
                item.has_pending_returns = any(
                    return_obj.return_status == 'pending'
                    for return_obj in item.all_returns
                )

        context['orders'] = page_obj.object_list
        context['page_obj'] = page_obj
        context['order_status_choices'] = OrderItem.ORDER_STATUS_CHOICES

        return context


class MyReturnsView(LoginRequiredMixin, TemplateView):
    template_name = 'userdashboard/view/my_returns.html'
    login_url = 'dashboard:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        returns_qs = (
            Return.objects.filter(client=user)
            .select_related('order_item__product', 'order_item__order')
            .prefetch_related('order_item__product__images')
            .order_by('-request_date')
        )

        # Apply filters
        status_filter = self.request.GET.get('status')
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        if status_filter and status_filter != 'all':
            returns_qs = returns_qs.filter(return_status=status_filter)

        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                returns_qs = returns_qs.filter(request_date__gte=start_date)
            except ValueError:
                pass

        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d')
                # Include entire end date
                end_date = end_date.replace(hour=23, minute=59, second=59)
                returns_qs = returns_qs.filter(request_date__lte=end_date)
            except ValueError:
                pass

        # Paginate the returns
        paginator = Paginator(returns_qs, 2)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context.update({
            'returns': page_obj.object_list,
            'page_obj': page_obj,
            'current_status': status_filter or 'all',
            'start_date': self.request.GET.get('start_date', ''),
            'end_date': self.request.GET.get('end_date', ''),
        })
     
        return context
class SubmitReviewView(LoginRequiredMixin, View):
    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        rating = request.POST.get('rating')
        review = request.POST.get('review')
        photo = request.FILES.get('photo')
        if RatingReview.objects.filter(user=request.user, product=product).exists():
            messages.error(request, "You have already reviewed this product.")
            user_failed_activity(
                request.user,
                f"Attempted duplicate review for product {product.name}"
            )
            return redirect('dashboard:my_orders')
        if not rating:
            messages.error(request, "Rating is required.")
            user_failed_activity(
                request.user,
                f"Failed to submit review for product {product.name} (rating missing)"
            )
            return redirect('dashboard:my_orders')
        RatingReview.objects.create(
            product=product,
            user=request.user,
            rating=int(rating),
            review=review,
            photo=photo
        )
        user_created_activity(
            request.user,
            f"Submitted review for product {product.name}"
        )
        messages.success(request, "Your review has been submitted!")
        return redirect('dashboard:my_orders')

class ReorderView(LoginRequiredMixin, View):
    login_url = 'dashboard:login'

    def post(self, request, order_id, *args, **kwargs):
        order = get_object_or_404(Order, id=order_id, user=request.user)

        # Get all OrderItems for the order
        order_items = OrderItem.objects.filter(order=order)
        if not order_items.exists():
            logger.error(f"No items found for order {order_id} and user {request.user.id}")
            messages.error(request, "No items found in this order.")
            return redirect('dashboard:my_orders')

        # Add each item to the cart
        for item in order_items:
            cart_item, created = CartProduct.objects.get_or_create(
                user=request.user,
                product=item.product,
                defaults={'quantity': item.quantity}
            )
            if not created:
                cart_item.quantity += item.quantity
                cart_item.save()
            logger.info(f"Added {item.quantity} x {item.product.name} to cart for user {request.user.id}")

        messages.success(request, f"Added items from order {order.order_id} to your cart.")
        return redirect('dashboard:shopping_cart')  # Or redirect to cart page


class OrderReceiptView(LoginRequiredMixin, TemplateView):
    template_name = 'userdashboard/view/order_receipt.html'
    login_url = 'dashboard:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        order_id = self.kwargs.get('pk')

        # Prefetch main product images for OrderItems
        main_image_prefetch = Prefetch(
            'items__product__images',
            queryset=ProductImage.objects.filter(is_main=True),
            to_attr='main_image'
        )

        # Fetch the specific order for the authenticated user
        try:
            order = Order.objects.filter(id=order_id, user=user).select_related('payment').prefetch_related(main_image_prefetch).get()
        except Order.DoesNotExist:
            logger.error(f"Order {order_id} not found for user {user.id}")
            context['error'] = "Order not found or you don't have permission to view it."
            return context

        # Fetch related payment details
        payment = order.payment
        payment_method = payment.payment_method if payment else order.items.first().payment_type.lower()
        

        # Determine payment details based on payment method
        payment_details = None
        if payment_method == "stripe":
            payment_details = StripePayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()
            if payment_details and payment_details.stripe_customer_id:
                billing_with_card = CustomerBillingAddress.objects.filter(user=user, is_old=True, is_deleted=False).first()
                if billing_with_card and billing_with_card.old_card:
                    try:
                        card_info = json.loads(billing_with_card.old_card.replace("'", "\""))
                        payment_details.card_last4 = card_info.get('last4', 'N/A')
                    except (json.JSONDecodeError, AttributeError):
                        payment_details.card_last4 = 'N/A'
                else:
                    payment_details.card_last4 = 'N/A'
        elif payment_method == "razorpay":
            payment_details = RazorpayPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()
        elif payment_method == "cod":
            payment_details = CODPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()
        elif payment_method == "bank_transfer":
            payment_details = BankTransferPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()

        # Prepare order item details
        items = []
        for order_item in order.items.all():
            product_image = order_item.product.main_image[0] if order_item.product.main_image else None
            items.append({
                'product': order_item.product,
                'quantity': order_item.quantity,
                'sku': order_item.product.supplier_sku,
                'total_price': order_item.price * order_item.quantity,
                'image_url': product_image.image.url if product_image else None,
            })

        # Fetch billing address
        billing = CustomerBillingAddress.objects.filter(user=user, is_default=True, is_deleted=False).first()

        # Calculate order totals for summary
        subtotal = sum(item.price * item.quantity for item in order.items.all()) or Decimal('0.00')
        shipping = order.shipping_fees or Decimal('0.00')
        vat = Decimal('0.00')  # Adjust if VAT logic is implemented
        total = subtotal + shipping + vat

        context.update({
            'order': order,
            'items': items,
            'order_summary': {
                'subtotal': subtotal,
                'shipping': shipping,
                'vat': vat,
                'total': total,
            },
            'order_total': total,
            'order_date': order.created_at,
            'billing': billing,
            'estimated_delivery': order.created_at.date() + timedelta(days=max((item.product.delivery_time or 5) for item in order.items.all())),
            'payment_method': payment_method,
            'payment_details': payment_details,
            'currency_symbol': 'USD' if payment_method in ['stripe', 'cod'] else 'INR'
        })

        logger.info(f"Order receipt loaded for order {order.order_id} and user {user.id}")
        return context
class DownloadReceiptView(LoginRequiredMixin, View):
    login_url = 'dashboard:login'

    def get(self, request, pk):
        user = request.user
        main_image_prefetch = Prefetch(
            'items__product__images',
            queryset=ProductImage.objects.filter(is_main=True),
            to_attr='main_image'
        )
        try:
            order = (
                Order.objects
                .filter(id=pk, user=user)
                .select_related('payment')
                .prefetch_related(main_image_prefetch)
                .get()
            )
        except Order.DoesNotExist:
            logger.error(f"Order {pk} not found for user {user.id}")
            return HttpResponse("Order not found or unauthorized", status=404)
       
        payment = order.payment
        payment_method = payment.payment_method if payment else order.items.first().payment_type.lower()

        payment_details = None
        if payment_method == "stripe":
            payment_details = StripePayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()

            if payment_details and payment_details.stripe_customer_id:
                billing_with_card = CustomerBillingAddress.objects.filter(
                    user=user,
                    is_old=True,
                    is_deleted=False
                ).first()

                if billing_with_card and billing_with_card.old_card:
                    try:
                        card_info = json.loads(billing_with_card.old_card.replace("'", "\""))
                        payment_details.card_last4 = card_info.get('last4', 'N/A')
                    except (json.JSONDecodeError, AttributeError):
                        payment_details.card_last4 = 'N/A'
                else:
                    payment_details.card_last4 = 'N/A'

        elif payment_method == "razorpay":
            payment_details = RazorpayPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()

        elif payment_method == "cod":
            payment_details = CODPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()

        elif payment_method == "bank_transfer":
            payment_details = BankTransferPayment.objects.filter(
                user=user,
                created_at__range=(payment.created_at, payment.created_at + timedelta(minutes=5))
            ).order_by('-created_at').first()
        items = []
        for order_item in order.items.all():
            product_image = (
                order_item.product.main_image[0]
                if order_item.product.main_image
                else None
            )

            items.append({
                'product': order_item.product,
                'quantity': order_item.quantity,
                'sku': order_item.product.supplier_sku,
                'total_price': order_item.price * order_item.quantity,
                'image_url': request.build_absolute_uri(product_image.image.url) if product_image else None,
            })
        billing = CustomerBillingAddress.objects.filter(
            user=user,
            is_default=True,
            is_deleted=False
        ).first()
        subtotal = sum(item.price * item.quantity for item in order.items.all()) or Decimal('0.00')
        shipping = order.shipping_fees or Decimal('0.00')
        vat = Decimal('0.00')
        total = subtotal + shipping + vat

        context = {
            'order': order,
            'items': items,
            'order_summary': {
                'subtotal': subtotal,
                'shipping': shipping,
                'vat': vat,
                'total': total,
            },
            'order_total': total,
            'order_date': order.created_at,
            'billing': billing,
            'estimated_delivery': order.created_at.date() + timedelta(
                days=max((item.product.delivery_time or 5) for item in order.items.all())
            ),
            'payment_method': payment_method,
            'payment_details': payment_details,
            'currency_symbol': 'USD' if payment_method in ['stripe', 'cod'] else 'INR'
        }
        html_string = render_to_string(
            'userdashboard/view/order_receipt_pdf.html',
            context
        )
        result = BytesIO()
        pdf = pisa.CreatePDF(src=html_string, dest=result)
        if pdf.err:
            logger.error(f"Failed to generate PDF for order {order.order_id}: {pdf.err}")
           

            return HttpResponse('Error generating PDF', status=500)
        user_update_activity(
            user,
            f"Downloaded receipt for order #{order.order_id}"
        )

        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="order_receipt_{order.order_id}.pdf"'
        )

        logger.info(f"Generated PDF receipt for order {order.order_id} and user {user.id}")
        return response


class UserProfile(LoginRequiredMixin, TemplateView):
    template_name = 'pages/user_profile.html'
    login_url = 'dashboard:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['user'] = user

        # Get user profile and type
        profile = None
        profile_type = None

        try:
            profile = RetailProfile.objects.get(user=user)
            profile_type = 'retailer'
        except RetailProfile.DoesNotExist:
            try:
                profile = WholesaleBuyerProfile.objects.get(user=user)
                profile_type = 'wholesaler'
            except WholesaleBuyerProfile.DoesNotExist:
                try:
                    profile = SupplierProfile.objects.get(user=user)
                    profile_type = 'supplier'
                except SupplierProfile.DoesNotExist:
                    try:
                        profile = AdminUserProfile.objects.get(user=user)
                        profile_type = 'admin'
                    except AdminUserProfile.DoesNotExist:
                        pass

        context['profile'] = profile
        context['profile_type'] = profile_type


        if profile and hasattr(profile, "profile_picture") and profile.profile_picture:
            avatar = profile.profile_picture
        elif hasattr(user, "profile_picture") and user.profile_picture:  # superuser / base User
            avatar = user.profile_picture
        else:
            avatar = None

        context['avatar'] = avatar

        # Phone
        phone = getattr(profile, "phone", None) if profile else None
        context['phone'] = phone or 'Not set'

        # Default billing address
        try:
            default_address = CustomerBillingAddress.objects.get(user=user, is_default=True, is_deleted=False)
        except CustomerBillingAddress.DoesNotExist:
            default_address = None
        context['default_address'] = default_address

        addresses = CustomerBillingAddress.objects.filter(user=user, is_deleted=False)
        context['addresses'] = addresses
        print("Addresses -------", addresses)

       # Order summary
        orders = Order.objects.filter(user=user)
        context.update({
            'total_orders': orders.count(),
            'pending_orders': orders.filter(status='pending').count(),
            'delivered_orders': orders.filter(status='delivered').count(),
            'cancelled_orders': orders.filter(status='cancelled').count(),
            'return_orders': Return.objects.filter(client=user).count(),  
        })


        # Wishlist count
        context['wishlist_count'] = WishlistProduct.objects.filter(user=user).count()

        # Latest payment info
        stripe_payment = StripePayment.objects.filter(user=user, paid=True).order_by('-created_at').first()
        razorpay_payment = RazorpayPayment.objects.filter(user=user, paid=True).order_by('-created_at').first()
        cod_payment = CODPayment.objects.filter(user=user, paid=True).order_by('-created_at').first()

        latest_payment = None

        if stripe_payment:
            latest_payment = {
                'type': 'Stripe',
                'details': f"{stripe_payment.name} ending in {stripe_payment.stripe_customer_id[-4:]}",
                'created_at': stripe_payment.created_at
            }

        if razorpay_payment and (not latest_payment or razorpay_payment.created_at > latest_payment['created_at']):
            latest_payment = {
                'type': 'Razorpay',
                'details': f"{razorpay_payment.name} ending in {razorpay_payment.razorpay_payment_id[-4:]}",
                'created_at': razorpay_payment.created_at
            }

        if cod_payment and (not latest_payment or cod_payment.created_at > latest_payment['created_at']):
            latest_payment = {
                'type': 'COD',
                'details': f"COD - {cod_payment.name}",
                'created_at': cod_payment.created_at
            }

        context['payment_method'] = latest_payment

        return context


class UploadAvatarView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            profile, profile_type = get_user_profile(request.user)
            if not profile:
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse({"status": "error", "message": "Profile not found."}, status=404)
                messages.error(request, "Profile not found.")
                return redirect('dashboard:user_profile')

            if 'avatar' in request.FILES:
                profile.profile_picture = request.FILES['avatar']
                profile.save()
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse({"status": "success", "message": "Avatar updated successfully."})
                user_update_activity(
                    request.user,
                    "Updated profile avatar"
                )

                messages.success(request, "Avatar updated successfully.")

            elif 'avatar_remove' in request.POST:
                if profile.profile_picture:
                    profile.profile_picture.delete(save=True)
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse({"status": "success", "message": "Avatar removed successfully."})
                user_update_activity(
                    request.user,
                    "Removed profile avatar"
                )

                messages.success(request, "Avatar removed successfully.")

            return redirect('dashboard:user_profile')

        except Exception as e:
            print("Error in image upload -----", e)
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"status": "error", "message": "Something went wrong.", "errors": str(e)}, status=500)
            messages.error(request, "Something went wrong.")
            return redirect('dashboard:user_profile')

class EditProfileView(LoginRequiredMixin, View):
    def post(self, request):
        user = request.user

        # Detect profile
        if hasattr(user, 'retailprofile'):
            profile = user.retailprofile
            profile_type = 'retailer'
        elif hasattr(user, 'wholesalebuyerprofile'):
            profile = user.wholesalebuyerprofile
            profile_type = 'wholesaler'
        elif hasattr(user, 'supplierprofile'):
            profile = user.supplierprofile
            profile_type = 'supplier'
        else:
            return JsonResponse({'status': 'error', 'message': 'Profile not found'}, status=400)

        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        company_name = request.POST.get('company_name', '').strip()
        speciality = request.POST.get('speciality', '').strip()

        if not first_name or not last_name:
            return JsonResponse({'status': 'error', 'message': 'First and last name are required'}, status=400)

        user.first_name = first_name
        user.last_name = last_name
        user.save()

        if profile_type in ['wholesaler', 'supplier']:
            profile.company_name = company_name
        elif profile_type == 'retailer':
            profile.speciality = speciality

        profile.save()
        user_update_activity(
            user,
            "Updated profile details"
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Profile updated successfully.'
        })
class ChangePasswordView(LoginRequiredMixin, View):
    def post(self, request):
        user = request.user

        current = request.POST.get('current_password')
        new = request.POST.get('new_password')
        confirm = request.POST.get('confirm_password')

        if not user.check_password(current):
            return JsonResponse({'status': 'error', 'message': 'Current password is incorrect'}, status=400)

        if new != confirm:
            return JsonResponse({'status': 'error', 'message': 'Passwords do not match'}, status=400)

        if len(new) < 6:
            return JsonResponse({'status': 'error', 'message': 'Password must be at least 6 characters'}, status=400)

        user.set_password(new)
        user.save()
        logout(request)
        user_update_activity(
            user,
            "Changed account password"
        )
        return JsonResponse({
            'status': 'success',
            'message': 'Password changed successfully. Please login again.'
        })




class EditEmailView(LoginRequiredMixin, View):
    def post(self, request):
        form = EmailForm(request.POST, instance=self.request.user)
        if form.is_valid():
            form.save()
            user_failed_activity(
            request.user,
            "Failed to update email"
        )
            return JsonResponse({'status': 'success', 'message': 'Email updated successfully.'})
        return JsonResponse({'status': 'error', 'message': 'Failed to update email. Please check the form.'})


class EditPhoneView(LoginRequiredMixin, View):
    def post(self, request):
        phone_number = request.POST.get("phone")
        print('----Phone ----', phone_number)

        if not phone_number:
            return JsonResponse({
                'status': 'error',
                'message': 'Phone number is required.'
            }, status=400)

        try:
            with transaction.atomic():

                if hasattr(request.user, "retailprofile"):
                    request.user.retailprofile.phone = phone_number
                    request.user.retailprofile.save()
                    print('----Phone Updated in retailprofile ----', phone_number)
                    user_update_activity(
                    request.user,
                    f"Updated phone number to {phone_number}"
                )
                    return JsonResponse({
                        'status': 'success',
                        'message': 'Phone number updated successfully'
                    })

                elif hasattr(request.user, "wholesalebuyerprofile"):
                    request.user.wholesalebuyerprofile.phone = phone_number
                    request.user.wholesalebuyerprofile.save()
                    print('----Phone Updated in wholesalebuyerprofile ----', phone_number)
                    user_update_activity(
                    request.user,
                    f"Updated phone number to {phone_number}"
                )
                    return JsonResponse({
                        'status': 'success',
                        'message': 'Phone number updated successfully'
                    })

                elif hasattr(request.user, "supplierprofile"):
                    request.user.supplierprofile.phone = phone_number
                    request.user.supplierprofile.save()
                    print('----Phone Updated in supplierprofile ----', phone_number)
                    user_update_activity(
                    request.user,
                    f"Updated phone number to {phone_number}"
                )
                    return JsonResponse({
                        'status': 'success',
                        'message': 'Phone number updated successfully'
                    })

                elif request.user.is_superuser:
                    profile, created = AdminUserProfile.objects.get_or_create(user=request.user)
                    profile.phone = phone_number
                    profile.save()
                    print('----Phone Updated in admin side ----', phone_number)
                    user_update_activity(
                    request.user,
                    f"Updated phone number to {phone_number}"
                )
                    return JsonResponse({
                        'status': 'success',
                        'message': 'Phone number updated successfully'
                    })

                else:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'No profile found for this user.'
                    }, status=404)

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Internal error: {str(e)}'
            }, status=500)


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
            return redirect('dashboard:login')

        phone = signup_data['phone']
        result = verify_mobile_otp(VERIFY_URL, TEXTDRIP_OTP_TOKEN, phone, otp)

        print("OTP VERIFICATION RESULT:", result)

        if result.get("success") or result.get("status") is True:
            # Double-check user doesn't exist
            if User.objects.filter(username=signup_data['email']).exists():
                messages.error(request, "An account with this email already exists.")
                request.session.pop('signup_data', None)
                return redirect('dashboard:login')

            try:
                User.objects.create_user(
                    username=signup_data['email'],
                    email=signup_data['email'],
                    password=signup_data['password']
                )
                request.session.pop('signup_data', None)
                messages.success(request, "Account created successfully.")
                return redirect('dashboard:login')
            except Exception as e:
                messages.error(request, f"Error creating account: {str(e)}")
                return redirect('dashboard:user_signup')
        else:
            messages.error(request, result.get("message", "OTP verification failed."))
            return redirect('dashboard:verify_otp')


class ResendOTPView(View):
    def post(self, request):
        if request.headers.get('x-requested-with') != 'XMLHttpRequest':
            return JsonResponse({'message': 'Invalid request.'}, status=400)

        token = request.POST.get('token')
        if not token:
            return JsonResponse({'success': False, 'message': 'Token is missing.'}, status=400)

        try:
            pending = PendingSignup.objects.get(token=token)
        except PendingSignup.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Invalid or expired token.'}, status=400)

        try:
            data = json.loads(pending.data)
        except Exception:
            return JsonResponse({'success': False, 'message': 'Corrupted signup data.'}, status=500)

        phone = data.get('phone')
        otp_response = send_phone_otp(phone, TEXTDRIP_OTP_TOKEN)

        if "error" in otp_response:
            return JsonResponse({'success': False, 'message': otp_response["error"]}, status=400)

        return JsonResponse({'success': True, 'message': 'OTP resent successfully.'})



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
            return redirect('dashboard:login')
class LogoutView(View):
    def get(self, request):
        user = request.user 

        if user.is_authenticated:
            user_logout_activity(user)

        logout(request)
        messages.success(request, "You have been logged out successfully.")
        return redirect('dashboard:home')



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


# ------------------------------------------------------------------------------------------------------------------------


class ManageRequestsView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = RoleRequest
    template_name = 'userdashboard/seller/manage_requests.html'
    context_object_name = 'requests'

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to manage requests.")
        return redirect('dashboard:home')


class ApproveRoleRequestView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = RoleRequest
    fields = []
    template_name = 'userdashboard/seller/approve_role_request.html'
    success_url = reverse_lazy('dashboard:manage_requests')

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to approve requests.")
        return redirect('dashboard:home')

    def form_valid(self, form):
        role_request = self.object
        user = role_request.user
        current_status = role_request.status

        if role_request.status == 'pending':
            role_request.status = 'approved'
            role_request.save()

            # Ensure profile exists (should already be created from request)
            try:
                if role_request.requested_role == 'supplier':
                    supplier_profile, _ = SupplierProfile.objects.get_or_create(user=user)
                    logger.info(f"Verified SupplierProfile for {user.username}")
                elif role_request.requested_role == 'wholesaler':
                    wholesale_profile, _ = WholesaleBuyerProfile.objects.get_or_create(user=user)
                    logger.info(f"Verified WholesaleBuyerProfile for {user.username}")
                elif role_request.requested_role == 'retailer':
                    retail_profile, _ = RetailProfile.objects.get_or_create(user=user)
                    logger.info(f"Verified RetailProfile for {user.username}")
            except Exception as e:
                logger.error(f"Failed to verify profile for {user.username}: {str(e)}")
                messages.error(self.request, f"Failed to verify profile: {str(e)}")
                return self.form_invalid(form)

            # Send acceptance email with current date and time
            subject = 'Role Request Approved'
            html_message = render_to_string('userdashboard/email/role_approved.html', {
                'user': user.username,
                'role': role_request.requested_role,
                'date': '04:31 PM IST on Thursday, July 10, 2025'
            })
            plain_message = strip_tags(html_message)
            try:
                send_mail(
                    subject,
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                logger.info(f"Email sent to {user.email} for role approval")
            except Exception as e:
                logger.error(f"Email sending failed for {user.email}: {str(e)}")
                messages.warning(self.request, "Role approved, but email failed to send.")

            messages.success(self.request, f"Role '{role_request.requested_role}' approved for {user.username}.")
        elif current_status == 'approved' and 'reject' in self.request.POST:
            role_request.status = 'rejected'
            role_request.save()

            # Send rejection email with current date and time
            subject = 'Role Request Rejected'
            html_message = render_to_string('userdashboard/email/role_rejected.html', {
                'user': user.username,
                'role': role_request.requested_role,
                'date': '04:31 PM IST on Thursday, July 10, 2025'
            })
            plain_message = strip_tags(html_message)
            try:
                send_mail(
                    subject,
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                logger.info(f"Email sent to {user.email} for role rejection")
            except Exception as e:
                logger.error(f"Email sending failed for {user.email}: {str(e)}")
                messages.warning(self.request, "Role rejected, but email failed to send.")

            messages.warning(self.request, f"Role request for {user.username} has been rejected.")

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_reject'] = self.object.status == 'approved'
        return context

class RFQSubmissionView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        product_id = request.POST.get('product_id')

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return redirect('dashboard:home')
        rfq = RFQRequest.objects.create(
            requested_by=request.user,
            product=product,
            quantity=request.POST.get('quantity'),
            message=request.POST.get('message', ''),
            company_name=request.POST.get('company_name', ''),
            expected_delivery_date=request.POST.get('expected_delivery_date') or None,
            status='received',
        )
        user_created_activity(
            request.user,
            f"Submitted RFQ for {product.name} (Qty: {rfq.quantity})"
        )
        send_mail(
            subject='Quotation Request Received',
            message='Thank you for your quotation request. Our team will get back to you shortly.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
        )
        rfq.email_sent = True
        rfq.save()
        user_update_activity(
            request.user,
            f"RFQ confirmation email sent for {product.name}"
        )
        return redirect('dashboard:home')
    def get(self, request, *args, **kwargs):
        return redirect('dashboard:home')



class UserQuotationView(LoginRequiredMixin, TemplateView):
    template_name = 'userdashboard/view/view_user_quotations.html'
    login_url = 'dashboard:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['sent_quotations'] = RFQRequest.objects.filter(quoted_by=user)
        context['received_quotations'] = RFQRequest.objects.filter(requested_by=user)
        user_update_activity(
            user,
            "Viewed RFQ quotations"
        )
        return context
class AddRFQCommentView(LoginRequiredMixin, View):
    def post(self, request, rfq_id):
        rfq = get_object_or_404(RFQRequest, id=rfq_id)
        comment_text = request.POST.get('comment', '').strip()
        total_price = request.POST.get('total_price')
        total_commission = request.POST.get('total_commission')

        if not comment_text:
            messages.error(request, "Comment cannot be empty.")
            return redirect('dashboard:view_user_quotations')

        RFQComment.objects.create(
            rfq=rfq,
            comment=comment_text,
            total_price=total_price or None,
            total_commission=total_commission or None,
            commented_by=request.user,
            admin_reply=None
        )
        user_created_activity(
            request.user,
            f"Added comment on RFQ #{rfq.id} for {rfq.product.name}"
        )
        messages.success(request, "Comment added successfully.")
        return redirect('dashboard:view_user_quotations')


class RFQCommentsAPIView(LoginRequiredMixin, View):
    def get(self, request, rfq_id):
        rfq = get_object_or_404(RFQRequest, id=rfq_id)
        comments = rfq.comments.all().values(
            'id', 'comment', 'total_price', 'total_commission',
            'commented_by__username', 'commented_by__first_name', 'commented_by__last_name',
            'created_at', 'admin_reply', 'replied_at'
        )
        data = []
        for c in comments:
            fullname = f"{c['commented_by__first_name']} {c['commented_by__last_name']}".strip()
            if not fullname:
                fullname = c['commented_by__username']
            data.append({
                'comment': c['comment'],
                'total_price': c['total_price'],
                'total_commission': c['total_commission'],
                'commented_by': c['commented_by__username'],
                'commented_by_fullname': fullname,
                'created_at': c['created_at'],
                'admin_reply': c['admin_reply'],
                'replied_at': c['replied_at'],
            })
        return JsonResponse(data, safe=False)
class RFQActionBaseView(LoginRequiredMixin, View):
    action = None  # 'accepted' or 'rejected'
    success_message = ""

    def post(self, request, pk, *args, **kwargs):
        rfq = get_object_or_404(RFQRequest, pk=pk, requested_by=request.user)

        if rfq.status != 'quoted':
            messages.warning(request, "This quotation is not available for action.")
            return redirect('dashboard:home')  # Change to your actual dashboard view name

        rfq.status = self.action
        rfq.updated_at = timezone.now()
        rfq.save()

        messages.success(request, self.success_message)
        return redirect('dashboard:home')


class RFQAcceptView(RFQActionBaseView):
    action = 'accepted'
    success_message = "You have accepted the quotation."


class RFQRejectView(RFQActionBaseView):
    action = 'rejected'
    success_message = "You have rejected the quotation."


class SubscriptionPlanView(LoginRequiredMixin, TemplateView):
    template_name = 'userdashboard/view/subscription_plans.html'
    login_url = 'dashboard:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get client_type and buyer_type from request or user profile
        client_type = self.request.GET.get('client_type', 'buyer')  # Default to 'buyer'
        buyer_type = self.request.GET.get('buyer_type', 'retailer') if client_type == 'buyer' else None

        # Validate client_type
        valid_client_types = [choice[0] for choice in SubscriptionPlan.CLIENT_TYPE_CHOICES]
        if client_type not in valid_client_types:
            client_type = 'buyer'

        # Validate buyer_type if client_type is 'buyer'
        valid_buyer_types = [choice[0] for choice in SubscriptionPlan.BUYER_TYPE_CHOICES]
        if client_type == 'buyer' and buyer_type not in valid_buyer_types:
            buyer_type = 'retailer'

        # Build filter for plans
        filters = {'client_type': client_type, 'is_active': True}
        if client_type == 'buyer':
            filters['buyer_type'] = buyer_type

        # Fetch active subscription plans
        plans = SubscriptionPlan.objects.filter(**filters).select_related('stripe_metadata').prefetch_related(
            'features')

        # Get user's current subscription
        user_subscription = UserSubscription.objects.filter(
            user=self.request.user,
            is_active=True
        ).select_related('plan').first()

        # Fetch all features for the filtered plans
        features = Feature.objects.filter(plans__in=plans).distinct()

        if not plans:
            context[
                'no_plans_message'] = f"No subscription plans available for {client_type}{' - ' + buyer_type if buyer_type else ''} at this time."

        context.update({
            'plans': plans,
            'features': features,
            'user_subscription': user_subscription,
            'client_type': client_type,
            'buyer_type': buyer_type,
            'client_type_choices': SubscriptionPlan.CLIENT_TYPE_CHOICES,
            'buyer_type_choices': SubscriptionPlan.BUYER_TYPE_CHOICES,
        })

        return context

    def post(self, request, *args, **kwargs):
        plan_id = request.POST.get('plan_id')
        platform = request.POST.get('platform', 'web')
        user = request.user

        try:
            plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
            stripe_price_id = plan.stripe_metadata.price_id

            profile = user.profile
            customer_id = profile.stripe_customer_id

            # Check existing Stripe subscriptions
            subscriptions = stripe.Subscription.list(customer=customer_id, status='active')

            if subscriptions.data:
                subscription_id = subscriptions.data[0].id
                stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=False,
                    proration_behavior='create_prorations',
                    items=[{
                        'id': subscriptions.data[0]['items']['data'][0].id,
                        'price': stripe_price_id,
                    }],
                    expand=["latest_invoice.payment_intent"],
                )
                stripe_subscription = stripe.Subscription.retrieve(subscription_id)
            else:
                stripe_subscription = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{'price': stripe_price_id}],
                    expand=["latest_invoice.payment_intent"],
                )

            # Save in profile
            profile.stripe_subscription_id = stripe_subscription.id
            profile.active_subscription_price_id = stripe_price_id
            profile.subscription_status = stripe_subscription.status
            profile.save()

            # Deactivate current user subscription (local)
            UserSubscription.objects.filter(user=user, is_active=True).update(is_active=False)

            # Save new local user subscription
            UserSubscription.objects.create(
                user=user,
                plan=plan,
                platform=platform,
                is_active=True
            )

            return JsonResponse({
                'success': True,
                'message': f'Subscribed to {plan.name}'
            })

        except stripe.error.StripeError as e:
            return JsonResponse({'success': False, 'message': f'Stripe error: {str(e)}'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)


class UpdateSubscriptionView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        plan_id = request.POST.get('plan_id')
        platform = request.POST.get('platform', 'web')
        client_type = request.POST.get('client_type', 'buyer')
        buyer_type = request.POST.get('buyer_type') if client_type == 'buyer' else None

        try:
            # Validate plan
            filters = {'id': plan_id, 'client_type': client_type, 'is_active': True}
            if client_type == 'buyer':
                filters['buyer_type'] = buyer_type
            plan = SubscriptionPlan.objects.get(**filters)

            # Deactivate current subscription
            user_subscription = UserSubscription.objects.filter(
                user=request.user,
                is_active=True
            ).first()
            if user_subscription:
                user_subscription.is_active = False
                user_subscription.save()

            # Create new subscription
            new_subscription = UserSubscription(
                user=request.user,
                plan=plan,
                platform=platform,
            )
            new_subscription.clean()
            new_subscription.save()

            return JsonResponse({
                'status': 'success',
                'message': 'Subscription updated successfully.'
            })
        except SubscriptionPlan.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid plan.'
            }, status=400)
        except ValidationError as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': 'An error occurred while updating the subscription.'
            }, status=500)


# views.py
class CheckStripeSubscriptionView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        user = request.user
        price_id = request.GET.get('price_id')
        profile = user.profile
        customer_id = profile.stripe_customer_id

        try:
            existing_subscriptions = stripe.Subscription.list(customer=customer_id, status='active')
            disallowed_upgrade = False

            for sub in existing_subscriptions.auto_paging_iter():
                items = sub.get('items', {}).get('data', [])
                if not items:
                    continue  # Skip if no items

                current_item = items[0]
                current_price_obj = current_item.get('price')
                if not current_price_obj:
                    continue  # Skip if price info is missing

                current_price_id = current_price_obj.get('id')
                if not current_price_id:
                    continue

                # Get Stripe price amounts
                current_price = stripe.Price.retrieve(current_price_id)
                new_price = stripe.Price.retrieve(price_id)

                if price_id == current_price_id or (new_price.unit_amount or 0) <= (current_price.unit_amount or 0):
                    disallowed_upgrade = True

            if disallowed_upgrade:
                return JsonResponse({
                    "status": "blocked",
                    "message": "Cannot downgrade or select same plan."
                })

            return JsonResponse({"status": "ok"})

        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e)
            }, status=500)
class PostQuestionView(LoginRequiredMixin, View):
    def post(self, request):
        question_text = request.POST.get('question', '').strip()
        product_id = request.POST.get('product_id')
        if not question_text:
            user_failed_activity(
                request.user,
                "Attempted to post an empty product question"
            )
            messages.error(request, "Please type your question.")
            if product_id:
                return redirect('dashboard:product_detail', pk=product_id)
            return redirect('dashboard:home')
        product = get_object_or_404(Product, pk=product_id)
        Question.objects.create(
            user=request.user,
            product=product,
            text=question_text
        )
        user_created_activity(
            request.user,
            f"Posted a question on product {product.name}"
        )

        messages.success(request, "Your question has been posted.")
        return redirect('dashboard:product_detail', pk=product.id)


class CancelReturnView(LoginRequiredMixin, View):
    @method_decorator(csrf_protect)
    def post(self, request, return_id):
        return_obj = get_object_or_404(
            Return,
            id=return_id,
            client=request.user,
            return_status='pending'  # Only pending returns can be cancelled
        )

        try:
            # Update return status to cancelled
            return_obj.return_status = 'cancelled'
            return_obj.updated_at = timezone.now()
            return_obj.save()

            messages.success(
                request,
                f"Return request {return_obj.return_serial} has been cancelled successfully."
            )

            # Notify admin about cancellation
            self._notify_admin_return_cancelled(return_obj)

        except Exception as e:
            messages.error(
                request,
                "An error occurred while cancelling your return request. Please try again."
            )

        return redirect('dashboard:my_orders')

    def _notify_admin_return_cancelled(self, return_obj):
        """Send notification to admin about cancelled return"""
        try:
            from django.contrib.auth.models import User
            admin_users = User.objects.filter(is_staff=True)

            for admin in admin_users:
                Notification.objects.create(
                    recipient=admin,
                    title="Return Request Cancelled",
                    message=f"Return request {return_obj.return_serial} has been cancelled by {return_obj.client.get_full_name() or return_obj.client.username}"
                )
        except Exception:
            pass


class RequestReturnView(LoginRequiredMixin, View):
    def post(self, request, item_id):
        order_item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)

        # Comprehensive validation
        validation_error = self._validate_return_eligibility(order_item)
        if validation_error:
            messages.error(request, validation_error)
            return redirect('dashboard:my_orders')

        return_option = request.POST.get('return_option')
        price = request.POST.get('price')
        reason = request.POST.get('reason', '').strip()

        # Validate form data
        if not return_option:
            messages.error(request, "Please select a return option.")
            return redirect('dashboard:my_orders')

        if return_option not in ['return', 'replace']:
            messages.error(request, "Invalid return option selected.")
            return redirect('dashboard:my_orders')

        if not price:
            messages.error(request, "Price information is missing.")
            return redirect('dashboard:my_orders')

        # Check if user already has a pending return for this item
        existing_return = Return.objects.filter(
            order_item=order_item,
            return_status='pending'
        ).first()

        if existing_return:
            messages.warning(
                request,
                f"You already have a pending return request for this item (ID: {existing_return.return_serial})"
            )
            return redirect('dashboard:my_orders')

        # Generate unique return_serial
        return_serial = self._generate_return_serial()

        try:
            return_obj = Return.objects.create(
                return_serial=return_serial,
                order_item=order_item,
                client=request.user,
                return_option=return_option,
                price=price,
                return_status='pending',
                reason=reason
            )

            # ===== New: Update the order_type to 'return' =====
            order_item.order.order_type = 'return'
            order_item.order.save(update_fields=['order_type'])
            # ================================================

            option_text = "refund" if return_option == "return" else "replacement"
            user_created_activity(
                request.user,
                f"Return request {return_serial} submitted for {order_item.product.name} ({option_text})"
            )
            messages.success(
                request,
                f"Return request for {option_text} submitted successfully! "
                f"Return ID: {return_serial}. You will be notified once processed."
            )
            self._notify_admin_new_return(return_obj)
        except Exception as e:
            messages.error(request, "An error occurred while processing your return request. Please try again.")

        return redirect('dashboard:my_orders')

    def _validate_return_eligibility(self, order_item):
        """Validate if the item is eligible for return"""

        # Check if order is delivered
        if order_item.order.status != 'delivered':
            return f"This order hasn't been delivered yet. Current status: {order_item.order.get_status_display()}"

        # Check if product is returnable
        if not order_item.product.is_returnable:
            return "This product is not eligible for returns according to our policy."

        # Check return period
        if not order_item.can_return:
            if order_item.return_deadline:
                return f"Return period has expired. The deadline was: {order_item.return_deadline.strftime('%d %b, %Y')}"
            else:
                return "Return period information is not available for this item."

        return None  # No error

    def _generate_return_serial(self):
        """Generate unique return serial number"""
        base_serial = 'R'
        year = timezone.now().strftime('%y')
        month = timezone.now().strftime('%m')
        suffix = 'R' + year

        # Try to generate unique serial (max 10 attempts)
        for _ in range(10):
            unique_code = ''.join(random.choices('0123456789', k=3))
            return_serial = f"{base_serial}{month}{unique_code}-{suffix}"

            if not Return.objects.filter(return_serial=return_serial).exists():
                return return_serial

        # Fallback with timestamp if all random attempts fail
        timestamp = timezone.now().strftime('%H%M%S')
        return f"{base_serial}{month}{timestamp}-{suffix}"

    def _notify_admin_new_return(self, return_obj):
        """Send notification to admin about new return request"""
        try:
            # Create admin notification
            from django.contrib.auth.models import User
            admin_users = User.objects.filter(is_staff=True)

            for admin in admin_users:
                Notification.objects.create(
                    recipient=admin,
                    title="New Return Request",
                    message=f"Return request {return_obj.return_serial} for {return_obj.order_item.product.name} by {return_obj.client.get_full_name() or return_obj.client.username}"
                )
        except Exception:
            pass



class MarkNotificationReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, recipient=request.user, is_deleted=False)
            notif.is_read = True
            notif.save()
            return JsonResponse({
                "success": True,
                "title": notif.title,
                "message": notif.message,
                "created_at": localtime(notif.created_at).strftime('%d %b %Y, %I:%M %p')
            })
        except Notification.DoesNotExist:
            return JsonResponse({'error': 'Notification not found or not authorized'}, status=404)


class MarkNotificationUnreadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, recipient=request.user, is_deleted=False)
            notif.is_read = False
            notif.save()
            return JsonResponse({
                "success": True,
                "title": notif.title,
                "message": notif.message,
                "created_at": localtime(notif.created_at).strftime('%d %b %Y, %I:%M %p')
            })
        except Notification.DoesNotExist:
            return JsonResponse({'error': 'Notification not found or not authorized'}, status=404)


class ClearAllNotificationsView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        if request.user.is_superuser:
            Notification.objects.all().update(is_deleted=True)
            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({'status': 'unauthorized'}, status=403)


class DeleteNotificationView(LoginRequiredMixin, View):
    def post(self, request, id):
        notification = get_object_or_404(
            Notification, id=id, recipient=request.user, is_deleted=False
        )
        notification.delete() 
        return JsonResponse({'status': 'success'})





class CategoryProductListView(TemplateView):
    template_name = "userdashboard/view/category_products_list.html"

    def _add_delivery_dates(self, products):
        today = date.today()
        for product in products:
            if getattr(product, "delivery_time", None) is not None:
                delivery = today + timedelta(days=product.delivery_time)
                product.delivery_date = delivery.strftime("%a, %d %b")
            else:
                product.delivery_date = "N/A"

    def _add_ratings(self, products):
        """Add dynamic rating & total reviews to each product"""
        for product in products:
            reviews = product.reviews.all()

            if reviews.exists():
                total_reviews = reviews.count()
                avg_rating = reviews.aggregate(Avg("rating"))["rating__avg"]
                product.rating = round(avg_rating, 1)
                product.total_reviews = total_reviews
            else:
                product.rating = 0.0
                product.total_reviews = 0

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category_id = self.kwargs["category_id"]
        category = ProductCategory.objects.get(id=category_id)

        last_categories = ProductLastCategory.objects.filter(sub_category__category=category)

        products = Product.objects.filter(category=category, is_active=True)
        self._add_delivery_dates(products)
        self._add_ratings(products)

        user_cart_ids = []
        user_cart_quantities = {}
        user_wishlist_ids = []

        if self.request.user.is_authenticated:
            cart_items = CartProduct.objects.filter(user=self.request.user)
            user_cart_ids = [item.product.id for item in cart_items]
            user_cart_quantities = {item.product.id: item.quantity for item in cart_items}

            wishlist_items = WishlistProduct.objects.filter(user=self.request.user)
            user_wishlist_ids = [item.product.id for item in wishlist_items]

        context["category"] = category
        context["last_categories"] = last_categories
        context["products"] = products
        context["user_cart_ids"] = user_cart_ids
        context["user_cart_quantities"] = user_cart_quantities
        context["user_wishlist_ids"] = user_wishlist_ids

        return context



class AboutView(TemplateView):
    template_name = "pages/about.html"  

class PrivacyPolicyView(TemplateView):
    template_name = "pages/privacy_policy.html"

class TermsConditionsView(TemplateView):
    template_name = "pages/terms_conditions.html"

class ContactUsView(FormView):
    template_name = "pages/contact_us.html"
    form_class = ContactForm
    success_url = reverse_lazy('dashboard:contact_us')

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contact_info'] = Contact.objects.filter(
            display_phone__isnull=False
        ).first()
        return context
class UserLogsView(LoginRequiredMixin, TemplateView):
    template_name = "pages/userlogs.html"
    paginate_by = 10  

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        all_logs = (
            UserLogs.objects
            .filter(is_deleted=False)
            .select_related('user')
            .order_by('-created_at')
        )

        paginator = Paginator(all_logs, self.paginate_by)
        page_number = self.request.GET.get("page")

        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        context.update({
            "user_logs": page_obj,         
            "page_obj": page_obj,
            "paginator": paginator,
            "total_logs": all_logs.count(),
            "action_types": UserLogs.ActionType.choices,
        })

        return context
