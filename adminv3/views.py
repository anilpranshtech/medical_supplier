from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.views.generic import ListView

from adminv3.mixins import StaffAccountRequiredMixin

from django.contrib.auth.models import User

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


class PermissionsUsers(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    template_name = 'adminv3/users/permissions.html'

    def get(self, request):

        return render(request, self.template_name)



class ProductsListView(LoginRequiredMixin, StaffAccountRequiredMixin, View):
    template_name = 'adminv3/products/products_list.html'

    def get(self, request):

        return render(request, self.template_name)

