from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect


def superuser_required(user):
    return user.is_authenticated and user.is_superuser

class SuperuserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return superuser_required(self.request.user)


def staff_required(user):
    return user.is_authenticated and user.is_staff

class StaffAccountRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return staff_required(self.request.user)


class PermissionRequiredMixin:
    required_permissions = []
    def dispatch(self, request, *args, **kwargs):
        if not all(request.user.has_perm(perm) for perm in self.required_permissions):
            messages.error(request, 'You do not have permission to view or perform this action.')
            return redirect('superuser:superuser')
        return super().dispatch(request, *args, **kwargs)
