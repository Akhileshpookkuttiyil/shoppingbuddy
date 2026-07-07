import razorpay
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from orders.models import Order

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def create_razorpay_order(order):
    """
    Creates a Razorpay order for the specified order.
    The amount is in paise (total_amount * 100).
    """
    data = {
        "amount": int(order.total_amount * 100),
        "currency": "INR",
        "receipt": f"receipt_{order.order_number}",
        "payment_capture": 1
    }
    try:
        razorpay_order = client.order.create(data=data)
        return razorpay_order
    except Exception as e:
        raise ValidationError(f"Razorpay order creation failed: {str(e)}")

def verify_razorpay_signature(data):
    """
    Verifies the Razorpay payment signature.
    """
    try:
        client.utility.verify_payment_signature(data)
        return True
    except Exception:
        return False

def handle_payment_success(order, payment_id=None, signature=None):
    """
    Idempotent method to handle successful payment.
    Updates statuses and timestamps. Does NOT touch inventory since it is already reserved.
    """
    if order.payment_status == 'PAID':
        return order

    order.payment_status = 'PAID'
    order.status = 'PROCESSING'
    if payment_id:
        order.razorpay_payment_id = payment_id
    if signature:
        order.razorpay_signature = signature
    order.paid_at = timezone.now()
    order.save(update_fields=['payment_status', 'status', 'razorpay_payment_id', 'razorpay_signature', 'paid_at'])
    return order

def handle_payment_failure(order):
    """
    Idempotent method to handle payment failure.
    Does NOT restore stock; restoration is handled by expire_orders cron command.
    """
    if order.payment_status == 'FAILED' or order.status == 'PAYMENT_FAILED':
        return order

    order.payment_status = 'FAILED'
    order.status = 'PAYMENT_FAILED'
    order.save(update_fields=['payment_status', 'status'])
    return order
