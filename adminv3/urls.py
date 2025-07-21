from django.urls import path
from .views import *

app_name = 'adminv3'
urlpatterns = [

    # Home analytics
    path('', HomeView.as_view(), name='admin_v3_home'),

    # Users pages
    path('users/accounts/', UsersAccounts.as_view(), name='user_accounts'),
    path('users/<int:pk>/details/', UserDetailView.as_view(), name='user_detail'),

    path('users/permissions/', PermissionsUsers.as_view(), name='user_permissions'),

    # Products pages
    path('products/list/', ProductsListView.as_view(), name='products_list'),

]
