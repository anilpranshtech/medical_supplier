from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import *

app_name = 'medical_api'

router = DefaultRouter()
router.register(r'home', HomeAPIViewSet, basename='home')
router.register(r'user-list', UserEmailViewSet, basename='user_list')
router.register(r'supplier-list', SupplierList, basename='supplier_list')
router.register(r'order-placed', OrderPlacedAPIViewSet, basename='order-placed')
router.register(r'my-orders', MyOrdersAPIViewSet, basename='my-orders')

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
 

    path('submit-review/<int:product_id>/', SubmitReviewAPIView.as_view(), name='submit-review'),
    path('reorder/<int:order_id>/', ReorderAPIView.as_view(), name='reorder'),
    path('order-receipt/<int:order_id>/', OrderReceiptAPIView.as_view(), name='order-receipt'),
    path('download-receipt/<int:order_id>/', DownloadReceiptAPIView.as_view(), name='download-receipt'),

    path('submit-rfq/', RFQSubmissionAPIView.as_view(), name='submit-rfq'),
    path('quotations/', UserQuotationAPIView.as_view(), name='user-quotations'),
    path('rfq-accept/<int:pk>/', RFQAcceptAPIView.as_view(), name='rfq-accept'),
    path('rfq-reject/<int:pk>/', RFQRejectAPIView.as_view(), name='rfq-reject'),

    path('request-role/', RequestRoleAPIView.as_view(), name='request-role'),
    path('manage-requests/', ManageRequestsAPIView.as_view(), name='manage-requests'),
    path('approve-role-request/<int:pk>/', ApproveRoleRequestAPIView.as_view(), name='approve-role-request'),
  # ------------------- Cart --------------------
    path('cart/', CartListAPIView.as_view(), name='cart-list'),
    path('cart/add/', CartAddAPIView.as_view(), name='cart-add'),
    path('cart/remove/', CartRemoveAPIView.as_view(), name='cart-remove'),

 # ------------------- wishlist --------------------
    path('wishlist/toggle/', WishlistToggleAPIView.as_view(), name='wishlist-toggle'),
    path('wishlist/remove/', WishlistRemoveAPIView.as_view(), name='wishlist-remove'),
    path('wishlist/list/', WishlistListAPIView.as_view(), name='wishlist-list'),

 # ------------------- shipping info --------------------   
    path('shipping-info/', ShippingInfoAPIView.as_view(), name='shipping-info'),
    path('address/add/', AddAddressAPIView.as_view(), name='add-address'),
    path('address/<int:pk>/edit/', EditAddressAPIView.as_view(), name='edit-address'),
    path('address/<int:address_id>/delete/', RemoveAddressAPIView.as_view(), name='remove-address'),

  # ------------------- search bar --------------------   
    path('api/search/', ProductSearchAPIView.as_view(), name='product-search-api'),
 
  # ------------------- registration --------------------   
    path('api/register/wholesaler/', WholesaleRegisterAPIView.as_view(), name='wholesaler_register'), 
    path('api/register/supplier/', SupplierRegisterAPIView.as_view(), name='supplier-register'),
    path('profile/wholesaler/', WholesaleBuyerProfileAPIView.as_view(), name='wholesaler-profile'),
    path('api/supplier/profile/', SupplierProfileAPIView.as_view(), name='supplier-profile'),

    path("api/user/profile/", UserProfileAPIView.as_view(), name="user-profile"),
 



    
]
