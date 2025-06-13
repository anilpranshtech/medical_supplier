from django.urls import path
from .views import ProductsView,EditcategoryView,EditproductsView,CategoryView,AddcategoryView,AddproductsView

app_name = 'adminv2'
urlpatterns = [
    path('products/', ProductsView.as_view(), name='products_list'),
    path('products/edit/', EditproductsView.as_view(), name='edit_product'),
    path('category/edit/', EditcategoryView.as_view(), name='edit_category'),
    path('category/', CategoryView.as_view(), name='categories_list'),
    path('category/add/', AddcategoryView.as_view(), name='add_category'),
    path('products/add/', AddproductsView.as_view(), name='add_product'),
]