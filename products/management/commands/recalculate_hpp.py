"""
Management command to recalculate HPP (Harga Pokok Penjualan) for all products
using weighted average method from PriceHistory

Usage: python manage.py recalculate_hpp
"""

from django.core.management.base import BaseCommand
from django.db.models import Sum
from products.models import Product
from purchasing.models import PriceHistory


class Command(BaseCommand):
    help = 'Recalculate HPP (Weighted Average) for all products from PriceHistory'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sku',
            type=str,
            help='Calculate HPP for specific SKU only',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )

    def handle(self, *args, **options):
        sku = options.get('sku')
        verbose = options.get('verbose', False)
        
        if sku:
            # Calculate for specific product
            try:
                product = Product.objects.get(sku=sku)
                products = [product]
                self.stdout.write(f"Calculating HPP for SKU: {sku}")
            except Product.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Product with SKU '{sku}' not found"))
                return
        else:
            # Calculate for all products
            products = Product.objects.all()
            self.stdout.write(f"Calculating HPP for {products.count()} products...")
        
        success_count = 0
        no_history_count = 0
        error_count = 0
        
        for product in products:
            try:
                # Get all price history for this product (ordered by date)
                price_histories = PriceHistory.objects.filter(product=product).order_by('purchase_date')
                
                if not price_histories.exists():
                    no_history_count += 1
                    if verbose:
                        self.stdout.write(f"  {product.sku}: No price history")
                    continue
                
                # Calculate HPP using simple weighted average method
                # Start with first purchase as initial HPP
                hpp_current = 0
                qty_current = 0
                
                for ph in price_histories:
                    harga_beli = float(ph.price)
                    qty_beli = ph.quantity
                    
                    if hpp_current == 0:
                        # First purchase
                        hpp_current = harga_beli
                        qty_current = qty_beli
                    else:
                        # Weighted average: (HPP_lama × Qty_lama + Harga_Beli × Qty_Beli) / (Qty_lama + Qty_Beli)
                        total_cost = (hpp_current * qty_current) + (harga_beli * qty_beli)
                        total_qty = qty_current + qty_beli
                        
                        if total_qty > 0:
                            hpp_current = total_cost / total_qty
                            qty_current = total_qty
                
                old_hpp = product.hpp or 0
                product.hpp = round(hpp_current, 2)
                product.save(update_fields=['hpp'])
                
                success_count += 1
                
                if verbose:
                    change = product.hpp - old_hpp if old_hpp > 0 else 0
                    self.stdout.write(
                        f"  {product.sku}: HPP = Rp {product.hpp:,.0f} "
                        f"(based on {price_histories.count()} purchases) "
                        f"[Change: {change:+,.0f}]"
                    )
                        
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f"  Error calculating HPP for {product.sku}: {str(e)}")
                )
        
        # Summary
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS(f"✓ Successfully calculated HPP for {success_count} products"))
        if no_history_count > 0:
            self.stdout.write(self.style.WARNING(f"⚠ {no_history_count} products have no price history"))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"✗ {error_count} products failed"))
        self.stdout.write("="*60)

