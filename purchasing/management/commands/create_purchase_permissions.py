#!/usr/bin/env python
"""
Management command to create purchase permissions
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from purchasing.models import Purchase


class Command(BaseCommand):
    help = 'Create purchase permissions (finance and warehouse)'

    def handle(self, *args, **options):
        # Get content type for Purchase model
        content_type = ContentType.objects.get_for_model(Purchase)
        
        # Create permissions
        permissions = [
            ('purchase_finance', 'Can manage purchase finance (verify, payment, tax invoice)'),
            ('purchase_warehouse', 'Can manage purchase warehouse (create, edit, receive, delete)'),
        ]
        
        created_count = 0
        for codename, name in permissions:
            permission, created = Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={'name': name}
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'[OK] Created permission: {codename}')
                )
                created_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(f'[SKIP] Permission already exists: {codename}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'\n[OK] Created {created_count} new permission(s)')
        )

