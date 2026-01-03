from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get value from dictionary by key."""
    return dictionary.get(key)
