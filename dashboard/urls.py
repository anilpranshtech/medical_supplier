from . import views
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import CustomLoginView, RegistrationView, HomeView, UserProfileView


urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('', HomeView.as_view(), name='home'),
    path('register/', RegistrationView.as_view(), name='register'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('upload-profile-picture/', views.UploadProfilePictureView.as_view(), name='upload_profile_picture'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
