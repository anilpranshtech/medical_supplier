import razorpay
import stripe
from django.conf import settings
from django.core.mail import send_mail
from django.http import QueryDict

from django.shortcuts import render, redirect
from django.http import Http404
from django.contrib.auth.models import User
from django.core.signing import Signer, BadSignature
import base64
from django.utils import timezone

from datetime import date, datetime, timedelta

signer = Signer()


def requestParamsToDict(request, url_params=False, get_params=False, post_params=False):
    parsed_params = {}
    if url_params:
        current_url_params = request.META.get('HTTP_X_URL_PARAMETERS')
        if '?' in current_url_params:
            current_url_params = current_url_params.split('?')[-1]
            parsed_params = QueryDict(current_url_params)
    elif get_params:
        parsed_params = dict(request.GET.items())
    elif post_params:
        parsed_params = dict(request.POST.items())

    return parsed_params


def util_get_date_range(filter_date):
    try:
        date_parts = filter_date.split('-')
        start_date_str, end_date_str = map(str.strip, date_parts)

        start_date = timezone.make_aware(timezone.datetime.strptime(start_date_str, '%m/%d/%Y'),
                                         timezone.get_current_timezone())
        end_date = timezone.make_aware(timezone.datetime.strptime(end_date_str, '%m/%d/%Y'),
                                       timezone.get_current_timezone())
        if start_date == end_date:
            end_date = end_date + timedelta(days=1) - timedelta(seconds=1)
        else:
            end_date = end_date + timedelta(days=1) - timedelta(seconds=1)

        return start_date, end_date
    except Exception as e:
        print(f"Error parsing date range: {e}")
        return None, None


def send_refund_notification(user_email, subject, message):
    """
    Sends refund notification email to the user.
    """
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,  # sender email
            [user_email],
            fail_silently=False,
        )
    except Exception as e:
        # Optional: log error
        print(f"Error sending refund email: {e}")


def process_stripe_refund(payment_intent_id, amount=None):
    """
    Refunds a Stripe payment. If amount is None, full refund.
    """
    try:
        refund = stripe.Refund.create(
            payment_intent=payment_intent_id,
            amount=int(amount * 100) if amount else None,  # amount in cents
        )
        return refund
    except Exception as e:
        return {"error": str(e)}


def process_razorpay_refund(payment_id, amount=None):
    """
    Refunds a Razorpay payment. If amount is None, full refund.
    """
    try:
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        refund = client.payment.refund(payment_id, {
            "amount": int(amount * 100) if amount else None
        })
        return refund
    except Exception as e:
        return {"error": str(e)}
