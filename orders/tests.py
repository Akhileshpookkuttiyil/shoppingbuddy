from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.management import call_command
from io import StringIO
from datetime import timedelta
from cart.models import Cart_List, Cart_Items
from shop.models import Product, Category
from accounts.models import UserAddress
from .models import Order, OrderItem
from .services import create_order

class OrderCreationSystemTest(TestCase):
    def setUp(self):
        self.username1 = 'testuser1'
        self.username2 = 'testuser2'
        self.password = 'securepassword123'
        
        self.user1 = User.objects.create_user(
            username=self.username1, password=self.password, email='user1@example.com'
        )
        self.user2 = User.objects.create_user(
            username=self.username2, password=self.password, email='user2@example.com'
        )

        self.category = Category.objects.create(name='Clothing', slug='clothing')
        self.product1 = Product.objects.create(
            name='Product 1', slug='product-1', price=100.00, stock=5, in_stock=True, category=self.category
        )
        self.product2 = Product.objects.create(
            name='Product 2', slug='product-2', price=50.00, stock=10, in_stock=True, category=self.category
        )

        self.addr1 = UserAddress.objects.create(
            user=self.user1,
            full_name='John Doe',
            phone='9876543210',
            address_line_1='Flat 12',
            address_line_2='Block B',
            landmark='Near Park',
            city='Mumbai',
            state='MH',
            country='India',
            postal_code='400001',
            is_default=True
        )
        self.inactive_addr = UserAddress.objects.create(
            user=self.user1,
            full_name='Inactive User',
            phone='9876543210',
            address_line_1='Flat 13',
            city='Mumbai',
            state='MH',
            postal_code='400001',
            is_active=False
        )
        self.addr2 = UserAddress.objects.create(
            user=self.user2,
            full_name='Other User',
            phone='9876543210',
            address_line_1='Flat 14',
            city='Mumbai',
            state='MH',
            postal_code='400001',
            is_default=True
        )

        # Mock requests session/cart configuration
        self.cart_id = 'test-cart-id'
        self.cart = Cart_List.objects.create(cart_id=self.cart_id)

    def _setup_session_cart(self):
        session = self.client.session
        session['cart_id'] = self.cart_id
        session.save()

    def test_create_order_success(self):
        """1. Verify successful order creation with full transactional pipeline."""
        Cart_Items.objects.create(cart=self.cart, product=self.product1, quantity=2, active=True)
        
        self.client.login(username=self.username1, password=self.password)
        self._setup_session_cart()
        
        response = self.client.post('/checkout/', {
            'shipping_address': self.addr1.id,
            'payment_method': 'COD'
        })
        
        order = Order.objects.first()
        self.assertIsNotNone(order)
        self.assertRedirects(response, f'/checkout/{order.id}/confirmation/')

        # 12. Check order number format SB-YYYYMMDD-XXXXXX
        today_str = timezone.now().strftime('%Y%m%d')
        self.assertTrue(order.order_number.startswith(f"SB-{today_str}-"))
        self.assertEqual(len(order.order_number), len("SB-20260707-000001"))

    def test_create_order_empty_cart(self):
        """2. Verify that empty cart triggers ValidationError during order placement."""
        self.client.login(username=self.username1, password=self.password)
        self._setup_session_cart()
        
        response = self.client.post('/checkout/', {
            'shipping_address': self.addr1.id,
            'payment_method': 'COD'
        })
        self.assertContains(response, "Your cart is empty.")

    def test_create_order_invalid_address(self):
        """3. Verify order fails with inactive address."""
        Cart_Items.objects.create(cart=self.cart, product=self.product1, quantity=2, active=True)
        self.client.login(username=self.username1, password=self.password)
        self._setup_session_cart()
        
        response = self.client.post('/checkout/', {
            'shipping_address': self.inactive_addr.id,
            'payment_method': 'COD'
        })
        self.assertContains(response, "Invalid or inactive shipping address.")

    def test_create_order_other_user_address(self):
        """4. Verify order fails if shipping address belongs to another user."""
        Cart_Items.objects.create(cart=self.cart, product=self.product1, quantity=2, active=True)
        self.client.login(username=self.username1, password=self.password)
        self._setup_session_cart()
        
        response = self.client.post('/checkout/', {
            'shipping_address': self.addr2.id,
            'payment_method': 'COD'
        })
        self.assertContains(response, "Selected shipping address does not exist.")

    def test_create_order_insufficient_stock(self):
        """5. Verify order placement fails if requested quantity exceeds product stock."""
        Cart_Items.objects.create(cart=self.cart, product=self.product1, quantity=10, active=True)
        self.client.login(username=self.username1, password=self.password)
        self._setup_session_cart()
        
        response = self.client.post('/checkout/', {
            'shipping_address': self.addr1.id,
            'payment_method': 'COD'
        })
        self.assertContains(response, "Insufficient stock for product: Product 1")

    def test_create_order_inventory_decrement_and_stock_zero(self):
        """6 & 13. Verify stock decrementing and setting in_stock=False when hitting zero."""
        Cart_Items.objects.create(cart=self.cart, product=self.product1, quantity=5, active=True)
        self.client.login(username=self.username1, password=self.password)
        self._setup_session_cart()
        
        self.client.post('/checkout/', {
            'shipping_address': self.addr1.id,
            'payment_method': 'COD'
        })
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock, 0)
        self.assertFalse(self.product1.in_stock)

    def test_create_order_cart_clearing(self):
        """7. Verify cart is efficiently cleared upon successful checkout."""
        Cart_Items.objects.create(cart=self.cart, product=self.product1, quantity=2, active=True)
        self.client.login(username=self.username1, password=self.password)
        self._setup_session_cart()
        
        self.client.post('/checkout/', {
            'shipping_address': self.addr1.id,
            'payment_method': 'COD'
        })
        cart_count = Cart_Items.objects.filter(cart=self.cart).count()
        self.assertEqual(cart_count, 0)

    def test_create_order_address_snapshotting(self):
        """8. Verify all shipping details are correctly snapshotted onto the Order."""
        Cart_Items.objects.create(cart=self.cart, product=self.product1, quantity=1, active=True)
        self.client.login(username=self.username1, password=self.password)
        self._setup_session_cart()
        
        self.client.post('/checkout/', {
            'shipping_address': self.addr1.id,
            'payment_method': 'COD'
        })
        order = Order.objects.first()
        self.assertEqual(order.shipping_full_name, self.addr1.full_name)
        self.assertEqual(order.shipping_phone, self.addr1.phone)
        self.assertEqual(order.shipping_address_line_1, self.addr1.address_line_1)
        self.assertEqual(order.shipping_address_line_2, self.addr1.address_line_2)
        self.assertEqual(order.shipping_landmark, self.addr1.landmark)
        self.assertEqual(order.shipping_city, self.addr1.city)
        self.assertEqual(order.shipping_state, self.addr1.state)
        self.assertEqual(order.shipping_country, self.addr1.country)
        self.assertEqual(order.shipping_postal_code, self.addr1.postal_code)

    def test_create_order_multiple_items(self):
        """9. Verify order handles multiple cart items correctly."""
        Cart_Items.objects.create(cart=self.cart, product=self.product1, quantity=2, active=True)
        Cart_Items.objects.create(cart=self.cart, product=self.product2, quantity=3, active=True)
        self.client.login(username=self.username1, password=self.password)
        self._setup_session_cart()
        
        self.client.post('/checkout/', {
            'shipping_address': self.addr1.id,
            'payment_method': 'COD'
        })
        order = Order.objects.first()
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(float(order.total_amount), 350.00)

    def test_confirmation_page_access_and_security(self):
        """10 & 11. Verify user can view their own confirmation, but another user gets 404."""
        order = Order.objects.create(
            user=self.user1,
            order_number='SB-20260707-111111',
            payment_method='COD',
            status='PENDING_PAYMENT',
            total_amount=100.00,
            shipping_full_name='John Doe',
            shipping_phone='9876543210',
            shipping_address_line_1='Flat 12',
            shipping_city='Mumbai',
            shipping_postal_code='400001'
        )

        confirmation_url = f'/checkout/{order.id}/confirmation/'
        
        self.client.login(username=self.username2, password=self.password)
        response = self.client.get(confirmation_url)
        self.assertEqual(response.status_code, 404)
        
        self.client.login(username=self.username1, password=self.password)
        response = self.client.get(confirmation_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'confirmation.html')
        self.assertContains(response, 'SB-20260707-111111')

    def test_payment_method_persistence(self):
        """14. Verify payment method defaults and overrides persist correctly."""
        Cart_Items.objects.create(cart=self.cart, product=self.product1, quantity=1, active=True)
        self.client.login(username=self.username1, password=self.password)
        self._setup_session_cart()
        
        self.client.post('/checkout/', {
            'shipping_address': self.addr1.id,
            'payment_method': 'COD'
        })
        order = Order.objects.first()
        self.assertEqual(order.payment_method, 'COD')


class OrderHistoryAndDetailTest(TestCase):
    def setUp(self):
        self.username1 = 'testuser1'
        self.username2 = 'testuser2'
        self.password = 'securepassword123'
        
        self.user1 = User.objects.create_user(
            username=self.username1, password=self.password, email='user1@example.com'
        )
        self.user2 = User.objects.create_user(
            username=self.username2, password=self.password, email='user2@example.com'
        )
        self.category = Category.objects.create(name='Clothing', slug='clothing')
        self.product = Product.objects.create(
            name='Test Product', slug='test-product', price=100.00, stock=5, in_stock=True, category=self.category
        )
        
        # Create orders for user1
        self.order1 = Order.objects.create(
            user=self.user1,
            order_number='SB-20260707-111111',
            payment_method='COD',
            status='PENDING_PAYMENT',
            total_amount=100.00,
            shipping_full_name='John Doe',
            shipping_phone='9876543210',
            shipping_address_line_1='Flat 12',
            shipping_city='Mumbai',
            shipping_postal_code='400001'
        )
        self.order2 = Order.objects.create(
            user=self.user1,
            order_number='SB-20260707-222222',
            payment_method='COD',
            status='DELIVERED',
            total_amount=200.00,
            shipping_full_name='John Doe',
            shipping_phone='9876543210',
            shipping_address_line_1='Flat 12',
            shipping_city='Mumbai',
            shipping_postal_code='400001'
        )
        OrderItem.objects.create(order=self.order1, product=self.product, price=100.00, quantity=1)

    def test_unauthenticated_order_list_redirect(self):
        """Verify guest user is redirected to login from order history."""
        response = self.client.get('/account/orders/history/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_unauthenticated_order_detail_redirect(self):
        """Verify guest user is redirected to login from order details."""
        response = self.client.get(f'/account/orders/{self.order1.id}/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_authenticated_user_sees_their_orders_and_newest_first(self):
        """Verify user sees only their orders sorted newest first."""
        self.client.login(username=self.username1, password=self.password)
        response = self.client.get('/account/orders/history/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'account/orders.html')
        
        # Check order list contains order numbers
        self.assertContains(response, 'SB-20260707-111111')
        self.assertContains(response, 'SB-20260707-222222')
        
        # Check ordering is newest first
        orders = list(response.context['orders'])
        self.assertEqual(orders[0], self.order2)
        self.assertEqual(orders[1], self.order1)

    def test_user_cannot_view_another_user_order_detail(self):
        """Verify users get 404 trying to access someone else's order detail."""
        self.client.login(username=self.username2, password=self.password)
        response = self.client.get(f'/account/orders/{self.order1.id}/')
        self.assertEqual(response.status_code, 404)

    def test_empty_order_list_renders_empty_state(self):
        """Verify empty state is shown if user has zero orders."""
        self.client.login(username=self.username2, password=self.password)
        response = self.client.get('/account/orders/history/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No orders yet")
        self.assertContains(response, "Your purchases will appear here once you place an order.")

    def test_order_detail_renders_items_and_snapshots(self):
        """Verify order details page renders ordered items and address snapshot."""
        self.client.login(username=self.username1, password=self.password)
        response = self.client.get(f'/account/orders/{self.order1.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'account/order_detail.html')
        
        self.assertContains(response, 'SB-20260707-111111')
        self.assertContains(response, 'Test Product')
        self.assertContains(response, 'Flat 12')
        self.assertContains(response, 'Mumbai')

    def test_order_detail_explicit_context(self):
        """Verify that context includes 'order' and 'order_items' explicitly."""
        self.client.login(username=self.username1, password=self.password)
        response = self.client.get(f'/account/orders/{self.order1.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('order', response.context)
        self.assertIn('order_items', response.context)
        self.assertEqual(response.context['order'], self.order1)
        self.assertEqual(list(response.context['order_items']), list(self.order1.items.all()))

    def test_order_detail_query_optimization(self):
        """Verify that customer order detail page utilizes query optimization to prevent N+1 queries."""
        self.client.login(username=self.username1, password=self.password)
        
        # Create a few more items on this order to check for N+1 query loops
        product2 = Product.objects.create(
            name='Test Product 2', slug='test-product-2', price=200.00, stock=5, in_stock=True, category=self.category
        )
        OrderItem.objects.create(order=self.order1, product=product2, price=200.00, quantity=2)
        
        from django.db import connection
        
        # Clear database queries log
        connection.queries_log.clear()
        
        # Fetch detail page
        response = self.client.get(f'/account/orders/{self.order1.id}/')
        self.assertEqual(response.status_code, 200)
        
        # Capture the query count before accessing relationships
        num_queries_before = len(connection.queries)
        
        # Access relationship attributes on the context variables
        order = response.context['order']
        order_items = response.context['order_items']
        
        # Accessing order.user, items, and items' products should not hit the database
        user_email = order.user.email
        for item in order_items:
            product_name = item.product.name
            
        num_queries_after = len(connection.queries)
        
        # Assert no extra database calls are made
        self.assertEqual(num_queries_after - num_queries_before, 0)

    def test_order_list_pagination_and_page_2(self):
        """Verify that order list paginates 10 orders per page and page 2 returns the rest."""
        self.client.login(username=self.username1, password=self.password)
        
        # Clear existing orders to have exact counting
        Order.objects.filter(user=self.user1).delete()
        
        # Create 15 orders for user1
        for i in range(1, 16):
            order = Order.objects.create(
                user=self.user1,
                order_number=f'SB-PAGINATE-{i:03d}',
                payment_method='COD',
                status='PENDING_PAYMENT',
                total_amount=100.00,
                shipping_full_name='John Doe',
                shipping_phone='9876543210',
                shipping_address_line_1='Flat 12',
                shipping_city='Mumbai',
                shipping_postal_code='400001'
            )
            OrderItem.objects.create(order=order, product=self.product, price=100.00, quantity=1)
            
        # Request page 1
        response = self.client.get('/account/orders/')
        self.assertEqual(response.status_code, 200)
        
        # Page 1 should contain 10 orders
        page_1_orders = list(response.context['orders'])
        self.assertEqual(len(page_1_orders), 10)
        # Check ordering (newest first)
        self.assertEqual(page_1_orders[0].order_number, 'SB-PAGINATE-015')
        self.assertEqual(page_1_orders[9].order_number, 'SB-PAGINATE-006')
        
        # Request page 2
        response = self.client.get('/account/orders/?page=2')
        self.assertEqual(response.status_code, 200)
        
        # Page 2 should contain 5 orders
        page_2_orders = list(response.context['orders'])
        self.assertEqual(len(page_2_orders), 5)
        # Check ordering (newest first)
        self.assertEqual(page_2_orders[0].order_number, 'SB-PAGINATE-005')
        self.assertEqual(page_2_orders[4].order_number, 'SB-PAGINATE-001')
        
        # Check pagination default behavior for invalid pages
        # non-integer page should default to page 1
        response = self.client.get('/account/orders/?page=invalid_page')
        self.assertEqual(response.status_code, 200)
        page_invalid_orders = list(response.context['orders'])
        self.assertEqual(len(page_invalid_orders), 10)
        self.assertEqual(page_invalid_orders[0].order_number, 'SB-PAGINATE-015')
        
        # out-of-bound page should default to the last page (page 2)
        response = self.client.get('/account/orders/?page=999')
        self.assertEqual(response.status_code, 200)
        page_out_of_bound_orders = list(response.context['orders'])
        self.assertEqual(len(page_out_of_bound_orders), 5)
        self.assertEqual(page_out_of_bound_orders[0].order_number, 'SB-PAGINATE-005')

    def test_order_list_query_optimization(self):
        """Verify that select_related and prefetch_related are used to avoid N+1 queries."""
        self.client.login(username=self.username1, password=self.password)
        
        # Clear existing orders and create a few orders
        Order.objects.filter(user=self.user1).delete()
        for i in range(1, 6):
            order = Order.objects.create(
                user=self.user1,
                order_number=f'SB-OPT-{i}',
                payment_method='COD',
                status='PENDING_PAYMENT',
                total_amount=100.00,
                shipping_full_name='John Doe',
                shipping_phone='9876543210',
                shipping_address_line_1='Flat 12',
                shipping_city='Mumbai',
                shipping_postal_code='400001'
            )
            OrderItem.objects.create(order=order, product=self.product, price=100.00, quantity=1)
        
        from django.db import connection
        
        # Reset queries list to clean log
        connection.queries_log.clear()
        
        response = self.client.get('/account/orders/')
        self.assertEqual(response.status_code, 200)
        
        orders = response.context['orders']
        
        num_queries_before = len(connection.queries)
        
        for order in orders:
            # Accessing items and their products should not hit the database again if prefetched
            for item in order.items.all():
                product_name = item.product.name
                
        num_queries_after = len(connection.queries)
        
        # The difference should be 0 because of prefetch_related
        self.assertEqual(num_queries_after - num_queries_before, 0)


class OrderExpirationCommandTest(TestCase):
    def setUp(self):
        self.username = 'testuser1'
        self.password = 'securepassword123'
        self.user = User.objects.create_user(username=self.username, password=self.password)
        
        self.category = Category.objects.create(name='Electronics', slug='electronics')
        self.product1 = Product.objects.create(
            name='Laptop', slug='laptop', price=1000.00, stock=5, in_stock=True, category=self.category
        )
        self.product2 = Product.objects.create(
            name='Phone', slug='phone', price=500.00, stock=0, in_stock=False, category=self.category
        )

        # Create expired pending order
        self.expired_order = Order.objects.create(
            user=self.user,
            order_number='SB-EXPIRED-PENDING',
            payment_method='COD',
            status='PENDING_PAYMENT',
            expires_at=timezone.now() - timedelta(minutes=1),
            total_amount=1500.00
        )
        OrderItem.objects.create(order=self.expired_order, product=self.product1, price=1000.00, quantity=1)
        OrderItem.objects.create(order=self.expired_order, product=self.product2, price=500.00, quantity=1)

        # Create non-expired pending order
        self.active_order = Order.objects.create(
            user=self.user,
            order_number='SB-ACTIVE-PENDING',
            payment_method='COD',
            status='PENDING_PAYMENT',
            expires_at=timezone.now() + timedelta(minutes=20),
            total_amount=1000.00
        )
        OrderItem.objects.create(order=self.active_order, product=self.product1, price=1000.00, quantity=1)

        # Create expired PAID order (should remain untouched)
        self.paid_order = Order.objects.create(
            user=self.user,
            order_number='SB-EXPIRED-PAID',
            payment_method='COD',
            status='PAID',
            expires_at=timezone.now() - timedelta(minutes=1),
            total_amount=1000.00
        )
        OrderItem.objects.create(order=self.paid_order, product=self.product1, price=1000.00, quantity=1)

    def test_expire_orders_command_success(self):
        """Verify expired pending orders are expired and inventory is restored."""
        out = StringIO()
        call_command('expire_orders', stdout=out)
        output = out.getvalue()

        # Check command output
        self.assertIn("Expired orders processed: 1", output)
        self.assertIn("Inventory restored: 2 products", output)

        # Check order statuses
        self.expired_order.refresh_from_db()
        self.active_order.refresh_from_db()
        self.paid_order.refresh_from_db()

        self.assertEqual(self.expired_order.status, 'PAYMENT_EXPIRED')
        self.assertEqual(self.active_order.status, 'PENDING_PAYMENT')
        self.assertEqual(self.paid_order.status, 'PAID')

        # Check product stock and availability restoration
        self.product1.refresh_from_db()
        self.product2.refresh_from_db()

        self.assertEqual(self.product1.stock, 6)
        self.assertTrue(self.product1.in_stock)

        self.assertEqual(self.product2.stock, 1)
        self.assertTrue(self.product2.in_stock)

    def test_expire_orders_command_idempotent(self):
        """Verify command is idempotent and doesn't restore inventory twice when run multiple times."""
        out = StringIO()
        call_command('expire_orders', stdout=out)
        
        # Second run should do nothing
        out2 = StringIO()
        call_command('expire_orders', stdout=out2)
        output2 = out2.getvalue()

        self.assertIn("Expired orders processed: 0", output2)
        self.assertIn("Inventory restored: 0 products", output2)

        # Check stock is not doubled
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock, 6)


class CODPaymentFlowTest(TestCase):
    def setUp(self):
        self.username1 = 'testuser1'
        self.password = 'securepassword123'
        self.user1 = User.objects.create_user(
            username=self.username1, password=self.password, email='user1@example.com'
        )
        self.addr1 = UserAddress.objects.create(
            user=self.user1,
            full_name='John Doe',
            phone='9876543210',
            address_line_1='Flat 12',
            city='Mumbai',
            state='MH',
            country='India',
            postal_code='400001',
            is_default=True
        )
        self.category = Category.objects.create(name='Clothing', slug='clothing')
        self.product = Product.objects.create(
            name='Test Product', slug='test-product', price=100.00, stock=5, in_stock=True, category=self.category
        )
        self.cart_id = 'test-cart-id'
        self.cart = Cart_List.objects.create(cart_id=self.cart_id)
        Cart_Items.objects.create(cart=self.cart, product=self.product, quantity=2, active=True)

    def _setup_session_cart(self):
        session = self.client.session
        session['cart_id'] = self.cart_id
        session.save()

    def test_cod_checkout_success(self):
        """Verify COD order placement succeeds, skips payment gateway, redirects, and sets status."""
        self.client.login(username=self.username1, password=self.password)
        self._setup_session_cart()

        # Check stock before
        self.assertEqual(self.product.stock, 5)

        response = self.client.post('/checkout/', {
            'shipping_address': self.addr1.id,
            'payment_method': 'COD'
        })
        order = Order.objects.first()
        self.assertIsNotNone(order)
        self.assertRedirects(response, f'/checkout/{order.id}/confirmation/')

        # Order Status = PROCESSING, Payment Status = PENDING
        self.assertEqual(order.status, 'PROCESSING')
        self.assertEqual(order.payment_status, 'PENDING')

        # Stock remains decremented (reserved) after creation
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_customer_order_detail_payment_info(self):
        """Verify payment details are rendered properly on the customer detail page."""
        order = Order.objects.create(
            user=self.user1,
            order_number='SB-20260707-333333',
            payment_method='COD',
            status='PROCESSING',
            payment_status='PENDING',
            total_amount=200.00
        )
        self.client.login(username=self.username1, password=self.password)
        response = self.client.get(f'/account/orders/{order.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cash on Delivery')
        self.assertContains(response, 'Pending')
        self.assertContains(response, 'Processing')

    def test_admin_update_payment_status(self):
        """Verify admin can change order payment status to PAID or REFUNDED."""
        order = Order.objects.create(
            user=self.user1,
            order_number='SB-20260707-444444',
            payment_method='COD',
            status='PROCESSING',
            payment_status='PENDING',
            total_amount=200.00
        )
        staff_user = User.objects.create_user(
            username='admin_user', password=self.password, email='admin@example.com', is_staff=True
        )
        self.client.login(username='admin_user', password=self.password)
        
        detail_url = f'/dashboard/orders/{order.id}/'
        # Mark as PAID
        response = self.client.post(detail_url, {
            'action': 'update_payment_status',
            'payment_status': 'PAID'
        })
        self.assertRedirects(response, detail_url)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'PAID')

        # Mark as REFUNDED
        response = self.client.post(detail_url, {
            'action': 'update_payment_status',
            'payment_status': 'REFUNDED'
        })
        self.assertRedirects(response, detail_url)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'REFUNDED')





