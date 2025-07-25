from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import *

app_name = 'medical_api'

router = DefaultRouter()


urlpatterns = [

    path('', include(router.urls)),

    #--------------------- Authentication APIs ---------------------
    path("login/", UserLoginAdminView.as_view(), name="user_login"),
    path('signup/', DoctorRegisterAPIView.as_view(), name='doctor-register'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('logout/', LogoutView.as_view(), name='user_logout'),

    # --------------------- User Profile APIs ---------------------
    path('user-profile/', DoctorProfileAPIView.as_view(), name='user_profile'),

    # --------------------- Categories ---------------------
    path('categories/', CategoryListAPIView.as_view(), name='category-list'),
    path('subcategories/', SubCategoryListByCategoryAPIView.as_view(), name='subcategory_by_category'),
    path('last-categories/', LastCategoryListBySubCategoryAPIView.as_view(), name='lastcategory_by_subcategory'),

    # --------------------- Products ---------------------


]
