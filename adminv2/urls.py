from django.urls import path
from .views import *

app_name = 'adminv2'
urlpatterns = [
    path('admin_v2/', HomeView.as_view(), name='admin_v2'),

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
    path('orders/delete/<slug:order_id>/', OrderDeleteView.as_view(), name='order_delete'),

    # Cart
    path('cart/products', CartProductsView.as_view(), name='cart_product_list'),
    path("cart/update-quantity/", UpdateCartQuantityView.as_view(), name="update_cart_quantity"),
    path("cart/delete-item/", DeleteCartItemView.as_view(), name="delete_cart_item"),


    path('adminv2/login/', AdminloginView.as_view(), name='admin_login'),
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
   
    #RFQ Request for Quotation
    path('rfq/', RFQListView.as_view(), name='rfq_list'),
    path('rfq/<int:pk>/quote/', SupplierQuotationUpdateView.as_view(), name='rfq_quote'),

    #Banner Upload
    path('banner-list/', BannerListView.as_view(), name='banner_list'),
    path('banner-upload/', BannerCreateView.as_view(), name='banner_upload'),
    path('banner-edit/<int:pk>/', BannerUpdateView.as_view(), name='banner_edit'),
    

]
