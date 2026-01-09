from celery import shared_task
from django.utils import timezone
from supplier.models import Banner

@shared_task
def update_banner_status():
    now = timezone.now()

    # Activate banners within their time
    Banner.objects.filter(
        start_at__lte=now,
        end_at__gte=now,
        is_active=False
    ).update(is_active=True)

    # Deactivate banners expired
    Banner.objects.filter(
        end_at__lt=now,
        is_active=True
    ).update(is_active=False)
