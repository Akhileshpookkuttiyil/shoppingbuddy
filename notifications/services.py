import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

logger = logging.getLogger(__name__)

def _get_order_context(order):
    """Helper to build context variables including order items calculation."""
    items_data = []
    for item in order.items.all():
        items_data.append({
            'name': item.product.name,
            'quantity': item.quantity,
            'price': item.price,
            'total': item.price * item.quantity
        })
    return {
        'order': order,
        'items': items_data
    }

def _send_email_safe(subject, template_name, context, recipient_email):
    """
    Safely renders and sends an HTML/Text email using EmailMultiAlternatives.
    Gracefully handles all SMTP exceptions and logs failures.
    """
    try:
        html_content = render_to_string(template_name, context)
        text_content = strip_tags(html_content)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@shoppingbuddy.com')

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[recipient_email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        logger.info(f"Successfully sent email '{subject}' to {recipient_email}")
        return True
    except Exception as e:
        logger.exception(f"Failed to send email '{subject}' to {recipient_email}: {str(e)}")
        return False

def send_order_confirmation_email(order):
    """Sends order confirmation notification."""
    recipient = order.user.email if order.user else 'customer@example.com'
    subject = f"Order Confirmation - {order.order_number}"
    context = _get_order_context(order)
    return _send_email_safe(subject, 'emails/order_confirmation.html', context, recipient)

def send_payment_success_email(order):
    """Sends payment success notification."""
    recipient = order.user.email if order.user else 'customer@example.com'
    subject = f"Payment Successful - Order {order.order_number}"
    context = _get_order_context(order)
    return _send_email_safe(subject, 'emails/payment_success.html', context, recipient)

def send_payment_failed_email(order):
    """Sends payment failed notification."""
    recipient = order.user.email if order.user else 'customer@example.com'
    subject = f"Payment Failed - Order {order.order_number}"
    context = _get_order_context(order)
    return _send_email_safe(subject, 'emails/payment_failed.html', context, recipient)

def send_refund_email(order):
    """Sends refund notification."""
    recipient = order.user.email if order.user else 'customer@example.com'
    subject = f"Refund Processed - Order {order.order_number}"
    context = _get_order_context(order)
    return _send_email_safe(subject, 'emails/refund_processed.html', context, recipient)
