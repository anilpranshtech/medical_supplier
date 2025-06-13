from django.views import View
from django.shortcuts import render

class ProductsView(View):
    def get(self, request):
        return render(request, 'adminv2/products.html')

class EditproductsView(View):
    def get(self, request):
        return render(request, 'adminv2/edit-product.html')

class EditcategoryView(View):
    def get(self, request):
        return render(request, 'adminv2/edit-category.html')
    
class AddproductsView(View):
    def get(self, request):
        return render(request, 'adminv2/add-product.html')

class AddcategoryView(View):
    def get(self, request):
        return render(request, 'adminv2/add-category.html')

class CategoryView(View):
    def get(self, request):
        return render(request, 'adminv2/categories.html')  