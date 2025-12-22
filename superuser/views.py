import stripe
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Prefetch, F, Sum, Avg, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse, Http404, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView
from django.core.paginator import EmptyPage,PageNotAnInteger
from django.views.generic import ListView, CreateView, UpdateView, View
from django.urls import reverse_lazy
from datetime import datetime
import re
from django.views.decorators.csrf import csrf_exempt
import supplier
from superuser.filters import QS_filter_user, QS_Products_filter, QS_orders_filters
from superuser.mixins import StaffAccountRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.hashers import make_password
import requests
from .refunds import process_refund
from .utils import *
from dashboard.models import *
from django.conf import settings
#from superuser.forms import *
from superuser.models import *
from django.views.generic import TemplateView
from .forms import BannerForm
from django.views.generic.edit import UpdateView
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from dashboard.models import RFQRequest
from .forms import SuperuserRFQQuotationForm
from django.views.generic import TemplateView, View
from supplier.models import Banner 
from supplier.forms import BannerForm  
from superuser.forms import BannerForm
from django.views import View
from django.db.models import Avg, Count, Q, Sum, Value
from django.db.models.functions import Coalesce
from datetime import datetime, timedelta
from django.shortcuts import render
from django.db.models import Count, Q
import logging
logger = logging.getLogger(__name__)
from utils.adminlogs import *

class HomeView(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    template_name = 'superuser/home.html'
    login_url = 'dashboard:login'
    redirect_field_name = None


    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('dashboard:login')

        total_order_price = OrderItem.objects.aggregate(
            total=Sum(F('price') * F('quantity'))
        )['total'] or 0
                        
        total_products = Product.objects.count()
        total_payments = Payment.objects.count()
        successful_payments = Payment.objects.filter(paid=True).count()
        unpaid_payments = total_payments - successful_payments
        total_orders = Order.objects.count()
        total_event = Event.objects.count()
        
        order_status_counts = {
            'pending': Order.objects.filter(status='pending').count(),
            'completed': Order.objects.filter(status='completed').count(),
            'processing': Order.objects.filter(status='processing').count(),
            'shipped': Order.objects.filter(status='shipped').count(),
            'delivered': Order.objects.filter(status='delivered').count(),
            'delivering': Order.objects.filter(status='delivering').count(),
            'cancelled': Order.objects.filter(status='cancelled').count(),
            'refunded': Order.objects.filter(status='refunded').count(),
            'failed': Order.objects.filter(status='failed').count(),
        }

        payment_data = {
            'paid': successful_payments,
            'unpaid': unpaid_payments,
        }

        return render(request, self.template_name, {
            'total_order_price': total_order_price,
            'total_products': total_products,
            'order_status_counts': order_status_counts,
            'total_payments': total_payments,
            'successful_payments': successful_payments,
            'total_orders': total_orders, 
            'total_event': total_event,
            'payment_data': payment_data, 
        })


class UsersAccounts(LoginRequiredMixin, PermissionRequiredMixin, StaffAccountRequiredMixin, ListView):
    required_permissions = ('auth.view_user',)
    template_name = 'superuser/users/users_list.html'
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
    template_name = 'superuser/users/user_details.html'

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

    def post(self, request, *args, **kwargs):
        user = get_object_or_404(User, pk=kwargs['pk'])
        profile, created = AdminUserProfile.objects.get_or_create(user=user)

        if 'delete_profile_picture' in request.POST:
            if profile.profile_picture:
                profile.profile_picture.delete()
                profile.profile_picture = None
            profile.save()
        elif 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']
            profile.save()

        return redirect('superuser:user_detail', pk=user.pk)


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

            #Retail Profile 
            retail_profile = RetailProfile.objects.filter(user=user).first()
            if retail_profile:
                retail_profile.age = post_dict.get('age', '').strip()
                retail_profile.medical_needs = post_dict.get('medical_needs', '').strip()
                retail_profile.save()

            #Wholesale Profile
            wholesale_profile = WholesaleBuyerProfile.objects.filter(user=user).first()
            if wholesale_profile:
                wholesale_profile.company_name = post_dict.get('company_name', '').strip()
                wholesale_profile.gst_number = post_dict.get('gst_number', '').strip()
                wholesale_profile.department = post_dict.get('department', '').strip()
                wholesale_profile.purchase_capacity = post_dict.get('purchase_capacity', '').strip()
                wholesale_profile.save()

            #Supplier Profie
            supplier_profile = SupplierProfile.objects.filter(user=user).first()
            if supplier_profile:
                supplier_profile.company_name = post_dict.get('company_name', '').strip()
                supplier_profile.license_number = post_dict.get('license_number', '').strip()
                supplier_profile.save()
            admin_update_activity(
                request.user,
                f"Updated profile details for user: {user.username}"
            )

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
            admin_password_change_activity(request.user)
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
        status_text = "Activated" if user_obj.is_active else "Deactivated"

        admin_update_activity(
        request.user,
        f"{status_text} account for user {user_obj.username}"
        )
   
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
            admin_update_activity(
            request.user,
           f"Updated role of user {user_obj.username} to {account_role}"
           )

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
            username = user_obj.username
            user_obj.delete()

            admin_delete_activity(
            request.user,
           f"Deleted user account: {username}"
            )


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

            group_names = list(new_groups.values_list('name', flat=True))

            admin_update_activity(
            request.user,
            f"Updated permission groups for {user_obj.username}: {', '.join(group_names)}"
            )

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
        # if '+' in post_dict.get('user_email_address'):
        #     return JsonResponse({'status': 'error', 'message': 'Invalid Email! Plus(+) sign is not allowed.'},
        #                         status=400)

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
            admin_create_activity(
            request.user,
            f"Created new {account_type} account: {user_obj.username}"
            )

            return JsonResponse({'status': 'valid', 'message': 'New User has been added successfully!'}, status=200)
        except:
            pass


        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


GROUP_PERMISSIONS_MODELS_LIST = ['user', 'product', 'productcategory','order', 'return', 'rfqrequest', 'banner', 'ratingreview',
  'question', 'topsupplier', 'vacationrequest', 'coupon', 'buyxgetypromotion', 'buyxgiftypromotion',
  'basketpromotion', 'notification',]

class PermissionsUsers(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    template_name = 'superuser/permissions/permissions.html'

    def get(self, request, *args, **kwargs):
        skipped_permissions = ['add_order', 'add_return',
                               'add_rfqrequest',
                               'add_ratingreview', 'change_ratingreview', 'delete_ratingreview',
                               'add_question',
                               'add_vacationrequest', 'delete_vacationrequest']


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

            admin_create_activity(
            request.user,
            f"Created permission group '{group_name}' with {len(permission_objs)} permissions"
            )

            return JsonResponse({'status': 'valid', 'message': 'Group has been added.'}, status=200)
        except:
            return JsonResponse({'status': 'error', 'message': 'Check details and try again!'}, status=400)
class User_Permissions_DeleteGroup(View):

    def post(self, request, *args, **kwargs):
        try:
            group_id = request.POST.get('group_id')
            group_obj = Group.objects.get(pk=group_id)
        except Group.DoesNotExist:
            admin_failed_activity(
                request.user,
                f"Attempted to delete non-existing permission group ID {request.POST.get('group_id')}"
            )
            raise Http404()
        if User.objects.filter(groups=group_obj).exists():
            return JsonResponse(
                {'message': f"Cannot delete the group '{group_obj.name}' because it is assigned to users."},
                status=400
            )
        try:
            group_name = group_obj.name
            group_obj.delete()
            admin_delete_activity(
                request.user,
                f"Deleted permission group '{group_name}'"
            )
            return JsonResponse({'message': 'success'}, status=200)
        except Exception as e:
            admin_failed_activity(
                request.user,
                f"Failed to delete permission group '{group_obj.name}'. Error: {str(e)}"
            )
            return JsonResponse({'status': 'error', 'message': 'Check details and try again!'}, status=400)

class User_Permissions_EditGroup(StaffAccountRequiredMixin, View):

    def get(self, request, *args, **kwargs):
        try:
            if request.headers.get('HX-Request'):
                id = kwargs['UID']

                skipped_permissions = ['add_order', 'add_rfqrequest', 'add_return',
                                       'add_ratingreview', 'change_ratingreview', 'delete_ratingreview', 'view_ratingrevie',
                                       'add_question',
                                       'add_vacationrequest', 'delete_vacationrequest']

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

                return render(request, 'superuser/permissions/snippets/form/_form_permission_group_edit.html', context)

        except Exception as e:
            admin_failed_activity(
                request.user,
                f"Failed to load edit form for permission group ID {kwargs.get('UID')}"
            )
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
            old_group_name = group_obj.name  # store old name for logging
            group_obj.permissions.clear()
            group_obj.name = group_name

            permissions = [
                perm for model in GROUP_PERMISSIONS_MODELS_LIST
                for perm in post_data.getlist(f'{model}_permissions[]') if perm != 'all'
            ]

            if len(permissions) < 1:
                return JsonResponse({'status': 'error', 'message': 'At least 1 permission is required!'}, status=400)

            permission_objs = Permission.objects.filter(codename__in=permissions)
            group_obj.permissions.add(*permission_objs)
            group_obj.save()

            # --- Log successful update ---
            admin_update_activity(
                request.user,
                f"Updated permission group '{old_group_name}' to '{group_name}' with {len(permission_objs)} permissions"
            )

            return JsonResponse({'status': 'valid', 'message': 'Group has been updated.'}, status=200)

        except Exception as e:
            # --- Log failure ---
            admin_failed_activity(
                request.user,
                f"Failed to update permission group '{group_obj.name}'"
            )
            return JsonResponse({'status': 'error', 'message': 'Check details and try again!'}, status=400)



# class ProductsListView(LoginRequiredMixin, StaffAccountRequiredMixin, View):
#     template_name = 'superuser/products/products_list.html'
#
#
#     def get(self, request):
#         user = request.user
#         products = Product.objects.all().order_by('-created_at')
#
#         for product in products:
#             image = ProductImage.objects.filter(product=product).first()
#             product.image_url = image.image.url if image else '/static/supplier/media/stock/ecommerce/placeholder.png'
#
#         return render(request, self.template_name, {'products': products})


class ProductsListView(LoginRequiredMixin,StaffAccountRequiredMixin, PermissionRequiredMixin, ListView):
    required_permissions = ('dashboard.view_product',)
    model = Product
    template_name = 'superuser/products/products_list.html'
    context_object_name = "products"
    paginate_by = 25

    def get_queryset(self):
        filter_dict = requestParamsToDict(self.request, get_params=True)
        qs = QS_Products_filter(filter_dict)

        for product in qs:
            image = ProductImage.objects.filter(product=product).first()
            product.image_url = image.image.url if image else '/static/supplier/media/stock/ecommerce/placeholder.png'

        return qs

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)
        context['category'] = ProductCategory.objects.all()
        return context


class AddproductsView(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    template = 'superuser/products/add_product.html'

    def get(self, request):
        context = {
            'categories': ProductCategory.objects.all(),
            'subcategories': ProductSubCategory.objects.all(),
            'lastcategories': ProductLastCategory.objects.all(),
            'suppliers': SupplierProfile.objects.all()
        }
        return render(request, self.template, context)

    def post(self, request):
        data = request.POST
        files = request.FILES
        name = data.get('product_name')
        description = data.get('product_description')
        selling_countries = data.get('selling_countries')
        base_price = self._parse_float(data.get('base_price'), min_value=1, max_value=999999)
        discount_option = data.get('discount_option')
        offer_percentage = self._parse_float(data.get('offer_percentage'), min_value=0, max_value=100)
        fixed_discounted_price = self._parse_float(data.get('discount_price'))  # Changed to match form field name
        stock_quantity = self._parse_int(data.get('product_quantity'), min_value=0)
        commission = self._parse_float(data.get('commission_percentage'), min_value=0, max_value=100)
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
        supplier = data.get('supplier')

        # Calculate discount_price
        discount_price = None
        if discount_option == '2' and base_price and offer_percentage:
            discount_price = base_price * (1 - offer_percentage / 100)
        elif discount_option == '3' and fixed_discounted_price:
            discount_price = fixed_discounted_price
        elif discount_option == '1':
            discount_price = base_price

        # Validate supplier
        try:
            sup_user = SupplierProfile.objects.get(id=supplier)
        except SupplierProfile.DoesNotExist:
            messages.error(request, "Selected supplier does not exist.")
            return self._render_form_with_context(request, data)

        # Validate offer dates
        if offer_start and offer_end and offer_end < offer_start:
            messages.warning(request, "Offer end date cannot be before start date.")
            return self._render_form_with_context(request, data)

        # Set offer active based on user role
        offer_active = data.get('offer_active') == 'on' if request.user.is_superuser else False
        ask_admin_to_publish = data.get('ask_admin_to_publish') == 'on'

        # Handle brand creation
        brand_name = data.get('brand')
        brand = None
        if brand_name:
            brand, _ = Brand.objects.get_or_create(
                name=brand_name,
                defaults={'supplier': sup_user.user}
            )

        # Validate required fields
        if not base_price:
            messages.error(request, "Base price is required and must be between 1 and 999999.")
            return self._render_form_with_context(request, data)

        try:
            product = Product.objects.create(
                name=name or '',
                description=description or '',
                price=base_price or 0,
                discount_price=discount_price,
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
                created_by=sup_user.user
            )

            # Handle event for event categories
            category_obj = self._get_object(ProductCategory, data.get('category'))
            if self._is_event_category(category_obj):
                event = Event.objects.create(
                    conference_link=data.get('registration_link') or None,
                    speaker_name=data.get('webinar_name') or None,
                    conference_at=self._parse_date(data.get('webinar_date')) or None,
                    duration=self._parse_duration(data.get('webinar_duration')) or None,
                    venue=data.get('webinar_venue') or None,
                )
                product.event = event
                product.save()

            # Handle images
            main_image = files.get('main_image')
            if main_image:
                ProductImage.objects.create(product=product, image=main_image, is_main=True)

            gallery_images = files.getlist('gallery_images')
            for img in gallery_images:
                ProductImage.objects.create(product=product, image=img, is_main=False)
            admin_create_activity(
            request.user,
            f"Created product '{product.name}' (ID: {product.id})"
            )


            messages.success(request, "Product added successfully.")
            return redirect('superuser:products_list')

        except IntegrityError as e:
            messages.error(request, f"Integrity error: {e}")
        except Exception as e:
            messages.error(request, f"Error: {e}")

        return self._render_form_with_context(request, data)

    def _is_event_category(self, category):
        event_keywords = ['conference', 'event', 'webinar']
        if category and category.name:
            return category.name.lower() in event_keywords
        return False

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
        if not val:
            return None
        return parse_datetime(val) or parse_date(val)

    def _parse_duration(self, val):
        if not val:
            return None
        try:
            if ":" in val:  # HH:MM[:SS]
                parts = list(map(int, val.split(":")))
                while len(parts) < 3:
                    parts.append(0)  # pad missing seconds/minutes
                h, m, s = parts
                return timedelta(hours=h, minutes=m, seconds=s)
            else:
                # assume number = hours
                return timedelta(hours=int(val))
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
            'suppliers': SupplierProfile.objects.all(),
            **data.dict()
        })


class EditproductsView(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    template = 'superuser/products/edit_product.html'

    def get_context_data(self, pk):
        product = get_object_or_404(Product, pk=pk)
        product_images = ProductImage.objects.filter(product=product)
        main_image = product_images.filter(is_main=True).first()
        gallery_images = product_images.filter(is_main=False)
        categories = ProductCategory.objects.all()

        # Determine discount_option
        if product.discount_price is None and (product.offer_percentage is None or product.offer_percentage == 0):
            discount_option = '1'
        elif product.offer_percentage and product.offer_percentage > 0:
            discount_option = '2'
        else:
            discount_option = '3'

        # Fetch event details
        event = product.event
        registration_link = event.conference_link if event else ''
        webinar_name = event.speaker_name if event else ''
        webinar_date = event.conference_at.strftime('%Y-%m-%dT%H:%M') if event and event.conference_at else ''
        webinar_duration = str(event.duration) if event and event.duration else ''
        webinar_venue = event.venue if event else ''

        is_returnable = product.return_time_limit > 0

        return {
            'pk': pk,
            'product': product,
            'product_name': product.name,
            'product_description': product.description,
            'price': product.price,
            'base_price': product.price,
            'discount_price': product.discount_price or '',
            'discount_option': discount_option,
            'offer_percentage': product.offer_percentage or 0,
            'discounted_price': product.discount_price or '',
            'product_quantity': product.stock_quantity,
            'product_from': product.product_from,
            'selling_countries': product.selling_countries or '',
            'warranty': product.warranty,
            'condition': product.condition,
            'is_returnable': is_returnable,
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
            'offer_active': product.offer_active,
            'brand': product.brand.name if product.brand else '',
            'categories': categories,
            'category_id': product.category.id if product.category else None,
            'selected_sub_category': product.sub_category.id if product.sub_category else None,
            'selected_sub_category_name': product.sub_category.name if product.sub_category else '',
            'selected_last_category': product.last_category.id if product.last_category else None,
            'selected_last_category_name': product.last_category.name if product.last_category else '',
            'main_image_url': main_image.image.url if main_image else None,
            'gallery_images': gallery_images,
            'brochure_url': product.brochure.url if product.brochure else None,
            'subcategories': ProductSubCategory.objects.filter(category=product.category) if product.category else ProductSubCategory.objects.none(),
            'lastcategories': ProductLastCategory.objects.filter(sub_category=product.sub_category) if product.sub_category else ProductLastCategory.objects.none(),
            'suppliers': SupplierProfile.objects.all(),
            'sup_selected': product.created_by.email,
            'sup_selected_id': product.created_by.id,
            'registration_link': registration_link,
            'webinar_name': webinar_name,
            'webinar_date': webinar_date,
            'webinar_duration': webinar_duration,
            'webinar_venue': webinar_venue,
        }

    def get(self, request, pk):
        context = self.get_context_data(pk)
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
            if not product.name:
                raise ValueError("Product name is required")
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

            # Returnable toggle
            product.is_returnable = data.get('is_returnable') == 'on'
            product.return_time_limit = self._parse_int(data.get('return_time_limit'), min_value=0) if product.is_returnable else 0

            # Dates
            product.manufacture_date = self._parse_date(data.get('manufacture_date'))
            product.expiry_date = self._parse_date(data.get('expiry_date'))
            product.offer_start = self._parse_date(data.get('offer_start')) if data.get('offer_start') else None
            product.offer_end = self._parse_date(data.get('offer_end')) if data.get('offer_end') else None

            # Offer status
            product.offer_active = data.get('offer_active') == 'on'

            # Discount handling
            discount_option = data.get('discount_option')
            offer_percentage = self._parse_decimal(data.get('offer_percentage'), min_value=Decimal('0.00'), max_value=Decimal('100.00'))
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
                    product.price = base_price
                    product.offer_percentage = 0
                    product.discount_price = discounted_price

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
                brand_obj, _ = Brand.objects.get_or_create(name=brand_name)
                product.brand = brand_obj
            else:
                product.brand = None

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

            # Event details
            if is_webinar:
                registration_link = data.get('registration_link')
                speaker_name = data.get('webinar_name')
                conference_at_str = data.get('webinar_date')
                duration_str = data.get('webinar_duration')
                venue = data.get('webinar_venue')

                if not all([registration_link, speaker_name, conference_at_str, duration_str, venue]):
                    raise ValueError("All event fields are required for Webinar/Conference/Event")

                event = product.event if product.event else Event()
                event.conference_link = registration_link
                event.speaker_name = speaker_name
                event.conference_at = datetime.strptime(conference_at_str, '%Y-%m-%dT%H:%M')

                try:
                    parts = duration_str.split(':')
                    if len(parts) == 3:
                        h, m, s = map(int, parts)
                    elif len(parts) == 2:
                        h, m = map(int, parts)
                        s = 0
                    elif len(parts) == 1:
                        h, m, s = 0, int(parts[0]), 0
                    else:
                        raise ValueError
                    event.duration = timedelta(hours=h, minutes=m, seconds=s)
                except ValueError:
                    raise ValueError("Invalid duration format. Use HH:MM[:SS] or just MM")

                event.venue = venue
                event.save()
                product.event = event
            else:
                product.event = None

            product.save()

            # Debug: Verify saved values
            saved_product = Product.objects.get(pk=pk)
            print(f"After save - product.price: {saved_product.price}, product.offer_percentage: {saved_product.offer_percentage}, product.discount_price: {saved_product.discount_price}")
            admin_update_activity(
            request.user,
            f"Updated product '{product.name}' (ID: {product.id})"
            )

            messages.success(request, 'Product updated successfully!')
            return redirect('superuser:products_list')

        except Exception as e:
            print(f'Exception in edit product: {str(e)}')
            messages.error(request, f'Issue in Product update: {str(e)}')
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

        # Determine discount_option
        discount_option = data.get('discount_option', '1')
        if discount_option not in ['1', '2', '3']:
            if product.discount_price is None and (product.offer_percentage is None or product.offer_percentage == 0):
                discount_option = '1'
            elif product.offer_percentage and product.offer_percentage > 0:
                discount_option = '2'
            else:
                discount_option = '3'

        return render(request, self.template, {
            'pk': product.id,
            'product': product,
            'product_name': data.get('product_name', product.name),
            'product_description': data.get('product_description', product.description),
            'base_price': data.get('base_price', product.price),
            'discount_price': data.get('discount_price', product.discount_price or ''),
            'discount_option': discount_option,
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
            'suppliers': SupplierProfile.objects.all(),
            'sup_selected': data.get('supplier', product.created_by.email),
            'sup_selected_id': data.get('supplier', product.created_by.id),
            'registration_link': data.get('registration_link', ''),
            'webinar_name': data.get('webinar_name', ''),
            'webinar_date': data.get('webinar_date', ''),
            'webinar_duration': data.get('webinar_duration', ''),
            'webinar_venue': data.get('webinar_venue', ''),
        })
class DeleteProductView(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    def post(self, request, pk):
        try:
            product = get_object_or_404(Product, pk=pk)
            product_name = product.name
            product.delete()

            admin_delete_activity(
                request.user,
                f"Deleted product '{product_name}' (ID: {pk})"
            )

            messages.success(request, "Product deleted successfully")

        except Exception as e:
            admin_failed_activity(
                request.user,
                f"Failed to delete product ID {pk}: {str(e)}"
            )
            messages.error(request, "Failed to delete product.")

        return redirect('superuser:products_list')

class CreateProductCategoryView(StaffAccountRequiredMixin, View):
    def post(self, request):
        name = request.POST.get('name')
        if not name:
            messages.error(request, "Category name is required.")
            return redirect('superuser:add_product')

        if ProductCategory.objects.filter(name__iexact=name).exists():
            messages.warning(request, "This category already exists.")
            return redirect('superuser:add_product')

        ProductCategory.objects.create(name=name)
        messages.success(request, f"Category '{name}' created successfully.")
        return redirect('superuser:add_product')


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
        return redirect('superuser:add_product')
    


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
        return redirect('superuser:add_product')


class DeleteProductImageView(StaffAccountRequiredMixin, View):
    def post(self, request, pk):
        image = get_object_or_404(ProductImage, pk=pk)
        product_id = image.product.id
        image.delete()
        return redirect('superuser:edit_product', pk=product_id)

    def get(self, request, pk):
        return self.post(request, pk)


class OrderListingView( PermissionRequiredMixin, View):
    template_name = 'superuser/orders/orders_list.html'
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
class UpdatePaymentStatusView(View):
    def post(self, request):
        order_id = request.POST.get("order_id")
        paid = request.POST.get("paid")

        if paid not in ["True", "False"]:
            return JsonResponse({"success": False, "error": "Invalid status"})

        try:
            order = get_object_or_404(Order, order_id=order_id)

            if not order.items.filter(order_to=request.user).exists():
                return JsonResponse({"success": False, "error": "Permission denied"})

            if not order.payment:
                return JsonResponse({"success": False, "error": "Payment not found"})

            order.payment.paid = True if paid == "True" else False
            order.payment.save(update_fields=["paid"])
            admin_update_activity(
                request.user,
                f"Updated payment status for Order {order.order_id} to "
                f"{'Paid' if order.payment.paid else 'Unpaid'}"
            )

            return JsonResponse({
                "success": True,
                "paid": order.payment.paid
            })

        except Exception as e:
            admin_failed_activity(
                request.user,
                f"Failed to update payment status for Order {order_id}: {str(e)}"
            )
            return JsonResponse({"success": False, "error": "Something went wrong"}, status=500)

class OrderListAndStatusView(View):
    template_name = 'superuser/orders/orders.html'

    def get(self, request):
        status = request.GET.get('status')
        orders = Order.objects.select_related('user', 'payment')
        if status:
            orders = orders.filter(status=status)

        context = {
            'orders': orders,
            'selected_status': status,
            'total_orders': Order.objects.count(),
            'completed_orders': Order.objects.filter(status='completed').count(),
            'pending_orders': Order.objects.filter(status='pending').count(),
            'cancelled_orders': Order.objects.filter(status='cancelled').count(),
        }
        return render(request, self.template_name, context)

    def post(self, request):
        order_id = request.POST.get('order_id')
        status = request.POST.get('status')

        try:
            order = get_object_or_404(Order, order_id=order_id)
            valid_statuses = dict(Order._meta.get_field('status').choices)

            if status not in valid_statuses:
                return JsonResponse({'success': False, 'error': 'Invalid status'})
            old_status = order.status
            order.status = status
            if status == 'delivered':
                order.delivered_at = timezone.now()
            order.save()
            admin_update_activity(
                request.user,
                f"Changed order status for Order {order.order_id} "
                f"from '{old_status}' to '{status}'"
            )

            return JsonResponse({'success': True})

        except Exception as e:
            admin_failed_activity(
                request.user,
                f"Failed to change order status for Order {order_id}: {str(e)}"
            )
            return JsonResponse({'success': False, 'error': 'Something went wrong'}, status=500)

class ChangeOrderStatusView(View):
    def post(self, request):
        order_id = request.POST.get('order_id')
        new_status = request.POST.get('status')
        if not order_id or not new_status:
            return JsonResponse({'success': False, 'message': 'Invalid data'}, status=400)
        try:
            order = get_object_or_404(Order, order_id=order_id)
            old_status = order.status
            order.status = new_status
            if new_status == 'delivered':
                order.delivered_at = timezone.now()
            order.save()
            admin_update_activity(
                request.user,
                f"Updated order status for Order {order.order_id} "
                f"from '{old_status}' to '{new_status}'"
            )
            return JsonResponse({
                'success': True,
                'new_status': new_status
            })
        except Exception as e:
            admin_failed_activity(
                request.user,
                f"Failed to update order status for Order {order_id}: {str(e)}"
            )
            return JsonResponse({'success': False, 'message': 'Something went wrong'}, status=500)

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
            return redirect('superuser:order_listing')
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
        return render(request, 'superuser/orders/order_details.html', context)



class OrderDeleteView(StaffAccountRequiredMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        order.delete()
        return JsonResponse({'success': True})

    
class RatingView(TemplateView):
    template_name = "superuser/rating.html"

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


# class MostViewedProductsView(View):
#     def get(self, request):
#         products = Product.objects.annotate(
#             delivered_count=Count(
#                 'orderitem',
#                 filter=Q(orderitem__status='delivered'),
#                 distinct=True
#             ),
#             review_count=Count(
#                 'reviews',
#                 distinct=True
#             )
#         ).prefetch_related(
#             Prefetch(
#                 'productimage_set',
#                 queryset=ProductImage.objects.order_by('-is_main', '-created_at'),
#                 to_attr='images'
#             )
#         ).order_by('-delivered_count')

#         # Attach a display image to each product
#         for product in products:
#             if product.images:
#                 main_images = [img for img in product.images if img.is_main]
#                 product.display_image = main_images[0] if main_images else product.images[0]
#             else:
#                 product.display_image = None

#         # All payments
#         payments = Payment.objects.all()

#         # Paid Money
#         paid_money = payments.filter(paid=True).aggregate(total=Sum('amount'))['total'] or 0

#         # Unpaid Money
#         unpaid_money = payments.filter(paid=False).aggregate(total=Sum('amount'))['total'] or 0

#         # Cash Money (COD only)
#         cash_money = payments.filter(payment_method="cod").aggregate(total=Sum('amount'))['total'] or 0

#         # Define context dictionary
#         context = {
#             'total_orders': paid_money,
#             'pending_orders': unpaid_money,
#             'cash_money': cash_money,
#             'orders': payments,
#             'products': products,
#         }

#         # Render template with context
#         return render(request, "superuser/view_product.html", context)



class BannerListView(LoginRequiredMixin, TemplateView):
    template_name = 'superuser/banner_list.html'
    # required_permissions = ('dashboard.view_banner')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = BannerForm()
        banners = Banner.objects.all()

        # ---- Filters ----
        search_query = self.request.GET.get('search', '')  
        is_active = self.request.GET.get('is_active', '')
        order = self.request.GET.get('order', '')

        if search_query:
            banners = banners.filter(title__icontains=search_query)
        if is_active in ['0', '1']:
            banners = banners.filter(is_active=bool(int(is_active)))
        if order:
            try:
                banners = banners.filter(order=int(order))
            except ValueError:
                pass

        # ---- Pagination (3 per page) ----
        paginator = Paginator(banners, 3)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        # Context
        context['page_obj'] = page_obj
        context['banners'] = page_obj.object_list  
        context['search'] = search_query
        context['is_active'] = is_active
        context['order'] = order

        return context
class BannerCreateView(LoginRequiredMixin, View):
    def get(self, request):
        form = BannerForm()
        return render(request, 'superuser/banner_upload.html', {'form': form})

    def post(self, request):
        form = BannerForm(request.POST, request.FILES)

        if form.is_valid():
            banner = form.save()

            admin_log_activity(
                request.user,
                f"Created banner ID {banner.id}",
                AdminActivityLog.ActionType.CREATED
            )

            return redirect('superuser:banner_list')

        return render(request, 'superuser/banner_upload.html', {'form': form})


class BannerUpdateView(LoginRequiredMixin, View):
    def get(self, request, pk):
        banner = get_object_or_404(Banner, pk=pk)
        form = BannerForm(instance=banner)
        return render(request, 'superuser/banner_edit.html', {
            'form': form,
            'object': banner
        })

    def post(self, request, pk):
        banner = get_object_or_404(Banner, pk=pk)
        form = BannerForm(request.POST, request.FILES, instance=banner)

        if form.is_valid():
            banner = form.save()

            admin_log_activity(
                request.user,
                f"Updated banner ID {banner.id}",
                AdminActivityLog.ActionType.UPDATED
            )

            return redirect('superuser:banner_list')

        return render(request, 'superuser/banner_edit.html', {
            'form': form,
            'object': banner
        })



class AdminRFQListView(LoginRequiredMixin, ListView):
    template_name = 'superuser/rfq_list.html'
    context_object_name = 'rfqs'
    paginate_by = 10   

    def get_queryset(self):
        user = self.request.user
        queryset = RFQRequest.objects.all()

        # Apply filters
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
                created_at_from = datetime.strptime(created_at_from, '%Y-%m-%d')
                queryset = queryset.filter(created_at__gte=created_at_from)
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


class AdminQuotationUpdateView(UpdateView):
    model = RFQRequest
    form_class = SuperuserRFQQuotationForm
    template_name = 'superuser/rfq_quotation_form.html'
    success_url = reverse_lazy('superuser:rfq_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comments'] = self.object.comments.all()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        # === 1. ADD COMMENT ===
        if 'add_comment' in request.POST:
            comment_text = request.POST.get('comment', '').strip()
            if comment_text:
                RFQComment.objects.create(
                    rfq=self.object,
                    comment=comment_text,
                    commented_by=request.user,
                )
                messages.success(request, "Comment added.")
            else:
                messages.error(request, "Comment cannot be empty.")
            return redirect('superuser:rfq_quote', pk=self.object.pk)

        # === 2. ADD ADMIN REPLY ===
        if 'add_reply' in request.POST:
            reply_to_id = request.POST.get('reply_to')
            reply_text = request.POST.get('admin_reply', '').strip()

            if not reply_to_id or not reply_text:
                messages.error(request, "Invalid reply.")
                return redirect('superuser:rfq_quote', pk=self.object.pk)

            try:
                comment = RFQComment.objects.get(id=reply_to_id, rfq=self.object)
                if comment.admin_reply:
                    messages.error(request, "Reply already exists.")
                else:
                    comment.admin_reply = reply_text
                    comment.replied_at = timezone.now()
                    comment.save()
                    messages.success(request, "Reply saved.")
            except RFQComment.DoesNotExist:
                messages.error(request, "Comment not found.")
            return redirect('superuser:rfq_quote', pk=self.object.pk)

        # === 3. SEND QUOTATION ===
        if 'send_quotation' in request.POST:
            form = self.get_form()
            if form.is_valid():
                return self.form_valid(form)
            else:
                return self.form_invalid(form)

        return redirect('superuser:rfq_quote', pk=self.object.pk)

    def form_valid(self, form):
        rfq = form.save(commit=False)
        rfq.quoted_by = self.request.user
        rfq.quote_sent_at = timezone.now()
        rfq.status = 'quoted'
        rfq.save()

        self.send_quotation_email(rfq)
        messages.success(self.request, "Quotation sent and email delivered.")
        return super().form_valid(form)

    def send_quotation_email(self, rfq):
        subject = f"Quotation for RFQ #{rfq.id} - {rfq.product.name}"
        recipient_email = rfq.requested_by.email
        context = {
            'rfq': rfq,
            'supplier': rfq.quoted_by,
            'comments': rfq.comments.all(),
        }
        message = render_to_string('superuser/rfq_quotation_sent.html', context)
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


class RatingView(TemplateView):
    template_name = "superuser/rating.html"  

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
    template_name = "superuser/product_ratings.html"
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



class AdminMostViewedProductsView(View):
    def get(self, request):
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
        ).filter(
            Q(delivered_count__gt=0) | Q(review_count__gt=0) 
        ).prefetch_related(
            Prefetch(
                'images',  
                queryset=ProductImage.objects.order_by('-is_main', '-created_at'),
                to_attr='prefetched_images' 
            )
        ).order_by('-delivered_count')

        for product in products:
            images = getattr(product, 'prefetched_images', [])
            if images:
                main_images = [img for img in images if img.is_main]
                product.display_image = main_images[0] if main_images else images[0]
            else:
                product.display_image = None

        context = {'products': products}
        return render(request, 'superuser/view_product.html', context)

class AdminReturnsView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'superuser/returns.html'
    login_url = 'dashboard:login'
    permission_required = 'is_staff'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = Return.objects.select_related(
            'order_item__product__brand__supplier',
            'order_item__order__payment',
            'order_item__order', 
            'client'
        ).prefetch_related(
            'order_item__order' 
        ).order_by('-request_date')

        paginator = Paginator(qs, 13)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context.update({
            'page_obj': page_obj,
            'returns': page_obj.object_list,
            'count_all': qs.count(),
            'count_approved': qs.filter(return_status='approved').count(),
            'count_pending': qs.filter(return_status='pending').count(),
            'count_rejected': qs.filter(return_status='rejected').count(),
            'user_permissions_list': self.request.user.get_all_permissions(),
        })
        return context
class AdminReturnUpdateStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'is_staff'

    def post(self, request, return_serial, *args, **kwargs):
        return_instance = get_object_or_404(Return, return_serial=return_serial)
        new_status = request.POST.get('return_status')
        valid_statuses = dict(return_instance.RETURN_STATUS_CHOICES)
        if new_status not in valid_statuses:
            messages.error(request, "Invalid status selected.")
            return redirect('superuser:admin_returns')
        old_status = return_instance.return_status
        if old_status == new_status:
            messages.info(request, "Return status is already up to date.")
            return redirect('superuser:admin_returns')
        return_instance.return_status = new_status
        return_instance.save(update_fields=['return_status'])
        admin_update_activity(
            request.user,
            f"Updated return status for Return {return_serial} "
            f"from '{old_status}' to '{new_status}'"
        )

        messages.success(
            request,
            f"Return {return_serial} status updated to {new_status}."
        )

        return redirect('superuser:admin_returns')




#
#
# class StripeRefundView(LoginRequiredMixin, PermissionRequiredMixin, View):
#     permission_required = 'is_staff'
#
#     def post(self, request, *args, **kwargs):
#         return_serial = request.POST.get("return_serial")
#         refund_amount = request.POST.get("final_refund_amount")
#         admin_note = request.POST.get("hidden_admin_note")
#         user_note = request.POST.get("hidden_user_note")
#
#         try:
#             return_instance = get_object_or_404(Return, return_serial=return_serial, return_status='approved')
#             payment = return_instance.order_item.order.payment
#
#             if not (payment and payment.payment_method == 'stripe' and hasattr(payment, "stripe_payment")):
#                 messages.error(request, "No linked Stripe payment found.")
#                 return redirect("superuser:admin_returns")
#
#             stripe.api_key = settings.STRIPE_SECRET_KEY
#             stripe_payment = payment.stripe_payment
#
#             # ✅ Refund using PaymentIntent or Charge
#             if stripe_payment.stripe_payment_intent_id:
#                 refund = stripe.Refund.create(
#                     payment_intent=stripe_payment.stripe_payment_intent_id,
#                     amount=int(float(refund_amount) * 100),
#                     metadata={
#                         "return_id": return_instance.return_serial,
#                         "admin_notes": admin_note or "Processed by admin",
#                         "description": user_note or "User-initiated return"
#                     }
#                 )
#             elif stripe_payment.stripe_charge_id:
#                 refund = stripe.Refund.create(
#                     charge=stripe_payment.stripe_charge_id,
#                     amount=int(float(refund_amount) * 100),
#                     metadata={
#                         "return_id": return_instance.return_serial,
#                         "admin_notes": admin_note or "Processed by admin",
#                         "description": user_note or "User-initiated return"
#                     }
#                 )
#             else:
#                 messages.error(request, "No PaymentIntent or Charge ID found.")
#                 return redirect("superuser:admin_returns")
#
#             # ✅ Update statuses
#             return_instance.return_status = "return_completed"
#             return_instance.updated_at = timezone.now()
#             return_instance.save()
#
#             payment.paid = False
#             payment.save()
#
#             stripe_payment.paid = False
#             stripe_payment.save()
#
#             # ✅ Notify user
#             subject = f"Refund processed for Return {return_instance.return_serial}"
#             message = (
#                 f"Hello {return_instance.client.username},\n\n"
#                 f"Your refund for order {return_instance.order_item.order.order_id} "
#                 f"has been processed successfully.\n\n"
#                 f"Refund Amount: ${refund_amount}\n"
#                 f"Reference: {refund['id']}\n"
#             )
#             send_refund_notification(return_instance.client.email, subject, message)
#
#             messages.success(request, f"Refund processed for {return_instance.return_serial}.")
#             return redirect("superuser:admin_returns")
#
#         except Exception as e:
#             messages.error(request, f"Error processing refund: {str(e)}")
#             return redirect("superuser:admin_returns")
#
#
class ReturnDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'is_staff'

    def post(self, request, return_serial, *args, **kwargs):
        try:
            return_instance = get_object_or_404(Return, return_serial=return_serial)
            user_email = return_instance.client.email
            username = return_instance.client.username
            order_id = return_instance.order_item.order.order_id

            return_instance.delete()

            subject = f"Return {return_serial} Deleted"
            message = (
                f"Hello {username},\n\n"
                f"Your return request for order {order_id} (Return ID: {return_serial}) "
                f"has been deleted by admin.\n\n"
                f"If you believe this is an error, please contact support.\n\n"
                f"Thank you."
            )
            send_refund_notification(user_email, subject, message)

            messages.success(request, f"Return {return_serial} deleted successfully.")
            return redirect('superuser:admin_returns')

        except Exception as e:
            messages.error(request, f"Error deleting return: {str(e)}")
        return redirect('superuser:admin_returns')
    

class AdminProcessRefundView(View):
    def post(self, request, *args, **kwargs):
        return_serial = request.POST.get("hidden_transaction_id")
        refund_amount = float(request.POST.get("final_refund_amount") or request.POST.get("hidden_transaction_amount", 0))
        admin_note = request.POST.get("hidden_admin_note")
        user_note = request.POST.get("hidden_user_note")

        return_instance = get_object_or_404(Return, return_serial=return_serial, return_status="approved")
        payment = return_instance.order_item.order.payment

        if not payment:
            messages.error(request, "Payment record not found.")
            return redirect("superuser:admin_returns")

        success, msg, refund_id = process_refund(payment, return_serial, refund_amount, admin_note, user_note)

        if success:
            return_instance.return_status = "return_completed"
            return_instance.is_refunded = True
            return_instance.refund_id = refund_id
            return_instance.updated_at = timezone.now()
            return_instance.save()

            messages.success(request, f"Refund successful: {msg}")
        else:
            messages.error(request, f"Refund failed: {msg}")

        return redirect("superuser:admin_returns")


class NotificationListView(PermissionRequiredMixin, StaffAccountRequiredMixin, ListView):
    model = Notification
    template_name = "superuser/notification.html"
    context_object_name = "notifications"
    paginate_by = 14
    required_permissions = ('dashboard.view_notification',)

    def get_queryset(self):
        queryset = super().get_queryset()
        search_by = self.request.GET.get('search_by', '').strip()
        created_date = self.request.GET.get('created_date', '').strip()
        sort_filter = self.request.GET.get('filterSort', '')
        checked_filter = self.request.GET.get('filterChecked', '')

        # 🔍 Search
        if search_by:
            queryset = queryset.filter(
                Q(recipient__email__icontains=search_by) |
                Q(title__icontains=search_by) |
                Q(message__icontains=search_by)
            )

        # 📅 Date Range
        if created_date:
            match = re.match(r'(\d{2}/\d{2}/\d{4}) - (\d{2}/\d{2}/\d{4})', created_date)
            if match:
                start_date_str, end_date_str = match.groups()
                try:
                    start_date = datetime.strptime(start_date_str, '%m/%d/%Y')
                    end_date = datetime.strptime(end_date_str, '%m/%d/%Y').replace(hour=23, minute=59, second=59)
                    queryset = queryset.filter(created_at__range=[start_date, end_date])
                except ValueError:
                    pass

        # ✅ Read/Unread Filter
        if checked_filter:
            queryset = queryset.filter(is_read=(checked_filter == 'true'))

        # 🔽 Sort
        if sort_filter:
            queryset = queryset.order_by('created_at' if sort_filter == 'asc' else '-created_at')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["users"] = User.objects.all()
        context["search_placeholder_text"] = "Search by User, Title, or Message"
        context["search_help_text"] = "Search notifications by user email, title, or message content."
        context["show_advance_search_link"] = True
        return context
from itertools import chain

class NotificationCreateView(CreateView):
    model = Notification
    template_name = "superuser/notification_form.html"
    fields = ["title", "message", "send_to", "recipient"]
    success_url = reverse_lazy("superuser:notifications_list")

    def post(self, request, *args, **kwargs):
        send_to = request.POST.get("send_to")
        title = request.POST.get("title", "").strip()
        message = request.POST.get("message", "").strip()
        user_ids = request.POST.getlist("recipients")

        notifications_to_create = []
        total_recipients = 0

        # 1️Specific User(s)
        if send_to == "single" and user_ids:
            users = User.objects.filter(id__in=user_ids)
            for user in users:
                notifications_to_create.append(Notification(
                    recipient=user,
                    send_to="single",
                    title=title,
                    message=message,
                ))
            total_recipients = users.count()

        # 2️ All Buyers
        elif send_to == "buyer":
            retail_users = User.objects.filter(retailprofile__isnull=False)
            wholesale_users = User.objects.filter(wholesalebuyerprofile__isnull=False)
            all_buyers = set(chain(retail_users, wholesale_users))
            for user in all_buyers:
                notifications_to_create.append(Notification(
                    recipient=user,
                    send_to="buyer",
                    title=title,
                    message=message,
                ))
            total_recipients = len(all_buyers)

        # 3️All Suppliers
        elif send_to == "supplier":
            supplier_users = User.objects.filter(supplierprofile__isnull=False)
            for user in supplier_users:
                notifications_to_create.append(Notification(
                    recipient=user,
                    send_to="supplier",
                    title=title,
                    message=message,
                ))
            total_recipients = supplier_users.count()

        # 4️All Users
        elif send_to == "all":
            retail_users = User.objects.filter(retailprofile__isnull=False)
            wholesale_users = User.objects.filter(wholesalebuyerprofile__isnull=False)
            supplier_users = User.objects.filter(supplierprofile__isnull=False)
            all_users = set(chain(retail_users, wholesale_users, supplier_users))
            for user in all_users:
                notifications_to_create.append(Notification(
                    recipient=user,
                    send_to="all",
                    title=title,
                    message=message,
                ))
            total_recipients = len(all_users)

        if notifications_to_create:
            Notification.objects.bulk_create(notifications_to_create)

            admin_log_activity(
                request.user,
                f"Sent notification '{title}' to {total_recipients} user(s) [{send_to}]",
                AdminActivityLog.ActionType.CREATED
            )

        messages.success(request, "Notification(s) sent successfully!")
        return redirect(self.success_url)


class EditNotificationView(UpdateView):
    model = Notification
    fields = ['title', 'message']
    template_name = 'superuser/notification.html'
    success_url = reverse_lazy('superuser:notifications_list')

    def form_valid(self, form):
        notification = form.save()

        admin_log_activity(
            self.request.user,
            f"Updated notification ID {notification.id}",
            AdminActivityLog.ActionType.UPDATED
        )

        messages.success(self.request, "Notification updated successfully.")
        return super().form_valid(form)


class DeleteNotificationView(View):
    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk)
        notification_title = notification.title
        notification.delete()

        admin_log_activity(
            request.user,
            f"Deleted notification '{notification_title}' (ID {pk})",
            AdminActivityLog.ActionType.DELETED
        )

        messages.success(request, "Notification deleted successfully.")
        return redirect('superuser:notifications_list')



# category get and post AJAX method

class AJAXGetCategoriesView(StaffAccountRequiredMixin, View):
    def get(self, request):
        categories = ProductCategory.objects.values("id", "name").order_by("name")
        return JsonResponse({"categories": list(categories)})

class AJAXCreateCategory(View):
    def post(self, request):
        name = request.POST.get('name')
        image = request.FILES.get('image')  

        if not name:
            return JsonResponse({"status": "error", "message": "Category name is required."}, status=400)

        if ProductCategory.objects.filter(name__iexact=name).exists():
            return JsonResponse({"status": "warning", "message": "This category already exists."}, status=400)

        category = ProductCategory.objects.create(name=name, image=image)  # <-- save image
        return JsonResponse({"status": "success", "message": f"Category '{category.name}' created successfully.", "id": category.id})



def get_subcategories(request):
    subcategories = ProductSubCategory.objects.all()

    data = [
        {"id": sub.id, "name": sub.name, "category": sub.category.name}
        for sub in subcategories
    ]
    return JsonResponse(data, safe=False)

class AJAXCreateSubCategory( View):
    def post(self, request):
        name = request.POST.get('name')
        category_id = request.POST.get('category')

        if not name or not category_id:
            return JsonResponse({"status": "error", "message": "Sub-category name and parent category are required."}, status=400)

        if ProductSubCategory.objects.filter(name__iexact=name, category_id=category_id).exists():
            return JsonResponse({"status": "warning", "message": "This sub-category already exists."}, status=400)

        subcat = ProductSubCategory.objects.create(name=name, category_id=category_id)

        return JsonResponse({
            "status": "success",
            "message": f"Sub-category '{subcat.name}' created successfully.",
            "id": subcat.id,
            "name": subcat.name,
            "category_id": subcat.category_id,
        })

class AJAXCreateLastCategory(View):
    def post(self, request):
        name = request.POST.get('name')
        sub_category_id = request.POST.get('sub_category')
        image = request.FILES.get('image')  

        if not name or not sub_category_id:
            return JsonResponse({"status": "error", "message": "Last category name and parent sub-category are required."}, status=400)

        if ProductLastCategory.objects.filter(name__iexact=name, sub_category_id=sub_category_id).exists():
            return JsonResponse({"status": "warning", "message": "This last category already exists."}, status=400)

        lastcat = ProductLastCategory.objects.create(
            name=name,
            sub_category_id=sub_category_id,
            image=image 
        )

        return JsonResponse({
            "status": "success",
            "message": f"Last category '{lastcat.name}' created successfully.",
            "id": lastcat.id,
            "name": lastcat.name,
            "sub_category_id": lastcat.sub_category_id,
        })
class AdminQuestionView(TemplateView):
    template_name = 'superuser/question_list.html'
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user_products = Product.objects.filter(created_by=self.request.user)
        questions_qs = Question.objects.filter(product__in=user_products).select_related('user', 'product')

        # Search
        search_by = self.request.GET.get('search_by')
        if search_by:
            questions_qs = questions_qs.filter(
                Q(text__icontains=search_by) |
                Q(user__username__icontains=search_by) |
                Q(product__name__icontains=search_by)
            )

        # Sorting
        sort_by = self.request.GET.get('sort_by')
        if sort_by == "asc_created":
            questions_qs = questions_qs.order_by('created_at')
        else:
            questions_qs = questions_qs.order_by('-created_at')

        # Date range filter
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

        # Pagination
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
            Question, id=question_id, product__in=user_products
        )

        if action_type == "reply":
            question.reply = reply_text
            question.replied_at = timezone.now()
            question.save()
            messages.success(request, "Reply sent successfully.")
            admin_update_activity(
                user=request.user,
                description=f"Replied to question (ID: {question_id}) on product: {question.product.name}"
            )

        elif action_type == "delete":
            product_name = question.product.name
            question.delete()
            messages.success(request, "Question deleted successfully.")
            admin_delete_activity(
                user=request.user,
                description=f"Deleted question (ID: {question_id}) from product: {product_name}"
            )

        return redirect('superuser:question_list')






# class CategoryListView(View):
#     def get(self, request):
#         categories = ProductCategory.objects.exclude(
#             Q(name__iexact="event") | Q(name__iexact="webinar") | Q(name__iexact="conference")
#         )

#         search_query = request.GET.get('search_by', '')  
#         sort_by = request.GET.get('sort_by', 'desc_created')  
#         date_from = request.GET.get('date_from', '')
#         date_to = request.GET.get('date_to', '')

#         sort_mapping = {
#             'asc_created': 'created_at',    
#             'desc_created': '-created_at', 
#         }
#         sort_by = sort_mapping.get(sort_by, '-created_at')  
        
#         if search_query:
#             categories = categories.filter(name__icontains=search_query)
#         if date_from:
#             categories = categories.filter(created_at__date__gte=date_from)
#         if date_to:
#             categories = categories.filter(created_at__date__lte=date_to)

#         categories = categories.order_by(sort_by)
#         total_categories = categories.count()
        
#         paginator = Paginator(categories, 10) 
#         page_number = request.GET.get('page')
        
#         try:
#             categories_page = paginator.page(page_number)
#         except PageNotAnInteger:
#             categories_page = paginator.page(1)
#         except EmptyPage:
#             categories_page = paginator.page(paginator.num_pages)
        
#         context = {
#             'categories': categories_page, 
#             'total_categories': total_categories,
#             'search_query': search_query, 
#             'sort_by': request.GET.get('sort_by', 'desc_created'),
#             'date_from': date_from,
#             'date_to': date_to,
#         }
        
#         return render(request, "superuser/categories/categories.html", context)
    
#     def post(self, request):
#         return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
from datetime import datetime

class CategoryListView(View):
    def get(self, request):
        categories = ProductCategory.objects.exclude(
            Q(name__iexact="event") | 
            Q(name__iexact="webinar") | 
            Q(name__iexact="conference")
        )

        search_query = request.GET.get('search_by', '')  
        sort_by = request.GET.get('sort_by', 'desc_created')  
        date_range = request.GET.get('created_date', '')  

        sort_mapping = {
            'asc_created': 'created_at',    
            'desc_created': '-created_at', 
        }
        sort_by = sort_mapping.get(sort_by, '-created_at')
        if search_query:
            categories = categories.filter(name__icontains=search_query)
        if date_range:
            try:
                date_from_str, date_to_str = [d.strip() for d in date_range.split('-')]

                if date_from_str:
                    date_from = datetime.strptime(date_from_str, "%m/%d/%Y").date()
                    categories = categories.filter(created_at__date__gte=date_from)
                if date_to_str:
                    date_to = datetime.strptime(date_to_str, "%m/%d/%Y").date()
                    categories = categories.filter(created_at__date__lte=date_to)
            except ValueError:
                pass 

        categories = categories.order_by(sort_by)
        total_categories = categories.count()

      
        paginator = Paginator(categories, 10)
        page_number = request.GET.get('page')
        try:
            categories_page = paginator.page(page_number)
        except PageNotAnInteger:
            categories_page = paginator.page(1)
        except EmptyPage:
            categories_page = paginator.page(paginator.num_pages)

        context = {
            'categories': categories_page,
            'total_categories': total_categories,
            'search_query': search_query,
            'sort_by': request.GET.get('sort_by', 'desc_created'),
            'created_date': date_range,
        }

        return render(request, "superuser/categories/categories.html", context)

    def post(self, request):
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
class CategoryCreateView(View):
    def get(self, request):
        return render(request, 'superuser/categories/add_category_modal.html')

    def post(self, request):
        name = request.POST.get('name')
        image = request.FILES.get('image')

        if not name:
            return JsonResponse({'status': 'error', 'message': 'Category name is required'})

        try:
            category = ProductCategory.objects.create(name=name, image=image)

            admin_log_activity(
                request.user,
                f"Created category '{category.name}'",
                AdminActivityLog.ActionType.CREATED
            )

            return JsonResponse({'status': 'success', 'message': 'Category added successfully', 'id': category.id})
        except ValidationError as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
class CategoryEditView(View):
    def post(self, request):
        category_id = request.POST.get('id')
        name = request.POST.get('name')
        image = request.FILES.get('image')

        if not name:
            return JsonResponse({'status': 'error', 'message': 'Category name is required'})

        try:
            category = ProductCategory.objects.get(id=category_id)
            old_name = category.name

            category.name = name
            if image:
                category.image = image
            category.save()

            admin_log_activity(
                request.user,
                f"Updated category '{old_name}' to '{category.name}'",
                AdminActivityLog.ActionType.UPDATED
            )

            return JsonResponse({'status': 'success', 'message': 'Category updated successfully', 'id': category.id})
        except ProductCategory.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Category not found'})
        except ValidationError as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
class CategoryDeleteView(View):
    def post(self, request):
        category_id = request.POST.get('id')
        try:
            category = ProductCategory.objects.get(id=category_id)
            category_name = category.name
            category.delete()

            admin_log_activity(
                request.user,
                f"Deleted category '{category_name}'",
                AdminActivityLog.ActionType.DELETED
            )

            return JsonResponse({'status': 'success', 'message': f'Category "{category_name}" deleted successfully'})
        except ProductCategory.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Category not found'})




# class CategorySubListView(View):
#     def get(self, request, category_id=None):
#         categories = ProductCategory.objects.exclude(
#             Q(name__iexact="event") | Q(name__iexact="webinar") | Q(name__iexact="conference")
#         )
#         search_query = request.GET.get('search_by', '')  
#         sort_by = request.GET.get('sort_by', 'desc_created')
#         date_from = request.GET.get('date_from', '')
#         date_to = request.GET.get('date_to', '')
        
#         sort_mapping = {
#             'asc_created': 'created_at',
#             'desc_created': '-created_at',
#         }
#         django_sort_by = sort_mapping.get(sort_by, '-created_at')
        
#         if category_id:
#             try:
#                 category = ProductCategory.objects.get(id=category_id)
#                 subcategories = ProductSubCategory.objects.filter(
#                     category=category
#                 ).select_related('category').prefetch_related('productlastcategory_set')
                
#                 if search_query:
#                     subcategories = subcategories.filter(name__icontains=search_query)
#                 if date_from:
#                     subcategories = subcategories.filter(created_at__date__gte=date_from)
#                 if date_to:
#                     subcategories = subcategories.filter(created_at__date__lte=date_to)
                
#                 subcategories = subcategories.order_by(django_sort_by)
                
#                 paginator = Paginator(subcategories, 10)
#                 page_number = request.GET.get('page')
#                 try:
#                     subcategories_page = paginator.page(page_number)
#                 except PageNotAnInteger:
#                     subcategories_page = paginator.page(1)
#                 except EmptyPage:
#                     subcategories_page = paginator.page(paginator.num_pages)
                
#                 context = {
#                     'subcategories': subcategories_page,
#                     'category': category,
#                     'category_id': category_id,
#                     'categories': categories,
#                     'total_subcategories': subcategories.count(),
#                     'search_query': search_query,
#                     'sort_by': sort_by,
#                     'date_from': date_from,
#                     'date_to': date_to,
#                 }
#             except ProductCategory.DoesNotExist:
#                 context = {
#                     'subcategories': [],
#                     'categories': categories,
#                     'error': 'Category not found',
#                     'search_query': search_query,
#                     'sort_by': sort_by,
#                     'date_from': date_from,
#                     'date_to': date_to,
#                 }
#         else:
#             subcategories = ProductSubCategory.objects.all().select_related('category').prefetch_related('productlastcategory_set')
            
#             if search_query:
#                 subcategories = subcategories.filter(name__icontains=search_query)
#             if date_from:
#                 subcategories = subcategories.filter(created_at__date__gte=date_from)
#             if date_to:
#                 subcategories = subcategories.filter(created_at__date__lte=date_to)
            
#             subcategories = subcategories.order_by(django_sort_by)
            
#             paginator = Paginator(subcategories, 10)
#             page_number = request.GET.get('page')
#             try:
#                 subcategories_page = paginator.page(page_number)
#             except PageNotAnInteger:
#                 subcategories_page = paginator.page(1)
#             except EmptyPage:
#                 subcategories_page = paginator.page(paginator.num_pages)
            
#             context = {
#                 'subcategories': subcategories_page,
#                 'category': None,
#                 'category_id': None,
#                 'categories': categories,
#                 'total_subcategories': subcategories.count(),
#                 'search_query': search_query,
#                 'sort_by': sort_by,
#                 'date_from': date_from,
#                 'date_to': date_to,
#             }
        
#         return render(request, "superuser/categories/sub_categories.html", context)
class CategorySubListView(View):
    def get(self, request, category_id=None):
        categories = ProductCategory.objects.exclude(
            Q(name__iexact="event") | Q(name__iexact="webinar") | Q(name__iexact="conference")
        )

        search_query = request.GET.get('search_by', '')
        sort_by = request.GET.get('sort_by', 'desc_created')
        created_date = request.GET.get('created_date', '')

        # Map sort options
        sort_mapping = {
            'asc_created': 'created_at',
            'desc_created': '-created_at',
        }
        django_sort_by = sort_mapping.get(sort_by, '-created_at')

        # Parse date range from single input (MM/DD/YYYY format)
        date_from = None
        date_to = None
        if created_date:
            try:
                dates = created_date.split(' - ')
                if len(dates) == 2:
                    date_from = datetime.strptime(dates[0].strip(), '%m/%d/%Y').date()
                    date_to = datetime.strptime(dates[1].strip(), '%m/%d/%Y').date()
                elif len(dates) == 1:
                    date_from = date_to = datetime.strptime(dates[0].strip(), '%m/%d/%Y').date()
            except ValueError:
                date_from = date_to = None

        # Filter by category if category_id provided
        if category_id:
            try:
                category = ProductCategory.objects.get(id=category_id)
                subcategories = ProductSubCategory.objects.filter(
                    category=category
                ).select_related('category').prefetch_related('productlastcategory_set')

                # Apply search and date filters
                if search_query:
                    subcategories = subcategories.filter(name__icontains=search_query)
                if date_from:
                    subcategories = subcategories.filter(created_at__date__gte=date_from)
                if date_to:
                    subcategories = subcategories.filter(created_at__date__lte=date_to)

                subcategories = subcategories.order_by(django_sort_by)

                # Pagination
                paginator = Paginator(subcategories, 10)
                page_number = request.GET.get('page')
                try:
                    subcategories_page = paginator.page(page_number)
                except PageNotAnInteger:
                    subcategories_page = paginator.page(1)
                except EmptyPage:
                    subcategories_page = paginator.page(paginator.num_pages)

                context = {
                    'subcategories': subcategories_page,
                    'category': category,
                    'category_id': category_id,
                    'categories': categories,
                    'total_subcategories': subcategories.count(),
                    'search_query': search_query,
                    'sort_by': sort_by,
                    'created_date': created_date,
                }

            except ProductCategory.DoesNotExist:
                context = {
                    'subcategories': [],
                    'categories': categories,
                    'error': 'Category not found',
                    'search_query': search_query,
                    'sort_by': sort_by,
                    'created_date': created_date,
                }

        else:
            # No category filter
            subcategories = ProductSubCategory.objects.all().select_related('category').prefetch_related('productlastcategory_set')

            if search_query:
                subcategories = subcategories.filter(name__icontains=search_query)
            if date_from:
                subcategories = subcategories.filter(created_at__date__gte=date_from)
            if date_to:
                subcategories = subcategories.filter(created_at__date__lte=date_to)

            subcategories = subcategories.order_by(django_sort_by)

            # Pagination
            paginator = Paginator(subcategories, 10)
            page_number = request.GET.get('page')
            try:
                subcategories_page = paginator.page(page_number)
            except PageNotAnInteger:
                subcategories_page = paginator.page(1)
            except EmptyPage:
                subcategories_page = paginator.page(paginator.num_pages)

            context = {
                'subcategories': subcategories_page,
                'category': None,
                'category_id': None,
                'categories': categories,
                'total_subcategories': subcategories.count(),
                'search_query': search_query,
                'sort_by': sort_by,
                'created_date': created_date,
            }

        return render(request, "superuser/categories/sub_categories.html", context)
class SubCategoryCreateView(View):
    def get(self, request):
        categories = ProductCategory.objects.exclude(
            Q(name__iexact="event") | Q(name__iexact="webinar") | Q(name__iexact="conference")
        )
        return render(request, 'superuser/categories/add_subcategory_modal.html', {'categories': categories})

    def post(self, request):
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        image = request.FILES.get('image')

        if not name or not category_id:
            return JsonResponse({'status': 'error', 'message': 'Subcategory name and category are required'})

        try:
            category = ProductCategory.objects.get(id=category_id)
            subcategory = ProductSubCategory.objects.create(
                name=name,
                category=category,
                image=image
            )

            admin_log_activity(
                request.user,
                f"Created subcategory '{subcategory.name}' under category '{category.name}'",
                AdminActivityLog.ActionType.CREATED
            )

            return JsonResponse({
                'status': 'success',
                'message': 'Subcategory added successfully',
                'id': subcategory.id,
                'name': subcategory.name,
                'category_id': category.id,
                'image_url': subcategory.image.url if subcategory.image else None
            })
        except ProductCategory.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Category not found'})
        except ValidationError as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
class SubCategoryEditView(View):
    def post(self, request):
        subcategory_id = request.POST.get('id')
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        image = request.FILES.get('image')

        if not name or not category_id:
            return JsonResponse({'status': 'error', 'message': 'Subcategory name and category are required'})

        try:
            subcategory = ProductSubCategory.objects.get(id=subcategory_id)
            old_name = subcategory.name
            category = ProductCategory.objects.get(id=category_id)

            if image and subcategory.image:
                subcategory.image.delete(save=False)

            subcategory.name = name
            subcategory.category = category
            if image:
                subcategory.image = image

            subcategory.save()

            admin_log_activity(
                request.user,
                f"Updated subcategory '{old_name}' to '{subcategory.name}' under category '{category.name}'",
                AdminActivityLog.ActionType.UPDATED
            )

            return JsonResponse({
                'status': 'success',
                'message': 'Subcategory updated successfully',
                'id': subcategory.id
            })
        except ProductSubCategory.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Subcategory not found'})
        except ProductCategory.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Category not found'})
        except ValidationError as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

class SubCategoryDeleteView(View):
    def post(self, request):
        subcategory_id = request.POST.get('id')
        try:
            subcategory = ProductSubCategory.objects.get(id=subcategory_id)
            subcategory_name = subcategory.name

            if subcategory.image:
                subcategory.image.delete(save=False)

            subcategory.delete()

            admin_log_activity(
                request.user,
                f"Deleted subcategory '{subcategory_name}'",
                AdminActivityLog.ActionType.DELETED
            )

            return JsonResponse({'status': 'success', 'message': f'Subcategory "{subcategory_name}" deleted successfully'})
        except ProductSubCategory.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Subcategory not found'})


# class SubCategoryLastListView(View):
#     def get(self, request, subcategory_id=None):
#         # Load subcategories for edit modal
#         subcategories = ProductSubCategory.objects.select_related('category').all()
        
#         if subcategory_id:
#             try:
#                 subcategory = ProductSubCategory.objects.select_related('category').get(id=subcategory_id)
#                 last_categories = ProductLastCategory.objects.filter(sub_category=subcategory).select_related('sub_category')
#                 context = {
#                     'last_categories': last_categories,
#                     'subcategory': subcategory,
#                     'subcategory_id': subcategory_id,
#                     'subcategories': subcategories
#                 }
#             except ProductSubCategory.DoesNotExist:
#                 return render(request, "superuser/categories/last_categories.html", {
#                     'last_categories': [],
#                     'subcategories': subcategories,
#                     'error': 'Subcategory not found'
#                 })
#         else:
#             last_categories = ProductLastCategory.objects.select_related('sub_category').all()
#             context = {
#                 'last_categories': last_categories,
#                 'subcategory': None,
#                 'subcategory_id': None,
#                 'subcategories': subcategories
#             }
        
#         return render(request, "superuser/categories/last_categories.html", context)

class SubCategoryLastListView(View):
    def get(self, request, subcategory_id=None):
        subcategories = ProductSubCategory.objects.select_related('category').all()
        search_query = request.GET.get('search_by', '')
        sort_by = request.GET.get('sort_by', '-created_at')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        subcategory_id = request.GET.get('subcategory_id', subcategory_id)
        subcategory = None
        if subcategory_id:
            try:
                subcategory = ProductSubCategory.objects.get(id=subcategory_id)
            except ProductSubCategory.DoesNotExist:
                subcategory = None

        if not subcategory:
            subcategory = subcategories.first()
            if not subcategory:
                return render(request, "superuser/categories/last_categories.html", {
                    'last_categories': [],
                    'subcategories': [],
                    'error': 'No subcategories found',
                })
            subcategory_id = subcategory.id
        last_categories = ProductLastCategory.objects.filter(sub_category=subcategory)

        if search_query:
            last_categories = last_categories.filter(name__icontains=search_query)
        if date_from:
            last_categories = last_categories.filter(created_at__date__gte=date_from)
        if date_to:
            last_categories = last_categories.filter(created_at__date__lte=date_to)

        if sort_by == 'desc_created':
            sort_by = '-created_at'
        elif sort_by == 'asc_created':
            sort_by = 'created_at'
        last_categories = last_categories.order_by(sort_by)
        paginator = Paginator(last_categories, 10)
        page_number = request.GET.get('page')
        last_categories_page = paginator.get_page(page_number)

        context = {
            'last_categories': last_categories_page,
            'subcategory': subcategory,
            'subcategory_id': subcategory_id,
            'subcategories': subcategories,
            'total_last_categories': last_categories.count(),
        }

        return render(request, "superuser/categories/last_categories.html", context)

class LastCategoryCreateView(View):
    def get(self, request):
        subcategories = ProductSubCategory.objects.select_related('category').all()
        return render(request, 'superuser/categories/add_lastcategory_modal.html', {'subcategories': subcategories})

    def post(self, request):
        name = request.POST.get('name')
        subcategory_id = request.POST.get('subcategory')
        image = request.FILES.get('image')

        if not name or not subcategory_id:
            return JsonResponse({'status': 'error', 'message': 'Last category name and subcategory are required'})

        try:
            subcategory = ProductSubCategory.objects.get(id=subcategory_id)

            last_category = ProductLastCategory.objects.create(
                name=name,
                sub_category=subcategory,
                image=image
            )

            admin_log_activity(
                request.user,
                f"Created last category '{last_category.name}' under subcategory '{subcategory.name}'",
                AdminActivityLog.ActionType.CREATED
            )

            return JsonResponse({
                'status': 'success',
                'message': 'Last category added successfully',
                'id': last_category.id,
                'name': last_category.name,
                'subcategory_id': subcategory.id,
                'image_url': last_category.image.url if last_category.image else None
            })
        except ProductSubCategory.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Subcategory not found'})
        except ValidationError as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
class LastCategoryEditView(View):
    def get(self, request, lastcategory_id):
        try:
            last_category = ProductLastCategory.objects.select_related('sub_category').get(id=lastcategory_id)
            subcategories = ProductSubCategory.objects.select_related('category').all()
            return render(request, 'superuser/categories/edit_lastcategory_modal.html', {
                'last_category': last_category,
                'subcategories': subcategories
            })
        except ProductLastCategory.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Last category not found'})

    def post(self, request):
        lastcategory_id = request.POST.get('id')
        name = request.POST.get('name')
        subcategory_id = request.POST.get('subcategory')
        image = request.FILES.get('image')

        if not name or not subcategory_id:
            return JsonResponse({'status': 'error', 'message': 'Last category name and subcategory are required'})

        try:
            last_category = ProductLastCategory.objects.get(id=lastcategory_id)
            old_name = last_category.name
            subcategory = ProductSubCategory.objects.get(id=subcategory_id)

            if image and last_category.image:
                last_category.image.delete(save=False)

            last_category.name = name
            last_category.sub_category = subcategory
            if image:
                last_category.image = image

            last_category.save()

            admin_log_activity(
                request.user,
                f"Updated last category '{old_name}' to '{last_category.name}' under subcategory '{subcategory.name}'",
                AdminActivityLog.ActionType.UPDATED
            )

            return JsonResponse({
                'status': 'success',
                'message': 'Last category updated successfully',
                'id': last_category.id,
                'name': last_category.name,
                'subcategory_id': subcategory.id,
                'image_url': last_category.image.url if last_category.image else None
            })
        except ProductLastCategory.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Last category not found'})
        except ProductSubCategory.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Subcategory not found'})
        except ValidationError as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
class LastCategoryDeleteView(View):
    def post(self, request):
        lastcategory_id = request.POST.get('id')
        try:
            last_category = ProductLastCategory.objects.get(id=lastcategory_id)
            last_category_name = last_category.name

            if last_category.image:
                last_category.image.delete(save=False)

            last_category.delete()

            admin_log_activity(
                request.user,
                f"Deleted last category '{last_category_name}'",
                AdminActivityLog.ActionType.DELETED
            )

            return JsonResponse({
                'status': 'success',
                'message': f'Last category "{last_category_name}" deleted successfully'
            })
        except ProductLastCategory.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Last category not found'})

        

class SupplierCommissionListView(ListView):
    model = SupplierCommission
    template_name = 'superuser/suppliercommission.html'
    context_object_name = 'commissions'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.forms import modelform_factory
        CommissionForm = modelform_factory(SupplierCommission, fields=['supplier'])
        form = CommissionForm()
        form.fields['supplier'].help_text = ''
        context['form'] = form
        return context

    def post(self, request, *args, **kwargs):
        from django.forms import modelform_factory
        CommissionForm = modelform_factory(SupplierCommission, fields=['supplier'])
        form = CommissionForm(request.POST)
        form.fields['supplier'].help_text = '' 
        if form.is_valid():
            form.save()
            return redirect('superuser:supplier_commission')
        context = self.get_context_data()
        context['form'] = form
        return self.render_to_response(context)
class SupplierCommissionEditView(View):
    def post(self, request, *args, **kwargs):
        commission = get_object_or_404(SupplierCommission, id=request.POST.get('id'))
        commission.supplier_id = request.POST.get('supplier')
        commission.save()
        return redirect('superuser:supplier_commission')


class SupplierCommissionDeleteView(View):
    def post(self, request, *args, **kwargs):
        commission = get_object_or_404(SupplierCommission, id=request.POST.get('id'))
        commission.delete()
        return redirect('superuser:supplier_commission')

class AdminVacationModeView(View):
    template_name = 'superuser/vacationmode.html'

    def get(self, request):
        queryset = VacationRequest.objects.all().order_by('-created_at')
        search_query = self.request.GET.get('search_by', '')
        if search_query:
            queryset = queryset.filter(
                Q(supplier__username__icontains=search_query) |
                Q(supplier__email__icontains=search_query)
            )

        created_date = request.GET.get("created_date", "")
        if created_date:
            try:
                start_str, end_str = created_date.split(" - ")

                start_date = datetime.strptime(start_str, "%m/%d/%Y")
                end_date = datetime.strptime(end_str, "%m/%d/%Y")
                end_date = end_date.replace(hour=23, minute=59, second=59)

                queryset = queryset.filter(
                    created_at__range=(start_date, end_date)
                )
            except ValueError:
                pass

        sort_by = request.GET.get("sort_by", "desc_created")
        if sort_by == "asc_created":
            queryset = queryset.order_by("created_at")
        else: 
            queryset = queryset.order_by("-created_at")
            
        # ---------------- PAGINATION ----------------
        paginator = Paginator(queryset, 10)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)
        
        return render(request, self.template_name, {
            "vacation_requests": page_obj.object_list,
            "page_obj": page_obj,
        })
        
    def post(self, request):
        request_id = request.POST.get('request_id')
        action = request.POST.get('action')
        vacation_request = get_object_or_404(VacationRequest, id=request_id)
        if vacation_request.status != 'Pending':
            return JsonResponse({
                'success': False,
                'error': 'This request has already been processed.'
            })

        if action == 'approve':
            vacation_request.status = 'Approved'
            admin_update_activity(
                user=request.user,
                description=f"Approved vacation request (ID: {request_id}) for supplier: {vacation_request.supplier.username}"
            )
            
        elif action == 'reject':
            vacation_request.status = 'Rejected'
            admin_update_activity(
                user=request.user,
                description=f"Rejected vacation request (ID: {request_id}) for supplier: {vacation_request.supplier.username}"
            )
            
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid action.'
            })

        vacation_request.save()
        return JsonResponse({
            'success': True,
            'message': f"Vacation request has been {vacation_request.status.lower()}!"
        })
        




# class AddTopSupplierView(View):
#     template_name = 'superuser/addtopsupplier.html'

#     def get(self, request):
#         suppliers = SupplierProfile.objects.all()
#         return render(request, self.template_name, {'suppliers': suppliers})

#     def post(self, request):
#         supplier_id = request.POST.get('supplier')
#         order = request.POST.get('order')

#         if not supplier_id or not order:
#             messages.error(request, "All fields are required.")
#             suppliers = SupplierProfile.objects.all()
#             return render(request, self.template_name, {'suppliers': suppliers})

#         try:
#             supplier = SupplierProfile.objects.get(id=supplier_id)
#             TopSupplier.objects.create(supplier=supplier, order=order)
#             messages.success(request, "Supplier added successfully!")
#             return redirect('superuser:add_to_supplier')
#         except SupplierProfile.DoesNotExist:
#             messages.error(request, "Invalid supplier selected.")
#             return redirect('superuser:add_to_supplier')



class TopSupplierListView(View):
    def get(self, request):
        # Annotate suppliers with order count
        queryset = SupplierProfile.objects.annotate(
            order_count=Count(
                "user__brands__product__orderitem",
                distinct=True
            )
        )

        # ---------------- SEARCH FILTER ----------------
        search_query = self.request.GET.get('search_by', '')
        if search_query:
            queryset = queryset.filter(
                Q(company_name__icontains=search_query) |
                Q(user__email__icontains=search_query)
            )

        created_date = request.GET.get("created_date", "")
        if created_date:
            try:
                start_str, end_str = created_date.split(" - ")

                start_date = datetime.strptime(start_str, "%m/%d/%Y")
                end_date = datetime.strptime(end_str, "%m/%d/%Y")
                end_date = end_date.replace(hour=23, minute=59, second=59)

                queryset = queryset.filter(
                    user__date_joined__range=(start_date, end_date)
                )
            except ValueError:
                pass

        sort_by = request.GET.get("sort_by", "desc_created")
        if sort_by == "asc_created":
            queryset = queryset.order_by("user__date_joined")
        else: 
            queryset = queryset.order_by("-user__date_joined")
            

        # ---------------- PAGINATION ----------------
        paginator = Paginator(queryset, 10)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        return render(request, "superuser/topsupplierlist.html", {
            "top_suppliers": page_obj.object_list,
            "page_obj": page_obj,
        })


# class EditTopSupplierView(View):
#     def post(self, request):
#         id = request.POST.get('id')
#         supplier_id = request.POST.get('supplier')
#         order = request.POST.get('order')

#         try:
#             top_supplier = TopSupplier.objects.get(id=id)
#             supplier = SupplierProfile.objects.get(id=supplier_id)

#             top_supplier.supplier = supplier
#             top_supplier.order = order
#             top_supplier.save()

#             return JsonResponse({'success': True})
#         except TopSupplier.DoesNotExist:
#             return JsonResponse({'success': False, 'error': 'Top Supplier not found'})
#         except SupplierProfile.DoesNotExist:
#             return JsonResponse({'success': False, 'error': 'Supplier not found'})


# class DeleteTopSupplierView(View):
#     def post(self, request):
#         import json
#         data = json.loads(request.body)
#         id = data.get('id')

#         try:
#             supplier = TopSupplier.objects.get(id=id)
#             supplier.delete()
#             return JsonResponse({'success': True})
#         except TopSupplier.DoesNotExist:
#             return JsonResponse({'success': False, 'error': 'Supplier not found'})
        
class BuyXGetYPromotionView(TemplateView):
    template_name = 'superuser/Buyxgetypromotion.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        promotions_qs = BuyXGetYPromotion.objects.prefetch_related(
            'supplier',
            'product'
        )
        search_by = self.request.GET.get("search_by", "").strip()
        if search_by:
            promotions_qs = promotions_qs.filter(
                Q(product_type__icontains=search_by) |
                Q(supplier__user__username__icontains=search_by) |
                Q(product__name__icontains=search_by)
            ).distinct()
        sort_by = self.request.GET.get("sort_by", "desc_created")
        if sort_by == "asc_created":
            promotions_qs = promotions_qs.order_by("created_at")
        else:
            promotions_qs = promotions_qs.order_by("-created_at")
        paginator = Paginator(promotions_qs, 10)
        page_number = self.request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)
        context.update({
            "page_title": "Buy X Get Y Promotion",
            "promotions": page_obj,
            "page_obj": page_obj,
            "suppliers": SupplierProfile.objects.all(),
            "products": Product.objects.all(),
            "search_placeholder_text": "Search Promotions",
            "search_help_text": "Choices: Product Type, Supplier, Product",
            "show_advance_search_link": True,
        })

        return context

class AddPromotionView(TemplateView):
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

        return JsonResponse({'success': True})
class EditPromotionView(TemplateView):
    def get(self, request, pk):
        try:
            promo = BuyXGetYPromotion.objects.get(pk=pk)
            start_str, _, end_str = promo.promotion_period.partition(' - ')
            start_str = start_str.strip()
            end_str = end_str.strip()

            def format_datetime(dt_str):
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

            admin_log_activity(
                request.user,
                f"Updated Buy {buy} Get {get} promotion (ID: {promo.id})",
                AdminActivityLog.ActionType.UPDATED
            )
            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'msg': str(e)})
def delete_promotion(request, pk):
    try:
        promo = BuyXGetYPromotion.objects.get(pk=pk)
        promo_id = promo.id
        promo.delete()

        admin_log_activity(
            request.user,
            f"Deleted promotion (ID: {promo_id})",
            AdminActivityLog.ActionType.DELETED
        )
        return JsonResponse({'success': True})
    except:
        return JsonResponse({'success': False})

class BuyXGiftYPromotionView(TemplateView):
    template_name = 'superuser/Buyxgiftypromotion.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        # ---------------- BASE QUERYSET ----------------
        promotions_qs = BuyXGiftYPromotion.objects.all()

        # Filter by supplier if user is a supplier
        if hasattr(user, 'supplierprofile'):
            promotions_qs = promotions_qs.filter(supplier=user.supplierprofile)
            ctx['suppliers'] = [user.supplierprofile]
            ctx['products'] = Product.objects.filter(created_by=user)
        else:
            ctx['suppliers'] = SupplierProfile.objects.all()
            ctx['products'] = Product.objects.all()

        # ---------------- SEARCH FILTER ----------------
        search_by = self.request.GET.get("search_by", "").strip()
        if search_by:
            promotions_qs = promotions_qs.filter(
                Q(product_type__icontains=search_by) |
                Q(supplier__user__username__icontains=search_by) |
                Q(product__name__icontains=search_by)
            ).distinct()

        # ---------------- SORT FILTER ----------------
        sort_by = self.request.GET.get("sort_by", "desc_created")
        if sort_by == "asc_created":
            promotions_qs = promotions_qs.order_by("created_at")
        else:
            promotions_qs = promotions_qs.order_by("-created_at")

        # ---------------- PAGINATION ----------------
        paginator = Paginator(promotions_qs, 10)
        page_number = self.request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)

        # ---------------- CONTEXT ----------------
        ctx.update({
            "page_title": "Buy X Gift Y Promotion",
            "promotions": page_obj,
            "page_obj": page_obj,
            "search_placeholder_text": "Search Promotions",
            "search_help_text": "Choices: Product Type, Supplier, Product",
            "show_advance_search_link": True,
        })

        return ctx


class AddGiftPromotionView(TemplateView):
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
            admin_create_activity(
                user=request.user,
                description=f"Created Buy {buy} Gift {gift} promotion for {product_type}"
            )

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'msg': str(e)})


class EditGiftPromotionView(TemplateView):
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
            admin_update_activity(
                user=request.user,
                description=f"Updated Buy {promo.buy} Gift {promo.gift} promotion (ID: {pk})"
            )

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'msg': str(e)})
def delete_gift_promotion(request, pk):
    try:
        promo = BuyXGiftYPromotion.objects.get(pk=pk)
        promo_info = f"Buy {promo.buy} Gift {promo.gift} promotion"
        promo.delete()
        admin_delete_activity(
            user=request.user,
            description=f"Deleted {promo_info} (ID: {pk})"
        )

        return JsonResponse({'success': True})
    except Exception:
        return JsonResponse({'success': False})

class BasketPromotionView(TemplateView):
    template_name = 'superuser/Basketpromotion.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        promotions_qs = BasketPromotion.objects.all()
        if hasattr(user, 'supplierprofile'):
            promotions_qs = promotions_qs.filter(supplier=user.supplierprofile)
            context['suppliers'] = [user.supplierprofile]
            context['products'] = Product.objects.filter(created_by=user)
        else:
            context['suppliers'] = SupplierProfile.objects.all()
            context['products'] = Product.objects.all()
        search_by = self.request.GET.get("search_by", "").strip()
        if search_by:
            promotions_qs = promotions_qs.filter(
                Q(title_en__icontains=search_by) |
                Q(supplier__user__username__icontains=search_by) |
                Q(product__name__icontains=search_by)
            ).distinct()
        sort_by = self.request.GET.get("sort_by", "desc_created")
        if sort_by == "asc_created":
            promotions_qs = promotions_qs.order_by("created_at")
        else:
            promotions_qs = promotions_qs.order_by("-created_at")
        paginator = Paginator(promotions_qs, 10)  
        page_number = self.request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)
        context.update({
            "page_title": "Basket Promotions",
            "promotions": page_obj,
            "page_obj": page_obj,
            "search_placeholder_text": "Search Promotions",
            "search_help_text": "Choices: Title, Supplier, Products",
            "show_advance_search_link": True,
        })

        return context
class AddBasketPromotionView(View):
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

            admin_log_activity(
                request.user,
                f"Created basket promotion '{title_en}' (ID: {promo.id})",
                AdminActivityLog.ActionType.CREATED
            )

            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'msg': str(e)})
class EditBasketPromotionView(View):
    def get(self, request, pk):
        try:
            promo = BasketPromotion.objects.get(pk=pk)
            start_str, _, end_str = promo.promotion_period.partition(' - ')

            def parse_date(date_str):
                try:
                    return datetime.strptime(
                        date_str.strip(), "%d %b %Y"
                    ).strftime("%Y-%m-%dT%H:%M")
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

            admin_log_activity(
                request.user,
                f"Updated basket promotion '{promo.title_en}' (ID: {promo.id})",
                AdminActivityLog.ActionType.UPDATED
            )

            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'msg': str(e)})
def delete_basket_promotion(request, pk):
    try:
        promo = BasketPromotion.objects.get(pk=pk)
        promo_title = promo.title_en
        promo_id = promo.id

        if promo.main_image:
            promo.main_image.delete(save=False)

        promo.delete()

        admin_log_activity(
            request.user,
            f"Deleted basket promotion '{promo_title}' (ID: {promo_id})",
            AdminActivityLog.ActionType.DELETED
        )
        return JsonResponse({'success': True})

    except BasketPromotion.DoesNotExist:
        return JsonResponse({'success': False, 'msg': 'Not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'msg': str(e)})

class CouponsView(TemplateView):
    template_name = "superuser/coupons.html"

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'supplierprofile'):
            return redirect('superuser:superuser')
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
                start_date = timezone.make_aware(datetime.strptime(start_str, "%m/%d/%Y"))
                end_date = timezone.make_aware(datetime.strptime(end_str, "%m/%d/%Y")).replace(
                    hour=23, minute=59, second=59
                )
                coupons_qs = coupons_qs.filter(created_at__range=(start_date, end_date))
            except ValueError:
                pass

        paginator = Paginator(coupons_qs, 10)
        page_number = self.request.GET.get("page", 1)
        coupons = paginator.get_page(page_number)

        supplier_products = Product.objects.filter(
            created_by=self.request.user
        ).select_related("category", "brand")
        # ---------------- PRODUCTS ----------------
        products = Product.objects.all().select_related("category", "brand")

        buyer_ids = OrderItem.objects.filter(
            product__created_by=self.request.user
        ).values_list("order__user_id", flat=True).distinct()

        clients = User.objects.filter(id__in=buyer_ids) if buyer_ids else User.objects.none()
        # clients = (
        #     User.objects.filter(id__in=buyer_ids)
        #     if buyer_ids else User.objects.none()
        # )
        clients = (
            User.objects.all()
        )

        context.update({
            "coupons": coupons,
            "page_obj": coupons,
            "products": products,
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

            start_datetime = timezone.make_aware(
                datetime.strptime(request.POST.get("start_datetime"), "%Y-%m-%dT%H:%M")
            )
            end_datetime = timezone.make_aware(
                datetime.strptime(request.POST.get("end_datetime"), "%Y-%m-%dT%H:%M")
            )

            coupon = Coupon.objects.create(
                code=code,
                coupon_type=request.POST.get("coupon_type"),
                discount_type=request.POST.get("discount_type"),
                discount=Decimal(request.POST.get("discount", "0")),
                max_discount=Decimal(request.POST.get("max_discount", "0")),
                minimum_purchase_amount=Decimal(request.POST.get("minimum_purchase_amount", "0")),
                count_of_use=int(request.POST.get("count_of_use", 1)),
                filter_by_orders_count=int(request.POST.get("filter_by_orders_count", 0)),
                filter_by_orders_amount=Decimal(request.POST.get("filter_by_orders_amount", "0")),
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                can_be_used_with_promotions=request.POST.get("can_be_used_with_promotions") == "true",
                created_by=request.user,
            )

            coupon.products.set(
                Product.objects.filter(
                    id__in=request.POST.getlist("product_ids[]"),
                    created_by=request.user
                )
            )
            coupon.client.set(User.objects.filter(id__in=request.POST.getlist("client_ids[]")))

            admin_log_activity(
                request.user,
                f"Created coupon '{coupon.code}'",
                AdminActivityLog.ActionType.CREATED
            )

            return JsonResponse({"status": "success", "message": "Coupon created successfully!"})

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


def edit_coupon(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

    coupon = get_object_or_404(Coupon, id=request.POST.get('coupon_id'))

    try:
        coupon.code = request.POST.get('code').strip().upper()
        coupon.coupon_type = request.POST.get('coupon_type')
        coupon.discount_type = request.POST.get('discount_type')
        coupon.discount = Decimal(request.POST.get('discount'))
        coupon.minimum_purchase_amount = Decimal(request.POST.get('minimum_purchase_amount', '0'))
        coupon.max_discount = Decimal(request.POST.get('max_discount', '0'))
        coupon.count_of_use = int(request.POST.get('count_of_use', 1))
        coupon.filter_by_orders_count = int(request.POST.get('filter_by_orders_count', 0))
        coupon.filter_by_orders_amount = Decimal(request.POST.get('filter_by_orders_amount', '0'))
        coupon.start_datetime = timezone.make_aware(
            datetime.strptime(request.POST.get("start_datetime"), "%Y-%m-%dT%H:%M")
        )
        coupon.end_datetime = timezone.make_aware(
            datetime.strptime(request.POST.get("end_datetime"), "%Y-%m-%dT%H:%M")
        )
        coupon.can_be_used_with_promotions = request.POST.get('can_be_used_with_promotions') == 'true'
        coupon.save()

        coupon.products.set(
            Product.objects.filter(
                created_by=request.user,
                id__in=request.POST.getlist('product_ids[]')
            )
        )
        coupon.client.set(User.objects.filter(id__in=request.POST.getlist('client_ids[]')))

        admin_log_activity(
            request.user,
            f"Updated coupon '{coupon.code}'",
            AdminActivityLog.ActionType.UPDATED
        )

        return JsonResponse({'status': 'success', 'message': 'Coupon updated successfully!'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def delete_coupon(request):
    if request.method == 'POST':
        coupon = get_object_or_404(Coupon, id=request.POST.get('coupon_id'))
        coupon_code = coupon.code
        coupon.delete()

        admin_log_activity(
            request.user,
            f"Deleted coupon '{coupon_code}'",
            AdminActivityLog.ActionType.DELETED
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
class BankView(TemplateView):
    template_name = "superuser/bank.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # ---- SEARCH ----
        search_by = self.request.GET.get("search_by", "")
        banks = Bank.objects.all()
        if search_by:
            banks = banks.filter(Q(name__icontains=search_by))

        # ---- SORT BY CREATED ----
        sort_by = self.request.GET.get("sort_by")
        if sort_by == "asc_created":
            banks = banks.order_by("created_at")
        elif sort_by == "desc_created":
            banks = banks.order_by("-created_at")
        else:
            banks = banks.order_by("-id") 

        # ---- DATE RANGE FILTER ----
        created_date = self.request.GET.get("created_date", "")
        if created_date:
            try:
                if " - " in created_date:
                    start_str, end_str = created_date.split(" - ")
                else:
                    start_str = end_str = created_date

                # Convert string to datetime object
                start_date = datetime.strptime(start_str.strip(), "%m/%d/%Y")
                end_date = datetime.strptime(end_str.strip(), "%m/%d/%Y")

                # Filter by date range
                banks = banks.filter(created_at__date__range=[start_date, end_date])
            except ValueError:
                pass

        # ---- PAGINATION ----
        page_number = self.request.GET.get("page", 1)
        per_page = self.request.GET.get("per_page", 10)
        paginator = Paginator(banks, per_page)
        page_obj = paginator.get_page(page_number)

        context["banks"] = page_obj.object_list
        context["page_obj"] = page_obj
        context["search_by"] = search_by
        context["sort_by"] = sort_by
        context["created_date"] = created_date
        return context



class AddBankView(View):
    def post(self, request):
        name = request.POST.get("name")

        if Bank.objects.filter(name__iexact=name).exists():
            return JsonResponse({"success": False, "msg": "Bank name already exists."})

        bank = Bank.objects.create(name=name)
        admin_create_activity(
            request.user,
            f"Created bank: {bank.name}"
        )

        return JsonResponse({"success": True})


class GetBankView(View):
    def get(self, request, pk):
        bank = get_object_or_404(Bank, pk=pk)
        return JsonResponse({
            "success": True,
            "data": {
                "id": bank.id,
                "name": bank.name
            }
        })
class EditBankView(View):
    def post(self, request, pk):
        bank = get_object_or_404(Bank, pk=pk)
        old_name = bank.name
        name = request.POST.get("name")

        if Bank.objects.filter(name__iexact=name).exclude(pk=pk).exists():
            return JsonResponse({
                "success": False,
                "msg": "Bank name already exists."
            })

        bank.name = name
        bank.save()
        admin_log_activity(
            request.user,
            f"Updated bank name from '{old_name}' to '{name}' (ID: {bank.id})",
            AdminActivityLog.ActionType.UPDATED
        )

        return JsonResponse({"success": True})

class DeleteBankView(View):
    def post(self, request, pk):
        bank = get_object_or_404(Bank, pk=pk)
        bank_name = bank.name
        bank.delete()

        # 🔹 Admin log
        admin_delete_activity(
            request.user,
            f"Deleted bank: {bank_name}"
        )

        return JsonResponse({"success": True})

class OriginCountryView(TemplateView):
    template_name = "superuser/origincountry.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        countries = Country.objects.all()
        search_by = self.request.GET.get("search_by")
        if search_by:
            countries = countries.filter(name__icontains=search_by)
        created_date = self.request.GET.get("created_date")
        if created_date:
            try:
                start_str, end_str = created_date.split(" - ")
                start_date = datetime.strptime(start_str.strip(), "%m/%d/%Y")
                end_date = datetime.strptime(end_str.strip(), "%m/%d/%Y")
                countries = countries.filter(
                    created_at__date__gte=start_date.date(),
                    created_at__date__lte=end_date.date()
                )
            except ValueError:
                pass
        sort_by = self.request.GET.get("sort_by", "desc_created")
        if sort_by == "asc_created":
            countries = countries.order_by("created_at")
        else: 
            countries = countries.order_by("-created_at")

        # --- Pagination ---
        page_number = self.request.GET.get("page", 1)
        paginator = Paginator(countries, 10)
        page_obj = paginator.get_page(page_number)

        # --- Context ---
        context["countries"] = page_obj.object_list
        context["page_obj"] = page_obj
        context["search_by"] = search_by or ""
        context["sort_by"] = sort_by or "desc_created"
        context["created_date"] = created_date or ""

        return context
def add_origin_country(request):
    if request.method == "POST":
        name = request.POST.get("name")

        if Country.objects.filter(name__iexact=name).exists():
            return JsonResponse({"success": False, "msg": "Country already exists"})

        country = Country.objects.create(name=name)
        admin_create_activity(
            request.user,
            f"Added origin country: {country.name}"
        )

        return JsonResponse({"success": True, "msg": "Country added successfully"})
def edit_origin_country(request, pk):
    country = get_object_or_404(Country, pk=pk)

    if request.method == "POST":
        old_name = country.name
        name = request.POST.get("name")

        if Country.objects.filter(name__iexact=name).exclude(id=pk).exists():
            return JsonResponse({"success": False, "msg": "Country already exists"})

        country.name = name
        country.save()
        admin_update_activity(
            request.user,
            f"Updated origin country from '{old_name}' to '{name}'"
        )

        return JsonResponse({"success": True, "msg": "Updated successfully"})

    return JsonResponse({"success": True, "data": {"name": country.name}})
def delete_origin_country(request, pk):
    country = get_object_or_404(Country, pk=pk)
    country_name = country.name
    country.delete()
    admin_delete_activity(
        request.user,
        f"Deleted origin country: {country_name}"
    )

    return JsonResponse({"success": True, "msg": "Deleted successfully"})
class CountryView(ListView):
    model = OriginCountry
    template_name = "superuser/country.html"
    context_object_name = "countries"
    paginate_by = 10 

    def get_queryset(self):
        queryset = super().get_queryset()

        # ---- SEARCH ----
        search_by = self.request.GET.get("search_by", "")
        if search_by:
            queryset = queryset.filter(
                Q(name_en__icontains=search_by) |
                Q(iso__icontains=search_by) |
                Q(currency__icontains=search_by)
            )

        # ---- SORT BY CREATED ----
        sort_by = self.request.GET.get("sort_by")
        if sort_by == "asc_created":
            queryset = queryset.order_by("created_at")
        else: 
            queryset = queryset.order_by("-created_at")
        # else:
        #     queryset = queryset.order_by("order", "name_en") 

        # ---- DATE RANGE FILTER ----
        created_date = self.request.GET.get("created_date", "")
        if created_date:
            try:
                if " - " in created_date:
                    start_str, end_str = created_date.split(" - ")
                else:
                    start_str = end_str = created_date

                start_date = datetime.strptime(start_str.strip(), "%m/%d/%Y")
                end_date = datetime.strptime(end_str.strip(), "%m/%d/%Y")

                queryset = queryset.filter(created_at__date__range=[start_date, end_date])
            except ValueError:
                pass  

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # ---- Currency list ----
        try:
            url = "https://open.er-api.com/v6/latest/USD"
            data = requests.get(url, timeout=5).json()
            context["currency_list"] = list(data.get("rates", {}).keys())
        except:
            context["currency_list"] = ["USD", "EUR", "INR"]
        context["search_by"] = self.request.GET.get("search_by", "")
        context["sort_by"] = self.request.GET.get("sort_by", "")
        context["created_date"] = self.request.GET.get("created_date", "")
        context["current_filters"] = self.request.GET.dict()

        return context
class CountryAddView(View):
    def post(self, request):
        name_en = request.POST.get("name_en")

        if OriginCountry.objects.filter(name_en=name_en).exists():
            return JsonResponse({"success": False, "msg": "Country already exists!"})

        country = OriginCountry.objects.create(
            name_en=name_en,
            iso=request.POST.get("iso"),
            phone_prefix=request.POST.get("phone_prefix"),
            order=request.POST.get("order"),
            currency=request.POST.get("currency"),
            is_default=request.POST.get("is_default") == "on"
        )
        admin_create_activity(
            request.user,
            f"Created country: {country.name_en}"
        )

        return JsonResponse({"success": True, "msg": "Country added successfully!"})
class CountryEditView(View):
    def post(self, request, cid):
        country = get_object_or_404(OriginCountry, id=cid)
        old_name = country.name_en

        country.name_en = request.POST.get("name_en")
        country.iso = request.POST.get("iso")
        country.phone_prefix = request.POST.get("phone_prefix")
        country.order = request.POST.get("order")
        country.currency = request.POST.get("currency")
        country.is_default = request.POST.get("is_default") == "on"
        country.save()
        admin_update_activity(
            request.user,
            f"Updated country from '{old_name}' to '{country.name_en}'"
        )

        return JsonResponse({"success": True, "msg": "Country updated!"})
class CountryDeleteView(View):
    def post(self, request, cid):
        country = get_object_or_404(OriginCountry, id=cid)
        name = country.name_en
        country.delete()
        admin_delete_activity(
            request.user,
            f"Deleted country: {name}"
        )

        return JsonResponse({"success": True, "msg": "Country deleted!"})


def get_country_list():
    try:
        url = "https://countriesnow.space/api/v0.1/countries"
        response = requests.get(url, timeout=5).json()
        country_list = [item["country"] for item in response["data"]]
        return sorted(country_list)
    except Exception as e:
        print("COUNTRY API ERROR:", e)
        return []  

class RegionView(TemplateView):
    template_name = "superuser/region.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        regions_list = Region.objects.all()

        search = self.request.GET.get("search_by")
        adv_region = self.request.GET.get("adv_region_name")
        created_range = self.request.GET.get("created_date")

        sort_by = self.request.GET.get("sort_by")
        if search:
            regions_list = regions_list.filter(name_en__icontains=search)

        if adv_region:
            regions_list = regions_list.filter(name_en__icontains=adv_region)
        if created_range:
            try:
                start_str, end_str = created_range.split(" - ")

                start_date = datetime.strptime(start_str, "%m/%d/%Y").date()
                end_date = datetime.strptime(end_str, "%m/%d/%Y").date()

                regions_list = regions_list.filter(
                    created_at__date__gte=start_date,
                    created_at__date__lte=end_date
                )

            except ValueError:
                pass
        if sort_by == "asc_created":
            regions_list = regions_list.order_by("created_at")
        else:
            regions_list = regions_list.order_by("-created_at")
        paginator = Paginator(regions_list, 8)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)
        context["page_obj"] = page_obj
        context["countries"] = get_country_list()

        return context
class RegionAddView(View):
    def post(self, request):
        name = request.POST.get("name")
        country = request.POST.get("country")

        if Region.objects.filter(name_en=name).exists():
            return JsonResponse({"success": False, "msg": "Region already exists!"})

        region = Region.objects.create(name_en=name, country=country)
        admin_create_activity(
            request.user,
            f"Created region: {region.name_en} ({region.country})"
        )

        return JsonResponse({"success": True, "msg": "Region added"})
class RegionEditView(View):
    def post(self, request, pk):
        region = get_object_or_404(Region, pk=pk)
        old_name = region.name_en

        name = request.POST.get("name")
        country = request.POST.get("country")

        if Region.objects.exclude(id=pk).filter(name_en=name).exists():
            return JsonResponse({"success": False, "msg": "Region name already exists!"})

        region.name_en = name
        region.country = country
        region.save()
        admin_update_activity(
            request.user,
            f"Updated region from '{old_name}' to '{name}'"
        )

        return JsonResponse({"success": True, "msg": "Region updated"})
class RegionDeleteView(View):
    def post(self, request, pk):
        region = get_object_or_404(Region, pk=pk)
        region_name = region.name_en
        region.delete()
        admin_delete_activity(
            request.user,
            f"Deleted region: {region_name}"
        )

        return JsonResponse({"success": True, "msg": "Region deleted"})
class CityListView(ListView):
    model = City
    template_name = "superuser/cities.html"
    context_object_name = "cities"
    paginate_by = 8

    def get_queryset(self):
        qs = City.objects.all()
        search = self.request.GET.get("search_by")
        if search:
            qs = qs.filter(name__icontains=search)
        date_range = self.request.GET.get("created_date")

        if date_range:
            try:
                start_str, end_str = date_range.split(" - ")

                start_date = datetime.strptime(start_str, "%m/%d/%Y").date()
                end_date = datetime.strptime(end_str, "%m/%d/%Y").date()

                qs = qs.filter(created_at__date__gte=start_date,
                               created_at__date__lte=end_date)
            except:
                pass
        sort_by = self.request.GET.get("sort_by")
        sort_map = {
            "asc_created": "created_at",
            "desc_created": "-created_at",
        }

        if sort_by in sort_map:
            qs = qs.order_by(sort_map[sort_by])
        else:
            qs = qs.order_by("-created_at")

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["regions"] = Regioncities.objects.all()
        return ctx
class CityCreateView(View):
    def post(self, request):
        name = request.POST.get("name")
        region_id = request.POST.get("region")

        if not name or not region_id:
            return JsonResponse({"success": False, "msg": "Name and region are required"})

        region = Regioncities.objects.get(id=region_id)
        city = City.objects.create(name=name, region=region)
        admin_create_activity(
            request.user,
            f"Created city: {city.name} (Region: {region.name_en})"
        )

        return JsonResponse({"success": True})
class CityUpdateView(View):
    def post(self, request, pk):
        try:
            city = City.objects.get(id=pk)
        except City.DoesNotExist:
            return JsonResponse({"success": False, "msg": "City not found"})

        old_name = city.name
        name = request.POST.get("name")
        region_id = request.POST.get("region")

        if not name or not region_id:
            return JsonResponse({"success": False, "msg": "Name and region are required"})

        region = Regioncities.objects.get(id=region_id)
        city.name = name
        city.region = region
        city.save()
        admin_update_activity(
            request.user,
            f"Updated city from '{old_name}' to '{name}'"
        )

        return JsonResponse({"success": True})
class CityDeleteView(View):
    def post(self, request, pk):
        try:
            city = City.objects.get(id=pk)
            city_name = city.name
            city.delete()
            admin_delete_activity(
                request.user,
                f"Deleted city: {city_name}"
            )

            return JsonResponse({"success": True})
        except:
            return JsonResponse({"success": False, "msg": "Delete failed"})

class CurrencyView(ListView):
    model = Currency
    template_name = "superuser/currency.html"
    context_object_name = "currencies"
    paginate_by = 8

    def get_queryset(self):
        qs = Currency.objects.all()
        search = self.request.GET.get("search_by")
        if search:
            qs = qs.filter(name_en__icontains=search)
        date_range = self.request.GET.get("created_date")
        if date_range:
            try:
                start_str, end_str = date_range.split(" - ")
                start = datetime.strptime(start_str, "%m/%d/%Y").date()
                end = datetime.strptime(end_str, "%m/%d/%Y").date()
                qs = qs.filter(created_at__date__gte=start, created_at__date__lte=end)
            except:
                pass
        sort_by = self.request.GET.get("sort_by")
        sort_map = {
            "asc_created": "created_at",
            "desc_created": "-created_at",
            "asc_name": "name_en",
            "desc_name": "-name_en",
        }
        order_field = sort_map.get(sort_by, "-created_at")
        qs = qs.order_by(order_field)

        return qs

def add_currency(request):
    if request.method == 'POST':
        cid = request.POST.get('cid')
        name = request.POST.get('name')
        code = request.POST.get('code')
        rate = request.POST.get('rate')
        country = request.POST.get('country')
        status = request.POST.get('status') or 'Active'
        default = request.POST.get('set_as_default') == 'on'

        if cid:
            currency = get_object_or_404(Currency, id=cid)
            old_name = currency.name_en

            currency.name_en = name
            currency.code_en = code
            currency.rate = rate
            currency.country = country
            currency.status = status
            currency.set_as_default = default
            currency.save()
            admin_update_activity(
                request.user,
                f"Updated currency from '{old_name}' to '{name}'"
            )
        else:
            currency = Currency.objects.create(
                name_en=name,
                code_en=code,
                rate=rate,
                country=country,
                status=status,
                set_as_default=default
            )
            admin_create_activity(
                request.user,
                f"Created currency: {currency.name_en}"
            )

        return JsonResponse({"success": True})

    return JsonResponse({"success": False, "msg": "Invalid request"})



def delete_currency(request, pk):
    if request.method == 'POST':
        currency = get_object_or_404(Currency, id=pk)
        name = currency.name_en
        currency.delete()
        admin_delete_activity(
            request.user,
            f"Deleted currency: {name}"
        )

        return JsonResponse({"success": True})
    return JsonResponse({"success": False, "msg": "Invalid request"})

class ReturnReasonView(TemplateView):
    template_name = "superuser/returnresponse.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        reasons_list = ReturnReason.objects.all()
        search_query = self.request.GET.get('search_by', '')
        if search_query:
            reasons_list = reasons_list.filter(Q(reason_en__icontains=search_query))
        created_date = self.request.GET.get('created_date', '')
        if created_date:
            try:
                dates = created_date.split(' - ')
                if len(dates) == 2:
                    start_date = datetime.strptime(dates[0], '%m/%d/%Y')
                    end_date = datetime.strptime(dates[1], '%m/%d/%Y')
                    reasons_list = reasons_list.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
                else:
                    single_date = datetime.strptime(dates[0], '%m/%d/%Y')
                    reasons_list = reasons_list.filter(created_at__date=single_date)
            except ValueError:
                pass  
        sort_by = self.request.GET.get('sort_by', 'desc_created')
        if sort_by == 'desc_created':
            reasons_list = reasons_list.order_by('-id')
        elif sort_by == 'asc_created':
            reasons_list = reasons_list.order_by('id')
        page_number = self.request.GET.get('page', 1)
        paginator = Paginator(reasons_list, 8) 
        page_obj = paginator.get_page(page_number)
        ctx['reasons'] = page_obj.object_list
        ctx['page_obj'] = page_obj
        return ctx


def add_return_reason(request):
    if request.method == "POST":
        reason_en = request.POST.get("reason_en", "").strip()

        if reason_en == "":
            return JsonResponse({"success": False, "msg": "Reason is required."})

        reason = ReturnReason.objects.create(reason_en=reason_en)
        admin_create_activity(
            request.user,
            f"Added return reason: {reason.reason_en}"
        )

        return JsonResponse({"success": True})

    return JsonResponse({"success": False, "msg": "Invalid request."})


def edit_return_reason(request, pk):
    reason = get_object_or_404(ReturnReason, pk=pk)

    if request.method == "POST":
        old_reason = reason.reason_en
        reason_en = request.POST.get("reason_en", "").strip()

        if reason_en == "":
            return JsonResponse({"success": False, "msg": "Reason is required."})

        reason.reason_en = reason_en
        reason.save()
        admin_update_activity(
            request.user,
            f"Updated return reason from '{old_reason}' to '{reason_en}'"
        )

        return JsonResponse({"success": True})

    return JsonResponse({"success": False, "msg": "Invalid request."})
def delete_return_reason(request, pk):
    reason = get_object_or_404(ReturnReason, pk=pk)

    if request.method == "POST":
        reason_text = reason.reason_en
        reason.delete()
        admin_delete_activity(
            request.user,
            f"Deleted return reason: {reason_text}"
        )

        return JsonResponse({"success": True})

    return JsonResponse({"success": False, "msg": "Invalid request."})

class DepartmentView(TemplateView):
    template_name = "superuser/department.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = Department.objects.all()
        search_by = self.request.GET.get('search_by')
        if search_by:
            qs = qs.filter(Q(name_en__icontains=search_by))
        created_date = self.request.GET.get('created_date')
        if created_date:
            dates = [d.strip() for d in created_date.split('-')]
            if len(dates) == 2:
                created_from, created_to = dates
            else:
                created_from = created_to = dates[0]
            from datetime import datetime
            try:
                created_from = datetime.strptime(created_from, "%m/%d/%Y").date()
                created_to = datetime.strptime(created_to, "%m/%d/%Y").date()
                qs = qs.filter(created_at__date__range=[created_from, created_to])
            except ValueError:
                pass  
        sort_by = self.request.GET.get('sort_by', 'desc_created') 
        sort_mapping = {
            'asc_name': 'name_en',
            'desc_name': '-name_en',
            'asc_created': 'created_at',
            'desc_created': '-created_at',
        }
        qs = qs.order_by(sort_mapping.get(sort_by, '-created_at'))
        page_number = self.request.GET.get('page', 1)
        per_page = self.request.GET.get('per_page', 8)
        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(page_number)
        ctx['departments'] = page_obj.object_list
        ctx['page_obj'] = page_obj
        ctx['request'] = self.request 
        return ctx
def add_department(request):
    if request.method == "POST":
        name = request.POST.get("name")

        if not name or name.strip() == "":
            return JsonResponse({"success": False, "msg": "Department Name is required."})

        if Department.objects.filter(name_en=name).exists():
            return JsonResponse({"success": False, "msg": "Department already exists."})

        dep = Department.objects.create(name_en=name)
        admin_create_activity(
            request.user,
            f"Created department: {dep.name_en}"
        )

        return JsonResponse({"success": True})

    return JsonResponse({"success": False, "msg": "Invalid request!"})
def edit_department(request, pk):
    if request.method == "POST":
        name = request.POST.get("name")

        if not name or name.strip() == "":
            return JsonResponse({"success": False, "msg": "Department Name is required."})

        if Department.objects.filter(name_en=name).exclude(id=pk).exists():
            return JsonResponse({"success": False, "msg": "Department already exists."})

        try:
            dep = Department.objects.get(id=pk)
            old_name = dep.name_en
            dep.name_en = name
            dep.save()
            admin_update_activity(
                request.user,
                f"Updated department from '{old_name}' to '{name}'"
            )

            return JsonResponse({"success": True})
        except Department.DoesNotExist:
            return JsonResponse({"success": False, "msg": "Department not found!"})

    return JsonResponse({"success": False, "msg": "Invalid request!"})
def delete_department(request, pk):
    if request.method == "POST":
        try:
            dep = Department.objects.get(id=pk)
            name = dep.name_en
            dep.delete()
            admin_delete_activity(
                request.user,
                f"Deleted department: {name}"
            )

            return JsonResponse({"success": True})
        except Department.DoesNotExist:
            return JsonResponse({"success": False, "msg": "Department not found!"})

    return JsonResponse({"success": False, "msg": "Invalid request!"})

class AddressTypeView(TemplateView):
    template_name = "superuser/addresstype.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        qs = AddressType.objects.all()
        search = self.request.GET.get('search_by', '')
        if search:
            qs = qs.filter(name_en__icontains=search)
        date_range = self.request.GET.get('created_date')
        if date_range:
            try:
                start_date, end_date = [d.strip() for d in date_range.split('-')]
                from datetime import datetime
                start_date = datetime.strptime(start_date, "%m/%d/%Y")
                end_date = datetime.strptime(end_date, "%m/%d/%Y")
                qs = qs.filter(created_at__date__range=[start_date, end_date])
            except:
                pass
        sort_by = self.request.GET.get('sort_by', '-created_at')
        allowed = {
            'asc_created': 'created_at',
            'desc_created': '-created_at',
            'asc_name': 'name_en',
            'desc_name': '-name_en',
        }
        qs = qs.order_by(allowed.get(sort_by, '-created_at'))
        paginator = Paginator(qs, self.request.GET.get('per_page', 8))
        page_obj = paginator.get_page(self.request.GET.get('page'))

        ctx.update({
            'address_types': page_obj,
            'page_obj': page_obj,
            'request': self.request,
            'search_by': search,
            'sort_by': sort_by      
        })
        return ctx
def add_address_type(request):
    if request.method == "POST":
        name = request.POST.get("name_en", "").strip()
        client_type = request.POST.get("client_type")

        if not name:
            return JsonResponse({"success": False, "msg": "Name is required."})
        if AddressType.objects.filter(name_en__iexact=name).exists():
            return JsonResponse({"success": False, "msg": "This Address Type already exists."})
        obj = AddressType.objects.create(name_en=name, client_type=client_type)
        admin_create_activity(
            request.user,
            f"Created address type: {obj.name_en}"
        )
        return JsonResponse({"success": True})
    return JsonResponse({"success": False, "msg": "Invalid request"})
def edit_address_type(request, pk):
    if request.method == "POST":
        try:
            obj = AddressType.objects.get(id=pk)
        except AddressType.DoesNotExist:
            return JsonResponse({"success": False, "msg": "Address Type not found."})

        old_name = obj.name_en
        name = request.POST.get("name_en", "").strip()
        client_type = request.POST.get("client_type")

        if not name:
            return JsonResponse({"success": False, "msg": "Name is required."})

        if AddressType.objects.filter(name_en__iexact=name).exclude(id=pk).exists():
            return JsonResponse({"success": False, "msg": "This name already exists."})

        obj.name_en = name
        obj.client_type = client_type
        obj.save()
        admin_update_activity(
            request.user,
            f"Updated address type from '{old_name}' to '{name}'"
        )
        return JsonResponse({"success": True})

    return JsonResponse({"success": False, "msg": "Invalid request"})
def delete_address_type(request, pk):
    if request.method == "POST":
        try:
            obj = AddressType.objects.get(id=pk)
            name = obj.name_en
            obj.delete()
            admin_delete_activity(
                request.user,
                f"Deleted address type: {name}"
            )
            return JsonResponse({"success": True})
        except AddressType.DoesNotExist:
            return JsonResponse({"success": False, "msg": "Address Type not found."})
    return JsonResponse({"success": False, "msg": "Invalid request"})

class SupplierTypeView(TemplateView):
    template_name = "superuser/suppliertype.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        
        qs = SupplierType.objects.all()
        search_by = self.request.GET.get('search_by')
        if search_by:
            qs = qs.filter(name_en__icontains=search_by)
        created_date = self.request.GET.get('created_date')
        start_date = end_date = None
        if created_date:
            try:
                dates = created_date.split(" - ")
                if len(dates) == 2:
                    start_date = datetime.strptime(dates[0].strip(), "%m/%d/%Y")
                    end_date = datetime.strptime(dates[1].strip(), "%m/%d/%Y")
                    qs = qs.filter(created_at__date__range=[start_date, end_date])
                else:
                    single_date = datetime.strptime(dates[0].strip(), "%m/%d/%Y")
                    qs = qs.filter(created_at__date=single_date)
            except:
                pass  

        # Sorting
        sort_by = self.request.GET.get('sort_by', 'desc_created')
        sort_mapping = {
            'asc_name': 'name_en',
            'desc_name': '-name_en',
            'asc_created': 'created_at',
            'desc_created': '-created_at',
        }
        qs = qs.order_by(sort_mapping.get(sort_by, '-created_at'))

        # Pagination
        page_number = self.request.GET.get('page', 1)
        per_page = self.request.GET.get('per_page', 8)
        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(page_number)

        # Context
        ctx['supplier_types'] = page_obj.object_list
        ctx['page_obj'] = page_obj
        ctx['request'] = self.request
        ctx['search_by'] = search_by or ""
        ctx['sort_by'] = sort_by
        ctx['created_date'] = created_date or "" 
        ctx['sort_options'] = sort_mapping
        return ctx
def add_supplier_type(request):
    if request.method == "POST":
        name = request.POST.get("name_en", "").strip()
        status = request.POST.get("status")

        if not name:
            return JsonResponse({"success": False, "msg": "Name is required."})

        if SupplierType.objects.filter(name_en__iexact=name).exists():
            return JsonResponse({"success": False, "msg": "This Supplier Type already exists."})

        obj = SupplierType.objects.create(name_en=name, status=status)
        admin_create_activity(
            request.user,
            f"Created supplier type: {obj.name_en}"
        )
        return JsonResponse({"success": True})

    return JsonResponse({"success": False, "msg": "Invalid request"})
def edit_supplier_type(request, pk):
    if request.method == "POST":
        try:
            obj = SupplierType.objects.get(id=pk)
        except SupplierType.DoesNotExist:
            return JsonResponse({"success": False, "msg": "Supplier Type not found."})
        old_name = obj.name_en
        name = request.POST.get("name_en", "").strip()
        status = request.POST.get("status")
        if not name:
            return JsonResponse({"success": False, "msg": "Name is required."})

        if SupplierType.objects.filter(name_en__iexact=name).exclude(id=pk).exists():
            return JsonResponse({"success": False, "msg": "This name already exists."})

        obj.name_en = name
        obj.status = status
        obj.save()
        admin_update_activity(
            request.user,
            f"Updated supplier type from '{old_name}' to '{name}'"
        )
        return JsonResponse({"success": True})

    return JsonResponse({"success": False, "msg": "Invalid request"})
def delete_supplier_type(request, pk):
    if request.method == "POST":
        try:
            obj = SupplierType.objects.get(id=pk)
            name = obj.name_en
            obj.delete()
            admin_delete_activity(
                request.user,
                f"Deleted supplier type: {name}"
            )
            return JsonResponse({"success": True})
        except SupplierType.DoesNotExist:
            return JsonResponse({"success": False, "msg": "Supplier Type not found."})
    return JsonResponse({"success": False, "msg": "Invalid request"})

class UnitView(View):
    def get(self, request):
        qs = Unit.objects.all()

        # ---- SEARCH ----
        search_by = request.GET.get("search_by")
        if search_by:
            qs = qs.filter(Q(name__icontains=search_by))

        # ---- SORT BY CREATED (Unified) ----
        sort_by = self.request.GET.get("sort_by")
        if sort_by == "asc_created":
            qs = qs.order_by("created_at")
        else: 
            qs = qs.order_by("-created_at")

        # ---- DATE RANGE ----
        created_date = request.GET.get("created_date")
        if created_date:
            try:
                if " - " in created_date:
                    start_str, end_str = created_date.split(" - ")
                else:
                    start_str = end_str = created_date

                start_date = datetime.strptime(start_str.strip(), "%m/%d/%Y")
                end_date = datetime.strptime(end_str.strip(), "%m/%d/%Y")
                qs = qs.filter(created_at__date__range=[start_date, end_date])
            except ValueError:
                pass

        # ---- PAGINATION ----
        page = request.GET.get("page", 1)
        per_page = request.GET.get("per_page", 8)
        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(page)

        return render(request, "superuser/unit.html", {
            "units": page_obj.object_list,
            "page_obj": page_obj,
            "request": request,
        })
class AddUnitView(View):
    def post(self, request):
        name = request.POST.get('name')
        status = request.POST.get('status')

        if not name:
            return JsonResponse({'success': False, 'msg': 'Name is required.'})
        if not status:
            return JsonResponse({'success': False, 'msg': 'Status is required.'})
        if Unit.objects.filter(name__iexact=name).exists():
            return JsonResponse({'success': False, 'msg': 'Unit with this name already exists.'})
        unit = Unit.objects.create(name=name, status=status)
        admin_create_activity(
            request.user,
            f"Created unit: {unit.name}"
        )

        return JsonResponse({'success': True})
class EditUnitView(View):
    def post(self, request, id):
        unit = get_object_or_404(Unit, id=id)
        old_name = unit.name
        name = request.POST.get('name')
        status = request.POST.get('status')

        if not name:
            return JsonResponse({'success': False, 'msg': 'Name is required.'})
        if not status:
            return JsonResponse({'success': False, 'msg': 'Status is required.'})
        if Unit.objects.filter(name__iexact=name).exclude(id=id).exists():
            return JsonResponse({'success': False, 'msg': 'Another unit with this name already exists.'})

        unit.name = name
        unit.status = status
        unit.save()
        admin_update_activity(
            request.user,
            f"Updated unit from '{old_name}' to '{name}'"
        )

        return JsonResponse({'success': True})
class DeleteUnitView(View):
    def post(self, request, id):
        unit = get_object_or_404(Unit, id=id)
        name = unit.name
        unit.delete()
        admin_delete_activity(
            request.user,
            f"Deleted unit: {name}"
        )

        return JsonResponse({'success': True})

class DeliveryTimeView(View):
    def get(self, request):
        qs = DeliveryTime.objects.all()

        # ---- SEARCH ----
        search_by = request.GET.get("search_by")
        if search_by:
            qs = qs.filter(Q(name__icontains=search_by))

        # ---- SORT BY CREATED ----
        sort_by = request.GET.get("sort_by")
        if sort_by == "asc_created":
            qs = qs.order_by("created_at")
        else:
            qs = qs.order_by("-created_at")

        # ---- DATE RANGE ----
        created_date = request.GET.get("created_date")
        if created_date:
            try:
                if " - " in created_date:
                    start_str, end_str = created_date.split(" - ")
                else:
                    start_str = end_str = created_date
                start_date = datetime.strptime(start_str.strip(), "%m/%d/%Y")
                end_date = datetime.strptime(end_str.strip(), "%m/%d/%Y")
                qs = qs.filter(created_at__date__range=[start_date, end_date])
            except ValueError:
                pass

        # ---- PAGINATION ----
        paginator = Paginator(qs, request.GET.get("per_page", 10))
        page_obj = paginator.get_page(request.GET.get("page", 1))

        return render(request, "superuser/deliverytime.html", {
            "delivery_times": page_obj.object_list,
            "page_obj": page_obj,
            "request": request,
        })
class DeliveryTimeAddView(View):
    def post(self, request):
        name = request.POST.get('name')
        status = request.POST.get('status')

        if not name:
            return JsonResponse({'success': False, 'msg': 'Name is required.'})
        if not status:
            return JsonResponse({'success': False, 'msg': 'Status is required.'})

        delivery = DeliveryTime.objects.create(name=name, status=status)

        admin_create_activity(
            request.user,
            f"Created Delivery Time: {delivery.name}"
        )

        return JsonResponse({'success': True})
class DeliveryTimeEditView(View):
    def post(self, request, pk):
        delivery = get_object_or_404(DeliveryTime, pk=pk)
        name = request.POST.get('name')
        status = request.POST.get('status')

        if not name:
            return JsonResponse({'success': False, 'msg': 'Name is required.'})
        if not status:
            return JsonResponse({'success': False, 'msg': 'Status is required.'})

        delivery.name = name
        delivery.status = status
        delivery.save()

        admin_update_activity(
            request.user,
            f"Updated Delivery Time: {delivery.name}"
        )

        return JsonResponse({'success': True})
class DeliveryTimeDeleteView(View):
    def post(self, request, pk):
        delivery = get_object_or_404(DeliveryTime, pk=pk)
        name = delivery.name
        delivery.delete()

        admin_delete_activity(
            request.user,
            f"Deleted Delivery Time: {name}"
        )

        return JsonResponse({'success': True})

class ReturnTimeView(View):
    def get(self, request):
        qs = ReturnTime.objects.all()

        # ---- SEARCH ----
        search_by = request.GET.get("search_by")
        if search_by:
            qs = qs.filter(
                Q(name__icontains=search_by) |
                Q(value__icontains=search_by)
            )

        # ---- SORT BY CREATED ----
        sort_by = request.GET.get("sort_by")
        if sort_by == "asc_created":
            qs = qs.order_by("created_at")
        else:
            qs = qs.order_by("-created_at")

        # ---- DATE RANGE ----
        created_date = request.GET.get("created_date")
        if created_date:
            try:
                if " - " in created_date:
                    start_str, end_str = created_date.split(" - ")
                else:
                    start_str = end_str = created_date
                start_date = datetime.strptime(start_str.strip(), "%m/%d/%Y")
                end_date = datetime.strptime(end_str.strip(), "%m/%d/%Y")
                qs = qs.filter(created_at__date__range=[start_date, end_date])
            except ValueError:
                pass

        # ---- PAGINATION ----
        paginator = Paginator(qs, request.GET.get("per_page", 10))
        page_obj = paginator.get_page(request.GET.get("page", 1))

        return render(request, "superuser/ReturnTime.html", {
            "return_times": page_obj.object_list,
            "page_obj": page_obj,
            "request": request,
        })
class ReturnTimeAddView(View):
    def post(self, request):
        name = request.POST.get('name')
        value = request.POST.get('value')
        status = request.POST.get('status')

        if not name or not value or not status:
            return JsonResponse({'success': False, 'msg': 'All fields are required.'})

        return_time = ReturnTime.objects.create(
            name=name, value=value, status=status
        )

        admin_create_activity(
            request.user,
            f"Created Return Time: {return_time.name}"
        )

        return JsonResponse({'success': True})
class ReturnTimeEditView(View):
    def post(self, request, pk):
        return_time = get_object_or_404(ReturnTime, pk=pk)

        name = request.POST.get('name')
        value = request.POST.get('value')
        status = request.POST.get('status')

        if not name or not value or not status:
            return JsonResponse({'success': False, 'msg': 'All fields are required.'})

        return_time.name = name
        return_time.value = value
        return_time.status = status
        return_time.save()

        admin_update_activity(
            request.user,
            f"Updated Return Time: {return_time.name}"
        )

        return JsonResponse({'success': True})
class ReturnTimeDeleteView(View):
    def post(self, request, pk):
        return_time = get_object_or_404(ReturnTime, pk=pk)
        name = return_time.name
        return_time.delete()

        admin_delete_activity(
            request.user,
            f"Deleted Return Time: {name}"
        )

        return JsonResponse({'success': True})

class StandingTimeView(View):
    def get(self, request):
        qs = StandingTime.objects.all()

        # ---- SEARCH ----
        search_by = request.GET.get("search_by")
        if search_by:
            qs = qs.filter(
                Q(name__icontains=search_by) |
                Q(value__icontains=search_by)
            )

        # ---- SORT BY CREATED ----
        sort_by = request.GET.get("sort_by")
        if sort_by == "asc_created":
            qs = qs.order_by("created_at")
        else:
            qs = qs.order_by("-created_at")

        # ---- DATE RANGE ----
        created_date = request.GET.get("created_date")
        if created_date:
            try:
                if " - " in created_date:
                    start_str, end_str = created_date.split(" - ")
                else:
                    start_str = end_str = created_date
                start_date = datetime.strptime(start_str.strip(), "%m/%d/%Y")
                end_date = datetime.strptime(end_str.strip(), "%m/%d/%Y")
                qs = qs.filter(created_at__date__range=[start_date, end_date])
            except ValueError:
                pass

        # ---- PAGINATION ----
        paginator = Paginator(qs, request.GET.get("per_page", 10))
        page_obj = paginator.get_page(request.GET.get("page", 1))

        return render(request, "superuser/StandingTime.html", {
            "return_times": page_obj.object_list,
            "page_obj": page_obj,
            "request": request,
        })
class StandigTimeAddView(View):
    def post(self, request):
        name = request.POST.get('name')
        value = request.POST.get('value')
        status = request.POST.get('status')

        if not name or not value or not status:
            return JsonResponse({'success': False, 'msg': 'All fields are required.'})

        standing = StandingTime.objects.create(
            name=name, value=value, status=status
        )

        admin_create_activity(
            request.user,
            f"Created Standing Time: {standing.name}"
        )

        return JsonResponse({'success': True})
class StandingTimeEditView(View):
    def post(self, request, pk):
        standing = get_object_or_404(StandingTime, pk=pk)

        name = request.POST.get('name')
        value = request.POST.get('value')
        status = request.POST.get('status')

        if not name or not value or not status:
            return JsonResponse({'success': False, 'msg': 'All fields are required.'})

        standing.name = name
        standing.value = value
        standing.status = status
        standing.save()

        admin_update_activity(
            request.user,
            f"Updated Standing Time: {standing.name}"
        )

        return JsonResponse({'success': True})
class StandingTimeDeleteView(View):
    def post(self, request, pk):
        standing = get_object_or_404(StandingTime, pk=pk)
        name = standing.name
        standing.delete()

        admin_delete_activity(
            request.user,
            f"Deleted Standing Time: {name}"
        )

        return JsonResponse({'success': True})

class WarrantyView(View):
    def get(self, request):
        qs = Warranty.objects.all()

        # ---- SEARCH ----
        search_by = request.GET.get("search_by")
        if search_by:
            qs = qs.filter(Q(name__icontains=search_by))

        # ---- SORT BY CREATED ----
        sort_by = request.GET.get("sort_by")
        if sort_by == "asc_created":
            qs = qs.order_by("created_at")
        else:
            qs = qs.order_by("-created_at")

        # ---- DATE RANGE ----
        created_date = request.GET.get("created_date")
        if created_date:
            try:
                if " - " in created_date:
                    start_str, end_str = created_date.split(" - ")
                else:
                    start_str = end_str = created_date

                start_date = datetime.strptime(start_str.strip(), "%m/%d/%Y")
                end_date = datetime.strptime(end_str.strip(), "%m/%d/%Y")

                qs = qs.filter(created_at__date__range=[start_date, end_date])
            except ValueError:
                pass

        # ---- PAGINATION ----
        page = request.GET.get("page", 1)
        per_page = request.GET.get("per_page", 10)
        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(page)

        return render(request, "superuser/warranty.html", {
            "warranties": page_obj.object_list,
            "page_obj": page_obj,
            "request": request,
        })


class AddWarrantyView(View):
    def post(self, request):
        name = request.POST.get('name')
        status = request.POST.get('status')

        if not name:
            return JsonResponse({'success': False, 'msg': 'Name is required.'})
        if not status:
            return JsonResponse({'success': False, 'msg': 'Status is required.'})
        if Warranty.objects.filter(name__iexact=name).exists():
            return JsonResponse({'success': False, 'msg': 'Warranty with this name already exists.'})

        Warranty.objects.create(name=name, status=status)
        admin_create_activity(
            request.user,
            f"Created Warranty: {name}"
        )
        return JsonResponse({'success': True})

class EditWarrantyView(View):
    def post(self, request, pk):
        warranty = get_object_or_404(Warranty, pk=pk)
        name = request.POST.get('name')
        status = request.POST.get('status')

        if not name:
            return JsonResponse({'success': False, 'msg': 'Name is required.'})
        if not status:
            return JsonResponse({'success': False, 'msg': 'Status is required.'})
        if Warranty.objects.filter(name__iexact=name).exclude(pk=pk).exists():
            return JsonResponse({'success': False, 'msg': 'Another warranty with this name already exists.'})

        warranty.name = name
        warranty.status = status
        warranty.save()
        admin_create_activity(
            request.user,
            f"Update Warranty: {name}"
        )
        return JsonResponse({'success': True})

class DeleteWarrantyView(View):
    def post(self, request, pk):
        warranty = get_object_or_404(Warranty, pk=pk)
        admin_create_activity(
            request.user,
            f"Delete Warannty: {warranty.name}"
        )
        warranty.delete()
        
        return JsonResponse({'success': True})
class SplashScreenView(TemplateView):
    template_name = "superuser/SplashScreen.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = SplashScreen.objects.all()

        # ---- SEARCH FILTER ----
        search_by = self.request.GET.get("search_by")
        if search_by:
            qs = qs.filter(
                Q(screen_title__icontains=search_by) |
                Q(screen_language__icontains=search_by)
            )

        # ---- SORT BY CREATED ----
        sort_by = self.request.GET.get("sort_by")
        if sort_by == "asc_created":
            qs = qs.order_by("created_at")
        elif sort_by == "desc_created":
            qs = qs.order_by("-created_at")
        else:
            qs = qs.order_by("screen_order")  

        # ---- DATE RANGE FILTER ----
        created_date = self.request.GET.get("created_date")
        if created_date:
            try:
                if " - " in created_date:
                    start_str, end_str = created_date.split(" - ")
                else:
                    start_str = end_str = created_date

                start_date = datetime.strptime(start_str.strip(), "%m/%d/%Y")
                end_date = datetime.strptime(end_str.strip(), "%m/%d/%Y")

                qs = qs.filter(created_at__date__range=[start_date, end_date])
            except ValueError:
                pass 

        # ---- PAGINATION ----
        page_number = self.request.GET.get("page", 1)
        per_page = self.request.GET.get("per_page", 10)
        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(page_number)

        context["screens"] = page_obj.object_list
        context["page_obj"] = page_obj
        context["search_by"] = search_by
        context["sort_by"] = sort_by
        context["created_date"] = created_date  
        return context
class SplashScreenAddView(View):
    def post(self, request):
        screen_image = request.FILES.get('screen_image')
        screen_text = request.POST.get('screen_text')
        screen_title = request.POST.get('screen_title', '').strip()
        screen_body = request.POST.get('screen_body', '').strip()
        screen_order = request.POST.get('screen_order', '').strip()
        screen_language = request.POST.get('screen_language', '').strip()

        if not screen_title:
            return JsonResponse({'success': False, 'field': 'title', 'msg': 'Screen Title is required.'})
        if not screen_body:
            return JsonResponse({'success': False, 'field': 'body', 'msg': 'Screen Body is required.'})
        if not screen_order:
            return JsonResponse({'success': False, 'field': 'order', 'msg': 'Screen Order is required.'})
        if not screen_language:
            return JsonResponse({'success': False, 'field': 'language', 'msg': 'Screen Language is required.'})
        if not screen_image:
            return JsonResponse({'success': False, 'field': 'image', 'msg': 'Screen Image is required.'})

        screen = SplashScreen.objects.create(
            screen_image=screen_image,
            screen_text=screen_text,
            screen_title=screen_title,
            screen_body=screen_body,
            screen_order=screen_order,
            screen_language=screen_language
        )

        admin_create_activity(
            request.user,
            f"Created Splash Screen: {screen.screen_title}"
        )

        return JsonResponse({'success': True})
class SplashScreenEditView(View):
    def post(self, request, pk):
        screen = get_object_or_404(SplashScreen, pk=pk)

        screen_text = request.POST.get('screen_text')
        screen_title = request.POST.get('screen_title', '').strip()
        screen_body = request.POST.get('screen_body', '').strip()
        screen_order = request.POST.get('screen_order', '').strip()
        screen_language = request.POST.get('screen_language', '').strip()

        if not screen_title:
            return JsonResponse({'success': False, 'field': 'title', 'msg': 'Screen Title is required.'})
        if not screen_body:
            return JsonResponse({'success': False, 'field': 'body', 'msg': 'Screen Body is required.'})
        if not screen_order:
            return JsonResponse({'success': False, 'field': 'order', 'msg': 'Screen Order is required.'})
        if not screen_language:
            return JsonResponse({'success': False, 'field': 'language', 'msg': 'Screen Language is required.'})

        screen.screen_text = screen_text
        screen.screen_title = screen_title
        screen.screen_body = screen_body
        screen.screen_order = screen_order
        screen.screen_language = screen_language

        if request.FILES.get('screen_image'):
            screen.screen_image = request.FILES.get('screen_image')

        screen.save()

        admin_update_activity(
            request.user,
            f"Updated Splash Screen: {screen.screen_title}"
        )

        return JsonResponse({'success': True})
class SplashScreenDeleteView(View):
    def post(self, request, pk):
        screen = get_object_or_404(SplashScreen, pk=pk)
        title = screen.screen_title
        screen.delete()

        admin_delete_activity(
            request.user,
            f"Deleted Splash Screen: {title}"
        )

        return JsonResponse({'success': True})

class StaticcontentsView(TemplateView):
    template_name = "superuser/Staticcontents.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = Staticcontents.objects.all()

        # ---- SEARCH FILTER ----
        search_by = self.request.GET.get("search_by")
        if search_by:
            qs = qs.filter(
                Q(name_en__icontains=search_by) |
                Q(description_en__icontains=search_by)
            )

        # ---- DATE RANGE FILTER ----
        created_date = self.request.GET.get("created_date")
        if created_date:
            try:
                start_str, end_str = created_date.split(" - ")
                start_date = datetime.strptime(start_str.strip(), "%m/%d/%Y")
                end_date = datetime.strptime(end_str.strip(), "%m/%d/%Y")
                end_date = end_date.replace(hour=23, minute=59, second=59)
                qs = qs.filter(created_at__range=(start_date, end_date))
            except ValueError:
                pass  
        # ---- SORT FILTER ----
        sort_by = self.request.GET.get("sort_by")
        if sort_by == "asc_created":
            qs = qs.order_by("created_at")
        else:  
            qs = qs.order_by("-created_at")

        # ---- PAGINATION ----
        page_number = self.request.GET.get("page", 1)
        per_page = self.request.GET.get("per_page", 10)
        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(page_number)

        context.update({
            "contents": page_obj.object_list,
            "page_obj": page_obj,
            "search_by": search_by,
            "sort_by": sort_by,
            "created_date": created_date, 
        })

        return context




class AddStaticcontentView(View):
    def post(self, request):
        name_en = request.POST.get("name_en", "").strip()
        description_en = request.POST.get("description_en", "").strip()

        if not name_en:
            return JsonResponse({"success": False, "msg": "Name En is required."})
        if not description_en:
            return JsonResponse({"success": False, "msg": "Description EN is required."})

        Staticcontents.objects.create(
            name_en=name_en,
            description_en=description_en
        )
        admin_create_activity(
            request.user,
            f"Create a Static Contant: {name_en}"
        )
      
        return JsonResponse({"success": True})

class EditStaticcontentView(View):
    def post(self, request, pk):
        name_en = request.POST.get("name_en", "").strip()
        description_en = request.POST.get("description_en", "").strip()

        if not name_en:
            return JsonResponse({"success": False, "msg": "Name En is required."})
        if not description_en:
            return JsonResponse({"success": False, "msg": "Description EN is required."})

        content = get_object_or_404(Staticcontents, pk=pk)
        content.name_en = name_en
        content.description_en = description_en
        content.save()
        admin_create_activity(
            request.user,
            f"Edit Static Content: {name_en}"
        )
      
        return JsonResponse({"success": True})

class DeleteStaticcontentView(View):
    def post(self, request, pk):
        content = get_object_or_404(Staticcontents, pk=pk)
        title = getattr(content, "title", f"ID {content.pk}")
        content.delete()

        admin_delete_activity(
            request.user,
            f"Deleted Static Content: {title}"
        )

        return JsonResponse({"success": True})

class SocialLinksView(TemplateView):
    template_name = "superuser/sociallink.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = SocialLinks.objects.all()

        # ---- SEARCH FILTER ----
        search_by = self.request.GET.get("search_by")
        if search_by:
            qs = qs.filter(
                Q(title__icontains=search_by) |
                Q(link__icontains=search_by)
            )

        # ---- DATE RANGE FILTER ----
        created_date = self.request.GET.get("created_date")
        if created_date:
            try:
                start_str, end_str = created_date.split(" - ")
                start_date = datetime.strptime(start_str.strip(), "%m/%d/%Y")
                end_date = datetime.strptime(end_str.strip(), "%m/%d/%Y")
                end_date = end_date.replace(hour=23, minute=59, second=59)
                qs = qs.filter(created_at__range=(start_date, end_date))
            except ValueError:
                pass  

        # ---- SORT FILTER ----
        sort_by = self.request.GET.get("sort_by")
        if sort_by == "asc_created":
            qs = qs.order_by("created_at")
        elif sort_by == "desc_created":
            qs = qs.order_by("-created_at")
        else:
            qs = qs.order_by("-id")  

        # ---- PAGINATION ----
        page_number = self.request.GET.get("page", 1)
        per_page = self.request.GET.get("per_page", 10)
        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(page_number)

        context.update({
            "links": page_obj.object_list,
            "page_obj": page_obj,
            "search_by": search_by,
            "sort_by": sort_by,
            "created_date": created_date, 
        })

        return context
class AddSocialLinkView(View):
    def post(self, request):
        title = request.POST.get("title", "").strip()
        link = request.POST.get("link", "").strip()

        if not title:
            return JsonResponse({"success": False, "msg": "Title is required."})
        if not link:
            return JsonResponse({"success": False, "msg": "Link is required."})

        social = SocialLinks.objects.create(title=title, link=link)

        admin_create_activity(
            request.user,
            f"Created Social Link: {social.title}"
        )

        return JsonResponse({"success": True})
class EditSocialLinkView(View):
    def post(self, request, pk):
        title = request.POST.get("title", "").strip()
        link = request.POST.get("link", "").strip()

        if not title:
            return JsonResponse({"success": False, "msg": "Title is required."})
        if not link:
            return JsonResponse({"success": False, "msg": "Link is required."})

        try:
            link_obj = SocialLinks.objects.get(pk=pk)
            link_obj.title = title
            link_obj.link = link
            link_obj.save()

            admin_update_activity(
                request.user,
                f"Updated Social Link: {link_obj.title}"
            )

            return JsonResponse({"success": True})

        except SocialLinks.DoesNotExist:
            return JsonResponse({"success": False, "msg": "Record not found."})
class DeleteSocialLinkView(View):
    def post(self, request, pk):
        try:
            link_obj = SocialLinks.objects.get(pk=pk)
            title = link_obj.title
            link_obj.delete()

            admin_delete_activity(
                request.user,
                f"Deleted Social Link: {title}"
            )

            return JsonResponse({"success": True})

        except SocialLinks.DoesNotExist:
            return JsonResponse({"success": False, "msg": "Record not found."})

class FaqView(TemplateView):
    template_name = "superuser/faq.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = FaqForm.objects.all()

        # ---- SEARCH FILTER ----
        search_by = self.request.GET.get("search_by")
        if search_by:
            qs = qs.filter(
                Q(title_en__icontains=search_by) |
                Q(description_en__icontains=search_by)
            )

        # ---- DATE RANGE FILTER ----
        created_date = self.request.GET.get("created_date")
        if created_date:
            try:
                start_str, end_str = created_date.split(" - ")
                start_date = datetime.strptime(start_str.strip(), "%m/%d/%Y")
                end_date = datetime.strptime(end_str.strip(), "%m/%d/%Y")
                end_date = end_date.replace(hour=23, minute=59, second=59)
                qs = qs.filter(created_at__range=(start_date, end_date))
            except ValueError:
                pass  

        # ---- SORT FILTER ----
        sort_by = self.request.GET.get("sort_by")
        if sort_by == "asc_created":
            qs = qs.order_by("created_at")
        elif sort_by == "desc_created":
            qs = qs.order_by("-created_at")
        elif sort_by == "asc_title":
            qs = qs.order_by("title_en")
        elif sort_by == "desc_title":
            qs = qs.order_by("-title_en")
        else:
            qs = qs.order_by("-id")  

        # ---- PAGINATION ----
        page_number = self.request.GET.get("page", 1)
        per_page = self.request.GET.get("per_page", 10)
        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(page_number)

        context.update({
            "faqs": page_obj.object_list,
            "page_obj": page_obj,
            "search_by": search_by,
            "sort_by": sort_by,
            "created_date": created_date, 
        })

        return context
class AddFaqView(View):
    def post(self, request):
        title = request.POST.get('title_en')
        desc = request.POST.get('description_en')

        if not title or not desc:
            return JsonResponse({'success': False, 'msg': 'All fields are required.'})

        faq = FaqForm.objects.create(title_en=title, description_en=desc)

        admin_create_activity(
            request.user,
            f"Created FAQ: {faq.title_en}"
        )

        return JsonResponse({
            'success': True,
            'msg': 'FAQ added successfully!',
            'id': faq.id
        })
class EditFaqView(View):
    def post(self, request, pk):
        faq = get_object_or_404(FaqForm, pk=pk)
        title = request.POST.get('title_en')
        desc = request.POST.get('description_en')

        if not title or not desc:
            return JsonResponse({'success': False, 'msg': 'All fields are required.'})

        faq.title_en = title
        faq.description_en = desc
        faq.save()

        admin_update_activity(
            request.user,
            f"Updated FAQ: {faq.title_en}"
        )

        return JsonResponse({'success': True, 'msg': 'FAQ updated successfully!'})
class DeleteFaqView(View):
    def post(self, request, pk):
        faq = get_object_or_404(FaqForm, pk=pk)
        title = faq.title_en
        faq.delete()

        admin_delete_activity(
            request.user,
            f"Deleted FAQ: {title}"
        )

        return JsonResponse({
            'success': True,
            'msg': 'FAQ deleted successfully!'
        })

class AdminListView(TemplateView):
    template_name = "superuser/adminlist.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['links'] = AdminUser.objects.select_related('user').all()
        return context

class AddAdminView(View):
    def post(self, request):
        name = request.POST.get('name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        role = request.POST.get('role')

        if password != confirm_password:
            return JsonResponse({'success': False, 'msg': 'Passwords do not match!'})

        if User.objects.filter(username=username).exists():
            return JsonResponse({'success': False, 'msg': 'Username already exists!'})

        user = User.objects.create(
            first_name=name,
            username=username,
            email=email,
            password=make_password(password)
        )
        AdminUser.objects.create(user=user, role=role)
        return JsonResponse({'success': True})
class EditAdminView(View):
    def post(self, request, pk):
        admin_user = get_object_or_404(AdminUser, pk=pk)
        user = admin_user.user

        name = request.POST.get('name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        role = request.POST.get('role')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        if username and username != user.username:
            if User.objects.filter(username=username).exclude(pk=user.pk).exists():
                return JsonResponse({'success': False, 'msg': 'Username is already taken.'})
        if email and email != user.email:
            if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                return JsonResponse({'success': False, 'msg': 'Email is already taken.'})

        if password or confirm_password:
            if password != confirm_password:
                return JsonResponse({'success': False, 'msg': 'Passwords do not match.'})
            user.set_password(password)

        user.first_name = name
        user.username = username
        user.email = email
        user.save()

        admin_user.role = role
        admin_user.save()

        return JsonResponse({'success': True})
class DeleteAdminView(View):
    def post(self, request, pk):
        admin_user = get_object_or_404(AdminUser, pk=pk)
        admin_user.user.delete()
        admin_user.delete()
        return JsonResponse({'success': True})
class SiteMessagesView(TemplateView):
    template_name = "superuser/SiteMessages.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = Contact.objects.all()

        # ---- SEARCH FILTER ----
        search_by = self.request.GET.get("search_by")
        if search_by:
            qs = qs.filter(
                Q(full_name__icontains=search_by) |
                Q(email__icontains=search_by) |
                Q(phone__icontains=search_by) |
                Q(subject__icontains=search_by) |
                Q(message__icontains=search_by)
            )

        # ---- DATE RANGE FILTER ----
        created_date = self.request.GET.get("created_date")
        if created_date:
            try:
                start_str, end_str = created_date.split(" - ")
                start_date = datetime.strptime(start_str.strip(), "%m/%d/%Y")
                end_date = datetime.strptime(end_str.strip(), "%m/%d/%Y")
           
                end_date = end_date.replace(hour=23, minute=59, second=59)
                qs = qs.filter(created_at__range=(start_date, end_date))
            except ValueError:
                pass  

        # ---- SORT FILTER ----
        sort_by = self.request.GET.get("sort_by")
        if sort_by == "asc_created":
            qs = qs.order_by("created_at")
        elif sort_by == "desc_created":
            qs = qs.order_by("-created_at")
        elif sort_by == "asc_name":
            qs = qs.order_by("full_name")
        elif sort_by == "desc_name":
            qs = qs.order_by("-full_name")
        else:
            qs = qs.order_by("-created_at") 

        # ---- PAGINATION ----
        page_number = self.request.GET.get("page", 1)
        per_page = self.request.GET.get("per_page", 10)
        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(page_number)

        context.update({
            "contacts": page_obj.object_list,
            "page_obj": page_obj,
            "search_by": search_by,
            "sort_by": sort_by,
            "created_date": created_date,  
        })

        return context
class ContactDeleteView(View):
    def post(self, request, pk):
        contact = get_object_or_404(Contact, pk=pk)
        name = getattr(contact, "name", f"ID {contact.pk}")
        contact.delete()

        admin_delete_activity(
            request.user,
            f"Deleted Contact: {name}"
        )

        return JsonResponse({'success': True})


from dashboard.forms import RetailProfileForm, WholesaleBuyerProfileForm, SupplierProfileForm
from datetime import datetime, time
class DynamicInputListView(View):
    template_name = 'superuser/DynamicInputs.html'

    def get(self, request):
        inputs = DynamicInput.objects.all()

        # ---- SEARCH ----
        search_by = request.GET.get("search_by")
        if search_by:
            inputs = inputs.filter(
                Q(title_en__icontains=search_by) |
                Q(form_name__icontains=search_by) |
                Q(field_type__icontains=search_by)
            )

        # ---- CREATED DATE RANGE FILTER ----
        created_date = request.GET.get("created_date")
        if created_date:
            try:
                start_str, end_str = created_date.split(" - ")

                start_date = datetime.strptime(start_str, "%m/%d/%Y")
                end_date = datetime.strptime(end_str, "%m/%d/%Y")
                start_date = datetime.combine(start_date.date(), time.min)
                end_date = datetime.combine(end_date.date(), time.max)

                inputs = inputs.filter(
                    created_at__range=(start_date, end_date)
                )
            except ValueError:
                pass 
        # ---- SORT ----
        sort_by = request.GET.get("sort_by")
        if sort_by == "asc_created":
            inputs = inputs.order_by("created_at")
        else:
            inputs = inputs.order_by("-created_at")

        # ---- PAGINATION ----
        page_number = request.GET.get("page", 1)
        per_page = request.GET.get("per_page", 10)
        paginator = Paginator(inputs, per_page)
        page_obj = paginator.get_page(page_number)

        form_classes = [
            RetailProfileForm,
            WholesaleBuyerProfileForm,
            SupplierProfileForm
        ]
        form_names = [f.__name__ for f in form_classes]

        return render(request, self.template_name, {
            'inputs': page_obj.object_list,
            'form_names': form_names,
            'page_obj': page_obj,
            'search_by': search_by,
            'sort_by': sort_by,
            'created_date': created_date
        })
class DynamicInputAddView(View):
    def post(self, request):
        try:
            form_name = request.POST.get('form_name')
            field_type = request.POST.get('field_type')
            title_en = request.POST.get('title_en')
            required = request.POST.get('required') == 'on'
            status = request.POST.get('status') == 'on'

            obj = DynamicInput.objects.create(
                form_name=form_name,
                field_type=field_type,
                title_en=title_en,
                required=required,
                status=status
            )

            admin_create_activity(
                request.user,
                f"Created Dynamic Input: {obj.title_en}"
            )

            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'msg': str(e)})
class DynamicInputEditView(View):
    def post(self, request, pk):
        try:
            obj = get_object_or_404(DynamicInput, pk=pk)

            obj.form_name = request.POST.get('form_name')
            obj.field_type = request.POST.get('field_type')
            obj.title_en = request.POST.get('title_en')
            obj.required = request.POST.get('required') == 'on'
            obj.status = request.POST.get('status') == 'on'
            obj.save()

            admin_update_activity(
                request.user,
                f"Updated Dynamic Input: {obj.title_en}"
            )

            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'msg': str(e)})
class DynamicInputDeleteView(View):
    def post(self, request, pk):
        try:
            obj = get_object_or_404(DynamicInput, pk=pk)
            title = obj.title_en
            obj.delete()

            admin_delete_activity(
                request.user,
                f"Deleted Dynamic Input: {title}"
            )

            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'msg': str(e)})

class FormControlsView(TemplateView):
    template_name = "superuser/FormControls.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = FormControl.objects.all()

        search_by = self.request.GET.get("search_by")
        if search_by:
            qs = qs.filter(Q(name__icontains=search_by) | Q(form__icontains=search_by))

        created_date = self.request.GET.get("created_date")
        if created_date:
            try:
                start_str, end_str = created_date.split(" - ")
                qs = qs.filter(
                    created_at__date__gte=datetime.strptime(start_str, "%m/%d/%Y").date(),
                    created_at__date__lte=datetime.strptime(end_str, "%m/%d/%Y").date()
                )
            except ValueError:
                pass

        sort_by = self.request.GET.get("sort_by")
        qs = qs.order_by("created_at" if sort_by == "asc_created" else "-created_at")

        paginator = Paginator(qs, self.request.GET.get("per_page", 10))
        page_obj = paginator.get_page(self.request.GET.get("page", 1))

        context.update({
            "controls": page_obj.object_list,
            "page_obj": page_obj,
            "search_by": search_by,
            "sort_by": sort_by,
        })
        return context


class FormControlToggleView(View):
    def post(self, request, pk):
        form_control = get_object_or_404(FormControl, pk=pk)
        data = json.loads(request.body)
        field = data.get('field')
        value = data.get('value')

        if field in ['required', 'status']:
            setattr(form_control, field, value)
            form_control.save()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False})
    
class CatalogView(TemplateView):
    template_name = "superuser/Catalog.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = Catalog.objects.all()

        search_by = self.request.GET.get("search_by")
        if search_by:
            qs = qs.filter(Q(key__icontains=search_by) | Q(description__icontains=search_by))

        created_date = self.request.GET.get("created_date")
        if created_date:
            try:
                start_str, end_str = created_date.split(" - ")
                qs = qs.filter(
                    created_at__date__gte=datetime.strptime(start_str, "%m/%d/%Y").date(),
                    created_at__date__lte=datetime.strptime(end_str, "%m/%d/%Y").date()
                )
            except ValueError:
                pass

        sort_by = self.request.GET.get("sort_by")
        qs = qs.order_by("created_at" if sort_by == "asc_created" else "-created_at")

        paginator = Paginator(qs, self.request.GET.get("per_page", 10))
        page_obj = paginator.get_page(self.request.GET.get("page", 1))

        context.update({
            "catalogs": page_obj.object_list,
            "page_obj": page_obj,
            "search_by": search_by,
            "sort_by": sort_by,
        })
        return context
def add_catalog(request):
    if request.method == "POST":
        key = request.POST.get("key", "").strip()
        description = request.POST.get("description", "").strip()

        if not key:
            return JsonResponse({"success": False, "msg": "Key is required."})
        if not description:
            return JsonResponse({"success": False, "msg": "Description is required."})

        if Catalog.objects.filter(key=key).exists():
            return JsonResponse({"success": False, "msg": "Key must be unique."})

        catalog = Catalog.objects.create(key=key, description=description)

        admin_create_activity(
            request.user,
            f"Created Catalog: {catalog.key}"
        )

        return JsonResponse({"success": True})
def edit_catalog(request, pk):
    catalog = Catalog.objects.get(id=pk)

    if request.method == "POST":
        key = request.POST.get("key", "").strip()
        description = request.POST.get("description", "").strip()

        if not key:
            return JsonResponse({"success": False, "msg": "Key is required."})
        if not description:
            return JsonResponse({"success": False, "msg": "Description is required."})

        if Catalog.objects.filter(key=key).exclude(id=pk).exists():
            return JsonResponse({"success": False, "msg": "Key must be unique."})

        catalog.key = key
        catalog.description = description
        catalog.save()

        admin_update_activity(
            request.user,
            f"Updated Catalog: {catalog.key}"
        )

        return JsonResponse({"success": True})
def delete_catalog(request, pk):
    catalog = Catalog.objects.filter(id=pk).first()
    key = catalog.key if catalog else f"ID {pk}"

    Catalog.objects.filter(id=pk).delete()

    admin_delete_activity(
        request.user,
        f"Deleted Catalog: {key}"
    )

    return JsonResponse({"success": True})

class ConfigurationView(TemplateView):
    template_name = "superuser/configuration.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = Configuration.objects.all()

        search_by = self.request.GET.get("search_by")
        if search_by:
            qs = qs.filter(key__icontains=search_by)

        created_date = self.request.GET.get("created_date")
        if created_date:
            try:
                start_str, end_str = created_date.split(" - ")
                qs = qs.filter(
                    created_at__date__gte=datetime.strptime(start_str, "%m/%d/%Y").date(),
                    created_at__date__lte=datetime.strptime(end_str, "%m/%d/%Y").date()
                )
            except ValueError:
                pass

        sort_by = self.request.GET.get("sort_by")
        qs = qs.order_by("created_at" if sort_by == "asc_created" else "-created_at")

        paginator = Paginator(qs, self.request.GET.get("per_page", 10))
        page_obj = paginator.get_page(self.request.GET.get("page", 1))

        context.update({
            "configs": page_obj.object_list,
            "page_obj": page_obj,
            "search_by": search_by,
            "sort_by": sort_by,
        })
        return context


    
def update_configuration(request, pk):
    obj = Configuration.objects.get(pk=pk)
    new_status = request.POST.get("status") == "true"
    obj.status = new_status
    obj.save()
    return JsonResponse({"success": True})

class SMSConfigurationView(TemplateView):
    template_name = "superuser/smsconfiguration.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = SMSConfiguration.objects.all()

        search_by = self.request.GET.get("search_by")
        if search_by:
            qs = qs.filter(Q(name__icontains=search_by) | Q(sms_sender__icontains=search_by))

        created_date = self.request.GET.get("created_date")
        if created_date:
            try:
                start_str, end_str = created_date.split(" - ")
                qs = qs.filter(
                    created_at__date__gte=datetime.strptime(start_str, "%m/%d/%Y").date(),
                    created_at__date__lte=datetime.strptime(end_str, "%m/%d/%Y").date()
                )
            except ValueError:
                pass

        sort_by = self.request.GET.get("sort_by")
        qs = qs.order_by("created_at" if sort_by == "asc_created" else "-created_at")

        paginator = Paginator(qs, self.request.GET.get("per_page", 10))
        page_obj = paginator.get_page(self.request.GET.get("page", 1))

        context.update({
            "sms_list": page_obj.object_list,
            "page_obj": page_obj,
            "search_by": search_by,
            "sort_by": sort_by,
        })
        return context
def sms_edit(request, uid):
    if request.method == "POST":
        try:
            sms = SMSConfiguration.objects.get(id=uid)
        except SMSConfiguration.DoesNotExist:
            return JsonResponse({"success": False, "msg": "Record not found"})

        sms.sms_sender = request.POST.get("sms_sender")
        sms.sms_auth_token = request.POST.get("sms_auth_token")
        sms.sms_account_sid = request.POST.get("sms_account_sid")
        sms.save()

        admin_update_activity(
            request.user,
            f"Updated SMS Configuration (ID: {sms.id})"
        )

        return JsonResponse({"success": True})

    return JsonResponse({"success": False})

def sms_toggle_status(request, uid):
    if request.method == "POST":
        try:
            sms = SMSConfiguration.objects.get(id=uid)
        except SMSConfiguration.DoesNotExist:
            return JsonResponse({"success": False})

        sms.status = not sms.status  
        sms.save()
        return JsonResponse({"success": True})

    return JsonResponse({"success": False})
class ThemeView(TemplateView):
    template_name = "superuser/theme.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = Theme.objects.all()

        search_by = self.request.GET.get("search_by")
        if search_by:
            qs = qs.filter(Q(key__icontains=search_by) | Q(description__icontains=search_by))

        created_date = self.request.GET.get("created_date")
        if created_date:
            try:
                start_str, end_str = created_date.split(" - ")
                qs = qs.filter(
                    created_at__date__gte=datetime.strptime(start_str, "%m/%d/%Y").date(),
                    created_at__date__lte=datetime.strptime(end_str, "%m/%d/%Y").date()
                )
            except ValueError:
                pass

        sort_by = self.request.GET.get("sort_by")
        qs = qs.order_by("created_at" if sort_by == "asc_created" else "-created_at")

        paginator = Paginator(qs, self.request.GET.get("per_page", 10))
        page_obj = paginator.get_page(self.request.GET.get("page", 1))

        context.update({
            "theme_list": page_obj.object_list,
            "page_obj": page_obj,
            "search_by": search_by,
            "sort_by": sort_by,
        })
        return context
def edit_theme_value(request, pk):
    if request.method == "POST":
        try:
            theme = Theme.objects.get(pk=pk)
            theme.value = request.POST.get("value", "")
            theme.save()

            admin_update_activity(
                request.user,
                f"Updated Theme: {theme.key if hasattr(theme, 'key') else theme.id}"
            )

            return JsonResponse({"success": True})

        except Theme.DoesNotExist:
            return JsonResponse({"success": False, "error": "Theme not found"})

    return JsonResponse({"success": False, "error": "Invalid request"})

class APIControlView(TemplateView):
    template_name = "superuser/apicontrol.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = APIControls.objects.all()

        search_by = self.request.GET.get("search_by")
        if search_by:
            qs = qs.filter(Q(portal__icontains=search_by) | Q(api_name__icontains=search_by))

        created_date = self.request.GET.get("created_date")
        if created_date:
            try:
                start_str, end_str = created_date.split(" - ")
                qs = qs.filter(
                    created_at__date__gte=datetime.strptime(start_str, "%m/%d/%Y").date(),
                    created_at__date__lte=datetime.strptime(end_str, "%m/%d/%Y").date()
                )
            except ValueError:
                pass

        sort_by = self.request.GET.get("sort_by")
        qs = qs.order_by("created_at" if sort_by == "asc_created" else "-created_at")

        paginator = Paginator(qs, self.request.GET.get("per_page", 10))
        page_obj = paginator.get_page(self.request.GET.get("page", 1))

        context.update({
            "apis": page_obj.object_list,
            "page_obj": page_obj,
            "search_by": search_by,
            "sort_by": sort_by,
        })
        return context


@csrf_exempt
def toggle_api_status(request, id):
    if request.method == "POST":
        api = APIControls.objects.get(id=id)
        api.status = "inactive" if api.status == "active" else "active"
        api.save()
        return JsonResponse({"success": True})
    return JsonResponse({"success": False}, status=400)
class SEOSettingsView(TemplateView):
    template_name = "superuser/seo.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = SEOSettings.objects.all()

        search_by = self.request.GET.get("search_by")
        if search_by:
            qs = qs.filter(Q(key__icontains=search_by) | Q(description__icontains=search_by))

        created_date = self.request.GET.get("created_date")
        if created_date:
            try:
                start_str, end_str = created_date.split(" - ")
                qs = qs.filter(
                    created_at__date__gte=datetime.strptime(start_str, "%m/%d/%Y").date(),
                    created_at__date__lte=datetime.strptime(end_str, "%m/%d/%Y").date()
                )
            except ValueError:
                pass

        sort_by = self.request.GET.get("sort_by")
        qs = qs.order_by("created_at" if sort_by == "asc_created" else "-created_at")

        paginator = Paginator(qs, self.request.GET.get("per_page", 10))
        page_obj = paginator.get_page(self.request.GET.get("page", 1))

        context.update({
            "seo_list": page_obj.object_list,
            "page_obj": page_obj,
            "search_by": search_by,
            "sort_by": sort_by,
        })
        return context
class SEOEditView(View):
    def post(self, request, pk):
        try:
            seo = SEOSettings.objects.get(id=pk)
            seo.value = request.POST.get("value", "")
            seo.save()

            admin_update_activity(
                request.user,
                f"Updated SEO Setting: {seo.key if hasattr(seo, 'key') else seo.id}"
            )

            return JsonResponse({"success": True})

        except SEOSettings.DoesNotExist:
            return JsonResponse({"success": False, "msg": "SEO setting not found"})

class PaymentsettingsView(View):
    template_name = "superuser/paymentsettings.html"

    def get(self, request):
        qs = PaymentSettings.objects.all()

        search_by = request.GET.get("search_by")
        if search_by:
            qs = qs.filter(Q(key__icontains=search_by) | Q(status__icontains=search_by))

        created_date = request.GET.get("created_date")
        if created_date:
            try:
                start_str, end_str = created_date.split(" - ")
                qs = qs.filter(
                    created_at__date__gte=datetime.strptime(start_str, "%m/%d/%Y").date(),
                    created_at__date__lte=datetime.strptime(end_str, "%m/%d/%Y").date()
                )
            except ValueError:
                pass

        sort_by = request.GET.get("sort_by")
        qs = qs.order_by("created_at" if sort_by == "asc_created" else "-created_at")

        paginator = Paginator(qs, request.GET.get("per_page", 10))
        page_obj = paginator.get_page(request.GET.get("page", 1))

        return render(request, self.template_name, {
            "settings_data": page_obj.object_list,
            "page_obj": page_obj,
            "search_by": search_by,
            "sort_by": sort_by,
        })


class PaymentToggleStatus(View):
    def post(self, request, pk):
        setting = PaymentSettings.objects.get(id=pk)
        setting.status = "inactive" if setting.status == "active" else "active"
        setting.save()
        return JsonResponse({"success": True})

class AdminLogsView(LoginRequiredMixin, TemplateView):
    template_name = 'superuser/adminlogs.html'
    login_url = 'dashboard:login'  # optional

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        logs_qs = AdminActivityLog.objects.filter(is_deleted=False)

        # ---- SEARCH (Action / Description / User) ----
        search_by = self.request.GET.get("search_by")
        if search_by:
            logs_qs = logs_qs.filter(
                Q(description__icontains=search_by) |
                Q(actions__icontains=search_by) |
                Q(user__username__icontains=search_by)
            )

        # ---- DATE RANGE FILTER ----
        created_date = self.request.GET.get("created_date")
        if created_date:
            try:
                if " - " in created_date:
                    start_str, end_str = created_date.split(" - ")
                else:
                    start_str = end_str = created_date

                start_date = datetime.strptime(start_str.strip(), "%m/%d/%Y")
                end_date = datetime.strptime(end_str.strip(), "%m/%d/%Y")
                end_date = end_date.replace(hour=23, minute=59, second=59)

                logs_qs = logs_qs.filter(created_at__range=(start_date, end_date))
            except ValueError:
                pass

        # ---- PAGINATION ----
        page_number = self.request.GET.get("page", 1)
        per_page = self.request.GET.get("per_page", 10)
        paginator = Paginator(logs_qs, per_page)
        page_obj = paginator.get_page(page_number)

        context.update({
            "logs": page_obj.object_list,
            "page_obj": page_obj,
            "search_by": search_by,
            "created_date": created_date,
        })

        return context
