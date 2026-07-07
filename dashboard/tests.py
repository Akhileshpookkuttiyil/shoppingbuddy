from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from orders.models import Order, OrderItem
from shop.models import Product, Category

class AdminOrderDashboardTest(TestCase):
    def setUp(self):
        self.password = 'securepassword123'
        self.staff_user = User.objects.create_user(
            username='adminuser', password=self.password, email='admin@example.com', is_staff=True
        )
        self.non_staff_user = User.objects.create_user(
            username='regularuser', password=self.password, email='regular@example.com', is_staff=False
        )

        self.category = Category.objects.create(name='Electronics', slug='electronics')
        self.product = Product.objects.create(
            name='Dashboard Product', slug='dash-prod', price=200.00, stock=5, in_stock=True, category=self.category
        )

        self.order1 = Order.objects.create(
            user=self.non_staff_user,
            order_number='SB-20260707-000001',
            payment_method='COD',
            status='PENDING_PAYMENT',
            total_amount=200.00,
            shipping_full_name='John Doe',
            shipping_phone='9876543210',
            shipping_address_line_1='Flat 101',
            shipping_city='Mumbai',
            shipping_postal_code='400001'
        )
        OrderItem.objects.create(order=self.order1, product=self.product, price=200.00, quantity=1)

        self.order2 = Order.objects.create(
            user=self.non_staff_user,
            order_number='SB-20260707-000002',
            payment_method='STRIPE',
            status='PAID',
            total_amount=400.00,
            shipping_full_name='Jane Doe',
            shipping_phone='9876543211',
            shipping_address_line_1='Flat 102',
            shipping_city='Bangalore',
            shipping_postal_code='560001'
        )

        self.list_url = '/dashboard/orders/'
        self.detail_url = f'/dashboard/orders/{self.order1.id}/'

    # --- Access Control Tests ---
    def test_guest_redirected_to_login(self):
        """Verify guest user is redirected from list and details views."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/account/login/', response.url)

        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/account/login/', response.url)

    def test_non_staff_user_denied(self):
        """Verify non-staff authenticated user is redirected to login."""
        self.client.login(username='regularuser', password=self.password)
        
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/account/login/', response.url)

    def test_staff_user_allowed(self):
        """Verify staff authenticated user is allowed access."""
        self.client.login(username='adminuser', password=self.password)
        
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/orders.html')

    # --- Search Tests ---
    def test_search_by_order_number(self):
        self.client.login(username='adminuser', password=self.password)
        response = self.client.get(self.list_url, {'q': 'SB-20260707-000001'})
        orders = response.context['page_obj'].object_list
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0], self.order1)

    def test_search_by_customer_name(self):
        self.client.login(username='adminuser', password=self.password)
        response = self.client.get(self.list_url, {'q': 'Jane'})
        orders = response.context['page_obj'].object_list
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0], self.order2)

    def test_search_by_customer_email(self):
        self.client.login(username='adminuser', password=self.password)
        response = self.client.get(self.list_url, {'q': 'regular@example.com'})
        orders = response.context['page_obj'].object_list
        self.assertEqual(len(orders), 2)

    # --- Filter Tests ---
    def test_filter_by_status(self):
        self.client.login(username='adminuser', password=self.password)
        response = self.client.get(self.list_url, {'status': 'PAID'})
        orders = response.context['page_obj'].object_list
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0], self.order2)

    def test_filter_by_payment_method(self):
        self.client.login(username='adminuser', password=self.password)
        response = self.client.get(self.list_url, {'payment_method': 'COD'})
        orders = response.context['page_obj'].object_list
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0], self.order1)

    # --- Pagination Tests ---
    def test_pagination_twenty_orders_per_page(self):
        self.client.login(username='adminuser', password=self.password)
        
        # Create additional 22 orders (total 24)
        for i in range(22):
            Order.objects.create(
                user=self.non_staff_user,
                order_number=f'SB-20260707-0001{i:02d}',
                payment_method='COD',
                status='PENDING_PAYMENT',
                total_amount=100.00
            )

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        page_obj = response.context['page_obj']
        self.assertEqual(len(page_obj.object_list), 20)
        self.assertTrue(page_obj.has_next())

    # --- Status Transition Tests ---
    def test_valid_status_transition(self):
        """Verify transitioning from PENDING_PAYMENT to PAID succeeds."""
        self.client.login(username='adminuser', password=self.password)
        response = self.client.post(self.detail_url, {'status': 'PAID'})
        self.assertRedirects(response, self.detail_url)
        
        self.order1.refresh_from_db()
        self.assertEqual(self.order1.status, 'PAID')

    def test_invalid_status_transition(self):
        """Verify transitioning from PENDING_PAYMENT to SHIPPED fails (invalid next status)."""
        self.client.login(username='adminuser', password=self.password)
        response = self.client.post(self.detail_url, {'status': 'SHIPPED'})
        self.assertRedirects(response, self.detail_url)
        
        self.order1.refresh_from_db()
        self.assertEqual(self.order1.status, 'PENDING_PAYMENT')

    def test_terminal_state_remains_immutable(self):
        """Verify order in CANCELLED state cannot change status."""
        self.order1.status = 'CANCELLED'
        self.order1.save()

        self.client.login(username='adminuser', password=self.password)
        response = self.client.post(self.detail_url, {'status': 'PAID'})
        self.assertRedirects(response, self.detail_url)

        self.order1.refresh_from_db()
        self.assertEqual(self.order1.status, 'CANCELLED')

    # --- Order Details Render Tests ---
    def test_order_detail_renders_items_and_snapshots(self):
        self.client.login(username='adminuser', password=self.password)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/order_detail.html')

        # Check snapshot details
        self.assertContains(response, 'John Doe')
        self.assertContains(response, 'Flat 101')
        self.assertContains(response, 'Mumbai')

        # Check items rendering
        self.assertContains(response, 'Dashboard Product')
        self.assertContains(response, '₹200')

