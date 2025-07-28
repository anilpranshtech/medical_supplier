from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import *

app_name = 'medical_api'

router = DefaultRouter()
router.register(r'user-list',UserEmailViewSet, basename='user_list')
router.register(r'supplier-list', SupplierList, basename='supplier_list')

urlpatterns = [

    path('', include(router.urls)),

    #--------------------- Authentication APIs ---------------------

    path("login/", UserLoginAdminView.as_view(), name="user_login"),
    path('signup/', DoctorRegisterAPIView.as_view(), name='doctor-register'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('logout/', LogoutView.as_view(), name='user_logout'),

    path('forgot-password/', ForgotPasswordAPIView.as_view(), name='forgot-password'),
    path('reset-password/<uidb64>/<token>/', ResetPasswordAPIView.as_view(), name='reset-password'),

    # --------------------- User Profile APIs ---------------------
    path('user-profile/', DoctorProfileAPIView.as_view(), name='user_profile'),

    # --------------------- Categories ---------------------
    path('categories/', CategoryListAPIView.as_view(), name='category-list'),
    path('subcategories/', SubCategoryListByCategoryAPIView.as_view(), name='subcategory_by_category'),
    path('last-categories/', LastCategoryListBySubCategoryAPIView.as_view(), name='lastcategory_by_subcategory'),

    # --------------------- Products ---------------------
    path('products/', ProductListAPIView.as_view(), name='product-list'),
    path('products/<int:id>/', ProductDetailAPIView.as_view(), name='product-detail'),
    path("products/create/", ProductCreateAPIView.as_view(), name="product-create"),

    # ------------------- registration list --------------------
    path('specialties/', SpecialityListView.as_view(), name='specialty-list'),
    path('residencies/', ResidencyListView.as_view(), name='residency-list'),
    path('nationalities/', NationalityListView.as_view(), name='nationality-list'),
    path('country-codes/', CountryCodeListView.as_view(), name='countrycode-list'),

    path('plans/', SubscriptionPlanListCreateAPIView.as_view(), name='plan-list-create'),
    path('subscriptions/', UserSubscriptionListAPIView.as_view(), name='user-subscription-list'),
    path('subscribe/', UserSubscriptionCreateAPIView.as_view(), name='user-subscription-create'),


]
