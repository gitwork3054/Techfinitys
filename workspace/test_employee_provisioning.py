"""Regression tests for secure, idempotent named employee provisioning."""

import os
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from workspace.models import Member


STAFF_NAMES = ('priya', 'yatri', 'janvi', 'maya', 'mahi')
SAMPLE_SECRET = 'ExampleStrongSharedPass-2026!'


class EmployeeProvisioningTests(TestCase):
    def run_seed(self, secret=SAMPLE_SECRET):
        output = StringIO()
        with patch.dict(os.environ, {'CRM_EMPLOYEE_INITIAL_PASSWORD': secret}):
            call_command('ensure_employees', stdout=output)
        return output.getvalue()

    def test_creates_five_regular_employees_with_one_common_password(self):
        output = self.run_seed()
        User = get_user_model()
        self.assertEqual(User.objects.filter(username__in=STAFF_NAMES).count(), 5)
        for username in STAFF_NAMES:
            user = User.objects.get(username=username)
            self.assertEqual(user.first_name.lower(), username)
            self.assertTrue(user.check_password(SAMPLE_SECRET))
            self.assertFalse(user.is_staff)
            self.assertFalse(user.is_superuser)
            self.assertTrue(user.is_active)
            member = Member.objects.get(user=user)
            self.assertEqual(member.role, 'employee')
            self.assertIsNone(member.client_account)
            self.assertTrue(member.is_active)
        self.assertIn('5 created', output)
        self.assertNotIn(SAMPLE_SECRET, output)

    def test_repeated_startup_preserves_existing_employee_passwords(self):
        self.run_seed()
        User = get_user_model()
        priya = User.objects.get(username='priya')
        priya.set_password('PriyaChangedHerOwnPassword#2026')
        priya.save(update_fields=['password'])
        result = self.run_seed()
        priya.refresh_from_db()
        self.assertTrue(priya.check_password('PriyaChangedHerOwnPassword#2026'))
        self.assertFalse(priya.check_password(SAMPLE_SECRET))
        self.assertEqual(User.objects.filter(username__in=STAFF_NAMES).count(), 5)
        self.assertIn('0 created, 5 already existed', result)

    def test_existing_privileged_username_is_not_hijacked(self):
        User = get_user_model()
        manager_user = User.objects.create_superuser('maya', password='KeepExistingAdminPassword#2026')
        Member.objects.create(user=manager_user, role='admin')
        self.run_seed()
        manager_user.refresh_from_db()
        self.assertTrue(manager_user.check_password('KeepExistingAdminPassword#2026'))
        self.assertEqual(manager_user.workspace_member.role, 'admin')
        self.assertEqual(User.objects.filter(username__in=STAFF_NAMES).count(), 5)
        self.assertEqual(Member.objects.filter(role='employee', user__username__in=STAFF_NAMES).count(), 4)

    def test_missing_password_skips_creation(self):
        result = self.run_seed(secret='')
        self.assertIn('skipped', result)
        self.assertFalse(get_user_model().objects.filter(username__in=STAFF_NAMES).exists())

    def test_weak_password_is_rejected(self):
        with self.assertRaises(CommandError):
            self.run_seed(secret='short')
        self.assertFalse(get_user_model().objects.filter(username__in=STAFF_NAMES).exists())