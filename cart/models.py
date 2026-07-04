from django.db import models
from shop.models import Product
# Create your models here.
class Cart_List(models.Model):
    cart_id = models.CharField(max_length=250, unique=True)
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.cart_id

class Cart_Items(models.Model):
    product = models.ForeignKey(Product,on_delete=models.CASCADE)
    cart = models.ForeignKey(Cart_List,on_delete=models.CASCADE)
    quantity = models.IntegerField()
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.product
