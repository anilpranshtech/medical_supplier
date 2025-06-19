from django.views import View
from django.shortcuts import render,redirect
from django.contrib import messages
from dashboard.models import Product,ProductImage
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse   
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import check_password

class HomeView(LoginRequiredMixin, UserPassesTestMixin, View):
    login_url = 'adminv2:admin_login'
    def get(self, request):
        return render(request, 'adminv2/base.html')
    
    def test_func(self):
        return self.request.user.is_superuser
    
class ProductsView(LoginRequiredMixin, UserPassesTestMixin,View):
    def get(self, request):
        products = Product.objects.all()

        for product in products:
            image = ProductImage.objects.filter(product=product).first()
            product.image_url = image.image.url if image else '/static/adminv2/media/stock/ecommerce/placeholder.png'

        return render(request, 'adminv2/products.html', {'products': products})
    def test_func(self):
        return self.request.user.is_superuser
    
class EditproductsView(LoginRequiredMixin, UserPassesTestMixin,View):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        product_image = ProductImage.objects.filter(product=product).first()  
        return render(request, 'adminv2/edit-product.html', {
            'product': product,
            'product_image': product_image
        })

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        product.name = request.POST.get('product_name')
        product.description = request.POST.get('description')
        product.price = request.POST.get('price')
        product.save()

        if 'avatar' in request.FILES:
            image_file = request.FILES['avatar']
            product_image, created = ProductImage.objects.get_or_create(product=product)
            product_image.image = image_file
            product_image.save()
        
        messages.success(request, 'Changes saved successfully!')
        return redirect('adminv2:products_list')  
        
    def test_func(self):
        return self.request.user.is_superuser
    

class DeleteProductView(LoginRequiredMixin, UserPassesTestMixin,View):
    def post(self, request, pk):
        print("hello")
        product = get_object_or_404(Product, pk=pk)
        product.delete()
        return JsonResponse({'success': True})
    
    def test_func(self):
        return self.request.user.is_superuser

class EditcategoryView(LoginRequiredMixin, UserPassesTestMixin,View):
    def get(self, request):
        return render(request, 'adminv2/edit-category.html')
    def test_func(self):
        return self.request.user.is_superuser

class AddproductsView(LoginRequiredMixin, UserPassesTestMixin,View):
    def get(self, request):
        return render(request, 'adminv2/add-product.html')

    def post(self, request):
        name = request.POST.get('product_name')
        description = request.POST.get('product_description')
        price = request.POST.get('price')
        avatar = request.FILES.get('avatar')  

        try:
            price = float(price)
        except (TypeError, ValueError):
            messages.error(request, "Please enter a valid number for price.")
            return render(request, 'adminv2/add-product.html')

        if not name or not description:
            messages.error(request, "All fields are required.")
            return render(request, 'adminv2/add-product.html')

        try:
            product = Product.objects.create(
                name=name,
                description=description,
                price=price
            )
            if avatar:
                ProductImage.objects.create(
                    product=product,
                    image=avatar
                )

            messages.success(request, "Product added successfully!")
            return redirect('adminv2:add_product')

        except Exception as e:
            messages.error(request, f"Failed to save product: {e}")
            return render(request, 'adminv2/add-product.html')
        
    def test_func(self):
        return self.request.user.is_superuser


class AddcategoryView(LoginRequiredMixin, UserPassesTestMixin,View):
    def get(self, request):
        return render(request, 'adminv2/add-category.html')
    
    def test_func(self):
        return self.request.user.is_superuser

class CategoryView(LoginRequiredMixin, UserPassesTestMixin,View):
    def get(self, request):
        return render(request, 'adminv2/categories.html')  
    
    def test_func(self):
        return self.request.user.is_superuser

class AdminloginView(View):
    def get(self, request):
        return render(request, 'adminv2/sign-in.html')

    def post(self, request):
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            user_obj = User.objects.get(email=email) 
            user = authenticate(request, username=user_obj.username, password=password)
            
            if user is not None:
                if user.is_superuser:
                    login(request, user)
                    return redirect('adminv2:products_list')
                else:
                    messages.error(request, "Only superusers are allowed to log in.")
            else:
                messages.error(request, "Invalid email or password.")
        except User.DoesNotExist:
            messages.error(request, "User with this email does not exist.")

        return render(request, 'adminv2/sign-in.html')


class UserProfileView(View):
    def get(self, request):
        return render(request, 'adminv2/user-profile.html')
class UserOverView(View):
    def get(self, request):
        return render(request, 'adminv2/overview.html')
class AdminSettingView(View):
    def get(self, request):
     
        return render(request, 'adminv2/settings.html')

class AdminSettingView(View):
    def get(self, request):
        return render(request, 'adminv2/settings.html')

    def post(self, request):
        if 'fname' in request.POST:
            fname = request.POST.get('fname')
            lname = request.POST.get('lname')
            email = request.POST.get('aemail')
           
            user = request.user
            user.first_name = fname
            user.last_name = lname
            user.email = email
            user.save()

            messages.success(request, "Profile updated successfully!")
            return redirect('adminv2:profile_setting')

        elif 'currentpassword' in request.POST:
            current = request.POST.get('currentpassword')
            new = request.POST.get('newpassword')
            confirm = request.POST.get('confirmpassword')
            user = request.user

            if not check_password(current, user.password):
                messages.error(request, "Current password is incorrect.")
            elif new != confirm:
                messages.error(request, "New passwords do not match.")
            elif len(new) < 8:
                messages.error(request, "Password must be at least 8 characters.")
            else:
                user.set_password(new)
                user.save()
                update_session_auth_hash(request, user) 
                messages.success(request, "Password updated successfully.")

            return redirect('adminv2:profile_setting')
