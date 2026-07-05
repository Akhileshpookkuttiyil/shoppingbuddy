from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Product, Category
from django.db.models import Q

def home(request, c_slug=None):
    """Render the homepage, optionally filtering by category."""
    c_page = None
    products_qs = Product.objects.filter(in_stock=True).select_related('category')
    
    if c_slug:
        c_page = get_object_or_404(Category, slug=c_slug)
        products_qs = products_qs.filter(category=c_page)
        
    # Pagination: 12 items per page is ideal as it is perfectly divisible by 1, 2, 3, and 4
    # ensuring perfect grid alignment across all screen sizes (mobile, tablet, desktop).
    paginator = Paginator(products_qs, 12)
    page = request.GET.get('page')
    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        # Gracefully handle out of bounds pages
        products = paginator.page(paginator.num_pages)
        
    return render(request, 'home.html', {
        'products': products
    })

def search(request):
    """Handle product search via query parameters."""
    query = request.GET.get('q', '').strip()
    products_qs = Product.objects.none()
    count = 0
    
    if query:
        # icontains is used for case-insensitive matching
        products_qs = Product.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query),
            in_stock=True
        ).select_related('category')
        count = products_qs.count()
        
    paginator = Paginator(products_qs, 12)
    page = request.GET.get('page')
    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)
        
    return render(request, 'search.html', {
        'query': query,
        'products': products,
        'count': count
    })

def detail(request, c_slug, p_slug):
    """Render the detailed view for a single product."""
    product = get_object_or_404(Product.objects.select_related('category'), category__slug=c_slug, slug=p_slug, in_stock=True)
    return render(request, 'detail.html', {'product': product})

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages
from .models import Wishlist

@login_required
def toggle_wishlist(request, product_id):
    """Toggle a product in the user's wishlist."""
    product = get_object_or_404(Product, id=product_id)
    wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    
    if not created:
        wishlist_item.delete()
        messages.info(request, f'Removed {product.name} from your wishlist.')
    else:
        messages.success(request, f'Added {product.name} to your wishlist.')
        
    return redirect(request.META.get('HTTP_REFERER', '/'))

@login_required
def wishlist_view(request):
    """Render the user's wishlist."""
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product', 'product__category')
    return render(request, 'wishlist.html', {
        'wishlist_items': wishlist_items
    })
