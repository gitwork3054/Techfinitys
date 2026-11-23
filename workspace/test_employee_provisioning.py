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

    def test_three_character_password_is_rejected(self):
        with self.assertRaises(CommandError):
            self.run_seed(secret='abc')
        self.assertFalse(get_user_model().objects.filter(username__in=STAFF_NAMES).exists())

    def test_four_character_initial_password_is_accepted(self):
        self.run_seed(secret='a2!Z')
        for username in STAFF_NAMES:
            self.assertTrue(get_user_model().objects.get(username=username).check_password('a2!Z'))

from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.test import override_settings
import json


@override_settings(SECURE_SSL_REDIRECT=False)
class FourCharacterPasswordPolicyTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create_superuser(
            username='password-policy-admin', password='OriginalPassForTest!92'
        )
        Member.objects.create(user=self.superuser, role='admin')
        self.client.force_login(self.superuser)

    def post_action(self, url, **kwargs):
        return self.client.post(url, json.dumps(kwargs), content_type='application/json')

    def test_create_employee_accepts_four_and_rejects_three(self):
        good = self.post_action('/api/workspace/', action='create_member',
                                username='fourstaff', firstName='Four',
                                role='employee', password='abcd')
        self.assertEqual(good.status_code, 200, good.content)
        self.assertTrue(get_user_model().objects.get(username='fourstaff').check_password('abcd'))
        bad = self.post_action('/api/workspace/', action='create_member',
                               username='threestaff', firstName='Three',
                               role='employee', password='abc')
        self.assertEqual(bad.status_code, 400, bad.content)
        self.assertFalse(get_user_model().objects.filter(username='threestaff').exists())

    def test_client_portal_accepts_four_and_rejects_three(self):
        good = self.post_action('/api/workspace/', action='create_client',
                                name='Four Portal Client', code='fourportal',
                                portalUsername='fourportaluser', portalPassword='ab12')
        self.assertEqual(good.status_code, 200, good.content)
        self.assertTrue(get_user_model().objects.get(username='fourportaluser').check_password('ab12'))
        bad = self.post_action('/api/workspace/', action='create_client',
                               name='Three Portal Client', code='threeportal',
                               portalUsername='threeportaluser', portalPassword='abc')
        self.assertEqual(bad.status_code, 400, bad.content)
        self.assertFalse(get_user_model().objects.filter(username='threeportaluser').exists())

    def test_change_password_accepts_four_characters(self):
        changed = self.post_action('/api/operations/', action='change_password',
                                   oldPassword='OriginalPassForTest!92', newPassword='four')
        self.assertEqual(changed.status_code, 200, changed.content)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.check_password('four'))
        short = self.post_action('/api/operations/', action='change_password',
                                 oldPassword='four', newPassword='abc')
        self.assertEqual(short.status_code, 400, short.content)
        identical = self.post_action('/api/operations/', action='change_password',
                                     oldPassword='four', newPassword='four')
        self.assertEqual(identical.status_code, 400, identical.content)

    def test_django_minimum_length_is_four(self):
        self.assertIsNone(validate_password('x5#Z'))
        with self.assertRaises(ValidationError):
            validate_password('abc')


class InitialAdminPasswordPolicyTests(TestCase):
    def test_four_character_admin_password_is_accepted(self):
        with patch.dict(os.environ, {'CRM_ADMIN_USERNAME':'four-admin', 'CRM_ADMIN_PASSWORD':'ab12'}):
            call_command('ensure_admin', stdout=StringIO())
        self.assertTrue(get_user_model().objects.get(username='four-admin').check_password('ab12'))

    def test_three_character_admin_password_is_rejected(self):
        with patch.dict(os.environ, {'CRM_ADMIN_USERNAME':'three-admin', 'CRM_ADMIN_PASSWORD':'abc'}):
            with self.assertRaises(CommandError):
                call_command('ensure_admin', stdout=StringIO())
        self.assertFalse(get_user_model().objects.filter(username='three-admin').exists())
