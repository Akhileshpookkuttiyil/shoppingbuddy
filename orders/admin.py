from django.contrib import admin
from .models import Order, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    raw_id_fields = ['product']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'shipping_full_name', 'total_amount', 'status', 'payment_method', 'payment_status', 'created_at']
    list_filter = ['status', 'payment_method', 'payment_status', 'created_at']
    search_fields = ['order_number', 'shipping_full_name', 'user__username', 'user__email']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    inlines = [OrderItemInline]
    
    readonly_fields = [
        'shipping_full_name',
        'shipping_phone',
        'shipping_address_line_1',
        'shipping_address_line_2',
        'shipping_landmark',
        'shipping_city',
        'shipping_state',
        'shipping_country',
        'shipping_postal_code',
        'expires_at',
    ]

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'product', 'price', 'quantity']
    raw_id_fields = ['order', 'product']

