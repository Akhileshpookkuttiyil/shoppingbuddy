from django.db import models, transaction
from django.conf import settings
from django.core.validators import RegexValidator

class UserAddress(models.Model):
    ADDRESS_TYPES = (
        ('HOME', 'Home (All-day delivery)'),
        ('WORK', 'Work (9 AM - 5 PM delivery)'),
        ('OTHER', 'Other'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='addresses',
        help_text="The user profile associated with this address."
    )
    full_name = models.CharField(
        max_length=150,
        help_text="Recipient's full name."
    )
    phone = models.CharField(
        max_length=15,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', message="Enter a valid phone number.")],
        help_text="Contact phone number for shipping updates."
    )
    address_line_1 = models.CharField(
        max_length=255,
        help_text="Flat, House no., Building, Company, Apartment"
    )
    address_line_2 = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Area, Street, Sector, Village"
    )
    landmark = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="E.g. near hospital, mall, school etc."
    )
    city = models.CharField(
        max_length=100,
        help_text="City or Town name."
    )
    state = models.CharField(
        max_length=100,
        help_text="State, Province, or Region."
    )
    country = models.CharField(
        max_length=100,
        default='India',
        help_text="Country name."
    )
    postal_code = models.CharField(
        max_length=10,
        validators=[RegexValidator(r'^\d{5,6}$', message="Enter a valid postal code.")],
        help_text="ZIP or PIN code."
    )
    address_type = models.CharField(
        max_length=10,
        choices=ADDRESS_TYPES,
        default='HOME',
        help_text="Category of address (Home, Work, or Other)."
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Designates this address as the default shipping destination."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this address is active or soft-deleted."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Address"
        verbose_name_plural = "User Addresses"
        ordering = ['-is_default', '-updated_at']

    def save(self, *args, **kwargs):
        with transaction.atomic():
            # Enforce that only one address can be set as default per user
            if self.is_default:
                UserAddress.objects.filter(
                    user=self.user, 
                    is_default=True
                ).exclude(pk=self.pk).update(is_default=False)
            # If this is the user's only address, automatically make it the default
            elif not UserAddress.objects.filter(user=self.user).exclude(pk=self.pk).exists():
                self.is_default = True
                
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.address_type}) - {self.address_line_1}, {self.city}"

