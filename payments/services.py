import logging
import razorpay
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction

logger = logging.getLogger(__name__)

# Module-level variable to support mocking in the existing test suite
client = None

def get_razorpay_client():
    """
    Dynamically initializes and returns the Razorpay client from Django settings.
    Validates that all required Razorpay environment variables exist:
    - RAZORPAY_KEY_ID
    - RAZORPAY_KEY_SECRET
    - RAZORPAY_WEBHOOK_SECRET
    
    Raises:
        ValidationError: If any of the required settings are missing or invalid.
    """
    global client
    if client is not None:
        return client

    key_id = getattr(settings, 'RAZORPAY_KEY_ID', None)
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', None)
    webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', None)
    
    if not key_id:
        logger.error("RAZORPAY_KEY_ID is missing from settings.")
        raise ValidationError("Razorpay API credentials are not configured: RAZORPAY_KEY_ID is missing.")
    if not key_secret:
        logger.error("RAZORPAY_KEY_SECRET is missing from settings.")
        raise ValidationError("Razorpay API credentials are not configured: RAZORPAY_KEY_SECRET is missing.")
    if not webhook_secret:
        logger.error("RAZORPAY_WEBHOOK_SECRET is missing from settings.")
        raise ValidationError("Razorpay API credentials are not configured: RAZORPAY_WEBHOOK_SECRET is missing.")
        
    try:
        # TODO: Later phases will use the initialized client for checkout integrations and webhooks.
        return razorpay.Client(auth=(key_id, key_secret))
    except Exception as e:
        logger.exception("Failed to initialize Razorpay client.")
        raise ValidationError(f"Failed to initialize Razorpay client: {str(e)}")

def create_razorpay_order(order):
    """
    Creates a Razorpay order for the specified order.
    The amount is in paise (total_amount * 100).
    """
    global client
    local_client = client or get_razorpay_client()
    data = {
        "amount": int(order.total_amount * 100),
        "currency": "INR",
        "receipt": f"receipt_{order.order_number}",
        "payment_capture": 1
    }
    try:
        # TODO: Implement checkout integration in subsequent phase
        razorpay_order = local_client.order.create(data=data)
        logger.info(f"Successfully created Razorpay order for Order ID {order.id}")
        return razorpay_order
    except Exception as e:
        logger.exception(f"Razorpay order creation failed for Order ID {order.id}")
        raise ValidationError(f"Razorpay order creation failed: {str(e)}")

def verify_razorpay_signature(data):
    """
    Verifies the Razorpay payment signature.
    """
    global client
    local_client = client or get_razorpay_client()
    try:
        # TODO: Implement signature verification callbacks and checks in subsequent phase
        local_client.utility.verify_payment_signature(data)
        logger.info("Razorpay payment signature verified successfully.")
        return True
    except Exception as e:
        logger.warning(f"Razorpay payment signature verification failed: {str(e)}")
        return False

def handle_payment_success(order, payment_id=None, signature=None):
    """
    Idempotent method to handle successful payment.
    Updates statuses and timestamps. Does NOT touch inventory since it is already reserved.
    """
    # TODO: Add post-payment hooks, signals, or custom payment processing notifications in subsequent phase.
    if order.payment_status == 'PAID':
        return order

    with transaction.atomic():
        order.payment_status = 'PAID'
        order.status = 'PROCESSING'
        if payment_id:
            order.razorpay_payment_id = payment_id
        if signature:
            order.razorpay_signature = signature
        order.paid_at = timezone.now()
        order.save(update_fields=['payment_status', 'status', 'razorpay_payment_id', 'razorpay_signature', 'paid_at'])
        logger.info(f"Order ID {order.id} payment successfully processed and transitioned to PROCESSING.")
    
    try:
        from notifications.services import send_payment_success_email
        send_payment_success_email(order)
    except Exception as e:
        logger.exception(f"Error sending payment success email: {str(e)}")
        
    return order

def handle_payment_failure(order):
    """
    Idempotent method to handle payment failure.
    Does NOT restore stock; restoration is handled by expire_orders cron command.
    """
    # TODO: Add post-failure event alerts or log analysis hooks in subsequent phase.
    if order.payment_status == 'FAILED' or order.status == 'PAYMENT_FAILED':
        return order

    with transaction.atomic():
        order.payment_status = 'FAILED'
        order.status = 'PAYMENT_FAILED'
        order.save(update_fields=['payment_status', 'status'])
        logger.info(f"Order ID {order.id} payment failed and transitioned to PAYMENT_FAILED.")
        
    try:
        from notifications.services import send_payment_failed_email
        send_payment_failed_email(order)
    except Exception as e:
        logger.exception(f"Error sending payment failure email: {str(e)}")
        
    return order
