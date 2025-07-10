import json

from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render,redirect
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import logout
from dashboard.models import *
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseServerError
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import check_password
from datetime import timezone, datetime 
from django.db import IntegrityError
from django.utils.dateparse import parse_date
from django.utils.timezone import localtime
from django.db.models.functions import Coalesce,TruncDay
from django.db.models import Sum, F, DecimalField
from django.utils import timezone
from datetime import timedelta
from calendar import monthrange




class HomeView(LoginRequiredMixin, View):
    login_url = 'adminv2:admin_login'

    def get(self, request):
        user = request.user
        supplier_orders = Orders.objects.filter(order_to=user)
        total_orders = supplier_orders.count()
        subtotal = supplier_orders.annotate(
            product_total=F('product__price') * F('quantity')
        ).aggregate(
            total=Coalesce(Sum('product_total'), 0, output_field=DecimalField())
        )['total']

        top_categories = supplier_orders.annotate(
            category_name=F('product__category__name'),
            product_total=F('product__price') * F('quantity')
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
        
        daily_sales = Orders.objects.filter(
            order_to=user,
            created_at__date__range=(first_day.date(), last_day.date())
        ).annotate(
            day=TruncDay('created_at'),
            product_total=F('product__price') * F('quantity')
        ).values('day').annotate(
            total_sales=Sum('product_total')
        ).order_by('day')
        discounted_daily_sales = Orders.objects.filter(
            order_to=user,
            created_at__date__range=(first_day.date(), last_day.date()),
            product__offer_active=True
        ).annotate(
            day=TruncDay('created_at'),
            product_total=F('product__price') * F('quantity')
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
                sales_data[day_index] = float(sale['total_sales'])
        for sale in discounted_daily_sales:
            day_index = (sale['day'].date() - first_day.date()).days
            if 0 <= day_index < days_in_month:
                discounted_sales_data[day_index] = float(sale['total_sales'])

        this_month_sales = sum(sales_data)
        this_month_discounted_sales = sum(discounted_sales_data)
        previous_month = first_day - timedelta(days=1)
        previous_month_first_day = previous_month.replace(day=1)
        previous_month_last_day = previous_month.replace(day=monthrange(previous_month.year, previous_month.month)[1])
        
        previous_month_discounted_sales = Orders.objects.filter(
            order_to=user,
            created_at__date__range=(previous_month_first_day.date(), previous_month_last_day.date()),
            product__offer_active=True
        ).annotate(
            product_total=F('product__price') * F('quantity')
        ).aggregate(
            total=Coalesce(Sum('product_total'), 0, output_field=DecimalField())
        )['total']
        
        if previous_month_discounted_sales > 0:
            growth_percentage = ((this_month_discounted_sales - float(previous_month_discounted_sales)) / 
                                float(previous_month_discounted_sales)) * 100
        else:
            growth_percentage = 0
        this_month_customers = Orders.objects.filter(
            order_to=user,
            created_at__date__range=(first_day.date(), last_day.date())
        ).values('order_by').distinct().count()
        
        
        
        this_month_orders = Orders.objects.filter(
            order_to=user,
            created_at__date__range=(first_day.date(), last_day.date())
        ).count()

        # This week orders
        today = timezone.now()
        start_of_week = today - timedelta(days=today.weekday())  # Monday
        end_of_week = start_of_week + timedelta(days=6)          # Sunday

        this_week_orders = Orders.objects.filter(
            order_to=user,
            created_at__date__range=(start_of_week.date(), end_of_week.date())
        ).count()

        recent_orders = Orders.objects.filter(order_to=user).select_related('product', 'order_by').order_by('-created_at')[:6]
        context = {
            'total_orders': total_orders,
            'subtotal': subtotal,
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
                'growth_percentage': growth_percentage,
                'previous_month_total': float(previous_month_discounted_sales)
            }
        }
        return render(request, 'adminv2/home.html', context)

class ProductsView(LoginRequiredMixin,View):
    template = 'adminv2/products.html'
    def get(self, request):
        products = Product.objects.all()

        for product in products:
            image = ProductImage.objects.filter(product=product).first()
            product.image_url = image.image.url if image else '/static/adminv2/media/stock/ecommerce/placeholder.png'

        return render(request, self.template, {'products': products})
    
    
class AddproductsView(LoginRequiredMixin, View):
    template = 'adminv2/add-product.html'

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
        return_time = self._parse_int(data.get('return_time_limit'), min_value=0)
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

    
        if offer_start and offer_end and offer_end < offer_start:
            messages.warning(request, "Offer end date cannot be before start date.")

        # Set offer active based on user role
        if request.user.is_superuser:
            offer_active = data.get('offer_active') == 'on'
        else:
            offer_active = False

        ask_admin_to_publish = data.get('ask_admin_to_publish') == 'on'

        brand_name = data.get('brand')
        brand = None
        if brand_name:
            brand, _ = Brand.objects.get_or_create(name=brand_name)

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
                return_time_limit=return_time or 0,
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

         
            main_image = files.get('main_image')
            if main_image:
                ProductImage.objects.create(product=product, image=main_image, is_main=True)

            gallery_images = files.getlist('gallery_images')
            for img in gallery_images:
                ProductImage.objects.create(product=product, image=img, is_main=False)

            messages.success(request, "Product added successfully.")
            return redirect('adminv2:products_list')

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

   

    
class EditproductsView(LoginRequiredMixin, View):
    template = 'adminv2/edit-product.html'

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        product_images = ProductImage.objects.filter(product=product)
        main_image = product_images.filter(is_main=True).first()
        gallery_images = product_images.filter(is_main=False)
        categories = ProductCategory.objects.all()
        subcategories = ProductSubCategory.objects.filter(category=product.category) if product.category else ProductSubCategory.objects.none()
        lastcategories = ProductLastCategory.objects.filter(sub_category=product.sub_category) if product.sub_category else ProductLastCategory.objects.none()
        selling_countries = product.selling_countries if product.selling_countries else ''
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
            product.name = request.POST.get('product_name')
            product.description = request.POST.get('product_description')
            product.price = request.POST.get('price')
            product.stock_quantity = request.POST.get('product_quantity')
            product.product_from = request.POST.get('product_from')
            product.selling_countries = request.POST.get('selling_countries', '')
            product.warranty = request.POST.get('warranty', 'none')
            product.condition = request.POST.get('condition', 'new')
            product.return_time_limit = request.POST.get('return_time_limit')
            product.manufacture_date = request.POST.get('manufacture_date')
            product.expiry_date = request.POST.get('expiry_date')
            product.weight = request.POST.get('weight')
            product.weight_unit = request.POST.get('weight_unit', 'gm')
            product.delivery_time = request.POST.get('delivery_time')
            product.commission_percentage = request.POST.get('commission_percentage')
            product.barcode = request.POST.get('barcode')
            product.keywords = request.POST.get('keywords')
            product.supplier_sku = request.POST.get('supplier_sku')
            product.pcs_per_unit = request.POST.get('pcs_per_unit')
            product.min_order_qty = request.POST.get('min_order_qty')
            product.low_stock_alert = request.POST.get('low_stock_alert')
            product.expiration_days = request.POST.get('expiration_days')
            product.tag = request.POST.get('tag', 'none')

            offer_percentage = request.POST.get('offer_percentage')
            if offer_percentage:
                product.offer_percentage = offer_percentage

            start_offer = request.POST.get('offer_start')
            end_offer = request.POST.get('offer_end')

            if start_offer:
                product.offer_start = start_offer

            if end_offer:
                product.offer_end = end_offer

            product.is_active = request.POST.get('is_active') == 'True'
            category_id = request.POST.get('category')
            if category_id:
                try:
                    product.category = ProductCategory.objects.get(pk=category_id)
                except ProductCategory.DoesNotExist:
                    product.category = None
            sub_category_id = request.POST.get('sub_category')
            if sub_category_id:
                try:
                    product.sub_category = ProductSubCategory.objects.get(pk=sub_category_id)
                except ProductSubCategory.DoesNotExist:
                    product.sub_category = None
            last_category_id = request.POST.get('last_category')
            if last_category_id:
                try:
                    product.last_category = ProductLastCategory.objects.get(pk=last_category_id)
                except ProductLastCategory.DoesNotExist:
                    product.last_category = None

            if 'main_image' in request.FILES:
                ProductImage.objects.filter(product=product, is_main=True).delete()
                ProductImage.objects.create(
                    product=product,
                    image=request.FILES['main_image'],
                    is_main=True
                )
            if 'gallery_images' in request.FILES:
                for image in request.FILES.getlist('gallery_images'):
                    ProductImage.objects.create(
                        product=product,
                        image=image,
                        is_main=False
                    )
            brand_name = request.POST.get('brand')
            if brand_name:
                    brand_obj, created = Brand.objects.get_or_create(name=brand_name)
                    product.brand = brand_obj

            if 'brochure' in request.FILES:
                product.brochure = request.FILES['brochure']

            product.save()

            messages.success(request, 'Product updated successfully!')
        except Exception as e:
            print('exception in edit product --- ',e)
            messages.error(request, 'Issue in Product updated !')

        return redirect('adminv2:products_list')  
        
   
    
class DeleteProductImageView(LoginRequiredMixin, View):
    def post(self, request, pk):
        image = get_object_or_404(ProductImage, pk=pk)
        product_id = image.product.id
        image.delete()
        return redirect('adminv2:edit_product', pk=product_id)
    
    def get(self, request, pk):
        return self.post(request, pk)
    
class DeleteProductView(LoginRequiredMixin,View):
    def post(self, request, pk):
        try:
            product = get_object_or_404(Product, pk=pk)
            product.delete()
            messages.success(request, "Product deleted successfully")
            return JsonResponse({'success': True})
        except Exception as e:
            messages.error(request, "Faild to delect product.")
            return JsonResponse({'success': False})
   
class CreateProductCategoryView(View):
    def post(self, request):
        name = request.POST.get('name')
        if not name:
            messages.error(request, "Category name is required.")
            return redirect('adminv2:add_product')

        if ProductCategory.objects.filter(name__iexact=name).exists():
            messages.warning(request, "This category already exists.")
            return redirect('adminv2:add_product')

        ProductCategory.objects.create(name=name)
        messages.success(request, f"Category '{name}' created successfully.")
        return redirect('adminv2:add_product')

class CreateProductSubCategoryView(View):
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
        return redirect('adminv2:add_product')
    
class CreateProductLastCategoryView(View):
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
        return redirect('adminv2:add_product')
    
class GetSubcategoriesView(View):
    def get(self, request, *args, **kwargs):
        category_id = request.GET.get('category_id')
        if category_id:
            subcats = ProductSubCategory.objects.filter(category_id=category_id).values('id', 'name')
            return JsonResponse(list(subcats), safe=False)
        return JsonResponse([], safe=False)

class GetLastCategoriesView(View):
    def get(self, request, *args, **kwargs):
        sub_id = request.GET.get('sub_id')
        if sub_id:
            lastcats = ProductLastCategory.objects.filter(sub_category_id=sub_id).values('id', 'name')
            return JsonResponse(list(lastcats), safe=False)
        return JsonResponse([], safe=False)



class AdminloginView(View):
    def get(self, request):
        return render(request, 'adminv2/sign-in.html')

    def post(self, request):
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)

            if user is not None:
                if hasattr(user, 'supplierprofile'):
                    login(request, user)
                    return redirect('adminv2:admin_v2') 
                else:
                    messages.error(request, "Only suppliers are allowed to log in.")
            else:
                messages.error(request, "Invalid email or password.")
        except User.DoesNotExist:
            messages.error(request, "User with this email does not exist.")

        return render(request, 'adminv2/sign-in.html')
    
class OrderListingView(View):
    def get(self, request):
        status_filter = request.GET.get('status')

        orders = Orders.objects.select_related('order_by', 'product')
        if status_filter and status_filter != '':
            orders = orders.filter(status=status_filter)

        total_orders = Orders.objects.count()
        completed_orders = Orders.objects.filter(status='completed').count()
        pending_orders = Orders.objects.filter(status='pending').count()
        cancelled_orders = Orders.objects.filter(status='cancelled').count()

        context = {
            'orders': orders,
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'pending_orders': pending_orders,
            'cancelled_orders': cancelled_orders,
            'selected_status': status_filter,
        }
        return render(request, 'adminv2/order-listing.html', context)

    
class OrderDetailesView(View):
    def get(self, request, pk):
        order = get_object_or_404(Orders, pk=pk)
        product = order.product
        brand = product.brand.name if product.brand else '-'
        user = order.order_by 
        
        subtotal = float(order.price) * order.quantity
        commission = (float(order.price) * float(product.commission_percentage) / 100) * order.quantity
        shipping_fee = float(order.shipping_fees) if order.shipping_fees else 0

        grand_total = subtotal - commission + shipping_fee
        
        
        context = {
            'order': order,
            'product': product,
            'brand': brand,
            'user': user,
            'subtotal': round(subtotal, 2),
            'total_commission': round(commission, 2),
            'shipping_fee': round(shipping_fee, 2),
            'grand_total': round(grand_total, 2),
           
        }
        return render(request, 'adminv2/order-detailes.html', context)
    
class OrderDeleteView(View):
    def post(self, request, pk):
        order = get_object_or_404(Orders, pk=pk)
        order.delete()
        return JsonResponse({'success': True})

class UserProfileView(View):
    def get(self, request):
        return render(request, 'adminv2/user-profile.html')

class UserOverView(View):
    def get(self, request):
        return render(request, 'adminv2/overview.html')

class AdminSettingView(View):
    def get(self, request):
        return render(request, 'adminv2/settings.html')

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
            return redirect('adminv2:profile_setting')

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

            return redirect('adminv2:profile_setting')

class CompanyDetailsView(LoginRequiredMixin, View):
    template = "adminv2/company_details.html"

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
            return redirect("adminv2:company_details")

        except Exception as e:
            print("Exception in saving profile:", e)
            messages.error(request, "Failed to update company details. Please try again.")
            return redirect("adminv2:company_details")

class WishlistProductView(LoginRequiredMixin,View):
    template = 'adminv2/wishlist_product.html'

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
                return redirect('adminv2:wishlist_products_list')

            except Exception as e:
                print("Exception as e ----", e)
                messages.error(request, "Failed to add to cart, please try again")
                return redirect('adminv2:wishlist_products_list')

        if mode == 'remove-wishlist':
            try:
                item = get_object_or_404(WishlistProduct, id=product_id)
                item.delete()

                messages.success(request, "Removed from Wishlist")
                return redirect('adminv2:wishlist_products_list')

            except Exception as e:
                messages.error(request, "Faild to remove, please try again")
                return redirect('adminv2:wishlist_products_list')

class CartProductsView(LoginRequiredMixin, View):
    template = "adminv2/cart_product.html"

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

class MarkNotificationReadView(View):
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


class MarkNotificationReadView(View):
    def post(self, request, pk):
        notif = Notification.objects.get(pk=pk)
        notif.is_read = True
        notif.save()
        return JsonResponse({
            "title": notif.title,
            "message": notif.message,
            "created_at": localtime(notif.created_at).strftime('%d %b %Y, %I:%M %p')
        })


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('adminv2:admin_login') 



























