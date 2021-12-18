from django.urls import path
from . import views
urlpatterns=[
    path('',views.home,name='home'),
    path('search',views.search,name="search"),
    path('<slug:c_slug>/',views.home,name="product_category"),
    path('detail',views.detail,name="detail"),
    path('<slug:c_slug>/<slug:p_slug>',views.detail,name="product_detail"),
    ]

