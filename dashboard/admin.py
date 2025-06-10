from django.contrib import admin

from dashboard.views import DoctorProfile, MedicalSupplierProfile, CorporateProfile


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'current_position', 'workplace')


@admin.register(MedicalSupplierProfile)
class MedicalSupplierProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'workplace', 'nationality')


@admin.register(CorporateProfile)
class CorporateProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'company_name', 'department')
