"""Read-only Zoho Projects importer tests: consent, preview, scoping and duplicates."""
import json
import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .models import ClientAccount, Member, Project, ZohoProjectLink


@override_settings(SECURE_SSL_REDIRECT=False)
class ZohoProjectImporterTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = Member.objects.create(
            user=User.objects.create_user('zoho_import_admin', password='testpassword'),
            role='admin')
        self.employee = Member.objects.create(
            user=User.objects.create_user('zoho_import_employee', password='testpassword'),
            role='employee')
        self.client_account = ClientAccount.objects.create(code='zoho-import-test', name='Imported Test Client')
        self.client.force_login(self.admin.user)
        session = self.client.session
        session['zoho_projects_connection'] = {
            'owner': self.admin.user.pk, 'region': 'in',
            'access_token': 'mock-access-token', 'refresh_token': 'mock-refresh-token',
            'expires_at': time.time() + 3500
        }
        session.save()

    def test_requires_manager_role(self):
        self.client.force_login(self.employee.user)
        response = self.client.get('/api/zoho/status/')
        self.assertEqual(response.status_code, 403)

    @patch('workspace.zoho_import.requests.get')
    def test_preview_then_import_is_idempotent(self, mocked_get):
        def response(url, **kwargs):
            result = type('Response', (), {})()
            result.ok = True
            if url.endswith('/projects'):
                result.json = lambda: {'projects': [
                    {'id': '789100', 'name': 'Sample from Zoho', 'status': {'name': 'Active'},
                     'description': 'Example', 'start_date': '2026-11-01'}
                ], 'page_info': {'has_next_page': False}}
            elif url.endswith('/projects/789100'):
                result.json = lambda: {'project': {
                    'id': '789100', 'name': 'Sample from Zoho', 'status': {'name': 'Active'},
                    'description': 'Example', 'start_date': '2026-11-01'
                }}
            else:
                raise AssertionError('Unexpected Zoho API path: ' + url)
            return result
        mocked_get.side_effect = response
        preview = self.client.get('/api/zoho/preview/?portal_id=12345')
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertEqual(preview.json()['projects'][0]['name'], 'Sample from Zoho')
        body = json.dumps({'portal_id': '12345', 'client_id': str(self.client_account.pk),
                           'project_ids': ['789100']})
        first = self.client.post('/api/zoho/import/', body, content_type='application/json')
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(len(first.json()['created']), 1)
        second = self.client.post('/api/zoho/import/', body, content_type='application/json')
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(second.json()['skipped'], 1)
        self.assertEqual(Project.objects.filter(client=self.client_account, title='Sample from Zoho').count(), 1)
        self.assertEqual(ZohoProjectLink.objects.filter(zoho_project_id='789100').count(), 1)

    def test_cannot_import_projects_not_in_preview(self):
        payload = json.dumps({'portal_id': '12345', 'client_id': str(self.client_account.pk),
                              'project_ids': ['999']})
        r = self.client.post('/api/zoho/import/', payload, content_type='application/json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(Project.objects.count(), 0)

    def test_oauth_requires_configuration(self):
        with patch.dict('os.environ', {'ZOHO_PROJECTS_CLIENT_ID': '', 'ZOHO_PROJECTS_CLIENT_SECRET': ''}):
            response = self.client.get('/api/zoho/connect/?region=in')
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('access_token', response.content.decode())
