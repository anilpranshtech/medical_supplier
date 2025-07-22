from django.db.models import Q
from django.contrib.auth.models import User

def QS_filter_user(filter_dict={}):
    search_by = filter_dict.get('search_by', '').strip()
    account_status = filter_dict.get('account_status', 'all')  # active/inactive
    account_role = filter_dict.get('account_role', 'all')  # administrator/staff/users
    user_type = filter_dict.get('account_type', 'all')  # retailer/wholesaler/supplier
    sort_by = filter_dict.get('sort_by', 'desc_created')

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

    ordering = '-date_joined' if sort_by == 'desc_created' else 'date_joined'

    return User.objects.filter(filters).order_by(ordering)
