from django.urls import path
from . import views

urlpatterns=[
    path('login/',views.login,name='login'),
    path('register/',views.register,name='register'),
    path('logout/',views.logout,name='logout'),
    path('addresses/', views.address_list, name='address_list'),
    path('addresses/add/', views.add_address, name='add_address'),
    ]
