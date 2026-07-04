from django.shortcuts import render,get_object_or_404
from .models import Product,Category
from django.db.models import Q
# Create your views here.
def home(request,c_slug=None):
    c_page=None
    products=None
    if c_slug is not None:
        c_page=get_object_or_404(Category,slug=c_slug)
        products=Product.objects.filter(category=c_page,in_stock=True)
    else:
        products=Product.objects.all()
    categories=Category.objects.all()
    return render(request,'home.html',{'products':products,'categories':categories})

def search(request):
    query=None
    prod=None
    cnt=0
    if 'q' in request.GET:
        query=request.GET.get('q')
        prod=Product.objects.all().filter(Q(name__contains=query)|Q(description__contains=query))
        for p in prod:
            cnt+=1
    return render(request, 'search.html', {'query': query, 'products': prod,'count':cnt})

def detail(request,c_slug,p_slug):
    prod=Product.objects.get(category__slug=c_slug,slug=p_slug)
    return render(request,'detail.html',{'product':prod})
