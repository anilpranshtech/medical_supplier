import uuid
from decimal import Decimal
from io import BytesIO
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
from django.views.decorators.csrf import csrf_exempt
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
from datetime import date, timedelta
import random
import re
import requests
from adminv2.models import *
from django.http import JsonResponse
from datetime import date, timedelta
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Avg
from django.db.models import  ExpressionWrapper, DecimalField, Case, When

import logging
from .forms import *
logger = logging.getLogger(__name__)

class HomeView(TemplateView):
    template_name = 'dashboard/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date() 
        today = date.today()

        def set_product_fields(product_queryset):
            for product in product_queryset:
                main_img = ProductImage.objects.filter(product=product, is_main=True).first()
                product.main_image = main_img.image.url if main_img else None

                # Calculate delivery date
                if product.delivery_time:
                    delivery_date = today + timedelta(days=product.delivery_time)
                    product.delivery_date = delivery_date.strftime('%a, %d %b')  
                else:
                    product.delivery_date = 'N/A'

                # Calculate rating and review count
                reviews = RatingReview.objects.filter(product=product)
                total_reviews = reviews.count()
                average_rating = reviews.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0.0
                product.rating = round(average_rating, 1) if total_reviews > 0 else 0.0
                product.total_reviews = total_reviews
            return product_queryset

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
        context['special_offers'] = set_product_fields(special_offers)

        # New Arrivals
        recent_products = Product.objects.filter(
            tag='recent',
            is_active=True
        ).order_by('-created_at')[:4]
        for product in recent_products:
            main_img = ProductImage.objects.filter(product=product, is_main=True).first()
            product.main_image = main_img.image.url if main_img else None

        context['recent_products'] = set_product_fields(recent_products)

        # Popular Medical Supplies
        popular_products = Product.objects.filter(
            tag='popular',
            is_active=True
        ).order_by('-created_at')[:4]
        for product in popular_products:
            main_img = ProductImage.objects.filter(product=product, is_main=True).first()
            product.main_image = main_img.image.url if main_img else None
        context['popular_products'] = set_product_fields(popular_products)

        # Limited-Time Deals
        limited_products = Product.objects.filter(
            tag='limited',
            is_active=True
        ).order_by('-created_at')[:4]
        for product in limited_products:
            main_img = ProductImage.objects.filter(product=product, is_main=True).first()
            product.main_image = main_img.image.url if main_img else None
        context['limited_products'] = set_product_fields(limited_products)

        # Featured Products
        all_ids = list(Product.objects.filter(is_active=True).values_list('id', flat=True))
        random_ids = random.sample(all_ids, min(len(all_ids), 6))
        featured_products = Product.objects.filter(id__in=random_ids)
        for product in featured_products:
            main_img = ProductImage.objects.filter(product=product, is_main=True).first()
            product.main_image = main_img.image.url if main_img else None
        context['featured_products'] = set_product_fields(featured_products)

        # Wishlist
        if self.request.user.is_authenticated:
            context['user_wishlist_ids'] = list(
                WishlistProduct.objects.filter(user=self.request.user)
                .values_list('product_id', flat=True)
            )

            context['user_cart_ids'] = list(
                CartProduct.objects.filter(user=self.request.user).values_list('product_id', flat=True)
            )
        else:
            context['user_wishlist_ids'] = []
            context['user_cart_ids'] = []

        context['banners'] = Banner.objects.filter(is_active=True)

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
            # Role validation
            if user_type == 'supplier':
                if not hasattr(user, 'supplierprofile'):
                    form.add_error(None, f"{email} is not registered as a supplier.")
                    return self.form_invalid(form)
            elif user_type == 'buyer':
                if buyer_type == 'retailer' and not hasattr(user, 'retailprofile'):
                    form.add_error(None, f"{email} is not registered as a retailer.")
                    return self.form_invalid(form)
                elif buyer_type == 'wholesaler' and not hasattr(user, 'wholesalebuyerprofile'):
                    form.add_error(None, f"{email} is not registered as a wholesaler.")
                    return self.form_invalid(form)

            # Login and set role
            login(self.request, user)
            if user_type == 'supplier':
                self.request.session['user_role'] = 'supplier'
            else:
                self.request.session['user_role'] = buyer_type

            # Success message
            messages.success(self.request, f"Welcome back, {email}!")

            return redirect(self.get_success_url())
        else:
            form.add_error(None, f"Invalid credentials for {email}.")
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse_lazy('dashboard:home')




def generate_token():
    return uuid.uuid4().hex

class RegistrationView(View):
    recaptcha_secret = '6LdTHV8rAAAAAIgLr2wdtdtWExTS6xJpUpD8qEzh'
    template_name = 'dashboard/register.html'

    def get(self, request):
        # Render the registration form with necessary context
        context = {
            'form_data': {},  # Empty dict for initial form rendering
            'nationalities': Nationality.objects.all(),
            'residencies': Residency.objects.all(),
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
        # reCAPTCHA verification
        recaptcha_response = request.POST.get('g-recaptcha-response')
        recaptcha_result = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={'secret': self.recaptcha_secret, 'response': recaptcha_response}
        ).json()

        if not recaptcha_result.get('success'):
            errors['recaptcha'] = 'Invalid reCAPTCHA.'

        # Collect data
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

        # Save pending data
        token = uuid.uuid4().hex
        PendingSignup.objects.create(token=token, data=request.POST.dict())

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

        data = pending.data
        phone = data.get('phone')

        # Verify OTP
        result = verify_mobile_otp(VERIFY_URL, TEXTDRIP_OTP_TOKEN, phone, otp)
        if not (result.get("success") or result.get("status") is True):
            return JsonResponse({'success': False, 'errors': {'otp': result.get("message", "OTP verification failed.")}}, status=400)

        # Create user
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=data['email'],
                    email=data['email'],
                    password=data['password'],
                    first_name=data['first_name'],
                    last_name=data['last_name']
                )

                if hasattr(user, 'phone'):
                    user.phone = phone
                    user.save()

                user_type = data.get('user_type')
                buyer_type = data.get('buyer_type')

                if user_type == 'supplier':
                    SupplierProfile.objects.create(
                        user=user,
                        phone=phone,
                        company_name=data.get('supplier_company_name', ''),
                        license_number=data.get('license_number', '')
                    )
                elif buyer_type == 'retailer':
                    nationality = Nationality.objects.filter(id=data.get('nationality')).first()
                    residency = Residency.objects.filter(id=data.get('residency')).first()
                    country_code = CountryCode.objects.filter(id=data.get('country_code')).first()
                    speciality = Speciality.objects.filter(id=data.get('speciality')).first()

                    RetailProfile.objects.create(
                        user=user,
                        phone=phone,
                        current_position=data.get('current_position', ''),
                        workplace=data.get('workplace', ''),
                        nationality=nationality,
                        residency=residency,
                        country_code=country_code,
                        speciality=speciality,
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
                else:
                    return JsonResponse({'success': False, 'errors': {'general': 'Invalid user type.'}}, status=400)

                pending.delete()
                return JsonResponse({'success': True, 'redirect': '/login/'})
        except Exception as e:
            return JsonResponse({'success': False, 'errors': {'general': f'Error creating account: {str(e)}'}}, status=500)


class ResendOTPView(View):
    def post(self, request):
        token = request.POST.get('token')
        if not token:
            return JsonResponse({'message': 'No token provided.'}, status=400)
        try:
            pending = PendingSignup.objects.get(token=token)
            phone = pending.data.get('phone')
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


class SearchResultsGridView(TemplateView):
    template_name = 'userdashboard/view/search_results_grid.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render_to_string(self.template_name, context, request=request)
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

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

        # Categories & Subcategories
        last_categories_with_products = ProductLastCategory.objects.annotate(
            product_count=Count('product', filter=Q(product__is_active=True))
        ).filter(product_count__gt=0)

        valid_subcategory_ids = last_categories_with_products.values_list('sub_category_id', flat=True).distinct()
        subcategories_with_products = ProductSubCategory.objects.filter(
            id__in=valid_subcategory_ids
        ).prefetch_related('productlastcategory_set')

        valid_category_ids = subcategories_with_products.values_list('category_id', flat=True).distinct()
        categories_with_products = ProductCategory.objects.filter(
            id__in=valid_category_ids
        ).prefetch_related('productsubcategory_set')

        context['categories'] = categories_with_products

        # Define effective price for sorting
        effective_price = ExpressionWrapper(
            F('price') * (1 - F('offer_percentage') / 100.0),
            output_field=DecimalField(max_digits=10, decimal_places=2)
        )
        products = Product.objects.annotate(
            effective_price=Case(
                When(offer_active=True, offer_percentage__isnull=False, then=effective_price),
                default=F('price'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )

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
                else:
                    products = products.order_by('-created_at')

                paginator = Paginator(products, 16)
                page_obj = paginator.get_page(page)

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
                category = ProductCategory.objects.get(id=category_id)
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
        else:
            context['user_cart_ids'] = []
            context['user_wishlist_ids'] = []

        return context


class SearchResultsListView(TemplateView):
    template_name = 'userdashboard/view/search_results_list.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render_to_string(self.template_name, context, request=request)
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request

        category_id = request.GET.get('category')
        sub_category_id = request.GET.get('sub_category')
        last_category_id = request.GET.get('last_category')
        sort_by = request.GET.get('sort_by')
        page_number = request.GET.get('page', 1)

        context.update({
            'selected_category': None,
            'selected_sub_category': None,
            'selected_last_category': None,
            'page_obj': None,
            'total_products': 0,
        })

        # Categories & Subcategories with active products
        last_categories_with_products = ProductLastCategory.objects.annotate(
            product_count=Count('product', filter=Q(product__is_active=True))
        ).filter(product_count__gt=0)

        valid_subcategory_ids = last_categories_with_products.values_list('sub_category_id', flat=True).distinct()
        subcategories_with_products = ProductSubCategory.objects.filter(
            id__in=valid_subcategory_ids
        ).prefetch_related(
            Prefetch('productlastcategory_set', queryset=last_categories_with_products)
        )

        valid_category_ids = subcategories_with_products.values_list('category_id', flat=True).distinct()
        categories_with_products = ProductCategory.objects.filter(
            id__in=valid_category_ids
        ).prefetch_related(
            Prefetch('productsubcategory_set', queryset=subcategories_with_products)
        )

        context['categories'] = categories_with_products

        # Base product queryset with effective price annotation
        effective_price = ExpressionWrapper(
            F('price') * (1 - F('offer_percentage') / 100.0),
            output_field=DecimalField(max_digits=10, decimal_places=2)
        )
        products_qs = Product.objects.annotate(
            effective_price=Case(
                When(offer_active=True, offer_percentage__isnull=False, then=effective_price),
                default=F('price'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )

        # Filtering + sorting
        if last_category_id:
            try:
                last_category = ProductLastCategory.objects.get(id=last_category_id)
                products_qs = products_qs.filter(last_category=last_category, is_active=True)

                if sort_by == '1':
                    products_qs = products_qs.order_by('-effective_price')
                elif sort_by == '2':
                    products_qs = products_qs.order_by('effective_price')
                else:
                    products_qs = products_qs.order_by('-created_at')

                paginator = Paginator(products_qs, 10)
                page_obj = paginator.get_page(page_number)

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
                category = ProductCategory.objects.get(id=category_id)
                subcategories = ProductSubCategory.objects.filter(category=category)
                context['last_categories'] = last_categories_with_products.filter(sub_category__in=subcategories)
                context['selected_category'] = category
            except ProductCategory.DoesNotExist:
                context['last_categories'] = []
        else:
            context['products'] = []

        # User-specific wishlist/cart IDs
        if request.user.is_authenticated:
            cart_ids = CartProduct.objects.filter(user=request.user).values_list('product_id', flat=True)
            wishlist_ids = WishlistProduct.objects.filter(user=request.user).values_list('product_id', flat=True)
            context['user_cart_ids'] = list(cart_ids)
            context['user_wishlist_ids'] = list(wishlist_ids)
        else:
            context['user_cart_ids'] = []
            context['user_wishlist_ids'] = []

        return context
    

class ProductDetailsView(TemplateView):
    template_name = 'userdashboard/view/product_details.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pk = self.kwargs.get('pk')

        if pk:
            try:
                product = Product.objects.select_related(
                    'category', 'sub_category', 'last_category', 'brand', 'event'  # Add 'event' to select_related
                ).get(id=pk)

                # Main and other images
                main_img = ProductImage.objects.filter(product=product, is_main=True).first()
                product.main_image = main_img.image.url if main_img else None
                other_images = ProductImage.objects.filter(product=product).exclude(id=main_img.id if main_img else None)

                # Rating & review data
                reviews = RatingReview.objects.filter(product=product)
                rating_counts = {i: reviews.filter(rating=i).count() for i in range(1, 6)}
                total_reviews = reviews.count()
                avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0

                # Cart & Wishlist IDs
                user_cart_ids = []
                user_wishlist_ids = []

                user = self.request.user
                if user.is_authenticated:
                    user_cart_ids = list(CartProduct.objects.filter(user=user).values_list('product_id', flat=True))
                    user_wishlist_ids = list(WishlistProduct.objects.filter(user=user).values_list('product_id', flat=True))

                # Event data
                event = product.event if hasattr(product, 'event') and product.event else None

                context.update({
                    'product': product,
                    'other_images': other_images,
                    'reviews': reviews,
                    'rating_counts': rating_counts,
                    'total_reviews': total_reviews,
                    'average_rating': round(avg_rating, 1),
                    'user_cart_ids': user_cart_ids,
                    'user_wishlist_ids': user_wishlist_ids,
                    'event': event,  # Add event to context
                })

            except Product.DoesNotExist:
                context['product'] = None
                context['other_images'] = []
                context['event'] = None  # Ensure event is None if product not found

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
            EventRegistration.objects.create(
                product=product,
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
            if item.product.productimage_set.exists():
                image = item.product.productimage_set.first().image.url

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
    login_url = 'dashboard:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        wishlist_items = WishlistProduct.objects.filter(user=self.request.user).select_related('product')

        for item in wishlist_items:
            main_img = ProductImage.objects.filter(product=item.product, is_main=True).first()
            item.product.main_image = main_img.image if main_img else None

        paginator = Paginator(wishlist_items, 5)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['wishlist_items'] = page_obj
        context['page_obj'] = page_obj
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


class ShoppingCartView(LoginRequiredMixin, TemplateView):
    template_name = 'userdashboard/view/shopping_cart.html'
    login_url = 'dashboard:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart_items = CartProduct.objects.filter(user=self.request.user).select_related('product')

        total = sum(item.get_total_price() for item in cart_items)

        paginator = Paginator(cart_items, 5)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['cart_items'] = page_obj
        context['page_obj'] = page_obj
        context['total'] = "{:.2f}".format(total)

        return context

@require_POST
def add_to_cart(request):
    product_id = request.POST.get('product_id')
    quantity_change = int(request.POST.get('quantity', 1))

    try:
        product = get_object_or_404(Product, id=product_id)
        cart_item, created = CartProduct.objects.get_or_create(
            user=request.user,
            product=product,
            defaults={'quantity': 0}
        )

        new_quantity = cart_item.quantity + quantity_change
        if new_quantity <= 0:
            cart_item.delete()
            return JsonResponse({'status': 'removed'})
        else:
            cart_item.quantity = new_quantity
            cart_item.save()
            return JsonResponse({'status': 'success', 'quantity': cart_item.quantity})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
@require_POST
def update_cart_item(request):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
    
    product_id = request.POST.get('product_id')
    quantity = int(request.POST.get('quantity', 1))
    
    try:
        cart_item = CartProduct.objects.get(user=request.user, product_id=product_id)
        cart_item.quantity = quantity
        cart_item.save()
        
        return JsonResponse({
            'status': 'success',
            'product_id': product_id,
            'quantity': quantity
        })
        
    except CartProduct.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Item not found'}, status=404)

@require_POST
def remove_from_cart(request):
    item_id = request.POST.get('item_id')

    try:
        cart_item = get_object_or_404(CartProduct, product__id=item_id, user=request.user)
        cart_item.delete()
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

        # Get phone number
        phone = None
        profile_type = None
        try:
            profile = RetailProfile.objects.get(user=user)
            phone = phone
            profile_type = 'retailer'
        except RetailProfile.DoesNotExist:
            try:
                profile = WholesaleBuyerProfile.objects.get(user=user)
                phone = phone
                profile_type = 'wholesaler'
            except WholesaleBuyerProfile.DoesNotExist:
                try:
                    profile = SupplierProfile.objects.get(user=user)
                    phone = phone
                    profile_type = 'supplier'
                except SupplierProfile.DoesNotExist:
                    pass
        context['phone'] = phone or 'Not set'
        context['profile_type'] = profile_type

        # Get all non-deleted addresses
        context['addresses'] = CustomerBillingAddress.objects.filter(user=user, is_deleted=False)
        context['default_address'] = CustomerBillingAddress.objects.filter(user=user, is_default=True, is_deleted=False).first()

        # Order summary based on CartProduct
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
            'total': total
        }

        return context


class AddAddressView(LoginRequiredMixin, FormView):
    form_class = AddressForm
    template_name = 'userdashboard/view/add_address.html'
    success_url = reverse_lazy('dashboard:shipping_info')

    def form_valid(self, form):
        address = form.save(commit=False)
        address.user = self.request.user
        if address.is_default:
            CustomerBillingAddress.objects.filter(user=self.request.user, is_default=True).update(is_default=False)
        address.save()
        messages.success(self.request, "Address added successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Failed to add address. Please check the form.")
        return super().form_invalid(form)


class EditAddressView(LoginRequiredMixin, UpdateView):
    model = CustomerBillingAddress
    form_class = AddressForm
    template_name = 'userdashboard/view/edit_address.html'
    success_url = reverse_lazy('dashboard:shipping_info')

    def get_queryset(self):
        return CustomerBillingAddress.objects.filter(user=self.request.user, is_deleted=False)

    def form_valid(self, form):
        address = form.save(commit=False)
        if address.is_default:
            CustomerBillingAddress.objects.filter(user=self.request.user, is_default=True).exclude(id=address.id).update(is_default=False)
        address.save()
        messages.success(self.request, "Address updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Failed to update address. Please check the form.")
        return super().form_invalid(form)


class RemoveAddressView(LoginRequiredMixin, View):
    def post(self, request, address_id):
        address = get_object_or_404(CustomerBillingAddress, id=address_id, user=self.request.user, is_deleted=False)
        address.is_deleted = True
        address.save()
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

        billing = CustomerBillingAddress.objects.filter(user=user, is_default=True, is_deleted=False).first()
        if not billing:
            logger.error(f"No default billing address found for user {user.id}")
            raise ValueError("No default billing address found")

        subtotal = sum(item.get_total_price() for item in cart_items)
        shipping_fees = Decimal('00.00')
        total = subtotal + shipping_fees

        with transaction.atomic():
            order = Order.objects.create(
                user=user,
                payment=payment,
                order_id=generate_order_id(),
                shipping_fees=shipping_fees,
                shipping_type='Standard Shipping',
                shipping_full_address=billing.customer_address1 + (f", {billing.customer_address2}" if billing.customer_address2 else ""),
                shipping_city=billing.customer_city,
                shipping_country=billing.customer_country,
                status='pending',
                created_at=timezone.now()
            )
            logger.info(f"Created Order {order.order_id} (ID: {order.id}) for user {user.id} with payment {payment.id}")

            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    order_by=user,
                    order_to=item.product.created_by,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.discounted_price(),
                    payment_type=payment_type,
                    payment_status=payment_status,
                    payment_currency='USD' if payment_type in ['stripe', 'cod'] else 'INR',
                    phone_number=billing.phone,
                    status='pending'
                )
                logger.info(f"Created OrderItem for product {item.product.id} (quantity: {item.quantity}) in Order {order.order_id}")

            # Clear the cart
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
        total = subtotal + shipping + vat
        billing = CustomerBillingAddress.objects.filter(user=request.user, is_default=True, is_deleted=False).first()

        return {
            'cart_items': cart_items,
            'order_summary': {
                'subtotal': subtotal,
                'shipping': shipping,
                'vat': vat,
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
                        cod_tracking_id="COD123456",  # Replace with dynamic tracking ID
                        delivery_partner=delivery_partner
                    )

                    order = create_orders_from_cart(user, payment_type="cod", payment_status="unpaid", payment=payment)
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
                        source=token
                    )
                    charge = stripe.Charge.create(
                        customer=customer.id,
                        amount=int(total * 100),
                        currency="usd",
                        description="Product Payment"
                    )

                    payment = Payment.objects.create(
                        user=user,
                        name=crd_name,
                        amount=total,
                        payment_method="stripe",
                        paid=True
                    )
                    logger.info(f"Created Stripe Payment {payment.id} for user {user.id}")

                    StripePayment.objects.create(
                        user=user,
                        name=crd_name,
                        amount=total,
                        paid=True,
                        stripe_charge_id=charge.id,
                        stripe_customer_id=customer.id,
                        stripe_signature=charge.payment_method,
                    )

                    order = create_orders_from_cart(user, payment_type="stripe", payment_status="paid", payment=payment)
                    card_details = charge.payment_method_details.get("card") if charge.payment_method_details else None

                    latest_address = CustomerBillingAddress.objects.filter(user=user, is_deleted=False).order_by('-id').first()
                    if latest_address:
                        for attr, value in {
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
                        }.items():
                            if value:
                                setattr(latest_address, attr, value)
                        latest_address.save()
                    else:
                        CustomerBillingAddress.objects.create(
                            user=user,
                            customer_name=crd_name,
                            customer_address1=request.POST.get("customer_address1"),
                            customer_address2=request.POST.get("customer_address2"),
                            customer_city=request.POST.get("customer_city"),
                            customer_state=request.POST.get("customer_state"),
                            customer_postal_code=request.POST.get("customer_postal_code"),
                            customer_country=request.POST.get("customer_country"),
                            customer_country_code=request.POST.get("customer_country_code"),
                            is_old=True,
                            old_card=json.dumps({
                                "brand": card_details.brand,
                                "last4": card_details.last4,
                                "exp_month": card_details.exp_month,
                                "exp_year": card_details.exp_year
                            }) if card_details else None,
                            is_default=True
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
                f"No order found for payment {payment.id} (method: {payment.payment_method}, created: {payment.created_at}) and user {request.user.id}")
            recent_order = Order.objects.filter(user=request.user).order_by('-created_at').first()
            if recent_order:
                logger.warning(
                    f"Fallback: Found recent order {recent_order.order_id} for user {request.user.id}, but not linked to payment {payment.id}")
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

        # Get the most recent payment
        payment = Payment.objects.filter(user=user).order_by('-created_at').first()
        if not payment:
            logger.error(f"No payment found for user {user.id} in get_context_data")
            context['error'] = "No payment found."
            return context

        # Prefetch main product images
        main_image_prefetch = Prefetch(
            'items__product__productimage_set',
            queryset=ProductImage.objects.filter(is_main=True),
            to_attr='main_image'
        )

        # Get the most recent order
        order = Order.objects.filter(
            user=user,
            payment=payment
        ).select_related(
            'payment'
        ).prefetch_related(main_image_prefetch).first()

        if not order:
            logger.error(f"No order found for payment {payment.id} and user {user.id} in get_context_data")
            # Fallback: Try recent order for user
            order = Order.objects.filter(user=user).order_by('-created_at').first()
            if order:
                logger.warning(f"Fallback: Using recent order {order.order_id} for user {user.id}, not linked to payment {payment.id}")
            else:
                context['error'] = "No order found for this payment."
                return context

        # Order summary calculations
        subtotal = sum(item.price * item.quantity for item in order.items.all()) or Decimal('0.00')
        shipping = order.shipping_fees or Decimal('00.00')
        vat = Decimal('0.00')
        total = subtotal + shipping + vat

        # Estimated delivery date
        max_delivery_days = max((item.product.delivery_time or 5) for item in order.items.all())
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

        # Billing address
        billing = CustomerBillingAddress.objects.filter(
            user=user,
            is_default=True,
            is_deleted=False
        ).first()

        # Context update
        context.update({
            'payment': payment,
            'order': order,
            'order_items': order.items.all(),
            'order_summary': {
                'subtotal': subtotal,
                'shipping': shipping,
                'vat': vat,
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
            'items__product__productimage_set',
            queryset=ProductImage.objects.filter(is_main=True),
            to_attr='main_image'
        )

        orders_qs = Order.objects.filter(user=user).select_related('payment').prefetch_related(
            main_image_prefetch,
            Prefetch('items__product__reviews', queryset=RatingReview.objects.filter(user=user), to_attr='user_reviews')
        ).order_by('-created_at')

        paginator = Paginator(orders_qs, 2)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['orders'] = page_obj.object_list
        context['page_obj'] = page_obj

        return context


class SubmitReviewView(LoginRequiredMixin, View):
    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        rating = request.POST.get('rating')
        review = request.POST.get('review')
        photo = request.FILES.get('photo')

        # Avoid duplicate
        if RatingReview.objects.filter(user=request.user, product=product).exists():
            messages.error(request, "You have already reviewed this product.")
            return redirect('dashboard:my_orders')

        if not rating:
            messages.error(request, "Rating is required.")
            return redirect('dashboard:my_orders')

        RatingReview.objects.create(
            product=product,
            user=request.user,
            rating=int(rating),
            review=review,
            photo=photo
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
            'items__product__productimage_set',
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

        # Prefetch main product images for OrderItems
        main_image_prefetch = Prefetch(
            'items__product__productimage_set',
            queryset=ProductImage.objects.filter(is_main=True),
            to_attr='main_image'
        )

        # Fetch the specific order
        try:
            order = Order.objects.filter(id=pk, user=user).select_related('payment').prefetch_related(main_image_prefetch).get()
        except Order.DoesNotExist:
            logger.error(f"Order {pk} not found for user {user.id}")
            return HttpResponse("Order not found or unauthorized", status=404)

        # Fetch related payment details
        payment = order.payment
        payment_method = payment.payment_method if payment else order.items.first().payment_type.lower()

        # Determine payment details
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
                'image_url': request.build_absolute_uri(product_image.image.url) if product_image else None,
            })

        # Fetch billing address
        billing = CustomerBillingAddress.objects.filter(user=user, is_default=True, is_deleted=False).first()

        # Calculate order totals
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
            'estimated_delivery': order.created_at.date() + timedelta(days=max((item.product.delivery_time or 5) for item in order.items.all())),
            'payment_method': payment_method,
            'payment_details': payment_details,
            'currency_symbol': 'USD' if payment_method in ['stripe', 'cod'] else 'INR'
        }

        html_string = render_to_string('userdashboard/view/order_receipt_pdf.html', context)

        # Render PDF using xhtml2pdf
        result = BytesIO()
        pdf = pisa.CreatePDF(src=html_string, dest=result)
        if pdf.err:
            logger.error(f"Failed to generate PDF for order {order.order_id}: {pdf.err}")
            return HttpResponse('Error generating PDF', status=500)

        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="order_receipt_{order.order_id}.pdf"'
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
                    pass

        context['profile'] = profile
        context['profile_type'] = profile_type

        # Phone
        phone = profile.phone if profile else None
        context['phone'] = phone or 'Not set'

        # Avatar (profile picture)
        avatar = profile.profile_picture if profile else None
        context['avatar'] = avatar

        # Default billing address
        try:
            default_address = CustomerBillingAddress.objects.get(user=user, is_default=True, is_deleted=False)
        except CustomerBillingAddress.DoesNotExist:
            default_address = None
        context['default_address'] = default_address

        # Order summary
        orders = Order.objects.filter(user=user)
        context.update({
            'total_orders': orders.count(),
            'pending_orders': orders.filter(status='pending').count(),
            'delivered_orders': orders.filter(status='delivered').count(),
            'cancelled_orders': orders.filter(status='cancelled').count(),
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
        profile, _ = get_user_profile(request.user)
        if profile:
            if 'avatar' in request.FILES:
                profile.profile_picture = request.FILES['avatar']
                profile.save()
                messages.success(request, "Avatar updated successfully.")
            elif 'avatar_remove' in request.POST:
                if profile.profile_picture:
                    profile.profile_picture.delete(save=True)
                messages.success(request, "Avatar removed successfully.")
        else:
            messages.error(request, "Profile not found.")
        return redirect('dashboard:user_profile')


class EditProfileView(LoginRequiredMixin, View):
    def post(self, request):
        user = request.user

        # Detect profile type and get profile
        profile = None
        profile_type = None
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
            return JsonResponse({'status': 'error', 'message': 'Profile not found.'}, status=400)

        # Get input fields
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        company_name = request.POST.get('company_name', '').strip()

        # Basic validation
        if not first_name or not last_name:
            return JsonResponse({'status': 'error', 'message': 'First and last name are required.'}, status=400)

        # Update User model
        user.first_name = first_name
        user.last_name = last_name
        user.save()

        # Update profile's company_name (if applicable)
        if profile_type in ['wholesaler', 'supplier']:
            profile.company_name = company_name

        profile.save()

        return JsonResponse({'status': 'success', 'message': 'Profile updated successfully.'})


class EditEmailView(LoginRequiredMixin, View):
    def post(self, request):
        form = EmailForm(request.POST, instance=self.request.user)
        if form.is_valid():
            form.save()
            return JsonResponse({'status': 'success', 'message': 'Email updated successfully.'})
        return JsonResponse({'status': 'error', 'message': 'Failed to update email. Please check the form.'})


class EditPhoneView(LoginRequiredMixin, View):
    def post(self, request):
        default_address = CustomerBillingAddress.objects.filter(
            user=request.user, is_default=True, is_deleted=False
        ).first()

        if not default_address:
            default_address = CustomerBillingAddress.objects.filter(
                user=request.user, is_deleted=False
            ).first()
            if default_address:
                default_address.is_default = True
                default_address.save()
            else:
                default_address = CustomerBillingAddress.objects.create(
                    user=request.user,
                    address_title="Default Address",
                    customer_address1="Not set",
                    customer_city="Not set",
                    customer_state="Not set",
                    customer_postal_code="00000",
                    customer_country="Not set",
                    is_default=True
                )

        form = PhoneForm(request.POST, instance=default_address)
        if form.is_valid():
            form.save()
            return JsonResponse({'status': 'success', 'message': 'Phone number updated successfully.'})
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to update phone number.',
            'errors': form.errors
        })


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

        signup_data = request.session.get('signup_data')
        if not signup_data:
            return JsonResponse({'success': False, 'message': 'Session expired. Please sign up again.'}, status=400)

        phone = signup_data.get('phone')
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


class RequestRoleView(LoginRequiredMixin, View):
    template_name = 'userdashboard/seller/request_role.html'
    success_url = reverse_lazy('dashboard:home')

    def get_form_class(self):
        role = self.request.POST.get('requested_role') or self.request.GET.get('requested_role', 'retailer')
        if role == 'retailer':
            return RetailProfileForm
        elif role == 'wholesaler':
            return WholesaleBuyerProfileForm
        elif role == 'supplier':
            return SupplierProfileForm
        return RetailProfileForm

    def get(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = form_class()
        return render(request, self.template_name, {
            'form': form,
            'profile_form': form,
            'role_choices': RoleRequest.ROLE_CHOICES,
            'selected_role': request.GET.get('requested_role', 'retailer')
        })

    def post(self, request, *args, **kwargs):
        requested_role = request.POST.get('requested_role')
        form_class = self.get_form_class()
        form = form_class(request.POST, request.FILES)

        if RoleRequest.objects.filter(user=request.user, requested_role=requested_role).exists():
            messages.error(request, "You already have a pending or approved request for this role.")
            return self.get(request)

        if form.is_valid():
            # Save role request
            role_request = RoleRequest.objects.create(
                user=request.user,
                requested_role=requested_role,
                status='pending'
            )

            # Save profile data
            profile = form.save(commit=False)
            profile.user = request.user

            if requested_role == 'retailer':
                RetailProfile.objects.update_or_create(user=request.user, defaults={
                    'profile_picture': profile.profile_picture,
                    'age': profile.age,
                    'medical_needs': profile.medical_needs
                })
            elif requested_role == 'wholesaler':
                WholesaleBuyerProfile.objects.update_or_create(user=request.user, defaults={
                    'profile_picture': profile.profile_picture,
                    'company_name': profile.company_name,
                    'gst_number': profile.gst_number,
                    'department': profile.department,
                    'purchase_capacity': profile.purchase_capacity
                })
            elif requested_role == 'supplier':
                SupplierProfile.objects.update_or_create(user=request.user, defaults={
                    'profile_picture': profile.profile_picture,
                    'company_name': profile.company_name,
                    'license_number': profile.license_number
                })

            messages.success(request, f"Your role request for {requested_role} has been submitted.")
            return redirect(self.success_url)

        messages.error(request, "Please correct the errors below.")
        return render(request, self.template_name, {
            'form': form,
            'profile_form': form,
            'role_choices': RoleRequest.ROLE_CHOICES,
            'selected_role': requested_role
        })


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

        # Send email confirmation
        send_mail(
            subject='Quotation Request Received',
            message='Thank you for your quotation request. Our team will get back to you shortly.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
        )
        rfq.email_sent = True

        rfq.save()
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
        return context


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
