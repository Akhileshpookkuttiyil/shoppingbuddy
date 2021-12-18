from django.contrib import admin
from .models import Category,Product
# Register your models here.
class CategoryAdmin(admin.ModelAdmin):
    list_display=['name','slug']
    prepopulated_fields={'slug':('name',)}
admin.site.register(Category,CategoryAdmin)

class ProductAdmin(admin.ModelAdmin):
    list_display=['name','category','description','image','color','price','stock','in_stock','created']
    list_editable=['in_stock','price','stock','color']
    prepopulated_fields={'slug':('name',)}
admin.site.register(Product,ProductAdmin)
