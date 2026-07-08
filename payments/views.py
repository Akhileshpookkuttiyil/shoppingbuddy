import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from orders.models import Order
from . import services

logger = logging.getLogger(__name__)

@login_required
def payment_page(request, order_id):
    """
    Renders the checkout form for Razorpay payments.
    Includes security checks to block unauthorized access, expired, cancelled, or paid orders.
    """
    order = get_object_or_404(Order, pk=order_id, user=request.user)

    if order.status in ['CANCELLED', 'PAYMENT_EXPIRED', 'REFUNDED'] or order.payment_status in ['PAID', 'REFUNDED'] or order.status == 'PAID':
        return HttpResponseBadRequest("Order is in a final, cancelled, expired, already paid, or refunded state.")

    context = {
        'order': order,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'amount_in_paise': int(order.total_amount * 100),
    }
    return render(request, 'payment.html', context)

from django.views.decorators.http import require_POST

@csrf_exempt
@require_POST
@login_required
def verify_payment(request):
    """
    Handles payment verification callback.
    """
    razorpay_order_id = request.POST.get('razorpay_order_id', '').strip()
    razorpay_payment_id = request.POST.get('razorpay_payment_id', '').strip()
    razorpay_signature = request.POST.get('razorpay_signature', '').strip()

    if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
        return HttpResponseBadRequest("Missing required payment verification fields.")

    order = get_object_or_404(Order, razorpay_order_id=razorpay_order_id, user=request.user)

    # Prevent verification of orders that are already paid, cancelled, expired, or refunded
    if order.status in ['CANCELLED', 'PAYMENT_EXPIRED', 'REFUNDED'] or order.payment_status in ['PAID', 'REFUNDED'] or order.status == 'PAID':
        return HttpResponseBadRequest("Order is in a final, cancelled, expired, already paid, or refunded state.")

    data = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }

    if services.verify_razorpay_signature(data):
        services.handle_payment_success(order, payment_id=razorpay_payment_id, signature=razorpay_signature)
    else:
        services.handle_payment_failure(order)

    return redirect('order_confirmation', order_id=order.id)

@login_required
def payment_cancel(request, order_id):
    """
    Handles cancellation when the user dismisses the payment modal.
    """
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    if order.status == 'PENDING_PAYMENT':
        services.handle_payment_failure(order)
    return redirect('order_confirmation', order_id=order.id)

@require_POST
@login_required
def payment_retry(request, order_id):
    """
    Retries payment on an existing order. Regenerates Razorpay order.
    """
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    
    # Reject retry for invalid statuses
    if order.status in ['PAID', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'REFUNDED', 'PAYMENT_EXPIRED'] or order.payment_status == 'PAID':
        return HttpResponseBadRequest("Retries are not allowed for this order status.")

    if order.status != 'PAYMENT_FAILED' and order.payment_status != 'FAILED':
        return HttpResponseBadRequest("Only failed payments can be retried.")

    try:
        rz_order = services.create_razorpay_order(order)
        order.razorpay_order_id = rz_order['id']
        order.status = 'PENDING_PAYMENT'
        order.payment_status = 'PENDING'
        
        # Clear previous payment verification details
        order.razorpay_payment_id = None
        order.razorpay_signature = None
        order.paid_at = None
        
        order.save(update_fields=[
            'razorpay_order_id', 'status', 'payment_status',
            'razorpay_payment_id', 'razorpay_signature', 'paid_at'
        ])
    except Exception as e:
        return HttpResponseBadRequest(f"Failed to retry payment: {str(e)}")

    return redirect('payments:payment_page', order_id=order.id)

@csrf_exempt
def razorpay_webhook(request):
    """
    Idempotent webhook handler with signature verification.
    """
    if request.method != 'POST':
        logger.warning(f"Webhook received with invalid method: {request.method}")
        return HttpResponse("Method Not Allowed", status=405)

    signature = request.headers.get('X-Razorpay-Signature', '')
    if not signature:
        logger.warning("Webhook signature header is missing.")
        return HttpResponse("Missing Webhook Signature", status=400)

    body = request.body.decode('utf-8')
    
    # Try fetching webhook secret and client dynamically
    try:
        client = services.get_razorpay_client()
        secret = settings.RAZORPAY_WEBHOOK_SECRET
    except Exception as e:
        logger.exception("Failed to initialize client or settings during webhook processing.")
        return HttpResponse("Configuration Error", status=500)

    # Verify signature
    try:
        client.utility.verify_webhook_signature(body, signature, secret)
    except Exception as e:
        logger.warning(f"Webhook signature verification failed: {str(e)}")
        return HttpResponse("Invalid Webhook Signature", status=400)

    # Parse JSON body
    try:
        event_data = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("Webhook payload is not valid JSON.")
        return HttpResponse("Invalid JSON payload", status=400)

    event = event_data.get('event')
    payload = event_data.get('payload', {})
    
    if not event:
        logger.warning("Webhook payload is missing 'event' key.")
        return HttpResponse("Missing event key", status=400)

    logger.info(f"Processing Razorpay webhook event: {event}")

    # Handle events
    if event in ['payment.captured', 'payment.authorized']:
        payment = payload.get('payment', {}).get('entity', {})
        razorpay_order_id = payment.get('order_id')
        razorpay_payment_id = payment.get('id')
        razorpay_signature = payment.get('signature', '')

        if not razorpay_order_id or not razorpay_payment_id:
            logger.warning(f"Webhook {event} missing order_id or payment_id.")
            return HttpResponse("Missing payload fields", status=400)

        order = Order.objects.filter(razorpay_order_id=razorpay_order_id).first()
        if not order:
            logger.warning(f"Order not found for razorpay_order_id: {razorpay_order_id}")
            return HttpResponse("Order not found", status=404)

        # Idempotency check: Already processed
        if order.payment_status == 'PAID' or order.status == 'PAID':
            logger.info(f"Order {order.id} is already marked as PAID. Ignoring duplicate event {event}.")
            return HttpResponse("Duplicate event ignored", status=200)

        services.handle_payment_success(order, payment_id=razorpay_payment_id, signature=razorpay_signature)
        logger.info(f"Webhook {event} successfully processed for Order {order.id}.")
            
    elif event == 'payment.failed':
        payment = payload.get('payment', {}).get('entity', {})
        razorpay_order_id = payment.get('order_id')
        
        if not razorpay_order_id:
            logger.warning("Webhook payment.failed missing razorpay_order_id.")
            return HttpResponse("Missing payload fields", status=400)

        order = Order.objects.filter(razorpay_order_id=razorpay_order_id).first()
        if not order:
            logger.warning(f"Order not found for razorpay_order_id: {razorpay_order_id}")
            return HttpResponse("Order not found", status=404)

        # Idempotency check: Already failed
        if order.payment_status == 'FAILED' or order.status == 'PAYMENT_FAILED':
            logger.info(f"Order {order.id} already failed. Ignoring duplicate event {event}.")
            return HttpResponse("Duplicate event ignored", status=200)

        services.handle_payment_failure(order)
        logger.info(f"Webhook {event} successfully processed for Order {order.id}.")
            
    elif event == 'refund.processed':
        refund = payload.get('refund', {}).get('entity', {})
        payment_id = refund.get('payment_id')
        
        if not payment_id:
            logger.warning("Webhook refund.processed missing payment_id.")
            return HttpResponse("Missing payload fields", status=400)

        order = Order.objects.filter(razorpay_payment_id=payment_id).first()
        if not order:
            logger.warning(f"Order not found for razorpay_payment_id: {payment_id}")
            return HttpResponse("Order not found", status=404)

        # Idempotency check: Already refunded
        if order.payment_status == 'REFUNDED' or order.status == 'REFUNDED':
            logger.info(f"Order {order.id} already refunded. Ignoring duplicate event {event}.")
            return HttpResponse("Duplicate event ignored", status=200)

        with transaction.atomic():
            order.payment_status = 'REFUNDED'
            order.status = 'REFUNDED'
            order.save(update_fields=['payment_status', 'status'])
            
        try:
            from notifications.services import send_refund_email
            send_refund_email(order)
        except Exception as e:
            logger.exception(f"Error sending refund email: {str(e)}")

        logger.info(f"Webhook refund.processed successfully processed for Order {order.id}.")
        
    else:
        logger.info(f"Ignored unsupported webhook event: {event}")
        return HttpResponse("Unsupported event ignored", status=200)

    return HttpResponse("OK", status=200)
