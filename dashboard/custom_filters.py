from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Safely get item from dict in template.
    Returns None if dictionary is not a dict or key not found.
    """
    try:
        if isinstance(dictionary, dict):
            return dictionary.get(key)
        return None
    except Exception:
        return None 
