from django.urls import path
from .views import *

app_name = 'supplier'
urlpatterns = [
    path('supplier/', HomeView.as_view(), name='supplier'),
    

    # Products
    path('products/', ProductsView.as_view(), name='products_list'),
    path('products/add/', AddproductsView.as_view(), name='add_product'),
    path('products/edit/<int:pk>/', EditproductsView.as_view(), name='edit_product'),
    path('products/delete/<int:pk>/', DeleteProductView.as_view(), name='delete_product'),
    path('delete-product-image/<int:pk>/', DeleteProductImageView.as_view(), name='delete_product_image'),
    
    # Category 
    path('categories/create/', CreateProductCategoryView.as_view(), name='create_category'),
    path('create-sub-category/', CreateProductSubCategoryView.as_view(), name='create_subcategory'),
    path('create-last-category/', CreateProductLastCategoryView.as_view(), name='create_lastcategory'),
    path('ajax/get-subcategories/', GetSubcategoriesView.as_view(), name='get_subcategories'),
    path('ajax/get-lastcategories/', GetLastCategoriesView.as_view(), name='get_lastcategories'),

    # Wishlist
    path('wishlist/products', WishlistProductView.as_view(), name='wishlist_products_list'),
    
    #order
    path('orderlist/', OrderListingView.as_view(), name='order_listing'),
    path('order-detail/<slug:order_id>/', OrderDetailsView.as_view(), name='order_detail'),
    path( "orders/update-payment-status/", UpdatePaymentStatusView.as_view(), name="update_payment_status" ),
    path('orders/', OrderListAndStatusView.as_view(), name='orders'),
    path('order/change-status/', ChangeOrderStatusView.as_view(), name='change_order_status'),

    # path('orders/delete/<slug:order_id>/', OrderDeleteView.as_view(), name='order_delete'),
    # Cart
    path('cart/products', CartProductsView.as_view(), name='cart_product_list'),
    path("cart/update-quantity/", UpdateCartQuantityView.as_view(), name="update_cart_quantity"),
    path("cart/delete-item/", DeleteCartItemView.as_view(), name="delete_cart_item"),
    path('supplier/login/', AdminloginView.as_view(), name='admin_login'),
    path('logout/', LogoutView.as_view(), name='admin_logout'),
    
    # user profile
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/add/', UserAddView.as_view(), name='add_user'),
    path('users/edit/<int:pk>/', UserEditView.as_view(), name='edit_user'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user_detail'),
    path('users/delete/<int:pk>/', UserDeleteView.as_view(), name='delete_user'),
    path('user-profile/', UserProfileView.as_view(), name='user_profile'),
    path('overview/', UserOverView.as_view(), name='overview_list'),
    path('settings/', AdminSettingView.as_view(), name='profile_setting'),
    path('company/details', CompanyDetailsView.as_view(), name='company_details'),
    
    #notification
    path('mark-notification-read/<int:pk>/', MarkNotificationReadView.as_view(), name='mark_notification_read'),
    path('notifications/clear-all/', ClearAllNotificationsView.as_view(), name='clear_all_notifications'),
    path('mark-notification-read/<int:pk>/', MarkNotificationReadView.as_view(), name='mark_notification_read'),
    path('delete-notification/<int:id>/', DeleteNotificationView.as_view(), name='delete_notification'),
   
    #RFQ Request for Quotation
    path('rfq/', SupplierRFQListView.as_view(), name='rfq_list'),
    path('rfq/<int:pk>/quote/', SupplierQuotationUpdateView.as_view(), name='rfq_quote'),
   

    #Banner Upload
    # path('banner-list/', BannerListView.as_view(), name='banner_list'),
    # path('banner-upload/', BannerCreateView.as_view(), name='banner_upload'),
    # path('banner-edit/<int:pk>/', BannerUpdateView.as_view(), name='banner_edit'),

    path('transaction/', TransactionView.as_view(), name='transaction_list'),
    path('print-bill/<int:pk>/', PrintBillView, name='print_bill'),
    path('question/', QuestionView.as_view(), name='question_list'),
    path('rating/', RatingView.as_view(), name='rating_list'),
    path('rating/<int:product_id>/', ProductRatingListView.as_view(), name='product_ratings'),
    path('most-viewed-products/', MostViewedProductsView.as_view(), name='view_product'),
    
    #shipping method
    path('shipping-list/', ShippingListView.as_view(), name='shipping_list'),
    path('shipping-create/', ShippingCreateView.as_view(), name='shipping_create'),
    path('shipping-update/<int:pk>/', ShippingUpdateView.as_view(), name='shipping_update'),
    path('shipping-delete/<int:pk>/', ShippingDeleteView.as_view(), name='shipping_delete'),

    #return
    path('supplier/returns/', SupplierReturnsView.as_view(), name='supplier_returns'),
    path('supplier/returns/<str:return_serial>/', SupplierReturnsView.as_view(), name='supplier_returns'),
    
    #my profile
    path("user-info/", UserInformationView.as_view(), name="user_information"),
    path("business-info/", BusinessInformationView.as_view(), name="business_information"),
    path("bank-details/", BankDetailsView.as_view(), name="bank_details"),
    path("selling-categories/", SellingCategoriesView.as_view(), name="selling_categories"),
    path("supplier-description/", SupplierDescriptionView.as_view(), name="supplier_description"),
    path("pickup-shipping/", PickupShippingView.as_view(), name="pickup_shipping"),
    path("get-states/", GetStatesView.as_view(), name="get_states"),
    path("get-cities/", GetCitiesView.as_view(), name="get_cities"),
    path('supplier/documents/', SupplierDocumentsView.as_view(), name='supplier_documents'),
    path('supplier/status/', SupplierStatusView.as_view(), name='supplier_status'),
    path('track-onboarding-progress/', TrackOnboardingProgressView.as_view(), name='track_onboarding_progress'),

    #return 
    path('returns/update/<str:return_serial>/', AdminReturnUpdateStatusView.as_view(), name='admin_returns_update_status'),
    path('returns/delete/<str:return_serial>/', ReturnDeleteView.as_view(), name='admin_returns_delete'),
    path('returns/refund/', AdminProcessRefundView.as_view(), name='process_refund'),
    path('returns/', AdminReturnsView.as_view(), name='admin_returns'),
    
    #coupons
    path('admincoupons/', CouponsView.as_view(), name='coupons'),
    path('admincoupon/edit/', edit_coupon, name='edit_coupon'),
    path('admincoupon/delete/', delete_coupon, name='delete_coupon'),
    path('admincoupon/details/<int:coupon_id>/', coupon_details, name='coupon_details'),

    #vacationmode
    path('vacation-request/', VacationRequestView.as_view(), name='vacation_request'),

    #Marketing tools
    path('supplierbuyxgety/', SupplierBuyXGetYPromotionView.as_view(), name='buyxgety_promotion'),
    path('supplierbuyxgety/add/', SupplierAddPromotionView.as_view(), name='add_promotion'),
    path('supplierbuyxgety/edit/<int:pk>/', SupplierEditPromotionView.as_view(), name='edit_promotion'),
    path('supplierbuyxgety/delete/<int:pk>/', supplier_delete_promotion, name='delete_promotion'),
     
    path('supplierbuyxgifty/',supplierBuyXGiftYPromotionView.as_view(),name='buyxgift_promotion'),
    path('supplierbuyxgifty/add/', supplierAddGiftPromotionView.as_view(), name='add_gift_promotion'),
    path('supplierbuyxgifty/edit/<int:pk>/', supplierEditGiftPromotionView.as_view(), name='edit_gift_promotion'),
    path('supplierbuyxgifty/delete/<int:pk>/', supplier_delete_gift_promotion, name='delete_gift_promotion'),

    path('supplierbasketpromotion/', supplierBasketPromotionView.as_view(), name='basket_promotion'),
    path('supplierbasketpromotion/add/', supplierAddBasketPromotionView.as_view(),name='add_basket_promotion'),
    path('supplierbasketpromotion/edit/<int:pk>/', supplierEditBasketPromotionView.as_view(), name='edit_basket_promotion'),
    path('supplierbasketpromotion/delete/<int:pk>/', supplier_delete_basket_promotion,name='delete_basket_promotion'),
    

    path('suppliercontact-us/', SupplierContactUsView.as_view(), name='contact_us'),
    path('supplier-logs/', SupplierLogsView.as_view(), name='supplier_logs'),
    path('supplierchats/', SupplierChatsView.as_view(), name='supplier_chats'),
    path('supplierchatlist/',SupplierChatsListView.as_view(),name= "supplier_chat_list"),
    
]

    


