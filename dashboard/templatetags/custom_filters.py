from datetime import timedelta

from django import template
from django.utils import timezone

import logging
logger = logging.getLogger(__name__)

register = template.Library()


@register.filter
def add_class(field, css_class):
    return field.as_widget(attrs={"class": css_class})


@register.filter
def subtract(value, arg):
    return float(value) - float(arg)


@register.filter
def dict_get(dictionary, key):
    return dictionary.get(key)


@register.filter
def divide(value, arg):
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0


@register.filter
def get(dictionary, key):
    return dictionary.get(int(key), 0)


@register.filter
def percentage(value, total):
    try:
        return (value / total) * 100 if total else 0
    except:
        return 0


@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def get_feature_value(dictionary, key):
    return dictionary.get(key)


@register.filter
def get_user_review(reviews, user):
    return reviews.filter(user=user).first()


@register.filter
def get_rating_label(value):
    labels = {
        1: "Very Bad",
        2: "Bad",
        3: "Okay",
        4: "Good",
        5: "Excellent"
    }
    return labels.get(value, "Select rating")


@register.filter
def filter_by_user(product, user):
    reviews = product.user_reviews.all() if hasattr(product.user_reviews, 'all') else product.user_reviews
    if hasattr(reviews, 'filter'):
        return reviews.filter(user=user).first()
    else:
        for review in reviews:
            if review.user == user:
                return review
        return None


@register.simple_tag(takes_context=True)
def query_replace(context, **kwargs):
    request = context['request']
    params = request.GET.copy()
    for k, v in kwargs.items():
        if v is None or v == '':
            params.pop(k, None)
        else:
            params[k] = v
    return params.urlencode()


@register.filter
def add_days(value, days):
    if not value:
        return value
    try:
        # Ensure value is a datetime object
        if isinstance(value, str):
            from django.utils.dateparse import parse_datetime
            value = parse_datetime(value)
        # Add days
        result = value + timedelta(days=int(days))
        return result
    except (ValueError, TypeError):
        return value


@register.filter
def is_event_category(category_name):
    event_categories = ["Conference", "Webinar", "Event"]
    return category_name in event_categories


@property
def get_main_image(self):
    return self.main_image.first()


@register.filter
def status_count(returns, status):
    return returns.filter(return_status=status).count()


@register.filter
def dictfilter(d, key):
    if isinstance(d, dict):
        return d.get(key, "")
    return ""


@register.filter
def return_debug(order_item):
    """Debug filter to show return eligibility information"""
    debug_info = {
        'order_status': order_item.order.status,
        'product_returnable': order_item.product.is_returnable,
        'delivery_date': order_item.delivery_date,
        'order_delivered_at': order_item.order.delivered_at,
        'return_deadline': order_item.return_deadline,
        'can_return': order_item.can_return,
        'days_left': order_item.days_left_to_return if hasattr(order_item, 'days_left_to_return') else 'N/A'
    }
    return debug_info


@register.filter
def days_until_deadline(deadline):
    """Calculate days until deadline"""
    if not deadline:
        return 0
    days_left = (deadline - timezone.now()).days
    return max(0, days_left)


@register.simple_tag
def return_status_class(order_item):
    """Return CSS class based on return status"""
    if not order_item.product.is_returnable:
        return 'text-gray-500'
    elif order_item.can_return:
        days_left = order_item.days_left_to_return if hasattr(order_item, 'days_left_to_return') else 0
        if days_left > 3:
            return 'text-green-600'
        elif days_left > 0:
            return 'text-yellow-600'
        else:
            return 'text-red-600'
    else:
        return 'text-red-600'


@register.filter
def filter_by_name(value, name):
    if hasattr(value, 'filter'):
        result = value.filter(name=name).first()
        logger.debug(f"filter_by_name: Queryset filtered, result: {result}")
        return result
    logger.error(f"filter_by_name received non-queryset: type={type(value)}, value={value}")
    return None


@register.filter
def is_number(value):
    try:
        int(value)
        return True
    except (ValueError, TypeError):
        return False


@register.filter
def get_type(value):
    return str(type(value).__name__)


@register.filter
def multiply(value, arg):
    """Multiply two numbers and return the result."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def add(value, arg):
    """Add two numbers and return the result."""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def get_return_status_message(item):
    """Get user-friendly return status message for an OrderItem."""
    return item.get_return_status_message()


@register.filter
def can_request_return(item):
    """Check if an OrderItem can have a new return request."""
    return item.can_request_return


@register.filter
def days_left_to_return(item):
    """Get number of days left to return an OrderItem."""
    return item.days_left_to_return


@register.filter
def return_deadline(item):
    """Get the return deadline for an OrderItem."""
    deadline = item.return_deadline
    return deadline if deadline else None


@register.filter
def has_pending_return(item):
    """Check if OrderItem has a pending return request."""
    return item.has_pending_return


@register.filter
def latest_return(item):
    """Get the latest return request for an OrderItem."""
    return item.latest_return


@register.filter
def return_history(item):
    """Get all return requests for an OrderItem."""
    return item.return_history


@register.filter
def format_currency(value, currency="USD"):
    """Format a value as currency with given currency code."""
    try:
        return f"{currency} {float(value):.2f}"
    except (ValueError, TypeError):
        return f"{currency} 0.00"


@register.filter
def order_item_total(item):
    """Calculate total price for an OrderItem (quantity * price)."""
    try:
        return item.quantity * item.price
    except (ValueError, TypeError):
        return 0


@register.filter
def order_total(order):
    """Calculate total price for an Order (sum of item totals + shipping)."""
    try:
        subtotal = sum(item.quantity * item.price for item in order.items.all())
        shipping = order.shipping_fees or 0
        return subtotal + shipping
    except (ValueError, TypeError):
        return 0


@register.filter
def get_order_status_class(status):
    """Return CSS classes for order status badge based on status."""
    status_classes = {
        'pending': 'bg-yellow-200 text-yellow-800',
        'processing': 'bg-blue-200 text-blue-800',
        'shipped': 'bg-purple-200 text-purple-800',
        'delivered': 'bg-green-200 text-green-800',
        'cancelled': 'bg-red-200 text-red-800',
        'completed': 'bg-green-200 text-green-800',
        'delivering': 'bg-blue-200 text-blue-800',
        'refunded': 'bg-gray-200 text-gray-800',
        'failed': 'bg-red-200 text-red-800',
    }
    return status_classes.get(status.lower(), 'bg-gray-200 text-gray-800')


@register.filter
def get_return_status_badge(return_obj):
    """Return CSS classes and icon for return status badge."""
    status = return_obj.return_status
    badge_info = {
        'pending': {'class': 'bg-yellow-200 text-yellow-800', 'icon': 'ki-filled ki-time'},
        'return_completed': {'class': 'bg-green-200 text-green-800', 'icon': 'ki-filled ki-check'},
        'replace_completed': {'class': 'bg-blue-200 text-blue-800', 'icon': 'ki-filled ki-arrows-loop'},
        'cancelled': {'class': 'bg-red-200 text-red-800', 'icon': 'ki-filled ki-cross'},
    }
    info = badge_info.get(status, {'class': 'bg-gray-200 text-gray-800', 'icon': 'ki-filled ki-information'})
    return {'class': info['class'], 'icon': info['icon']}


@register.filter
def get_return_status_class(return_obj):
    """Return CSS class for return status badge."""
    status = return_obj.return_status
    badge_info = {
        'pending': 'bg-yellow-200 text-yellow-800',
        'return_completed': 'bg-green-200 text-green-800',
        'replace_completed': 'bg-blue-200 text-blue-800',
        'cancelled': 'bg-red-200 text-red-800',
    }
    return badge_info.get(status, 'bg-gray-200 text-gray-800')


@register.filter
def get_return_status_icon(return_obj):
    """Return icon class for return status badge."""
    status = return_obj.return_status
    badge_info = {
        'pending': 'ki-filled ki-time',
        'return_completed': 'ki-filled ki-check',
        'replace_completed': 'ki-filled ki-arrows-loop',
        'cancelled': 'ki-filled ki-cross',
    }
    return badge_info.get(status, 'ki-filled ki-information')


@register.filter
def is_returnable(item):
    """Check if the product associated with OrderItem is returnable."""
    return item.product.is_returnable


@register.filter
def get_delivery_date(item):
    """Get the delivery date for an OrderItem, falling back to order's delivered_at."""
    return item.delivery_date or item.order.delivered_at

@register.filter
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except:
        return 0
