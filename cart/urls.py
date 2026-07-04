from django.urls import path
from . import views
urlpatterns=[
    path('CartDetails',views.cart_details,name='cart_details'),
    path('cartAdd/<int:product_id>',views.add_cart,name='cartAdd'),
    path('cartdel/<int:product_id>',views.del_cart,name='cartdel'),
    path('cartMin/<int:product_id>',views.min_cart,name="cartMin"),
    path('clear_cart',views.clear_cart,name="clear_cart"),
    ]

