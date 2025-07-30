from django import template

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
    """
    Filter reviews to return the review made by the specified user, if any.
    Works with both querysets and lists.
    """
    reviews = product.user_reviews.all() if hasattr(product.user_reviews, 'all') else product.user_reviews
    if hasattr(reviews, 'filter'):  # Check if reviews is a queryset
        return reviews.filter(user=user).first()
    else:  # Treat as a list
        for review in reviews:
            if review.user == user:
                return review
        return None