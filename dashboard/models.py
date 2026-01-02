import json
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.timezone import now
from datetime import timedelta
from django.conf import settings


# -------------------- Country, State, City --------------------

class Regioncities(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)


    def __str__(self):
        return self.name


class State(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="states")
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ("country", "name")

    def __str__(self):
        return f"{self.name}, {self.country.name}"


class City(models.Model):
    state = models.ForeignKey(State, on_delete=models.CASCADE, null=True,blank=True, related_name="cities")
    region = models.ForeignKey(Regioncities, on_delete=models.SET_NULL, null=True, blank=True, related_name="cities")
    created_at = models.DateTimeField(auto_now_add=True, null=True,blank=True)
  
    name = models.CharField(max_length=100)

    class Meta: 
        unique_together = ("state", "name")

    def __str__(self):
        city = self.name if self.name else "Unnamed City"
        state = self.state.name if self.state and self.state.name else "No State"
        return f"{city}, {state}"



# -------------------- Specialities --------------------
class Speciality(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class SubSpeciality(models.Model):
    speciality = models.ForeignKey(Speciality, related_name="sub_specialities", on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("speciality", "name")

    def __str__(self):
        return f"{self.name} ({self.speciality.name})"


# -------------------- Residency --------------------
class Residency(models.Model):
    country = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.country


# -------------------- Nationality --------------------
class Nationality(models.Model):
    country = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.country


# -------------------- CountryCode --------------------
class CountryCode(models.Model):
    code = models.CharField(max_length=10, unique=True)
    country = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="phone_codes"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.code} → {self.country.name if self.country else 'No country'}"




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

    nationality = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
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





class ProductCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural ="Product Category"


SUPPLIER_TYPE_CHOICES = [
    ('distributor', 'Distributor'),
    ('supplier', 'Supplier'),
]

B2B_CHOICES = [
    ('yes', 'Yes'),
    ('no', 'No'),
]


class SupplierProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    onboarding_complete = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    company_name = models.CharField(max_length=255)
    license_number = models.CharField(max_length=100)
    is_verified = models.BooleanField(default=False)
    email_confirmed = models.BooleanField(default=False)

    # New fields
    job_title = models.CharField(max_length=255, blank=True, null=True)
    supplier_type = models.CharField(max_length=20, choices=SUPPLIER_TYPE_CHOICES, blank=True, null=True)
    are_you_buyer_b2b = models.CharField(max_length=3, choices=B2B_CHOICES, blank=True, null=True)
    selling_for = models.CharField(max_length=255, blank=True, null=True)
    meta_description = models.TextField(blank=True, null=True)
    meta_keywords = models.TextField(blank=True, null=True)

    # New Business Information fields
    business_name = models.CharField(max_length=255, blank=True, null=True)
    company_logo = models.ImageField(upload_to='company_logos/', null=True, blank=True)
    registration_number = models.CharField(max_length=100, blank=True, null=True)
    company_commercial_license = models.ImageField(upload_to='commercial_licenses/', null=True, blank=True)
    authorized_person_name = models.CharField(max_length=255, blank=True, null=True)
    iso_certificate = models.ImageField(upload_to='iso_certificates/', null=True, blank=True)
    export_import_license = models.ImageField(upload_to='export_import_licenses/', null=True, blank=True)

     # Bank Details
    account_holder_name = models.CharField(max_length=255, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    iban_code = models.CharField(max_length=50, blank=True, null=True)
    iban_certificate = models.ImageField(upload_to='iban_certificates/', null=True, blank=True)
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    swift_code = models.CharField(max_length=50, blank=True, null=True)

    # 
    selling_categories = models.ManyToManyField(ProductCategory, blank=True, related_name="suppliers")

    # Supplier description fields
    facebook = models.URLField(max_length=500, blank=True, null=True)
    instagram = models.URLField(max_length=500, blank=True, null=True)
    twitter = models.URLField(max_length=500, blank=True, null=True)
    google_page = models.URLField(max_length=500, blank=True, null=True)
    linkedin = models.URLField(max_length=500, blank=True, null=True)

    short_description = models.TextField(blank=True, null=True)
    shipping_and_payment_terms = models.TextField(blank=True, null=True)
    return_policy = models.TextField(blank=True, null=True)

    banner = models.ImageField(upload_to='supplier_banners/', null=True, blank=True)


      # pickup Description Fields
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    support_pickup = models.BooleanField(default=False)

    #  Suppier Documents
    signature_authority_doc = models.ImageField(upload_to='supplier_docs/signature_authority/', null=True, blank=True)
    memorandum_of_association = models.ImageField(upload_to='supplier_docs/memorandum/', null=True, blank=True)
    ce_certificate = models.ImageField(upload_to='supplier_docs/ce_certificates/', null=True, blank=True)
    fda_certificate = models.ImageField(upload_to='supplier_docs/fda_certificates/', null=True, blank=True)
    other_certificate_1 = models.ImageField(upload_to='supplier_docs/other_certificates/', null=True, blank=True)
    other_certificate_2 = models.ImageField(upload_to='supplier_docs/other_certificates/', null=True, blank=True)
    other_supporting_doc_1 = models.ImageField(upload_to='supplier_docs/other_supporting_docs/', null=True, blank=True)
    other_supporting_doc_2 = models.ImageField(upload_to='supplier_docs/other_supporting_docs/', null=True, blank=True)
    other_supporting_doc_3 = models.ImageField(upload_to='supplier_docs/other_supporting_docs/', null=True, blank=True)

    #Status 
    current_status = models.CharField(max_length=10, choices=[('active','Active'),('inactive','Inactive')], default='active')
    request_for = models.CharField(max_length=10, choices=[('vacation','Vacation'),('close','Close'),('none','None')], default='none')
    equest_reason = models.TextField(blank=True, null=True)
    steps_tracking = models.IntegerField(default=0)
    class Meta:
        verbose_name = "Supplier Profile"
        verbose_name_plural = "Supplier Profiles"

    def __str__(self):
        return f"{self.user.username} - {self.company_name}"


class ProductSubCategory(models.Model):
    category = models.ForeignKey(ProductCategory,on_delete=models.CASCADE)
    name = models.CharField(max_length=255, unique=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural ="Product Sub Category"


class ProductLastCategory(models.Model):
    sub_category = models.ForeignKey(ProductSubCategory,on_delete=models.CASCADE)
    name = models.CharField(max_length=255, unique=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural ="Product Last Category"


class Brand(models.Model):
    name = models.CharField(max_length=100)
    supplier = models.ForeignKey(User, on_delete=models.CASCADE, related_name='brands')

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
    id = models.AutoField(primary_key=True)
    # Category 
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

    # Countries 
    all_countries = models.BooleanField(default=False)
    selling_countries = models.CharField(max_length=1000, blank=True,help_text="Comma-separated country names (e.g., India, USA, UK)")


    # Uploads
    brochure = models.FileField(upload_to='product_brochures/', null=True, blank=True)
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, blank=True)

    # B2B / Pricing
    supplier_sku = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) 
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
    cash_on_delivery = models.BooleanField(
        default=True, 
        verbose_name="Cash on Delivery Available",
        help_text="Enable Cash on Delivery option for this product"
    )

    created_by = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def discounted_price(self):
        if self.offer_active and self.offer_percentage and self.price:
            discount_amount = self.price * (self.offer_percentage / 100)
            return self.price - discount_amount
        return self.price

    def get_main_image(self):
        main_image = self.images.filter(is_main=True).first()
        if main_image:
            return main_image.image.url
        first_image = self.images.first()
        return first_image.image.url if first_image else None

    def get_return_deadline(self, delivered_at):
        if not delivered_at or not self.is_returnable:
            return None
        return delivered_at + timedelta(days=self.return_time_limit)
    
  
    def get_final_commission(self):
        if self.commission_percentage > 0:
            return self.commission_percentage
        supplier_commission = SupplierCommission.objects.filter(supplier=self.created_by).first()
        return supplier_commission.commission_b2c if supplier_commission else 0
    
    def is_out_of_stock(self):
        return self.stock_quantity < self.min_order_qty
 
    def available_stock(self):
        return max(self.stock_quantity, 0)

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
    order_type = models.CharField(
    max_length=10,
    choices=[('order', 'Order'), ('return', 'Return')],
    default='order'
)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    payment = models.ForeignKey('Payment', on_delete=models.SET_NULL, null=True, blank=True, related_name='order')
    order_id = models.CharField(max_length=50, unique=True)  
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    shipping_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_type = models.CharField(max_length=100, default='Shipping')
    shipping_full_address = models.TextField(null=True, blank=True)
    shipping_city = models.CharField(max_length=100, null=True, blank=True)
    shipping_country = models.CharField(max_length=100, null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
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

    @property
    def return_deadline(self):
        """Calculate return deadline based on delivery date"""
        # First check if the product is returnable
        if not self.product.is_returnable:
            return None

        # Get delivery date - prioritize order item's delivery_date, then order's delivered_at
        delivered_on = self.delivery_date or self.order.delivered_at

        # If no delivery date is set, but order status is 'delivered', use updated_at
        if not delivered_on and self.order.status == 'delivered':
            delivered_on = self.order.updated_at

        if not delivered_on:
            return None

        # Use product's return_time_limit or default to 15 days
        return_days = self.product.return_time_limit or 15
        return delivered_on + timedelta(days=return_days)

    @property
    def can_return(self):
        """Check if item can be returned"""
        # Must be delivered to be returnable
        if self.order.status != 'delivered':
            return False

        # Product must be returnable
        if not self.product.is_returnable:
            return False

        # Check if within return deadline
        deadline = self.return_deadline
        if not deadline:
            return False

        return timezone.now() <= deadline

    @property
    def days_left_to_return(self):
        """Get number of days left to return"""
        deadline = self.return_deadline
        if not deadline:
            return 0

        days_left = (deadline - timezone.now()).days
        return max(0, days_left)  # Return 0 if negative

    def get_return_status_message(self):
        """Get a user-friendly return status message"""
        if not self.product.is_returnable:
            return "This product is not returnable"

        if self.order.status != 'delivered':
            return "Product must be delivered before return request"

        days_left = self.days_left_to_return
        if days_left > 0:
            return f"Return available for {days_left} more days"
        else:
            return "Return period has expired"

    @property
    def has_pending_return(self):
        """Check if item has a pending return request"""
        return self.returns.filter(return_status='pending').exists()

    @property
    def latest_return(self):
        """Get the latest return request for this item"""
        return self.returns.order_by('-request_date').first()

    @property
    def return_history(self):
        """Get all return requests for this item"""
        return self.returns.all().order_by('-request_date')

    @property
    def can_request_return(self):
        """Check if user can request a new return (no pending returns)"""
        return (
                self.can_return and
                not self.has_pending_return and
                self.order.status == 'delivered'
        )

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


# class Notification(models.Model):
#     recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
#     title = models.CharField(max_length=255)
#     message = models.TextField()
#     is_read = models.BooleanField(default=False)
#     is_deleted = models.BooleanField(default=False)
#     created_at = models.DateTimeField(default=timezone.now)

#     class Meta:
#         ordering = ['-created_at']
#         verbose_name = verbose_name_plural = "Notification"

# class Notification(models.Model):
#     SEND_TO_CHOICES = [
#         ('buyer', 'All Buyers'),
#         ('supplier', 'All Suppliers'),
#         ('all', 'All Users'),
#         ('single', 'Specific User'),
#     ]

#     recipient = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
#     send_to = models.CharField(max_length=20, choices=SEND_TO_CHOICES, default='single', null=True, blank=True)

#     title = models.CharField(max_length=255)
#     message = models.TextField()
#     is_read = models.BooleanField(default=False)
#     is_deleted = models.BooleanField(default=False)
#     created_at = models.DateTimeField(default=timezone.now)

#     class Meta:
#         ordering = ['-created_at']

#     def delete(self, using=None, keep_parents=False):
#         is_deleted = True



#     def __str__(self):
#         if self.send_to == "single" and self.recipient:
#             return f"To {self.recipient.username} - {self.title}"
#         else:
#             return f"{self.get_send_to_display()} - {self.title}"



class Notification(models.Model):
    SEND_TO_CHOICES = [
        ('buyer', 'All Buyers'),
        ('supplier', 'All Suppliers'),
        ('all', 'All Users'),
        ('single', 'Specific User'),
    ]

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications'
    )
    send_to = models.CharField(
        max_length=20, choices=SEND_TO_CHOICES, default='single', null=True, blank=True
    )

    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)   
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.save(update_fields=["is_deleted"])

    def __str__(self):
        if self.send_to == "single" and self.recipient:
            return f"To {self.recipient.username} - {self.title}"
        else:
            return f"{self.get_send_to_display()} - {self.title}"



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
        db_table = "dashboard_payment"


class StripePayment(models.Model):
    payment = models.OneToOneField("Payment", on_delete=models.CASCADE, related_name="stripe_payment", null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="stripe_payments")
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=True)

    # Stripe IDs
    stripe_payment_intent_id = models.CharField(max_length=150, blank=True, null=True)
    stripe_charge_id = models.CharField(max_length=150, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=150, blank=True, null=True)

    # Extra metadata
    stripe_signature = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural = "Stripe Payment"

    def __str__(self):
        return f"{self.user.username} - {self.amount} ({'Paid' if self.paid else 'Unpaid'})"


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
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='rfq_requests')
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
class RFQComment(models.Model):
    rfq = models.ForeignKey(RFQRequest, on_delete=models.CASCADE, related_name='comments')
    comment = models.TextField()
    admin_reply = models.TextField(blank=True, null=True)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_commission = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    commented_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    replied_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Comment by {self.commented_by.username} on RFQ #{self.rfq.id}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "RFQ Comment"
        verbose_name_plural = "RFQ Comments"



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
    data = models.TextField()
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
    reason = models.TextField(blank=True, null=True)
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

    @property
    def is_refunded(self):
        return self.return_status in ['return_completed', 'replace_completed']

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


class Contact(models.Model):
    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    display_phone = models.CharField(max_length=20, blank=True, null=True)
    display_email = models.EmailField(blank=True, null=True)
    display_address = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.full_name} - {self.subject}"


PERIOD_TYPE_CHOICES = [
    ('days', 'Days'),
    ('weeks', 'Weeks'),
    ('months', 'Months'),
]

class ShippingMethod(models.Model):
    country = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    
    order_subtotal_from = models.DecimalField(max_digits=10, decimal_places=2)
    order_subtotal_to = models.DecimalField(max_digits=10, decimal_places=2)
    
    price = models.DecimalField(max_digits=10, decimal_places=2)
    period = models.PositiveIntegerField()  
    period_type = models.CharField(max_length=10, choices=PERIOD_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.country} - {self.state} - {self.city} : {self.price}"

from decimal import Decimal
class Coupon(models.Model):
    COUPON_TYPE_CHOICES = [
        ('both', 'Both'),
        ('b2b', 'B2B Buyer Product'),
        ('retail', 'Retail Buyer Product'),
    ]

    DISCOUNT_TYPE_CHOICES = [
        ('amount', 'Amount'),
        ('percent', 'Percent'),
    ]
    coupon_type = models.CharField(
        max_length=20,
        choices=COUPON_TYPE_CHOICES,
        verbose_name="Coupon Type"
    )

    filter_by_orders_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Filter By Orders Count"
    )
    filter_by_orders_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Filter By Orders Amount"
    )
    client = models.ManyToManyField(
        User,
        related_name="applied_coupons",
        verbose_name="Client",
        blank=True
    )

    products = models.ManyToManyField(
        'Product',
        related_name="coupons",
        verbose_name="Search Product",
        blank=True
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Coupon Code"
    )

    discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Discount"
    )

    discount_type = models.CharField(
        max_length=10,
        choices=DISCOUNT_TYPE_CHOICES,
        verbose_name="Discount Type"
    )

    max_discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Max Discount"
    )

    minimum_purchase_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Minimum Purchase Amount"
    )

    count_of_use = models.PositiveIntegerField(
        default=1,
        verbose_name="Count Of Use"
    )
    start_datetime = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Start Date & Time"
    )

    end_datetime = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="End Date & Time"
    )
    can_be_used_with_promotions = models.BooleanField(
        default=False,
        verbose_name="Can be used with promotions"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_coupons"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def is_valid_now(self):
        """Check if coupon is currently active"""
        now = timezone.now()

        if not self.start_datetime or not self.end_datetime:
            return False

        return self.start_datetime <= now <= self.end_datetime

    def calculate_discount(self, order_total):
        """Return discount amount based on type."""
        if self.discount_type == 'percent':
            discount_value = order_total * (self.discount / Decimal('100'))
        else:
            discount_value = self.discount

        if discount_value > self.max_discount and self.max_discount > 0:
            discount_value = self.max_discount
        return discount_value

    def __str__(self):
        return f"{self.code} ({self.get_discount_type_display()})"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Coupon"
        verbose_name_plural = "Coupons"

PRODUCT_TYPE_CHOICES = [
    ('b2b', 'B2B'),
    ('b2c', 'B2C'),
]

class BuyXGetYPromotion(models.Model):
    product_type = models.CharField(max_length=10,choices=PRODUCT_TYPE_CHOICES)
    supplier = models.ManyToManyField('SupplierProfile', related_name='buyxgety_promotions')
    product = models.ManyToManyField('Product', related_name='buyxgety_products')
    
    buy = models.IntegerField()
    get = models.IntegerField()

    promotion_period = models.CharField( max_length=100, help_text="Promotion period (e.g., 01 Nov 2025 - 30 Nov 2025)")
    created_at = models.DateTimeField(auto_now_add=True) 
    status = models.CharField(
        max_length=10,
        choices=[('Active', 'Active'), ('Inactive', 'Inactive')],
        default='Inactive'
    )
    

    def __str__(self):
        suppliers = ", ".join(s.user.username for s in self.supplier.all())
        products = ", ".join(p.name for p in self.product.all())
        return f"{self.product_type.upper()} | Suppliers: {suppliers} | Products: {products} | Buy {self.buy} Get {self.get}"
    def save(self, *args, **kwargs):
        try:
         
            period = self.promotion_period.split(" - ")
            if len(period) == 2:
                start_date = timezone.datetime.strptime(period[0], "%d %b %Y").date()
                end_date = timezone.datetime.strptime(period[1], "%d %b %Y").date()
                now = timezone.now().date()

                if start_date <= now <= end_date:
                    self.status = 'Active'
                else:
                    self.status = 'Inactive'
        except Exception as e:

            self.status = 'Inactive'

        super().save(*args, **kwargs)
class BuyXGiftYPromotion(models.Model):
    product_type = models.CharField(max_length=10, choices=PRODUCT_TYPE_CHOICES)
    supplier = models.ManyToManyField('SupplierProfile', related_name='buyxgift_promotions')
    product = models.ManyToManyField('Product', related_name='buyxgift_products')
    giftproduct = models.ManyToManyField('Product', related_name='buyxgift_giftproducts')

    buy = models.IntegerField()
    gift = models.IntegerField()

    promotion_period = models.CharField(
        max_length=100,
        help_text="Promotion period (e.g., 01 Nov 2025 - 30 Nov 2025)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10,
        choices=[('Active', 'Active'), ('Inactive', 'Inactive')],
        default='Inactive'
    )

    def __str__(self):
        suppliers = ", ".join(s.user.username for s in self.supplier.all())
        products = ", ".join(p.name for p in self.product.all())
        return f"{self.product_type.upper()} | Suppliers: {suppliers} | Products: {products} | Buy {self.buy} Gift {self.gift}"

    def save(self, *args, **kwargs):
        try:
            period = self.promotion_period.split(" - ")
            if len(period) == 2:
                start_date = timezone.datetime.strptime(period[0], "%d %b %Y").date()
                end_date = timezone.datetime.strptime(period[1], "%d %b %Y").date()
                now = timezone.now().date()

                if start_date <= now <= end_date:
                    self.status = 'Active'
                else:
                    self.status = 'Inactive'
        except Exception:
            self.status = 'Inactive'

        super().save(*args, **kwargs)

class BasketPromotion(models.Model):
    product_type = models.CharField(max_length=10, choices=PRODUCT_TYPE_CHOICES)
    supplier = models.ManyToManyField('SupplierProfile', related_name='basket_promotions')
    product = models.ManyToManyField('Product', related_name='basket_products')
    promotion_period = models.CharField(max_length=100, help_text="Promotion period (e.g., 01 Nov 2025 - 30 Nov 2025)")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10,
        choices=[('Active', 'Active'), ('Inactive', 'Inactive')],
        default='Inactive'
    )

    time_limit = models.CharField(max_length=50, blank=True, null=True)
    title_en = models.CharField(max_length=255, blank=True, null=True)
    description_en = models.TextField(blank=True, null=True)
    main_image = models.ImageField(upload_to='promotions/main_images/', blank=True, null=True)

    def __str__(self):
        return self.title_en or "Untitled Basket Promotion"

    def save(self, *args, **kwargs):
        try:
            period = self.promotion_period.split(" - ")
            if len(period) == 2:
                start = timezone.datetime.strptime(period[0].strip(), "%d %b %Y").date()
                end = timezone.datetime.strptime(period[1].strip(), "%d %b %Y").date()
                today = timezone.now().date()
                self.status = 'Active' if start <= today <= end else 'Inactive'
        except:
            self.status = 'Inactive'
        super().save(*args, **kwargs)

class SupplierCommission(models.Model):
    supplier = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="supplier_commissions",
        help_text="Select the supplier to whom this commission applies."
    )
    commission_b2b = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Commission percentage for B2B sales."
    )
    commission_b2c = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Commission percentage for B2C sales."
    )

    type_b2b = models.CharField(
        max_length=10,
        choices=[("include", "Include"), ("exclude", "Exclude")],
        default="exclude",
        help_text="Include or exclude commission for B2B sales."
    )
    type_b2c = models.CharField(
        max_length=10,
        choices=[("include", "Include"), ("exclude", "Exclude")],
        default="exclude",
        help_text="Include or exclude commission for B2C sales."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.supplier.username} - B2B: {self.commission_b2b}%, B2C: {self.commission_b2c}%"

    class Meta:
        verbose_name = "Supplier Commission"
        verbose_name_plural = "Supplier Commissions"
        ordering = ['-created_at']

class VacationRequest(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    supplier = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vacation_requests')
    type = models.CharField(max_length=50, default='vacation')  # In case you add more types later
    reason = models.TextField(blank=True, null=True)
    from_date = models.DateField()
    to_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.supplier.username} - {self.type} ({self.status})"
    
class TopSupplier(models.Model):
    supplier = models.ForeignKey(SupplierProfile, on_delete=models.CASCADE, related_name='to_suppliers')
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Top Supplier"
        verbose_name_plural = "Top Suppliers"

    def __str__(self):
        return f"{self.supplier.company_name} - {self.order}"

class Bank(models.Model):
    name = models.CharField(max_length=150, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return self.name
class OriginCountry(models.Model):
    name_en = models.CharField(max_length=100, unique=True)
    iso = models.CharField(max_length=10, unique=True)      
    phone_prefix = models.CharField(max_length=10)         
    order = models.PositiveIntegerField(default=0)          
    currency = models.CharField(max_length=20, blank=True, null=True)  
    is_default = models.BooleanField(default=False)      
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)

    class Meta:
        ordering = ['order', 'name_en']

    def __str__(self):
        return self.name_en
class Region(models.Model):
    name_en = models.CharField(max_length=150)
    country = models.CharField(max_length=150) 
    created_at = models.DateTimeField(auto_now_add=True,blank=True, null=True)

    def __str__(self):
        return f"{self.name_en} ({self.country})"

class Currency(models.Model):
    name_en = models.CharField(max_length=100)
    code_en = models.CharField(max_length=10)
    rate = models.DecimalField(max_digits=10, decimal_places=4)
    country = models.CharField(max_length=100)  
    created_at = models.DateTimeField(auto_now_add=True,blank=True, null=True)

    status = models.CharField(
        max_length=10,
        choices=[('Active', 'Active'), ('Inactive', 'Inactive')],
        default='Active'
    )

    set_as_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name_en

class ReturnReason(models.Model):
    reason_en = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True,blank=True, null=True)

    def __str__(self):
        return self.reason_en
class Department(models.Model):
    name_en = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True,blank=True, null=True)

    def __str__(self):
        return self.name_en
class SupplierType(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    )

    name_en = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True,blank=True, null=True)

    def __str__(self):
        return self.name_en
class AddressType(models.Model):
    CLIENT_TYPE = (
        ('b2b','B2b'),
        ('b2c','B2c'),
    )
    name_en = models.CharField(max_length=255)
    client_type = models.CharField(max_length=10,choices=CLIENT_TYPE,default='b2b')
    created_at = models.DateTimeField(auto_now_add=True,blank=True, null=True)

    def __str__(self):
        return self.name_en

class Unit(models.Model):
    STATUS_CHOICES = (
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    )

    name = models.CharField(max_length=100, verbose_name="Name (En)")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Active')
    created_at = models.DateTimeField(auto_now_add=True,blank=True, null=True)

    def __str__(self):
        return self.name
class DeliveryTime(models.Model):
    STATUS_CHOICES = (
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    )

    name = models.CharField(max_length=100, verbose_name="Name (En)")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Active')
    created_at = models.DateTimeField(auto_now_add=True,blank=True, null=True)

    def __str__(self):
        return self.name
class ReturnTime(models.Model):
    STATUS_CHOICES = (
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    )

    name = models.CharField(max_length=100, verbose_name="Name (En)")
    value = models.CharField(max_length=100, verbose_name="Value")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Active')
    created_at = models.DateTimeField(auto_now_add=True,blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.value})"

class StandingTime(models.Model):
    STATUS_CHOICES = (
        ('Active','Active'),
        ('Inactive','Inactive'),
    )
    name = models.CharField(max_length=100, verbose_name="Name (En)")
    value = models.CharField(max_length=100,verbose_name="Value")
    status = models.CharField(max_length=10,choices=STATUS_CHOICES , default='Active')
    created_at = models.DateTimeField(auto_now_add=True,blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.value})"
          
class Warranty(models.Model):
        STATUS_CHOICES = (
            ('Active','Active'),
            ('Inactive','Inactive'),
        )

        name = models.CharField(max_length=100,verbose_name="Name(En)")
        status = models.CharField(max_length=10,choices=STATUS_CHOICES,default='Active')
        created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

        def __str__(self):
            return self.name

class SplashScreen(models.Model):
    LANGUAGE_CHOICES = [
        ('gu', 'Gujarati'),
        ('hi', 'Hindi'),
        ('en', 'English'),
    ]

    screen_image = models.ImageField(upload_to='splash_screens/', verbose_name="Upload Screen Image")
    screen_text = models.TextField(verbose_name="Upload Screen Text", blank=True, null=True)
    screen_title = models.CharField(max_length=200, verbose_name="Screen Title")
    screen_body = models.TextField(verbose_name="Screen Body")
    screen_order = models.PositiveIntegerField(verbose_name="Screen Order")
    screen_language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, verbose_name="Screen Language")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        ordering = ['screen_order']
        verbose_name = "Splash Screen"
        verbose_name_plural = "Splash Screens"

    def __str__(self):
        return f"{self.screen_title} ({self.get_screen_language_display()})"

class Staticcontents(models.Model):
    name_en = models.CharField(max_length=255, verbose_name="Name En *")
    description_en = models.TextField(verbose_name="Description EN *")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        verbose_name = "Website Metadata"
        verbose_name_plural = "Website Metadata"

    def __str__(self):
        return self.name_en
class SocialLinks(models.Model):
    title = models.CharField(max_length=255, verbose_name="Title *")
    link = models.URLField(max_length=500, verbose_name="Link *")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        verbose_name = "Social Link"
        verbose_name_plural = "Social Links"

    def __str__(self):
        return self.title

class FaqForm(models.Model):
    title_en = models.CharField("Title En", max_length=255, blank=False, null=False)
    description_en = models.TextField("Description En", blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return self.title_en

    class Meta:
        verbose_name = "FAQ Form"
        verbose_name_plural = "FAQ Forms"
        ordering = ["title_en"]

class AdminUser(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('sub admin', 'Sub Admin'),
      
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)

    def __str__(self):
        return self.user.username
class DynamicInput(models.Model):
    FIELD_TYPES = [
        ('text', 'Text'),
        ('checkbox', 'Checkbox'),
        ('select', 'Select'),
    ]

    form_name = models.CharField(max_length=100) 
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    title_en = models.CharField(max_length=200)
    required = models.BooleanField(default=False)
    status = models.BooleanField(default=True)  
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.title_en} ({self.field_type})"

class FormControl(models.Model):
    form = models.CharField(max_length=100)    
    name = models.CharField(max_length=255)     
    required = models.BooleanField(default=True) 
    status = models.BooleanField(default=True) 
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.form} - {self.name}"

class Catalog(models.Model):
    key = models.CharField(max_length=255, unique=True)   
    description = models.TextField() 
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return self.key

class Configuration(models.Model):
    key = models.CharField(max_length=255, unique=True)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return self.key

class SMSConfiguration(models.Model):
    PROVIDER_CHOICES = (
        ('twilio', 'Twilio'),
    )

    name = models.CharField(
        max_length=100,
        choices=PROVIDER_CHOICES,
        unique=True
    )

    sms_sender = models.CharField(max_length=200, verbose_name="SMS Sender Name / Mobile Number")
    sms_auth_token = models.CharField(max_length=200, verbose_name="SMS Auth Token")
    sms_account_sid = models.CharField(max_length=200, verbose_name="SMS Account SID")

    status = models.BooleanField(default=False)  
    created_at = models.DateTimeField(auto_now_add=True) 
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Theme(models.Model):
    THEME_TYPE_CHOICES = (
        ('text', 'Text'),
        ('image', 'Image'),
        ('icon', 'Icon'),
        ('theme', 'Theme'),
    )

    key = models.CharField(max_length=100, unique=True, help_text="Unique key for the theme")
    description = models.TextField(blank=True, help_text="Description of the theme")
    value = models.CharField(max_length=200, blank=True, help_text="Value associated with the theme")
    image = models.ImageField(upload_to='theme_images/', blank=True, null=True, help_text="Image for the theme")
    type = models.CharField(max_length=50, choices=THEME_TYPE_CHOICES, default='custom', help_text="Type of the theme")
    created_at = models.DateTimeField(auto_now_add=True) 
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key
class APIControls(models.Model):
    portal = models.CharField(max_length=100)
    api_name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),

        ],
        default='active'
    )

    def __str__(self):
        return f"{self.portal} - {self.api_name}"

class SEOSettings(models.Model):

    TYPE_CHOICES = (
        ('text', 'Text'),
    )

    key = models.CharField(max_length=200, unique=True)
    description = models.CharField(max_length=300, blank=True, null=True)
    value = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='seo_images/', blank=True, null=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='text')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return self.key

class PaymentSettings(models.Model):
    key = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    status = models.CharField(
        max_length=10,
        choices=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
        ],
        default='inactive'
    )

    def __str__(self):
        return f"{self.key} - {self.status}"
    
class UserActivityLog(models.Model):
    class ActionType(models.TextChoices):
        CREATED = "created", "Created"
        DELETED = "deleted", "Deleted"
        LOGGEDIN = "logged in", "Logged In"
        LOGGEDOUT = "logged out", "Logged Out"
        PASSWORDCHANGE = "password change", "Password Change"
        FAILED = "failed", "Failed"
        UPDATED = "updated", "Updated"
        PURCHASE = "purchase", "Purchase"
        REFUND = "payment refund", "Payment Refund"
        CANCELED = "canceled subscription", "Canceled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_activity'
    )
    actions = models.CharField(
        max_length=50,
        choices=ActionType.choices,
        blank=True,
        null=True
    )
    description = models.TextField(blank=True, null=True)
    amount = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def delete(self, *args, **kwargs):
        """Soft delete by marking as deleted and setting the deletion timestamp."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural = "User Activity Logs"


class AdminActivityLog(models.Model):
    class ActionType(models.TextChoices):
        CREATED = "created", "Created"
        DELETED = "deleted", "Deleted"
        LOGGEDIN = "logged in", "Logged In"
        LOGGEDOUT = "logged out", "Logged Out"
        PASSWORDCHANGE = "password change", "Password Change"
        FAILED = "failed", "Failed"
        UPDATED = "updated", "Updated"
        PURCHASE = "purchase", "Purchase"
        REFUND = "payment refund", "Payment Refund"
        CANCELED = "canceled subscription", "Canceled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_activity_logs"   
    )
    actions = models.CharField(max_length=50, choices=ActionType.choices, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    amount = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    class Meta: 
        ordering = ["-created_at"]
        verbose_name = "Admin Activity Log"
        verbose_name_plural = "Admin Activity Logs"

class UserLogs(models.Model):
    class ActionType(models.TextChoices):
        CREATED = "created", "Created"
        DELETED = "deleted", "Deleted"
        LOGGEDIN = "logged in", "Logged In"
        LOGGEDOUT = "logged out", "Logged Out"
        PASSWORDCHANGE = "password change", "Password Change"
        FAILED = "failed", "Failed"
        UPDATED = "updated", "Updated"
        PURCHASE = "purchase", "Purchase"
        REFUND = "payment refund", "Payment Refund"
        CANCELED = "canceled subscription", "Canceled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_logs'  
    )

    actions = models.CharField(max_length=50, choices=ActionType.choices, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    amount = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural = "User Logs"

class ChatRoom(models.Model):
    CHAT_TYPE_CHOICES = [
        ('supplier_admin', 'Supplier-Admin'),
        ('buyer_supplier', 'Buyer-Supplier'),
    ]
    
    supplier = models.ForeignKey(User, on_delete=models.CASCADE, related_name='supplier_rooms')
    buyer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='buyer_rooms',
        null=True, blank=True
    )  
    admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_rooms', null=True, blank=True)
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='chat_rooms', null=True, blank=True)
    chat_type = models.CharField(max_length=20, choices=CHAT_TYPE_CHOICES, default='supplier_admin')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        if self.chat_type == 'buyer_supplier':
            return f"Chat: {self.buyer.username if self.buyer else 'Buyer'} - {self.supplier.username} (Product: {self.product.name if self.product else 'N/A'})"
        else:
            return f"Chat: {self.supplier.username} - {self.admin.username if self.admin else 'Admin'}"
        
class ChatMessage(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.sender.username}: {self.message[:50]}"




class UserCardsAndSubscriptions(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_payment_method_id = models.CharField(max_length=500, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=500, blank=True, null=True)    
    active_subscription_price_id = models.CharField(max_length=255, blank=True, null=True)
    subscription_status = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-updated_at"]
        verbose_name = verbose_name_plural ="Customer Cards And Subscriptions"


class UserBillingAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    customer_name = models.CharField(verbose_name="Card Holder Name", max_length=128, null=True, blank=True)
    customer_address1 = models.CharField(max_length=255, null=True, blank=True)
    customer_address2 = models.CharField(max_length=255, null=True, blank=True)
    customer_city = models.CharField(max_length=128, null=True, blank=True)
    customer_state = models.CharField(max_length=128, null=True, blank=True)
    customer_postal_code = models.CharField(max_length=64, null=True, blank=True)
    customer_country = models.CharField(max_length=128, null=True, blank=True)
    customer_country_code = models.CharField(max_length=10, null=True, blank=True)

    is_old = models.BooleanField(default=False)
    old_card = models.TextField(null=True, blank=True)

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text="Date when card was deleted")
    deleted_via_api = models.CharField(
        max_length=20, 
        null=True, 
        blank=True,
        choices=[
            ('NEW_API', 'PaymentMethod (New API)'),
            ('OLD_API', 'Source (Old API)'),
        ],
        help_text="Which Stripe API was used to delete the card"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def delete(self, *args, **kwargs):
        """Override delete method to implement soft delete"""
        self.is_deleted = True
        self.save()


    def __str__(self):
        return f"{self.user} Billing Address"

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = verbose_name_plural ="Customer Billing Address"

    @property
    def old_card_info(self):
        try:
            last_card = json.loads(self.old_card.replace("\'", "\""))
            return f"{last_card['last4']}-{last_card['exp_month']}/{last_card['exp_year']}"
        except:
            return "Not Available"
        
class CustomerPayment(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    stripe_charge_id = models.CharField(max_length=128)
    amount = models.IntegerField()
    is_refunded = models.BooleanField(default=False)
    is_bonus = models.BooleanField(default=False)
    is_autotop = models.BooleanField(default=False)
    is_subscription = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    user_refund_notes = models.TextField(null=True,blank=True)
    admin_refund_notes = models.TextField(null=True,blank=True)
    refund_info = models.JSONField(verbose_name="Refund Info", default=dict,null=True,blank=True)
    receipt_url = models.URLField(max_length=512, null=True, blank=True)
    refund_pdf_url = models.URLField(max_length=512, null=True, blank=True)
    
    def __str__(self):
        return f"{self.user} Payment"

    class Meta:
        # ordering = ["-timestamp"]
        verbose_name = verbose_name_plural ="Customer Payment"
        db_table = "dashboard_customer_payment"

    
    
      

    
   