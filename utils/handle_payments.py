from django.db import transaction
import logging
from django.utils import timezone
from decimal import Decimal
from dashboard.models import *

logger = logging.getLogger(__name__)

def create_orders_from_cart(user, payment_type, payment_status):
    with transaction.atomic():
        cart_items = CartProduct.objects.filter(user=user).select_related('product')
        default_billing = CustomerBillingAddress.objects.filter(user=user, is_default=True, is_deleted=False).first()

        # Calculate total for Payment object
        total = sum(item.get_total_price() for item in cart_items) or Decimal('0.00')
        payment = Payment.objects.create(
            user=user,
            name=user.get_full_name(),
            amount=total,
            payment_method=payment_type,
            paid=(payment_status == 'paid')
        )

        for item in cart_items:
            if not item.product.created_by:
                logger.error(f"Product {item.product.id} has no created_by user.")
                continue
            if not hasattr(item.product.created_by, 'supplierprofile'):
                logger.warning(f"Product {item.product.id} created by non-supplier user {item.product.created_by}.")
                continue

            Orders.objects.create(
                order_by=user,
                order_to=item.product.created_by,
                product=item.product,
                quantity=item.quantity,
                price=item.get_total_price(),
                phone_number=default_billing.phone if default_billing and default_billing.phone else "Not provided",
                payment=payment,
                payment_type=payment_type,
                payment_status=payment_status,
                payment_currency="INR" if payment_type == "razorpay" else "USD",
                shipping_fees=0,
                shipping_type="Standard",
                shipping_full_address=default_billing.customer_address1 if default_billing else "No address provided",
                shipping_city=default_billing.customer_city if default_billing else "No city provided",
                shipping_country=default_billing.customer_country if default_billing else "No country provided",
                status="processing",
                created_at=timezone.now()
            )

        cart_items.delete()
        return payment