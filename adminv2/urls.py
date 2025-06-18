from django.urls import path
from .views import HomeView,ProductsView,EditcategoryView,EditproductsView,CategoryView,AddcategoryView,AddproductsView,AdminloginView,UserProfileView

app_name = 'adminv2'
urlpatterns = [
    path('admin_v2/', HomeView.as_view(), name='dashboard'),
    path('products/', ProductsView.as_view(), name='products_list'),
    path('products/edit/', EditproductsView.as_view(), name='edit_product'),
    path('category/edit/', EditcategoryView.as_view(), name='edit_category'),
    path('category/', CategoryView.as_view(), name='categories_list'),
    path('category/add/', AddcategoryView.as_view(), name='add_category'),
    path('products/add/', AddproductsView.as_view(), name='add_product'),
    path('adminv2/login/', AdminloginView.as_view(), name='admin_login'),
    path('user-profile/', UserProfileView.as_view(), name='user_profile'),
    
]