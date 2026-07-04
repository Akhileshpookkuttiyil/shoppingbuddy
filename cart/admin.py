from django.contrib import admin
from .models import Cart_List, Cart_Items

class CartItemsInline(admin.TabularInline):
    model = Cart_Items
    extra = 0
    readonly_fields = ['product', 'quantity', 'active']
    can_delete = False
    
    # Do not allow adding new items directly from the cart admin
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Cart_List)
class CartListAdmin(admin.ModelAdmin):
    list_display = ['cart_id', 'date_added', 'total_items']
    readonly_fields = ['cart_id', 'date_added']
    search_fields = ['cart_id']
    date_hierarchy = 'date_added'
    inlines = [CartItemsInline]
    list_per_page = 20
    
    def total_items(self, obj):
        return obj.items.count()
    total_items.short_description = "Total Unique Items"

@admin.register(Cart_Items)
class CartItemsAdmin(admin.ModelAdmin):
    list_display = ['product', 'cart_link', 'quantity', 'active']
    list_filter = ['active']
    search_fields = ['product__name', 'cart__cart_id']
    readonly_fields = ['product', 'cart', 'quantity']
    list_select_related = ['product', 'cart']
    list_per_page = 20
    
    def cart_link(self, obj):
        return obj.cart.cart_id
    cart_link.short_description = 'Session Cart ID'

