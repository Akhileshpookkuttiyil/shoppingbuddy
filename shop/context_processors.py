from .models import Category, Wishlist

def categories(request):
    """
    Globally provides the 'categories' context variable to all templates.
    """
    context = {
        'categories': Category.objects.all(),
        'wishlist_count': 0,
        'wishlist_product_ids': []
    }
    
    if request.user.is_authenticated:
        wishlist = Wishlist.objects.filter(user=request.user)
        context['wishlist_count'] = wishlist.count()
        context['wishlist_product_ids'] = list(wishlist.values_list('product_id', flat=True))
        
    return context
