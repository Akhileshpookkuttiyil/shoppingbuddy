from django.shortcuts import render,redirect,get_object_or_404
from .models import *
from shop.models import *
from django.core.exceptions import ObjectDoesNotExist
# Create your views here.

def c_id(request):
    ct_id=request.session.session_key
    if not c_id:
        ct_id=request.session.create()
    return ct_id

def cart_details(request,tot=0,count=0,cart_items=None):
    try:
        crt=Cart_List.objects.get(cart_id=c_id(request))
        cart_items=Cart_Items.objects.filter(cart=crt,active=True)
        for item in cart_items:
            tot+=(item.product.price*item.quantity)
            count+=item.quantity
    except ObjectDoesNotExist:
        pass
    return render(request,'cart.html',{'total':tot,'count':count,'cart_items':cart_items})



def add_cart(request,product_id):
    prod=Product.objects.get(id=product_id)
    try:
        ct=Cart_List.objects.get(cart_id=c_id(request))
    except Cart_List.DoesNotExist:
        ct=Cart_List.objects.create(cart_id=c_id(request))
        ct.save()
    try:
        c_items=Cart_Items.objects.get(product=prod,cart=ct)
        if c_items.quantity < c_items.product.stock:
            c_items.quantity+=1
        c_items.save()
    except Cart_Items.DoesNotExist:
        c_items=Cart_Items.objects.create(product=prod,cart=ct,quantity=1)
        c_items.save()
    return redirect('cart_details')
        
def del_cart(request,product_id):
    prod=get_object_or_404(Product,id=product_id)
    ct=Cart_List.objects.get(cart_id=c_id(request))
    cart_item=Cart_Items.objects.get(product=prod,cart=ct)
    cart_item.delete()
    return redirect('cart_details')

def min_cart(request,product_id):
    prod=get_object_or_404(Product,id=product_id)
    ct=Cart_List.objects.get(cart_id=c_id(request))
    c_items=Cart_Items.objects.get(product=prod,cart=ct)
    if c_items.quantity>1:
        c_items.quantity-=1
        c_items.save()
    else:
        c_items.delete()
    return redirect('cart_details')

def clear_cart(request):
    ct=Cart_List.objects.get(cart_id=c_id(request))
    cart_items=Cart_Items.objects.filter(cart_id=ct)
    cart_items.delete()
    return redirect('cart_details')
