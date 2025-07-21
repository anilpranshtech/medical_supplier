from datetime import timedelta

from django.contrib.auth.mixins import UserPassesTestMixin



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
