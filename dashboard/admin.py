from django.contrib import admin

from dashboard.models import DoctorProfile, MedicalSupplierProfile, CorporateProfile, RetailProfile, WholesaleBuyerProfile, SupplierProfile, Product,ProductImage


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
    list_display = ('name', 'description', 'price')

@admin.register(ProductImage)
class ProductImagesAdmin(admin.ModelAdmin):
    list_display = ('image',)
