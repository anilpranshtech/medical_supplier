# context_processors.py
from utils.handle_user_profile import get_user_profile
from .models import ProductCategory, Notification
from .models import ProductCategory
from django.db.models import Q



def categories_processor(request):
    categories = ProductCategory.objects.filter(
        product__last_category__isnull=False
    ).distinct()
    return {"categories": categories}

def header_avatar(request):
    if request.user.is_authenticated:
        profile, profile_type = get_user_profile(request.user)
        if profile and profile.profile_picture:
            return {"header_avatar_url": profile.profile_picture.url}
    return {"header_avatar_url": None}



def notification_context(request):
    if not request.user.is_authenticated:
        return {'all_notifications': [], 'read_notifications': [], 'unread_notifications': []}

    all_notifications = Notification.objects.filter(recipient=request.user, is_deleted=False)
    return {
        'all_notifications': all_notifications,
        'read_notifications': all_notifications.filter(is_read=True),
        'unread_notifications': all_notifications.filter(is_read=False),
    }
