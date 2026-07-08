from django.urls import path
from . import views

app_name = 'returns_admin'

urlpatterns = [
    path('', views.admin_return_list, name='list'),
    path('<int:request_id>/', views.admin_return_detail, name='detail'),
    path('<int:request_id>/approve/', views.admin_approve, name='approve'),
    path('<int:request_id>/reject/', views.admin_reject, name='reject'),
    path('<int:request_id>/start-refund/', views.admin_start_refund, name='start_refund'),
    path('<int:request_id>/complete-refund/', views.admin_complete_refund, name='complete_refund'),
]
