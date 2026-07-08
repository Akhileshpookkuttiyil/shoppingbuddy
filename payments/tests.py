import json
from io import StringIO
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.management import call_command
from orders.models import Order, OrderItem
from shop.models import Product, Category
from accounts.models import UserAddress

class RazorpayFoundationTest(TestCase):
    def test_service_import_integrity(self):
        """Verify that all services functions can be imported successfully."""
        try:
            from payments.services import (
                get_razorpay_client,
                create_razorpay_order,
                verify_razorpay_signature,
                handle_payment_success,
                handle_payment_failure
            )
        except ImportError as e:
            self.fail(f"Services import integrity failed: {str(e)}")

    def test_successful_client_initialization(self):
        """Verify get_razorpay_client returns a valid Razorpay Client instance when all credentials are set."""
        from payments.services import get_razorpay_client
        import razorpay
        client_inst = get_razorpay_client()
        self.assertIsInstance(client_inst, razorpay.Client)

    @override_settings(RAZORPAY_KEY_ID=None, RAZORPAY_KEY_SECRET='secret', RAZORPAY_WEBHOOK_SECRET='webhook')
    def test_client_initialization_missing_key_id(self):
        """Verify ValidationError is raised when RAZORPAY_KEY_ID is missing."""
        from payments.services import get_razorpay_client
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError) as ctx:
            get_razorpay_client()
        self.assertIn("RAZORPAY_KEY_ID is missing", str(ctx.exception))

    @override_settings(RAZORPAY_KEY_ID='key', RAZORPAY_KEY_SECRET=None, RAZORPAY_WEBHOOK_SECRET='webhook')
    def test_client_initialization_missing_secret(self):
        """Verify ValidationError is raised when RAZORPAY_KEY_SECRET is missing."""
        from payments.services import get_razorpay_client
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError) as ctx:
            get_razorpay_client()
        self.assertIn("RAZORPAY_KEY_SECRET is missing", str(ctx.exception))

    @override_settings(RAZORPAY_KEY_ID='key', RAZORPAY_KEY_SECRET='secret', RAZORPAY_WEBHOOK_SECRET=None)
    def test_client_initialization_missing_webhook_secret(self):
        """Verify ValidationError is raised when RAZORPAY_WEBHOOK_SECRET is missing."""
        from payments.services import get_razorpay_client
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError) as ctx:
            get_razorpay_client()
        self.assertIn("RAZORPAY_WEBHOOK_SECRET is missing", str(ctx.exception))

    @override_settings(RAZORPAY_KEY_ID=None, RAZORPAY_KEY_SECRET=None, RAZORPAY_WEBHOOK_SECRET=None)
    def test_client_initialization_all_missing(self):
        """Verify ValidationError is raised when all credentials are missing."""
        from payments.services import get_razorpay_client
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError) as ctx:
            get_razorpay_client()
        self.assertIn("RAZORPAY_KEY_ID is missing", str(ctx.exception))

    def test_order_model_razorpay_fields_and_indexes(self):
        """Verify that Order model has the required Razorpay fields and indexes."""
        from orders.models import Order
        fields = [f.name for f in Order._meta.get_fields()]
        self.assertIn('razorpay_order_id', fields)
        self.assertIn('razorpay_payment_id', fields)
        self.assertIn('razorpay_signature', fields)
        self.assertIn('paid_at', fields)
        self.assertIn('status', fields)
        self.assertIn('payment_status', fields)

        # Verify database indexing is enabled where appropriate
        self.assertTrue(Order._meta.get_field('razorpay_order_id').db_index)
        self.assertTrue(Order._meta.get_field('status').db_index)
        self.assertTrue(Order._meta.get_field('payment_status').db_index)

    def test_migration_integrity(self):
        """Verify there are no pending database migration changes."""
        from django.core.management import call_command
        out = StringIO()
        try:
            call_command('makemigrations', check=True, dry_run=True, stdout=out)
        except SystemExit as e:
            if getattr(e, 'code', 0) != 0:
                self.fail(f"Pending migrations detected:\n{out.getvalue()}")
        except Exception as e:
            self.fail(f"makemigrations check failed: {str(e)}")

    @patch('payments.services.client')
    def test_mocked_verify_razorpay_signature(self, mock_client):
        """Verify verify_razorpay_signature returns True on valid signature validation."""
        mock_client.utility.verify_payment_signature.return_value = True
        from payments.services import verify_razorpay_signature
        data = {
            'razorpay_order_id': 'order_id',
            'razorpay_payment_id': 'pay_id',
            'razorpay_signature': 'sig'
        }
        res = verify_razorpay_signature(data)
        self.assertTrue(res)
        mock_client.utility.verify_payment_signature.assert_called_once_with(data)


class RazorpayPaymentIntegrationTest(TestCase):
    def setUp(self):
        self.password = 'securepassword123'
        self.user = User.objects.create_user(username='testcustomer', password=self.password, email='cust@example.com')
        self.other_user = User.objects.create_user(username='othercustomer', password=self.password, email='other@example.com')
        
        self.addr = UserAddress.objects.create(
            user=self.user, full_name='John Doe', phone='9876543210', address_line_1='Flat 101', city='Mumbai', postal_code='400001', is_active=True
        )

        self.category = Category.objects.create(name='Electronics', slug='electronics')
        self.product = Product.objects.create(
            name='Smartphone', slug='smartphone', price=500.00, stock=10, in_stock=True, category=self.category
        )

        self.order = Order.objects.create(
            user=self.user,
            order_number='SB-20260707-888888',
            payment_method='RAZORPAY',
            status='PENDING_PAYMENT',
            payment_status='PENDING',
            total_amount=500.00,
            expires_at=timezone.now() + timedelta(minutes=20),
            razorpay_order_id='order_test_123'
        )
        OrderItem.objects.create(order=self.order, product=self.product, price=500.00, quantity=1)
        # Decrement stock initially to mimic initial order reservation
        self.product.stock -= 1
        self.product.save()

    @patch('payments.services.client')
    def test_razorpay_order_creation(self, mock_client):
        """Verify services.create_razorpay_order calls Razorpay API and returns order dict."""
        mock_client.order.create.return_value = {'id': 'order_test_123', 'amount': 50000, 'currency': 'INR'}
        
        from payments.services import create_razorpay_order
        rz_order = create_razorpay_order(self.order)
        
        self.assertEqual(rz_order['id'], 'order_test_123')
        mock_client.order.create.assert_called_once()

    @patch('payments.services.client')
    def test_successful_callback(self, mock_client):
        """Verify successful callback signature verification transitions status to PAID and PROCESSING."""
        mock_client.utility.verify_payment_signature.return_value = True
        self.client.login(username='testcustomer', password=self.password)

        response = self.client.post('/payments/verify/', {
            'razorpay_order_id': 'order_test_123',
            'razorpay_payment_id': 'pay_test_123',
            'razorpay_signature': 'sig_test_123'
        })
        self.assertRedirects(response, f'/checkout/{self.order.id}/confirmation/')

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'PROCESSING')
        self.assertEqual(self.order.payment_status, 'PAID')
        self.assertEqual(self.order.razorpay_payment_id, 'pay_test_123')
        self.assertEqual(self.order.razorpay_signature, 'sig_test_123')
        self.assertIsNotNone(self.order.paid_at)

        # Inventory remains decremented
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 9)

    @patch('payments.services.client')
    def test_invalid_signature(self, mock_client):
        """Verify callback signature mismatch transitions order status to PAYMENT_FAILED."""
        mock_client.utility.verify_payment_signature.side_effect = Exception("Signature verification failed")
        self.client.login(username='testcustomer', password=self.password)

        response = self.client.post('/payments/verify/', {
            'razorpay_order_id': 'order_test_123',
            'razorpay_payment_id': 'pay_test_123',
            'razorpay_signature': 'sig_invalid'
        })
        self.assertRedirects(response, f'/checkout/{self.order.id}/confirmation/')

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'PAYMENT_FAILED')
        self.assertEqual(self.order.payment_status, 'FAILED')

        # Stock remains reserved
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 9)

    @patch('payments.services.client')
    def test_duplicate_callback(self, mock_client):
        """Verify callback idempotency: processing duplicate callback does not double-process."""
        mock_client.utility.verify_payment_signature.return_value = True
        self.client.login(username='testcustomer', password=self.password)

        # First callback succeeds
        self.client.post('/payments/verify/', {
            'razorpay_order_id': 'order_test_123',
            'razorpay_payment_id': 'pay_test_123',
            'razorpay_signature': 'sig_test_123'
        })
        self.order.refresh_from_db()
        first_paid_at = self.order.paid_at

        # Duplicate callback triggers
        self.client.post('/payments/verify/', {
            'razorpay_order_id': 'order_test_123',
            'razorpay_payment_id': 'pay_test_123',
            'razorpay_signature': 'sig_test_123'
        })
        self.order.refresh_from_db()
        
        self.assertEqual(self.order.payment_status, 'PAID')
        self.assertEqual(self.order.paid_at, first_paid_at) # paid_at timestamp did not change

    @patch('payments.services.client')
    def test_successful_webhook(self, mock_client):
        """Verify webhook payload signature verification transitions order to PAID and PROCESSING."""
        mock_client.utility.verify_webhook_signature.return_value = True
        self.order.razorpay_order_id = 'order_test_123'
        self.order.save()

        payload = {
            'event': 'payment.captured',
            'payload': {
                'payment': {
                    'entity': {
                        'order_id': 'order_test_123',
                        'id': 'pay_test_123'
                    }
                }
            }
        }

        response = self.client.post(
            '/payments/webhook/razorpay/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE='valid_sig'
        )
        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'PROCESSING')
        self.assertEqual(self.order.payment_status, 'PAID')
        self.assertEqual(self.order.razorpay_payment_id, 'pay_test_123')

    @patch('payments.services.client')
    def test_duplicate_webhook(self, mock_client):
        """Verify webhook processing is idempotent on duplicate events."""
        mock_client.utility.verify_webhook_signature.return_value = True
        self.order.razorpay_order_id = 'order_test_123'
        self.order.save()

        payload = {
            'event': 'payment.captured',
            'payload': {
                'payment': {
                    'entity': {
                        'order_id': 'order_test_123',
                        'id': 'pay_test_123'
                    }
                }
            }
        }

        # Send first
        self.client.post(
            '/payments/webhook/razorpay/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE='valid_sig'
        )
        self.order.refresh_from_db()
        first_paid_at = self.order.paid_at

        # Send duplicate
        self.client.post(
            '/payments/webhook/razorpay/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE='valid_sig'
        )
        self.order.refresh_from_db()
        
        self.assertEqual(self.order.payment_status, 'PAID')
        self.assertEqual(self.order.paid_at, first_paid_at)

    def test_payment_failure(self):
        """Verify user cancellation marks payment status as failed and does not restore inventory."""
        self.client.login(username='testcustomer', password=self.password)
        
        response = self.client.get(f'/payments/cancel/{self.order.id}/')
        self.assertRedirects(response, f'/checkout/{self.order.id}/confirmation/')

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'PAYMENT_FAILED')
        self.assertEqual(self.order.payment_status, 'FAILED')

        # Stock remains reserved
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 9)

    @patch('payments.services.client')
    def test_retry_payment_flow(self, mock_client):
        """Verify retrying a failed payment updates order fields and redirects to payment page."""
        mock_client.order.create.return_value = {'id': 'order_new_retry_456'}
        self.order.status = 'PAYMENT_FAILED'
        self.order.payment_status = 'FAILED'
        self.order.save()

        self.client.login(username='testcustomer', password=self.password)
        response = self.client.get(f'/payments/retry/{self.order.id}/')
        
        self.assertRedirects(response, f'/payments/payment/{self.order.id}/')

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'PENDING_PAYMENT')
        self.assertEqual(self.order.payment_status, 'PENDING')
        self.assertEqual(self.order.razorpay_order_id, 'order_new_retry_456')

    @patch('payments.services.client')
    def test_retry_payment_does_not_create_new_order(self, mock_client):
        """Verify retry payment reuses the same internal Order record (same ID, same number) but gets a new Razorpay ID."""
        mock_client.order.create.return_value = {'id': 'order_retry_unique_999'}
        self.order.status = 'PAYMENT_FAILED'
        self.order.payment_status = 'FAILED'
        self.order.save()

        old_order_id = self.order.id
        old_order_number = self.order.order_number

        self.client.login(username='testcustomer', password=self.password)
        self.client.get(f'/payments/retry/{self.order.id}/')

        self.order.refresh_from_db()
        self.assertEqual(self.order.id, old_order_id)
        self.assertEqual(self.order.order_number, old_order_number)
        self.assertEqual(self.order.razorpay_order_id, 'order_retry_unique_999')

    def test_unauthorized_payment_page_access(self):
        """Verify other users cannot access payment page (returns 404)."""
        self.client.login(username='othercustomer', password=self.password)
        response = self.client.get(f'/payments/payment/{self.order.id}/')
        self.assertEqual(response.status_code, 404)

    def test_expired_order_access(self):
        """Verify expired order payment page access is blocked (returns 400)."""
        self.order.status = 'PAYMENT_EXPIRED'
        self.order.save()

        self.client.login(username='testcustomer', password=self.password)
        response = self.client.get(f'/payments/payment/{self.order.id}/')
        self.assertEqual(response.status_code, 400)

    def test_cancelled_order_access(self):
        """Verify cancelled order payment page access is blocked (returns 400)."""
        self.order.status = 'CANCELLED'
        self.order.save()

        self.client.login(username='testcustomer', password=self.password)
        response = self.client.get(f'/payments/payment/{self.order.id}/')
        self.assertEqual(response.status_code, 400)

    def test_already_paid_order_cannot_be_paid_again(self):
        """Verify paid order payment page access is blocked (returns 400)."""
        self.order.status = 'PROCESSING'
        self.order.payment_status = 'PAID'
        self.order.save()

        self.client.login(username='testcustomer', password=self.password)
        response = self.client.get(f'/payments/payment/{self.order.id}/')
        self.assertEqual(response.status_code, 400)

    def test_inventory_restored_only_by_expire_orders(self):
        """Verify stock is restored only when running expire_orders command on expired order."""
        # Set order as expired
        self.order.expires_at = timezone.now() - timedelta(minutes=1)
        self.order.save()

        # Check stock before: 9
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 9)

        # Run command
        out = StringIO()
        call_command('expire_orders', stdout=out)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'PAYMENT_EXPIRED')

        # Stock restored: 9 + 1 = 10
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertTrue(self.product.in_stock)


class RazorpayCheckoutIntegrationTest(TestCase):
    def setUp(self):
        self.username = 'testcustomer_check'
        self.password = 'securepassword123'
        self.user = User.objects.create_user(username=self.username, password=self.password, email='cust_check@example.com')
        self.other_user = User.objects.create_user(username='otheruser_check', password=self.password)
        
        self.category = Category.objects.create(name='Electronics', slug='electronics')
        self.product = Product.objects.create(
            name='Smartphone', slug='smartphone', price=500.00, stock=10, in_stock=True, category=self.category
        )
        
        self.addr = UserAddress.objects.create(
            user=self.user, full_name='John Doe', phone='9876543210', address_line_1='Flat 101', city='Mumbai', postal_code='400001', is_active=True
        )
        
        self._setup_session_cart()

    def _setup_session_cart(self):
        from cart.models import Cart_List, Cart_Items
        # Create a session cart
        session = self.client.session
        cart_list = Cart_List.objects.create(cart_id='test_cart_session_check')
        session['cart_id'] = 'test_cart_session_check'
        session.save()
        Cart_Items.objects.create(product=self.product, cart=cart_list, quantity=2, active=True)

    @patch('payments.services.client')
    def test_checkout_razorpay_flow(self, mock_client):
        """Verify selecting Razorpay creates a Razorpay order, saves id, redirects, and reserves inventory."""
        mock_client.order.create.return_value = {'id': 'order_rz_check_777'}
        self.client.login(username=self.username, password=self.password)
        
        response = self.client.post('/checkout/', {
            'shipping_address': self.addr.id,
            'payment_method': 'RAZORPAY'
        })
        
        # Get order
        order = Order.objects.filter(payment_method='RAZORPAY').first()
        self.assertIsNotNone(order)
        self.assertEqual(order.status, 'PENDING_PAYMENT')
        self.assertEqual(order.payment_status, 'PENDING')
        self.assertEqual(order.razorpay_order_id, 'order_rz_check_777')
        
        # Customer should be redirected to payment page
        self.assertRedirects(response, f'/payments/payment/{order.id}/')
        
        # Stock must remain reserved (decremented from 10 to 8)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)

    def test_checkout_cod_flow_remains_unchanged(self):
        """Verify selecting Cash on Delivery redirects to confirmation without creating Razorpay order."""
        self.client.login(username=self.username, password=self.password)
        
        response = self.client.post('/checkout/', {
            'shipping_address': self.addr.id,
            'payment_method': 'COD'
        })
        
        order = Order.objects.filter(payment_method='COD').first()
        self.assertIsNotNone(order)
        self.assertEqual(order.status, 'PROCESSING')
        self.assertIsNone(order.razorpay_order_id)
        
        self.assertRedirects(response, f'/checkout/{order.id}/confirmation/')
        
        # Stock must be reserved
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)

    def test_payment_page_unauthorized_user_returns_404(self):
        """Verify other users cannot access payment page (returns 404)."""
        order = Order.objects.create(
            user=self.user, order_number='SB-TEST-CHECK-001', payment_method='RAZORPAY', status='PENDING_PAYMENT', total_amount=100.00
        )
        self.client.login(username='otheruser_check', password=self.password)
        response = self.client.get(f'/payments/payment/{order.id}/')
        self.assertEqual(response.status_code, 404)

    def test_payment_page_expired_order_cannot_be_opened(self):
        """Verify expired orders return 400 (Bad Request)."""
        order = Order.objects.create(
            user=self.user, order_number='SB-TEST-CHECK-002', payment_method='RAZORPAY', status='PAYMENT_EXPIRED', total_amount=100.00
        )
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(f'/payments/payment/{order.id}/')
        self.assertEqual(response.status_code, 400)

    def test_payment_page_cancelled_order_cannot_be_opened(self):
        """Verify cancelled orders return 400 (Bad Request)."""
        order = Order.objects.create(
            user=self.user, order_number='SB-TEST-CHECK-003', payment_method='RAZORPAY', status='CANCELLED', total_amount=100.00
        )
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(f'/payments/payment/{order.id}/')
        self.assertEqual(response.status_code, 400)

    def test_payment_page_paid_order_cannot_be_opened(self):
        """Verify paid orders return 400 (Bad Request)."""
        order = Order.objects.create(
            user=self.user, order_number='SB-TEST-CHECK-004', payment_method='RAZORPAY', status='PROCESSING', payment_status='PAID', total_amount=100.00
        )
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(f'/payments/payment/{order.id}/')
        self.assertEqual(response.status_code, 400)

    def test_payment_page_refunded_order_cannot_be_opened(self):
        """Verify refunded orders return 400 (Bad Request)."""
        order = Order.objects.create(
            user=self.user, order_number='SB-TEST-CHECK-005', payment_method='RAZORPAY', status='REFUNDED', payment_status='REFUNDED', total_amount=100.00
        )
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(f'/payments/payment/{order.id}/')
        self.assertEqual(response.status_code, 400)
