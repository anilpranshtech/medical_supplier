from django.urls import path
from .views import *

app_name = 'adminv3'
urlpatterns = [

    # Home analytics
    path('', HomeView.as_view(), name='admin_v3_home'),

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

    # Orders Urls
    path('orders/list/', OrderListingView.as_view(), name='orders_list'),
    path('order/detail/<slug:order_id>/', OrderDetailesView.as_view(), name='orders_detail'),
    path('orders/delete/<int:pk>/', OrderDeleteView.as_view(), name='order_delete'),


]
