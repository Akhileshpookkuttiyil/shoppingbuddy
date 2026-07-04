from django.db.models import Sum
from .models import Cart_List, Cart_Items
from .views import _cart_id

def cart_count(request):
    """
    Globally provides the 'cart_count' variable to all templates, representing
    the total number of active items in the current user's cart.
    """
    count = 0
    # Avoid querying the cart on Django admin pages
    if request.path.startswith('/admin/'):
        return {}
        
    try:
        cart = Cart_List.objects.filter(cart_id=_cart_id(request)).first()
        if cart:
            # Optimized: Delegate calculation entirely to the database via SUM aggregate
            count = Cart_Items.objects.filter(cart=cart, active=True).aggregate(total_qty=Sum('quantity'))['total_qty'] or 0
    except Exception:
        count = 0
        
    return {'cart_count': count}
