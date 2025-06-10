from . import views
from django.urls import path
from .views import  CustomLoginView

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('', views.home, name='home'),
    path('register/', views.RegistrationView.as_view(), name='register'),
]
