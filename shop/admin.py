from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from .models import Category, Product

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'product_count']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'slug']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Optimize product count via DB annotation rather than N+1 template queries
        return qs.annotate(product_count=Count('products'))
        
    def product_count(self, obj):
        return obj.product_count
    product_count.short_description = 'Total Products'
    product_count.admin_order_field = 'product_count'

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['thumbnail_preview', 'name', 'category', 'price', 'stock', 'in_stock_badge', 'created']
    list_editable = ['price', 'stock']
    list_filter = ['in_stock', 'category', 'created']
    search_fields = ['name', 'description', 'color', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created', 'thumbnail_preview']
    list_per_page = 20
    date_hierarchy = 'created'
    autocomplete_fields = ['category']
    list_select_related = ['category']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'category', 'description', 'color')
        }),
        ('Pricing & Inventory', {
            'fields': ('price', 'stock', 'in_stock')
        }),
        ('Media', {
            'fields': ('image', 'thumbnail_preview')
        }),
        ('Meta Data', {
            'fields': ('created',),
            'classes': ('collapse',)
        }),
    )
    
    def thumbnail_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 45px; height: 45px; object-fit: cover; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);" />',
                obj.image.url
            )
        return format_html('<span style="color: #999;">No image</span>')
    thumbnail_preview.short_description = 'Preview'

    def in_stock_badge(self, obj):
        if obj.in_stock and obj.stock > 0:
            return format_html('<span style="color: #10B981; font-weight: 600;">In Stock</span>')
        elif obj.in_stock and obj.stock <= 0:
            return format_html('<span style="color: #F59E0B; font-weight: 600;">Backordered</span>')
        return format_html('<span style="color: #EF4444; font-weight: 600;">Disabled</span>')
    in_stock_badge.short_description = 'Status'

