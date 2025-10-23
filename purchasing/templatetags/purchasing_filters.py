from django import template

register = template.Library()

@register.filter
def div(value, arg):
    """Divide the value by arg"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

