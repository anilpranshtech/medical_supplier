# context_processors.py
from utils.handle_user_profile import get_user_profile


def header_avatar(request):
    if request.user.is_authenticated:
        profile, profile_type = get_user_profile(request.user)
        if profile and profile.profile_picture:
            return {"header_avatar_url": profile.profile_picture.url}
    return {"header_avatar_url": None}

from dashboard.models import Notification
from django.contrib.auth.models import User
from django.db.models import Q

def notification_context(request):
    if not request.user.is_authenticated:
        return {
            'all_notifications': [],
            'read_notifications': [],
            'unread_notifications': [],
        }

    user = request.user

    # Superuser → all
    if user.is_superuser:
        all_notifications = Notification.objects.filter(is_deleted=False)

    # Supplier → his own + all suppliers
    elif hasattr(user, 'retailprofile'):  
        all_notifications = Notification.objects.filter(
            is_deleted=False
        ).filter(
            Q(recipient=user) | Q(send_to="all_suppliers")
        )

    # Staff → notifications for normal users
    elif user.is_staff:
        normal_users = User.objects.filter(is_staff=False, is_superuser=False)
        all_notifications = Notification.objects.filter(recipient__in=normal_users, is_deleted=False)

    # Normal user → only his
    else:
        all_notifications = Notification.objects.filter(recipient=user, is_deleted=False)

    return {
        'all_notifications': all_notifications.order_by('-created_at'),
        'read_notifications': all_notifications.filter(is_read=True).order_by('-created_at'),
        'unread_notifications': all_notifications.filter(is_read=False).order_by('-created_at'),
    }
