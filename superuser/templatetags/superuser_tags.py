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


@register.simple_tag
def tag_user_permissions_list(user):
    if user.is_authenticated:
        # print('permission -----------', user.get_all_permissions())
        return user.get_all_permissions()
    return []


@register.filter
def tag_user_has_permission(user, perm_codename):
    if user.is_authenticated:
        # print('user permission -----------', user.has_perm(perm_codename))
        return user.has_perm(perm_codename)
    return False

@register.filter
def tag_format_permission_name(value):
    if value.lower().startswith('can '):
        value = value[4:]

    value = value.replace("change user", "Update User")

    # Handle RatingReview → Rating/Review
    value = value.replace("rating review", "Rating/Review")

    # Handle RFQRequest → RFQ Request (if needed)
    value = value.replace("Rfqrequest", "RFQ request")
    value = value.replace("Rfq Request", "RFQ request")


    return value.title()


@register.filter
def tag_format_model_name(model_name):
    format_model_name = model_name.title()
    if model_name == 'ratingreview': format_model_name = "Rating/Review"
    elif model_name == 'rfqrequest': format_model_name = "RFQ request"

    return format_model_name
