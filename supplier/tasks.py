from celery import shared_task
from django.core.mail import send_mass_mail
from django.contrib.auth import get_user_model
from django.conf import settings
from dashboard.models import Event

User = get_user_model()

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def send_event_email_task(self, event_id):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return "Event not found"

    users = User.objects.filter(is_active=True).values_list('email', flat=True)

    if not users:
        return "No users to send email"

    subject = f"📢 New Event: {event.speaker_name}"
    message = f"""
Hello,

We are excited to announce a new event!

📌 Event: {event.speaker_name}
📍 Venue: {event.venue}
🕒 Date: {event.conference_at}
⏳ Duration: {event.duration}

🔗 Register here:
{event.conference_link}

Thank you,
Team {settings.DEFAULT_FROM_EMAIL}
"""

    emails = [
        (subject, message, settings.DEFAULT_FROM_EMAIL, [email])
        for email in users if email
    ]

    send_mass_mail(emails, fail_silently=False)
    return f"Emails sent to {len(emails)} users"
