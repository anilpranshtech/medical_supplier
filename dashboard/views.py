from django.http import HttpResponse
from django.shortcuts import render,redirect
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from .forms import EmailOnlyLoginForm
from django.views import View
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from .models import DoctorProfile, MedicalSupplierProfile, CorporateProfile
from django.contrib import messages
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin


class HomeView(TemplateView):
    template_name = 'dashboard/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context


class CustomLoginView(LoginView):
    form_class = EmailOnlyLoginForm
    template_name = 'dashboard/login.html' 

    def get_success_url(self):
        return reverse_lazy('home')


class RegistrationView(View):
    template_name = "dashboard/register.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type')

        try:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            if user_type == 'doctor':
                DoctorProfile.objects.create(user=user)
                messages.success(request, "Doctor user created. Please update your profile.")

            elif user_type == 'supplier':
                MedicalSupplierProfile.objects.create(user=user)
                messages.success(request, "Supplier user created. Please update your profile.")

            elif user_type == 'corporate':
                CorporateProfile.objects.create(user=user)
                messages.success(request, "Corporate user created. Please update your profile.")

            else:
                messages.error(request, "Invalid user type.")
                user.delete()
                return render(request, self.template_name, {'error': "Invalid user type."})

            return redirect('login')

        except Exception as e:
            messages.error(request, f"An error occurred: {e}")
            return render(request, self.template_name, {'error': str(e)})


class UserProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        profile = None
        profile_type = None

        if hasattr(user, 'doctorprofile'):
            profile = user.doctorprofile
            profile_type = 'doctor'
        elif hasattr(user, 'medicalsupplierprofile'):
            profile = user.medicalsupplierprofile
            profile_type = 'supplier'
        elif hasattr(user, 'corporateprofile'):
            profile = user.corporateprofile
            profile_type = 'corporate'

        context['user'] = user
        context['profile'] = profile
        context['profile_type'] = profile_type
        return context


class UploadProfilePictureView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        profile = None

        if hasattr(request.user, 'doctorprofile'):
            profile = request.user.doctorprofile
        elif hasattr(request.user, 'medicalsupplierprofile'):
            profile = request.user.medicalsupplierprofile
        elif hasattr(request.user, 'corporateprofile'):
            profile = request.user.corporateprofile

        if profile and 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']
            profile.save()

        return redirect('profile')
