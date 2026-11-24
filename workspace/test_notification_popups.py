"""Notification popup polling uses only the current account's notifications."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from workspace.models import Member, Notification


class NotificationPopupTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.one = Member.objects.create(user=User.objects.create_user('popup_one', password='test-pass-1234'), role='employee')
        self.two = Member.objects.create(user=User.objects.create_user('popup_two', password='test-pass-1234'), role='employee')
        self.n1 = Notification.objects.create(recipient=self.one, title='Your assigned task', body='Task changed')
        self.n2 = Notification.objects.create(recipient=self.two, title='Private leave update', body='Not for another employee')

    def test_notification_feed_is_recipient_scoped(self):
        self.client.force_login(self.one.user)
        response = self.client.get('/api/workspace/?notifications_only=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        titles = [item['title'] for item in response.json()['notifications']]
        self.assertIn('Your assigned task', titles)
        self.assertNotIn('Private leave update', titles)

    def test_notification_feed_requires_sign_in(self):
        response = self.client.get('/api/workspace/?notifications_only=1')
        self.assertEqual(response.status_code, 401)

    def test_reading_notification_is_user_scoped(self):
        self.client.force_login(self.one.user)
        result = self.client.post('/api/workspace/',
            data='{"action":"read_notification","id":'+str(self.n2.pk)+'}',
            content_type='application/json')
        self.assertNotEqual(result.status_code, 200)
        self.n2.refresh_from_db()
        self.assertIsNone(self.n2.read_at)

    def test_employee_self_created_task_generates_inbox_notification(self):
        import json
        from workspace.models import ClientAccount, ClientAssignment, Project
        client = ClientAccount.objects.create(name='Test client', code='popup-test')
        project = Project.objects.create(client=client, title='Test delivery')
        ClientAssignment.objects.create(client=client, employee=self.one, active=True)
        self.client.force_login(self.one.user)
        response = self.client.post('/api/workspace/',
            data=json.dumps({'action':'self_create_task','projectId':str(project.pk),'title':'Prepare creative draft'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        feed = self.client.get('/api/workspace/?notifications_only=1')
        self.assertEqual(feed.status_code, 200)
        self.assertTrue(any('Prepare creative draft' in n['title'] for n in feed.json()['notifications']))
        self.assertTrue(all('Private leave update' not in n['title'] for n in feed.json()['notifications']))

    def test_manager_quick_task_notifies_assigned_employee_only(self):
        import json
        from workspace.models import ClientAccount, ClientAssignment, Project
        client = ClientAccount.objects.create(name='Test client', code='popup-test')
        project = Project.objects.create(client=client, title='Test delivery')
        ClientAssignment.objects.create(client=client, employee=self.one, active=True)
        supervisor = Member.objects.create(
            user=get_user_model().objects.create_user('popup_manager', password='test-pass-1234'),
            role='manager')
        self.client.force_login(supervisor.user)
        response = self.client.post('/api/projects-plus/',
            data=json.dumps({'action':'quick_create_task','projectId':str(project.pk),'title':'Review social post'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(Notification.objects.filter(recipient=self.one,title__icontains='Review social post').exists())
        self.assertFalse(Notification.objects.filter(recipient=self.two,title__icontains='Review social post').exists())
