# context_processors.py
from dashboard.models import Notification
from django.contrib.auth.models import User

def notification_context(request):
    if request.user.is_authenticated and request.user.is_staff:
        normal_users = User.objects.filter(is_staff=False, is_superuser=False)
        return {
            'all_notifications': Notification.objects.filter(recipient__in=normal_users, is_deleted=False),
            'read_notifications': Notification.objects.filter(recipient__in=normal_users, is_read=True, is_deleted=False),
            'unread_notifications': Notification.objects.filter(recipient__in=normal_users, is_read=False, is_deleted=False),
        }
    return {
        'all_notifications': [],
        'read_notifications': [],
        'unread_notifications': [],
    }
