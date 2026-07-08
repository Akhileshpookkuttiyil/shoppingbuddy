from django.urls import path
from . import views

urlpatterns = [
    path('', views.my_orders, name='order_list'),
    path('history/', views.my_orders, name='order_list'),
    path('<int:order_id>/', views.order_detail, name='order_detail'),
]

