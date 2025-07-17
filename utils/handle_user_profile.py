from dashboard.models import RetailProfile, WholesaleBuyerProfile, SupplierProfile


def get_user_profile(user):
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