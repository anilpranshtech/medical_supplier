from django.db import transaction
import logging
import uuid
from django.utils import timezone
from decimal import Decimal
from dashboard.models import *

logger = logging.getLogger(__name__)

def generate_order_id():
    import uuid
    return f"X{uuid.uuid4().hex[:6].upper()}-S{timezone.now().strftime('%y')}"

def create_orders_from_cart(user, payment_type, payment_status, payment):
    try:
        # Verify cart items
        cart_items = CartProduct.objects.filter(user=user).select_related('product')
        if not cart_items.exists():
            logger.error(f"No cart items found for user {user.id}")
            raise ValueError("Cart is empty")

        # Verify billing address
        billing = CustomerBillingAddress.objects.filter(user=user, is_default=True, is_deleted=False).first()
        if not billing:
            logger.error(f"No default billing address found for user {user.id}")
            raise ValueError("No default billing address found")

        # Calculate totals
        subtotal = sum(item.get_total_price() for item in cart_items)
        shipping_fees = Decimal('24.60')  # Matches $512.60 - $488.00 from order_placed.html
        total = subtotal + shipping_fees

        # Create Order within transaction
        with transaction.atomic():
            order = Order.objects.create(
                user=user,
                payment=payment,
                order_id=generate_order_id(),
                shipping_fees=shipping_fees,
                shipping_type='Standard Shipping',
                shipping_full_address=billing.customer_address1 + (f", {billing.customer_address2}" if billing.customer_address2 else ""),
                shipping_city=billing.customer_city,
                shipping_country=billing.customer_country,
                status='pending',
                created_at=timezone.now()
            )
            logger.info(f"Created Order {order.order_id} (ID: {order.id}) for user {user.id} with payment {payment.id}")

            # Create OrderItem entries
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    order_by=user,
                    order_to=item.product.created_by,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.discounted_price(),
                    payment_type=payment_type,
                    payment_status=payment_status,
                    payment_currency='USD' if payment_type in ['stripe', 'cod'] else 'INR',
                    phone_number=billing.phone,
                    status='pending'
                )
                logger.info(f"Created OrderItem for product {item.product.id} (quantity: {item.quantity}) in Order {order.order_id}")

            # Clear the cart
            cart_items.delete()
            logger.info(f"Cleared cart for user {user.id}")

            return order

    except Exception as e:
        logger.error(f"Failed to create order for user {user.id}: {str(e)}", exc_info=True)
        raise