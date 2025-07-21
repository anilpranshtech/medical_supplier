from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView

from adminv3.mixins import StaffAccountRequiredMixin

from django.contrib.auth.models import User

from adminv3.utils import requestParamsToDict
from dashboard.models import RetailProfile, WholesaleBuyerProfile, SupplierProfile


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

        context = {
            'user': user,
            'retail_profile': RetailProfile.objects.filter(user=user).first(),
            'wholesale_profile': WholesaleBuyerProfile.objects.filter(user=user).first(),
            'supplier_profile': SupplierProfile.objects.filter(user=user).first(),
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



class PermissionsUsers(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    template_name = 'adminv3/users/permissions.html'

    def get(self, request):

        return render(request, self.template_name)



class ProductsListView(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    template_name = 'adminv3/products/products_list.html'

    def get(self, request):

        return render(request, self.template_name)

