from django.urls import path
from .views import *

app_name = 'superuser'
urlpatterns = [

    # Home analytics
    path('', HomeView.as_view(), name='superuser'),
    # Users pages
    path('users/accounts/', UsersAccounts.as_view(), name='user_accounts'),
    path('users/<int:pk>/details/', UserDetailView.as_view(), name='user_detail'),
    path('users/<int:pk>/update-profile/', User_Accounts_Update_Profile.as_view(),
         name='user_accounts_update_profile'),
    path('users/<int:pk>/change-email/', User_Accounts_Change_Email.as_view(), name='user_accounts_change_email'),
    path('users/<int:pk>/update-role/', User_Accounts_Update_Role.as_view(), name='user_accounts_update_role'),
    path('users/<int:pk>/change-password/', User_Accounts_Change_Password.as_view(),
         name='user_accounts_change_password'),
    path('users/<int:pk>/update_status/', UserUpdateAccountStatusView.as_view(),
         name='user_update_account_status'),
    path('users/<int:pk>/delete/', User_Accounts_Delete_Account.as_view(), name='user_accounts_delete_account'),
    path('users/<int:pk>/modify-permission-groups/', User_Accounts_Modify_Permission_Groups.as_view(),
         name='user_accounts_modify_permission_groups'),

    path('users/add-new-user/', User_Accounts_AddNewUser.as_view(), name='user_accounts_add_new_user'),


    # Permissions urls
    path('users/permissions/', PermissionsUsers.as_view(), name='user_permissions'),
    path('users/permissions/add-new-group/', User_Permissions_AddNewGroup.as_view(),
         name='user_permissions_add_new_group'),
    path('users/permissions/delete-group/', User_Permissions_DeleteGroup.as_view(),
         name='user_permissions_delete_group'),
    path('users/permissions/<UID>/edit/', User_Permissions_EditGroup.as_view(), name='user_permissions_edit_group'),


    # Products urls
    path('products/list/', ProductsListView.as_view(), name='products_list'),
    path('products/add/', AddproductsView.as_view(), name='add_product'),
    path('products/edit/<int:pk>/', EditproductsView.as_view(), name='edit_product'),
    path('products/delete/<int:pk>/', DeleteProductView.as_view(), name='delete_product'),

    # categories urls
    path('categories/create/', CreateProductCategoryView.as_view(), name='create_category'),
    path('create-sub-category/', CreateProductSubCategoryView.as_view(), name='create_subcategory'),
    path('create-last-category/', CreateProductLastCategoryView.as_view(), name='create_lastcategory'),
    path('delete-product-image/<int:pk>/', DeleteProductImageView.as_view(), name='delete_product_image'),

    # AJAX category create
    path('ajax-categories/get/', AJAXGetCategoriesView.as_view(), name='AJAX_get_category'),
    path('ajax-categories/create/', AJAXCreateCategory.as_view(), name='AJAX_create_category'),
    path('ajax-sub-category/get/', get_subcategories, name='AJAX_get_subcategory'),
    path('ajax-sub-category/create/', AJAXCreateSubCategory.as_view(), name='AJAX_create_subcategory'),
    path('ajax-last-category/create/', AJAXCreateLastCategory.as_view(), name='AJAX_create_lastcategory'),

    # Orders Urls
    path('orders/list/', OrderListingView.as_view(), name='orders_list'),
    path('order/detail/<slug:order_id>/', OrderDetailesView.as_view(), name='orders_detail'),
    path('orders/delete/<int:pk>/', OrderDeleteView.as_view(), name='order_delete'),

    path('banner-list/', BannerListView.as_view(), name='banner_list'),
    path('banner-upload/', BannerCreateView.as_view(), name='banner_upload'),
    path('banner-edit/<int:pk>/', BannerUpdateView.as_view(), name='banner_edit'),

    path('rfq/', AdminRFQListView.as_view(), name='rfq_list'),
    path('rfq/<int:pk>/quote/', AdminQuotationUpdateView.as_view(), name='rfq_quote'),
    path('most-viewed-products/', AdminMostViewedProductsView.as_view(), name='view_product'),
   
    path('rating/', RatingView.as_view(), name='rating_list'),
    #notification
    path("notifications/", NotificationListView.as_view(), name="notifications_list"),
    path("notifications/add/", NotificationCreateView.as_view(), name="add_notification"),
    path('notifications/edit/<int:pk>/', EditNotificationView.as_view(), name='edit_notification'),
    path('notifications/delete/<int:pk>/', DeleteNotificationView.as_view(), name='delete_notification'),

    path('returns/', AdminReturnsView.as_view(), name='admin_returns'),
    path('returns/update/<str:return_serial>/', AdminReturnUpdateStatusView.as_view(), name='admin_returns_update_status'),
    # path('returns/refund/', StripeRefundView.as_view(), name='stripe_refund'),
    path('returns/delete/<str:return_serial>/', ReturnDeleteView.as_view(), name='admin_returns_delete'),

    path('returns/refund/', AdminProcessRefundView.as_view(), name='process_refund'),
    path('question/', AdminQuestionView.as_view(), name='question_list'),


    #category
    path("categories/", CategoryListView.as_view(), name="categories"),
    path('add-category/', CategoryCreateView.as_view(), name='add_category'),
    path('edit-category/', CategoryEditView.as_view(), name='edit_category'),
    path('delete-category/', CategoryDeleteView.as_view(), name='delete_category'),

    # Subcategory URLs
    path('subcategories/', CategorySubListView.as_view(), name='subcategory_list'),
    path('subcategories/<int:category_id>/', CategorySubListView.as_view(), name='category_subcategories'),
    path('add-subcategory/', SubCategoryCreateView.as_view(), name='add_subcategory'),
    path('edit-subcategory/', SubCategoryEditView.as_view(), name='edit_subcategory'),
    path('delete-subcategory/', SubCategoryDeleteView.as_view(), name='delete_subcategory'),
    path('edit-subcategory/<int:subcategory_id>/', SubCategoryEditView.as_view(), name='edit_subcategory_detail'),

    # Last Category URLs
    path('last-categories/<int:subcategory_id>/', SubCategoryLastListView.as_view(), name='lastcategory_list'),
    path('lastcategories/<int:subcategory_id>/', SubCategoryLastListView.as_view(), name='subcategory_lastcategories'),
    path('add-lastcategory/', LastCategoryCreateView.as_view(), name='add_lastcategory'),
    path('edit-lastcategory/', LastCategoryEditView.as_view(), name='edit_lastcategory'),
    path('delete-lastcategory/', LastCategoryDeleteView.as_view(), name='delete_lastcategory'),
    path('edit-lastcategory/<int:lastcategory_id>/', LastCategoryEditView.as_view(), name='edit_lastcategory_detail'),

    #Supplier Commission
    path('supplier-commission/', SupplierCommissionListView.as_view(), name='supplier_commission'),
    path('supplier-commission/edit/', SupplierCommissionEditView.as_view(), name='supplier_commission_edit'),
    path('supplier-commission/delete/', SupplierCommissionDeleteView.as_view(), name='supplier_commission_delete'),

    #vacationmode
    path('vacation-mode/', AdminVacationModeView.as_view(), name='admin_vacation_mode'),

    #Top supplier
     path('add-to-supplier/', AddTopSupplierView.as_view(), name='add_to_supplier'),
     path('top-supplier-list/', TopSupplierListView.as_view(), name='topsupplierlist'),
     path('edit-top-supplier/', EditTopSupplierView.as_view(), name='edit_top_supplier'),
     path('delete-top-supplier/', DeleteTopSupplierView.as_view(), name='delete_top_supplier'),
     
]



     


