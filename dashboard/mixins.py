from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib import messages
from django.shortcuts import redirect
from dashboard.models import SupplierProfile


# class SupplierPermissionMixin(UserPassesTestMixin):
#     def test_func(self):
#         user = self.request.user

#         # Allow access to superusers
#         if user.is_superuser:
#             return True

#         # Check if user is authenticated before querying DB
#         if not user.is_authenticated:
#             return False

#         # Check if the user has a SupplierProfile
#         return SupplierProfile.objects.filter(user=user).exists()

#     def handle_no_permission(self):
#         messages.error(self.request, "You do not have permission to access this page.")
#         return redirect('dashboard:login')
