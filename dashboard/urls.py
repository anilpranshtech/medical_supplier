from . import views
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import *

app_name = 'dashboard'

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('', HomeView.as_view(), name='home'),
    path('register/', RegistrationView.as_view(), name='register'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('upload-profile-picture/', views.UploadProfilePictureView.as_view(), name='upload_profile_picture'),

    # user dashboard
    path('search-results-grid/', views.SearchResultsGridView.as_view(), name='search_results_grid'),
    path('search-results-list/', views.SearchResultsListView.as_view(), name='search_results_list'),
    path('product-detail/', views.ProductDetailsView.as_view(), name='product_detail'),
    path('shopping-cart/', views.ShoppingCartView.as_view(), name='shopping_cart'),
    path('wish-list/', views.WishlistView.as_view(), name='wish_list'),
    path('order-summary/', views.OrderSummaryView.as_view(), name='order_summary'),
    path('shipping-info/', views.ShippingInfoView.as_view(), name='shipping_info'),
    path('payment-method/', views.PaymentMethodView.as_view(), name='payment_method'),
    path('order-placed/', views.OrderPlacedView.as_view(), name='order_placed'),
    path('my-orders/', views.MyOrdersView.as_view(), name='my_orders'),
    path('order-receipt/', views.OrderReceiptView.as_view(), name='order_receipt'),

    # user profile
    path('user-profile/', views.UserProfile.as_view(), name='user_profile'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
