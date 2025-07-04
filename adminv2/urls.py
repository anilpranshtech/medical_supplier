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

    # Category Add
    path('category/add/', AddcategoryView.as_view(), name='add_category'),
    path('category/edit/', EditcategoryView.as_view(), name='edit_category'),
    path('category/', CategoryView.as_view(), name='categories_list'),


    path('categories/create/', CreateProductCategoryView.as_view(), name='create_category'),


    path('adminv2/login/', AdminloginView.as_view(), name='admin_login'),
    path('user-profile/', UserProfileView.as_view(), name='user_profile'),
    path('overview/', UserOverView.as_view(), name='overview_list'),
    path('settings/', AdminSettingView.as_view(), name='profile_setting'),
    
]
