"""Integration tests for private WorkChat, Google SSO, avatars and tenant history.

Execute: python manage.py test workspace.test_collaboration -v 2
"""
import io
import json
import tempfile
from unittest.mock import patch

from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .models import (
    ClientAccount, ClientAssignment, Member, Project,
    ChatConversation, ChatMessage, ChatParticipant, RecentProjectVisit,
)


class CollaborationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def person(username, role, client=None):
            user=User.objects.create_user(username=username,email=username+'@example.com',password='correct-horse-battery-123')
            return Member.objects.create(user=user,role=role,client_account=client)
        cls.alpha=ClientAccount.objects.create(code='collab-alpha',name='Collaboration Alpha')
        cls.beta=ClientAccount.objects.create(code='collab-beta',name='Collaboration Beta')
        cls.admin=person('collab-admin','admin')
        cls.alice=person('collab-alice','employee')
        cls.bob=person('collab-bob','employee')
        cls.outsider=person('collab-outsider','employee')
        cls.client_a=person('collab-clienta','client',cls.alpha)
        cls.client_b=person('collab-clientb','client',cls.beta)
        ClientAssignment.objects.create(client=cls.alpha,employee=cls.alice)
        ClientAssignment.objects.create(client=cls.alpha,employee=cls.bob)
        ClientAssignment.objects.create(client=cls.beta,employee=cls.outsider)
        cls.project_a=Project.objects.create(client=cls.alpha,title='Project Alpha')
        cls.project_b=Project.objects.create(client=cls.beta,title='Project Beta')

    def enter(self, who):
        self.client.force_login(who.user)

    def call(self, action, **values):
        return self.client.post('/api/collaboration/',data=json.dumps({'action':action,**values}),content_type='application/json')

    def test_recent_projects_are_restricted_to_member_client_scope(self):
        self.enter(self.alice)
        response=self.client.get('/api/collaboration/').json()
        self.assertEqual({p['id'] for p in response['recentProjects']},{str(self.project_a.pk)})
        self.assertEqual(self.call('visit_project',projectId=str(self.project_b.pk)).status_code,403)
        self.assertEqual(RecentProjectVisit.objects.count(),0)
        self.assertEqual(self.call('visit_project',projectId=str(self.project_a.pk)).status_code,200)
        self.assertEqual(self.client.get('/api/collaboration/').json()['recentProjects'][0]['name'],'Project Alpha')
        self.enter(self.client_b)
        self.assertNotIn(str(self.project_a.pk),{p['id'] for p in self.client.get('/api/collaboration/').json()['recentProjects']})

    def test_direct_messages_require_membership_and_clients_are_excluded(self):
        self.enter(self.alice)
        r=self.call('start_chat',kind='direct',memberIds=[self.bob.pk])
        self.assertEqual(r.status_code,200,r.content)
        chat_id=r.json()['conversation']['id']
        again=self.call('start_chat',kind='direct',memberIds=[self.bob.pk])
        self.assertEqual(again.json()['conversation']['id'],chat_id)
        self.assertEqual(ChatConversation.objects.count(),1)
        self.assertEqual(ChatParticipant.objects.count(),2)
        self.assertEqual(self.call('send_chat',conversationId=chat_id,body='Hello Bob').status_code,200)
        self.assertEqual(ChatMessage.objects.count(),1)
        self.enter(self.bob)
        inbox=self.client.get('/api/collaboration/').json()
        self.assertEqual(inbox['conversations'][0]['unread'],1)
        self.assertEqual(self.client.get(f'/api/collaboration/thread/{chat_id}/').status_code,200)
        self.assertEqual(self.client.get('/api/collaboration/').json()['conversations'][0]['unread'],0)
        self.enter(self.outsider)
        self.assertEqual(self.client.get(f'/api/collaboration/thread/{chat_id}/').status_code,403)
        self.assertEqual(self.call('send_chat',conversationId=chat_id,body='Unauthorized').status_code,403)
        self.enter(self.client_a)
        result=self.client.get('/api/collaboration/').json()
        self.assertEqual(result['chatEnabled'],False)
        self.assertNotIn('conversations',result)
        self.assertEqual(self.call('start_chat',kind='direct',memberIds=[self.bob.pk]).status_code,403)

    def test_group_chat_and_membership_enforced(self):
        self.enter(self.alice)
        created=self.call('start_chat',kind='group',title='Content Team',memberIds=[self.bob.pk])
        self.assertEqual(created.status_code,200)
        conv=created.json()['conversation']['id']
        self.assertEqual(ChatParticipant.objects.filter(conversation_id=conv).count(),2)
        self.assertEqual(self.call('add_chat_members',conversationId=conv,memberIds=[self.outsider.pk]).status_code,200)
        self.enter(self.outsider)
        self.assertEqual(self.client.get(f'/api/collaboration/thread/{conv}/').status_code,200)
        self.assertEqual(self.call('add_chat_members',conversationId=conv,memberIds=[self.admin.pk]).status_code,403)
        self.assertEqual(self.call('leave_chat',conversationId=conv).status_code,200)
        self.assertEqual(self.client.get(f'/api/collaboration/thread/{conv}/').status_code,403)

    def test_image_upload_normalizes_to_webp_and_other_client_cannot_view(self):
        self.enter(self.alice)
        output=io.BytesIO()
        Image.new('RGB',(250,180),(120,50,220)).save(output,'PNG')
        image=SimpleUploadedFile('avatar.png',output.getvalue(),content_type='image/png')
        with tempfile.TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            response=self.client.post('/api/collaboration/profile/',{
                'firstName':'Alice','lastName':'Team','phone':'1112223333','photo':image
            })
            self.assertEqual(response.status_code,200,response.content)
            self.alice.refresh_from_db()
            self.assertEqual(self.alice.user.first_name,'Alice')
            self.assertEqual(self.alice.profile_photo.name.endswith('.webp'),True)
            self.assertEqual(self.client.get(f'/api/collaboration/avatar/{self.alice.id}/').status_code,200)
            self.enter(self.client_b)
            self.assertEqual(self.client.get(f'/api/collaboration/avatar/{self.alice.id}/').status_code,403)
            self.enter(self.client_a)
            self.assertEqual(self.client.get(f'/api/collaboration/avatar/{self.alice.id}/').status_code,200)

    def test_profile_rejects_non_image_data(self):
        self.enter(self.alice)
        bad=SimpleUploadedFile('avatar.png',b'not really an image',content_type='image/png')
        result=self.client.post('/api/collaboration/profile/',{'photo':bad})
        self.assertEqual(result.status_code,400)
        self.alice.refresh_from_db()
        self.assertFalse(bool(self.alice.profile_photo))


@override_settings(GOOGLE_OAUTH_CLIENT_ID='demo-client-id',GOOGLE_OAUTH_CLIENT_SECRET='demo-secret',
                   GOOGLE_OAUTH_REDIRECT_URI='http://testserver/auth/google/callback/')
class GoogleSignInTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=User.objects.create_user(username='sso-worker',email='sso-worker@example.com',password='a-local-password-123')
        cls.member=Member.objects.create(user=cls.user,role='employee')

    def begin(self):
        start=self.client.get('/auth/google/')
        self.assertEqual(start.status_code,302)
        self.assertIn('accounts.google.com',start['Location'])
        return self.client.session['tf_google_state'],self.client.session['tf_google_nonce']

    def test_valid_verified_email_can_sign_in_and_state_is_single_use(self):
        state,nonce=self.begin()
        fake_response=type('Response',(),{'raise_for_status':lambda self:None,
                   'json':lambda self:{'id_token':'verified-jwt'}})()
        with patch('workspace.google_signin.requests.post',return_value=fake_response),\
             patch('google.oauth2.id_token.verify_oauth2_token',return_value={
                 'email':'sso-worker@example.com','email_verified':True,'sub':'google-stable-123',
                 'nonce':nonce,'iss':'https://accounts.google.com'}):
            callback=self.client.get('/auth/google/callback/',{'state':state,'code':'temporary-code'})
        self.assertEqual(callback.status_code,302)
        self.member.refresh_from_db()
        self.assertEqual(self.member.google_sub,'google-stable-123')
        self.assertEqual(int(self.client.session['_auth_user_id']),self.user.pk)
        replay=self.client.get('/auth/google/callback/',{'state':state,'code':'temporary-code'})
        self.assertEqual(replay.status_code,400)

    def test_wrong_state_and_unverified_email_are_rejected(self):
        state,nonce=self.begin()
        self.assertEqual(self.client.get('/auth/google/callback/',{'state':'hijack','code':'bad'}).status_code,400)
        state,nonce=self.begin()
        fake_response=type('Response',(),{'raise_for_status':lambda self:None,
                   'json':lambda self:{'id_token':'jwt'}})()
        with patch('workspace.google_signin.requests.post',return_value=fake_response),\
             patch('google.oauth2.id_token.verify_oauth2_token',return_value={
                 'email':'sso-worker@example.com','email_verified':False,'sub':'sso-sub',
                 'nonce':nonce,'iss':'https://accounts.google.com'}):
            result=self.client.get('/auth/google/callback/',{'state':state,'code':'code'})
        self.assertEqual(result.status_code,302)
        self.assertIn('google_error=invalid',result['Location'])
        self.member.refresh_from_db()
        self.assertFalse(self.member.google_sub)
