"""Safely provision the very first production admin once, using secret env vars."""
import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from workspace.models import Member

class Command(BaseCommand):
    help = 'Provision initial admin once if none exists. Never resets existing passwords.'

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write('Super admin already exists; no credentials changed.')
            return
        username = os.environ.get('CRM_ADMIN_USERNAME', 'admin').strip()
        password = os.environ.get('CRM_ADMIN_PASSWORD', '')
        if not password:
            self.stdout.write(self.style.WARNING('No CRM_ADMIN_PASSWORD set; initial admin not created.'))
            return
        if not username or len(password) < 4:
            raise CommandError('Set CRM_ADMIN_USERNAME and CRM_ADMIN_PASSWORD of at least 4 characters.')
        if User.objects.filter(username=username).exists():
            raise CommandError('Initial admin username already belongs to a non-admin account.')
        user = User.objects.create_superuser(username=username, password=password)
        Member.objects.update_or_create(user=user, defaults={'role':'admin','client':'','permissions':[]})
        self.stdout.write(self.style.SUCCESS('Initial super admin created. Credentials were not logged.'))
