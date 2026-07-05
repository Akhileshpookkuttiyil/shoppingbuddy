from django.db import models
from django.urls import reverse

class Category(models.Model):
    """Represents a product category to organize the catalog."""
    name = models.CharField(max_length=255, db_index=True, help_text="The display name of the category.")
    slug = models.SlugField(max_length=255, unique=True, help_text="Unique URL-friendly name for routing.")

    class Meta:
        verbose_name = 'category'
        verbose_name_plural = 'categories'
        ordering = ('name',)

    def __str__(self):
        return self.name

    def get_url(self):
        return reverse('product_category', args=[self.slug])

class Product(models.Model):
    """Represents a single product in the catalog."""
    name = models.CharField(max_length=255, db_index=True, help_text="The display name of the product.")
    slug = models.SlugField(max_length=255, unique=True, help_text="Unique URL-friendly name for routing.")
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE, help_text="The category this product belongs to.")
    description = models.TextField(blank=True, help_text="Detailed description of the product.")
    color = models.CharField(max_length=50, default="None", help_text="Primary color of the product.")
    image = models.ImageField(upload_to='images/', help_text="Product image upload.")
    price = models.IntegerField(help_text="Price of the product in rupees.")
    stock = models.IntegerField(help_text="Current inventory level.")
    in_stock = models.BooleanField(default=True, help_text="Is this product currently available for purchase?")
    created = models.DateTimeField(auto_now_add=True, help_text="When this product was added to the catalog.")

    class Meta:
        verbose_name = 'product'
        verbose_name_plural = 'products'
        ordering = ('-created',)

    def __str__(self):
        return self.name

    def get_url(self):
        return reverse('product_detail', args=[self.category.slug, self.slug])

class Wishlist(models.Model):
    """Stores products saved by users for later."""
    user = models.ForeignKey('auth.User', related_name='wishlist', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name='wishlisted_by', on_delete=models.CASCADE)
    added_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'wishlist item'
        verbose_name_plural = 'wishlist items'
        unique_together = ('user', 'product')
        ordering = ('-added_date',)

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"
