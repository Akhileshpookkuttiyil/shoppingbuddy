from django.test import TestCase, Client
from django.urls import reverse
from .models import Category, Product

class SearchViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name='Electronics', slug='electronics')
        
        # Create a matching product
        self.product1 = Product.objects.create(
            name='Sony WH-1000XM5 Headphones',
            slug='sony-wh-1000xm5',
            category=self.category,
            description='Noise cancelling headphones',
            price=29990,
            stock=15,
            in_stock=True
        )
        
        # Create additional products to test pagination if needed
        # We need more than 12 products to test pagination because Paginator is configured for 12 items per page
        self.other_products = []
        for i in range(15):
            self.other_products.append(
                Product.objects.create(
                    name=f'Gadget {i}',
                    slug=f'gadget-{i}',
                    category=self.category,
                    description='Random gadget matching query gadget',
                    price=999,
                    stock=5,
                    in_stock=True
                )
            )

    def test_search_returns_products_scenario_1(self):
        """Scenario 1: Search term returns products -> grid appears, no empty state."""
        response = self.client.get(reverse('search') + '?q=Sony')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sony WH-1000XM5 Headphones')
        # Check that empty state is not rendered
        self.assertNotContains(response, 'No matches found')

    def test_search_returns_zero_products_scenario_2(self):
        """Scenario 2: Search term returns zero products -> empty state appears, no grid."""
        response = self.client.get(reverse('search') + '?q=NonexistentProduct')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No matches found')
        self.assertNotContains(response, 'grid-cols-1') # Ensure the product grid container is not rendered

    def test_search_pagination_works_scenario_3(self):
        """Scenario 3: Pagination works correctly with search term."""
        # Query matching 'gadget' returns 15 items
        response = self.client.get(reverse('search') + '?q=gadget')
        self.assertEqual(response.status_code, 200)
        # Page 1: Check pagination controls are rendered with correct page span tags
        self.assertContains(response, 'Showing page <span class="font-bold text-neutral-900">1</span> of <span class="font-bold text-neutral-900">2</span>', html=True)
        
        # Fetch Page 2
        response_page_2 = self.client.get(reverse('search') + '?q=gadget&page=2')
        self.assertEqual(response_page_2.status_code, 200)
        self.assertContains(response_page_2, 'Showing page <span class="font-bold text-neutral-900">2</span> of <span class="font-bold text-neutral-900">2</span>', html=True)
        self.assertNotContains(response_page_2, 'No matches found')

