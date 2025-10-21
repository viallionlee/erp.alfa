from django import template

register = template.Library()

@register.filter
def avg_price(price_histories):
    """Calculate average price from price histories"""
    if not price_histories:
        return 0
    
    total_price = sum(ph.price for ph in price_histories)
    return total_price / len(price_histories)

