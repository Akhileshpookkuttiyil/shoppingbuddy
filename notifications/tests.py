import logging
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.core import mail
from django.contrib.auth.models import User
from orders.models import Order, OrderItem
from shop.models import Product, Category
from notifications.services import (
    send_order_confirmation_email,
    send_payment_success_email,
    send_payment_failed_email,
    send_refund_email
)

class NotificationEmailTest(TestCase):
    def setUp(self):
        self.username = 'testcustomer_notify'
        self.password = 'securepassword123'
        self.user = User.objects.create_user(username=self.username, password=self.password, email='cust_notify@example.com')
        
        self.category = Category.objects.create(name='Books', slug='books')
        self.product = Product.objects.create(
            name='Django Book', slug='django-book', price=200.00, stock=5, in_stock=True, category=self.category
        )
        
        self.order = Order.objects.create(
            user=self.user,
            order_number='SB-NOTIFY-001',
            payment_method='RAZORPAY',
            status='PENDING_PAYMENT',
            payment_status='PENDING',
            total_amount=400.00,
            shipping_full_name='Alice Smith',
            shipping_phone='1234567890',
            shipping_address_line_1='Street 456',
            shipping_city='Delhi',
            shipping_postal_code='110001',
            shipping_country='India'
        )
        OrderItem.objects.create(order=self.order, product=self.product, price=200.00, quantity=2)

    def test_send_order_confirmation_email_success(self):
        """Verify order confirmation email content, subject, recipients, and HTML structure."""
        mail.outbox = []
        res = send_order_confirmation_email(self.order)
        self.assertTrue(res)
        
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        
        # Verify subject and recipient
        self.assertEqual(email.subject, "Order Confirmation - SB-NOTIFY-001")
        self.assertEqual(email.to, ["cust_notify@example.com"])
        
        # Verify body contents (text and html version)
        self.assertIn("SB-NOTIFY-001", email.body)
        self.assertIn("PENDING", email.body)
        self.assertIn("PENDING_PAYMENT", email.body)
        self.assertIn("Alice Smith", email.body)
        
        # Verify HTML alternative
        self.assertEqual(len(email.alternatives), 1)
        html_content, content_type = email.alternatives[0]
        self.assertEqual(content_type, "text/html")
        self.assertIn("Django Book", html_content)
        self.assertIn("₹400.00", html_content)

    def test_send_payment_success_email_success(self):
        """Verify payment success email content, status, and markup."""
        self.order.status = 'PROCESSING'
        self.order.payment_status = 'PAID'
        self.order.save()
        
        mail.outbox = []
        res = send_payment_success_email(self.order)
        self.assertTrue(res)
        
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        
        self.assertEqual(email.subject, "Payment Successful - Order SB-NOTIFY-001")
        self.assertIn("PAID", email.body)
        self.assertIn("PROCESSING", email.body)

    def test_send_payment_failed_email_success(self):
        """Verify payment failure email content, status, and layout."""
        self.order.status = 'PAYMENT_FAILED'
        self.order.payment_status = 'FAILED'
        self.order.save()
        
        mail.outbox = []
        res = send_payment_failed_email(self.order)
        self.assertTrue(res)
        
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        
        self.assertEqual(email.subject, "Payment Failed - Order SB-NOTIFY-001")
        self.assertIn("FAILED", email.body)
        self.assertIn("PAYMENT_FAILED", email.body)

    def test_send_refund_email_success(self):
        """Verify refund processed email contains correct labels and structures."""
        self.order.status = 'REFUNDED'
        self.order.payment_status = 'REFUNDED'
        self.order.save()
        
        mail.outbox = []
        res = send_refund_email(self.order)
        self.assertTrue(res)
        
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        
        self.assertEqual(email.subject, "Refund Processed - Order SB-NOTIFY-001")
        self.assertIn("REFUNDED", email.body)

    @patch('django.core.mail.EmailMultiAlternatives.send')
    def test_email_smtp_failure_handling(self, mock_send):
        """Verify that SMTP exception does not crash the service and returns False."""
        mock_send.side_effect = Exception("SMTP server connection timeout")
        
        res = send_order_confirmation_email(self.order)
        self.assertFalse(res) # returned False cleanly
