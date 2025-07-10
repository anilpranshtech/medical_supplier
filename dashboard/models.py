from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.utils import timezone

class DoctorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    current_position = models.CharField(max_length=100, null=True, blank=True)
    workplace = models.CharField(max_length=100, null=True, blank=True)
    nationality = models.CharField(max_length=100, null=True, blank=True)
    residency = models.CharField(max_length=100, null=True, blank=True)
    country_code = models.CharField(max_length=10, null=True, blank=True)
    phone_number = models.CharField(max_length=30, null=True, blank=True)
    speciality = models.CharField(max_length=100, null=True, blank=True)
    medical_license_number = models.CharField(max_length=100, null=True, blank=True)
    license_expiry_date = models.DateField(null=True, blank=True)
    experience_years = models.CharField(max_length=3, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        verbose_name = "Doctor Profile"
        verbose_name_plural = "Doctor Profiles"
        ordering = ['-created_at']


class MedicalSupplierProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    workplace = models.CharField(max_length=100, null=True, blank=True)
    nationality = models.CharField(max_length=100, null=True, blank=True)
    residency = models.CharField(max_length=100, null=True, blank=True)
    phone_details = models.CharField(max_length=30, null=True, blank=True)
    business_license_number = models.CharField(max_length=100, null=True, blank=True)
    company_name = models.CharField(max_length=100, null=True, blank=True)
    years_in_operation = models.CharField(max_length=3, null=True, blank=True)
    warehouse_locations = models.CharField(max_length=100, null=True, blank=True)
    product_specialization = models.CharField(max_length=200, null=True, blank=True)
    product_categories = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        verbose_name = "Medical Supplier Profile"
        verbose_name_plural = "Medical Supplier Profiles"
        ordering = ['-created_at']


class CorporateProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company_name = models.CharField(max_length=100, null=True, blank=True)
    department = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    industry_type = models.CharField(max_length=100, null=True, blank=True)
    company_website = models.URLField(blank=True, null=True)
    registration_number = models.CharField(max_length=100, null=True, blank=True)
    billing_address = models.TextField(null=True, blank=True)
    shipping_address = models.TextField(null=True, blank=True)
    contact_name = models.CharField(max_length=100, null=True, blank=True)
    contact_role = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        verbose_name = "Corporate Profile"
        verbose_name_plural = "Corporate Profiles"
        ordering = ['-created_at']


class RetailProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    medical_needs = models.TextField(blank=True)


class WholesaleBuyerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    company_name = models.CharField(max_length=255)
    gst_number = models.CharField(max_length=50)
    department = models.CharField(max_length=100)
    purchase_capacity = models.IntegerField(help_text="Monthly purchase capacity")


class SupplierProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    company_name = models.CharField(max_length=255)
    license_number = models.CharField(max_length=100)
    is_verified = models.BooleanField(default=False)


class ProductCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class ProductSubCategory(models.Model):
    category = models.ForeignKey(ProductCategory,on_delete=models.CASCADE)
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class ProductLastCategory(models.Model):
    sub_category = models.ForeignKey(ProductSubCategory,on_delete=models.CASCADE)
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Brand(models.Model):
    name = models.CharField(max_length=100)


class Product(models.Model):
    # Category hierarchy
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True)
    sub_category = models.ForeignKey(ProductSubCategory, on_delete=models.SET_NULL, null=True)
    last_category = models.ForeignKey(ProductLastCategory, on_delete=models.SET_NULL, null=True)

    # Basic Info
    name = models.CharField(max_length=255)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True)
    product_from = models.CharField(max_length=100, null=True, blank=True, help_text="Country of origin")
    description = models.TextField(blank=True)
    keywords = models.CharField(max_length=255, help_text="Comma-separated keywords", blank=True)

    # Countries sold in
    all_countries = models.BooleanField(default=False)
    selling_countries = models.CharField(max_length=1000, blank=True,help_text="Comma-separated country names (e.g., India, USA, UK)")


    # Uploads
    brochure = models.FileField(upload_to='product_brochures/', null=True, blank=True)

    # Images handled separately (see below)

    # B2B / Pricing
    supplier_sku = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    weight_unit = models.CharField(max_length=10, choices=[('gm', 'Gram'), ('kg', 'Kilogram'), ('cm', 'Centimeter'), ('ltr', 'Liter')], default='gm')
    stock_quantity = models.IntegerField(default=0)
    pcs_per_unit = models.IntegerField(default=1)

    # Purchase options
    show_add_to_cart = models.BooleanField(default=False)
    show_rfq = models.BooleanField(default=False)
    Both = models.BooleanField(default=False)

    min_order_qty = models.IntegerField(default=1)
    low_stock_alert = models.IntegerField(default=5)

    # Dates
    return_time_limit = models.PositiveIntegerField(help_text="Days", null=True, blank=True)
    delivery_time = models.PositiveIntegerField(help_text="Days", null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    manufacture_date = models.DateField(null=True, blank=True)
    expiration_days = models.PositiveIntegerField(null=True, blank=True)

    # Barcode & Offers
    barcode = models.CharField(max_length=100, blank=True)
    offer_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    offer_start = models.DateField(null=True, blank=True)
    offer_end = models.DateField(null=True, blank=True)
    offer_active = models.BooleanField(default=False)

    # Admin status
    is_active = models.BooleanField(default=False)
    ask_admin_to_publish = models.BooleanField(default=False)

    # Product status
    condition = models.CharField(max_length=20, choices=[('new', 'New'), ('used', 'Used')], default='new')
    tag = models.CharField(max_length=30, choices=[('recent', 'Recently Arrived'), ('popular', 'Most Wanted'),('limited', 'Limited Stoke'), ('none', 'None')], default='none')
    warranty = models.CharField(max_length=20, choices=[('none', 'None'), ('1yr', '1 Year'), ('2yr', '2 Years')], default='none')

    created_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ['-created_at']


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='product_images/')
    is_main = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        verbose_name = "Product Image"
        verbose_name_plural = "Product Images"
        ordering = ['-created_at']




class Orders(models.Model):

    ORDER_STATUS_CHOICES = [
        ('pending', 'Pending'),
         ('completed', 'Completed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('delivering', 'Delivering'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed')
    ]

    order_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders_placed')
    order_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders_received')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')

     # Customer Info
    phone_number = models.PositiveIntegerField(default=0)

    # Payment info
    payment_type = models.CharField(max_length=50, default='BANK TRANSFER')
    payment_status = models.CharField(max_length=20, default='PAID')
    payment_currency = models.CharField(max_length=10, default='USD')
   
    # Shipping info
    shipping_fees = models.PositiveIntegerField(default=0)
    shipping_type = models.CharField(max_length=100, default='Shipping')

    # Address info
    shipping_full_address = models.TextField(null=True,blank=True)
    shipping_city = models.CharField(max_length=100,null=True,blank=True)
    shipping_country = models.CharField(max_length=100,null=True,blank=True)


    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.pk} - {self.product.name} x {self.quantity}"


class WishlistProduct(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlists')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-created_at']
        verbose_name = 'Wishlist Item'
        verbose_name_plural = 'Wishlist Items'

    def __str__(self):
        return f"{self.user} - {self.product.name}"


class CartProduct(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-created_at']
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'

    def __str__(self):
        return f"{self.quantity} x {self.product.name} for {self.user}"

    def get_total_price(self):
        return self.quantity * self.product.price
    

class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False) 
    created_at = models.DateTimeField(default=timezone.now)
    

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notification"
        ordering = ['-created_at']


class Payment(models.Model):
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    order_id = models.CharField(max_length=100, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
