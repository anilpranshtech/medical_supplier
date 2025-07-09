from django.contrib import admin
from stripe import PaymentMethod

from dashboard.models import *


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'current_position', 'workplace')


@admin.register(MedicalSupplierProfile)
class MedicalSupplierProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'profile_picture', 'user', 'workplace', 'nationality', 'created_at')


@admin.register(CorporateProfile)
class CorporateProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'company_name', 'department')


@admin.register(RetailProfile)
class RetailProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'profile_picture', 'age', 'medical_needs')


@admin.register(WholesaleBuyerProfile)
class WholesaleBuyerProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'profile_picture', 'company_name', 'gst_number', 'department', 'purchase_capacity')


@admin.register(SupplierProfile)
class SupplierProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'profile_picture', 'company_name', 'license_number', 'is_verified')

@admin.register(Product)
class ProductProfileAdmin(admin.ModelAdmin):
    list_display = ('id','name', 'description', 'price')

admin.site.register(ProductImage)
admin.site.register(ProductCategory)
admin.site.register( ProductSubCategory)
admin.site.register(ProductLastCategory)
admin.site.register(Brand)
admin.site.register(Orders)



@admin.register(DeliveryPartner)
class DeliveryPartnerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'tracking_url_template', 'support_email', 'phone_number', 'is_active', 'created_at')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id','name', 'amount', 'payment_method', 'paid', 'created_at')
    list_filter = ('paid', 'created_at')

@admin.register(StripePayment)
class StripePaymentAdmin(admin.ModelAdmin):
    list_display = ('id','name', 'amount', 'paid', 'created_at')
    list_filter = ('paid', 'created_at')

@admin.register(RazorpayPayment)
class RazorpayPaymentAdmin(admin.ModelAdmin):
    list_display = ('id','name', 'amount', 'paid', 'created_at')
    list_filter = ('paid', 'created_at')

@admin.register(CODPayment)
class CODPaymentAdmin(admin.ModelAdmin):
    list_display = ('id','name', 'amount', 'paid', 'created_at')
    list_filter = ('paid', 'created_at')

@admin.register(CustomerBillingAddress)
class CustomerBillingAddressAdmin(admin.ModelAdmin):
    list_display = ('id','user', 'customer_name', 'is_deleted', 'created_at', 'updated_at')

