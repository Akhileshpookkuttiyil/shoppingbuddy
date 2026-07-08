from django.db import models
from django.conf import settings
from django.db.models import Q
from orders.models import Order, OrderItem

class ReturnRequest(models.Model):
    STATUS_CHOICES = (
        ('REQUESTED', 'Requested'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('REFUND_PROCESSING', 'Refund Processing'),
        ('REFUNDED', 'Refunded'),
        ('CANCELLED', 'Cancelled'),
    )

    REASON_CHOICES = (
        ('DAMAGED', 'Damaged'),
        ('WRONG_ITEM', 'Wrong Item'),
        ('DEFECTIVE', 'Defective'),
        ('NOT_AS_DESCRIBED', 'Not as Described'),
        ('QUALITY_ISSUE', 'Quality Issue'),
        ('SIZE_ISSUE', 'Size Issue'),
        ('CHANGED_MIND', 'Changed Mind'),
        ('OTHER', 'Other'),
    )

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='return_requests')
    order_item = models.ForeignKey(OrderItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='return_requests')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='return_requests')
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='REQUESTED', db_index=True)
    
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_returns')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    inventory_restored = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=["order", "order_item"],
                condition=Q(
                    status__in=[
                        "REQUESTED",
                        "UNDER_REVIEW",
                        "APPROVED",
                        "REFUND_PROCESSING",
                    ]
                ),
                name="unique_active_return_request",
            )
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['user']),
            models.Index(fields=['order']),
        ]

    def __str__(self):
        return f"Return {self.id} for Order {self.order.id}"

class ReturnAttachment(models.Model):
    return_request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name='attachments')
    image = models.ImageField(upload_to='return_attachments/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment {self.id} for ReturnRequest {self.return_request.id}"

class OrderAuditLog(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=100)
    old_status = models.CharField(max_length=50, null=True, blank=True)
    new_status = models.CharField(max_length=50, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f"Audit {self.action} on Order {self.order.id} at {self.created_at}"
