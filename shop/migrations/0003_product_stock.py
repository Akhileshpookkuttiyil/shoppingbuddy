# Generated by Django 3.2.9 on 2021-12-15 15:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0002_product_color'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='stock',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
    ]
