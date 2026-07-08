"""shoppingbuddy URL Configuration"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from orders import views as order_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('dashboard/', include('dashboard.urls')),
    path('accounts/', include('accounts.urls')),
    path('account/', include('accounts.urls')),
    path('cart/', include('cart.urls')),
    path('checkout/', order_views.checkout, name='checkout'),
    path('checkout/<int:order_id>/confirmation/', order_views.order_confirmation, name='order_confirmation'),
    path('account/orders/', include('orders.urls')),
    path('payments/', include('payments.urls')),
    path('returns/', include('returns.urls')),
    path('dashboard/returns/', include('returns.admin_urls')),
    path('', include('shop.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
