"""Employee project feed photo uploads and private file access."""
import io
import tempfile

from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .models import ClientAccount, ClientAssignment, Member, Project, ProjectDiscussion


@override_settings(SECURE_SSL_REDIRECT=False)
class ProjectPhotoUploadTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.media = override_settings(MEDIA_ROOT=self.tmp.name)
        self.media.enable()
        self.addCleanup(self.media.disable)
        self.client_account = ClientAccount.objects.create(code='photo-client', name='Photo client')
        self.project = Project.objects.create(client=self.client_account, title='Design project')
        self.employee = Member.objects.create(
            user=User.objects.create_user('photo_employee', password='demo-pass'),
            role='employee')
        self.outsider = Member.objects.create(
            user=User.objects.create_user('photo_outsider', password='demo-pass'),
            role='employee')
        self.portal = Member.objects.create(
            user=User.objects.create_user('photo_portal', password='demo-pass'),
            role='client', client_account=self.client_account)
        ClientAssignment.objects.create(client=self.client_account, employee=self.employee, active=True)

    def image(self):
        buffer = io.BytesIO()
        Image.new('RGB',(24,24),(44,88,155)).save(buffer,format='PNG')
        return SimpleUploadedFile('preview.png',buffer.getvalue(),content_type='image/png')

    def post(self, visibility='team'):
        return self.client.post('/api/projects-plus/feed-photo/upload/',{
            'projectId':str(self.project.pk),
            'body':'Design preview',
            'visibility':visibility,
            'photo':self.image(),
        })

    def test_employee_can_attach_photo_and_only_authorized_viewers_can_open(self):
        self.client.force_login(self.employee.user)
        response=self.post()
        self.assertEqual(response.status_code,201,response.content)
        post=ProjectDiscussion.objects.get(pk=response.json()['id'])
        self.assertTrue(post.photo)
        photo_url=f'/api/projects-plus/feed-photo/{post.pk}/'
        self.assertEqual(self.client.get(photo_url).status_code,200)
        feed=self.client.get('/api/projects-plus/')
        self.assertEqual(feed.status_code,200,feed.content)
        self.assertEqual(feed.json()['projectFeed'][0]['photoUrl'],photo_url)
        self.client.force_login(self.outsider.user)
        self.assertEqual(self.client.get(photo_url).status_code,404)
        self.client.force_login(self.portal.user)
        self.assertEqual(self.client.get(photo_url).status_code,404)

    def test_client_visible_photo_can_be_viewed_by_its_client(self):
        self.client.force_login(self.employee.user)
        response=self.post('client')
        self.assertEqual(response.status_code,201,response.content)
        self.client.force_login(self.portal.user)
        self.assertEqual(self.client.get(f"/api/projects-plus/feed-photo/{response.json()['id']}/").status_code,200)

    def test_invalid_image_and_unassigned_employee_rejected(self):
        self.client.force_login(self.employee.user)
        bad=SimpleUploadedFile('bad.png',b'not a real picture',content_type='image/png')
        response=self.client.post('/api/projects-plus/feed-photo/upload/',{
            'projectId':str(self.project.pk),'body':'bad','visibility':'team','photo':bad
        })
        self.assertEqual(response.status_code,400,response.content)
        self.client.force_login(self.outsider.user)
        self.assertIn(self.post().status_code,(400,403))
