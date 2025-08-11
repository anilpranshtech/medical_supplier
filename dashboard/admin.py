from django.contrib import admin
from stripe import PaymentMethod

from dashboard.models import *


@admin.register(RetailProfile)
class RetailProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'profile_picture', 'phone', 'current_position', 'workplace', 'nationality', 'residency', 'country_code', 'speciality')


@admin.register(WholesaleBuyerProfile)
class WholesaleBuyerProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'profile_picture', 'phone', 'company_name', 'gst_number', 'department', 'purchase_capacity')


@admin.register(SupplierProfile)
class SupplierProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'profile_picture', 'phone', 'company_name', 'license_number', 'is_verified')

@admin.register(Product)
class ProductProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description', 'price')

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'image', 'is_main')

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at')

@admin.register(ProductSubCategory)
class ProductSubCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'category', 'name', 'created_at')

@admin.register(Question)
class Quetions(admin.ModelAdmin):
    list_display = ['id', 'user', 'text']



@admin.register(ProductLastCategory)
class ProductLastCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'sub_category', 'name', 'created_at')

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'order_id', 'status', 'user', 'payment', 'phone_number')
    list_filter = ('status',)

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'order_by', 'order_to', 'status', 'payment_type', 'payment_status')
    list_filter = ('status', 'payment_status')

@admin.register(CartProduct)
class CartProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'quantity')

@admin.register(WishlistProduct)
class WishlistProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'quantity')

@admin.register(RatingReview)
class RatingReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'rating', 'review')
    list_filter = ('rating',)

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

@admin.register(BankTransferPayment)
class BankTransferPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'amount', 'verified_by_admin', 'created_at', 'proof_image')
    list_filter = ('verified_by_admin', 'created_at')
    search_fields = ('id', 'user__username', 'user__email')
    list_editable = ('verified_by_admin',)
    readonly_fields = ('created_at',)
    fieldsets = (
        (None, {
            'fields': ('user', 'name', 'amount', 'verified_by_admin')
        }),
        ('Bank Transfer Details', {
            'fields': ('admin_notes', 'proof_image')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )

@admin.register(CustomerBillingAddress)
class CustomerBillingAddressAdmin(admin.ModelAdmin):
    list_display = ('id','user', 'customer_name', 'is_default', 'is_deleted', 'created_at', 'updated_at')

@admin.register(RoleRequest)
class RoleRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'requested_role', 'status', 'created_at')
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

@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'current_position', 'workplace', 'nationality', 'residency', 'country_code', 'speciality', 'phone_number')

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('id', 'conference_link', 'speaker_name', 'conference_at', 'duration', 'venue')
    list_filter = ('conference_at', 'duration', 'venue')

@admin.register(Nationality)
class NationalityAdmin(admin.ModelAdmin):
    list_display = ('id', 'country', 'created_at')
    list_filter = ('country', 'created_at')

@admin.register(Residency)
class ResidencyAdmin(admin.ModelAdmin):
    list_display = ('id', 'country', 'created_at')
    list_filter = ('country', 'created_at')

@admin.register(CountryCode)
class CountryCodeAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'country', 'created_at')
    list_filter = ('country', 'created_at')

@admin.register(Speciality)
class SpecialityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at')
    list_filter = ('name', 'created_at')

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'client_type', 'buyer_type', 'cost', 'period', 'is_active')
    list_filter = ('client_type', 'buyer_type', 'is_active')
    search_fields = ('name', 'description')
    ordering = ('client_type', 'buyer_type', 'name')
    list_editable = ('is_active',)
    inlines = []

    def get_inlines(self, request, obj=None):
        return [PlatformPlanInline, FeatureInline] if obj else []


class PlatformPlanInline(admin.TabularInline):
    model = PlatformPlan
    extra = 1


class FeatureInline(admin.TabularInline):
    model = Feature.plans.through
    extra = 1
    verbose_name = "Feature"
    verbose_name_plural = "Features"


@admin.register(PlatformPlan)
class PlatformPlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'subscription_plan', 'platform', 'platform_plan_id')
    list_filter = ('platform',)
    search_fields = ('subscription_plan__name', 'platform_plan_id')


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'plan', 'platform', 'is_active', 'subscription_date', 'platform_plan_id')
    list_filter = ('platform', 'is_active')
    search_fields = ('user__email', 'plan__name')
    readonly_fields = ('subscription_date',)
    ordering = ('-subscription_date',)


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'status', 'cost')
    list_filter = ('status',)
    search_fields = ('name', 'cost')


@admin.register(StripeSubscriptionMetadata)
class StripeSubscriptionMetadataAdmin(admin.ModelAdmin):
    list_display = ('id', 'subscription_plan', 'price', 'price_id', 'plan_type', 'plan_duration', 'created_at')
    list_filter = ('plan_type', 'plan_duration')
    search_fields = ('subscription_plan__name', 'price_id')
    readonly_fields = ('created_at', 'updated_at')


# @admin.register(SubscriptionPlan)
# class SubscriptionPlanAdmin(admin.ModelAdmin):
#     list_display = ('id', 'name', 'client_type', 'buyer_type', 'period', 'cost', 'ios_plan_id', 'android_plan_id')
#     list_filter = ('client_type', 'buyer_type', 'period')
#     search_fields = ('name', 'description', 'ios_plan_id', 'android_plan_id')
#     fieldsets = (
#         ('Basic Information', {
#             'fields': ('name', 'description', 'period', 'cost')
#         }),
#         ('Client Type', {
#             'fields': ('client_type', 'buyer_type')
#         }),
#         ('Platform IDs', {
#             'fields': ('ios_plan_id', 'android_plan_id'),
#             'classes': ('collapse',)
#         }),
#     )
#
# @admin.register(UserSubscription)
# class UserSubscriptionAdmin(admin.ModelAdmin):
#     list_display = ('id', 'user', 'plan', 'platform', 'subscription_date', 'is_active')
#     list_filter = ('platform', 'is_active', 'plan__client_type', 'plan__buyer_type')
#     search_fields = ('user__email', 'user__username', 'plan__name')
#     readonly_fields = ('subscription_date', 'platform_plan_id')
#     date_hierarchy = 'subscription_date'
#
#     fieldsets = (
#         ('Subscription Info', {
#             'fields': ('user', 'plan', 'is_active')
#         }),
#         ('Platform Details', {
#             'fields': ('platform', 'platform_plan_id', 'subscription_date')
#         }),
#     )
#
#
# @admin.register(Feature)
# class FeatureAdmin(admin.ModelAdmin):
#     list_display = ('id', 'name', 'status', 'cost')
#     list_filter = ('name', 'status', 'cost')
#
#
# @admin.register(StripeSubscriptionMetadata)
# class StripeSubscriptionsAdmin(admin.ModelAdmin):
#     list_display = ('id', 'name', 'price', 'price_id', 'plan_type')
#     list_filter = ('name', 'plan_type')