from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from .forms import UserAddressForm
from .models import UserAddress

class UserAddressFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword123',
            email='testuser@example.com'
        )
        self.base_data = {
            'full_name': 'John Doe',
            'phone': '9876543210',
            'address_line_1': 'Flat 101, building A',
            'address_line_2': 'Street 2',
            'landmark': 'Near Hospital',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'country': 'India',
            'postal_code': '400001',
            'address_type': 'HOME',
            'is_default': False,
        }

    def test_valid_form_data(self):
        """Verify the form is valid with standard mock data."""
        form = UserAddressForm(data=self.base_data, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_phone_validation_strips_spaces(self):
        """Verify clean_phone strips spaces and validates only digits."""
        data = self.base_data.copy()
        data['phone'] = ' 987 654 3210 '
        form = UserAddressForm(data=data, user=self.user)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['phone'], '9876543210')

    def test_phone_validation_non_digits(self):
        """Verify clean_phone fails with alphabetical characters."""
        data = self.base_data.copy()
        data['phone'] = '987654abc0'
        form = UserAddressForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)
        self.assertEqual(form.errors['phone'][0], "Phone number must contain only digits.")

    def test_phone_validation_invalid_length(self):
        """Verify clean_phone fails if length is not between 9 and 15 digits."""
        data = self.base_data.copy()
        data['phone'] = '12345678'  # 8 digits
        form = UserAddressForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)
        self.assertEqual(form.errors['phone'][0], "Phone number must be between 9 and 15 digits.")

    def test_postal_code_validation_strips_spaces(self):
        """Verify clean_postal_code strips spaces and validates successfully."""
        data = self.base_data.copy()
        data['postal_code'] = ' 400 001 '
        form = UserAddressForm(data=data, user=self.user)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['postal_code'], '400001')

    def test_postal_code_validation_invalid(self):
        """Verify clean_postal_code fails if not 5 or 6 digits."""
        data = self.base_data.copy()
        data['postal_code'] = '1234'  # 4 digits
        form = UserAddressForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('postal_code', form.errors)
        self.assertEqual(form.errors['postal_code'][0], "Enter a valid 5 or 6 digit PIN code.")

    def test_max_address_limit_blocks_new_address(self):
        """Verify clean() prevents users from saving more than 20 active addresses."""
        # Create 20 active addresses
        for i in range(20):
            UserAddress.objects.create(
                user=self.user,
                full_name=f'Name {i}',
                phone='9876543210',
                address_line_1='Address line 1',
                city='City',
                state='State',
                postal_code='123456',
                address_type='HOME',
                is_active=True
            )
        
        # Verify creating another one fails
        form = UserAddressForm(data=self.base_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
        self.assertEqual(form.errors['__all__'][0], "You have reached the maximum number of saved addresses.")

    def test_max_address_limit_allows_edit(self):
        """Verify editing an existing address is allowed even if the user has 20 active addresses."""
        # Create 20 active addresses
        addresses = []
        for i in range(20):
            addresses.append(
                UserAddress.objects.create(
                    user=self.user,
                    full_name=f'Name {i}',
                    phone='9876543210',
                    address_line_1='Address line 1',
                    city='City',
                    state='State',
                    postal_code='123456',
                    address_type='HOME',
                    is_active=True
                )
            )

        # Edit the last address
        last_address = addresses[-1]
        data = self.base_data.copy()
        data['full_name'] = 'Updated Name'
        
        form = UserAddressForm(data=data, instance=last_address, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)


class UserAddressListViewTest(TestCase):
    def setUp(self):
        self.username = 'testuser'
        self.password = 'securepassword123'
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
            email='testuser@example.com'
        )
        self.address_url = '/account/addresses/'

    def test_unauthenticated_redirect(self):
        """Verify unauthenticated access to address list redirects to login."""
        response = self.client.get(self.address_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_empty_address_list(self):
        """Verify authenticated empty address list shows correct empty state."""
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.address_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No saved addresses yet.")
        self.assertContains(response, "Add Your First Address")

    def test_populated_address_list_ordering(self):
        """Verify addresses are displayed, active only, and ordered by is_default and updated_at."""
        self.client.login(username=self.username, password=self.password)
        
        # Create non-default address first
        addr1 = UserAddress.objects.create(
            user=self.user,
            full_name='Address One',
            phone='9876543210',
            address_line_1='Address Line 1-A',
            city='Mumbai',
            state='MH',
            postal_code='400001',
            is_default=False
        )

        # Create default address second
        addr2 = UserAddress.objects.create(
            user=self.user,
            full_name='Address Two (Default)',
            phone='9876543210',
            address_line_1='Address Line 2-A',
            city='Delhi',
            state='DL',
            postal_code='110001',
            is_default=True
        )

        # Create a soft-deleted address (is_active=False)
        addr3 = UserAddress.objects.create(
            user=self.user,
            full_name='Soft Deleted Address',
            phone='9876543210',
            address_line_1='Address Line 3-A',
            city='Bangalore',
            state='KA',
            postal_code='560001',
            is_active=False
        )

        response = self.client.get(self.address_url)
        self.assertEqual(response.status_code, 200)
        
        # Verify rendered addresses
        self.assertContains(response, 'Address One')
        self.assertContains(response, 'Address Two (Default)')
        self.assertNotContains(response, 'Soft Deleted Address')

        # Check default badge is present
        self.assertContains(response, 'Default')

        # Check ordering is correct (addr2 first, then addr1)
        addresses_in_context = list(response.context['addresses'])
        self.assertEqual(addresses_in_context[0].pk, addr2.pk)
        self.assertEqual(addresses_in_context[1].pk, addr1.pk)


class UserAddressCreateViewTest(TestCase):
    def setUp(self):
        self.username = 'testuser'
        self.password = 'securepassword123'
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
            email='testuser@example.com'
        )
        self.add_url = '/account/addresses/add/'
        self.list_url = '/account/addresses/'
        self.valid_data = {
            'full_name': 'Jane Doe',
            'phone': '9876543210',
            'address_line_1': 'Building B, Floor 2',
            'address_line_2': 'Street 10',
            'landmark': 'Opposite Library',
            'city': 'Bangalore',
            'state': 'Karnataka',
            'country': 'India',
            'postal_code': '560001',
            'address_type': 'WORK',
            'is_default': False,
        }

    def test_unauthenticated_redirect(self):
        """Verify unauthenticated access to add address page redirects to login."""
        response = self.client.get(self.add_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_get_add_address_renders_form(self):
        """Verify authenticated GET request on add address page renders form successfully."""
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.add_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add New Address')
        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_post_add_address_success(self):
        """Verify a valid POST request saves the address and redirects."""
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.add_url, self.valid_data)
        
        # Should redirect to address_list
        self.assertRedirects(response, self.list_url)
        
        # Verify address is saved in database
        addresses = UserAddress.objects.filter(user=self.user)
        self.assertEqual(addresses.count(), 1)
        address = addresses.first()
        self.assertEqual(address.full_name, 'Jane Doe')
        self.assertEqual(address.phone, '9876543210')
        self.assertEqual(address.city, 'Bangalore')
        
        # First address should automatically be set to default
        self.assertTrue(address.is_default)

    def test_post_add_address_failure_validation_errors(self):
        """Verify invalid POST requests keep user on page and render errors."""
        self.client.login(username=self.username, password=self.password)
        invalid_data = self.valid_data.copy()
        invalid_data['phone'] = 'abc1234567'
        
        response = self.client.post(self.add_url, invalid_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Phone number must contain only digits.')
        self.assertEqual(UserAddress.objects.filter(user=self.user).count(), 0)



