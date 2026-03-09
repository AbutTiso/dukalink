# dashboard/management/commands/fix_stock.py
from django.core.management.base import BaseCommand
from django.db.models import Sum
from orders.models import Order, OrderItem
from products.models import Product

class Command(BaseCommand):
    help = 'Fix product stock based on existing orders'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be done without actually doing it')
        parser.add_argument('--fix', action='store_true', help='Actually fix the stock (set to original stock)')
        parser.add_argument('--product-id', type=int, help='Fix only a specific product')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        should_fix = options['fix']
        product_id = options['product_id']
        
        self.stdout.write("=" * 60)
        self.stdout.write("FIXING PRODUCT STOCK BASED ON ORDERS")
        self.stdout.write("=" * 60)
        
        # Get products
        products = Product.objects.all()
        if product_id:
            products = products.filter(id=product_id)
        
        fixed_count = 0
        error_count = 0
        
        for product in products:
            try:
                # Calculate how many of this product have been sold in non-cancelled orders
                sold_items = OrderItem.objects.filter(
                    product=product,
                    order__status__in=['processing', 'completed']
                ).aggregate(total=Sum('quantity'))['total'] or 0
                
                # Calculate original stock (current stock + sold items)
                original_stock = product.stock + sold_items
                
                self.stdout.write(f"\n📦 Product: {product.name}")
                self.stdout.write(f"   Current stock: {product.stock}")
                self.stdout.write(f"   Sold in active orders: {sold_items}")
                self.stdout.write(f"   Original stock would be: {original_stock}")
                
                if original_stock == 0 and product.stock > 0:
                    self.stdout.write(self.style.WARNING(f"   ⚠️ Product has stock but no sales? This might indicate an issue."))
                
                if should_fix and not dry_run:
                    # Fix the stock if needed
                    product.stock = original_stock
                    product.save()
                    fixed_count += 1
                    self.stdout.write(self.style.SUCCESS(f"   ✅ Fixed: Stock set to {original_stock}"))
                else:
                    self.stdout.write(f"   ℹ️ No changes made (use --fix to apply)")
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f"   ❌ Error processing {product.name}: {str(e)}"))
        
        self.stdout.write("\n" + "=" * 60)
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"✅ Dry run completed. {products.count()} products checked."))
        elif should_fix:
            self.stdout.write(self.style.SUCCESS(f"✅ Fixed {fixed_count} products. Errors: {error_count}"))
        else:
            self.stdout.write(self.style.WARNING("⚠️ No changes made. Run with --fix to apply changes."))