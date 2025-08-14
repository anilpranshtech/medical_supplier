from django.contrib import admin
from django.contrib.auth.models import Permission


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'codename', 'content_type')
    search_fields = ('name', 'codename')
    list_filter = ('content_type',)