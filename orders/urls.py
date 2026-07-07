from django.urls import path
from . import views

urlpatterns = [
    path('', views.checkout, name='checkout'),
    path('<int:order_id>/confirmation/', views.order_confirmation, name='order_confirmation'),
]
