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

    # Superuser → can see all notifications
    if user.is_superuser:
        all_notifications = Notification.objects.filter(is_deleted=False)

    # Supplier → only his own notifications + "all suppliers"
    elif hasattr(user, 'retailprofile'):  
        all_notifications = Notification.objects.filter(
            is_deleted=False
        ).filter(
            Q(recipient=user) | Q(send_to="all_suppliers")   # ✅ fixed here
        )

    # Other staff → normal users ka notification
    elif user.is_staff:
        normal_users = User.objects.filter(is_staff=False, is_superuser=False)
        all_notifications = Notification.objects.filter(recipient__in=normal_users, is_deleted=False)

    else:
        # Normal user → only his notifications
        all_notifications = Notification.objects.filter(recipient=user, is_deleted=False)

    return {
        'all_notifications': all_notifications,
        'read_notifications': all_notifications.filter(is_read=True),
        'unread_notifications': all_notifications.filter(is_read=False),
    }
