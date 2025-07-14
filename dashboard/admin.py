from django.contrib import admin
from stripe import PaymentMethod

from dashboard.models import *


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
    list_display = ('id', 'name', 'description', 'price')

admin.site.register(ProductImage)
admin.site.register(ProductCategory)
admin.site.register(ProductSubCategory)
admin.site.register(ProductLastCategory)
admin.site.register(Brand)
admin.site.register(Orders)
admin.site.register(CartProduct)
admin.site.register(WishlistProduct)



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

@admin.register(RoleRequest)
class RoleRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'requested_role', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    actions = ['approve_requests']

    def approve_requests(self, request, queryset):
        for role_request in queryset:
            if role_request.status == 'pending':
                role_request.status = 'approved'
                role_request.save()
                user = role_request.user
                if role_request.requested_role == 'supplier':
                    SupplierProfile.objects.get_or_create(user=user)
                elif role_request.requested_role == 'retailer':
                    RetailProfile.objects.get_or_create(user=user)
                elif role_request.requested_role == 'wholesaler':
                    WholesaleBuyerProfile.objects.get_or_create(user=user)
        self.message_user(request, "Selected requests have been approved.")
    approve_requests.short_description = "Approve selected requests"


@admin.register(RFQRequest)
class RFQRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'product', 'requested_by', 'quoted_by', 'quoted_price', 'status', 'created_at'
    )
    list_filter = ('status', 'created_at')
    search_fields = ('product__name', 'requested_by__username', 'company_name', 'message')

    fieldsets = (
        ('RFQ Details', {
            'fields': ('requested_by', 'product', 'quantity', 'company_name', 'message', 'attached_file', 'expected_delivery_date')
        }),
        ('Quotation Details', {
            'fields': ('quoted_by', 'quoted_price', 'quote_attached_file', 'quote_delivery_date', 'supplier_notes', 'quote_sent_at')
        }),
        ('Meta', {
            'fields': ('status', 'email_sent', 'created_at', 'updated_at')
        }),
    )
    readonly_fields = ('created_at', 'updated_at', 'quote_sent_at')