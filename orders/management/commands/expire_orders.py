from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from orders.models import Order

class Command(BaseCommand):
    help = 'Automatically release inventory and expire orders that remain unpaid past their expiration timestamp'

    def handle(self, *args, **options):
        expired_count = 0
        restored_products_count = 0

        with transaction.atomic():
            # Query expired orders with locking and prefetching
            expired_orders = Order.objects.select_for_update().filter(
                status='PENDING_PAYMENT',
                expires_at__lt=timezone.now()
            ).prefetch_related('items__product')

            for order in expired_orders:
                expired_count += 1
                for item in order.items.all():
                    product = item.product
                    product.stock += item.quantity
                    if product.stock > 0:
                        product.in_stock = True
                    product.save(update_fields=['stock', 'in_stock'])
                    restored_products_count += 1

                order.status = 'PAYMENT_EXPIRED'
                order.save(update_fields=['status'])

        self.stdout.write(f"Expired orders processed: {expired_count}")
        self.stdout.write(f"Inventory restored: {restored_products_count} products")
