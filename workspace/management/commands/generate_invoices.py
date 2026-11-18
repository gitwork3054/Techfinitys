"""Idempotent daily recurring invoice generation.

Use `python manage.py generate_invoices` from a secure daily scheduler attached to
persistent PostgreSQL. This command does not email, charge or debit customers.
"""
from django.core.management.base import BaseCommand
from workspace.billing import generate_due_schedules


class Command(BaseCommand):
    help='Create invoices for active client billing schedules due today (or earlier).'

    def handle(self, *args, **options):
        invoices=generate_due_schedules()
        self.stdout.write(self.style.SUCCESS(f'Generated {len(invoices)} invoices: ' +
            ', '.join(i.invoice_number or str(i.pk) for i in invoices[:12])))
