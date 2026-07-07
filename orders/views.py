from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from cart.views import _get_cart
from cart.models import Cart_Items
from accounts.models import UserAddress

@login_required
def checkout(request):
    addresses = request.user.addresses.filter(is_active=True).order_by('-is_default', '-updated_at')
    
    total = 0
    count = 0
    cart_items = []
    
    cart = _get_cart(request)
    if cart:
        cart_items = Cart_Items.objects.filter(cart=cart, active=True).select_related('product')
        for item in cart_items:
            total += (item.product.price * item.quantity)
            count += item.quantity
            
    # Redirect to cart details if cart is empty
    if not cart_items:
        return redirect('cart_details')

    return render(request, 'checkout.html', {
        'addresses': addresses,
        'cart_items': cart_items,
        'total': total,
        'count': count,
    })

