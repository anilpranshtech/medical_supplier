import json
from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.utils import timezone


class RetailProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    age = models.IntegerField(null=True, blank=True)
    medical_needs = models.TextField(blank=True)

    class Meta:
        verbose_name = verbose_name_plural ="Retail Profile"


class WholesaleBuyerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    company_name = models.CharField(max_length=255)
    gst_number = models.CharField(max_length=50)
    department = models.CharField(max_length=100)
    purchase_capacity = models.IntegerField(help_text="Monthly purchase capacity")

    class Meta:
        verbose_name = verbose_name_plural ="Wholesale Buyer Profile"


class SupplierProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    company_name = models.CharField(max_length=255)
    license_number = models.CharField(max_length=100)
    is_verified = models.BooleanField(default=False)

    class Meta:
        verbose_name = verbose_name_plural ="Supplier Profile"


class ProductCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural ="Product Category"

class ProductSubCategory(models.Model):
    category = models.ForeignKey(ProductCategory,on_delete=models.CASCADE)
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural ="Product Sub Category"

class ProductLastCategory(models.Model):
    sub_category = models.ForeignKey(ProductSubCategory,on_delete=models.CASCADE)
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural ="Product Last Category"

class Brand(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = verbose_name_plural ="Brand"


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
    tag = models.CharField(max_length=30, choices=[('recent', 'Recently Arrived'), ('popular', 'Most Wanted'),('limited', 'Limited Stock'), ('none', 'None')], default='none')
    warranty = models.CharField(max_length=20, choices=[('none', 'None'), ('1yr', '1 Year'), ('2yr', '2 Years')], default='none')

    created_by = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']
        verbose_name = verbose_name_plural = "Product"

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='product_images/')
    is_main = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = verbose_name_plural = "Product Image"

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

    PAYMENT_STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('unpaid', 'Unpaid')
    ]

    order_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders_placed')
    order_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders_received')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')

     # Customer Info
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    # order_reference = models.CharField(max_length=20, blank=True, null=True)

    # Payment info
    payment = models.ForeignKey('Payment', on_delete=models.CASCADE, null=True, blank=True, related_name='orders')
    payment_type = models.CharField(max_length=50, default='BANK TRANSFER')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
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
        ordering = ['-created_at']
        verbose_name = verbose_name_plural = "Order"

    def __str__(self):
        return f"Order #{self.pk} - {self.product.name} x {self.quantity}"


class CustomerBillingAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    address_title = models.CharField(max_length=100, blank=True, default="Address")
    customer_name = models.CharField(verbose_name="Card Holder Name", max_length=128, null=True, blank=True)
    customer_address1 = models.CharField(max_length=255, null=True, blank=True)
    customer_address2 = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    customer_city = models.CharField(max_length=128, null=True, blank=True)
    customer_state = models.CharField(max_length=128, null=True, blank=True)
    customer_postal_code = models.CharField(max_length=64, null=True, blank=True)
    customer_country = models.CharField(max_length=128, null=True, blank=True)
    customer_country_code = models.CharField(max_length=10, null=True, blank=True)

    is_old = models.BooleanField(default=False)
    old_card = models.TextField(null=True, blank=True)

    is_deleted = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def delete(self, *args, **kwargs):
        """Override delete method to implement soft delete"""
        self.is_deleted = True
        self.save()


    def __str__(self):
        return f"{self.user} Billing Address"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_default=True),
                name='unique_default_billing_address'
            )
        ]
        ordering = ["-updated_at"]
        verbose_name = verbose_name_plural ="Customer Billing Address"

    @property
    def old_card_info(self):
        try:
            last_card = json.loads(self.old_card.replace("\'", "\""))
            return f"{last_card['last4']}-{last_card['exp_month']}/{last_card['exp_year']}"
        except:
            return "Not Available"


class WishlistProduct(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlists')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.product.name}"

    class Meta:
        unique_together = ('user', 'product')
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural = "Wishlist Product"



class CartProduct(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} for {self.user}"

    def get_total_price(self):
        return self.quantity * self.product.price

    class Meta:
        unique_together = ('user', 'product')
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural = "Cart Product"


class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = verbose_name_plural = "Notification"


class DeliveryPartner(models.Model):
    name = models.CharField(max_length=100, unique=True)
    tracking_url_template = models.URLField(
        max_length=500,
        blank=True,
        help_text="Use {tracking_id} as a placeholder. e.g., https://track.example.com/{tracking_id}"
    )
    support_email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural = "Delivery Partner"


class Payment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='payments')
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=[
        ("stripe", "Stripe"),
        ("razorpay", "Razorpay"),
        ("cod", "Cash on Delivery"),
    ])
    customer_id = models.CharField(max_length=100, blank=True, null=True)
    paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.amount} ({self.payment_method.upper()})"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural = "Payment"


class StripePayment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="stripe_payments")
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=True)
    customer_id = models.CharField(max_length=100)
    stripe_charge_id = models.CharField(max_length=100)
    stripe_customer_id = models.CharField(max_length=100)
    stripe_signature = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural = "Stripe Payment"


class RazorpayPayment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="razorpay_payments")
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=True)
    razorpay_payment_id = models.CharField(max_length=100)
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural = "Razorpay Payment"



class CODPayment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cod_payments")
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=False)
    cod_tracking_id = models.CharField(max_length=100, blank=True, null=True)
    delivery_partner = models.ForeignKey(
        DeliveryPartner, on_delete=models.SET_NULL, blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"COD - {self.cod_tracking_id or 'No Tracking ID'} by {self.user.get_full_name() or self.user.email}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural = "COD Payment"


class RoleRequest(models.Model):
    ROLE_CHOICES = [
        ('supplier', 'Supplier'),
        ('retailer', 'Retailer'),
        ('wholesaler', 'Wholesaler'),
    ]
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    requested_role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = verbose_name_plural = "Role Request"

    def __str__(self):
        return f"{self.user.username} - {self.requested_role} ({self.status})"

class RatingReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, f'{i} Stars') for i in range(1, 6)])
    review = models.TextField(blank=True)
    photo = models.ImageField(upload_to='review_photos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'user')  

class RFQRequest(models.Model):
    STATUS_CHOICES = [
        ('received', 'Received'),
        ('pending', 'Pending'),
        ('quoted', 'Quoted'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    # --- Request Info ---
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rfqs')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='rfq_requests')
    quantity = models.PositiveIntegerField(default=1)
    company_name = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
    attached_file = models.FileField(upload_to='rfq_attachments/', null=True, blank=True)
    expected_delivery_date = models.DateField(null=True, blank=True)

    # Quotation Info (from supplier/admin)
    quoted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='quoted_rfqs')
    quoted_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quote_attached_file = models.FileField(upload_to='rfq_attachments/', null=True, blank=True)
    supplier_notes = models.TextField(blank=True)
    quote_delivery_date = models.DateField(null=True, blank=True)
    quote_sent_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    email_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"RFQ #{self.id} - {self.product.name} by {self.requested_by.username}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural = "RFQ Request"
