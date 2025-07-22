from django import template
from django.contrib.auth import get_user_model

from dashboard.models import RetailProfile, WholesaleBuyerProfile, SupplierProfile

User = get_user_model()
register = template.Library()


@register.simple_tag
def tag_total_users():
    res_ = User.objects.count()
    return f"{res_:,}"

@register.simple_tag
def tag_total_active_users():
    res_ = User.objects.filter(
        is_active=True
    ).count()
    return f"{res_:,}"

@register.simple_tag
def tag_total_retailer():
    res_ = RetailProfile.objects.count()
    return f"{res_:,}"

@register.simple_tag
def tag_total_suppliers():
    res_ = SupplierProfile.objects.count()
    return f"{res_:,}"


@register.simple_tag
def tag_total_wholesaler():
    res_ = WholesaleBuyerProfile.objects.count()
    return f"{res_:,}"
