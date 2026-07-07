from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Q
from django.core.paginator import Paginator
from django.contrib import messages
from .decorators import staff_member_required
from orders.models import Order
from shop.models import Product
from django.contrib.auth.models import User

@staff_member_required
def index(request):
    total_orders = Order.objects.count()
    total_revenue = Order.objects.filter(status='delivered').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    total_customers = User.objects.filter(is_staff=False).count()
    low_stock_count = Product.objects.filter(stock__lt=10).count()
    
    recent_orders = Order.objects.all().order_by('-created_at')[:5]
    top_products = Product.objects.all().order_by('-created')[:5] # Mock for top products
    
    pending_orders_count = Order.objects.filter(status='PENDING_PAYMENT').count()
    
    context = {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'total_customers': total_customers,
        'low_stock_count': low_stock_count,
        'recent_orders': recent_orders,
        'top_products': top_products,
        'pending_orders_count': pending_orders_count,
    }
    return render(request, 'dashboard/index.html', context)

@staff_member_required
def order_list(request):
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    payment_method = request.GET.get('payment_method', '').strip()

    orders = Order.objects.select_related('user').order_by('-created_at')

    # Search
    if q:
        orders = orders.filter(
            Q(order_number__icontains=q) |
            Q(shipping_full_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q)
        )

    # Filters
    if status:
        orders = orders.filter(status=status)
    if payment_method:
        orders = orders.filter(payment_method=payment_method)

    # Pagination
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    pending_orders_count = Order.objects.filter(status='PENDING_PAYMENT').count()

    context = {
        'page_obj': page_obj,
        'q': q,
        'status': status,
        'payment_method': payment_method,
        'status_choices': Order.STATUS_CHOICES,
        'payment_choices': Order.PAYMENT_CHOICES,
        'pending_orders_count': pending_orders_count,
    }
    return render(request, 'dashboard/orders.html', context)

@staff_member_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('user').prefetch_related('items__product'),
        pk=order_id
    )

    ALLOWED_TRANSITIONS = {
        "PENDING_PAYMENT": ["PAID", "CANCELLED", "PAYMENT_EXPIRED"],
        "PAID": ["PROCESSING", "REFUNDED", "CANCELLED"],
        "PROCESSING": ["SHIPPED", "REFUNDED", "CANCELLED"],
        "SHIPPED": ["DELIVERED"],
        "DELIVERED": ["REFUNDED"],
        "CANCELLED": [],
        "REFUNDED": [],
        "PAYMENT_EXPIRED": [],
    }

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'update_payment_status':
            new_payment_status = request.POST.get('payment_status', '').strip()
            valid_keys = [c[0] for c in Order.PAYMENT_STATUS_CHOICES]
            if new_payment_status in valid_keys:
                order.payment_status = new_payment_status
                order.save()
                messages.success(request, f"Payment status updated to {order.get_payment_status_display()}.")
            else:
                messages.error(request, "Invalid payment status.")
            return redirect('dashboard:order_detail', order_id=order.id)
        else:
            new_status = request.POST.get('status', '').strip()
            current_status = order.status
            allowed_next = ALLOWED_TRANSITIONS.get(current_status, [])

            if new_status in allowed_next:
                order.status = new_status
                order.save()
                messages.success(request, f"Order status updated to {order.get_status_display()}.")
                return redirect('dashboard:order_detail', order_id=order.id)
            else:
                messages.error(request, f"Transition from {order.get_status_display()} to {new_status} is not allowed.")
                return redirect('dashboard:order_detail', order_id=order.id)

    allowed_next = ALLOWED_TRANSITIONS.get(order.status, [])
    status_choices_dict = dict(Order.STATUS_CHOICES)
    valid_next_statuses = [(code, status_choices_dict[code]) for code in allowed_next if code in status_choices_dict]

    pending_orders_count = Order.objects.filter(status='PENDING_PAYMENT').count()

    context = {
        'order': order,
        'valid_next_statuses': valid_next_statuses,
        'pending_orders_count': pending_orders_count,
    }
    return render(request, 'dashboard/order_detail.html', context)

