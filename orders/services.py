from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
from cart.views import _get_cart
from cart.models import Cart_Items
from .models import Order, OrderItem
from shop.models import Product

# Technical Debt Note:
# Checkout currently depends on session-based carts.
# Future work should associate carts with authenticated users.

def create_order(user, address, payment_method='COD', request=None):
    # Step 1: Validate address ownership and active state
    if not address or address.user != user or not address.is_active:
        raise ValidationError("Invalid or inactive shipping address.")

    if not request:
        raise ValidationError("Request object is required to fetch session cart.")

    with transaction.atomic():
        # Step 2: Fetch session cart
        cart = _get_cart(request)
        if not cart:
            raise ValidationError("No active cart found.")

        cart_items = Cart_Items.objects.filter(cart=cart, active=True)
        if not cart_items.exists():
            raise ValidationError("Your cart is empty.")

        # Step 3: Load products and lock rows using select_for_update()
        product_ids = [item.product.id for item in cart_items]
        products_dict = {
            p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)
        }

        # Step 4: Validate stock
        for item in cart_items:
            product = products_dict.get(item.product.id)
            if not product or product.stock < item.quantity:
                raise ValidationError(f"Insufficient stock for product: {item.product.name}")

        # Step 5: Generate order number
        today_str = timezone.now().strftime('%Y%m%d')
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # Using select_for_update on Order to lock today's count if needed, or simple count
        order_count = Order.objects.filter(created_at__gte=today_start).count()
        seq = order_count + 1
        order_number = f"SB-{today_str}-{seq:06d}"

        # Calculate totals
        total_amount = sum(item.product.price * item.quantity for item in cart_items)

        # Create Order (Step 5 & Step 6 Snapshotting)
        status = 'PROCESSING' if payment_method == 'COD' else 'PENDING_PAYMENT'

        order = Order.objects.create(
            user=user,
            order_number=order_number,
            payment_method=payment_method,
            status=status,
            payment_status='PENDING',
            expires_at=timezone.now() + timedelta(minutes=20),
            total_amount=total_amount,
            # Snapshot address fields
            shipping_full_name=address.full_name,
            shipping_phone=address.phone,
            shipping_address_line_1=address.address_line_1,
            shipping_address_line_2=address.address_line_2,
            shipping_landmark=address.landmark,
            shipping_city=address.city,
            shipping_state=address.state,
            shipping_country=address.country,
            shipping_postal_code=address.postal_code,
            # Legacy placeholder fields (not nullable in DB constraints if original schema required them)
            full_name=address.full_name,
            email=user.email or "guest@example.com",
            address=f"{address.address_line_1}, {address.address_line_2 or ''}".strip(', '),
            city=address.city,
            postal_code=address.postal_code,
        )

        # Step 7 & 8: Create OrderItem rows and decrement stock
        for item in cart_items:
            product = products_dict.get(item.product.id)
            
            # Create snapshot item
            OrderItem.objects.create(
                order=order,
                product=product,
                price=product.price,
                quantity=item.quantity
            )

            # Decrement stock
            product.stock -= item.quantity
            if product.stock <= 0:
                product.stock = 0
                product.in_stock = False
            product.save()

        # Step 9: Clear cart efficiently
        Cart_Items.objects.filter(cart=cart).delete()

        # Step 10: Return order instance
        return order


def cancel_order(order):
    # TODO: Implement cancel order logic restoring product stock.
    pass


def expire_orders():
    # TODO: Implement expire orders logic that runs via celery/cron.
    pass
