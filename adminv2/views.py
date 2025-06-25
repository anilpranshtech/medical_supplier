from django.views import View
from django.shortcuts import render,redirect
from django.contrib import messages
from dashboard.models import *
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse   
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import check_password
from datetime import date, timezone, datetime  # Import date for date conversion
from django.db import IntegrityError
from django.utils.dateparse import parse_date


class HomeView(LoginRequiredMixin, UserPassesTestMixin, View):
    login_url = 'adminv2:admin_login'
    def get(self, request):
        return render(request, 'adminv2/base.html')
    
    def test_func(self):
        return self.request.user.is_superuser
    
class ProductsView(LoginRequiredMixin, UserPassesTestMixin,View):
    template = 'adminv2/products.html'
    def get(self, request):
        products = Product.objects.all()

        for product in products:
            image = ProductImage.objects.filter(product=product).first()
            product.image_url = image.image.url if image else '/static/adminv2/media/stock/ecommerce/placeholder.png'

        return render(request, self.template, {'products': products})
    def test_func(self):
        return self.request.user.is_superuser
    
class AddproductsView(LoginRequiredMixin, UserPassesTestMixin, View):
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
        price = self._parse_float(data.get('price'), "Price")
        stock_quantity = self._parse_int(data.get('product_quantity'), "Quantity", min_value=0)
        commission = self._parse_float(data.get('commission_percentage'), "Commission %", 0, 100)
        offer_percentage = self._parse_float(data.get('offer_percentage'), "Offer %", 0, 100)
        pcs_per_unit = self._parse_int(data.get('pcs_per_unit'), "Pcs/Unit", min_value=1)
        min_order_qty = self._parse_int(data.get('min_order_qty'), "Min Order Qty", min_value=1)
        low_stock_alert = self._parse_int(data.get('low_stock_alert'), "Low Stock", min_value=0)
        expiration_days = self._parse_int(data.get('expiration_days'), "Expiration Days", min_value=0, required=False)
        return_time = self._parse_int(data.get('return_time_limit'), "Return Time", min_value=0, required=False)
        delivery_time = self._parse_int(data.get('delivery_time'), "Delivery Time", min_value=0, required=False)
        weight = self._parse_float(data.get('weight'), "Weight", min_value=0, required=False)

        manufacture_date = self._parse_date(data.get('manufacture_date'), "Manufacture Date")
        expiry_date = self._parse_date(data.get('expiry_date'), "Expiry Date")
        offer_start = self._parse_date(data.get('offer_start'), "Offer Start")
        offer_end = self._parse_date(data.get('offer_end'), "Offer End")

        if offer_start and offer_end and offer_end < offer_start:
            messages.error(request, "Offer end date cannot be before start date.")

        if not name:
            messages.error(request, "Product name is required.")
        if not description:
            messages.error(request, "Product description is required.")
        if price is None:
            messages.error(request, "Valid price is required.")

        if messages.get_messages(request):
            return self._render_form_with_context(request, data)

        brand_name = data.get('brand')
        brand = None
        if brand_name:
            brand, _ = Brand.objects.get_or_create(name=brand_name)

        try:
            product = Product.objects.create(
                name=name,
                description=description,
                price=price,
                stock_quantity=stock_quantity,
                brand=brand,
                category=self._get_object(ProductCategory, data.get('category')),
                sub_category=self._get_object(ProductSubCategory, data.get('sub_category')),
                last_category=self._get_object(ProductLastCategory, data.get('last_category')),
                product_from=data.get('product_from'),
                warranty=data.get('warranty'),
                condition=data.get('condition'),
                manufacture_date=manufacture_date,
                expiry_date=expiry_date,
                weight=weight,
                selling_countries=selling_countries,

                weight_unit=data.get('weight_unit'),
                barcode=data.get('barcode'),
                commission_percentage=commission,
                return_time_limit=return_time,
                delivery_time=delivery_time,
                keywords=data.get('keywords'),
                brochure=files.get('brochure'),
                supplier_sku=data.get('supplier_sku'),
                pcs_per_unit=pcs_per_unit,
                min_order_qty=min_order_qty,
                low_stock_alert=low_stock_alert,
                expiration_days=expiration_days,
                tag=data.get('tag'),
                offer_percentage=offer_percentage,
                offer_start=offer_start,
                offer_end=offer_end,
                is_active=(data.get('is_active') == 'True'),
                offer_active=(offer_percentage and offer_start and offer_end and offer_start <= date.today() <= offer_end)
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

    def _parse_float(self, val, field, min_value=None, max_value=None, required=True):
        try:
            f = float(val)
            if (min_value is not None and f < min_value) or (max_value is not None and f > max_value):
                raise ValueError
            return f
        except:
            if required or val:
                messages.error(self.request, f"Invalid {field}.")
            return None

    def _parse_int(self, val, field, min_value=None, required=True):
        try:
            i = int(val)
            if min_value is not None and i < min_value:
                raise ValueError
            return i
        except:
            if required or val:
                messages.error(self.request, f"Invalid {field}.")
            return None

    def _parse_date(self, val, field):
        try:
            return parse_date(val)
        except:
            if val:
                messages.error(self.request, f"Invalid {field}. Format must be YYYY-MM-DD.")
            return None

    def _get_object(self, model, pk):
        if not pk:
            return None
        try:
            return model.objects.get(id=pk)
        except model.DoesNotExist:
            messages.error(self.request, f"{model.__name__} not found.")
            return None

    def _render_form_with_context(self, request, data):
        return render(request, self.template, {
            'categories': ProductCategory.objects.all(),
            'subcategories': ProductSubCategory.objects.all(),
            'lastcategories': ProductLastCategory.objects.all(),
            **data.dict()
        })

    def test_func(self):
        return self.request.user.is_superuser
    
class EditproductsView(LoginRequiredMixin, UserPassesTestMixin,View):
    template = 'adminv2/edit-product.html'

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        product_image = ProductImage.objects.filter(product=product).first()
        categories = ProductCategory.objects.all()
        product_category = product.category
        product_quantity = product.stock_quantity
        context = {
            'product': product,
            'product_image': product_image,
            'categories': categories,
            'product_category': product_category,
            'product_quantity': product_quantity,
        }
        return render(request, self.template, context)

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        product.name = request.POST.get('product_name')
        product.description = request.POST.get('description')
        product.price = request.POST.get('price')
        product.stock_quantity = request.POST.get('product_quantity')

        category_id = request.POST.get('category')
        if category_id:
            try:
                product.category = ProductCategory.objects.get(pk=category_id)
            except ProductCategory.DoesNotExist:
                product.category = None

        product.save()

        if 'avatar' in request.FILES:
            image_file = request.FILES['avatar']
            product_image, created = ProductImage.objects.get_or_create(product=product)
            product_image.image = image_file
            product_image.save()
        
        messages.success(request, 'Changes saved successfully!')
        return redirect('adminv2:products_list')  
        
    def test_func(self):
        return self.request.user.is_superuser
    

class DeleteProductView(LoginRequiredMixin, UserPassesTestMixin,View):
    def post(self, request, pk):
        print("hello")
        product = get_object_or_404(Product, pk=pk)
        product.delete()
        return JsonResponse({'success': True})
    
    def test_func(self):
        return self.request.user.is_superuser

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
                if user.is_superuser:
                    login(request, user)
                    return redirect('adminv2:products_list')
                else:
                    messages.error(request, "Only superusers are allowed to log in.")
            else:
                messages.error(request, "Invalid email or password.")
        except User.DoesNotExist:
            messages.error(request, "User with this email does not exist.")

        return render(request, 'adminv2/sign-in.html')

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

class WishlistProductView(LoginRequiredMixin,View):
    template = 'adminv2/wishlist_product.html'

    def get(self,request, *args,**kwargs):

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

                CartProduct.objects.create(
                    user=item.user,
                    product=item.product,
                    quantity=item.quantity,
                    created_at=datetime.now()
                )

                item.delete()

                messages.success(request, "Added to card")
                return redirect('adminv2:wishlist_products_list')

            except Exception as e:
                print("Exception as e ----", e)
                messages.error(request, "Faild to Add in cart, please try again")
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



