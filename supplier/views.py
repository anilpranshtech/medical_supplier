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
from superuser.mixins import SuperuserRequiredMixin
from superuser.refunds import process_refund
from superuser.utils import send_refund_notification
from supplier.forms import *
from supplier.models import *
# from dashboard.mixins import SupplierPermissionMixin
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
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.timezone import localtime
from django.db.models.functions import Coalesce, TruncDay, Concat
from django.db.models import Sum, F, DecimalField, Prefetch
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg, Count, Q, Value
from calendar import monthrange
import logging
from .mixins import OnboardingRequiredMixin
from .forms import SupplierRFQQuotationForm
from django.core.paginator import Paginator
from decimal import Decimal 
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from dashboard.forms import ContactForm 
from utils.logs import (
    user_update_activity,
    user_password_change_activity,
    user_failed_activity,
    user_log_activity,
    user_update_activity,
    user_failed_activity,
    user_refund_activity
)   


logger = logging.getLogger(__name__)


class HomeView(LoginRequiredMixin,OnboardingRequiredMixin, View):
    login_url = 'supplier:admin_login'

    def get(self, request):
        supplier = request.user

        supplier_order_items = OrderItem.objects.filter(order_to=supplier).select_related(
            'order', 'order_by', 'order_to', 'product__category'
        )
        orders = Order.objects.filter(items__order_to=supplier).distinct().select_related('user', 'payment')

        total_orders = orders.count()
        subtotal = supplier_order_items.annotate(
            product_total=F('price') * F('quantity')
        ).aggregate(
            total=Coalesce(Sum('product_total'), 0, output_field=DecimalField())
        )['total']
        
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


class ProductsView(LoginRequiredMixin,OnboardingRequiredMixin, View):
    template_name = 'supplier/products.html'
    paginate_by = 15  

    def get(self, request):
        user = request.user
        products = Product.objects.filter(created_by=user)

        # Get filter parameters
        sort_by = request.GET.get('sort_by', 'desc_created')
        search_by = request.GET.get('search_by', '')
        product_status = request.GET.get('product_status', 'all')
        account_type = request.GET.get('account_type', 'all')
        created_date = request.GET.get('created_date', '')

        # Apply search filter
        if search_by:
            products = products.filter(
                Q(name__icontains=search_by) |
                Q(category__name__icontains=search_by) |
                Q(sub_category__name__icontains=search_by) |
                Q(last_category__name__icontains=search_by)
            )

        # Apply product status filter
        if product_status != 'all':
            if product_status == 'published':
                products = products.filter(is_active=True)
            elif product_status == 'inactive':
                products = products.filter(is_active=False)

        # Apply category filter
        if account_type != 'all':
            products = products.filter(category__name=account_type)

        # Apply date range filter
        if created_date:
            try:
                if ' - ' in created_date:
                    start_date_str, end_date_str = created_date.split(' - ')
                    start_date = datetime.strptime(start_date_str, '%m/%d/%Y')
                    end_date = datetime.strptime(end_date_str, '%m/%d/%Y')
                    products = products.filter(
                        created_at__date__gte=start_date,
                        created_at__date__lte=end_date
                    )
                else:
                    single_date = datetime.strptime(created_date, '%m/%d/%Y')
                    products = products.filter(created_at__date=single_date)
            except ValueError:
                pass  

        # Apply sorting
        if sort_by == 'asc_created':
            products = products.order_by('created_at')
        else:
            products = products.order_by('-created_at')

        # Attach image URLs to products
        for product in products:
            image = ProductImage.objects.filter(product=product).first()
            product.image_url = image.image.url if image else '/static/supplier/media/stock/ecommerce/placeholder.png'

        # Pagination 
        paginator = Paginator(products, self.paginate_by)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        categories = ProductCategory.objects.all()

        return render(request, self.template_name, {
            'products': page_obj,     
            'page_obj': page_obj,     
            'category': categories
        })


class AddproductsView(LoginRequiredMixin,OnboardingRequiredMixin, View):
    template = 'supplier/add-product.html'

    def dispatch(self, request, *args, **kwargs):
        profile = SupplierProfile.objects.get(user=request.user)
        if not profile.selling_categories.exists():
            messages.warning(request, "Please select your selling categories before adding a product.")
            return redirect("supplier:selling_categories")  
        return super().dispatch(request, *args, **kwargs)

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
        base_price = self._parse_float(data.get('base_price'), min_value=1, max_value=999999)
        discount_price = self._parse_float(data.get('discount_price'))
        offer_percentage = self._parse_float(data.get('offer_percentage'), min_value=0, max_value=100)
        fixed_price = self._parse_float(data.get('discounted_price'), min_value=0)
        stock_quantity = self._parse_int(data.get('product_quantity'), min_value=0)
        commission = self._parse_float(data.get('commission_percentage'), min_value=0, max_value=100)
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
        discount_option = data.get('discount_option')
        cash_on_delivery = data.get('cash_on_delivery') == 'on'

        # Debugging: Log form data
        print("Form POST data:", dict(data))

        def _is_event_category(self, category):
            event_keywords = ['conference', 'event', 'webinar']
            if category and category.name:
                return category.name.lower() in event_keywords
            return False

        # Validate required fields
        if not name:
            messages.error(request, "Product name is required.")
            return self._render_form_with_context(request, data)

        if not base_price:
            messages.error(request, "Base price is required and must be between 1 and 999999.")
            return self._render_form_with_context(request, data)

        if discount_option == '2' and offer_percentage is None:
            messages.error(request, "Please select a valid discount percentage.")
            return self._render_form_with_context(request, data)

        if discount_option == '3' and fixed_price is None:
            messages.error(request, "Please enter a valid fixed discounted price.")
            return self._render_form_with_context(request, data)

        if offer_start and offer_end and offer_end < offer_start:
            messages.warning(request, "Offer end date cannot be before start date.")
            return self._render_form_with_context(request, data)

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
            price = base_price
            final_offer_percentage = 0
            final_discount_price = None

            if discount_option == '2' and offer_percentage is not None:
                final_offer_percentage = offer_percentage
                final_discount_price = discount_price if discount_price is not None else base_price * (1 - offer_percentage / 100)
            elif discount_option == '3' and fixed_price is not None:
         
                price = fixed_price
                final_discount_price = fixed_price


            print(f"Saving product with price: {price}, offer_percentage: {final_offer_percentage}, discount_price: {final_discount_price}") 

            product = Product.objects.create(
                name=name,
                description=description or '',
                price=price,
                discount_price=final_discount_price,
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
                offer_percentage=final_offer_percentage,
                offer_start=offer_start,
                offer_end=offer_end,
                offer_active=offer_active,
                ask_admin_to_publish=ask_admin_to_publish,
                is_active=(data.get('is_active') == 'True'),
                show_add_to_cart=show_add_to_cart,
                cash_on_delivery=cash_on_delivery,
                show_rfq=show_rfq,
                Both=both_selected,
                created_by=request.user
            )

            category_obj = self._get_object(ProductCategory, data.get('category'))
            if _is_event_category(self, category_obj):
                event = Event.objects.create(
                    conference_link=data.get('registration_link') or None,
                    speaker_name=data.get('webinar_name') or None,
                    conference_at=self._parse_date(data.get('webinar_date')) or None,
                    duration=self._parse_duration(data.get('webinar_duration')) or None,
                    venue=data.get('webinar_venue') or None,
                )
                product.event = event
                product.save()

            main_image = files.get('main_image')
            if main_image:
                ProductImage.objects.create(product=product, image=main_image, is_main=True)

            gallery_images = files.getlist('gallery_images')
            for img in gallery_images:
                ProductImage.objects.create(product=product, image=img, is_main=False)
                
            user_log_activity(
            user=request.user,
            actions=UserActivityLog.ActionType.CREATED,
            description=f"Product created: {product.name} (ID: {product.id})"
            )
            messages.success(request, "Product added successfully.")
            return redirect('supplier:products_list')
        except IntegrityError as e:
            user_failed_activity(
             user=request.user,
             description=f"Failed to create product (IntegrityError): {e}"
            )
            messages.error(request, f"Integrity error: {e}")
        except Exception as e:
            user_failed_activity(
             user=request.user,
             description=f"Failed to create product: {e}"
            )
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

    def _parse_duration(self, val):
        if not val:
            return None
        try:
            if ":" in val:
                parts = list(map(int, val.split(":")))
                while len(parts) < 3:
                    parts.append(0)
                h, m, s = parts
                return timedelta(hours=h, minutes=m, seconds=s)
            else:
                return timedelta(hours=int(val))
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
        if not val:
            return None
        return parse_datetime(val) or parse_date(val)

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
            'base_price': data.get('base_price', ''),
            'discount_price': data.get('discount_price', ''),
            'offer_percentage': data.get('offer_percentage', ''),
            'discounted_price': data.get('discounted_price', ''),
            **data.dict()
        })

    
class EditproductsView(LoginRequiredMixin, View):
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

        # Determine discount_option
        if product.discount_price is None and (product.offer_percentage is None or product.offer_percentage == 0):
            discount_option = '1'
        elif product.offer_percentage and product.offer_percentage > 0:
            discount_option = '2'
        else:
            discount_option = '3'

        context = {
            'pk': pk,
            'product': product,
            'product_name': product.name,
            'product_description': product.description,
            'base_price': product.price,
            'discount_price': product.discount_price or '',
            'discount_option': discount_option,
            'offer_percentage': product.offer_percentage or 0,
            'discounted_price': product.discount_price or '',
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
            'offer_start': product.offer_start.strftime('%Y-%m-%d') if product.offer_start else '',
            'offer_end': product.offer_end.strftime('%Y-%m-%d') if product.offer_end else '',
            'offer_active': product.offer_active,
            'ask_admin_to_publish': product.ask_admin_to_publish,
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
            'cash_on_delivery': product.cash_on_delivery,
        }
        return render(request, self.template, context)

    def post(self, request, pk):
        try:
            product = get_object_or_404(Product, pk=pk)
            data = request.POST
            files = request.FILES

            # Debug: Log all form data
            print("Form POST data:", dict(data))

            # Check if product is in a webinar category
            category_id = data.get('category')
            is_webinar = False
            if category_id:
                category = ProductCategory.objects.filter(pk=category_id).first()
                is_webinar = category and category.name in ['Webinar', 'Conference', 'Event']

            # Basic info
            product.name = data.get('product_name', '')
            product.description = data.get('product_description', '')
            base_price = self._parse_decimal(data.get('base_price'), min_value=Decimal('0.00') if is_webinar else Decimal('1.00'), max_value=Decimal('999999.00'))
            product.stock_quantity = self._parse_int(data.get('product_quantity'), min_value=0)
            product.product_from = data.get('product_from', '')
            product.selling_countries = data.get('selling_countries', '')
            product.warranty = data.get('warranty', 'none')
            product.condition = data.get('condition', 'new')
            product.weight = self._parse_decimal(data.get('weight'), min_value=0)
            product.weight_unit = data.get('weight_unit', 'gm')
            product.delivery_time = self._parse_int(data.get('delivery_time'), min_value=0)
            product.commission_percentage = self._parse_decimal(data.get('commission_percentage'), min_value=0, max_value=100)
            product.barcode = data.get('barcode', '')
            product.keywords = data.get('keywords', '')
            product.supplier_sku = data.get('supplier_sku', '')
            product.pcs_per_unit = self._parse_int(data.get('pcs_per_unit'), min_value=1)
            product.min_order_qty = self._parse_int(data.get('min_order_qty'), min_value=1)
            product.low_stock_alert = self._parse_int(data.get('low_stock_alert'), min_value=0)
            product.expiration_days = self._parse_int(data.get('expiration_days'), min_value=0)
            product.tag = data.get('tag', 'none')
            product.is_active = data.get('is_active') == 'True'
            product.cash_on_delivery = data.get('cash_on_delivery') == 'on'

            # Returnable toggle
            product.is_returnable = data.get('is_returnable') == 'on'
            product.return_time_limit = self._parse_int(data.get('return_time_limit'), min_value=0) if product.is_returnable else 0

            # Dates
            product.manufacture_date = self._parse_date(data.get('manufacture_date'))
            product.expiry_date = self._parse_date(data.get('expiry_date'))
            product.offer_start = self._parse_date(data.get('offer_start')) if data.get('offer_start') else None
            product.offer_end = self._parse_date(data.get('offer_end')) if data.get('offer_end') else None

            # Offer status and approval request
            product.offer_active = data.get('offer_active') == 'on' if request.user.is_superuser else False
            product.ask_admin_to_publish = data.get('ask_admin_to_publish') == 'on'

            # Discount handling
            discount_option = data.get('discount_option')
            # Handle multiple offer_percentage values
            offer_percentage_values = data.getlist('offer_percentage')
            offer_percentage = None
            for val in offer_percentage_values:
                parsed = self._parse_decimal(val, min_value=Decimal('0.00'), max_value=Decimal('100.00'))
                if parsed is not None and parsed > 0:
                    offer_percentage = parsed
                    break
            if offer_percentage is None:
                offer_percentage = Decimal('0.00')

            discounted_price = self._parse_decimal(data.get('discounted_price'), min_value=Decimal('0.00'))
            discount_price = self._parse_decimal(data.get('discount_price'), min_value=Decimal('0.00'))

            # Debug: Log pricing inputs
            print(f"base_price: {base_price}, discount_option: {discount_option}, offer_percentage: {offer_percentage}, discounted_price: {discounted_price}, discount_price: {discount_price}")

            # Validate required fields
            if not is_webinar and not base_price:
                messages.error(request, "Base price is required and must be between 1 and 999999 for non-webinar products.")
                return self._render_form_with_context(request, data, product)

            if discount_option == '2' and (offer_percentage is None or offer_percentage <= 0):
                messages.error(request, "Please select a discount percentage greater than 0 for percentage discounts.")
                return self._render_form_with_context(request, data, product)

            if discount_option == '3' and (discounted_price is None or discounted_price <= 0):
                messages.error(request, "Please enter a valid fixed discounted price (greater than 0).")
                return self._render_form_with_context(request, data, product)

            # Handle discount logic
            if is_webinar:
                product.price = base_price if base_price is not None else Decimal('0.00')
                product.offer_percentage = 0
                product.discount_price = None
            else:
                if discount_option == '1':
                    product.price = base_price
                    product.offer_percentage = 0
                    product.discount_price = None
                elif discount_option == '2':
                    product.price = base_price
                    product.offer_percentage = offer_percentage or 0
                    product.discount_price = discount_price or (base_price * (1 - product.offer_percentage / 100))
                elif discount_option == '3':
                    product.price = base_price  # Save base_price to product.price
                    product.offer_percentage = 0
                    product.discount_price = discounted_price  # Save discounted_price to product.discount_price

            # Debug: Log values before saving
            print(f"Before save - product.price: {product.price}, product.offer_percentage: {product.offer_percentage}, product.discount_price: {product.discount_price}")

            # Category
            category_id = data.get('category')
            if category_id:
                product.category = ProductCategory.objects.filter(pk=category_id).first()
            sub_category_id = data.get('sub_category')
            if sub_category_id:
                product.sub_category = ProductSubCategory.objects.filter(pk=sub_category_id).first()
            last_category_id = data.get('last_category')
            if last_category_id:
                product.last_category = ProductLastCategory.objects.filter(pk=last_category_id).first()

            # Brand
            brand_name = data.get('brand')
            if brand_name:
                brand_obj, _ = Brand.objects.get_or_create(name=brand_name, defaults={'supplier': request.user})
                product.brand = brand_obj

            # Images
            if 'main_image' in files:
                ProductImage.objects.filter(product=product, is_main=True).delete()
                ProductImage.objects.create(product=product, image=files['main_image'], is_main=True)

            if 'gallery_images' in files:
                for image in files.getlist('gallery_images'):
                    ProductImage.objects.create(product=product, image=image, is_main=False)

            # Brochure
            if 'brochure' in files:
                product.brochure = files['brochure']

            product.save()

            # Debug: Verify saved values
            saved_product = Product.objects.get(pk=pk)
            print(f"After save - product.price: {saved_product.price}, product.offer_percentage: {saved_product.offer_percentage}, product.discount_price: {saved_product.discount_price}")
            user_update_activity(
                 user=request.user,
                 description=f"Product updated: {product.name} (ID: {product.id})"
            )

            messages.success(request, 'Product updated successfully!')
            return redirect('supplier:products_list')

        except Exception as e:
            user_failed_activity(
                  user=request.user,
                 description=f"Failed to update product ID {pk}: {e}"
            )
            print('Exception in edit product:', e)
            messages.error(request, f'Issue in Product update: {e}')
            return self._render_form_with_context(request, data, product)

    def _parse_decimal(self, val, min_value=None, max_value=None):
        if not val:
            return None
        try:
            d = Decimal(str(val))
            if (min_value is not None and d < min_value) or (max_value is not None and d > max_value):
                return None
            return d
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
        if not val:
            return None
        try:
            return parse_date(val)
        except:
            return None

    def _render_form_with_context(self, request, data, product):
        categories = ProductCategory.objects.all()
        subcategories = ProductSubCategory.objects.filter(category=product.category) if product.category else ProductSubCategory.objects.none()
        lastcategories = ProductLastCategory.objects.filter(sub_category=product.sub_category) if product.sub_category else ProductLastCategory.objects.none()
        product_images = ProductImage.objects.filter(product=product)
        main_image = product_images.filter(is_main=True).first()
        gallery_images = product_images.filter(is_main=False)
        brochure_url = product.brochure.url if product.brochure else None

        return render(request, self.template, {
            'pk': product.id,
            'product': product,
            'product_name': data.get('product_name', product.name),
            'product_description': data.get('product_description', product.description),
            'base_price': data.get('base_price', product.price),
            'discount_price': data.get('discount_price', product.discount_price or ''),
            'discount_option': data.get('discount_option', '1'),
            'offer_percentage': data.get('offer_percentage', product.offer_percentage or 0),
            'discounted_price': data.get('discounted_price', product.discount_price or ''),
            'product_quantity': data.get('product_quantity', product.stock_quantity),
            'product_from': data.get('product_from', product.product_from),
            'selling_countries': data.get('selling_countries', product.selling_countries or ''),
            'warranty': data.get('warranty', product.warranty),
            'condition': data.get('condition', product.condition),
            'is_returnable': data.get('is_returnable') == 'on',
            'return_time_limit': data.get('return_time_limit', product.return_time_limit),
            'manufacture_date': data.get('manufacture_date', product.manufacture_date.strftime('%Y-%m-%d') if product.manufacture_date else ''),
            'expiry_date': data.get('expiry_date', product.expiry_date.strftime('%Y-%m-%d') if product.expiry_date else ''),
            'weight': data.get('weight', product.weight),
            'weight_unit': data.get('weight_unit', product.weight_unit),
            'delivery_time': data.get('delivery_time', product.delivery_time),
            'commission_percentage': data.get('commission_percentage', product.commission_percentage),
            'barcode': data.get('barcode', product.barcode),
            'keywords': data.get('keywords', product.keywords),
            'supplier_sku': data.get('supplier_sku', product.supplier_sku),
            'pcs_per_unit': data.get('pcs_per_unit', product.pcs_per_unit),
            'min_order_qty': data.get('min_order_qty', product.min_order_qty),
            'low_stock_alert': data.get('low_stock_alert', product.low_stock_alert),
            'expiration_days': data.get('expiration_days', product.expiration_days),
            'tag': data.get('tag', product.tag),
            'offer_start': data.get('offer_start', product.offer_start.strftime('%Y-%m-%d') if product.offer_start else ''),
            'offer_end': data.get('offer_end', product.offer_end.strftime('%Y-%m-%d') if product.offer_end else ''),
            'offer_active': data.get('offer_active') == 'on',
            'ask_admin_to_publish': data.get('ask_admin_to_publish') == 'on',
            'brand': data.get('brand', product.brand.name if product.brand else ''),
            'categories': categories,
            'category_id': data.get('category', product.category.id if product.category else None),
            'selected_sub_category': data.get('sub_category', product.sub_category.id if product.sub_category else None),
            'selected_sub_category_name': product.sub_category.name if product.sub_category else '',
            'selected_last_category': data.get('last_category', product.last_category.id if product.last_category else None),
            'selected_last_category_name': product.last_category.name if product.last_category else '',
            'main_image_url': main_image.image.url if main_image else None,
            'gallery_images': gallery_images,
            'brochure_url': brochure_url,
            'subcategories': subcategories,
            'lastcategories': lastcategories,
        })


class DeleteProductImageView(LoginRequiredMixin, View):
    def post(self, request, pk):
        image = get_object_or_404(ProductImage, pk=pk)
        product_id = image.product.id
        user_log_activity(
        user=request.user,
        actions=UserActivityLog.ActionType.DELETED,
        description=f"Deleted product image (Image ID: {pk}) for Product ID {product_id}"
        )
        image.delete()
        return redirect('supplier:edit_product', pk=product_id)

    def get(self, request, pk):
        return self.post(request, pk)


class DeleteProductView(LoginRequiredMixin, View):
    def post(self, request, pk):
        try:
            product = get_object_or_404(Product, pk=pk)
            user_log_activity(
            user=request.user,
            actions=UserActivityLog.ActionType.DELETED,
            description=f"Deleted product: {product.name} (ID: {product.id})"
            )
            product.delete()
            messages.success(request, "Product deleted successfully")
            return JsonResponse({'success': True})
        except Exception as e:
            user_failed_activity(
            user=request.user,
            description=f"Failed to delete product ID {pk}: {e}"
            )
            messages.error(request, "Faild to delect product.")
            return JsonResponse({'success': False})


class CreateProductCategoryView(View):
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
 

class CreateProductSubCategoryView( View):
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

    
class CreateProductLastCategoryView( View):
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
    

class GetSubcategoriesView(View):
    def get(self, request, *args, **kwargs):
        category_id = request.GET.get('category_id')
        if category_id:
            subcats = ProductSubCategory.objects.filter(category_id=category_id).values('id', 'name')
            return JsonResponse(list(subcats), safe=False)
        return JsonResponse([], safe=False)


class GetLastCategoriesView( View):
    def get(self, request, *args, **kwargs):
        sub_id = request.GET.get('sub_id')
        if sub_id:
            lastcats = ProductLastCategory.objects.filter(sub_category_id=sub_id).values('id', 'name')
            return JsonResponse(list(lastcats), safe=False)
        return JsonResponse([], safe=False)


class AdminloginView( View):
    def get(self, request):
        return render(request, 'dashboard/login.html')

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
        return render(request, 'dashboard/login.html')


@method_decorator(login_required, name='dispatch')
class UserListView(OnboardingRequiredMixin, ListView):
    model = User
    template_name = 'supplier/user_list.html'
    context_object_name = 'users'
    ordering = ['-date_joined']
    paginate_by = 12   

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
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query)
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
class UserAddView( CreateView):
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
class UserEditView( UpdateView):
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
class UserDetailView( DetailView):
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
class UserDeleteView(View):
    def post(self, request, pk):
        try:
            user = get_object_or_404(User, pk=pk)
            user.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class OrderListingView( OnboardingRequiredMixin,View):
    def get(self, request):
        status_filter = request.GET.get('status')
        supplier = request.user

        item_queryset = OrderItem.objects.filter(order_to=supplier).annotate(
            item_total=F('price') * F('quantity')
        )

   
        orders = Order.objects.filter(
            items__order_to=supplier
        ).distinct().select_related('user', 'payment').prefetch_related(
            Prefetch('items', queryset=item_queryset, to_attr='filtered_items')
        )

     
        if status_filter:
            orders = orders.filter(status=status_filter)

     
        order_totals = {}
        order_phones = {}

        for order in orders:
            total = 0
            phone_number = "---"
            for item in order.filtered_items:
                total += float(item.item_total or 0)
                if item.phone_number and phone_number == "---":
                    phone_number = item.phone_number  
            order_totals[order.pk] = total
            order_phones[order.pk] = phone_number

      
        total_orders = orders.count()
        completed_orders = orders.filter(status='completed').count()
        pending_orders = orders.filter(status='pending').count()
        cancelled_orders = orders.filter(status='cancelled').count()


        paginator = Paginator(orders, 15)  
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context = {
            'orders': page_obj,            
            'order_totals': order_totals,  
            'order_phones': order_phones,    
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'pending_orders': pending_orders,
            'cancelled_orders': cancelled_orders,
            'selected_status': status_filter or '',
            'page_obj': page_obj,           
            'paginator': paginator,
            'is_paginated': page_obj.has_other_pages(),
        }

        logger.info(f"Supplier {supplier.id} viewed order listing with status filter: {status_filter}")
        return render(request, 'supplier/order-listing.html', context)
class UpdatePaymentStatusView(LoginRequiredMixin, View):
    def post(self, request):
        order_id = request.POST.get("order_id")
        paid = request.POST.get("paid")

        if paid not in ["True", "False"]:
            return JsonResponse({"success": False, "error": "Invalid status"})

        order = get_object_or_404(Order, order_id=order_id)
        if not order.items.filter(order_to=request.user).exists():
            return JsonResponse({"success": False, "error": "Permission denied"})

        if not order.payment:
            return JsonResponse({"success": False, "error": "Payment not found"})

        order.payment.paid = True if paid == "True" else False
        order.payment.save(update_fields=["paid"])

        return JsonResponse({
            "success": True,
            "paid": order.payment.paid
        })
class OrderListAndStatusView(View):
    template_name = 'supplier/orders.html'

    def get(self, request):
        status = request.GET.get('status')

        orders = Order.objects.select_related('user', 'payment')

        if status:
            orders = orders.filter(status=status)

        context = {
            'orders': orders,
            'selected_status': status,

            # DASHBOARD COUNTS
            'total_orders': Order.objects.count(),
            'completed_orders': Order.objects.filter(status='completed').count(),
            'pending_orders': Order.objects.filter(status='pending').count(),
            'cancelled_orders': Order.objects.filter(status='cancelled').count(),
        }
        return render(request, self.template_name, context)

    def post(self, request):
        order_id = request.POST.get('order_id')
        status = request.POST.get('status')

        order = get_object_or_404(Order, order_id=order_id)

        valid_statuses = dict(Order._meta.get_field('status').choices)

        if status not in valid_statuses:
            return JsonResponse({'success': False, 'error': 'Invalid status'})

        order.status = status

        if status == 'delivered':
            order.delivered_at = timezone.now()

        order.save()

        return JsonResponse({'success': True})
class ChangeOrderStatusView(View):
    def post(self, request):
        order_id = request.POST.get('order_id')
        new_status = request.POST.get('status')
        if not order_id or not new_status:
            return JsonResponse({'success': False, 'message': 'Invalid data'}, status=400)
        order = get_object_or_404(Order, order_id=order_id)
        order.status = new_status

        if new_status == 'delivered':
            order.delivered_at = timezone.now()

        order.save()

        return JsonResponse({
            'success': True,
            'new_status': new_status
        })
class OrderDetailsView(View):
    def get(self, request, order_id):
        supplier = request.user

        order = get_object_or_404(
            Order.objects.filter(items__order_to=supplier)
            .distinct()
            .select_related('user', 'payment')
            .prefetch_related(
                Prefetch(
                    'items',
                    queryset=OrderItem.objects
                        .select_related('product', 'order_by', 'order_to')
                        .prefetch_related(
                            Prefetch(
                                'product__images',
                                queryset=ProductImage.objects.filter(is_main=True),
                                to_attr='main_image'
                            )
                        )
                )
            ),
            order_id=order_id
        )

        order_items = order.items.filter(order_to=supplier)
        if not order_items.exists():
            messages.error(request, "You do not have permission to view this order.")
            return redirect('supplier:order_listing')
        subtotal = float(order.payment.amount) if order.payment else 0.0
        commission = order_items.aggregate(
            total=Sum(
                (F('price') * F('product__commission_percentage') / 100) * F('quantity')
            )
        )['total'] or 0.0

        shipping_fee = float(order.shipping_fees or 0.0)
        grand_total = subtotal - float(commission) + shipping_fee

        context = {
            'order': order,
            'order_items': order_items,
            'subtotal': round(subtotal, 2),
            'total_commission': round(float(commission), 2),
            'shipping_fee': round(shipping_fee, 2),
            'grand_total': round(grand_total, 2),
            'user': order.user,
        }

        logger.info(f"Supplier {supplier.id} viewed order {order.order_id}")
        return render(request, 'supplier/order-details.html', context)

# class OrderDeleteView(View):
#     def post(self, request, order_id):
#         supplier = request.user
#         order = get_object_or_404(
#             Order.objects.filter(items__order_to=supplier).distinct(),
#             order_id=order_id
#         )

#         # Check if supplier has items in this order
#         if not order.items.filter(order_to=supplier).exists():
#             logger.warning(f"Supplier {supplier.id} attempted to delete order {order.id} with no relevant items")
#             return JsonResponse({'success': False, 'error': 'You do not have permission to delete this order'}, status=403)

#         # Soft delete by updating status to 'cancelled'
#         order.status = 'cancelled'
#         order.save()
#         order.items.filter(order_to=supplier).update(status='cancelled')
#         logger.info(f"Supplier {supplier.id} cancelled order {order.order_id}")
#         return JsonResponse({'success': True})


class UserProfileView( View):
    def get(self, request):
        return render(request, 'supplier/user-profile.html')


class UserOverView( OnboardingRequiredMixin,View):
    def get(self, request):
        return render(request, 'supplier/overview.html')





class AdminSettingView(View):

    def get(self, request):
        return render(request, 'supplier/settings.html')
    def post(self, request):
        user = request.user
        if 'fname' in request.POST:
            fname = request.POST.get('fname')
            lname = request.POST.get('lname')
            email = request.POST.get('aemail')

            user.first_name = fname
            user.last_name = lname
            user.email = email
            user.save()
            user_update_activity(
                user=user,
                description="User updated profile information (name/email)"
            )

            messages.success(request, "Profile updated successfully!")
            return redirect('supplier:profile_setting')
        elif 'currentpassword' in request.POST:
            current = request.POST.get('currentpassword')
            new = request.POST.get('newpassword')
            confirm = request.POST.get('confirmpassword')

            if not check_password(current, user.password):
                messages.error(request, "Current password is incorrect.")
                user_failed_activity(
                    user=user,
                    description="Failed password change attempt (wrong current password)"
                )
            elif new != confirm:
                messages.error(request, "New passwords do not match.")

                user_failed_activity(
                    user=user,
                    description="Failed password change attempt (password mismatch)"
                )
            elif len(new) < 8:
                messages.error(request, "Password must be at least 8 characters.")

                user_failed_activity(
                    user=user,
                    description="Failed password change attempt (password too short)"
                )
            else:
                user.set_password(new)
                user.save()
                update_session_auth_hash(request, user)
                user_password_change_activity(user)
                messages.success(request, "Password updated successfully.")

            return redirect('supplier:profile_setting')


class CompanyDetailsView(LoginRequiredMixin, View):
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


class WishlistProductView(LoginRequiredMixin, View):
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


class CartProductsView(LoginRequiredMixin, View):
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
class UpdateCartQuantityView(LoginRequiredMixin, View):
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
class DeleteCartItemView(LoginRequiredMixin, View):
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


class MarkNotificationReadView( View):
    def post(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk)
            notif.is_read = True
            notif.save()
            return JsonResponse({'success': True})
        except Notification.DoesNotExist:
            return JsonResponse({'error': 'Notification not found'}, status=404)


class ClearAllNotificationsView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        if request.user.is_superuser:
            Notification.objects.all().delete()
            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({'status': 'unauthorized'}, status=403)


class MarkNotificationReadView( View):
    def post(self, request, pk):
        notif = Notification.objects.get(pk=pk)
        notif.is_read = True
        notif.save()
        return JsonResponse({
            "title": notif.title,
            "message": notif.message,
            "created_at": localtime(notif.created_at).strftime('%d %b %Y, %I:%M %p')
        })


class DeleteNotificationView(LoginRequiredMixin, View):
    def post(self, request, id):
        # Retrieve the notification, ensuring it belongs to the current user
        notification = get_object_or_404(Notification, id=id, recipient=request.user)
        # Delete the notification
        notification.delete()
        return JsonResponse({'status': 'success'})


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('supplier:admin_login') 

#
# class RFQListView(LoginRequiredMixin, SupplierPermissionMixin, OnboardingRequiredMixin,ListView):
#     template_name = 'supplier/rfq_list.html'
#     context_object_name = 'rfqs'
#
#     def get_queryset(self):
#         user = self.request.user
#         if user.is_superuser:
#             return RFQRequest.objects.all()
#         elif hasattr(user, 'supplierprofile'):
#             return RFQRequest.objects.filter(product__created_by=user)
#         return RFQRequest.objects.none()


# 
class SupplierRFQListView(LoginRequiredMixin, ListView):
    template_name = 'supplier/rfq_list.html'
    context_object_name = 'rfqs'
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        user_log_activity(
            user=user,
            actions=UserActivityLog.ActionType.UPDATED,
            description="Viewed RFQ list"
        )

        queryset = (
            RFQRequest.objects.all()
            if user.is_superuser
            else RFQRequest.objects.filter(product__created_by=user)
        )

        search_query = self.request.GET.get('search', '')
        status_filter = self.request.GET.get('status_filter', '')
        quantity_filter = self.request.GET.get('quantity_filter', '')
        created_at_from = self.request.GET.get('created_at_from', '')
        created_at_to = self.request.GET.get('created_at_to', '')

        if search_query:
            queryset = queryset.filter(
                Q(product__name__icontains=search_query) |
                Q(requested_by__username__icontains=search_query) |
                Q(company_name__icontains=search_query)
            )

        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)

        if quantity_filter:
            try:
                quantity = int(quantity_filter)
                if quantity > 0:
                    queryset = queryset.filter(quantity__gte=quantity)
            except ValueError:
                pass

        if created_at_from:
            try:
                queryset = queryset.filter(
                    created_at__gte=datetime.strptime(created_at_from, '%Y-%m-%d')
                )
            except ValueError:
                pass

        if created_at_to:
            try:
                created_at_to = datetime.strptime(created_at_to, '%Y-%m-%d')
                created_at_to = created_at_to.replace(hour=23, minute=59, second=59)
                queryset = queryset.filter(created_at__lte=created_at_to)
            except ValueError:
                pass

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = RFQRequest.STATUS_CHOICES
        return context
class SupplierQuotationUpdateView(LoginRequiredMixin, UpdateView):
    model = RFQRequest
    form_class = SupplierRFQQuotationForm
    template_name = 'supplier/rfq_quotation_form.html'
    success_url = reverse_lazy('supplier:rfq_list')

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)

        user_log_activity(
            user=request.user,
            actions=UserActivityLog.ActionType.UPDATED,
            description=f"Viewed RFQ quotation (RFQ ID {self.get_object().id})"
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comments'] = self.object.comments.all()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if 'add_comment' in request.POST:
            comment_text = request.POST.get('comment', '').strip()

            if comment_text:
                RFQComment.objects.create(
                    rfq=self.object,
                    comment=comment_text,
                    commented_by=request.user,
                )

                user_log_activity(
                    user=request.user,
                    actions=UserActivityLog.ActionType.CREATED,
                    description=f"Added comment on RFQ ID {self.object.id}"
                )

                messages.success(request, "Comment added.")
            else:
                messages.error(request, "Comment cannot be empty.")

            return redirect('supplier:rfq_quote', pk=self.object.pk)
        if 'add_reply' in request.POST:
            reply_to_id = request.POST.get('reply_to')
            reply_text = request.POST.get('admin_reply', '').strip()

            try:
                comment = RFQComment.objects.get(id=reply_to_id, rfq=self.object)
                comment.admin_reply = reply_text
                comment.replied_at = timezone.now()
                comment.save()

                user_log_activity(
                    user=request.user,
                    actions=UserActivityLog.ActionType.UPDATED,
                    description=f"Replied to RFQ comment (RFQ ID {self.object.id})"
                )

                messages.success(request, "Reply saved.")
            except RFQComment.DoesNotExist:
                messages.error(request, "Comment not found.")

            return redirect('supplier:rfq_quote', pk=self.object.pk)
        if 'send_quotation' in request.POST:
            form = self.get_form()
            if form.is_valid():
                return self.form_valid(form)
            return self.form_invalid(form)

        return redirect('supplier:rfq_quote', pk=self.object.pk)

    def form_valid(self, form):
        rfq = form.save(commit=False)
        rfq.quoted_by = self.request.user
        rfq.quote_sent_at = timezone.now()
        rfq.status = 'quoted'
        rfq.save()

        user_log_activity(
            user=self.request.user,
            actions=UserActivityLog.ActionType.CREATED,
            description=f"Quotation sent for RFQ ID {rfq.id}"
        )

        self.send_quotation_email(rfq)
        messages.success(self.request, "Quotation sent successfully.")
        return super().form_valid(form)

    def send_quotation_email(self, rfq):
        subject = f"Quotation for RFQ #{rfq.id}"
        message = render_to_string(
            'supplier/rfq_quotation_sent.html',
            {'rfq': rfq}
        )

        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[rfq.requested_by.email],
        )
        email.content_subtype = 'html'

        try:
            email.send()
        except Exception:
            user_failed_activity(
                user=rfq.quoted_by,
                description=f"Quotation email failed (RFQ ID {rfq.id})"
            )
            raise



# from django.core.paginator import Paginator
# from django.contrib.auth.mixins import LoginRequiredMixin
# from django.views.generic import TemplateView

# class BannerListView(LoginRequiredMixin, SupplierPermissionMixin, TemplateView):
#     template_name = 'supplier/banner_list.html'
#     paginate_by = 12   

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['form'] = BannerForm()
#         banners = Banner.objects.all()

#         # Handle filters
#         search_query = self.request.GET.get('search', '') 
#         is_active = self.request.GET.get('is_active', '')
#         order = self.request.GET.get('order', '')

#         # Apply filters
#         if search_query:
#             banners = banners.filter(title__icontains=search_query)
#         if is_active in ['0', '1']:
#             banners = banners.filter(is_active=bool(int(is_active)))
#         if order:
#             try:
#                 banners = banners.filter(order=int(order))
#             except ValueError:
#                 pass

#         # Pagination 
#         paginator = Paginator(banners, self.paginate_by)
#         page_number = self.request.GET.get('page')
#         page_obj = paginator.get_page(page_number)

#         # Send to context
#         context['banners'] = page_obj
#         context['page_obj'] = page_obj

#         # Preserve filters for template
#         context['search'] = search_query
#         context['is_active'] = is_active
#         context['order'] = order

#         return context


# class BannerCreateView(LoginRequiredMixin, SupplierPermissionMixin, View):
#     def get(self, request):
#         form = BannerForm()
#         return render(request, 'supplier/banner_upload.html', {'form': form})

#     def post(self, request):
#         form = BannerForm(request.POST, request.FILES)
#         if form.is_valid():
#             form.save()
#             return redirect('supplier:banner_list')
#         return render(request, 'supplier/banner_upload.html', {'form': form})


# class BannerUpdateView(LoginRequiredMixin, SupplierPermissionMixin, View):
#     def get(self, request, pk):
#         banner = get_object_or_404(Banner, pk=pk)
#         form = BannerForm(instance=banner)
#         return render(request, 'supplier/banner_edit.html', {'form': form, 'object': banner})

#     def post(self, request, pk):
#         banner = get_object_or_404(Banner, pk=pk)
#         form = BannerForm(request.POST, request.FILES, instance=banner)
#         if form.is_valid():
#             form.save()
#             return redirect('supplier:banner_list')
#         return render(request, 'supplier/view_product.html', {'form': form, 'object': banner})


class TransactionView(OnboardingRequiredMixin,TemplateView):
    template_name = 'supplier/transaction.html'
    paginate_by = 15 

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # ----------------- Aggregates -----------------
        all_payments = Payment.objects.all()
        paid_money = all_payments.filter(paid=True).aggregate(total=Sum('amount'))['total'] or 0
        unpaid_money = all_payments.filter(paid=False).aggregate(total=Sum('amount'))['total'] or 0
        cash_money = all_payments.filter(payment_method="cod").aggregate(total=Sum('amount'))['total'] or 0

        # ----------------- Filters -----------------
        payments = Payment.objects.all()
        search = self.request.GET.get('search', '').strip()
        if search:
            query = Q()
            query |= Q(name__icontains=search)
            query |= Q(user__username__icontains=search)
            query |= Q(user__first_name__icontains=search)
            query |= Q(user__last_name__icontains=search)

            # Annotate full name
            payments = payments.annotate(
                full_name=Concat(F('user__first_name'), Value(' '), F('user__last_name'))
            )
            query |= Q(full_name__icontains=search)

            if search.isdigit():
                query |= Q(id=int(search))

            payments = payments.filter(query)

        payment_method = self.request.GET.get('payment_method', '')
        if payment_method and payment_method != 'all':
            payments = payments.filter(payment_method=payment_method)

        status = self.request.GET.get('status', '')
        if status and status != 'all':
            paid_status = status == 'paid'
            payments = payments.filter(paid=paid_status)

        date_filter = self.request.GET.get('date_filter', '')
        if date_filter and date_filter != 'all':
            today = timezone.now().date()
            if date_filter == 'today':
                payments = payments.filter(created_at__date=today)
            elif date_filter == 'last_7_days':
                payments = payments.filter(created_at__date__gte=today - timedelta(days=7))
            elif date_filter == 'last_30_days':
                payments = payments.filter(created_at__date__gte=today - timedelta(days=30))

        payments = payments.order_by('-created_at')

        # ----------------- Pagination -----------------
        paginator = Paginator(payments, self.paginate_by)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # ----------------- Context -----------------
        context['total_orders'] = paid_money
        context['pending_orders'] = unpaid_money
        context['cash_money'] = cash_money
        context['orders'] = page_obj  
        context['page_obj'] = page_obj
        context['payment_method_choices'] = Payment._meta.get_field('payment_method').choices

        return context

def PrintBillView(request, pk):
    order = get_object_or_404(Order, pk=pk)
    payment = getattr(order, 'payment', None) 
    html_content = render_to_string('supplier/print_bill.html', {'order': order, 'payment': payment})
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Bill_Order_{order.id}.pdf"'
    pisa_status = pisa.CreatePDF(html_content, dest=response)
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html_content + '</pre>')
    
    return response

class MostViewedProductsView(OnboardingRequiredMixin,View):
    paginate_by = 12  

    def get(self, request):
        # Get filter parameters
        search = request.GET.get('search', '')
        brand_filter = request.GET.get('brand_filter', 'all')
        sort_by = request.GET.get('sort_by', 'desc_delivered')

        # Base queryset with annotations
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
                to_attr='images_list'
            )
        )

        # Apply filters
        if search:
            products = products.filter(
                Q(name__icontains=search) |
                Q(brand__name__icontains=search)
            )
        if brand_filter != 'all':
            products = products.filter(brand__id=brand_filter)

        # Apply sorting
        if sort_by == 'asc_delivered':
            products = products.order_by('delivered_count')
        elif sort_by == 'desc_delivered':
            products = products.order_by('-delivered_count')
        elif sort_by == 'asc_reviews':
            products = products.order_by('review_count')
        elif sort_by == 'desc_reviews':
            products = products.order_by('-review_count')

        # Set display image for each product
        for product in products:
            if product.images_list:
                main_images = [img for img in product.images_list if img.is_main]
                product.display_image = main_images[0] if main_images else product.images_list[0]
            else:
                product.display_image = None

        # Payment calculations
        payments = Payment.objects.all()
        paid_money = payments.filter(paid=True).aggregate(total=Sum('amount'))['total'] or 0
        unpaid_money = payments.filter(paid=False).aggregate(total=Sum('amount'))['total'] or 0
        cash_money = payments.filter(payment_method="cod").aggregate(total=Sum('amount'))['total'] or 0

        # Pagination 
        paginator = Paginator(products, self.paginate_by)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Context
        context = {
            'total_orders': paid_money,
            'pending_orders': unpaid_money,
            'cash_money': cash_money,
            'orders': payments,
            'products': page_obj,       
            'page_obj': page_obj,      
            'brands': Brand.objects.all(), 
            'search': search,          
            'brand_filter': brand_filter, 
            'sort_by': sort_by,         
        }

        return render(request, "supplier/view_product.html", context)
class QuestionView(OnboardingRequiredMixin, TemplateView):
    template_name = 'supplier/question.html'
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # 🔹 LOG: View questions page
        user_log_activity(
            user=self.request.user,
            actions=UserActivityLog.ActionType.UPDATED,
            description="Viewed product questions list"
        )

        user_products = Product.objects.filter(created_by=self.request.user)
        questions_qs = Question.objects.filter(
            product__in=user_products
        ).select_related('user', 'product')

        # ---------------- SEARCH ----------------
        search_by = self.request.GET.get('search_by')
        if search_by:
            questions_qs = questions_qs.filter(
                Q(text__icontains=search_by) |
                Q(user__username__icontains=search_by) |
                Q(product__name__icontains=search_by)
            )

        # ---------------- SORTING ----------------
        sort_by = self.request.GET.get('sort_by')
        if sort_by == "asc_created":
            questions_qs = questions_qs.order_by('created_at')
        else:
            questions_qs = questions_qs.order_by('-created_at')

        # ---------------- DATE RANGE ----------------
        created_date = self.request.GET.get('created_date')
        start_date = end_date = None

        if created_date:
            dates = created_date.split(' - ')
            if len(dates) == 2:
                start_date = datetime.strptime(dates[0], "%m/%d/%Y").date()
                end_date = datetime.strptime(dates[1], "%m/%d/%Y").date()
            elif len(dates) == 1:
                start_date = end_date = datetime.strptime(dates[0], "%m/%d/%Y").date()

        if start_date:
            questions_qs = questions_qs.filter(created_at__date__gte=start_date)
        if end_date:
            questions_qs = questions_qs.filter(created_at__date__lte=end_date)

        # ---------------- PAGINATION ----------------
        paginator = Paginator(questions_qs, self.paginate_by)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context.update({
            'questions': page_obj.object_list,
            'page_obj': page_obj,
            'search_by': search_by,
            'sort_by': sort_by,
            'created_date': created_date,
        })

        return context

    def post(self, request, *args, **kwargs):
        question_id = request.POST.get('question_id')
        reply_text = request.POST.get('reply_text')
        action_type = request.POST.get('action_type')

        user_products = Product.objects.filter(created_by=request.user)
        question = get_object_or_404(
            Question,
            id=question_id,
            product__in=user_products
        )

        # ---------------- REPLY ----------------
        if action_type == "reply":
            question.reply = reply_text
            question.replied_at = timezone.now()
            question.save()

            # ✅ CREATED (reply sent)
            user_log_activity(
                user=request.user,
                actions=UserActivityLog.ActionType.CREATED,
                description=f"Sent reply to question ID {question.id} (Product: {question.product.name})"
            )

            messages.success(request, "Reply sent successfully.")

        # ---------------- DELETE ----------------
        elif action_type == "delete":
            question.delete()

            user_log_activity(
                user=request.user,
                actions=UserActivityLog.ActionType.DELETED,
                description=f"Deleted question ID {question.id} (Product: {question.product.name})"
            )

            messages.success(request, "Question deleted successfully.")

        return redirect('supplier:question_list')

class RatingView(OnboardingRequiredMixin,TemplateView):
    template_name = "supplier/rating.html"  

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.is_superuser:
            products = Product.objects.all()
        else:
            products = Product.objects.filter(created_by=user)

        products = products.annotate(
            avg_rating=Avg('reviews__rating'),
            review_count=Coalesce(
                Count(
                    'reviews',
                    filter=Q(reviews__rating__isnull=False) & ~Q(reviews__review="")
                ),
                Value(0)
            )
        ).filter(avg_rating__isnull=False)

        # Get query parameters
        search_query = self.request.GET.get('search', '')
        rating_filter = self.request.GET.get('rating_filter', 'all')
        review_count = self.request.GET.get('review_count', 'all')
        price_range = self.request.GET.get('price_range', 'all')

        # Apply search filter (Product ID or Name)
        if search_query:
            products = products.filter(
                Q(name__icontains=search_query) |
                Q(id__icontains=search_query)
            )

        # Apply rating filter
        if rating_filter != 'all':
            try:
                min_rating, max_rating = map(float, rating_filter.split('-'))
                products = products.filter(
                    avg_rating__gte=min_rating,
                    avg_rating__lte=max_rating
                )
            except ValueError:
                pass  # invalid filter

        # Apply review count filter
        if review_count != 'all':
            if review_count == '101-plus':
                products = products.filter(review_count__gte=101)
            else:
                try:
                    min_count, max_count = map(int, review_count.split('-'))
                    products = products.filter(
                        review_count__gte=min_count,
                        review_count__lte=max_count
                    )
                except ValueError:
                    pass

        # Apply price range filter
        if price_range != 'all':
            if price_range == '201-plus':
                products = products.filter(price__gte=201)
            else:
                try:
                    min_price, max_price = map(int, price_range.split('-'))
                    products = products.filter(
                        price__gte=min_price,
                        price__lte=max_price
                    )
                except ValueError:
                    pass


        products = products.order_by('-avg_rating')

        # Pagination
        paginator = Paginator(products, 10)  
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

     
        context.update({
            'products': page_obj,
            'search_query': search_query,
            'rating_filter': rating_filter,
            'review_count': review_count,
            'price_range': price_range,
            'page_obj': page_obj,
        })

        return context
class ProductRatingListView(TemplateView):
    template_name = "supplier/product_ratings.html"
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = get_object_or_404(Product, id=self.kwargs['product_id'])

        ratings_qs = RatingReview.objects.filter(product=product).select_related('user')
        search_by = self.request.GET.get('search_by')
        if search_by:
            ratings_qs = ratings_qs.filter(
                Q(user__username__icontains=search_by) |
                Q(review__icontains=search_by)
            )
        created_date = self.request.GET.get('created_date')
        if created_date:
            try:
                start_date, end_date = created_date.split(' - ')
                start_date = datetime.strptime(start_date, '%m/%d/%Y')
                end_date = datetime.strptime(end_date, '%m/%d/%Y')
                ratings_qs = ratings_qs.filter(
                    created_at__date__range=[start_date.date(), end_date.date()]
                )
            except ValueError:
                pass
        sort_by = self.request.GET.get('sort_by', 'desc_created')
        ratings_qs = ratings_qs.order_by(
            '-created_at' if sort_by == 'desc_created' else 'created_at'
        )
        paginator = Paginator(ratings_qs, self.paginate_by)
        page_obj = paginator.get_page(self.request.GET.get('page'))

        context.update({
            "product": product,
            "ratings": page_obj,
            "page_obj": page_obj,
        })
        return context




class   SupplierReturnsView(LoginRequiredMixin, TemplateView):

    template_name = 'supplier/returns.html'
    login_url = 'dashboard:login'
    paginate_by = 14  

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Check user permissions
        # if not (user.is_superuser or (hasattr(user, 'userprofile') and user.userprofile.is_supplier)):
        #     raise PermissionDenied("You are not authorized to access this page.")

        # Base queryset for returns
        if user.is_superuser:
            returns_qs = Return.objects.all()
        else:
            returns_qs = Return.objects.filter(
                order_item__product__brand__supplier=user
            )

        # Apply filters from GET parameters
        search_query = self.request.GET.get('search', '').strip()
        product_filter = self.request.GET.get('product_filter', 'all')
        return_option_filter = self.request.GET.get('return_option_filter', 'all')
        return_status_filter = self.request.GET.get('return_status_filter', 'all')

        # Search filter
        if search_query:
            returns_qs = returns_qs.filter(
                Q(return_serial__icontains=search_query) |
                Q(order_item__product__name__icontains=search_query) |
                Q(client__username__icontains=search_query)
            )

        # Product filter
        if product_filter != 'all':
            returns_qs = returns_qs.filter(order_item__product__id=product_filter)

        # Return option filter
        if return_option_filter != 'all':
            returns_qs = returns_qs.filter(return_option=return_option_filter)

        # Return status filter
        if return_status_filter != 'all':
            returns_qs = returns_qs.filter(return_status=return_status_filter)

        # Optimize queryset
        returns_qs = returns_qs.select_related(
            'order_item__product', 'client'
        ).order_by('-request_date')

        # Paginate
        paginator = Paginator(returns_qs, self.paginate_by)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['returns'] = page_obj
        context['page_obj'] = page_obj

        # Product filter options
        if user.is_superuser:
            context['products'] = Product.objects.all()
        else:
            context['products'] = Product.objects.filter(brand__supplier=user)

        # Return choices
        context['return_option_choices'] = Return.RETURN_OPTION_CHOICES
        context['return_status_choices'] = Return.RETURN_STATUS_CHOICES

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

class UserInformationView(FormView):
    template_name = "supplier/user_information.html"
    form_class = UserInformationForm
    success_url = reverse_lazy("supplier:business_information")  

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        profile, created = SupplierProfile.objects.get_or_create(user=self.request.user)
        kwargs["instance"] = profile 
        return kwargs
                    
    def get_initial(self):
        user = self.request.user
        profile, created = SupplierProfile.objects.get_or_create(user=user)
        return {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone": profile.phone,
            "job_title": profile.job_title,
            "supplier_type": profile.supplier_type,
            "are_you_buyer_b2b": profile.are_you_buyer_b2b,
            "selling_for": profile.selling_for,
            "meta_description": profile.meta_description,
            "meta_keywords": profile.meta_keywords,
        }

    def form_valid(self, form):
        user = self.request.user
        profile, created = SupplierProfile.objects.get_or_create(user=user)
        user.first_name = form.cleaned_data["first_name"]
        user.last_name = form.cleaned_data["last_name"]
        user.email = form.cleaned_data["email"]
        user.save()

        for field in [
            "profile_picture",
            "phone",
            "job_title",
            "supplier_type",
            "are_you_buyer_b2b",
            "selling_for",
            "meta_description",
            "meta_keywords",
        ]:
            setattr(profile, field, form.cleaned_data[field])
        profile.save()

        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["step"] = 1
        context["progress"] = 12  
        return context

class BusinessInformationView(FormView):
    template_name = "supplier/user_information.html"
    form_class = BusinessInformationForm
    success_url = reverse_lazy("supplier:bank_details")

    def get_initial(self):
        user = self.request.user
        profile, created = SupplierProfile.objects.get_or_create(user=user)
        return {
            "business_name": profile.business_name,
            "registration_number": profile.registration_number,
            "authorized_person_name": profile.authorized_person_name,
        }

    def form_valid(self, form):
        """
        Save both text and file fields.
        File fields only update if a new file is uploaded.
        """
        user = self.request.user
        profile, created = SupplierProfile.objects.get_or_create(user=user)

        # Update normal fields (text)
        for field, value in form.cleaned_data.items():
            if field not in ["company_logo", "company_commercial_license", "iso_certificate", "export_import_license"]:
                setattr(profile, field, value)

        # Update file fields only if new files are uploaded
        file_fields = ["company_logo", "company_commercial_license", "iso_certificate", "export_import_license"]
        for file_field in file_fields:
            if self.request.FILES.get(file_field):
                setattr(profile, file_field, self.request.FILES[file_field])

        profile.save()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["step"] = 2
        context["progress"] = 25
        # Pass profile for previewing images
        context["profile"] = SupplierProfile.objects.get(user=self.request.user)
        return context


class BankDetailsView(TemplateView):
    template_name = "supplier/user_information.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["step"] = 3
        context["progress"] = 38  
        return context


class BankDetailsView(TemplateView):
    template_name = "supplier/user_information.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, created = SupplierProfile.objects.get_or_create(user=self.request.user)
        context["step"] = 3
        context["progress"] = 50  
        context["form"] = BankDetailsForm(instance=profile)
        return context

    def post(self, request, *args, **kwargs):
        profile, created = SupplierProfile.objects.get_or_create(user=request.user)
        form = BankDetailsForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("supplier:selling_categories")  
        context = self.get_context_data()
        context["form"] = form
        return self.render_to_response(context) 


class SellingCategoriesView(TemplateView):
    template_name = "supplier/user_information.html"

    def get(self, request, *args, **kwargs):
        profile = SupplierProfile.objects.get(user=request.user)
        form = SellingCategoriesForm(instance=profile)
        return self.render_to_response({
            "form": form,
            "step": 4,
            "progress": 65,
        })

    def post(self, request, *args, **kwargs):
        profile = SupplierProfile.objects.get(user=request.user)
        form = SellingCategoriesForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("supplier:supplier_description") 
        return self.render_to_response({
            "form": form,
            "step": 4,
            "progress": 65,
        })


class SupplierDescriptionView(TemplateView):
    template_name = "supplier/user_information.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, _ = SupplierProfile.objects.get_or_create(user=self.request.user)
        form = SupplierDescriptionForm(instance=profile)
        context["form"] = form
        context["step"] = 5
        context["progress"] = 80
        return context

    def post(self, request, *args, **kwargs):
        profile, _ = SupplierProfile.objects.get_or_create(user=request.user)
        form = SupplierDescriptionForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("supplier:pickup_shipping") 
        return self.render_to_response({
            "form": form,
            "step": 5,
            "progress": 80
        })

    
class PickupShippingView(TemplateView):
    template_name = "supplier/user_information.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = SupplierProfile.objects.get(user=self.request.user)
        form = PickupandShipping(instance=profile)
        context["form"] = form
        context["step"] = 6
        context["progress"] = 90
        context["saved_country"] = profile.country_id or ""
        context["saved_state"] = profile.state_id or ""
        context["saved_city"] = profile.city_id or ""
        return context

    def post(self, request, *args, **kwargs):
        profile = SupplierProfile.objects.get(user=request.user)
        form = PickupandShipping(request.POST, instance=profile)

        if form.is_valid():
            form.save()
            return redirect("supplier:supplier_documents")

        context = self.get_context_data()
        context["form"] = form
        return self.render_to_response(context)

class GetStatesView(View):
    def get(self, request, *args, **kwargs):
        country_id = request.GET.get("country_id")
        states = State.objects.filter(country_id=country_id).values("id", "name")
        return JsonResponse(list(states), safe=False)

class GetCitiesView(View):
    def get(self, request, *args, **kwargs):
        state_id = request.GET.get("state_id")
        cities = City.objects.filter(state_id=state_id).values("id", "name")
        return JsonResponse(list(cities), safe=False)
    
class SupplierDocumentsView(TemplateView):
    template_name = "supplier/user_information.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        step = 7
        supplier_profile = SupplierProfile.objects.get(user=self.request.user)

        form = SupplierDocumentsForm(instance=supplier_profile)

        context["step"] = step
        context["progress"] = 95
        context["form"] = form
        return context

    def post(self, request, *args, **kwargs):
        supplier_profile = SupplierProfile.objects.get(user=request.user)
        form = SupplierDocumentsForm(request.POST, request.FILES, instance=supplier_profile)
        
        if form.is_valid():
            form.save()
            return redirect("supplier:supplier_status") 

        context = self.get_context_data()
        context["form"] = form
        return self.render_to_response(context)


class SupplierStatusView(View):
    template_name = "supplier/user_information.html"

    def get(self, request):
        supplier_profile = SupplierProfile.objects.get(user=request.user)
        form = SupplierStatusForm(instance=supplier_profile)  
        context = {
            "supplier_profile": supplier_profile,
            "form": form,
            "step": 8,
            "progress": 100,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        supplier_profile = SupplierProfile.objects.get(user=request.user)
        form = SupplierStatusForm(request.POST, instance=supplier_profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.onboarding_complete = True 
            form.save()
            return redirect('supplier:supplier')  
        context = {
            "supplier_profile": supplier_profile,
            "form": form,
            "step": 8,
            "progress": 100,
        }
        return render(request, self.template_name, context)


class AdminReturnUpdateStatusView(LoginRequiredMixin, View):
    permission_required = 'is_staff'
    def post(self, request, return_serial, *args, **kwargs):
        return_instance = get_object_or_404(Return, return_serial=return_serial)
        new_status = request.POST.get('return_status')
        if new_status in dict(return_instance.RETURN_STATUS_CHOICES):
            old_status = return_instance.return_status
            return_instance.return_status = new_status
            return_instance.save()
            user_update_activity(
                user=request.user,
                description=(
                    f"Return status updated for Return #{return_serial} "
                    f"from '{old_status}' to '{new_status}'"
                )
            )
            messages.success(
                request,
                f"Return {return_serial} status updated to {new_status}."
            )
        else:
            user_failed_activity(
                user=request.user,
                description=(
                    f"Invalid return status '{new_status}' "
                    f"for Return #{return_serial}"
                )
            )
            messages.error(request, "Invalid status selected.")
        return redirect('supplier:admin_returns')
class AdminProcessRefundView(View):

    def post(self, request, *args, **kwargs):
        return_serial = request.POST.get("hidden_transaction_id")
        refund_amount = float(
            request.POST.get("final_refund_amount")
            or request.POST.get("hidden_transaction_amount", 0)
        )
        admin_note = request.POST.get("hidden_admin_note")
        user_note = request.POST.get("hidden_user_note")
        return_instance = get_object_or_404(
            Return,
            return_serial=return_serial,
            return_status="approved"
        )
        payment = return_instance.order_item.order.payment
        if not payment:
            user_failed_activity(
                user=request.user,
                description=f"Refund failed for Return #{return_serial}: Payment not found"
            )
            messages.error(request, "Payment record not found.")
            return redirect("supplier:admin_returns")

        success, msg, refund_id = process_refund(
            payment,
            return_serial,
            refund_amount,
            admin_note,
            user_note
        )
        if success:
            return_instance.return_status = "return_completed"
            return_instance.is_refunded = True
            return_instance.refund_id = refund_id
            return_instance.updated_at = timezone.now()
            return_instance.save()
            user_refund_activity(
                user=request.user,
                description=f"Refund processed for Return #{return_serial}",
                amount=refund_amount
            )
            messages.success(request, f"Refund successful: {msg}")
        else:
            user_failed_activity(
                user=request.user,
                description=f"Refund failed for Return #{return_serial}: {msg}"
            )
            messages.error(request, f"Refund failed: {msg}")
        return redirect("supplier:admin_returns")


class ReturnDeleteView(LoginRequiredMixin, View):
    permission_required = 'is_staff'
    def post(self, request, return_serial, *args, **kwargs):
        try:
            return_instance = get_object_or_404(Return, return_serial=return_serial)
            user_email = return_instance.client.email
            username = return_instance.client.username
            order_id = return_instance.order_item.order.order_id
            user_log_activity(
                user=request.user,
                actions=UserActivityLog.ActionType.DELETED,
                description=(
                    f"Return deleted by admin. "
                    f"Return ID: {return_serial}, Order ID: {order_id}, "
                    f"Customer: {username}"
                )
            )
            return_instance.delete()
            subject = f"Return {return_serial} Deleted"
            message = (
                f"Hello {username},\n\n"
                f"Your return request for order {order_id} "
                f"(Return ID: {return_serial}) has been deleted by admin.\n\n"
                f"If you believe this is an error, please contact support.\n\n"
                f"Thank you."
            )
            send_refund_notification(user_email, subject, message)
            messages.success(request, f"Return {return_serial} deleted successfully.")
            return redirect('supplier:admin_returns')
        except Exception as e:
            user_failed_activity(
                user=request.user,
                description=f"Failed to delete Return {return_serial}: {str(e)}"
            )
            messages.error(request, f"Error deleting return: {str(e)}")
            return redirect('supplier:admin_returns')


class AdminReturnsView(LoginRequiredMixin, TemplateView):
    template_name = 'supplier/returns.html'
    login_url = 'dashboard:login'
    permission_required = 'is_staff'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = Return.objects.select_related(
            'order_item__product__brand',
            'order_item__order__payment',
            'client'
        ).order_by('-request_date')

        # ---- Pagination Setup ----
        paginator = Paginator(qs, 13) 
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        # Add to context
        context['page_obj'] = page_obj
        context['returns'] = page_obj.object_list 
        context['count_all'] = qs.count()
        context['count_approved'] = qs.filter(return_status='approved').count()
        context['count_pending'] = qs.filter(return_status='pending').count()
        context['count_rejected'] = qs.filter(return_status='rejected').count()
        context['user_permissions_list'] = self.request.user.get_all_permissions()

        return context



class ShippingListView(TemplateView):
    template_name = 'supplier/shippingmethod.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['shipping_methods'] = ShippingMethod.objects.all()
        return context

class ShippingCreateView(View):
    def post(self, request):
        country = request.POST.get('country')
        state = request.POST.get('state')
        city = request.POST.get('city')
        order_subtotal_from = request.POST.get('order_subtotal_from')
        order_subtotal_to = request.POST.get('order_subtotal_to')
        price = request.POST.get('price')
        period = request.POST.get('period')
        period_type = request.POST.get('period_type')
        if float(order_subtotal_from) > float(order_subtotal_to):
            return JsonResponse({'status':'error','message':'Subtotal To must be >= Subtotal From'})

        shipping = ShippingMethod.objects.create(
            country=country, state=state, city=city,
            order_subtotal_from=order_subtotal_from,
            order_subtotal_to=order_subtotal_to,
            price=price, period=period, period_type=period_type
        )
        return JsonResponse({'status':'success','message':'Shipping created','id':shipping.id})

class ShippingUpdateView(View):
    def post(self, request, pk):
        shipping = get_object_or_404(ShippingMethod, pk=pk)
        country = request.POST.get('country')
        state = request.POST.get('state')
        city = request.POST.get('city')
        order_subtotal_from = request.POST.get('order_subtotal_from')
        order_subtotal_to = request.POST.get('order_subtotal_to')
        price = request.POST.get('price')
        period = request.POST.get('period')
        period_type = request.POST.get('period_type')

        # Validation
        if float(order_subtotal_from) > float(order_subtotal_to):
            return JsonResponse({'status':'error','message':'Subtotal To must be >= Subtotal From'})

        shipping.country = country
        shipping.state = state
        shipping.city = city
        shipping.order_subtotal_from = order_subtotal_from
        shipping.order_subtotal_to = order_subtotal_to
        shipping.price = price
        shipping.period = period
        shipping.period_type = period_type
        shipping.save()
        return JsonResponse({'status':'success','message':'Shipping updated'})

class ShippingDeleteView(View):
    def post(self, request, pk):
        shipping = get_object_or_404(ShippingMethod, pk=pk)
        shipping.delete()
        return JsonResponse({'status':'success','message':'Shipping deleted'})
    
class VacationRequestView(LoginRequiredMixin, View):
    template_name = 'supplier/vacationrequest.html'

    def get(self, request):
        requests = VacationRequest.objects.filter(supplier=request.user).order_by('-created_at')
        return render(request, self.template_name, {'requests': requests})

    def post(self, request):
        reason = request.POST.get('reason')
        from_date = request.POST.get('from_date')
        to_date = request.POST.get('to_date')
        if not from_date or not to_date:
            messages.error(request, "Please select both From and To dates.")
            return redirect('supplier:vacation_request')
        vacation_request = VacationRequest.objects.create(
            supplier=request.user,
            reason=reason,
            from_date=from_date,
            to_date=to_date,
        )
        user_log_activity(
            user=request.user,
            actions=UserActivityLog.ActionType.CREATED,
            description=f"Created vacation request (ID: {vacation_request.id}, From: {from_date}, To: {to_date})"
        )

        messages.success(request, "Vacation request submitted successfully!")
        return redirect('supplier:vacation_request')
class CouponsView(TemplateView):
    template_name = "supplier/coupons.html"
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'supplierprofile'):
            return redirect('supplier:supplier')
        return super().dispatch(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        coupons_qs = Coupon.objects.select_related("created_by").order_by("-id")
        search_by = self.request.GET.get("search_by", "").strip()
        if search_by:
            coupons_qs = coupons_qs.filter(
                Q(code__icontains=search_by) |
                Q(coupon_type__icontains=search_by) |
                Q(discount_type__icontains=search_by)
            )
        created_date = self.request.GET.get("created_date", "").strip()
        if created_date:
            try:
                start_str, end_str = created_date.split(" - ")

                start_date = timezone.make_aware(
                    datetime.strptime(start_str, "%m/%d/%Y")
                )

                end_date = timezone.make_aware(
                    datetime.strptime(end_str, "%m/%d/%Y")
                ).replace(hour=23, minute=59, second=59)

                coupons_qs = coupons_qs.filter(
                    created_at__range=(start_date, end_date)
                )
            except ValueError:
                pass  

        # ---------------- PAGINATION ----------------
        paginator = Paginator(coupons_qs, 10)
        page_number = self.request.GET.get("page", 1)
        coupons = paginator.get_page(page_number)

        # ---------------- PRODUCTS ----------------
        supplier_products = Product.objects.filter(
            created_by=self.request.user
        ).select_related("category", "brand")
        # ---------------- CLIENTS ----------------
        buyer_ids = OrderItem.objects.filter(
            product__created_by=self.request.user
        ).values_list("order__user_id", flat=True).distinct()

        clients = (
            User.objects.filter(id__in=buyer_ids)
            if buyer_ids else User.objects.all()
        )
        # ---------------- CONTEXT ----------------
        context.update({
            "coupons": coupons,
            "page_obj": coupons,
            "products": supplier_products,
            "clients": clients,
            "search_placeholder_text": "Search Coupons",
            "search_help_text": "Choices: Code, Coupon Type, Discount Type",
            "show_advance_search_link": True,
            "created_date": created_date,
        })

        return context
    def post(self, request, *args, **kwargs):
        try:
            code = request.POST.get("code", "").strip().upper()

            if Coupon.objects.filter(code=code).exists():
                return JsonResponse(
                    {"status": "error", "message": "Coupon code already exists!"},
                    status=400
                )
            start_datetime_str = request.POST.get("start_datetime", "").strip()
            end_datetime_str = request.POST.get("end_datetime", "").strip()

            if not start_datetime_str or not end_datetime_str:
                return JsonResponse(
                    {"status": "error", "message": "Start and End datetime required"},
                    status=400
                )

            start_datetime = timezone.make_aware(
                datetime.strptime(start_datetime_str, "%Y-%m-%dT%H:%M")
            )
            end_datetime = timezone.make_aware(
                datetime.strptime(end_datetime_str, "%Y-%m-%dT%H:%M")
            )
            coupon = Coupon.objects.create(
                code=code,
                coupon_type=request.POST.get("coupon_type"),
                discount_type=request.POST.get("discount_type"),
                discount=Decimal(request.POST.get("discount", "0")),
                max_discount=Decimal(request.POST.get("max_discount", "0")),
                minimum_purchase_amount=Decimal(
                    request.POST.get("minimum_purchase_amount", "0")
                ),
                count_of_use=int(request.POST.get("count_of_use", 1)),
                filter_by_orders_count=int(
                    request.POST.get("filter_by_orders_count", 0)
                ),
                filter_by_orders_amount=Decimal(
                    request.POST.get("filter_by_orders_amount", "0")
                ),
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                can_be_used_with_promotions=(
                    request.POST.get("can_be_used_with_promotions") == "true"
                ),
                created_by=request.user,
            )
            product_ids = request.POST.getlist("product_ids[]")
            client_ids = request.POST.getlist("client_ids[]")

            if product_ids:
                coupon.products.set(
                    Product.objects.filter(
                        id__in=product_ids,
                        created_by=request.user
                    )
                )

            if client_ids:
                coupon.client.set(User.objects.filter(id__in=client_ids))
            user_log_activity(
                user=request.user,
                actions=UserActivityLog.ActionType.CREATED,
                description=f"Created coupon '{code}' (ID: {coupon.id}, Type: {coupon.coupon_type}, Discount: {coupon.discount})"
            )

            return JsonResponse(
                {"status": "success", "message": "Coupon created successfully!"}
            )

        except ValueError as e:
            return JsonResponse(
                {"status": "error", "message": f"Invalid value: {str(e)}"},
                status=400
            )
        except Exception as e:
            return JsonResponse(
                {"status": "error", "message": str(e)},
                status=500
            )
def edit_coupon(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

    coupon_id = request.POST.get('coupon_id')
    coupon = get_object_or_404(Coupon, id=coupon_id)

    try:
        start_datetime_str = request.POST.get("start_datetime", "").strip()
        end_datetime_str = request.POST.get("end_datetime", "").strip()
        
        if not start_datetime_str or not end_datetime_str:
            return JsonResponse(
                {"status": "error", "message": "Start date/time and end date/time are required"},
                status=400
            )
        start_datetime = timezone.make_aware(
            datetime.strptime(start_datetime_str, "%Y-%m-%dT%H:%M")
        )
        end_datetime = timezone.make_aware(
            datetime.strptime(end_datetime_str, "%Y-%m-%dT%H:%M")
        )
        
        old_code = coupon.code
        
        coupon.code = request.POST.get('code').strip().upper()
        coupon.coupon_type = request.POST.get('coupon_type')
        coupon.discount_type = request.POST.get('discount_type')
        coupon.discount = Decimal(request.POST.get('discount'))
        coupon.minimum_purchase_amount = Decimal(request.POST.get('minimum_purchase_amount', '0'))
        coupon.max_discount = Decimal(request.POST.get('max_discount', '0'))
        coupon.count_of_use = int(request.POST.get('count_of_use', 1))
        coupon.filter_by_orders_count = int(request.POST.get('filter_by_orders_count', 0))
        coupon.filter_by_orders_amount = Decimal(request.POST.get('filter_by_orders_amount', '0'))
        coupon.start_datetime = start_datetime
        coupon.end_datetime = end_datetime
        coupon.can_be_used_with_promotions = request.POST.get('can_be_used_with_promotions') == 'true'
        coupon.save()

        product_ids = request.POST.getlist('product_ids[]')
        client_ids = request.POST.getlist('client_ids[]')
        valid_products = Product.objects.filter(created_by=request.user, id__in=product_ids)
        coupon.products.set(valid_products)

        coupon.client.set(User.objects.filter(id__in=client_ids))
        user_log_activity(
            user=request.user,
            actions=UserActivityLog.ActionType.UPDATED,
            description=f"Updated coupon '{coupon.code}' (ID: {coupon.id}, Previous code: {old_code})"
        )
        return JsonResponse({'status': 'success', 'message': 'Coupon updated successfully!'})
    except ValueError as e:
        return JsonResponse({'status': 'error', 'message': f'Invalid datetime format: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
def delete_coupon(request):
    if request.method == 'POST':
        coupon_id = request.POST.get('coupon_id')
        coupon = get_object_or_404(Coupon, id=coupon_id)
        coupon_code = coupon.code
        coupon.delete()
        user_log_activity(
            user=request.user,
            actions=UserActivityLog.ActionType.DELETED,
            description=f"Deleted coupon '{coupon_code}' (ID: {coupon_id})"
        )
        
        return JsonResponse({'status': 'success', 'message': 'Coupon deleted successfully!'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


def coupon_details(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id)

    product_ids = list(coupon.products.filter(created_by=request.user).values_list('id', flat=True))
    client_ids = list(coupon.client.values_list('id', flat=True))

    return JsonResponse({
        'status': 'success',
        'products': product_ids,
        'clients': client_ids
    })

    
class SupplierBuyXGetYPromotionView(TemplateView):
    template_name = 'supplier/Buyxgetypromotion.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Buy X Get Y Promotion'
        context['promotions'] = BuyXGetYPromotion.objects.all()
        context['suppliers'] = SupplierProfile.objects.all()
        context['products'] = Product.objects.all()
        return context
class SupplierAddPromotionView(TemplateView):
    def post(self, request):
        product_type = request.POST.get('product_type')
        supplier_ids = request.POST.getlist('supplier')
        product_ids = request.POST.getlist('product')
        buy = request.POST.get('buy')
        get = request.POST.get('get')
        promotion_period = request.POST.get('promotion_period')
        promo = BuyXGetYPromotion.objects.create(
            product_type=product_type,
            buy=buy,
            get=get,
            promotion_period=promotion_period
        )

        promo.supplier.set(supplier_ids)
        promo.product.set(product_ids)
        promo.save()
        user_log_activity(
            user=request.user,
            actions=UserActivityLog.ActionType.CREATED,
            description=f"Created Buy X Get Y promotion (ID: {promo.id}, Buy: {buy}, Get: {get}, Period: {promotion_period})"
        )

        return JsonResponse({'success': True})


class SupplierEditPromotionView(TemplateView):
    def get(self, request, pk):
        try:
            promo = BuyXGetYPromotion.objects.get(pk=pk)
            start_str, _, end_str = promo.promotion_period.partition(' - ')
            start_str = start_str.strip()
            end_str = end_str.strip()

            def format_datetime(dt_str):
                from datetime import datetime
                try:
                    dt = datetime.strptime(dt_str, "%d %b %Y")
                    return dt.strftime("%Y-%m-%dT00:00")
                except:
                    return ""

            data = {
                'product_type': promo.product_type,
                'supplier': list(promo.supplier.values_list('id', flat=True)),
                'product': list(promo.product.values_list('id', flat=True)),
                'buy': promo.buy,
                'get': promo.get,
                'start_datetime': format_datetime(start_str),
                'end_datetime': format_datetime(end_str),
            }
            return JsonResponse({'success': True, 'data': data})
        except BuyXGetYPromotion.DoesNotExist:
            return JsonResponse({'success': False, 'msg': 'Promotion not found'})

    def post(self, request, pk):
        try:
            promo = BuyXGetYPromotion.objects.get(pk=pk)

            product_type = request.POST.get('product_type')
            supplier_ids = request.POST.getlist('supplier')
            product_ids = request.POST.getlist('product')
            buy = request.POST.get('buy')
            get = request.POST.get('get')
            start = request.POST.get('start_datetime')
            end = request.POST.get('end_datetime')
            from datetime import datetime
            start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%M")
            end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M")
            promotion_period = f"{start_dt.strftime('%d %b %Y')} - {end_dt.strftime('%d %b %Y')}"

            promo.product_type = product_type
            promo.buy = buy
            promo.get = get
            promo.promotion_period = promotion_period
            promo.save()

            promo.supplier.set(supplier_ids)
            promo.product.set(product_ids)
            user_log_activity(
                user=request.user,
                actions=UserActivityLog.ActionType.UPDATED,
                description=f"Updated Buy X Get Y promotion (ID: {promo.id}, Buy: {buy}, Get: {get})"
            )

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'msg': str(e)})


def supplier_delete_promotion(request, pk):
    try:
        promo = BuyXGetYPromotion.objects.get(pk=pk)
        promo_info = f"Buy {promo.buy} Get {promo.get}"
        promo.delete()
        user_log_activity(
            user=request.user,
            actions=UserActivityLog.ActionType.DELETED,
            description=f"Deleted Buy X Get Y promotion (ID: {pk}, {promo_info})"
        )
        
        return JsonResponse({'success': True})
    except:
        return JsonResponse({'success': False})


class supplierBuyXGiftYPromotionView(TemplateView):
    template_name = 'supplier/Buyxgiftypromotion.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'Buy X Gift Y Promotion'
        ctx['promotions'] = BuyXGiftYPromotion.objects.all()

        user = self.request.user

        if hasattr(user, 'supplierprofile'):
            ctx['suppliers'] = [user.supplierprofile]
            ctx['products'] = Product.objects.filter(created_by=user)
        else:
            ctx['suppliers'] = SupplierProfile.objects.all()
            ctx['products'] = Product.objects.all()

        return ctx


class supplierAddGiftPromotionView(TemplateView):
    def post(self, request):
        try:
            product_type = request.POST.get('product_type')
            if hasattr(request.user, 'supplierprofile'):
                supplier_ids = [request.user.supplierprofile.id]
            else:
                supplier_ids = request.POST.getlist('supplier')

            product_ids = request.POST.getlist('product')
            giftproduct_ids = request.POST.getlist('giftproduct')
            buy = request.POST.get('buy')
            gift = request.POST.get('gift')
            start = request.POST.get('start_datetime')
            end = request.POST.get('end_datetime')
            start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%M")
            end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M")
            promotion_period = f"{start_dt.strftime('%d %b %Y')} - {end_dt.strftime('%d %b %Y')}"

            promo = BuyXGiftYPromotion.objects.create(
                product_type=product_type,
                buy=buy,
                gift=gift,
                promotion_period=promotion_period
            )
            promo.supplier.set(supplier_ids)
            promo.product.set(product_ids)
            promo.giftproduct.set(giftproduct_ids)
            promo.save()
            user_log_activity(
                user=request.user,
                actions=UserActivityLog.ActionType.CREATED,
                description=f"Created Buy X Gift Y promotion (ID: {promo.id}, Buy: {buy}, Gift: {gift}, Period: {promotion_period})"
            )

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'msg': str(e)})


class supplierEditGiftPromotionView(TemplateView):
    def get(self, request, pk):
        try:
            promo = BuyXGiftYPromotion.objects.get(pk=pk)
            start_str, _, end_str = promo.promotion_period.partition(' - ')
            start_str = start_str.strip()
            end_str = end_str.strip()

            def fmt(dt_str):
                try:
                    dt = datetime.strptime(dt_str, "%d %b %Y")
                    return dt.strftime("%Y-%m-%dT00:00")
                except:
                    return ""

            data = {
                'product_type': promo.product_type,
                'supplier': list(promo.supplier.values_list('id', flat=True)),
                'product': list(promo.product.values_list('id', flat=True)),
                'giftproduct': list(promo.giftproduct.values_list('id', flat=True)),
                'buy': promo.buy,
                'gift': promo.gift,
                'start_datetime': fmt(start_str),
                'end_datetime': fmt(end_str),
            }
            return JsonResponse({'success': True, 'data': data})
        except BuyXGiftYPromotion.DoesNotExist:
            return JsonResponse({'success': False, 'msg': 'Promotion not found'})

    def post(self, request, pk):
        try:
            promo = BuyXGiftYPromotion.objects.get(pk=pk)

            promo.product_type = request.POST.get('product_type')
            promo.buy = request.POST.get('buy')
            promo.gift = request.POST.get('gift')

            if hasattr(request.user, 'supplierprofile'):
                promo.supplier.set([request.user.supplierprofile.id])
            else:
                promo.supplier.set(request.POST.getlist('supplier'))

            promo.product.set(request.POST.getlist('product'))
            promo.giftproduct.set(request.POST.getlist('giftproduct'))

            start = request.POST.get('start_datetime')
            end = request.POST.get('end_datetime')
            start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%M")
            end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M")
            promo.promotion_period = f"{start_dt.strftime('%d %b %Y')} - {end_dt.strftime('%d %b %Y')}"

            promo.save()
            user_log_activity(
                user=request.user,
                actions=UserActivityLog.ActionType.UPDATED,
                description=f"Updated Buy X Gift Y promotion (ID: {promo.id}, Buy: {promo.buy}, Gift: {promo.gift})"
            )
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'msg': str(e)})


def supplier_delete_gift_promotion(request, pk):
    try:
        promo = BuyXGiftYPromotion.objects.get(pk=pk)
        promo_info = f"Buy {promo.buy} Gift {promo.gift}"
        promo.delete()
        user_log_activity(
            user=request.user,
            actions=UserActivityLog.ActionType.DELETED,
            description=f"Deleted Buy X Gift Y promotion (ID: {pk}, {promo_info})"
        )
        
        return JsonResponse({'success': True})
    except Exception:
        return JsonResponse({'success': False})


class supplierBasketPromotionView(TemplateView):
    template_name = 'supplier/Basketpromotion.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Basket Promotions'
        context['promotions'] = BasketPromotion.objects.all().order_by('-created_at')

        user = self.request.user

        if hasattr(user, 'supplierprofile'):
            context['suppliers'] = [user.supplierprofile]
            context['products'] = Product.objects.filter(created_by=user)
        else:
            context['suppliers'] = SupplierProfile.objects.all()
            context['products'] = Product.objects.all()

        return context


class supplierAddBasketPromotionView(View):
    def post(self, request):
        try:
            product_type = request.POST.get('product_type')
            title_en = request.POST.get('title_en')
            time_limit = request.POST.get('time_limit')
            description_en = request.POST.get('description_en')
            main_image = request.FILES.get('main_image')
            start = request.POST.get('start_datetime')
            end = request.POST.get('end_datetime')
            start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%M")
            end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M")
            promotion_period = f"{start_dt.strftime('%d %b %Y')} - {end_dt.strftime('%d %b %Y')}"
            if hasattr(request.user, 'supplierprofile'):
                supplier_ids = [request.user.supplierprofile.id]
            else:
                supplier_ids = request.POST.getlist('supplier')

            product_ids = request.POST.getlist('product')
            promo = BasketPromotion.objects.create(
                product_type=product_type,
                promotion_period=promotion_period,
                time_limit=time_limit,
                title_en=title_en,
                description_en=description_en,
                main_image=main_image,
            )
            promo.supplier.set(supplier_ids)
            promo.product.set(product_ids)
            promo.save()
            user_log_activity(
                user=request.user,
                actions=UserActivityLog.ActionType.CREATED,
                description=f"Created basket promotion '{title_en}' (ID: {promo.id}, Period: {promotion_period})"
            )

            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'msg': str(e)})


class supplierEditBasketPromotionView(View):
    def get(self, request, pk):
        try:
            promo = BasketPromotion.objects.get(pk=pk)
            start_str, _, end_str = promo.promotion_period.partition(' - ')

            def parse_date(date_str):
                try:
                    return datetime.strptime(date_str.strip(), "%d %b %Y").strftime("%Y-%m-%dT%H:%M")
                except:
                    return ""

            data = {
                'product_type': promo.product_type,
                'supplier': list(promo.supplier.values_list('id', flat=True)),
                'product': list(promo.product.values_list('id', flat=True)),
                'title_en': promo.title_en or "",
                'time_limit': promo.time_limit or "",
                'description_en': promo.description_en or "",
                'main_image_url': promo.main_image.url if promo.main_image else "",
                'start_datetime': parse_date(start_str),
                'end_datetime': parse_date(end_str),
            }
            return JsonResponse({'success': True, 'data': data})

        except BasketPromotion.DoesNotExist:
            return JsonResponse({'success': False, 'msg': 'Promotion not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'msg': str(e)})

    def post(self, request, pk):
        try:
            promo = BasketPromotion.objects.get(pk=pk)

            promo.product_type = request.POST.get('product_type')
            promo.title_en = request.POST.get('title_en')
            promo.time_limit = request.POST.get('time_limit')
            promo.description_en = request.POST.get('description_en')

            if 'main_image' in request.FILES:
                if promo.main_image:
                    promo.main_image.delete(save=False)
                promo.main_image = request.FILES['main_image']
            if hasattr(request.user, 'supplierprofile'):
                promo.supplier.set([request.user.supplierprofile.id])
            else:
                promo.supplier.set(request.POST.getlist('supplier'))

            promo.product.set(request.POST.getlist('product'))
            start = request.POST.get('start_datetime')
            end = request.POST.get('end_datetime')
            start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%M")
            end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M")
            promo.promotion_period = f"{start_dt.strftime('%d %b %Y')} - {end_dt.strftime('%d %b %Y')}"

            promo.save()
            user_log_activity(
                user=request.user,
                actions=UserActivityLog.ActionType.UPDATED,
                description=f"Updated basket promotion '{promo.title_en}' (ID: {promo.id})"
            )
            
            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'msg': str(e)})


def supplier_delete_basket_promotion(request, pk):
    try:
        promo = BasketPromotion.objects.get(pk=pk)
        promo_title = promo.title_en
        if promo.main_image:
            promo.main_image.delete(save=False)  
        promo.delete()
        user_log_activity(
            user=request.user,
            actions=UserActivityLog.ActionType.DELETED,
            description=f"Deleted basket promotion '{promo_title}' (ID: {pk})"
        )
        
        return JsonResponse({'success': True})
    except BasketPromotion.DoesNotExist:
        return JsonResponse({'success': False, 'msg': 'Not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'msg': str(e)})
class SupplierContactUsView(FormView):
    template_name = "supplier/contact_us.html"
    form_class = ContactForm
    success_url = reverse_lazy('supplier:contact_us')

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contact_info'] = Contact.objects.filter(
            display_phone__isnull=False
        ).first()
        return context


class SupplierLogsView(TemplateView):
    template_name = 'supplier/supplierlogs.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['logs'] = UserActivityLog.objects.filter(
            user=self.request.user,
            is_deleted=False
        )

        return context
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from dashboard.models import ChatRoom, ChatMessage
from django.contrib.auth.models import User

class SupplierChatsView(LoginRequiredMixin, TemplateView):
    template_name = 'supplier/supplierchats.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        admin_user = User.objects.filter(is_staff=True, is_active=True).first()
        
        if admin_user:
            room, created = ChatRoom.objects.get_or_create(
                supplier=user,
                admin=admin_user
            )
            context['room'] = room
            context['room_id'] = room.id
        else:
            context['room'] = None
        
        context['current_user'] = user
        return context
