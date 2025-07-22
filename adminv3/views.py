from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, Http404, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView

from adminv3.mixins import StaffAccountRequiredMixin
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from adminv3.utils import requestParamsToDict
from dashboard.models import RetailProfile, WholesaleBuyerProfile, SupplierProfile, Product, ProductImage


class HomeView(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    template_name = 'adminv3/home.html'

    def get(self, request):
        return render(request, self.template_name)


class UsersAccounts(LoginRequiredMixin, StaffAccountRequiredMixin, ListView):
    template_name = 'adminv3/users/users_list.html'
    model = User
    context_object_name = 'users'
    ordering = ['-date_joined']
    paginate_by = 25

    def get_queryset(self):

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


GROUP_PERMISSIONS_MODELS_LIST = ['user', 'orders', 'product']

class PermissionsUsers(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    template_name = 'adminv3/permissions/permissions.html'

    def get(self, request, *args, **kwargs):
        skipped_permissions = []


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

                skipped_permissions = [ ]

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


class ProductsListView(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    template_name = 'adminv3/products/products_list.html'

    def get(self, request):
        user = request.user
        products = Product.objects.all().order_by('-created_at')

        for product in products:
            image = ProductImage.objects.filter(product=product).first()
            product.image_url = image.image.url if image else '/static/adminv2/media/stock/ecommerce/placeholder.png'

        return render(request, self.template_name, {'products': products})

