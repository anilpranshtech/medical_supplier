# context_processors.py
from utils.handle_user_profile import get_user_profile
from dashboard.models import Notification
from django.db.models import Q

def header_avatar(request):
    if request.user.is_authenticated:
        profile, profile_type = get_user_profile(request.user)
        if profile and profile.profile_picture:
            return {"header_avatar_url": profile.profile_picture.url}
    return {"header_avatar_url": None}



def notification_context(request):
    if not request.user.is_authenticated:
        return {
            'all_notifications': [],
            'read_notifications': [],
            'unread_notifications': [],
        }

    user = request.user

    base_query = Notification.objects.filter(is_deleted=False)

    if user.is_superuser or user.is_staff:
        all_notifications = base_query.filter(
            Q(recipient=user, send_to="single") | Q(send_to="all") | Q(send_to="buyer")
        )

    elif hasattr(user, 'supplierprofile'):
        all_notifications = base_query.filter(
            Q(recipient=user, send_to="single") | Q(send_to="supplier") | Q(send_to="all")
        )

    else:

        all_notifications = base_query.filter(
            Q(recipient=user, send_to="single") | Q(send_to="buyer") | Q(send_to="all")
        )

    return {
        'all_notifications': all_notifications.order_by('-created_at'),
        'read_notifications': all_notifications.filter(is_read=True).order_by('-created_at'),
        'unread_notifications': all_notifications.filter(is_read=False).order_by('-created_at'),
    }

from .models import ProductCategory

def categories_processor(request):
    categories = ProductCategory.objects.all()
    return {"categories": categories}
