from django.core.management.base import BaseCommand
from django.utils import timezone
from products.models import Product
from inventory.models import OpnameQueue, OpnameHistory, Stock

class Command(BaseCommand):
    help = 'Trigger opname bulanan (cycle count) dan discrepancy (quantity < 0)'

    def handle(self, *args, **options):
        now = timezone.now()
        count_cycle = 0
        count_discrepancy = 0
        # Cycle count: semua SKU yang belum diopname 30 hari
        for product in Product.objects.all():
            last_opname = OpnameHistory.objects.filter(product=product).order_by('-tanggal_opname').first()
            if not last_opname or (now - last_opname.tanggal_opname).days >= 30:
                if not OpnameQueue.objects.filter(product=product, status='pending').exists():
                    OpnameQueue.objects.create(
                        product=product,
                        prioritas=10,
                        sumber_prioritas='cycle_count',
                        status='pending'
                    )
                    count_cycle += 1
        # Discrepancy: semua SKU yang quantity < 0
        for stock in Stock.objects.filter(quantity__lt=0):
            queue, created = OpnameQueue.objects.get_or_create(
                product=stock.product,
                status='pending',
                defaults={'prioritas': 1, 'sumber_prioritas': 'discrepancy'}
            )
            if not created and queue.prioritas > 1:
                queue.prioritas = 1
                queue.sumber_prioritas = 'discrepancy'
                queue.save(update_fields=['prioritas', 'sumber_prioritas'])
            count_discrepancy += 1
        self.stdout.write(self.style.SUCCESS(f'Opname cycle count: {count_cycle} SKU, discrepancy: {count_discrepancy} SKU')) 