from django.views import View
from django.shortcuts import render,redirect
from django.contrib import messages
from dashboard.models import Product


class HomeView(View):
    def get(self, request):
        return render(request, 'adminv2/base.html')

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

    def post(self, request):
        name = request.POST.get('product_name')
        description = request.POST.get('product_description')
        price = request.POST.get('price')



        try:
            price = float(price)
        except (TypeError, ValueError):
            messages.error(request, "Please enter a valid number for price.")
            return render(request, 'adminv2/add-product.html')


        if not name or not description:
            messages.error(request, "All fields are required.")
            return render(request, 'adminv2/add-product.html')

        try:
            Product.objects.create(
                name=name,
                description=description,
                price=price
            )
            messages.success(request, "Product added successfully!")
            return redirect('adminv2:add_product') 
        except Exception as e:
            messages.error(request, f"Failed to save product: {e}")
            return render(request, 'adminv2/add-product.html')



class AddcategoryView(View):
    def get(self, request):
        return render(request, 'adminv2/add-category.html')

class CategoryView(View):
    def get(self, request):
        return render(request, 'adminv2/categories.html')  

class AdminloginView(View):
    def get(self, request):
        return render(request, 'adminv2/sign-in.html')

    