"""Provision named employee accounts using a password stored only in Render.

Existing users and their passwords are never changed. The command is safe to
run on each application start, including when a demo database is recreated.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from workspace.models import Member


EMPLOYEE_FIRST_NAMES = ('Priya', 'Yatri', 'Janvi', 'Maya', 'Mahi')
SECRET_ENV_VAR = 'CRM_EMPLOYEE_INITIAL_PASSWORD'


class Command(BaseCommand):
    help = 'Create the five requested employee users without changing existing accounts.'

    def handle(self, *args, **options):
        password = os.environ.get(SECRET_ENV_VAR, '')
        if not password:
            self.stdout.write(self.style.WARNING(
                'Employee setup skipped: CRM_EMPLOYEE_INITIAL_PASSWORD is not configured.'
            ))
            return
        if len(password) < 16:
            raise CommandError('CRM_EMPLOYEE_INITIAL_PASSWORD must be at least 16 characters long.')

        User = get_user_model()
        created, existing_employees, conflicts = [], [], []
        with transaction.atomic():
            for first_name in EMPLOYEE_FIRST_NAMES:
                username = first_name.lower()
                existing = User.objects.filter(username__iexact=username).first()
                if existing is not None:
                    member = Member.objects.filter(user=existing).first()
                    if member and member.role == 'employee' and not existing.is_staff and not existing.is_superuser:
                        existing_employees.append(username)
                    else:
                        conflicts.append(username)
                    continue

                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=first_name,
                    is_active=True,
                    is_staff=False,
                    is_superuser=False,
                )
                Member.objects.create(user=user, role='employee', permissions=[], is_active=True)
                created.append(username)

        self.stdout.write(self.style.SUCCESS(
            'Employee provisioning complete: '
            f'{len(created)} created, {len(existing_employees)} already existed, '
            f'{len(conflicts)} username conflicts. No existing passwords changed.'
        ))
        if conflicts:
            self.stdout.write(self.style.WARNING(
                'Existing users with other roles were left untouched: ' + ', '.join(conflicts)
            ))