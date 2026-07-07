from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils import timezone
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



