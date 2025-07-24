from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Prefetch, F, Sum
from django.http import JsonResponse, Http404, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.dateparse import parse_date
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView
from django.core.paginator import EmptyPage,PageNotAnInteger
from adminv3.filters import QS_filter_user, QS_Products_filter, QS_orders_filters
from adminv3.mixins import StaffAccountRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from adminv3.utils import requestParamsToDict
from dashboard.models import RetailProfile, WholesaleBuyerProfile, SupplierProfile, Product, ProductImage, \
    ProductCategory, ProductLastCategory, ProductSubCategory, Brand, Order, OrderItem
from django.conf import settings


class HomeView(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    login_url = 'dashboard:login'
    template_name = 'adminv3/home.html'

    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('dashboard:login')
        return render(request, self.template_name)


class UsersAccounts(LoginRequiredMixin, PermissionRequiredMixin, StaffAccountRequiredMixin, ListView):
    required_permissions = ('auth.view_user',)
    template_name = 'adminv3/users/users_list.html'
    model = User
    context_object_name = 'users'
    paginate_by = 25

    def get_queryset(self):
        filter_dict = requestParamsToDict(self.request, get_params=True)
        return QS_filter_user(filter_dict)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Summary counts
        context['total_users'] = User.objects.count()
        context['retail_users'] = RetailProfile.objects.count()
        context['wholesale_users'] = WholesaleBuyerProfile.objects.count()
        context['supplier_users'] = SupplierProfile.objects.count()

        # Add filter values back to template
        context['selected_role'] = self.request.GET.get('user_type', '')
        context['account_status'] = self.request.GET.get('account_status', '')
        context['account_role'] = self.request.GET.get('account_role', '')
        context['sort_by'] = self.request.GET.get('sort_by', '')
        context['search_query'] = self.request.GET.get('search_by', '')
        context['permission_groups'] = Group.objects.all()

        return context


class UserDetailView(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    template_name = 'adminv3/users/user_details.html'

    def get(self, request, *args, **kwargs):
        user = get_object_or_404(User, pk=kwargs['pk'])
        user_permission_groups = user.groups.all()
        permission_group_list = Group.objects.all()

        context = {
            'user': user,
            'retail_profile': RetailProfile.objects.filter(user=user).first(),
            'wholesale_profile': WholesaleBuyerProfile.objects.filter(user=user).first(),
            'supplier_profile': SupplierProfile.objects.filter(user=user).first(),
            'user_permission_groups': user_permission_groups,
            'permission_group_list': permission_group_list,
        }
        return render(request, self.template_name, context)


class User_Accounts_Update_Profile(StaffAccountRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        if not request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)

        user_id = kwargs.get('pk')
        post_dict = request.POST

        try:
            user = User.objects.get(pk=user_id)

            user.first_name = post_dict.get('user_first_name', '').strip()
            user.last_name = post_dict.get('user_last_name', '').strip()

            user.save()

            return JsonResponse({'status': 'valid', 'message': 'Profile has been updated!'}, status=200)

        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'User not found!'}, status=404)

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': 'Check details and try again!'}, status=400)


class User_Accounts_Change_Email(StaffAccountRequiredMixin, View):

    def post(self, request, *args, **kwargs):
        if not request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)

        user_id = kwargs.get('pk')
        post_dict = request.POST

        post_dict = requestParamsToDict(self.request, post_params=True)

        user_new_email = post_dict.get('user_new_email', None)
        if user_new_email is None:
            return JsonResponse({'status': 'error', 'message': 'Invalid Email'}, status=400)

        user_obj = User.objects.get(pk=user_id)

        if User.objects.filter(email__iexact=user_new_email).exists():
            return JsonResponse({'status': 'error', 'message': 'Email already exists.'}, status=400)

        try:
            user_obj.email = user_new_email
            user_obj.save()

            return JsonResponse(
                {'status': 'valid', 'message': 'Email has been changed and all previous sessions has been deleted.'},
                status=200)
        except:
            pass

        return JsonResponse({'status': 'error', 'message': 'Check details and try again!'}, status=400)


class User_Accounts_Change_Password(StaffAccountRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        if not request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)

        user_id = kwargs.get('pk')
        post_dict = request.POST

        user_obj = User.objects.get(pk=user_id)
        new_password = post_dict.get('new_password', None)
        confirm_password = post_dict.get('confirm_password', None)

        if len(new_password) >= 8 and new_password == confirm_password:
            user_obj.set_password(new_password)
            user_obj.save()

            return JsonResponse(
                {'status': 'valid', 'message': 'Password has been changed and all previous sessions has been deleted.'},
                status=200)
        return JsonResponse({'status': 'error', 'message': 'Check details and try again!'}, status=400)


class UserUpdateAccountStatusView(View):
    http_method_names = ['post']

    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        user_id = kwargs.get('pk')
        post_dict = request.POST

        user_obj = User.objects.get(pk=user_id)
        account_status = request.POST.get('account_status', 'active')

        if account_status == 'inactive':
            user_obj.is_active = False
        else:
            user_obj.is_active = True

        user_obj.save()

        return JsonResponse({'status': 'success', 'message': 'Account status updated successfully.'})


class User_Accounts_Update_Role(StaffAccountRequiredMixin, View):
    def post(self, request, *args, **kwargs):

        user_id = kwargs.get('pk')
        post_dict = request.POST

        if not request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)

        post_dict = requestParamsToDict(self.request, post_params=True)
        account_role = post_dict.get('account_role', None)

        if account_role is None:
            return JsonResponse({'status': 'error', 'message': 'Invalid Account Role'}, status=400)

        user_obj = User.objects.get(pk=user_id)

        try:

            if account_role == 'user':
                user_obj.is_staff = False
                user_obj.is_superuser = False
            elif account_role == 'admin':
                user_obj.is_staff = True
                user_obj.is_superuser = True
            elif account_role == 'staff':
                user_obj.is_staff = True
                user_obj.is_superuser = False

            user_obj.save()

            return JsonResponse({'status': 'valid', 'message': 'Account role has been updated.'}, status=200)
        except:
            pass

        return JsonResponse({'status': 'error', 'message': 'Check details and try again!'}, status=400)


class User_Accounts_Delete_Account(StaffAccountRequiredMixin, View):
    def post(self, request, *args, **kwargs):

        user_id = kwargs.get('pk')
        post_dict = request.POST

        user_obj = User.objects.get(pk=user_id)

        if user_obj.pk == 1:
            return JsonResponse({'status': 'error', 'message': 'This account can not be deleted!'}, status=400)
        user = user_obj
        try:
            user_obj.delete()

            return JsonResponse({'status': 'valid', 'message': 'Account has been deleted.'}, status=200)
        except Exception as e:
            print(f"Error while terminating task: {str(e)}")

        return JsonResponse({'status': 'error', 'message': 'Check details and try again!'}, status=400)


class User_Accounts_Modify_Permission_Groups(StaffAccountRequiredMixin, View):

    def post(self, request, *args, **kwargs):
        user_id = kwargs.get('pk')
        post_dict = request.POST

        user_obj = User.objects.get(pk=user_id)

        if not request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)

        try:
            user_modify_groups_list = request.POST.getlist('user_modify_groups_list')
            selected_group_ids = [int(_) for _ in user_modify_groups_list if _.isdigit()]

            user_obj.groups.clear()

            new_groups = Group.objects.filter(id__in=selected_group_ids)
            user_obj.groups.add(*new_groups)


            return JsonResponse({'status': 'valid', 'message': 'Permission Groups has been updated.'}, status=200)
        except Exception as e:
            print("error  --",e)
            pass

        return JsonResponse({'status': 'error', 'message': 'Check details and try again!'}, status=400)


class User_Accounts_AddNewUser(StaffAccountRequiredMixin, View):

    def post(self, request, *args, **kwargs):
        if not request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)

        post_dict = requestParamsToDict(self.request, post_params=True)

        # check 1 - check username already exists or not
        if User.objects.filter(username__iexact=post_dict.get('user_username')).exists():
            return JsonResponse({'status': 'error', 'message': 'Username is already exist.'}, status=400)

        # check 2 - check email already exists or not
        if User.objects.filter(email__iexact=post_dict.get('user_email_address')).exists():
            return JsonResponse({'status': 'error', 'message': 'Email is already exist.'}, status=400)

        # check 3- check if email has + sign
        if '+' in post_dict.get('user_email_address'):
            return JsonResponse({'status': 'error', 'message': 'Invalid Email! Plus(+) sign is not allowed.'},
                                status=400)

        account_role = post_dict.get('account_role', None)
        if account_role == 'user':
            is_staff_status = False
            is_admin_status = False
        elif account_role == 'admin':
            is_staff_status = True
            is_admin_status = True
        elif account_role == 'staff':
            is_staff_status = True
            is_admin_status = False
        else:
            is_staff_status = False
            is_admin_status = False

        account_type = post_dict.get('account_type', None)
        print(account_type)


        try:
            user_obj = User.objects.create_user(first_name=post_dict.get('user_first_name'),
                                                     last_name=post_dict.get('user_last_name'),
                                                     username=post_dict.get('user_username'),
                                                     email=post_dict.get('user_email_address'),
                                                     password=post_dict.get('new_password'),
                                                     is_superuser=is_admin_status,
                                                     is_staff=is_staff_status
                                                     )

            user_obj.save()


            created_user_role =""
            if is_admin_status:
                created_user_role = "Administrator"
            if is_staff_status:
                created_user_role = "Staff"
            else:
                created_user_role = "User"


            if account_type == 'retailer':
                RetailProfile.objects.create(user=user_obj)

            elif account_type == 'wholesaler':
                WholesaleBuyerProfile.objects.create(
                    user=user_obj,
                    company_name='Default Company',
                    gst_number='N/A',
                    department='N/A',
                    purchase_capacity=0
                )

            elif account_type == 'supplier':
                SupplierProfile.objects.create(
                    user=user_obj,
                    company_name='Default Company',
                    license_number='N/A'
                )

            return JsonResponse({'status': 'valid', 'message': 'New User has been added successfully!'}, status=200)
        except:
            pass


        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


GROUP_PERMISSIONS_MODELS_LIST = ['user', 'product', 'order']

class PermissionsUsers(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    template_name = 'adminv3/permissions/permissions.html'

    def get(self, request, *args, **kwargs):
        skipped_permissions = ['delete_order', 'add_order', 'change_order']


        groups = Group.objects.all().order_by('pk')
        permissions_by_model = {}
        for model_name in GROUP_PERMISSIONS_MODELS_LIST:
            content_types = ContentType.objects.filter(model=model_name)
            model_permissions = Permission.objects.filter(content_type__in=content_types)

            permissions_by_model[model_name] = [_ for _ in model_permissions if not _.codename in skipped_permissions]


        context = {
            'groups': groups,
            'permissions_by_model': permissions_by_model
        }

        return render(request, self.template_name, context)


class User_Permissions_AddNewGroup(StaffAccountRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        if not request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)

        post_data = request.POST
        group_name = post_data.get('group_name', None)

        if not group_name:
            return JsonResponse({'status': 'error', 'message': 'Check details and try again!'}, status=400)

        if Group.objects.filter(name=group_name).exists():
            return JsonResponse({'status': 'error', 'message': 'Group is already exist!'}, status=400)

        try:
            permissions = [perm for model in GROUP_PERMISSIONS_MODELS_LIST for perm in post_data.getlist(model) if
                           perm != 'all']
            if len(permissions) < 1:
                return JsonResponse({'status': 'error', 'message': 'At least 1 permission is required!'}, status=400)

            group_obj = Group.objects.create(name=group_name)
            permission_objs = Permission.objects.filter(codename__in=permissions)
            group_obj.permissions.add(*permission_objs)

            return JsonResponse({'status': 'valid', 'message': 'Group has been added.'}, status=200)
        except:
            return JsonResponse({'status': 'error', 'message': 'Check details and try again!'}, status=400)


class User_Permissions_DeleteGroup(View):

    def post(self, request, *args, **kwargs):
        try:
            id = request.POST.get('group_id')
            group_obj = Group.objects.get(pk=id)
        except Group.DoesNotExist:
            raise Http404()

        # check if group is assigned to any user then throw error
        if User.objects.filter(groups=group_obj).exists():
            return JsonResponse(
                {'message': f"Cannot delete the group '{group_obj.name}' because it is assigned to users."}, status=400)

        try:

            group_obj.delete()
            return JsonResponse({'message': 'success'}, status=200)
        except:
            pass
        return JsonResponse({'status': 'error'}, status=400)


class User_Permissions_EditGroup(StaffAccountRequiredMixin, View):

    def get(self, request, *args, **kwargs):
        try:
            if request.headers.get('HX-Request'):
                id = kwargs['UID']

                skipped_permissions = ['delete_order', 'add_order', 'change_order']

                group_obj = get_object_or_404(Group, pk=id)

                permissions_by_model = {}

                for model_name in GROUP_PERMISSIONS_MODELS_LIST:
                    content_types = ContentType.objects.filter(model=model_name)
                    model_permissions = Permission.objects.filter(content_type__in=content_types)

                    filtered_permissions = [p for p in model_permissions if p.codename not in skipped_permissions]

                    group_permissions = set(group_obj.permissions.values_list('codename', flat=True))

                    all_selected = all(p.codename in group_permissions for p in filtered_permissions)

                    permissions_by_model[model_name] = {
                        'permissions': filtered_permissions,
                        'all_selected': all_selected
                    }

                context = {
                    'group': group_obj,
                    'permissions_by_model': permissions_by_model,
                    'group_permissions': list(group_obj.permissions.values_list('codename', flat=True))
                }

                return render(request, 'adminv3/permissions/snippets/form/_form_permission_group_edit.html', context)

        except Exception as e:
            return HttpResponse("Something went wrong! Contact Support", status=500, content_type="text/html")


    def post(self, request, *args, **kwargs):
        if not request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)

        id = kwargs['UID']
        group_obj = get_object_or_404(Group, pk=id)

        post_data = request.POST
        group_name = post_data.get('group_name', None)

        if not group_name:
            return JsonResponse({'status': 'error', 'message': 'Check details and try again!'}, status=400)

        try:
            group_obj.permissions.clear()
            group_obj.name = group_name

            permissions = [
                perm for model in GROUP_PERMISSIONS_MODELS_LIST
                for perm in post_data.getlist(f'{model}_permissions[]') if perm != 'all'
            ]

            print(f"Gathered permissions: {permissions}")

            if len(permissions) < 1:
                return JsonResponse({'status': 'error', 'message': 'At least 1 permission is required!'}, status=400)

            permission_objs = Permission.objects.filter(codename__in=permissions)
            group_obj.permissions.add(*permission_objs)
            group_obj.save()
            return JsonResponse({'status': 'valid', 'message': 'Group has been updated.'}, status=200)

        except Exception as e:

            return JsonResponse({'status': 'error', 'message': 'Check details and try again!'}, status=400)


# class ProductsListView(LoginRequiredMixin, StaffAccountRequiredMixin, View):
#     template_name = 'adminv3/products/products_list.html'
#
#
#     def get(self, request):
#         user = request.user
#         products = Product.objects.all().order_by('-created_at')
#
#         for product in products:
#             image = ProductImage.objects.filter(product=product).first()
#             product.image_url = image.image.url if image else '/static/adminv2/media/stock/ecommerce/placeholder.png'
#
#         return render(request, self.template_name, {'products': products})

class ProductsListView(LoginRequiredMixin,StaffAccountRequiredMixin, PermissionRequiredMixin, ListView):
    required_permissions = ('dashboard.view_product',)
    model = Product
    template_name = 'adminv3/products/products_list.html'
    context_object_name = "products"
    paginate_by = 25

    def get_queryset(self):
        filter_dict = requestParamsToDict(self.request, get_params=True)
        qs = QS_Products_filter(filter_dict)

        for product in qs:
            image = ProductImage.objects.filter(product=product).first()
            product.image_url = image.image.url if image else '/static/adminv2/media/stock/ecommerce/placeholder.png'

        return qs

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)
        context['category'] = ProductCategory.objects.all()
        return context


class AddproductsView(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    template = 'adminv3/products/add_product.html'

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
            return redirect('adminv3:products_list')

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


class EditproductsView(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    template = 'adminv3/products/edit_product.html'

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

        return redirect('adminv3:products_list')

class DeleteProductView(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    def post(self, request, pk):
        try:
            product = get_object_or_404(Product, pk=pk)
            product.delete()
            messages.success(request, "Product deleted successfully")
        except Exception as e:
            messages.error(request, "Failed to delete product.")
        return redirect('adminv3:products_list')  # or wherever the list is

class CreateProductCategoryView(StaffAccountRequiredMixin, View):
    def post(self, request):
        name = request.POST.get('name')
        if not name:
            messages.error(request, "Category name is required.")
            return redirect('adminv3:add_product')

        if ProductCategory.objects.filter(name__iexact=name).exists():
            messages.warning(request, "This category already exists.")
            return redirect('adminv3:add_product')

        ProductCategory.objects.create(name=name)
        messages.success(request, f"Category '{name}' created successfully.")
        return redirect('adminv3:add_product')

class CreateProductSubCategoryView(StaffAccountRequiredMixin, View):
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
        return redirect('adminv3:add_product')

class CreateProductLastCategoryView(StaffAccountRequiredMixin, View):
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
        return redirect('adminv3:add_product')


class DeleteProductImageView(StaffAccountRequiredMixin, View):
    def post(self, request, pk):
        image = get_object_or_404(ProductImage, pk=pk)
        product_id = image.product.id
        image.delete()
        return redirect('adminv3:edit_product', pk=product_id)

    def get(self, request, pk):
        return self.post(request, pk)


class OrderListingView(StaffAccountRequiredMixin, PermissionRequiredMixin, View):
    template_name = 'adminv3/orders/orders_list.html'
    paginate_by = 25
    required_permissions = ('dashboard.view_order',)

    def get(self, request):

        # Collect all filters
        filter_dict = {
            "order_status": request.GET.get("order_status", "all"),
            "payment_status": request.GET.get("payment_status", "all"),
            "search_by": request.GET.get("search_by"),
            "sort_by": request.GET.get("sort_by", "desc_created"),
            "payment_type": request.GET.get("payment_type", "all"),
            "created_date": request.GET.get("created_date", None),

        }

        base_queryset = QS_orders_filters(filter_dict)

        item_queryset = OrderItem.objects.all().annotate(
            item_total=F("price") * F("quantity")
        )

        orders_queryset = base_queryset.all().distinct().select_related(
            "user", "payment"
        ).prefetch_related(
            Prefetch("items", queryset=item_queryset, to_attr="filtered_items")
        )

        # Apply pagination
        page = request.GET.get("page", 1)
        paginator = Paginator(orders_queryset, self.paginate_by)

        try:
            orders = paginator.page(page)
        except PageNotAnInteger:
            orders = paginator.page(1)
        except EmptyPage:
            orders = paginator.page(paginator.num_pages)

        # Totals and phone mapping
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

        # Status counters (with supplier restriction)
        supplier_orders = base_queryset.all().distinct()
        total_orders = supplier_orders.count()
        completed_orders = supplier_orders.filter(status='completed').count()
        pending_orders = supplier_orders.filter(status='pending').count()
        cancelled_orders = supplier_orders.filter(status='cancelled').count()

        context = {
            "orders": orders,
            "page_obj":orders,
            "order_totals": order_totals,
            "order_phones": order_phones,
            "total_orders": total_orders,
            "completed_orders": completed_orders,
            "pending_orders": pending_orders,
            "cancelled_orders": cancelled_orders,
            "selected_status": filter_dict["order_status"],
            "selected_payment": filter_dict["payment_status"],
            "selected_sort_by": filter_dict["sort_by"],
            "search_by": filter_dict["search_by"],
        }

        return render(request, self.template_name, context)

class OrderDetailesView(StaffAccountRequiredMixin, View):
    template_name = 'adminv3/orders/order_details.html'

    def get(self, request, order_id):

        order = get_object_or_404(
            Order.objects.all().distinct().select_related('user', 'payment').prefetch_related(
                Prefetch('items', queryset=OrderItem.objects.select_related('product', 'order_by', 'order_to').prefetch_related(
                    Prefetch('product__productimage_set', queryset=ProductImage.objects.filter(is_main=True), to_attr='main_image')
                ))
            ),
            order_id=order_id
        )

        # Calculate totals for supplier's order items
        order_items = order.items.all()
        if not order_items.exists():
            logger.warning(f"Supplier {supplier.id} attempted to view order {order.id} with no relevant items")
            messages.error(request, "You do not have permission to view this order.")
            return redirect('adminv2:order_listing')

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

        return render(request, self.template_name , context)

class OrderDeleteView(StaffAccountRequiredMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        order.delete()
        return JsonResponse({'success': True})
