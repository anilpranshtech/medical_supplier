from . import views
from django.urls import path
from .views import CustomLoginView, RegistrationView, HomeView

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('', HomeView.as_view(), name='home'),
    path('register/', RegistrationView.as_view(), name='register'),
]
