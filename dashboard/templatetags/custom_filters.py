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