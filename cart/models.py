from django.db import models
from shop.models import Product

class Cart_List(models.Model):
    """Represents an anonymous user's shopping cart session."""
    cart_id = models.CharField(max_length=250, unique=True, help_text="The session key associated with this cart.")
    date_added = models.DateTimeField(auto_now_add=True, help_text="When this cart was created.")

    class Meta:
        verbose_name = 'Cart'
        verbose_name_plural = 'Carts'
        ordering = ('-date_added',)

    def __str__(self):
        return str(self.cart_id)

class Cart_Items(models.Model):
    """Represents a specific product and quantity in a shopping cart."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_items', help_text="The product being purchased.")
    cart = models.ForeignKey(Cart_List, on_delete=models.CASCADE, related_name='items', help_text="The cart this item belongs to.")
    quantity = models.IntegerField(help_text="Number of items added.")
    active = models.BooleanField(default=True, help_text="Is this item still active in the cart?")

    class Meta:
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
