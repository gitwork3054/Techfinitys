"""Regression tests for secure, idempotent named employee provisioning."""

import os
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

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


class DemoRecordsTests(TestCase):
    def setup_demo(self):
        with patch.dict(os.environ, {'CRM_EMPLOYEE_INITIAL_PASSWORD': SAMPLE_SECRET}):
            call_command('ensure_employees', stdout=StringIO())
        call_command('ensure_demo_records', stdout=StringIO())

    def test_saved_demo_data_is_visible_and_idempotent(self):
        from workspace.models import ClientAccount, ClientAssignment, Project, Task
        self.setup_demo()
        self.assertEqual(ClientAccount.objects.filter(code__startswith='demo-').count(), 5)
        self.assertEqual(Project.objects.filter(group_name='Demo projects').count(), 10)
        self.assertEqual(Task.objects.filter(title__startswith='DEMO |').count(), 30)
        self.assertEqual(ClientAssignment.objects.filter(
            active=True, client__code__startswith='demo-').count(), 5)

        priya = Member.objects.get(user__username='priya')
        project = Project.objects.filter(client__code='demo-aurelia-living').first()
        self.assertEqual(project.owner_id, priya.id)
        task = Task.objects.filter(project=project).first()
        task.title = 'DEMO | Updated by a user'
        task.save(update_fields=['title'])
        self.setup_demo()
        self.assertEqual(ClientAccount.objects.filter(code__startswith='demo-').count(), 5)
        self.assertEqual(Project.objects.filter(group_name='Demo projects').count(), 10)
        self.assertEqual(Task.objects.filter(client__code__startswith='demo-').count(), 30)
        self.assertTrue(Task.objects.filter(pk=task.pk,title='DEMO | Updated by a user').exists())

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_employees_can_view_demo_projects_after_new_login(self):
        from workspace.models import Project, Task
        self.setup_demo()
        employee = Member.objects.get(user__username='yatri')
        self.client.force_login(employee.user)
        first = self.client.get('/api/workspace/')
        self.assertEqual(first.status_code, 200)
        data = first.json()
        self.assertEqual(len([p for p in data['projects'] if p['clientName'].startswith('DEMO |')]), 2)
        self.assertEqual(len([t for t in data['tasks'] if t['title'].startswith('DEMO |')]), 6)
        self.client.logout()
        self.client.force_login(employee.user)
        again = self.client.get('/api/workspace/')
        self.assertEqual(again.status_code, 200)
        self.assertEqual(len([p for p in again.json()['projects'] if p['clientName'].startswith('DEMO |')]), 2)


@override_settings(SECURE_SSL_REDIRECT=False)
class BrowserPushSubscriptionTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from workspace.models import Member
        self.member = Member.objects.create(
            user=User.objects.create_user('push_employee',password='push-test-1234'),
            role='employee',
        )

    def test_push_subscriptions_are_scoped_and_revoked_at_logout(self):
        import json
        from workspace.models import PushSubscription
        from django.test import Client
        endpoint = 'https://fcm.googleapis.com/fcm/send/push-integration-test'
        payload = {
            'action': 'subscribe', 'endpoint': endpoint,
            'keys': {'p256dh': 'x'*80, 'auth': 'y'*22},
        }
        self.client.force_login(self.member.user)
        created = self.client.post('/api/push/subscription/',
            data=json.dumps(payload),content_type='application/json')
        self.assertEqual(created.status_code, 200, created.content)
        self.assertEqual(PushSubscription.objects.filter(member=self.member).count(),1)
        self.client.get('/logout/')
        self.assertFalse(PushSubscription.objects.filter(endpoint=endpoint).exists())

    def test_invalid_and_external_push_endpoints_are_rejected(self):
        import json
        from workspace.models import PushSubscription
        self.client.force_login(self.member.user)
        for endpoint in (
            'http://fcm.googleapis.com/fcm/send/unsafe',
            'https://evil.example.test/collector',
            'https://fcm.googleapis.com.evil.example.test/collector',
            'https://127.0.0.1/private',
        ):
            result=self.client.post('/api/push/subscription/',
                data=json.dumps({'action':'subscribe','endpoint':endpoint,
                    'keys':{'p256dh':'x'*80,'auth':'y'*22}}),
                content_type='application/json')
            self.assertEqual(result.status_code, 400, endpoint)
        self.assertEqual(PushSubscription.objects.count(),0)

    def test_worker_served_from_root_scope(self):
        response=self.client.get('/sw.js')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Service-Worker-Allowed'],'/')
        self.assertIn(b'showNotification',response.content)
