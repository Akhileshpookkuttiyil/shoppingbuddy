from django.urls import path
from . import views
urlpatterns=[
    path('',views.home,name='home'),
    path('search',views.search,name="search"),
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/toggle/<int:product_id>/', views.toggle_wishlist, name='toggle_wishlist'),
    path('<slug:c_slug>/',views.home,name="product_category"),
    path('<slug:c_slug>/<slug:p_slug>',views.detail,name="product_detail"),
    ]

