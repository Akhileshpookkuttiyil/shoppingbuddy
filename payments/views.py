import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.conf import settings
from django.utils import timezone
from orders.models import Order
from . import services

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

@login_required
def payment_retry(request, order_id):
    """
    Retries payment on an existing order. Regenerates Razorpay order.
    """
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    
    if order.status != 'PAYMENT_FAILED' and order.payment_status != 'FAILED':
        return redirect('order_confirmation', order_id=order.id)

    try:
        rz_order = services.create_razorpay_order(order)
        order.razorpay_order_id = rz_order['id']
        order.status = 'PENDING_PAYMENT'
        order.payment_status = 'PENDING'
        order.save(update_fields=['razorpay_order_id', 'status', 'payment_status'])
    except Exception as e:
        return HttpResponseBadRequest(f"Failed to retry payment: {str(e)}")

    return redirect('payments:payment_page', order_id=order.id)

@csrf_exempt
def razorpay_webhook(request):
    """
    Idempotent webhook handler with signature verification.
    """
    signature = request.headers.get('X-Razorpay-Signature', '')
    body = request.body.decode('utf-8')
    secret = settings.RAZORPAY_WEBHOOK_SECRET

    try:
        services.client.utility.verify_webhook_signature(body, signature, secret)
    except Exception:
        return HttpResponse("Invalid Webhook Signature", status=400)

    try:
        event_data = json.loads(body)
    except json.JSONDecodeError:
        return HttpResponse("Invalid JSON payload", status=400)

    event = event_data.get('event')
    payload = event_data.get('payload', {})

    if event in ['payment.captured', 'payment.authorized']:
        payment = payload.get('payment', {}).get('entity', {})
        razorpay_order_id = payment.get('order_id')
        razorpay_payment_id = payment.get('id')
        
        order = Order.objects.filter(razorpay_order_id=razorpay_order_id).first()
        if order:
            services.handle_payment_success(order, payment_id=razorpay_payment_id)
            
    elif event == 'payment.failed':
        payment = payload.get('payment', {}).get('entity', {})
        razorpay_order_id = payment.get('order_id')
        
        order = Order.objects.filter(razorpay_order_id=razorpay_order_id).first()
        if order:
            services.handle_payment_failure(order)
            
    elif event == 'refund.processed':
        refund = payload.get('refund', {}).get('entity', {})
        payment_id = refund.get('payment_id')
        
        order = Order.objects.filter(razorpay_payment_id=payment_id).first()
        if order:
            if order.payment_status != 'REFUNDED':
                order.payment_status = 'REFUNDED'
                order.status = 'REFUNDED'
                order.save(update_fields=['payment_status', 'status'])

    return HttpResponse("OK", status=200)
