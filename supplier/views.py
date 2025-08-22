import json
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render,redirect
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import logout
from django.views.generic import *
from supplier.forms import *
from supplier.models import *
from dashboard.mixins import SupplierPermissionMixin
from dashboard.models import *
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseServerError
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import check_password
from datetime import timezone, datetime 
from django.db import IntegrityError, transaction
from django.utils.dateparse import parse_date
from django.utils.timezone import localtime
from django.db.models.functions import Coalesce,TruncDay
from django.db.models import Sum, F, DecimalField, Prefetch
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg, Count, Q, Value
from django.db.models.functions import Coalesce
from calendar import monthrange
import logging
from django.views import View
from django.shortcuts import render
from django.db.models import Count, Q

logger = logging.getLogger(__name__)



class HomeView(LoginRequiredMixin, SupplierPermissionMixin, View):
    login_url = 'supplier:admin_login'

    def get(self, request):
        supplier = request.user

        # Query orders for supplier's products
        supplier_order_items = OrderItem.objects.filter(order_to=supplier).select_related(
            'order', 'order_by', 'order_to', 'product__category'
        )
        orders = Order.objects.filter(items__order_to=supplier).distinct().select_related('user', 'payment')

        # Total orders
        total_orders = orders.count()

        # Subtotal for supplier's items
        subtotal = supplier_order_items.annotate(
            product_total=F('price') * F('quantity')
        ).aggregate(
            total=Coalesce(Sum('product_total'), 0, output_field=DecimalField())
        )['total']
        

        # Top categories
        top_categories = supplier_order_items.annotate(
            category_name=F('product__category__name'),
            product_total=F('price') * F('quantity')
        ).values('category_name').annotate(
            total_sales=Sum('product_total')
        ).order_by('-total_sales')[:3]

        raw_colors = ['danger', 'primary', '#E4E6EF']
        color_map = {
            'danger': '#F1416C',
            'primary': '#7239EA',
            '#E4E6EF': '#E4E6EF'
        }

        categories_data = []
        for i, category in enumerate(top_categories):
            raw_color = raw_colors[i] if i < len(raw_colors) else '#E4E6EF'
            categories_data.append({
                'name': category['category_name'] or 'Uncategorized',
                'total_sales': float(category['total_sales']),
                'color': color_map.get(raw_color, raw_color)
            })

        # Monthly sales data
        now = timezone.now()
        first_day = now.replace(day=1)
        last_day = now.replace(day=monthrange(now.year, now.month)[1])

        daily_sales = supplier_order_items.filter(
            order__created_at__date__range=(first_day.date(), last_day.date())
        ).annotate(
            day=TruncDay('order__created_at'),
            product_total=F('price') * F('quantity')
        ).values('day').annotate(
            total_sales=Sum('product_total')
        ).order_by('day')

        discounted_daily_sales = supplier_order_items.filter(
            order__created_at__date__range=(first_day.date(), last_day.date()),
            product__offer_active=True
        ).annotate(
            day=TruncDay('order__created_at'),
            product_total=F('price') * F('quantity')
        ).values('day').annotate(
            total_sales=Sum('product_total')
        ).order_by('day')

        days_in_month = (last_day - first_day).days + 1
        sales_data = [0] * days_in_month
        discounted_sales_data = [0] * days_in_month
        labels = []

        current_date = first_day
        for i in range(days_in_month):
            labels.append(current_date.strftime('%d'))
            current_date += timedelta(days=1)

        for sale in daily_sales:
            day_index = (sale['day'].date() - first_day.date()).days
            if 0 <= day_index < days_in_month:
                sales_data[day_index] = float(sale['total_sales'] or 0)

        for sale in discounted_daily_sales:
            day_index = (sale['day'].date() - first_day.date()).days
            if 0 <= day_index < days_in_month:
                discounted_sales_data[day_index] = float(sale['total_sales'] or 0)

        this_month_sales = sum(sales_data)
        this_month_discounted_sales = sum(discounted_sales_data)

        # Previous month sales
        previous_month = first_day - timedelta(days=1)
        previous_month_first_day = previous_month.replace(day=1)
        previous_month_last_day = previous_month.replace(day=monthrange(previous_month.year, previous_month.month)[1])

        previous_month_discounted_sales = supplier_order_items.filter(
            order__created_at__date__range=(previous_month_first_day.date(), previous_month_last_day.date()),
            product__offer_active=True
        ).annotate(
            product_total=F('price') * F('quantity')
        ).aggregate(
            total=Coalesce(Sum('product_total'), 0, output_field=DecimalField())
        )['total']

        growth_percentage = (
            ((this_month_discounted_sales - float(previous_month_discounted_sales)) /
             float(previous_month_discounted_sales)) * 100
            if previous_month_discounted_sales > 0 else 0
        )

        # This month customers
        this_month_customers = supplier_order_items.filter(
            order__created_at__date__range=(first_day.date(), last_day.date())
        ).values('order_by').distinct().count()

        # This month orders
        this_month_orders = orders.filter(
            created_at__date__range=(first_day.date(), last_day.date())
        ).count()
        
       
        # This week orders
        today = timezone.now()
        start_of_week = today - timedelta(days=today.weekday())  # Monday
        end_of_week = start_of_week + timedelta(days=6)  # Sunday

        this_week_orders = orders.filter(
            created_at__date__range=(start_of_week.date(), end_of_week.date())
        ).count()
        
        # Recent orders
        recent_orders = supplier_order_items.select_related('order', 'product', 'order_by').order_by('-order__created_at')[:6]

        context = {
            'total_orders': total_orders,
            'subtotal': float(subtotal),
            'categories_data': categories_data,
            'this_month_customers': this_month_customers,
            'this_month_orders': this_month_orders,
            'this_week_orders': this_week_orders,
            'recent_orders': recent_orders,
            'sales_chart_data': {
                'labels': labels,
                'data': sales_data,
                'total': this_month_sales
            },
            'discounted_sales_data': {
                'labels': labels,
                'data': discounted_sales_data,
                'total': this_month_discounted_sales,
                'growth_percentage': round(growth_percentage, 2),
                'previous_month_total': float(previous_month_discounted_sales)
            }
            
        }
        logger.info(f"Supplier {supplier.id} accessed dashboard: {total_orders} orders, {this_month_sales} sales")
        return render(request, 'supplier/home.html', context)


class ProductsView(LoginRequiredMixin, SupplierPermissionMixin, View):
    template = 'supplier/products.html'

    def get(self, request):
        user = request.user
        products = Product.objects.filter(created_by=user)

        for product in products:
            image = ProductImage.objects.filter(product=product).first()
            product.image_url = image.image.url if image else '/static/supplier/media/stock/ecommerce/placeholder.png'

        return render(request, self.template, {'products': products})
    
    
class AddproductsView(LoginRequiredMixin, SupplierPermissionMixin, View):
    template = 'supplier/add-product.html'

    def get(self, request):
        context = {
            'categories': ProductCategory.objects.all(),
            'subcategories': ProductSubCategory.objects.all(),
            'lastcategories': ProductLastCategory.objects.all(),
        }
        return render(request, self.template, context)

    def post(self, request):
        data = request.POST
        files = request.FILES
        name = data.get('product_name')
        description = data.get('product_description')
        selling_countries = data.get('selling_countries')
        price = self._parse_float(data.get('price'))
        stock_quantity = self._parse_int(data.get('product_quantity'), min_value=0)
        commission = self._parse_float(data.get('commission_percentage'), 0, 100)
        offer_percentage = self._parse_float(data.get('offer_percentage'), 0, 100)
        pcs_per_unit = self._parse_int(data.get('pcs_per_unit'), min_value=1)
        min_order_qty = self._parse_int(data.get('min_order_qty'), min_value=1)
        low_stock_alert = self._parse_int(data.get('low_stock_alert'), min_value=0)
        expiration_days = self._parse_int(data.get('expiration_days'), min_value=0)
        is_returnable = data.get('is_returnable') == 'on'
        return_time_limit = self._parse_int(data.get('return_time_limit'), min_value=0)
        delivery_time = self._parse_int(data.get('delivery_time'), min_value=0)
        weight = self._parse_float(data.get('weight'), min_value=0)
        manufacture_date = self._parse_date(data.get('manufacture_date'))
        expiry_date = self._parse_date(data.get('expiry_date'))
        offer_start = self._parse_date(data.get('offer_start'))
        offer_end = self._parse_date(data.get('offer_end'))
        button_type = data.get('button_type')
        show_add_to_cart = button_type in ['both', 'cart']
        show_rfq = button_type in ['both', 'rfq']
        both_selected = button_type == 'both'

        def _is_event_category(self, category):
            event_keywords = ['conference', 'event', 'webinar']
            if category and category.name:
                return category.name.lower() in event_keywords
            return False

        if offer_start and offer_end and offer_end < offer_start:
            messages.warning(request, "Offer end date cannot be before start date.")

        if request.user.is_superuser:
            offer_active = data.get('offer_active') == 'on'
        else:
            offer_active = False

        ask_admin_to_publish = data.get('ask_admin_to_publish') == 'on'

        # Handle brand creation
        brand_name = data.get('brand')
        brand = None
        if brand_name:
            brand, _ = Brand.objects.get_or_create(
                name=brand_name,
                defaults={'supplier': request.user}
            )

        try:
            product = Product.objects.create(
                name=name or '',
                description=description or '',
                price=price or 0,
                stock_quantity=stock_quantity or 0,
                brand=brand,
                category=self._get_object(ProductCategory, data.get('category')),
                sub_category=self._get_object(ProductSubCategory, data.get('sub_category')),
                last_category=self._get_object(ProductLastCategory, data.get('last_category')),
                product_from=data.get('product_from'),
                warranty=data.get('warranty'),
                condition=data.get('condition'),
                manufacture_date=manufacture_date,
                expiry_date=expiry_date,
                weight=weight or 0,
                selling_countries=selling_countries,
                weight_unit=data.get('weight_unit'),
                barcode=data.get('barcode'),
                commission_percentage=commission or 0,
                is_returnable=is_returnable,
                return_time_limit=return_time_limit or 0,
                delivery_time=delivery_time or 0,
                keywords=data.get('keywords'),
                brochure=files.get('brochure'),
                supplier_sku=data.get('supplier_sku'),
                pcs_per_unit=pcs_per_unit or 1,
                min_order_qty=min_order_qty or 1,
                low_stock_alert=low_stock_alert or 0,
                expiration_days=expiration_days or 0,
                tag=data.get('tag'),
                offer_percentage=offer_percentage or 0,
                offer_start=offer_start,
                offer_end=offer_end,
                offer_active=offer_active,
                ask_admin_to_publish=ask_admin_to_publish,
                is_active=(data.get('is_active') == 'True'),
                show_add_to_cart=show_add_to_cart,
                show_rfq=show_rfq,
                Both=both_selected,
                created_by=request.user
            )

            category_obj = self._get_object(ProductCategory, data.get('category'))
            if _is_event_category(self, category_obj):
                event = Event.objects.create(
                    conference_link=data.get('registration_link') or None,  # Updated to match form field
                    speaker_name=data.get('webinar_name') or None,  # Updated to match form field
                    conference_at=data.get('webinar_date') or None,  # Updated to match form field
                    duration=data.get('webinar_duration') or None,  # Updated to match form field
                    venue=data.get('webinar_venue') or None,  # Updated to match form field
                )
                product.event = event
                product.save()

            main_image = files.get('main_image')
            if main_image:
                ProductImage.objects.create(product=product, image=main_image, is_main=True)

            gallery_images = files.getlist('gallery_images')
            for img in gallery_images:
                ProductImage.objects.create(product=product, image=img, is_main=False)

            messages.success(request, "Product added successfully.")
            return redirect('supplier:products_list')

        except IntegrityError as e:
            messages.error(request, f"Integrity error: {e}")
        except Exception as e:
            messages.error(request, f"Error: {e}")

        return self._render_form_with_context(request, data)

    def _parse_float(self, val, min_value=None, max_value=None):
        if not val:
            return None
        try:
            f = float(val)
            if (min_value is not None and f < min_value) or (max_value is not None and f > max_value):
                return None
            return f
        except:
            return None

    def _parse_int(self, val, min_value=None):
        if not val:
            return None
        try:
            i = int(val)
            if min_value is not None and i < min_value:
                return None
            return i
        except:
            return None

    def _parse_date(self, val):
        try:
            return parse_date(val)
        except:
            return None

    def _get_object(self, model, pk):
        if not pk:
            return None
        try:
            return model.objects.get(id=pk)
        except model.DoesNotExist:
            return None

    def _render_form_with_context(self, request, data):
        return render(request, self.template, {
            'categories': ProductCategory.objects.all(),
            'subcategories': ProductSubCategory.objects.all(),
            'lastcategories': ProductLastCategory.objects.all(),
            **data.dict()
        })

    
class EditproductsView(LoginRequiredMixin, SupplierPermissionMixin, View):
    template = 'supplier/edit-product.html'

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        product_images = ProductImage.objects.filter(product=product)
        main_image = product_images.filter(is_main=True).first()
        gallery_images = product_images.filter(is_main=False)
        categories = ProductCategory.objects.all()
        subcategories = ProductSubCategory.objects.filter(category=product.category) if product.category else ProductSubCategory.objects.none()
        lastcategories = ProductLastCategory.objects.filter(sub_category=product.sub_category) if product.sub_category else ProductLastCategory.objects.none()
        selling_countries = product.selling_countries or ''
        brochure_url = product.brochure.url if product.brochure else None

        context = {
            'pk': pk,
            'product': product,
            'product_name': product.name,
            'product_description': product.description,
            'price': product.price,
            'product_quantity': product.stock_quantity,
            'product_from': product.product_from,
            'selling_countries': selling_countries,
            'warranty': product.warranty,
            'condition': product.condition,
            'is_returnable': product.is_returnable,
            'return_time_limit': product.return_time_limit,
            'manufacture_date': product.manufacture_date.strftime('%Y-%m-%d') if product.manufacture_date else '',
            'expiry_date': product.expiry_date.strftime('%Y-%m-%d') if product.expiry_date else '',
            'weight': product.weight,
            'weight_unit': product.weight_unit,
            'delivery_time': product.delivery_time,
            'commission_percentage': product.commission_percentage,
            'barcode': product.barcode,
            'keywords': product.keywords,
            'supplier_sku': product.supplier_sku,
            'pcs_per_unit': product.pcs_per_unit,
            'min_order_qty': product.min_order_qty,
            'low_stock_alert': product.low_stock_alert,
            'expiration_days': product.expiration_days,
            'tag': product.tag,
            'offer_percentage': product.offer_percentage,
            'offer_start': product.offer_start.strftime('%Y-%m-%d') if product.offer_start else '',
            'offer_end': product.offer_end.strftime('%Y-%m-%d') if product.offer_end else '',
            'is_active': 'True' if product.is_active else 'False',
            'brand': product.brand.name if product.brand else '',
            'categories': categories,
            'category_id': product.category.id if product.category else None,
            'selected_sub_category': product.sub_category.id if product.sub_category else None,
            'selected_sub_category_name': product.sub_category.name if product.sub_category else '',
            'selected_last_category': product.last_category.id if product.last_category else None,
            'selected_last_category_name': product.last_category.name if product.last_category else '',
            'main_image_url': main_image.image.url if main_image else None,
            'gallery_images': gallery_images,
            'brochure_url': brochure_url,
            'subcategories': subcategories,
            'lastcategories': lastcategories,
        }
        return render(request, self.template, context)

    def post(self, request, pk):
        try:
            product = get_object_or_404(Product, pk=pk)

            # Basic info
            product.name = request.POST.get('product_name', '')
            product.description = request.POST.get('product_description', '')
            product.price = float(request.POST.get('price') or 0)
            product.stock_quantity = int(request.POST.get('product_quantity') or 0)
            product.product_from = request.POST.get('product_from', '')
            product.selling_countries = request.POST.get('selling_countries', '')
            product.warranty = request.POST.get('warranty', 'none')
            product.condition = request.POST.get('condition', 'new')
            product.weight = float(request.POST.get('weight') or 0)
            product.weight_unit = request.POST.get('weight_unit', 'gm')
            product.delivery_time = int(request.POST.get('delivery_time') or 0)
            product.commission_percentage = float(request.POST.get('commission_percentage') or 0)
            product.barcode = request.POST.get('barcode', '')
            product.keywords = request.POST.get('keywords', '')
            product.supplier_sku = request.POST.get('supplier_sku', '')
            product.pcs_per_unit = int(request.POST.get('pcs_per_unit') or 1)
            product.min_order_qty = int(request.POST.get('min_order_qty') or 1)
            product.low_stock_alert = int(request.POST.get('low_stock_alert') or 0)
            product.expiration_days = int(request.POST.get('expiration_days') or 0)
            product.tag = request.POST.get('tag', 'none')
            product.is_active = request.POST.get('is_active') == 'True'

            # Returnable toggle
            product.is_returnable = request.POST.get('is_returnable') == 'on'
            product.return_time_limit = int(request.POST.get('return_time_limit') or 0) if product.is_returnable else 0

            # Dates
            product.manufacture_date = parse_date(request.POST.get('manufacture_date'))
            product.expiry_date = parse_date(request.POST.get('expiry_date'))
            product.offer_start = parse_date(request.POST.get('offer_start')) if request.POST.get('offer_start') else None
            product.offer_end = parse_date(request.POST.get('offer_end')) if request.POST.get('offer_end') else None

            # Offer
            offer_percentage = request.POST.get('offer_percentage')
            if offer_percentage:
                product.offer_percentage = float(offer_percentage)

            # Category
            category_id = request.POST.get('category')
            if category_id:
                product.category = ProductCategory.objects.filter(pk=category_id).first()
            sub_category_id = request.POST.get('sub_category')
            if sub_category_id:
                product.sub_category = ProductSubCategory.objects.filter(pk=sub_category_id).first()
            last_category_id = request.POST.get('last_category')
            if last_category_id:
                product.last_category = ProductLastCategory.objects.filter(pk=last_category_id).first()

            # Brand
            brand_name = request.POST.get('brand')
            if brand_name:
                brand_obj, _ = Brand.objects.get_or_create(name=brand_name)
                product.brand = brand_obj

            # Images
            if 'main_image' in request.FILES:
                ProductImage.objects.filter(product=product, is_main=True).delete()
                ProductImage.objects.create(product=product, image=request.FILES['main_image'], is_main=True)

            if 'gallery_images' in request.FILES:
                for image in request.FILES.getlist('gallery_images'):
                    ProductImage.objects.create(product=product, image=image, is_main=False)

            # Brochure
            if 'brochure' in request.FILES:
                product.brochure = request.FILES['brochure']

            product.save()
            messages.success(request, 'Product updated successfully!')

        except Exception as e:
            print('Exception in edit product:', e)
            messages.error(request, 'Issue in Product update!')

        return redirect('supplier:products_list')

    
class DeleteProductImageView(LoginRequiredMixin, SupplierPermissionMixin, View):
    def post(self, request, pk):
        image = get_object_or_404(ProductImage, pk=pk)
        product_id = image.product.id
        image.delete()
        return redirect('supplier:edit_product', pk=product_id)
    
    def get(self, request, pk):
        return self.post(request, pk)


class DeleteProductView(LoginRequiredMixin, SupplierPermissionMixin, View):
    def post(self, request, pk):
        try:
            product = get_object_or_404(Product, pk=pk)
            product.delete()
            messages.success(request, "Product deleted successfully")
            return JsonResponse({'success': True})
        except Exception as e:
            messages.error(request, "Faild to delect product.")
            return JsonResponse({'success': False})


class CreateProductCategoryView(SupplierPermissionMixin, View):
    def post(self, request):
        name = request.POST.get('name')
        if not name:
            messages.error(request, "Category name is required.")
            return redirect('supplier:add_product')

        if ProductCategory.objects.filter(name__iexact=name).exists():
            messages.warning(request, "This category already exists.")
            return redirect('supplier:add_product')

        ProductCategory.objects.create(name=name)
        messages.success(request, f"Category '{name}' created successfully.")
        return redirect('supplier:add_product')
 

class CreateProductSubCategoryView(SupplierPermissionMixin, View):
    def post(self, request):
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        if not name or not category_id:
            messages.error(request, "Sub-category name and parent category are required.")
        elif ProductSubCategory.objects.filter(name__iexact=name).exists():
            messages.warning(request, "This sub-category already exists.")
        else:
            ProductSubCategory.objects.create(
                name=name,
                category_id=category_id
            )

            messages.success(request, f"Sub-category '{name}' created successfully.")
        return redirect('supplier:add_product')

    
class CreateProductLastCategoryView(SupplierPermissionMixin, View):
    def post(self, request):
        name = request.POST.get('name')
        sub_category_id = request.POST.get('sub_category')
        if not name or not sub_category_id:
            messages.error(request, "Last category name and parent sub-category are required.")
        elif ProductLastCategory.objects.filter(name__iexact=name).exists():
            messages.warning(request, "This last category already exists.")
        else:
            ProductLastCategory.objects.create(
                name=name,
                sub_category_id=sub_category_id
            )
            messages.success(request, f"Last category '{name}' created successfully.")
        return redirect('supplier:add_product')
    

class GetSubcategoriesView(SupplierPermissionMixin, View):
    def get(self, request, *args, **kwargs):
        category_id = request.GET.get('category_id')
        if category_id:
            subcats = ProductSubCategory.objects.filter(category_id=category_id).values('id', 'name')
            return JsonResponse(list(subcats), safe=False)
        return JsonResponse([], safe=False)


class GetLastCategoriesView(SupplierPermissionMixin, View):
    def get(self, request, *args, **kwargs):
        sub_id = request.GET.get('sub_id')
        if sub_id:
            lastcats = ProductLastCategory.objects.filter(sub_category_id=sub_id).values('id', 'name')
            return JsonResponse(list(lastcats), safe=False)
        return JsonResponse([], safe=False)


class AdminloginView(SupplierPermissionMixin, View):
    def get(self, request):
        return render(request, 'supplier/sign-in.html')

    def post(self, request):
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)

            if user is not None:
                if hasattr(user, 'supplierprofile'):
                    login(request, user)
                    return redirect('supplier:supplier') 
                else:
                    messages.error(request, "Only suppliers are allowed to log in.")
            else:
                messages.error(request, "Invalid email or password.")
        except User.DoesNotExist:
            messages.error(request, "User with this email does not exist.")
        return render(request, 'supplier/sign-in.html')


@method_decorator(login_required, name='dispatch')
class UserListView(SupplierPermissionMixin, ListView):
    model = User
    template_name = 'supplier/user_list.html'
    context_object_name = 'users'
    ordering = ['-date_joined']

    def get_queryset(self):
        # Get all users
        queryset = super().get_queryset()

        # Filter by role
        selected_role = self.request.GET.get('role', '')
        if selected_role == 'retailer':
            queryset = queryset.filter(retailprofile__isnull=False)
        elif selected_role == 'wholesaler':
            queryset = queryset.filter(wholesalebuyerprofile__isnull=False)
        elif selected_role == 'supplier':
            queryset = queryset.filter(supplierprofile__isnull=False)

        # Search functionality
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                username__icontains=search_query
            ) | queryset.filter(
                email__icontains=search_query
            ) | queryset.filter(
                first_name__icontains=search_query
            ) | queryset.filter(
                last_name__icontains=search_query
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get statistics
        total_users = User.objects.count()
        retail_users = RetailProfile.objects.count()
        wholesale_users = WholesaleBuyerProfile.objects.count()
        supplier_users = SupplierProfile.objects.count()

        # Add to context
        context['total_users'] = total_users
        context['retail_users'] = retail_users
        context['wholesale_users'] = wholesale_users
        context['supplier_users'] = supplier_users
        context['selected_role'] = self.request.GET.get('role', '')
        context['search_query'] = self.request.GET.get('search', '')

        return context


@method_decorator(login_required, name='dispatch')
class UserAddView(SupplierPermissionMixin, CreateView):
    model = User
    template_name = 'supplier/user_add.html'
    success_url = reverse_lazy('supplier:user_list')

    class Form(forms.ModelForm):
        password = forms.CharField(widget=forms.PasswordInput)
        role = forms.ChoiceField(choices=[
            ('retailer', 'Retailer'),
            ('wholesaler', 'Wholesaler'),
            ('supplier', 'Supplier'),
        ], required=True)

        class Meta:
            model = User
            fields = ['username', 'email', 'first_name', 'last_name', 'password']

    form_class = Form

    def form_valid(self, form):
        with transaction.atomic():
            # Save the user
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()

            # Create profile based on selected role
            role = form.cleaned_data['role']
            if role == 'retailer':
                RetailProfile.objects.create(user=user)
            elif role == 'wholesaler':
                WholesaleBuyerProfile.objects.create(
                    user=user,
                    company_name='Default Company',  # Required field
                    gst_number='N/A',  # Required field
                    department='N/A',  # Required field
                    purchase_capacity=0  # Required field
                )
            elif role == 'supplier':
                SupplierProfile.objects.create(
                    user=user,
                    company_name='Default Company',  # Required field
                    license_number='N/A'  # Required field
                )

        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class UserEditView(SupplierPermissionMixin, UpdateView):
    model = User
    template_name = 'supplier/user_edit.html'
    success_url = reverse_lazy('supplier:user_list')

    class Form(forms.ModelForm):
        password = forms.CharField(widget=forms.PasswordInput, required=False,
                                   help_text="Leave blank to keep current password")
        role = forms.ChoiceField(choices=[
            ('none', 'None'),
            ('retailer', 'Retailer'),
            ('wholesaler', 'Wholesaler'),
            ('supplier', 'Supplier'),
        ], required=True)

        # Profile fields
        age = forms.IntegerField(required=False, help_text="Required for Retailer role")
        medical_needs = forms.CharField(widget=forms.Textarea, required=False)
        profile_picture_retail = forms.ImageField(required=False)
        company_name_wholesale = forms.CharField(max_length=255, required=False,
                                                 help_text="Required for Wholesaler role")
        gst_number = forms.CharField(max_length=50, required=False)
        department = forms.CharField(max_length=100, required=False)
        purchase_capacity = forms.IntegerField(required=False, help_text="Monthly purchase capacity")
        profile_picture_wholesale = forms.ImageField(required=False)
        company_name_supplier = forms.CharField(max_length=255, required=False, help_text="Required for Supplier role")
        license_number = forms.CharField(max_length=100, required=False)
        is_verified = forms.BooleanField(required=False)
        profile_picture_supplier = forms.ImageField(required=False)

        class Meta:
            model = User
            fields = ['username', 'email', 'first_name', 'last_name', 'password']

        def clean(self):
            cleaned_data = super().clean()
            role = cleaned_data.get('role')

            if role == 'retailer':
                if not cleaned_data.get('age'):
                    self.add_error('age', 'Age is required for Retailer role')
            elif role == 'wholesaler':
                if not cleaned_data.get('company_name_wholesale'):
                    self.add_error('company_name_wholesale', 'Company name is required for Wholesaler role')
                if not cleaned_data.get('gst_number'):
                    self.add_error('gst_number', 'GST number is required for Wholesaler role')
                if not cleaned_data.get('department'):
                    self.add_error('department', 'Department is required for Wholesaler role')
                if not cleaned_data.get('purchase_capacity'):
                    self.add_error('purchase_capacity', 'Purchase capacity is required for Wholesaler role')
            elif role == 'supplier':
                if not cleaned_data.get('company_name_supplier'):
                    self.add_error('company_name_supplier', 'Company name is required for Supplier role')
                if not cleaned_data.get('license_number'):
                    self.add_error('license_number', 'License number is required for Supplier role')
            return cleaned_data

    form_class = Form

    def get_initial(self):
        initial = super().get_initial()
        user = self.get_object()

        # Set initial role
        if RetailProfile.objects.filter(user=user).exists():
            initial['role'] = 'retailer'
            retail_profile = RetailProfile.objects.get(user=user)
            initial['age'] = retail_profile.age
            initial['medical_needs'] = retail_profile.medical_needs
        elif WholesaleBuyerProfile.objects.filter(user=user).exists():
            initial['role'] = 'wholesaler'
            wholesale_profile = WholesaleBuyerProfile.objects.get(user=user)
            initial['company_name_wholesale'] = wholesale_profile.company_name
            initial['gst_number'] = wholesale_profile.gst_number
            initial['department'] = wholesale_profile.department
            initial['purchase_capacity'] = wholesale_profile.purchase_capacity
        elif SupplierProfile.objects.filter(user=user).exists():
            initial['role'] = 'supplier'
            supplier_profile = SupplierProfile.objects.get(user=user)
            initial['company_name_supplier'] = supplier_profile.company_name
            initial['license_number'] = supplier_profile.license_number
            initial['is_verified'] = supplier_profile.is_verified
        else:
            initial['role'] = 'none'

        return initial

    def form_valid(self, form):
        with transaction.atomic():
            user = form.save(commit=False)
            if form.cleaned_data['password']:
                user.set_password(form.cleaned_data['password'])
            user.save()

            # Handle profile updates
            role = form.cleaned_data['role']

            # Delete existing profiles
            RetailProfile.objects.filter(user=user).delete()
            WholesaleBuyerProfile.objects.filter(user=user).delete()
            SupplierProfile.objects.filter(user=user).delete()

            # Create or update profile based on role
            if role == 'retailer':
                RetailProfile.objects.create(
                    user=user,
                    age=form.cleaned_data.get('age'),
                    medical_needs=form.cleaned_data.get('medical_needs'),
                    profile_picture=form.cleaned_data.get('profile_picture_retail')
                )
            elif role == 'wholesaler':
                WholesaleBuyerProfile.objects.create(
                    user=user,
                    company_name=form.cleaned_data.get('company_name_wholesale'),
                    gst_number=form.cleaned_data.get('gst_number'),
                    department=form.cleaned_data.get('department'),
                    purchase_capacity=form.cleaned_data.get('purchase_capacity'),
                    profile_picture=form.cleaned_data.get('profile_picture_wholesale')
                )
            elif role == 'supplier':
                SupplierProfile.objects.create(
                    user=user,
                    company_name=form.cleaned_data.get('company_name_supplier'),
                    license_number=form.cleaned_data.get('license_number'),
                    is_verified=form.cleaned_data.get('is_verified'),
                    profile_picture=form.cleaned_data.get('profile_picture_supplier')
                )

        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class UserDetailView(SupplierPermissionMixin, DetailView):
    model = User
    template_name = 'supplier/user_detail.html'
    context_object_name = 'user'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_object()

        # Add profile information to context
        context['retail_profile'] = RetailProfile.objects.filter(user=user).first()
        context['wholesale_profile'] = WholesaleBuyerProfile.objects.filter(user=user).first()
        context['supplier_profile'] = SupplierProfile.objects.filter(user=user).first()

        return context


@method_decorator(login_required, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class UserDeleteView(SupplierPermissionMixin, View):
    def post(self, request, pk):
        try:
            user = get_object_or_404(User, pk=pk)
            user.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class OrderListingView(SupplierPermissionMixin, View):
    def get(self, request):
        status_filter = request.GET.get('status')
        supplier = request.user

        # Filter order items for the current supplier and annotate item totals
        item_queryset = OrderItem.objects.filter(order_to=supplier).annotate(
            item_total=F('price') * F('quantity')
        )

        # Fetch orders where items belong to the current supplier
        orders = Order.objects.filter(
            items__order_to=supplier
        ).distinct().select_related('user', 'payment').prefetch_related(
            Prefetch('items', queryset=item_queryset, to_attr='filtered_items')
        )

        # Apply status filter if selected
        if status_filter:
            orders = orders.filter(status=status_filter)

        # Totals and phone mapping
        order_totals = {}
        order_phones = {}

        for order in orders:
            total = 0
            phone_number = "---"
            for item in order.filtered_items:
                total += float(item.item_total or 0)
                if item.phone_number and phone_number == "---":
                    phone_number = item.phone_number  # Get first valid phone
            order_totals[order.pk] = total
            order_phones[order.pk] = phone_number

        # Status counters
        total_orders = orders.count()
        completed_orders = orders.filter(status='completed').count()
        pending_orders = orders.filter(status='pending').count()
        cancelled_orders = orders.filter(status='cancelled').count()

        context = {
            'orders': orders,
            'order_totals': order_totals,  # key = order.pk, value = total price
            'order_phones': order_phones,  # key = order.pk, value = phone number
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'pending_orders': pending_orders,
            'cancelled_orders': cancelled_orders,
            'selected_status': status_filter or '',
        }

        logger.info(f"Supplier {supplier.id} viewed order listing with status filter: {status_filter}")
        return render(request, 'supplier/order-listing.html', context)


class OrderDetailsView(SupplierPermissionMixin, View):
    def get(self, request, order_id):
        supplier = request.user
        order = get_object_or_404(
            Order.objects.filter(items__order_to=supplier).distinct().select_related('user', 'payment').prefetch_related(
                Prefetch('items', queryset=OrderItem.objects.select_related('product', 'order_by', 'order_to').prefetch_related(
                    Prefetch('product__productimage_set', queryset=ProductImage.objects.filter(is_main=True), to_attr='main_image')
                ))
            ),
            order_id=order_id
        )

        # Calculate totals for supplier's order items
        order_items = order.items.filter(order_to=supplier)
        if not order_items.exists():
            logger.warning(f"Supplier {supplier.id} attempted to view order {order.id} with no relevant items")
            messages.error(request, "You do not have permission to view this order.")
            return redirect('supplier:order_listing')

        subtotal = order_items.aggregate(
            total=Sum(F('price') * F('quantity'))
        )['total'] or 0.0

        commission = order_items.aggregate(
            total=Sum((F('price') * F('product__commission_percentage') / 100) * F('quantity'))
        )['total'] or 0.0

        shipping_fee = float(order.shipping_fees) if order.shipping_fees else 0.0
        grand_total = float(subtotal) - float(commission) + shipping_fee

        context = {
            'order': order,
            'order_items': order_items,
            'subtotal': round(float(subtotal), 2),
            'total_commission': round(float(commission), 2),
            'shipping_fee': round(shipping_fee, 2),
            'grand_total': round(grand_total, 2),
            'user': order.user,
        }
        logger.info(f"Supplier {supplier.id} viewed details for order {order.order_id}")
        return render(request, 'supplier/order-details.html', context)


class OrderDeleteView(SupplierPermissionMixin, View):
    def post(self, request, order_id):
        supplier = request.user
        order = get_object_or_404(
            Order.objects.filter(items__order_to=supplier).distinct(),
            order_id=order_id
        )

        # Check if supplier has items in this order
        if not order.items.filter(order_to=supplier).exists():
            logger.warning(f"Supplier {supplier.id} attempted to delete order {order.id} with no relevant items")
            return JsonResponse({'success': False, 'error': 'You do not have permission to delete this order'}, status=403)

        # Soft delete by updating status to 'cancelled'
        order.status = 'cancelled'
        order.save()
        order.items.filter(order_to=supplier).update(status='cancelled')
        logger.info(f"Supplier {supplier.id} cancelled order {order.order_id}")
        return JsonResponse({'success': True})


class UserProfileView(SupplierPermissionMixin, View):
    def get(self, request):
        return render(request, 'supplier/user-profile.html')


class UserOverView(SupplierPermissionMixin, View):
    def get(self, request):
        return render(request, 'supplier/overview.html')


class AdminSettingView(SupplierPermissionMixin, View):
    def get(self, request):
        return render(request, 'supplier/settings.html')

    def post(self, request):
        if 'fname' in request.POST:
            fname = request.POST.get('fname')
            lname = request.POST.get('lname')
            email = request.POST.get('aemail')
           
            user = request.user
            user.first_name = fname
            user.last_name = lname
            user.email = email
            user.save()

            messages.success(request, "Profile updated successfully!")
            return redirect('supplier:profile_setting')

        elif 'currentpassword' in request.POST:
            current = request.POST.get('currentpassword')
            new = request.POST.get('newpassword')
            confirm = request.POST.get('confirmpassword')
            user = request.user

            if not check_password(current, user.password):
                messages.error(request, "Current password is incorrect.")
            elif new != confirm:
                messages.error(request, "New passwords do not match.")
            elif len(new) < 8:
                messages.error(request, "Password must be at least 8 characters.")
            else:
                user.set_password(new)
                user.save()
                update_session_auth_hash(request, user) 
                messages.success(request, "Password updated successfully.")

            return redirect('supplier:profile_setting')


class CompanyDetailsView(LoginRequiredMixin, SupplierPermissionMixin, View):
    template = "supplier/company_details.html"

    def get(self, request, *args, **kwargd):
        user = request.user

        profile = SupplierProfile.objects.get(user=user)

        print('--- Profile ---', profile)
        print('--- Profile company name  ---', profile.company_name)
        print('--- Profile license number  ---', profile.license_number)
        context = {
            "company_name": profile.company_name,
            "license_number": profile.license_number
        }

        return render(request, self.template, context)

    def post(self, request, *args, **kwargs):
        try:
            company_name = request.POST.get('company_name')
            license_number = request.POST.get('license_number')

            print("--- company name --- ", company_name)
            print("--- license number --- ", license_number)

            user = request.user

            # Get or create the SupplierProfile for the user
            profile, created = SupplierProfile.objects.get_or_create(user=user)

            profile.company_name = company_name
            profile.license_number = license_number
            profile.save()

            messages.success(
                request,
                "Details created successfully" if created else "Details updated successfully"
            )
            return redirect("supplier:company_details")

        except Exception as e:
            print("Exception in saving profile:", e)
            messages.error(request, "Failed to update company details. Please try again.")
            return redirect("supplier:company_details")


class WishlistProductView(LoginRequiredMixin, SupplierPermissionMixin, View):
    template = 'supplier/wishlist_product.html'

    def get(self, request, *args, **kwargs):

        wishlist = WishlistProduct.objects.all()

        context = {
            'wishlist_product': wishlist
        }

        return render(self.request, self.template, context)

    def post(self, request, *args, **kwargs):
        mode = self.request.POST.get('mode')
        product_id = self.request.POST.get('product_id')

        if mode == 'add-to-card':
            try:
                item = get_object_or_404(WishlistProduct, id=product_id)
                user = item.user
                product = item.product

                cart_item, created = CartProduct.objects.get_or_create(
                    user=user,
                    product=product,
                    defaults={'quantity': item.quantity, 'created_at': datetime.now()}
                )

                if not created:
                    # If already exists, update the quantity
                    cart_item.quantity += item.quantity
                    cart_item.save()

                item.delete()  # remove from wishlist

                messages.success(request, "Added to cart" if created else "Updated quantity in cart")
                return redirect('supplier:wishlist_products_list')

            except Exception as e:
                print("Exception as e ----", e)
                messages.error(request, "Failed to add to cart, please try again")
                return redirect('supplier:wishlist_products_list')

        if mode == 'remove-wishlist':
            try:
                item = get_object_or_404(WishlistProduct, id=product_id)
                item.delete()

                messages.success(request, "Removed from Wishlist")
                return redirect('supplier:wishlist_products_list')

            except Exception as e:
                messages.error(request, "Faild to remove, please try again")
                return redirect('supplier:wishlist_products_list')


class CartProductsView(LoginRequiredMixin, SupplierPermissionMixin, View):
    template = "supplier/cart_product.html"

    def get(self, request, *args, **kwargs):
        user = request.user
        try:
            products = CartProduct.objects.filter(user=user).order_by('-created_at')
            total = sum([p.get_total_price() for p in products])
            items_total = len(products)
            context = {
                'products': products,
                'cart_total': total,
                'items_total': items_total
            }
            return render(request, self.template, context)
        except Exception as e:
            print("Exception in CartProductsView:", e)
            return HttpResponseServerError("Something went wrong loading your cart.")


@method_decorator(csrf_exempt, name='dispatch')
class UpdateCartQuantityView(LoginRequiredMixin, SupplierPermissionMixin, View):
    def post(self, request):
        data = json.loads(request.body)
        product_id = data.get("product_id")
        quantity = int(data.get("quantity", 1))

        cart_item = CartProduct.objects.get(id=product_id, user=request.user)
        cart_item.quantity = quantity
        cart_item.save()

        # Calculate updated values
        item_total = round(cart_item.get_total_price(), 2)
        cart_total = sum([item.get_total_price() for item in CartProduct.objects.filter(user=request.user)])

        return JsonResponse({
            "item_total": f"{item_total:.2f}",
            "cart_total": f"{cart_total:.2f}"
        })


@method_decorator(csrf_exempt, name='dispatch')
class DeleteCartItemView(LoginRequiredMixin, SupplierPermissionMixin, View):
    def post(self, request):
        data = json.loads(request.body)
        product_id = data.get("product_id")

        try:
            cart_item = CartProduct.objects.get(id=product_id, user=request.user)
            cart_item.delete()

            cart_total = sum([item.get_total_price() for item in CartProduct.objects.filter(user=request.user)])

            return JsonResponse({
                "success": True,
                "cart_total": f"{cart_total:.2f}"
            })

        except CartProduct.DoesNotExist:
            return JsonResponse({"success": False, "message": "Item not found"}, status=404)


class MarkNotificationReadView(SupplierPermissionMixin, View):
    def post(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk)
            notif.is_read = True
            notif.save()
            return JsonResponse({'success': True})
        except Notification.DoesNotExist:
            return JsonResponse({'error': 'Notification not found'}, status=404)


class ClearAllNotificationsView(LoginRequiredMixin, SupplierPermissionMixin, View):
    def post(self, request, *args, **kwargs):
        if request.user.is_superuser:
            Notification.objects.all().delete()
            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({'status': 'unauthorized'}, status=403)


class MarkNotificationReadView(SupplierPermissionMixin, View):
    def post(self, request, pk):
        notif = Notification.objects.get(pk=pk)
        notif.is_read = True
        notif.save()
        return JsonResponse({
            "title": notif.title,
            "message": notif.message,
            "created_at": localtime(notif.created_at).strftime('%d %b %Y, %I:%M %p')
        })


class LogoutView(SupplierPermissionMixin, View):
    def get(self, request):
        logout(request)
        return redirect('supplier:admin_login') 


class RFQListView(LoginRequiredMixin, SupplierPermissionMixin, ListView):
    template_name = 'supplier/rfq_list.html'
    context_object_name = 'rfqs'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return RFQRequest.objects.all()
        elif hasattr(user, 'supplierprofile'):
            return RFQRequest.objects.filter(product__created_by=user)
        return RFQRequest.objects.none()


from django.utils import timezone
from django.contrib import messages
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import UpdateView, ListView

from .forms import SupplierRFQQuotationForm


class RFQListView(LoginRequiredMixin, SupplierPermissionMixin, ListView):
    template_name = 'supplier/rfq_list.html'
    context_object_name = 'rfqs'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return RFQRequest.objects.all()
        elif hasattr(user, 'supplierprofile'):
            return RFQRequest.objects.filter(product__created_by=user)
        return RFQRequest.objects.none()


class SupplierQuotationUpdateView(LoginRequiredMixin, SupplierPermissionMixin, UpdateView):
    model = RFQRequest
    form_class = SupplierRFQQuotationForm
    template_name = 'supplier/rfq_quotation_form.html'
    success_url = '/rfq/'

    def form_valid(self, form):
        rfq_instance = form.save(commit=False)
        actual_price = rfq_instance.product.price
        quoted_price = form.cleaned_data.get('quoted_price')
        quote_delivery_date = form.cleaned_data.get('quote_delivery_date')

        # ✅ Validate future delivery date
        if quote_delivery_date and quote_delivery_date < timezone.now().date():
            form.add_error(
                'quote_delivery_date',
                'Delivery date must be in the future'
            )
            return self.form_invalid(form)

        # ✅ Validate quoted price
        if quoted_price > actual_price:
            form.add_error(
                'quoted_price',
                'Quoted price cannot be greater than actual price'
            )
            return self.form_invalid(form)

        # ✅ Set additional fields
        rfq_instance.quoted_by = self.request.user
        rfq_instance.quote_sent_at = timezone.now()
        rfq_instance.status = 'quoted'
        rfq_instance.save()

        # ✅ Send quotation email
        self.send_quotation_email(rfq_instance)

        messages.success(
            self.request,
            "Quotation sent and email delivered to the user."
        )
        return redirect(self.success_url)

    def send_quotation_email(self, rfq):
        subject = f"Quotation for RFQ #{rfq.id} - {rfq.product.name}"
        recipient_email = rfq.requested_by.email
        context = {
            'rfq': rfq,
            'supplier': rfq.quoted_by,
        }

        message = render_to_string('supplier/snippets/rfq_quotation_sent.html', context)

        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email]
        )
        email.content_subtype = 'html'

        if rfq.quote_attached_file:
            email.attach_file(rfq.quote_attached_file.path)

        email.send(fail_silently=False)

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser


class BannerListView(LoginRequiredMixin, SupplierPermissionMixin, TemplateView):
    template_name = 'supplier/banner_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = BannerForm()
        context['banners'] = Banner.objects.all().order_by('order')
        return context


class BannerCreateView(LoginRequiredMixin, SupplierPermissionMixin, View):
    def get(self, request):
        form = BannerForm()
        return render(request, 'supplier/banner_upload.html', {'form': form})

    def post(self, request):
        form = BannerForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('supplier:banner_list')
        return render(request, 'supplier/banner_upload.html', {'form': form})


class BannerUpdateView(LoginRequiredMixin, SupplierPermissionMixin, View):
    def get(self, request, pk):
        banner = get_object_or_404(Banner, pk=pk)
        form = BannerForm(instance=banner)
        return render(request, 'supplier/banner_edit.html', {'form': form, 'object': banner})

    def post(self, request, pk):
        banner = get_object_or_404(Banner, pk=pk)
        form = BannerForm(request.POST, request.FILES, instance=banner)
        if form.is_valid():
            form.save()
            return redirect('supplier:banner_list')
        return render(request, 'supplier/view_product.html', {'form': form, 'object': banner})
    

class TransactionView(TemplateView):
    template_name = 'supplier/transaction.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # All payments
        payments = Payment.objects.all()

        # Paid Money
        paid_money = payments.filter(paid=True).aggregate(total=Sum('amount'))['total'] or 0

        # Unpaid Money
        unpaid_money = payments.filter(paid=False).aggregate(total=Sum('amount'))['total'] or 0

        # Cash Money (COD only)
        cash_money = payments.filter(payment_method="cod").aggregate(total=Sum('amount'))['total'] or 0

        # Pass to template
        context['total_orders'] = paid_money
        context['pending_orders'] = unpaid_money
        context['cash_money'] = cash_money
        context['orders'] = payments

        return context
    

class MostViewedProductsView(View):
    def get(self, request):
        # Prefetch main images (or first image if no main exists)
        products = Product.objects.annotate(
            delivered_count=Count(
                'orderitem',
                filter=Q(orderitem__status='delivered'),
                distinct=True
            ),
            review_count=Count(
                'reviews',
                distinct=True
            )
        ).prefetch_related(
            Prefetch(
                'images',
                queryset=ProductImage.objects.order_by('-is_main', '-created_at'),
                to_attr='prefetched_images'
            )
        ).order_by('-delivered_count')

        # Attach a display image to each product
        for product in products:
            if hasattr(product, 'prefetched_images') and product.prefetched_images:
                main_images = [img for img in product.prefetched_images if img.is_main]
                product.display_image = main_images[0] if main_images else product.prefetched_images[0]
            else:
                product.display_image = None

        # All payments
        payments = Payment.objects.all()

        # Prepare context dictionary
        context = {}

        # Paid Money
        context['total_orders'] = payments.filter(paid=True).aggregate(total=Sum('amount'))['total'] or 0

        # Unpaid Money
        context['pending_orders'] = payments.filter(paid=False).aggregate(total=Sum('amount'))['total'] or 0

        # Cash Money (COD only)
        context['cash_money'] = payments.filter(payment_method="cod").aggregate(total=Sum('amount'))['total'] or 0

        # Pass products and orders to template
        context['products'] = products
        context['orders'] = payments

        return render(request, 'supplier/view_product.html', context)


class QuestionView(TemplateView):
    template_name = 'supplier/question.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['questions'] = Question.objects.select_related('user').order_by('-created_at')
        return context

    def post(self, request, *args, **kwargs):
        question_id = request.POST.get('question_id')
        reply_text = request.POST.get('reply_text')
        action_type = request.POST.get('action_type')

        if action_type == "reply":
            question = get_object_or_404(Question, id=question_id)
            question.reply = reply_text
            question.replied_at = timezone.now()
            question.save()
            messages.success(request, "Reply sent successfully.")

        elif action_type == "delete":
            question = get_object_or_404(Question, id=question_id)
            question.delete()
            messages.success(request, "Question deleted successfully.")

        return redirect('supplier:question_list')


class RatingView(TemplateView):
    template_name = "supplier/rating.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        products = (
            Product.objects
            .annotate(
                avg_rating=Avg('reviews__rating'),
                review_count=Coalesce(
                    Count(
                        'reviews',
                        filter=Q(reviews__rating__isnull=False) & ~Q(reviews__review="") 
                    ),
                    Value(0)
                )
            )
            .filter(avg_rating__isnull=False)
            .order_by('-avg_rating')
        )

        context['products'] = products
        return context
        context = {'products': products}
        return render(request, 'supplier/view_product.html', context)
    

class SupplierReturnsView(LoginRequiredMixin, TemplateView):
    template_name = 'supplier/returns.html'
    login_url = 'dashboard:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if not (user.is_superuser or (hasattr(user, 'userprofile') and user.userprofile.is_supplier)):
            raise PermissionDenied("You are not authorized to access this page.")

        if user.is_superuser:
            qs = Return.objects.all()
        else:
            qs = Return.objects.filter(
                order_item__product__brand__supplier=user
            )

        qs = qs.select_related(
            'order_item__product',
            'client'
        ).order_by('-request_date')

        context['returns'] = qs
        context['count_all'] = qs.count()
        context['count_approved'] = qs.filter(return_status='approved').count()
        context['count_pending'] = qs.filter(return_status='pending').count()
        context['count_rejected'] = qs.filter(return_status='rejected').count()

        return context

    def post(self, request, return_serial):
        user = request.user
        if user.is_superuser:
            return_request = get_object_or_404(Return, return_serial=return_serial)
        else:
            return_request = get_object_or_404(
                Return,
                return_serial=return_serial,
                order_item__product__brand__supplier=user
            )

        new_status = request.POST.get('return_status')

        if new_status in dict(Return.RETURN_STATUS_CHOICES):
            return_request.return_status = new_status
            return_request.save()
            messages.success(
                request,
                f"Return {return_request.return_serial} status updated to {return_request.get_return_status_display()}."
            )
        else:
            messages.error(request, "Invalid status selected.")

        return redirect('supplier:supplier_returns')