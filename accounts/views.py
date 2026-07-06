from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import JsonResponse
from .forms import RegistrationForm

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
