import logging
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from orders.models import Order, OrderItem
from shop.models import Product
from .models import ReturnRequest, ReturnAttachment, OrderAuditLog

logger = logging.getLogger(__name__)

ALLOWED_RETURN_TRANSITIONS = {
    "REQUESTED": ["UNDER_REVIEW", "CANCELLED"],
    "UNDER_REVIEW": ["APPROVED", "REJECTED"],
    "APPROVED": ["REFUND_PROCESSING"],
    "REFUND_PROCESSING": ["REFUNDED"],
}

def validate_return_transition(return_request, target_status):
    """Validates if the target status is allowed from the current state."""
    current = return_request.status
    allowed = ALLOWED_RETURN_TRANSITIONS.get(current, [])
    if target_status not in allowed:
        logger.warning(f"Invalid return state transition from {current} to {target_status} requested.")
        raise ValidationError(f"Transition from {current} to {target_status} is not allowed.")

def create_audit_log(order, user, action, old_status=None, new_status=None, notes=None):
    """Idempotently logs order status changes and transactions."""
    log = OrderAuditLog.objects.create(
        order=order,
        user=user,
        action=action,
        old_status=old_status,
        new_status=new_status,
        notes=notes
    )
    logger.info(f"Audit Log Created: {action} on Order {order.id} (user: {user})")
    return log

def cancel_order(order, user):
    """
    Cancels an order, releases inventory back, and logs status change.
    Allowed only if PENDING_PAYMENT or PAYMENT_FAILED.
    """
    if order.status not in ['PENDING_PAYMENT', 'PAYMENT_FAILED']:
        raise ValidationError("Order can only be cancelled in PENDING_PAYMENT or PAYMENT_FAILED status.")

    with transaction.atomic():
        # Lock order
        locked_order = Order.objects.select_for_update().get(pk=order.id)
        if locked_order.status == 'CANCELLED':
            return locked_order # Idempotent check

        old_status = locked_order.status
        locked_order.status = 'CANCELLED'
        locked_order.payment_status = 'FAILED'
        locked_order.save(update_fields=['status', 'payment_status'])

        # Lock and restore stock immediately
        for item in locked_order.items.select_related('product').all():
            product = Product.objects.select_for_update().get(pk=item.product.id)
            product.stock += item.quantity
            product.save(update_fields=['stock'])

        create_audit_log(locked_order, user, "Order Cancelled", old_status, "CANCELLED")
        create_audit_log(locked_order, user, "Inventory Restored", notes=f"Restored inventory for order {locked_order.order_number}")
        
    return locked_order

def request_return(order, user, reason, description, order_item=None, images=None):
    """
    Creates a customer return request for an order or item.
    Allowed only after order status is DELIVERED.
    """
    if order.status != 'DELIVERED':
        raise ValidationError("Returns can only be requested after the order has been DELIVERED.")

    if order.user != user:
        raise ValidationError("You do not own this order.")

    # Enforce database UniqueConstraint prevention in Python
    active_requests = ReturnRequest.objects.filter(
        order=order,
        order_item=order_item,
        status__in=["REQUESTED", "UNDER_REVIEW", "APPROVED", "REFUND_PROCESSING"]
    )
    if active_requests.exists():
        raise ValidationError("An active return request already exists for this order/item.")

    with transaction.atomic():
        return_request = ReturnRequest.objects.create(
            order=order,
            order_item=order_item,
            user=user,
            reason=reason,
            description=description,
            status='REQUESTED'
        )

        if images:
            for image in images:
                ReturnAttachment.objects.create(return_request=return_request, image=image)

        create_audit_log(order, user, "Return Requested", notes=f"Return requested for reason: {reason}")

    try:
        from notifications.services import send_return_requested_email
        send_return_requested_email(order)
    except Exception as e:
        logger.exception(f"Failed to send return requested email: {str(e)}")

    return return_request

def approve_return(return_request, reviewer):
    """Approves a customer return request."""
    validate_return_transition(return_request, 'APPROVED')
    
    with transaction.atomic():
        return_request = ReturnRequest.objects.select_for_update().get(pk=return_request.id)
        old_status = return_request.status
        return_request.status = 'APPROVED'
        return_request.reviewed_by = reviewer
        return_request.reviewed_at = timezone.now()
        return_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

        create_audit_log(return_request.order, reviewer, "Return Approved", old_status, "APPROVED")

    try:
        from notifications.services import send_return_approved_email
        send_return_approved_email(return_request.order)
    except Exception as e:
        logger.exception(f"Failed to send return approved email: {str(e)}")

    return return_request

def reject_return(return_request, reviewer, admin_notes):
    """Rejects a customer return request."""
    validate_return_transition(return_request, 'REJECTED')
    
    with transaction.atomic():
        return_request = ReturnRequest.objects.select_for_update().get(pk=return_request.id)
        old_status = return_request.status
        return_request.status = 'REJECTED'
        return_request.reviewed_by = reviewer
        return_request.reviewed_at = timezone.now()
        return_request.admin_notes = admin_notes
        return_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'admin_notes'])

        create_audit_log(return_request.order, reviewer, "Return Rejected", old_status, "REJECTED", notes=admin_notes)

    try:
        from notifications.services import send_return_rejected_email
        send_return_rejected_email(return_request.order)
    except Exception as e:
        logger.exception(f"Failed to send return rejected email: {str(e)}")

    return return_request

def start_refund(return_request, reviewer):
    """Initiates the refund status update."""
    validate_return_transition(return_request, 'REFUND_PROCESSING')
    
    with transaction.atomic():
        return_request = ReturnRequest.objects.select_for_update().get(pk=return_request.id)
        old_status = return_request.status
        return_request.status = 'REFUND_PROCESSING'
        return_request.save(update_fields=['status'])

        create_audit_log(return_request.order, reviewer, "Refund Started", old_status, "REFUND_PROCESSING")

    try:
        from notifications.services import send_refund_started_email
        send_refund_started_email(return_request.order)
    except Exception as e:
        logger.exception(f"Failed to send refund started email: {str(e)}")

    return return_request

def complete_refund(return_request, reviewer):
    """Completes the refund, logs transactions, and restores stock."""
    validate_return_transition(return_request, 'REFUNDED')
    
    with transaction.atomic():
        return_request = ReturnRequest.objects.select_for_update().get(pk=return_request.id)
        old_status = return_request.status
        return_request.status = 'REFUNDED'
        return_request.save(update_fields=['status'])

        # Process payment refund status change
        process_refund(return_request)

        # Restore inventory
        restore_inventory(return_request)

        create_audit_log(return_request.order, reviewer, "Refund Completed", old_status, "REFUNDED")
        create_audit_log(return_request.order, reviewer, "Inventory Restored", notes="Restored stock after refund complete")

    try:
        from notifications.services import send_refund_completed_email
        send_refund_completed_email(return_request.order)
    except Exception as e:
        logger.exception(f"Failed to send refund completed email: {str(e)}")

    return return_request

def process_refund(return_request):
    """
    Idempotent refund processor (COD vs Razorpay mock gateway implementation).
    """
    order = return_request.order
    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.id)
        if locked_order.payment_status == 'REFUNDED':
            return locked_order

        if locked_order.payment_method == 'RAZORPAY':
            # TODO: Integrate with live Razorpay refunds SDK API in subsequent phase:
            # try:
            #     from payments.services import get_razorpay_client
            #     client = get_razorpay_client()
            #     client.refund.create(data={
            #         "payment_id": locked_order.razorpay_payment_id,
            #         "amount": int(locked_order.total_amount * 100)
            #     })
            # except Exception as ex:
            #     logger.error(f"Razorpay gateway refund error for order {locked_order.id}: {str(ex)}")
            #     raise
            pass

        locked_order.payment_status = 'REFUNDED'
        locked_order.status = 'REFUNDED'
        locked_order.save(update_fields=['payment_status', 'status'])
        
    return locked_order

def restore_inventory(return_request):
    """
    Safely restores stock exactly once using select_for_update() database lock.
    """
    with transaction.atomic():
        locked_req = ReturnRequest.objects.select_for_update().get(pk=return_request.id)
        if locked_req.inventory_restored:
            return

        if locked_req.order_item:
            product = Product.objects.select_for_update().get(pk=locked_req.order_item.product.id)
            product.stock += locked_req.order_item.quantity
            product.save(update_fields=['stock'])
        else:
            for item in locked_req.order.items.select_related('product').all():
                product = Product.objects.select_for_update().get(pk=item.product.id)
                product.stock += item.quantity
                product.save(update_fields=['stock'])

        locked_req.inventory_restored = True
        locked_req.save(update_fields=['inventory_restored'])
