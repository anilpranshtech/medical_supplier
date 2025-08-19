import json
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.timezone import now
from datetime import timedelta
from django.conf import settings


class Speciality(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Residency(models.Model):
    country = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.country


class Nationality(models.Model):
    country = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.country


class CountryCode(models.Model):
    code = models.CharField(max_length=10, unique=True)
    country = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.country} ({self.code})"


class AdminUserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='adminuserprofile')
    profile_picture = models.ImageField(upload_to='avatars/', blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class RetailProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    current_position = models.CharField(max_length=255)
    workplace = models.CharField(max_length=255)

    nationality = models.ForeignKey(Nationality, on_delete=models.SET_NULL, null=True)
    residency = models.ForeignKey(Residency, on_delete=models.SET_NULL, null=True)
    country_code = models.ForeignKey(CountryCode, on_delete=models.SET_NULL, null=True)
    speciality = models.ForeignKey(Speciality, on_delete=models.SET_NULL, null=True)

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


class Event(models.Model):
    conference_link = models.URLField(max_length=500, null=True, blank=True)
    speaker_name = models.CharField(max_length=255, null=True, blank=True)
    conference_at = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True, help_text="Duration (e.g., 1:30:00 for 1 hour 30 minutes)")
    venue = models.CharField(max_length=500, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.speaker_name or 'Event'} at {self.venue or 'Unknown'}"

    class Meta:
        ordering = ['-conference_at']
        verbose_name = verbose_name_plural = "Events"


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
    script = models.TextField(blank=True,null=True)

    # Countries sold in
    all_countries = models.BooleanField(default=False)
    selling_countries = models.CharField(max_length=1000, blank=True,help_text="Comma-separated country names (e.g., India, USA, UK)")


    # Uploads
    brochure = models.FileField(upload_to='product_brochures/', null=True, blank=True)
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, blank=True)

    # Images handled separately (see below)

    # B2B / Pricing
    supplier_sku = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    weight_unit = models.CharField(max_length=10, choices=[('gm', 'Gram'), ('kg', 'Kilogram'), ('cm', 'Centimeter'), ('ltr', 'Liter')], null=True,blank=True)
    stock_quantity = models.IntegerField(default=0)
    pcs_per_unit = models.IntegerField(default=1)

    # Purchase options
    show_add_to_cart = models.BooleanField(default=False)
    show_rfq = models.BooleanField(default=False)
    Both = models.BooleanField(default=False)

    min_order_qty = models.IntegerField(default=0)
    low_stock_alert = models.IntegerField(default=0)

    # Dates
    is_returnable = models.BooleanField(default=False)
    return_time_limit = models.PositiveIntegerField(help_text="Days after delivery when returns are accepted", null=True, blank=True, default=7)
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
    condition = models.CharField(max_length=20, choices=[('new', 'New'), ('used', 'Used')], null=True, blank=True)
    tag = models.CharField(max_length=30, choices=[('recent', 'Recently Arrived'), ('popular', 'Most Wanted'),('limited', 'Limited Stock'), ('none', 'None')], default='none')
    warranty = models.CharField(max_length=20, choices=[('none', 'None'), ('1yr', '1 Year'), ('2yr', '2 Years')], default='none')

    created_by = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def discounted_price(self):
        if self.offer_active and self.offer_percentage and self.price:
            discount_amount = self.price * (self.offer_percentage / 100)
            return self.price - discount_amount
        return self.price

    def get_main_image(self):
        main_image = self.images.filter(is_main=True).first()  # ✅ use related_name
        if main_image:
            return main_image.image.url
        first_image = self.images.first()
        return first_image.image.url if first_image else None

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']
        verbose_name = verbose_name_plural = "Product"
    
    
class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to='product_images/')
    is_main = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = verbose_name_plural = "Product Image"


class EventRegistration(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, null=True, blank=True)
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    message = models.TextField(blank=True, null=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.product.name}"


class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    payment = models.ForeignKey('Payment', on_delete=models.SET_NULL, null=True, blank=True, related_name='order')
    order_id = models.CharField(max_length=50, unique=True)  # e.g., X319330-S24
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    shipping_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_type = models.CharField(max_length=100, default='Shipping')
    shipping_full_address = models.TextField(null=True, blank=True)
    shipping_city = models.CharField(max_length=100, null=True, blank=True)
    shipping_country = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('completed', 'Completed'),
            ('processing', 'Processing'),
            ('shipped', 'Shipped'),
            ('delivered', 'Delivered'),
            ('delivering', 'Delivering'),
            ('cancelled', 'Cancelled'),
            ('refunded', 'Refunded'),
            ('failed', 'Failed')
        ],
        default='pending'
    )

    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = generate_order_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order_id}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = verbose_name_plural = "Order"


# Renamed Orders to OrderItem
class OrderItem(models.Model):
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

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    order_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='order_items_placed')
    order_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='order_items_received')
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    payment_type = models.CharField(max_length=50, default='BANK TRANSFER')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    payment_currency = models.CharField(max_length=10, default='USD')
    delivery_date = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"OrderItem #{self.pk} - {self.product.name} x {self.quantity} in Order {self.order.order_id}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = verbose_name_plural = "Order Item"


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
        return self.quantity * self.product.discounted_price()

    def get_total_original_price(self):
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
        ("bank_transfer", "Bank Transfer"),
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


class BankTransferPayment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bank_transfer_payments")
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=False)
    verified_by_admin = models.BooleanField(default=False)
    admin_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    proof_image = models.ImageField(upload_to='bank_transfer_proofs/', blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural = "Bank Transfer Payment"


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


class PasswordUpdateTracker(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='password_tracker')
    last_password_update = models.DateTimeField(default=now)

    def is_password_expired(self):
        return self.last_password_update < now() - timedelta(days=90)


class DoctorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    current_position = models.CharField(max_length=255)
    workplace = models.CharField(max_length=255)

    nationality = models.ForeignKey(Nationality, on_delete=models.SET_NULL, null=True)
    residency = models.ForeignKey(Residency, on_delete=models.SET_NULL, null=True)
    country_code = models.ForeignKey(CountryCode, on_delete=models.SET_NULL, null=True)
    speciality = models.ForeignKey(Speciality, on_delete=models.SET_NULL, null=True)

    phone_number = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.speciality}"


class SubscriptionPlan(models.Model):
    CLIENT_TYPE_CHOICES = [
        ('supplier', 'Supplier'),
        ('buyer', 'Buyer'),
    ]

    BUYER_TYPE_CHOICES = [
        ('retailer', 'Retailer'),
        ('wholesaler', 'Wholesaler'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    period = models.CharField(max_length=50, blank=True, null=True)  # e.g. 'monthly', 'yearly'
    cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    web_plan_id = models.CharField(max_length=255, blank=True, null=True)
    ios_plan_id = models.CharField(max_length=100, null=True, blank=True)
    android_plan_id = models.CharField(max_length=100,null=True,blank=True)
    client_type = models.CharField(max_length=10, choices=CLIENT_TYPE_CHOICES)
    buyer_type = models.CharField(max_length=10, choices=BUYER_TYPE_CHOICES, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def clean(self):
        if self.client_type == 'buyer' and not self.buyer_type:
            raise ValidationError("buyer_type is required when client_type is 'buyer'.")

    def __str__(self):
        return f"{self.name} ({self.client_type}{' - ' + self.buyer_type if self.buyer_type else ''})"

    class Meta:
        unique_together = ('name', 'client_type', 'buyer_type')


class PlatformPlan(models.Model):
    PLATFORM_CHOICES = [
        ('ios', 'iOS'),
        ('android', 'Android'),
        ('web', 'Web'),
    ]

    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    subscription_plan = models.ForeignKey(SubscriptionPlan, related_name='platform_plans', on_delete=models.CASCADE)
    platform_plan_id = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.subscription_plan.name} - {self.platform.upper()} Plan ID"


class UserSubscription(models.Model):
    PLATFORM_CHOICES = [
        ('web', 'Web'),
        ('ios', 'iOS'),
        ('android', 'Android'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    subscription_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    platform_plan_id = models.CharField(max_length=100)

    def clean(self):
        platform_plan = PlatformPlan.objects.filter(subscription_plan=self.plan, platform=self.platform).first()
        if not platform_plan:
            raise ValidationError(f"{self.platform} plan ID not found for this subscription plan.")
        self.platform_plan_id = platform_plan.platform_plan_id

    def save(self, *args, **kwargs):
        if self.platform == 'ios':
            self.platform_plan_id = self.plan.ios_plan_id
        elif self.platform == 'android':
            self.platform_plan_id = self.plan.android_plan_id
        else:
            self.platform_plan_id = self.plan.web_plan_id
        super().save(*args, **kwargs)

     # def clean(self):
    #     if self.platform == 'ios' and not self.plan.ios_plan_id:
    #         raise ValidationError("ios_plan_id is required for iOS platform.")
    #     if self.platform == 'android' and not self.plan.android_plan_id:
    #         raise ValidationError("android_plan_id is required for Android platform.")

    def __str__(self):
        return f"{self.user.email} - {self.plan.name} ({self.platform})"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'plan', 'platform'], name='unique_user_plan_platform')
        ]


class Feature(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('additional', 'Additional'),
        ('unavailable', 'Unavailable'),
    ]

    name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    cost = models.CharField(max_length=50, blank=True, null=True)
    plans = models.ManyToManyField(SubscriptionPlan, related_name='features')

    def __str__(self):
        return self.name


class StripeSubscriptionMetadata(models.Model):
    PLAN_TYPE_CHOICES = [
        ('Golden', 'Golden'),
        ('Silver', 'Silver'),
        ('Platinum', 'Platinum'),
    ]

    DURATION_CHOICES = [
        ('Month', 'Month'),
        ('Year', 'Year'),
    ]

    subscription_plan = models.OneToOneField(SubscriptionPlan, on_delete=models.CASCADE, related_name='stripe_metadata')
    price = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    price_id = models.CharField(max_length=500)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPE_CHOICES, default='Golden')
    plan_duration = models.CharField(max_length=10, choices=DURATION_CHOICES, default='Year')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.subscription_plan.name} | {self.plan_type} | {self.plan_duration} - ${self.price}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural = "Stripe Subscriptions"


# class SubscriptionPlan(models.Model):
#     CLIENT_TYPE_CHOICES = [
#         ('supplier', 'Supplier'),
#         ('buyer', 'Buyer'),
#     ]
#
#     BUYER_TYPE_CHOICES = [
#         ('retailer', 'Retailer'),
#         ('wholesaler', 'Wholesaler'),
#     ]
#
#     name = models.CharField(max_length=100,null=True,blank=True)
#     description = models.TextField(null=True,blank=True)
#     ios_plan_id = models.CharField(max_length=100,null=True,blank=True)
#     android_plan_id = models.CharField(max_length=100,null=True,blank=True)
#     period = models.CharField(max_length=50,null=True,blank=True)
#     cost = models.DecimalField(max_digits=10, decimal_places=2,null=True,blank=True)
#     client_type = models.CharField(max_length=10, choices=CLIENT_TYPE_CHOICES,null=True,blank=True)
#     buyer_type = models.CharField(max_length=10, choices=BUYER_TYPE_CHOICES, blank=True, null=True)
#
#     def __str__(self):
#         return self.name
#
#     def clean(self):
#         if self.client_type == 'buyer' and not self.buyer_type:
#             raise ValidationError("buyer_type is required when client_type is 'buyer'.")
#
#     class Meta:
#         unique_together = ('name', 'client_type', 'buyer_type')
#
#
# class UserSubscription(models.Model):
#     PLATFORM_CHOICES = [
#         ('web', 'Web'),
#         ('ios', 'iOS'),
#         ('android', 'Android'),
#     ]
#
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
#     platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
#     subscription_date = models.DateTimeField(auto_now_add=True)
#     is_active = models.BooleanField(default=True)
#     platform_plan_id = models.CharField(max_length=100)
#
#     def save(self, *args, **kwargs):
#         if self.platform == 'ios':
#             self.platform_plan_id = self.plan.ios_plan_id
#         else:
#             self.platform_plan_id = self.plan.android_plan_id
#         super().save(*args, **kwargs)
#
#     def clean(self):
#         if self.platform == 'ios' and not self.plan.ios_plan_id:
#             raise ValidationError("ios_plan_id is required for iOS platform.")
#         if self.platform == 'android' and not self.plan.android_plan_id:
#             raise ValidationError("android_plan_id is required for Android platform.")
#
#     def __str__(self):
#         return f"{self.user.email} - {self.plan.name}"


class PendingSignup(models.Model):
    token = models.CharField(max_length=64, unique=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return now() > self.created_at + timedelta(minutes=10)


class Question(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="questions", null=True, blank=True)  # <-- added null=True, blank=True
    text = models.TextField()
    reply = models.TextField(null=True, blank=True) 
    replied_at = models.DateTimeField(null=True, blank=True) 
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text[:50]


class Return(models.Model):
    RETURN_OPTION_CHOICES = [
        ('replace', 'Replace'),
        ('return', 'Return'),
    ]
    RETURN_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('replace_completed', 'Replace Completed'),
        ('return_completed', 'Return Completed'),
        ('cancelled', 'Cancelled'),
    ]

    return_serial = models.CharField(max_length=50, primary_key=True)
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='returns')
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='return_requests')
    return_option = models.CharField(max_length=20, choices=RETURN_OPTION_CHOICES)
    return_status = models.CharField(max_length=20, choices=RETURN_STATUS_CHOICES, default='pending')
    request_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Return {self.return_serial} - {self.order_item.product.name}"

    class Meta:
        ordering = ['-request_date']
        verbose_name = verbose_name_plural = "Return"

    def is_within_return_period(self):
        from django.utils import timezone
        delivery_date = self.order_item.order.updated_at
        return (timezone.now() - delivery_date).days <= 15

    def save(self, *args, **kwargs):
        if not self.return_serial:
            from django.utils import timezone
            import random
            base_serial = 'R'
            year = timezone.now().strftime('%y')
            month = timezone.now().strftime('%m')
            unique_code = ''.join(random.choices('0123456789', k=3))
            suffix = 'R' + year
            self.return_serial = f"{base_serial}{month}{unique_code}-{suffix}"
            while Return.objects.filter(return_serial=self.return_serial).exists():
                unique_code = ''.join(random.choices('0123456789', k=3))
                self.return_serial = f"{base_serial}{month}{unique_code}-{suffix}"
        super().save(*args, **kwargs)