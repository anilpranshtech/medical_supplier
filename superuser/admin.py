from django.contrib import admin
from django.contrib.auth.models import Permission

from superuser.models import StaticPages


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'codename', 'content_type')
    search_fields = ('name', 'codename')
    list_filter = ('content_type',)

@admin.register(StaticPages)
class StaticPagesAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', "is_active", 'created', 'updated',)
