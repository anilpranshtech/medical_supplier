from dashboard.models import *


def get_user_profile(user):
    if user.is_superuser:
        profile, _ = AdminUserProfile.objects.get_or_create(user=user)
        return profile, 'admin'

    for ProfileModel, profile_type in [
        (RetailProfile, 'retailer'),
        (WholesaleBuyerProfile, 'wholesaler'),
        (SupplierProfile, 'supplier'),
    ]:
        try:
            return ProfileModel.objects.get(user=user), profile_type
        except ProfileModel.DoesNotExist:
            continue
    return None, None