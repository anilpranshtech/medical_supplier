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

    if user.is_superuser:
        # Superuser → all notifications
        all_notifications = Notification.objects.filter(is_deleted=False)

    elif hasattr(user, 'retailprofile'):  
        # Supplier → his own + all suppliers
        all_notifications = Notification.objects.filter(
            is_deleted=False
        ).filter(
            Q(recipient=user) | Q(send_to="all_suppliers")
        )

    elif user.is_staff:
        # Staff → notifications sent to normal users
        normal_users = User.objects.filter(is_staff=False, is_superuser=False)
        all_notifications = Notification.objects.filter(
            recipient__in=normal_users,
            is_deleted=False
        )

    else:
        # Normal user → only his own
        all_notifications = Notification.objects.filter(
            recipient=user,
            is_deleted=False
        )

    return {
        'all_notifications': all_notifications,
        'read_notifications': all_notifications.filter(is_read=True),
        'unread_notifications': all_notifications.filter(is_read=False),
    }
