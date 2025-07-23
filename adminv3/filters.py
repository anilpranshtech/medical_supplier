from django.db.models import Q
from django.contrib.auth.models import User

from dashboard.models import Product


def QS_filter_user(filter_dict={}):
    search_by = filter_dict.get('search_by', '').strip()
    account_status = filter_dict.get('account_status', 'all')  # active/inactive
    account_role = filter_dict.get('account_role', 'all')  # administrator/staff/users
    user_type = filter_dict.get('account_type', 'all')  # retailer/wholesaler/supplier
    sort_by = filter_dict.get('sort_by', 'desc_created')
    permission_group = filter_dict.get('permission_group', 'all')

    filters = Q()

    if search_by:
        filters &= (
            Q(username__icontains=search_by) |
            Q(email__icontains=search_by) |
            Q(first_name__icontains=search_by) |
            Q(last_name__icontains=search_by)
        )

    if account_status == 'active':
        filters &= Q(is_active=True)
    elif account_status == 'inactive':
        filters &= Q(is_active=False)

    if account_role == 'administrator':
        filters &= Q(is_superuser=True)
    elif account_role == 'staff':
        filters &= Q(is_staff=True, is_superuser=False)
    elif account_role == 'users':
        filters &= Q(is_staff=False, is_superuser=False)

    if user_type == 'retailer':
        filters &= Q(retailprofile__isnull=False)
    elif user_type == 'wholesaler':
        filters &= Q(wholesalebuyerprofile__isnull=False)
    elif user_type == 'supplier':
        filters &= Q(supplierprofile__isnull=False)

    if permission_group and permission_group != 'all':
        try:
            group_id = int(permission_group)
            filters &= Q(groups__id=group_id)
        except ValueError:
            pass

    ordering = '-date_joined' if sort_by == 'desc_created' else 'date_joined'

    return User.objects.filter(filters).order_by(ordering)


def QS_Products_filter(filter_dict={}):
    search_by = filter_dict.get("search_by")
    product_status = filter_dict.get("product_status")
    account_type = filter_dict.get("account_type")
    sort_by = filter_dict.get("sort_by", "desc_created")

    qs = Product.objects.all()

    if search_by:
        qs = qs.filter(
            Q(name__icontains=search_by) |
            Q(keywords__icontains=search_by) |
            Q(created_by__email__icontains=search_by) |
            Q(description__icontains=search_by)
        )

    if product_status and product_status != "all":
        if product_status == "published":
            qs = qs.filter(is_active=True)
        elif product_status == "inactive":
            qs = qs.filter(is_active=False)
        elif product_status == "scheduled":
            qs = qs.filter(is_active=False, ask_admin_to_publish=True)

    if account_type and account_type != "all":
        qs = qs.filter(category__name=account_type)

    if sort_by == "asc_created":
        qs = qs.order_by("created_at")
    else:
        qs = qs.order_by("-created_at")

    return qs
