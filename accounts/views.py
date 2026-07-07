from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import JsonResponse
from .forms import RegistrationForm, UserAddressForm
from .models import UserAddress

def is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')

def login(request):
    if request.user.is_authenticated:
        if is_ajax(request):
            return JsonResponse({'success': True, 'user': {'name': request.user.username, 'is_authenticated': True}})
        return redirect('/')
        
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            
            if is_ajax(request):
                return JsonResponse({
                    'success': True,
                    'user': {
                        'name': user.first_name or user.username,
                        'is_authenticated': True
                    }
                })
            
            # Prevent Open Redirect vulnerability
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure()
            ):
                return redirect(next_url)
            return redirect('/')
        else:
            if is_ajax(request):
                return JsonResponse({'success': False, 'errors': dict(form.errors)}, status=400)
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def register(request):
    if request.user.is_authenticated:
        if is_ajax(request):
            return JsonResponse({'success': True, 'user': {'name': request.user.username, 'is_authenticated': True}})
        return redirect('/')
        
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            if is_ajax(request):
                auth_login(request, user)
                return JsonResponse({
                    'success': True,
                    'user': {
                        'name': user.first_name or user.username,
                        'is_authenticated': True
                    }
                })
            return redirect('login')
        else:
            if is_ajax(request):
                return JsonResponse({'success': False, 'errors': dict(form.errors)}, status=400)
    else:
        form = RegistrationForm()
    return render(request, 'register.html', {'form': form})

def logout(request):
    auth_logout(request)
    return redirect('/')

from django.contrib.auth.decorators import login_required

@login_required
def address_list(request):
    addresses = request.user.addresses.filter(is_active=True).order_by('-is_default', '-updated_at')
    return render(request, 'account/addresses.html', {'addresses': addresses})

@login_required
def add_address(request):
    if request.method == 'POST':
        form = UserAddressForm(request.POST, user=request.user)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            return redirect('address_list')
    else:
        form = UserAddressForm(user=request.user)
    return render(request, 'account/address_form.html', {'form': form})

@login_required
def edit_address(request, address_id):
    address = get_object_or_404(UserAddress, pk=address_id, user=request.user, is_active=True)
    if request.method == 'POST':
        form = UserAddressForm(request.POST, instance=address, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('address_list')
    else:
        form = UserAddressForm(instance=address, user=request.user)
    return render(request, 'account/address_form.html', {'form': form})

from django.views.decorators.http import require_POST
from django.db import transaction

@login_required
@require_POST
def delete_address(request, address_id):
    address = get_object_or_404(UserAddress, pk=address_id, user=request.user, is_active=True)
    
    with transaction.atomic():
        # Rule 2: If address is default and other active addresses exist, promote another one
        if address.is_default:
            other_active = request.user.addresses.filter(is_active=True).exclude(pk=address.pk).order_by('-updated_at')
            if other_active.exists():
                new_default = other_active.first()
                new_default.is_default = True
                new_default.save(update_fields=['is_default'])
        
        # Rule 3: Soft delete
        address.is_active = False
        address.is_default = False
        address.save(update_fields=['is_active', 'is_default'])
        
    return redirect('address_list')




