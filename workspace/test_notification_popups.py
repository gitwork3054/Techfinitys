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
