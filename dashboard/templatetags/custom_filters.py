from django import template

register = template.Library()

@register.filter
def add_class(field, css_class):
    return field.as_widget(attrs={"class": css_class})

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