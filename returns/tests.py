from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.core import mail
from unittest.mock import patch, MagicMock
from orders.models import Order, OrderItem
from shop.models import Product, Category
from .models import ReturnRequest, ReturnAttachment, OrderAuditLog
from . import services

class ReturnsCancellationTest(TestCase):
    def setUp(self):
        self.username = 'customer1'
        self.password = 'pass123'
        self.user = User.objects.create_user(username=self.username, password=self.password, email='cust1@example.com')
        self.other_user = User.objects.create_user(username='customer2', password=self.password)
        
        self.category = Category.objects.create(name='Gadgets', slug='gadgets')
        self.product = Product.objects.create(
            name='Watch', slug='watch', price=100.00, stock=10, in_stock=True, category=self.category
        )
        
        # Order pending payment
        self.order = Order.objects.create(
            user=self.user,
            order_number='SB-CANCEL-01',
            payment_method='RAZORPAY',
            status='PENDING_PAYMENT',
            payment_status='PENDING',
            total_amount=200.00
        )
        self.item = OrderItem.objects.create(order=self.order, product=self.product, price=100.00, quantity=2)
        # Deduct stock as if ordered
        self.product.stock -= 2
        self.product.save()

    def test_cancel_order_success(self):
        """Verify customer order cancellation works, restores stock, and creates logs."""
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(f'/returns/cancel/{self.order.id}/')
        self.assertRedirects(response, f'/account/orders/{self.order.id}/')
        
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'CANCELLED')
        self.assertEqual(self.order.payment_status, 'FAILED')
        
        # Verify stock restored
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        
        # Verify audit logs created
        logs = OrderAuditLog.objects.filter(order=self.order)
        self.assertEqual(logs.count(), 2)
        self.assertTrue(logs.filter(action='Order Cancelled').exists())
        self.assertTrue(logs.filter(action='Inventory Restored').exists())

    def test_cancel_order_unauthorized(self):
        """Verify non-owners cannot cancel the order."""
        self.client.login(username='customer2', password=self.password)
        response = self.client.post(f'/returns/cancel/{self.order.id}/')
        self.assertEqual(response.status_code, 404)

    def test_cancel_order_invalid_status(self):
        """Verify that delivered orders cannot be cancelled."""
        self.order.status = 'DELIVERED'
        self.order.save()
        
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(f'/returns/cancel/{self.order.id}/')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'DELIVERED') # Status unchanged

    def test_cancel_order_duplicate_cancellation(self):
        """Verify duplicate order cancellation is idempotent and does not restore stock twice."""
        # Initial cancel
        services.cancel_order(self.order, self.user)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        
        # Second cancel (should return cleanly)
        services.cancel_order(self.order, self.user)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10) # Stock remains 10 (not 12)

    def test_concurrent_cancellation_select_for_update(self):
        """Verify cancellation locks order and prevents race conditions."""
        with patch('returns.services.Order.objects.select_for_update') as mock_select:
            mock_query = MagicMock()
            mock_query.get.return_value = self.order
            mock_select.return_value = mock_query
            
            services.cancel_order(self.order, self.user)
            mock_select.assert_called_once()


class ReturnsRequestTest(TestCase):
    def setUp(self):
        self.username = 'customer_ret'
        self.password = 'pass123'
        self.user = User.objects.create_user(username=self.username, password=self.password)
        
        self.category = Category.objects.create(name='Apparel', slug='apparel')
        self.product = Product.objects.create(
            name='T-Shirt', slug='t-shirt', price=50.00, stock=20, in_stock=True, category=self.category
        )
        
        self.order = Order.objects.create(
            user=self.user,
            order_number='SB-RETURN-01',
            status='DELIVERED',
            payment_status='PAID',
            total_amount=50.00
        )
        self.item = OrderItem.objects.create(order=self.order, product=self.product, price=50.00, quantity=1)

    @patch('notifications.services.send_return_requested_email')
    def test_request_return_success(self, mock_email):
        """Verify return request creation with attachments works."""
        self.client.login(username=self.username, password=self.password)
        
        test_image = SimpleUploadedFile(
            name='defect.jpg',
            content=b'dummy_image_bytes',
            content_type='image/jpeg'
        )
        
        response = self.client.post(
            f'/returns/request/{self.order.id}/',
            data={
                'reason': 'DEFECTIVE',
                'description': 'Product has a tear on the left sleeve.',
                'order_item_id': self.item.id,
                'images': [test_image]
            }
        )
        self.assertRedirects(response, f'/account/orders/{self.order.id}/')
        
        # Verify request exists
        req = ReturnRequest.objects.get(order=self.order)
        self.assertEqual(req.status, 'REQUESTED')
        self.assertEqual(req.reason, 'DEFECTIVE')
        self.assertEqual(req.order_item, self.item)
        
        # Verify attachments
        self.assertEqual(req.attachments.count(), 1)
        mock_email.assert_called_once_with(self.order)

    def test_request_return_duplicate_block(self):
        """Verify UniqueConstraint prevents creating duplicate return requests."""
        # Initial request
        services.request_return(self.order, self.user, 'DEFECTIVE', 'notes', self.item)
        
        # Duplicate request (must raise ValidationError)
        with self.assertRaises(ValidationError):
            services.request_return(self.order, self.user, 'WRONG_ITEM', 'notes', self.item)

    def test_request_return_invalid_status(self):
        """Verify returns are blocked if order status is not DELIVERED."""
        self.order.status = 'PROCESSING'
        self.order.save()
        
        with self.assertRaises(ValidationError):
            services.request_return(self.order, self.user, 'DEFECTIVE', 'notes')


class ReturnsAdminWorkflowTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(username='admin_staff', password='adminpassword')
        self.username = 'customer_wf'
        self.password = 'pass123'
        self.user = User.objects.create_user(username=self.username, password=self.password)
        
        self.category = Category.objects.create(name='Home', slug='home')
        self.product = Product.objects.create(
            name='Lamp', slug='lamp', price=120.00, stock=5, in_stock=True, category=self.category
        )
        
        self.order = Order.objects.create(
            user=self.user,
            order_number='SB-WF-01',
            status='DELIVERED',
            payment_status='PAID',
            total_amount=120.00
        )
        self.item = OrderItem.objects.create(order=self.order, product=self.product, price=120.00, quantity=1)
        # Mock initial deduction
        self.product.stock -= 1
        self.product.save()
        
        # Create return request
        self.req = ReturnRequest.objects.create(
            order=self.order,
            user=self.user,
            reason='QUALITY_ISSUE',
            description='Bad quality.',
            status='REQUESTED'
        )

    def test_unauthorized_admin_access(self):
        """Verify non-staff members cannot access return details page."""
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(f'/dashboard/returns/{self.req.id}/')
        # Django staff_member_required redirects to login
        self.assertTrue(response.status_code in [302, 403])

    def test_admin_approve_and_under_review_flow(self):
        """Verify detailed transition: REQUESTED -> UNDER_REVIEW -> APPROVED."""
        self.client.login(username='admin_staff', password='adminpassword')
        
        # Accessing detail page auto-transitions REQUESTED to UNDER_REVIEW
        response = self.client.get(f'/dashboard/returns/{self.req.id}/')
        self.assertEqual(response.status_code, 200)
        
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, 'UNDER_REVIEW')
        
        # Approve request
        response = self.client.post(f'/dashboard/returns/{self.req.id}/approve/')
        self.assertRedirects(response, f'/dashboard/returns/{self.req.id}/')
        
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, 'APPROVED')
        self.assertEqual(self.req.reviewed_by, self.admin_user)

    def test_admin_reject_flow(self):
        """Verify admin can reject return request and notes are saved."""
        self.req.status = 'UNDER_REVIEW'
        self.req.save()
        
        self.client.login(username='admin_staff', password='adminpassword')
        response = self.client.post(
            f'/dashboard/returns/{self.req.id}/reject/',
            data={'admin_notes': 'No product defect visible.'}
        )
        self.assertRedirects(response, f'/dashboard/returns/{self.req.id}/')
        
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, 'REJECTED')
        self.assertEqual(self.req.admin_notes, 'No product defect visible.')

    def test_invalid_transition_attempts(self):
        """Verify transition map constraints are strictly enforced."""
        # Current status is REQUESTED. Cannot jump to REFUNDED.
        with self.assertRaises(ValidationError):
            services.complete_refund(self.req, self.admin_user)

    def test_refund_completion_and_stock_restoration(self):
        """Verify refund completion updates payment, order, and restores stock exactly once."""
        self.req.status = 'APPROVED'
        self.req.save()
        
        # Move to processing
        self.req = services.start_refund(self.req, self.admin_user)
        self.assertEqual(self.req.status, 'REFUND_PROCESSING')
        
        # Stock before
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)
        
        # Complete refund
        self.req = services.complete_refund(self.req, self.admin_user)
        self.assertEqual(self.req.status, 'REFUNDED')
        
        # Check stock restored
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        
        # Check order and payment status updated
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'REFUNDED')
        self.assertEqual(self.order.payment_status, 'REFUNDED')
        
        # Try completing refund again (idempotent, stock shouldn't increment again)
        self.req.refresh_from_db()
        self.req.status = 'REFUND_PROCESSING'
        self.req.save(update_fields=['status'])
        services.complete_refund(self.req, self.admin_user)
        
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5) # Still 5

    def test_pagination(self):
        """Verify list page displays exactly 20 requests per page."""
        self.client.login(username='admin_staff', password='adminpassword')
        
        # Create 25 additional return requests
        for i in range(25):
            o = Order.objects.create(
                user=self.user,
                order_number=f'SB-PAG-{i}',
                status='DELIVERED',
                total_amount=10.00
            )
            ReturnRequest.objects.create(
                order=o,
                user=self.user,
                reason='CHANGED_MIND',
                status='REQUESTED'
            )
            
        response = self.client.get('/dashboard/returns/')
        self.assertEqual(len(response.context['page_obj']), 20)

    def test_query_optimization(self):
        """Verify that list queryset pre-fetches relations properly to avoid N+1 queries."""
        # Create some additional request entries
        for i in range(3):
            o = Order.objects.create(
                user=self.user,
                order_number=f'SB-OPT-{i}',
                status='DELIVERED',
                total_amount=10.00
            )
            req = ReturnRequest.objects.create(
                order=o,
                user=self.user,
                reason='CHANGED_MIND',
                status='REQUESTED'
            )
            ReturnAttachment.objects.create(return_request=req, image='test.jpg')

        qs = ReturnRequest.objects.filter(is_active=True).select_related(
            'order', 'user', 'order_item'
        ).prefetch_related('attachments')
        
        with self.assertNumQueries(2):
            res_list = list(qs)
            for req in res_list:
                req.order.order_number
                req.user.username
                if req.order_item:
                    req.order_item.quantity
                list(req.attachments.all())

    @patch('django.core.mail.EmailMultiAlternatives.send')
    def test_email_delivery_failures_caught(self, mock_send):
        """Verify that email SMTP failure does not disrupt database transactions."""
        mock_send.side_effect = Exception("SMTP timeout error")
        self.req.status = 'UNDER_REVIEW'
        self.req.save()
        
        # Approve return request
        res = services.approve_return(self.req, self.admin_user)
        self.assertEqual(res.status, 'APPROVED') # Transaction succeeded despite email failure
