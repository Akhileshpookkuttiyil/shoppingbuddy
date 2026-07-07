from django.test import TestCase
from django.contrib.auth.models import User
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

