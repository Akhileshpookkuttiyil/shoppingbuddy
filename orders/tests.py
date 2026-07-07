from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from cart.models import Cart_List, Cart_Items
from shop.models import Product, Category
from accounts.models import UserAddress

class CheckoutViewTest(TestCase):
    def setUp(self):
        self.username = 'testuser'
        self.password = 'securepassword123'
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
            email='testuser@example.com'
        )
        self.category = Category.objects.create(name='Electronics', slug='electronics')
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            price=150.00,
            stock=10,
            in_stock=True,
            category=self.category
        )
        self.checkout_url = '/checkout/'

    def test_unauthenticated_redirect(self):
        """Verify unauthenticated access to checkout page redirects to login."""
        response = self.client.get(self.checkout_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_empty_cart_redirects_to_cart_details(self):
        """Verify accessing checkout with empty cart redirects to cart details."""
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.checkout_url)
        self.assertRedirects(response, reverse('cart_details'))

    def test_authenticated_checkout_with_cart_and_address(self):
        """Verify authenticated checkout with populated cart and addresses renders page successfully."""
        self.client.login(username=self.username, password=self.password)
        
        # Setup cart
        session = self.client.session
        session['cart_id'] = 'test-cart-key'
        session.save()
        
        cart = Cart_List.objects.create(cart_id='test-cart-key')
        Cart_Items.objects.create(cart=cart, product=self.product, quantity=2, active=True)
        
        # Setup address
        address = UserAddress.objects.create(
            user=self.user,
            full_name='John Doe',
            phone='9876543210',
            address_line_1='Flat 101',
            city='Mumbai',
            state='MH',
            postal_code='400001',
            is_default=True
        )

        response = self.client.get(self.checkout_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'checkout.html')
        
        # Check order details in response
        self.assertContains(response, 'Checkout')
        self.assertContains(response, 'Test Product')
        self.assertContains(response, 'Qty: 2')
        self.assertContains(response, '₹300')  # Subtotal
        
        # Check address in response
        self.assertContains(response, 'John Doe')
        self.assertContains(response, 'Flat 101')
        
        # Check payment options
        self.assertContains(response, 'Cash on Delivery')
        self.assertContains(response, 'Razorpay')
        self.assertContains(response, 'Stripe')
        
        # Check disabled button and placeholder warning
        self.assertContains(response, 'Place Order')
        self.assertContains(response, 'Checkout functionality coming soon.')

