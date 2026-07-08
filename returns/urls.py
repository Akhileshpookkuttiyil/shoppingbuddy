from django.urls import path
from . import views

app_name = 'returns'

urlpatterns = [
    path('cancel/<int:order_id>/', views.cancel_order_view, name='cancel_order'),
    path('request/<int:order_id>/', views.request_return_view, name='request_return'),
]
