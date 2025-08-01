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
    path('search-suggestions/', views.SearchSuggestionsView.as_view(), name='search_suggestions'),
    path('product-detail/<int:pk>/', views.ProductDetailsView.as_view(), name='product_detail'),
    path('product-detail/', views.ProductDetailsView.as_view(), name='product_detail'),
   #cart
    path('add-to-cart/', CartAddView.as_view(), name='add_to_cart'),
    # path('order-summary/', OrderSummaryView.as_view(), name='order_summary'),
    path('remove-from-cart/', RemoveFromCartView.as_view(), name='remove_from_cart'),
    path('clear_cart_items/', clearcart, name='clear_cart_items'),

    path('wish-list/', views.WishlistView.as_view(), name='wish_list'),
    path('wishlist/toggle/', views.WishlistToggleView.as_view(), name='toggle_wishlist'),
    path('wishlist/clear/',views.WishlistClearView.as_view(), name='clear_wishlist'),
    path('wishlist/products/', WishlistProductListView.as_view(), name='wishlist_product_list'),
    path('shopping-cart/', views.ShoppingCartView.as_view(), name='shopping_cart'),
    path('add-to-cart/', add_to_cart, name='add_to_cart'),
    path('remove-from-cart/', remove_from_cart, name='remove_from_cart'),
    path('shipping-info/', views.ShippingInfoView.as_view(), name='shipping_info'),
    path('profile/add-address/', views.AddAddressView.as_view(), name='add_address'),
    path('profile/edit-address/<int:pk>/', views.EditAddressView.as_view(), name='edit_address'),
    path('profile/remove-address/<int:address_id>/', views.RemoveAddressView.as_view(), name='remove_address'),
    path('profile/set-default-address/', views.SetDefaultAddressView.as_view(), name='set_default_address'),
    path('payment-method/', views.PaymentMethodView.as_view(), name='payment_method'),
    path('order-placed/', views.OrderPlacedView.as_view(), name='order_placed'),
    path('my-orders/', views.MyOrdersView.as_view(), name='my_orders'),
    path('submit-review/<int:product_id>/', SubmitReviewView.as_view(), name='submit_review'),
    path('orders/<int:order_id>/reorder/', ReorderView.as_view(), name='reorder'),
    path('order-receipt/<int:pk>/', OrderReceiptView.as_view(), name='order_receipt'),
    path('order-receipt/<int:pk>/download/', views.DownloadReceiptView.as_view(), name='download_receipt'),

    # user profile
    path('user-profile/', views.UserProfile.as_view(), name='user_profile'),
    path('upload-avatar/', UploadAvatarView.as_view(), name='upload_avatar'),
    path('profile/edit/', views.EditProfileView.as_view(), name='edit_profile'),
    path('profile/edit-email/', views.EditEmailView.as_view(), name='edit_email'),
    path('profile/edit-phone/', views.EditPhoneView.as_view(), name='edit_phone'),

    path('user-signup/', views.SignUpView.as_view(), name='user_signup'),
    path('verify-otp/', views.VerifyOTPView.as_view(), name='verify_otp'),
    path('resend-otp/', views.ResendOTPView.as_view(), name='resend_otp'),
    path('user-signin/', views.SignInView.as_view(), name='user_signin'),
    path('user-logout/', views.LogoutView.as_view(), name='user_logout'),
    path('password-reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),

    # razorpay payment
    path('make-payment/', PaymentView.as_view(), name='make_payment'),
    path('payment-status/', PaymentStatusView.as_view(), name='payment_status'),

    # Become a seller
    path('request-role/', views.RequestRoleView.as_view(), name='request_role'),
    path('approve-role/<int:pk>/', views.ApproveRoleRequestView.as_view(), name='approve_role_request'),
    path('manage-requests/', views.ManageRequestsView.as_view(), name='manage_requests'),

    # RFQ
    path('rfq/submit/', RFQSubmissionView.as_view(), name='rfq_submit'),
    path('my-quotations/', UserQuotationView.as_view(), name='view_user_quotations'),
    path('rfq/<int:pk>/accept/', RFQAcceptView.as_view(), name='accept_rfq'),
    path('rfq/<int:pk>/reject/', RFQRejectView.as_view(), name='reject_rfq'),

    # Subscription Plan
    path('subscriptions-plans/', SubscriptionPlanView.as_view(), name='subscription_plans'),
    path('subscriptions/check/', CheckStripeSubscriptionView.as_view(), name='check_stripe_subscription'),
    path('update-subscription/', UpdateSubscriptionView.as_view(), name='update_subscription'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
