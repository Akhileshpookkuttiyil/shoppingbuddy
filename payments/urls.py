from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('payment/<int:order_id>/', views.payment_page, name='payment_page'),
    path('verify/', views.verify_payment, name='verify_payment'),
    path('cancel/<int:order_id>/', views.payment_cancel, name='payment_cancel'),
    path('retry/<int:order_id>/', views.payment_retry, name='payment_retry'),
    path('webhook/razorpay/', views.razorpay_webhook, name='razorpay_webhook'),
]
