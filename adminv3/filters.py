from django.db.models import Q
from django.contrib.auth.models import User

from adminv3.utils import util_get_date_range
from dashboard.models import Product, Order


def QS_filter_user(filter_dict={}):
    search_by = filter_dict.get('search_by', '').strip()
    account_status = filter_dict.get('account_status', 'all')  # active/inactive
    account_role = filter_dict.get('account_role', 'all')  # administrator/staff/users
    user_type = filter_dict.get('account_type', 'all')  # retailer/wholesaler/supplier
    sort_by = filter_dict.get('sort_by', 'desc_created')
    permission_group = filter_dict.get('permission_group', 'all')
    created_date = filter_dict.get('created_date', None)

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

    if created_date:
        start_date, end_date = util_get_date_range(created_date)
        if start_date and end_date:
            filters &= Q(date_joined__range=(start_date, end_date))

    ordering = '-date_joined' if sort_by == 'desc_created' else 'date_joined'

    return User.objects.filter(filters).order_by(ordering)


def QS_Products_filter(filter_dict={}):
    search_by = filter_dict.get("search_by")
    product_status = filter_dict.get("product_status")
    account_type = filter_dict.get("account_type")
    sort_by = filter_dict.get("sort_by", "desc_created")
    created_date = filter_dict.get('created_date', None)


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

    if created_date:
        start_date, end_date = util_get_date_range(created_date)
        if start_date and end_date:
            qs = qs.filter(created_at__range=(start_date, end_date))

    return qs


def QS_orders_filters(filter_dict={}):

    order_status = filter_dict.get("order_status")
    payment_status = filter_dict.get("payment_status")
    search_by = filter_dict.get("search_by")
    sort_by = filter_dict.get("sort_by")
    payment_type = filter_dict.get("payment_type")
    filter_created_date = filter_dict.get('created_date', None)



    qs = Order.objects.all()

    if search_by:
        qs = qs.filter(
            Q(order_id__icontains=search_by) |
            Q(user__email__icontains=search_by) |
            Q(phone_number__icontains=search_by)
        )

    if order_status and order_status != "all":
        qs = qs.filter(status=order_status)


    if payment_status and payment_status != "all":
        if payment_status == "paid":
            qs = qs.filter(payment__paid=True)
        elif payment_status == "unpaid":
            qs = qs.filter(Q(payment__isnull=True) | Q(payment__paid=False))


    if payment_type and payment_type != 'all':
        if payment_type == "cod":
            qs = qs.filter(payment__payment_method="cod")
        elif payment_type == "stripe":
            qs = qs.filter(payment__payment_method="stripe")
        elif payment_type == "razorpay":
            qs = qs.filter(payment__payment_method="razorpay")


    if sort_by == "asc_created":
        qs = qs.order_by("created_at")
    elif sort_by == "desc_created":
        qs = qs.order_by("-created_at")
    else:
        qs = qs.order_by("-created_at")

    if filter_created_date:
        start_date, end_date = util_get_date_range(filter_created_date)

        if start_date and end_date:
            qs = qs.filter(created_at__range=(start_date, end_date))

    return qs