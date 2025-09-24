# mixins.py
from django.shortcuts import redirect
from django.contrib import messages


class OnboardingRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")

        try:
            profile = request.user.supplierprofile
        except:
            return redirect("supplier:user_information")

        if not profile.onboarding_complete:
            messages.warning(request, "Please complete your onboarding before accessing this page.")
            return redirect("supplier:user_information") 

        return super().dispatch(request, *args, **kwargs)
