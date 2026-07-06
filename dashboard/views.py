from django.shortcuts import render
from django.db.models import Sum
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
    
    context = {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'total_customers': total_customers,
        'low_stock_count': low_stock_count,
        'recent_orders': recent_orders,
        'top_products': top_products,
    }
    return render(request, 'dashboard/index.html', context)
