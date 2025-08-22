import stripe
import razorpay
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from dashboard.models import *

stripe.api_key = settings.STRIPE_SECRET_KEY
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def process_refund(payment, return_serial, amount, admin_note=None, user_note=None):
    """
    Handle refunds for different payment methods and send email notification to the user.
    Returns: (success: bool, message: str, refund_id: str|None)
    """

    refund_id = None
    success_message = None

    try:
        # === COD / Bank Transfer → Manual refund ===
        if payment.payment_method in ["cod", "bank_transfer"]:
            refund_id = "MANUAL_REFUND"
            success_message = f"{payment.payment_method.upper()} refund marked as completed manually"

        # === Razorpay Refund ===
        elif payment.payment_method == "razorpay":
            razorpay_payment = payment.razorpay_payment.first()
            if not razorpay_payment:
                return False, "No Razorpay payment record found", None

            refund = razorpay_client.payment.refund(
                razorpay_payment.razorpay_payment_id,
                {
                    "amount": int(float(amount) * 100),  # amount in paise
                    "notes": {
                        "return_id": return_serial,
                        "admin_notes": admin_note or "Processed by admin",
                        "description": user_note or "User return refund"
                    }
                }
            )
            refund_id = refund.get("id")
            success_message = "Refunded via Razorpay"

        # === Stripe Refund ===
        elif payment.payment_method == "stripe":
            stripe_payment = StripePayment.objects.filter(payment=payment).first()
            if not stripe_payment:
                return False, "No Stripe payment record found", None

            if stripe_payment.stripe_payment_intent_id:
                refund = stripe.Refund.create(
                    payment_intent=stripe_payment.stripe_payment_intent_id,
                    amount=int(float(amount) * 100),
                    metadata={
                        "return_id": return_serial,
                        "admin_notes": admin_note or "Processed by admin",
                        "description": user_note or "User return refund"
                    }
                )
            elif stripe_payment.stripe_charge_id:
                refund = stripe.Refund.create(
                    charge=stripe_payment.stripe_charge_id,
                    amount=int(float(amount) * 100),
                    metadata={
                        "return_id": return_serial,
                        "admin_notes": admin_note or "Processed by admin",
                        "description": user_note or "User return refund"
                    }
                )
            else:
                return False, "No PaymentIntent ID or Charge ID found in StripePayment", None

            refund_id = refund["id"]
            success_message = "Refunded via Stripe"

        else:
            return False, f"Unsupported payment method: {payment.payment_method}", None

        # === Send Email Notification to User ===
        try:
            user_email = payment.user.email
            subject = f"Refund Processed for Return {return_serial}"

            html_message = render_to_string(
                "superuser/emails/refund_email.html",
                {
                    "user": payment.user,
                    "amount": amount,
                    "currency": payment.currency or "USD",
                    "return_serial": return_serial,
                    "admin_note": admin_note,
                    "user_note": user_note,
                    "refund_id": refund_id,
                    "payment_method": payment.payment_method,
                }
            )
            plain_message = strip_tags(html_message)

            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [user_email],
                html_message=html_message,
            )
        except Exception as e:
            # Email failed, but refund succeeded
            return True, f"{success_message}, but email failed: {str(e)}", refund_id

        return True, f"{success_message} and email sent successfully", refund_id

    except Exception as e:
        return False, f"Refund failed: {str(e)}", None
