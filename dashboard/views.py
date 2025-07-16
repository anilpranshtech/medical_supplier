from decimal import Decimal
from io import BytesIO
from xhtml2pdf import pisa
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.views import *
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.html import strip_tags
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from razorpay.errors import SignatureVerificationError
from .forms import *
from .models import *
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
from django.contrib import messages
from django.views.generic import TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.hashers import make_password
from django.contrib.auth import authenticate, login
from django.views.generic.edit import *
from datetime import date
from django.db.models import F
import random
import requests
from django.http import JsonResponse
from datetime import date, timedelta
from django.shortcuts import get_object_or_404
from django.db.models import Avg


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
                    product.delivery_date = delivery_date.strftime('%a, %d %b')  # e.g., Sun, 13 Jul
                else:
                    product.delivery_date = 'N/A'
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
        random_ids = random.sample(all_ids, min(len(all_ids), 7))
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
        return reverse_lazy('dashboard:home')


import re


class RegistrationView(View):
    template_name = "dashboard/register.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        errors = {}

        # Step 1: reCAPTCHA
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
            errors['recaptcha'] = 'Invalid reCAPTCHA. Please try again.'

        # Collect form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        phone = request.POST.get('phone')
        user_type = request.POST.get('user_type')
        buyer_type = request.POST.get('buyer_type')

        # Step 3: Basic field validations
        if not first_name:
            errors['first_name'] = 'First name is required.'
        if not last_name:
            errors['last_name'] = 'Last name is required.'
        if not email:
            errors['email'] = 'Email is required.'
        if not phone:
            errors['phone'] = 'Phone number is required.'
        if not password:
            errors['password'] = 'Password is required.'
        if not confirm_password:
            errors['confirm_password'] = 'Confirm password is required.'

        # Step 4: Email format & existing user
        if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors['email'] = 'Invalid email format.'
        elif email and User.objects.filter(username=email).exists():
            errors['email'] = 'An account with this email already exists.'

        # Step 5: Password strength
        if password:
            if len(password) < 8:
                errors['password'] = 'Password must be at least 8 characters.'
            if not re.search(r'[A-Z]', password):
                errors['password'] = 'Must include an uppercase letter.'
            if not re.search(r'[a-z]', password):
                errors['password'] = 'Must include a lowercase letter.'
            if not re.search(r'[0-9]', password):
                errors['password'] = 'Must include a number.'
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                errors['password'] = 'Must include a special character.'

        # Step 6: Password match
        if password and confirm_password and password != confirm_password:
            errors['confirm_password'] = 'Passwords do not match.'

        # Step 7: If errors → show messages
        if errors:
            for field, message in errors.items():
                messages.error(request, message, extra_tags=field)
            return render(request, self.template_name, {
                'form_data': request.POST
            })

        # Step 8: Send OTP
        otp_response = send_phone_otp(phone, TEXTDRIP_OTP_TOKEN)
        if "error" in otp_response:
            messages.error(request, otp_response["error"], extra_tags='phone')
            return render(request, self.template_name, {
                'form_data': request.POST
            })

        # Step 9: Save in session
        request.session['signup_data'] = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'password': password,
            'phone': phone,
            'user_type': user_type,
            'buyer_type': buyer_type,
            'supplier_company_name': request.POST.get('supplier_company_name'),
            'license_number': request.POST.get('license_number'),
            'age': request.POST.get('age'),
            'medical_needs': request.POST.get('medical_needs'),
            'company_name': request.POST.get('company_name'),
            'gst_number': request.POST.get('gst_number'),
            'department': request.POST.get('department'),
            'purchase_capacity': request.POST.get('purchase_capacity'),
        }

        return redirect('dashboard:verify_otp')

class VerifyOTPView(View):
    template_name = 'userdashboard/auth/verify_otp.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        otp = request.POST.get('otp')
        signup_data = request.session.get('signup_data')

        if not signup_data:
            messages.error(request, "Session expired. Please sign up again.")
            return redirect('dashboard:register')

        phone = signup_data['phone']
        result = verify_mobile_otp(VERIFY_URL, TEXTDRIP_OTP_TOKEN, phone, otp)

        if result.get("success") or result.get("status") is True:
            # Double-check user doesn't exist
            if User.objects.filter(username=signup_data['email']).exists():
                messages.error(request, "An account with this email already exists.")
                request.session.pop('signup_data', None)
                return redirect('dashboard:register')

            try:
                # Create user
                user = User.objects.create_user(
                    username=signup_data['email'],
                    email=signup_data['email'],
                    password=signup_data['password'],
                    first_name=signup_data['first_name'],
                    last_name=signup_data['last_name']
                )

                # Create profile based on user_type
                if signup_data['user_type'] == 'supplier':
                    SupplierProfile.objects.create(
                        user=user,
                        company_name=signup_data['supplier_company_name'],
                        license_number=signup_data['license_number']
                    )
                    messages.success(request, "Supplier account created successfully.")

                elif signup_data['buyer_type'] == 'retailer':
                    try:
                        age = int(signup_data['age'] or 0)
                    except ValueError:
                        age = 0
                    RetailProfile.objects.create(
                        user=user,
                        age=age,
                        medical_needs=signup_data['medical_needs'] or ''
                    )
                    messages.success(request, "Retailer user created. Please update your profile.")

                elif signup_data['user_type'] == 'wholesale' or signup_data['buyer_type'] == 'wholesaler':
                    WholesaleBuyerProfile.objects.create(
                        user=user,
                        company_name=signup_data['company_name'],
                        gst_number=signup_data['gst_number'],
                        department=signup_data['department'],
                        purchase_capacity=signup_data['purchase_capacity']
                    )
                    messages.success(request, "Wholesaler account created successfully.")

                else:
                    messages.error(request, "Invalid user type.")
                    user.delete()
                    request.session.pop('signup_data', None)
                    return redirect('dashboard:register')

                # Clean up session
                request.session.pop('signup_data', None)
                messages.success(request, "Account created successfully.")
                return redirect('dashboard:login')

            except Exception as e:
                messages.error(request, f"Error creating account: {str(e)}")
                return redirect('dashboard:register')
        else:
            messages.error(request, result.get("message", "OTP verification failed."))
            return redirect('dashboard:verify_otp')


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
from django.db.models import Count, Prefetch
from django.core.paginator import Paginator

class SearchResultsGridView(TemplateView):
    template_name = 'userdashboard/view/search_results_grid.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        category_id = self.request.GET.get('category')
        sub_category_id = self.request.GET.get('sub_category')
        last_category_id = self.request.GET.get('last_category')
        sort_by = self.request.GET.get('sort_by')
        page = self.request.GET.get('page', 1)

        context['selected_category'] = None
        context['selected_sub_category'] = None
        context['selected_last_category'] = None

        # Categories & Subcategories 
        last_categories_with_products = ProductLastCategory.objects.annotate(
            product_count=Count('product')
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

        # Handle products by last_category
        if last_category_id:
            try:
                last_category = ProductLastCategory.objects.get(id=last_category_id)
            except ProductLastCategory.DoesNotExist:
                last_category = None

            if last_category:
                products = Product.objects.filter(last_category=last_category)

                # Sorting
                if sort_by == '1':
                    products = products.order_by('-price')
                elif sort_by == '2':
                    products = products.order_by('price')
                else:
                    products = products.order_by('-created_at')

                paginator = Paginator(products, 16)
                page_obj = paginator.get_page(page)

                context.update({
                    'products': page_obj,
                    'page_obj': page_obj,
                    'paginator': paginator,
                    'selected_last_category': last_category,
                    'selected_sub_category': last_category.sub_category,
                    'selected_category': last_category.sub_category.category,
                    'total_products': paginator.count,
                })

        elif sub_category_id:
            try:
                sub_category = ProductSubCategory.objects.get(id=sub_category_id)
                context['last_categories'] = last_categories_with_products.filter(sub_category=sub_category)
                context['selected_sub_category'] = sub_category
                context['selected_category'] = sub_category.category
            except ProductSubCategory.DoesNotExist:
                pass

        elif category_id:
            try:
                category = ProductCategory.objects.get(id=category_id)
                subcategories = ProductSubCategory.objects.filter(category=category)
                context['last_categories'] = last_categories_with_products.filter(sub_category__in=subcategories)
                context['selected_category'] = category
            except ProductCategory.DoesNotExist:
                pass

        else:
            context['products'] = None

        # Wishlist/Cart 
        if self.request.user.is_authenticated:
            cart_ids = CartProduct.objects.filter(user=self.request.user).values_list('product_id', flat=True)
            context['user_cart_ids'] = list(cart_ids)
        else:
            context['user_cart_ids'] = []

        return context
    
class SearchResultsListView(TemplateView):
    template_name = 'userdashboard/view/search_results_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        category_id = self.request.GET.get('category')
        sub_category_id = self.request.GET.get('sub_category')
        last_category_id = self.request.GET.get('last_category')
        sort_by = self.request.GET.get('sort_by')
        page = self.request.GET.get('page', 1)

        context['selected_category'] = None
        context['selected_sub_category'] = None
        context['selected_last_category'] = None

        # LastCategories 
        last_categories_with_products = ProductLastCategory.objects.annotate(
            product_count=Count('product')
        ).filter(product_count__gt=0)

        # SubCategories 
        valid_subcategory_ids = last_categories_with_products.values_list('sub_category_id', flat=True).distinct()
        subcategories_with_products = ProductSubCategory.objects.filter(
            id__in=valid_subcategory_ids
        ).prefetch_related(
            Prefetch('productlastcategory_set', queryset=last_categories_with_products)
        )

        # Categories 
        valid_category_ids = subcategories_with_products.values_list('category_id', flat=True).distinct()
        categories_with_products = ProductCategory.objects.filter(
            id__in=valid_category_ids
        ).prefetch_related(
            Prefetch('productsubcategory_set', queryset=subcategories_with_products)
        )

        context['categories'] = categories_with_products

        if last_category_id:
            try:
                last_category = ProductLastCategory.objects.get(id=last_category_id)
                products = Product.objects.filter(last_category=last_category)

                # sorting 
                if sort_by == '1':
                    products = products.order_by('-price')
                elif sort_by == '2':
                    products = products.order_by('price')
                else:
                    products = products.order_by('-created_at')

                # Pagination 
                paginator = Paginator(products, 10)
                page_obj = paginator.get_page(page)

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
                pass

        elif sub_category_id:
            try:
                sub_category = ProductSubCategory.objects.get(id=sub_category_id)
                context['last_categories'] = last_categories_with_products.filter(sub_category=sub_category)
                context['selected_sub_category'] = sub_category
                context['selected_category'] = sub_category.category
            except ProductSubCategory.DoesNotExist:
                pass

        elif category_id:
            try:
                category = ProductCategory.objects.get(id=category_id)
                subcategories = ProductSubCategory.objects.filter(category=category)
                context['last_categories'] = last_categories_with_products.filter(sub_category__in=subcategories)
                context['selected_category'] = category
            except ProductCategory.DoesNotExist:
                pass

        # Wishlist/Cart 
        if self.request.user.is_authenticated:
            cart_ids = CartProduct.objects.filter(user=self.request.user).values_list('product_id', flat=True)
            context['user_cart_ids'] = list(cart_ids)
        else:
            context['user_cart_ids'] = []

        return context
    

class ProductDetailsView(TemplateView):
    template_name = 'userdashboard/view/product_details.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pk = self.kwargs.get('pk')

        if pk:
            try:
                product = Product.objects.select_related(
                    'category', 'sub_category', 'last_category', 'brand'
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

                context.update({
                    'product': product,
                    'other_images': other_images,
                    'reviews': reviews,
                    'rating_counts': rating_counts,
                    'total_reviews': total_reviews,
                    'average_rating': round(avg_rating, 1),
                    'user_cart_ids': user_cart_ids,
                    'user_wishlist_ids': user_wishlist_ids,
                })

            except Product.DoesNotExist:
                context['product'] = None
                context['other_images'] = []
            

        return context



class ShoppingCartView(LoginRequiredMixin, TemplateView):
    template_name = 'userdashboard/view/shopping_cart.html'
    login_url = 'dashboard:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart_items = CartProduct.objects.filter(user=self.request.user).select_related('product')
        total = sum(item.get_total_price() for item in cart_items)
        context['cart_items'] = cart_items
        context['total'] = total
        return context
    
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


class OrderSummaryView(LoginRequiredMixin, TemplateView):
    template_name = 'userdashboard/view/order_summary.html'
    login_url = 'dashboard:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch cart items for the authenticated user
        cart_items = CartProduct.objects.filter(user=self.request.user).select_related('product')

        # Calculate the total price of all cart items
        total = sum(item.get_total_price() for item in cart_items)

        # Add cart_items and total to the context
        context['cart_items'] = cart_items
        context['total'] = "{:.2f}".format(total)  # Format to two decimal places

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

        # Update quantity
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
            phone = None  # Adjust if RetailProfile has a phone field
            profile_type = 'retailer'
        except RetailProfile.DoesNotExist:
            try:
                profile = WholesaleBuyerProfile.objects.get(user=user)
                phone = None  # Adjust if WholesaleBuyerProfile has a phone field
                profile_type = 'wholesaler'
            except WholesaleBuyerProfile.DoesNotExist:
                try:
                    profile = SupplierProfile.objects.get(user=user)
                    phone = None  # Adjust if SupplierProfile has a phone field
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
        shipping = Decimal('0.00')  # Convert to Decimal; adjust based on your logic (e.g., Orders.shipping_fees)
        vat = Decimal('0.00')       # Convert to Decimal; adjust based on your logic (e.g., tax calculation)
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

def create_orders_from_cart(user, payment_type, payment_status):
    cart_items = CartProduct.objects.filter(user=user).select_related('product')

    for item in cart_items:
        Orders.objects.create(
            order_by=user,
            order_to=item.product.created_by,
            product=item.product,
            quantity=item.quantity,
            price=item.get_total_price(),
            phone_number=user.retailprofile.age if hasattr(user, 'retailprofile') else 0,
            payment_type=payment_type,
            payment_status=payment_status,
            payment_currency="INR" if payment_type == "razorpay" else "USD",
            shipping_fees=0,
            shipping_type="Standard",
            shipping_full_address="Auto-saved Address",
            shipping_city="Auto City",
            shipping_country="Auto Country",
            status="processing",
            created_at=now()
        )

    # Clear the cart after order creation
    cart_items.delete()

class PaymentMethodView(LoginRequiredMixin, View):
    template_name = 'userdashboard/view/payment_method.html'
    login_url = 'dashboard:login'

    def get_stripe_key(self, request):
        return settings.STRIPE_PUBLISHABLE_KEY, settings.STRIPE_SECRET_KEY

    def get_context_data(self, request):
        # Fetch cart items for the authenticated user
        cart_items = CartProduct.objects.filter(user=request.user).select_related('product')

        # Calculate totals
        subtotal = sum(item.get_total_price() for item in cart_items) or Decimal('0.00')
        shipping = Decimal('0.00')  # Adjust based on your shipping logic
        vat = Decimal('0.00')       # Adjust based on your tax logic
        total = subtotal + shipping + vat

        # Get default billing address
        billing = CustomerBillingAddress.objects.filter(user=request.user, is_default=True, is_deleted=False).first()

        # Prepare context
        context = {
            'cart_items': cart_items,
            'order_summary': {
                'subtotal': subtotal,
                'shipping': shipping,
                'vat': vat,
                'total': total
            },
            'billing': billing
        }
        return context

    def get(self, request):
        public_key, _ = self.get_stripe_key(request)
        context = self.get_context_data(request)
        total = context['order_summary']['total']

        # Razorpay: Create Order (convert total to INR paise)
        amount_in_paise = int(total * 100)  # Assuming total is in INR; adjust if needed
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
        payment_method = request.POST.get("payment_method")
        user = request.user

        if payment_method == "cod":
            payment = Payment.objects.create(
                name=user.get_full_name(),
                amount=total,
                payment_method="cod",
                paid=False
            )

            delivery_partner, _ = DeliveryPartner.objects.get_or_create(name="Delhivery")
            CODPayment.objects.create(
                user=request.user,
                name=user.get_full_name(),
                amount=total,
                paid=False,
                cod_tracking_id="COD123456",  # Replace with dynamic tracking ID logic
                delivery_partner=delivery_partner
            )

            create_orders_from_cart(user, payment_type="cod", payment_status="unpaid")

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
                    amount=int(total * 100),  # Convert to cents
                    currency="usd",
                    description="Product Payment"
                )

                payment = Payment.objects.create(
                    name=crd_name,
                    amount=total,
                    payment_method="stripe",
                    paid=True,
                    customer_id=customer.id
                )

                StripePayment.objects.create(
                    user=request.user,
                    name=crd_name,
                    amount=total,
                    paid=True,
                    customer_id=customer.id,
                    stripe_charge_id=charge.id,
                    stripe_customer_id=customer.id,
                    stripe_signature=charge.payment_method
                )

                create_orders_from_cart(user, payment_type="stripe", payment_status="paid")

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

            # Signature verification
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

            payment = Payment.objects.create(
                name=user.get_full_name(),
                amount=total,
                payment_method="razorpay",
                paid=True
            )

            RazorpayPayment.objects.create(
                user=request.user,
                name=user.get_full_name(),
                amount=total,
                paid=True,
                razorpay_payment_id=razorpay_payment_id,
                razorpay_order_id=razorpay_order_id,
                razorpay_signature=razorpay_signature
            )

            create_orders_from_cart(user, payment_type="razorpay", payment_status="paid")

            messages.success(request, "Razorpay Payment successful.")
            return redirect("dashboard:order_placed")

        else:
            messages.error(request, "Invalid payment method.")
            return redirect("dashboard:payment_method")


class OrderPlacedView(LoginRequiredMixin, TemplateView):
    template_name = 'userdashboard/view/order_placed.html'
    login_url = 'dashboard:login'

    def get_context_data(self, **kwargs):
        from datetime import timedelta
        from django.utils.timezone import now
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get the most recent successful payment
        payment = Payment.objects.filter(name=user.get_full_name()).order_by('-created_at').first()
        if not payment:
            context['error'] = "No payment found."
            return context

        # Get related cart items (assuming you didn't clear the cart after order)
        cart_items = CartProduct.objects.filter(user=user).select_related('product')

        subtotal = sum(item.get_total_price() for item in cart_items)
        shipping = Decimal('0.00')  # Adjust as per logic
        vat = Decimal('0.00')       # Adjust as per logic
        total = subtotal + shipping + vat

        # Delivery estimate
        estimated_delivery = now().date() + timedelta(days=5)

        # Payment method-specific info
        payment_method = payment.payment_method
        payment_details = None
        if payment_method == "stripe":
            payment_details = StripePayment.objects.filter(user=user).order_by('-created_at').first()
        elif payment_method == "razorpay":
            payment_details = RazorpayPayment.objects.filter(user=user).order_by('-created_at').first()
        elif payment_method == "cod":
            payment_details = CODPayment.objects.filter(user=user).order_by('-created_at').first()

        # Default billing address
        billing = CustomerBillingAddress.objects.filter(user=user, is_default=True, is_deleted=False).first()

        context.update({
            'payment': payment,
            'cart_items': cart_items,
            'order_summary': {
                'subtotal': subtotal,
                'shipping': shipping,
                'vat': vat,
                'total': total
            },
            'order_id': payment.id,
            'order_total': total,
            'order_date': payment.created_at if payment else now(),
            'estimated_delivery': estimated_delivery,
            'payment_method': payment_method,
            'payment_details': payment_details,
            'billing': billing
        })

        return context


class MyOrdersView(LoginRequiredMixin, TemplateView):
    template_name = 'userdashboard/view/my_orders.html'
    login_url = 'dashboard:login'  # or your login URL name

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['orders'] = Orders.objects.filter(order_by=user).select_related('product__brand').prefetch_related('product__productimage_set')
        return context


class OrderReceiptView(LoginRequiredMixin, TemplateView):
    template_name = 'userdashboard/view/order_receipt.html'
    login_url = 'dashboard:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        order_id = self.kwargs.get('pk')

        # Fetch the specific order for the authenticated user
        try:
            order = Orders.objects.get(id=order_id, order_by=user)
        except Orders.DoesNotExist:
            context['error'] = "Order not found or you don't have permission to view it."
            return context

        # Fetch related payment details
        payment = order.payment
        payment_method = payment.payment_method if payment else order.payment_type.lower()

        # Determine payment details based on payment method
        payment_details = None
        if payment_method == "stripe":
            payment_details = StripePayment.objects.filter(user=user, stripe_charge_id__isnull=False).order_by('-created_at').first()
            if payment_details and payment_details.stripe_customer_id:
                # Extract card details from CustomerBillingAddress.old_card
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
            payment_details = RazorpayPayment.objects.filter(user=user, razorpay_payment_id__isnull=False).order_by('-created_at').first()
        elif payment_method == "cod":
            payment_details = CODPayment.objects.filter(user=user, cod_tracking_id__isnull=False).order_by('-created_at').first()

        # Prepare order item details
        product_image = ProductImage.objects.filter(product=order.product, is_main=True).first()
        item = {
            'product': order.product,
            'quantity': order.quantity,
            'sku': order.product.supplier_sku,
            'total_price': order.price,  # Price already reflects quantity * product.price
            'image_url': product_image.image.url if product_image else None,
        }

        # Fetch billing address
        billing = CustomerBillingAddress.objects.filter(user=user, is_default=True, is_deleted=False).first()

        # Calculate order totals for summary
        related_orders = Orders.objects.filter(order_by=user, payment=order.payment).select_related('product')
        subtotal = sum(o.price for o in related_orders) if related_orders else order.price
        shipping = order.shipping_fees or 0
        vat = Decimal('0.00')  # Adjust if VAT logic is implemented
        total = subtotal + shipping + vat

        context.update({
            'order': order,
            'items': [item],  # Single item for this order
            'order_summary': {
                'subtotal': subtotal,
                'shipping': shipping,
                'vat': vat,
                'total': total,
            },
            'order_total': order.price,
            'order_date': order.created_at,
            'billing': billing,
            'estimated_delivery': order.created_at.date() + timedelta(days=5),
            'payment_method': payment_method,
            'payment_details': payment_details,
        })

        return context


class DownloadReceiptView(LoginRequiredMixin, View):
    login_url = 'dashboard:login'

    def get(self, request, pk):
        user = request.user
        try:
            order = Orders.objects.get(id=pk, order_by=user)
        except Orders.DoesNotExist:
            return HttpResponse("Order not found or unauthorized", status=404)

        payment = order.payment
        payment_method = payment.payment_method if payment else order.payment_type.lower()

        payment_details = None
        if payment_method == "stripe":
            payment_details = StripePayment.objects.filter(user=user, stripe_charge_id__isnull=False).order_by('-created_at').first()
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
            payment_details = RazorpayPayment.objects.filter(user=user, razorpay_payment_id__isnull=False).order_by('-created_at').first()
        elif payment_method == "cod":
            payment_details = CODPayment.objects.filter(user=user, cod_tracking_id__isnull=False).order_by('-created_at').first()

        product_image = ProductImage.objects.filter(product=order.product, is_main=True).first()
        item = {
            'product': order.product,
            'quantity': order.quantity,
            'sku': order.product.supplier_sku,
            'total_price': order.price,
            'image_url': request.build_absolute_uri(product_image.image.url) if product_image else None,
        }

        billing = CustomerBillingAddress.objects.filter(user=user, is_default=True, is_deleted=False).first()
        related_orders = Orders.objects.filter(order_by=user, payment=order.payment).select_related('product')
        subtotal = sum(o.price for o in related_orders) if related_orders else order.price
        shipping = order.shipping_fees or 0
        vat = Decimal('0.00')
        total = subtotal + shipping + vat

        context = {
            'order': order,
            'items': [item],
            'order_summary': {
                'subtotal': subtotal,
                'shipping': shipping,
                'vat': vat,
                'total': total,
            },
            'order_total': order.price,
            'order_date': order.created_at,
            'billing': billing,
            'estimated_delivery': order.created_at.date() + timedelta(days=5),
            'payment_method': payment_method,
            'payment_details': payment_details,
        }

        html_string = render_to_string('userdashboard/view/order_receipt_pdf.html', context)

        # Render PDF using xhtml2pdf
        result = BytesIO()
        pdf = pisa.CreatePDF(src=html_string, dest=result)
        if pdf.err:
            return HttpResponse('Error generating PDF', status=500)

        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="order_receipt_{order.id}.pdf"'
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
            phone = None
            profile_type = 'retailer'
        except RetailProfile.DoesNotExist:
            try:
                profile = WholesaleBuyerProfile.objects.get(user=user)
                phone = None
                profile_type = 'wholesaler'
            except WholesaleBuyerProfile.DoesNotExist:
                try:
                    profile = SupplierProfile.objects.get(user=user)
                    phone = None
                    profile_type = 'supplier'
                except SupplierProfile.DoesNotExist:
                    pass
        context['profile'] = profile
        context['profile_type'] = profile_type

        # Get phone number
        phone = None
        if profile_type == 'doctor':
            phone = profile.phone_number
        elif profile_type == 'medical_supplier':
            phone = profile.phone_details
        elif profile_type in ('corporate', 'wholesaler'):
            phone = None
        context['phone'] = phone or 'Not set'

        # Get avatar
        avatar = None
        if profile_type in ('medical_supplier', 'retailer', 'wholesaler', 'supplier'):
            avatar = profile.profile_picture
        context['avatar'] = avatar

        # Get default address
        try:
            default_address = CustomerBillingAddress.objects.get(user=user, is_default=True , is_deleted=False)
            context['default_address'] = default_address
        except CustomerBillingAddress.DoesNotExist:
            context['default_address'] = None

        # Order summary
        orders = Orders.objects.filter(order_by=user)
        context['total_orders'] = orders.count()
        context['pending_orders'] = orders.filter(status='pending').count()
        context['delivered_orders'] = orders.filter(status='delivered').count()
        context['cancelled_orders'] = orders.filter(status='cancelled').count()

        # Wishlist count
        context['wishlist_count'] = WishlistProduct.objects.filter(user=user).count()

        # Payment method (get most recent paid payment)
        stripe_payment = StripePayment.objects.filter(user=user, paid=True).order_by('-created_at').first()
        razorpay_payment = RazorpayPayment.objects.filter(user=user, paid=True).order_by('-created_at').first()
        cod_payment = CODPayment.objects.filter(user=user, paid=True).order_by('-created_at').first()

        latest_payment = None
        if stripe_payment:
            latest_payment = {'type': 'Stripe', 'details': f"{stripe_payment.name} ending in {stripe_payment.stripe_customer_id[-4:]}", 'created_at': stripe_payment.created_at}
        if razorpay_payment and (not latest_payment or razorpay_payment.created_at > latest_payment['created_at']):
            latest_payment = {'type': 'Razorpay', 'details': f"{razorpay_payment.name} ending in {razorpay_payment.razorpay_payment_id[-4:]}", 'created_at': razorpay_payment.created_at}
        if cod_payment and (not latest_payment or cod_payment.created_at > latest_payment['created_at']):
            latest_payment = {'type': 'COD', 'details': f"COD - {cod_payment.name}", 'created_at': cod_payment.created_at}

        context['payment_method'] = latest_payment

        return context

class UploadAvatarView(LoginRequiredMixin, View):
    def post(self, request):
        profile = None
        try:
            profile = RetailProfile.objects.get(user=self.request.user)
        except RetailProfile.DoesNotExist:
            try:
                profile = WholesaleBuyerProfile.objects.get(user=self.request.user)
            except WholesaleBuyerProfile.DoesNotExist:
                try:
                    profile = SupplierProfile.objects.get(user=self.request.user)
                except SupplierProfile.DoesNotExist:
                    pass

        if profile:
            if 'avatar' in self.request.FILES:
                profile.profile_picture = self.request.FILES['avatar']
                profile.save()
                messages.success(self.request, "Avatar updated successfully.")
            elif 'avatar_remove' in self.request.POST:
                profile.profile_picture.delete()
                profile.save()
                messages.success(self.request, "Avatar removed successfully.")
        else:
            messages.error(self.request, "Profile not found.")
        return redirect('dashboard:user_profile')

    def get(self, request):
        return redirect('dashboard:user_profile')

class EditProfileView(LoginRequiredMixin, UpdateView):
    template_name = 'pages/edit_profile.html'
    form_class = ProfileForm

    def get_object(self):
        user = self.request.user
        try:
            return RetailProfile.objects.get(user=user)
        except RetailProfile.DoesNotExist:
            try:
                return WholesaleBuyerProfile.objects.get(user=user)
            except WholesaleBuyerProfile.DoesNotExist:
                return SupplierProfile.objects.get(user=user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        # Determine profile_type directly
        user = self.request.user
        profile_type = None
        try:
            profile = RetailProfile.objects.get(user=user)
            phone = None
            profile_type = 'retailer'
        except RetailProfile.DoesNotExist:
            try:
                profile = WholesaleBuyerProfile.objects.get(user=user)
                phone = None
                profile_type = 'wholesaler'
            except WholesaleBuyerProfile.DoesNotExist:
                try:
                    profile = SupplierProfile.objects.get(user=user)
                    phone = None
                    profile_type = 'supplier'
                except SupplierProfile.DoesNotExist:
                    pass
        kwargs['profile_type'] = profile_type
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Reuse profile_type from get_form_kwargs logic
        user = self.request.user
        profile_type = None
        try:
            profile = RetailProfile.objects.get(user=user)
            phone = None
            profile_type = 'retailer'
        except RetailProfile.DoesNotExist:
            try:
                profile = WholesaleBuyerProfile.objects.get(user=user)
                phone = None
                profile_type = 'wholesaler'
            except WholesaleBuyerProfile.DoesNotExist:
                try:
                    profile = SupplierProfile.objects.get(user=user)
                    phone = None
                    profile_type = 'supplier'
                except SupplierProfile.DoesNotExist:
                    pass
        context['profile_type'] = profile_type
        return context

    def get_success_url(self):
        return reverse_lazy('dashboard:user_profile')


class EditEmailView(LoginRequiredMixin, View):
    def post(self, request):
        form = EmailForm(request.POST, instance=self.request.user)
        if form.is_valid():
            form.save()
            return JsonResponse({'status': 'success', 'message': 'Email updated successfully.'})
        return JsonResponse({'status': 'error', 'message': 'Failed to update email. Please check the form.'})


class EditPhoneView(LoginRequiredMixin, View):
    def post(self, request):
        default_address = CustomerBillingAddress.objects.filter(user=self.request.user, is_default=True, is_deleted=False).first()
        if not default_address:
            default_address = CustomerBillingAddress.objects.filter(user=self.request.user, is_deleted=False).first()
            if default_address:
                default_address.is_default = True
                default_address.save()
            else:
                default_address = CustomerBillingAddress.objects.create(
                    user=self.request.user,
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
        return JsonResponse({'status': 'error', 'message': 'Failed to update phone number. Please check the form.'})


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


# ------------------------------------------------------------------------------------------------------------------------
import logging
from .forms import *
logger = logging.getLogger(__name__)

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
