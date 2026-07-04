from django.shortcuts import render,redirect
from django.contrib.auth.models import User,auth
# Create your views here.

def login(request):
    if request.method=='POST':
        username=request.POST['username']
        password=request.POST['password']
        user=auth.authenticate(username=username,password=password)
        if user is not None:
            auth.login(request,user)
            print('login successfull')
            return redirect('/')
        else:
            print('login failed')
            return redirect('login')
    return render(request,'login.html')

def register(request):
    if request.method=='POST':
        firstname=request.POST['firstname']
        lastname=request.POST['lastname']
        username=request.POST['username']
        email=request.POST['email']
        password=request.POST['password1']
        confirm_password=request.POST['password2']
        if password==confirm_password:
            user=User.objects.create_user(first_name=firstname,last_name=lastname,username=username,email=email,password=password)
            user.save()
            print("new user")
            return redirect('login')
        else:
            return redirect('register')
    return render(request,'register.html')

def logout(request):
    auth.logout(request)
    return redirect('/')
