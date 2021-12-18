from django.db import models
from django.urls import reverse


# Create your models here.
class Category(models.Model):
    name=models.CharField(max_length=255,db_index=True)
    slug=models.SlugField(max_length=255,unique=True)

    class Meta:
        verbose_name_plural='categories'
        ordering=('name',)

    def __str__(self):
        return self.name

    def get_url(self):
        return reverse('product_category',args=[self.slug])

class Product(models.Model):
    name=models.CharField(max_length=255,db_index=True)
    slug=models.SlugField(max_length=255,unique=True)
    category=models.ForeignKey(Category,on_delete=models.CASCADE)
    description=models.TextField(blank=True)
    color=models.CharField(max_length=50,default="None")
    image=models.ImageField(upload_to='images/')
    price=models.IntegerField()
    stock=models.IntegerField()
    in_stock=models.BooleanField(default=True)
    created=models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural='products'

    def __str__(self):
        return self.name

    def get_url(self):
        return reverse('product_detail',args=[self.category.slug,self.slug])
