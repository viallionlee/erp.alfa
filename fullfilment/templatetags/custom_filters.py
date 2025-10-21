from django import template

register = template.Library()

@register.filter
def sub(value, arg):
    """Mengurangi arg dari value."""
    try:
        return value - arg
    except (ValueError, TypeError):
        return '' 