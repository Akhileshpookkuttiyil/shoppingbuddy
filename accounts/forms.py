from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import UserAddress

class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'placeholder': 'Firstname'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'placeholder': 'Lastname'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'placeholder': 'Enter Email'}))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('first_name', 'last_name', 'email')


class UserAddressForm(forms.ModelForm):
    class Meta:
        model = UserAddress
        fields = [
            'full_name', 'phone', 'address_line_1', 'address_line_2',
            'landmark', 'city', 'state', 'country', 'postal_code',
            'address_type', 'is_default'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'Full Name'}),
            'phone': forms.TextInput(attrs={'placeholder': 'Phone Number'}),
            'address_line_1': forms.TextInput(attrs={'placeholder': 'House No, Building, Apartment'}),
            'address_line_2': forms.TextInput(attrs={'placeholder': 'Area, Street, Village'}),
            'landmark': forms.TextInput(attrs={'placeholder': 'Landmark (Optional)'}),
            'city': forms.TextInput(attrs={'placeholder': 'City'}),
            'state': forms.TextInput(attrs={'placeholder': 'State'}),
            'country': forms.TextInput(attrs={'placeholder': 'Country'}),
            'postal_code': forms.TextInput(attrs={'placeholder': 'PIN Code'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Inject standard Tailwind CSS classes programmatically
        for field_name, field in self.fields.items():
            if field_name == 'is_default':
                field.widget.attrs.update({
                    'class': 'w-4 h-4 text-blue-600 border-neutral-300 rounded focus:ring-blue-500 cursor-pointer'
                })
            elif field_name == 'address_type':
                field.widget.attrs.update({
                    'class': 'block w-full px-4 py-2 border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm bg-white cursor-pointer'
                })
            else:
                field.widget.attrs.update({
                    'class': 'block w-full px-4 py-2 border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm placeholder-neutral-400'
                })

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip().replace(' ', '')
        if not phone.isdigit():
            raise forms.ValidationError("Phone number must contain only digits.")
        if len(phone) < 9 or len(phone) > 15:
            raise forms.ValidationError("Phone number must be between 9 and 15 digits.")
        return phone

    def clean_postal_code(self):
        postal_code = self.cleaned_data.get('postal_code', '').strip().replace(' ', '')
        if not postal_code.isdigit() or len(postal_code) not in [5, 6]:
            raise forms.ValidationError("Enter a valid 5 or 6 digit PIN code.")
        return postal_code

    def clean(self):
        cleaned_data = super().clean()
        user = self.user or (self.instance.user if self.instance and hasattr(self.instance, 'user') else None)
        
        # Enforce maximum address limit (20 active addresses)
        if user and not self.instance.pk:
            active_count = UserAddress.objects.filter(user=user, is_active=True).count()
            if active_count >= 20:
                raise forms.ValidationError("You have reached the maximum number of saved addresses.")
                
        return cleaned_data

