from django.contrib import admin
from .models import ReturnRequest, ReturnAttachment, OrderAuditLog

@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'user', 'reason', 'status', 'created_at')
    list_filter = ('status', 'reason')
    search_fields = ('order__order_number', 'user__email', 'user__username')

@admin.register(ReturnAttachment)
class ReturnAttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'return_request', 'created_at')

@admin.register(OrderAuditLog)
class OrderAuditLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'user', 'action', 'new_status', 'created_at')
    list_filter = ('action',)
    search_fields = ('order__order_number', 'user__username')
