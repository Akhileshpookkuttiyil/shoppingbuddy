from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import F
from .models import Cart_List, Cart_Items
from shop.models import Product

def _cart_id(request):
    """
    Helper to get or create a stable cart ID that survives session cycling.
    During login, Django rotates the session_key. By explicitly storing the
    cart_id inside the session dict, the cart won't be orphaned when a user logs in.
    """
    cart_id = request.session.get('cart_id')
    if not cart_id:
        cart_id = request.session.session_key
        if not cart_id:
            request.session.create()
            cart_id = request.session.session_key
        request.session['cart_id'] = cart_id
    return cart_id

def _get_cart(request, create_if_missing=False):
    """Helper to retrieve the cart, optionally creating it."""
    cart_id = _cart_id(request)
    if create_if_missing:
        cart, _ = Cart_List.objects.get_or_create(cart_id=cart_id)
        return cart
    try:
        return Cart_List.objects.get(cart_id=cart_id)
    except Cart_List.DoesNotExist:
        return None

def cart_details(request):
    """Render the cart details, calculating total cost and item count."""
    total = 0
    count = 0
    cart_items = []
    
    cart = _get_cart(request)
    if cart:
        # select_related optimizes the query by fetching related Products and their Categories in the same DB hit
        cart_items = Cart_Items.objects.filter(cart=cart, active=True).select_related('product', 'product__category')
        for item in cart_items:
            total += (item.product.price * item.quantity)
            count += item.quantity
            
    return render(request, 'cart.html', {
        'total': total,
        'count': count,
        'cart_items': cart_items
    })

def add_cart(request, product_id):
    """Add a product to the cart or increment its quantity safely."""
    product = get_object_or_404(Product, id=product_id, in_stock=True)
    
    # Prevent adding out-of-stock items
    if product.stock <= 0:
        return redirect('cart_details')
        
    cart = _get_cart(request, create_if_missing=True)
    
    cart_item, created = Cart_Items.objects.get_or_create(
        product=product,
        cart=cart,
        defaults={'quantity': 1}
    )
    
    if not created:
        # Ensure we don't exceed available stock
        if cart_item.quantity < product.stock:
            # Atomic update to prevent race conditions during concurrent clicks
            cart_item.quantity = F('quantity') + 1
            cart_item.save()
            
    return redirect('cart_details')
    
def min_cart(request, product_id):
    """Decrement a product's quantity in the cart cleanly."""
    product = get_object_or_404(Product, id=product_id)
    cart = _get_cart(request)
    
    if cart:
        try:
            cart_item = Cart_Items.objects.get(product=product, cart=cart)
            if cart_item.quantity > 1:
                # Atomic update
                cart_item.quantity = F('quantity') - 1
                cart_item.save()
            else:
                cart_item.delete()
        except Cart_Items.DoesNotExist:
            pass
            
    return redirect('cart_details')

def del_cart(request, product_id):
    """Completely remove a single product from the cart."""
    product = get_object_or_404(Product, id=product_id)
    cart = _get_cart(request)
    
    if cart:
        # Perform a direct query deletion, saving a database trip vs .get().delete()
        Cart_Items.objects.filter(product=product, cart=cart).delete()
        
    return redirect('cart_details')

def clear_cart(request):
    """Empty the entire cart efficiently."""
    cart = _get_cart(request)
    
    if cart:
        # Efficient bulk delete
        Cart_Items.objects.filter(cart=cart).delete()
        
    return redirect('cart_details')
