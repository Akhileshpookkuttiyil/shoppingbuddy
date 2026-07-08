from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from cart.views import _get_cart
from cart.models import Cart_Items
from accounts.models import UserAddress
from .services import create_order
from .models import Order

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
            
    # Redirect to cart details if cart is empty on GET
    if request.method == 'GET' and not cart_items:
        return redirect('cart_details')

    if request.method == 'POST':
        address_id = request.POST.get('shipping_address')
        payment_method = request.POST.get('payment_method', 'COD')

        if not address_id:
            return render(request, 'checkout.html', {
                'addresses': addresses,
                'cart_items': cart_items,
                'total': total,
                'count': count,
                'error': 'Please select a shipping address.'
            })

        try:
            address = request.user.addresses.get(pk=address_id)
            order = create_order(request.user, address, payment_method, request=request)
            if payment_method == 'RAZORPAY':
                from payments.services import create_razorpay_order
                try:
                    rz_order = create_razorpay_order(order)
                    order.razorpay_order_id = rz_order['id']
                    order.save(update_fields=['razorpay_order_id'])
                except Exception as ex:
                    raise ValidationError(f"Failed to initialize payment gateway: {str(ex)}")
                return redirect('payments:payment_page', order_id=order.id)
            else:
                return redirect('order_confirmation', order_id=order.id)
        except (ValidationError, UserAddress.DoesNotExist) as e:
            error_msg = str(e).strip("[]'") if isinstance(e, ValidationError) else 'Selected shipping address does not exist.'
            return render(request, 'checkout.html', {
                'addresses': addresses,
                'cart_items': cart_items,
                'total': total,
                'count': count,
                'error': error_msg
            })

    return render(request, 'checkout.html', {
        'addresses': addresses,
        'cart_items': cart_items,
        'total': total,
        'count': count,
    })

from django.core.paginator import Paginator

@login_required
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    return render(request, 'confirmation.html', {'order': order})

@login_required
def order_list(request):
    orders = request.user.orders.all().prefetch_related('items__product').order_by('-created_at')
    return render(request, 'account/orders.html', {'orders': orders})

@login_required
def my_orders(request):
    orders_queryset = Order.objects.filter(user=request.user).select_related('user').prefetch_related('items__product').order_by('-created_at')
    paginator = Paginator(orders_queryset, 10)
    page_number = request.GET.get('page')
    orders = paginator.get_page(page_number)
    return render(request, 'account/orders.html', {'orders': orders})

@login_required
def customer_order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('user').prefetch_related('items__product'),
        pk=order_id,
        user=request.user
    )
    return render(request, 'account/order_detail.html', {
        'order': order,
        'order_items': order.items.all(),
    })

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product'),
        pk=order_id,
        user=request.user
    )
    return render(request, 'account/order_detail.html', {'order': order})




