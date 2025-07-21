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

    path('users/add-new-user/', User_Accounts_AddNewUser.as_view(), name='user_accounts_add_new_user'),

    path('users/permissions/', PermissionsUsers.as_view(), name='user_permissions'),

    # Products pages
    path('products/list/', ProductsListView.as_view(), name='products_list'),

]
