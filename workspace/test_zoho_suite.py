"""Regression coverage for task detail workflows and tenant boundaries."""
import json
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from .models import ClientAccount, Member, ClientAssignment, Project, Task, TaskComment, TaskChecklistItem, Notification


@override_settings(SECURE_SSL_REDIRECT=False)
class TaskSuiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alpha = ClientAccount.objects.create(code='suite-alpha', name='Suite Alpha')
        cls.beta = ClientAccount.objects.create(code='suite-beta', name='Suite Beta')
        def make(name, role, client=None):
            user = User.objects.create_user(username=name, password='test-password-verified')
            return Member.objects.create(user=user, role=role, client_account=client)
        cls.manager = make('suite-manager', 'manager')
        cls.worker = make('suite-worker', 'employee')
        cls.other = make('suite-other', 'employee')
        cls.portal = make('suite-client', 'client', cls.alpha)
        ClientAssignment.objects.create(client=cls.alpha, employee=cls.worker, active=True)
        ClientAssignment.objects.create(client=cls.beta, employee=cls.other, active=True)
        cls.project = Project.objects.create(client=cls.alpha, title='Launch Website', status='active')
        cls.other_project = Project.objects.create(client=cls.beta, title='Hidden Website', status='active')
        cls.first = Task.objects.create(client=cls.alpha, project=cls.project, title='Storyboard', assigned_to=cls.worker, client_visible=True)
        cls.second = Task.objects.create(client=cls.alpha, project=cls.project, title='Production', assigned_to=cls.worker, client_visible=True)
        cls.secret = Task.objects.create(client=cls.alpha, project=cls.project, title='Private review', assigned_to=cls.worker, client_visible=False)
        cls.foreign = Task.objects.create(client=cls.beta, project=cls.other_project, title='Foreign task', assigned_to=cls.other)

    def login(self, member):
        self.client.force_login(member.user)

    def url(self, task):
        return f'/api/task-detail/{task.pk}/'

    def save(self, task, action, **payload):
        return self.client.post(self.url(task), json.dumps({'action': action, **payload}), content_type='application/json')

    def test_comments_visible_to_client_except_internal(self):
        self.login(self.worker)
        self.assertEqual(self.save(self.first, 'add_comment', body='Status is on track', isInternal=False).status_code, 201)
        self.assertEqual(self.save(self.first, 'add_comment', body='Internal coordination only', isInternal=True).status_code, 201)
        self.assertEqual(TaskComment.objects.filter(task=self.first).count(), 2)
        self.login(self.portal)
        r=self.client.get(self.url(self.first))
        self.assertEqual(r.status_code,200)
        self.assertEqual([c['body'] for c in r.json()['comments']], ['Status is on track'])
        self.assertEqual(self.save(self.first,'add_comment', body='Client feedback').status_code,201)
        self.assertEqual(self.save(self.first,'add_comment', body='private',isInternal=True).status_code,403)
        self.assertEqual(self.client.get(self.url(self.secret)).status_code,403)
        self.assertEqual(self.client.get(self.url(self.foreign)).status_code,400)

    def test_cross_client_reads_writes_are_blocked(self):
        self.login(self.worker)
        self.assertEqual(self.client.get(self.url(self.foreign)).status_code,400)
        self.assertEqual(self.save(self.foreign,'add_comment',body='Should not be visible').status_code,400)
        self.assertFalse(TaskComment.objects.filter(task=self.foreign).exists())

    def test_checklist_owner_permissions(self):
        self.login(self.worker)
        r=self.save(self.first,'add_check',title='Prepare draft')
        self.assertEqual(r.status_code,201)
        cid=r.json()['id']
        self.assertEqual(self.save(self.first,'toggle_check',checkId=cid).status_code,200)
        self.assertTrue(TaskChecklistItem.objects.get(pk=cid).done)
        self.assertEqual(self.save(self.first,'delete_check',checkId=cid).status_code,403)
        self.login(self.other)
        self.assertEqual(self.save(self.first,'toggle_check',checkId=cid).status_code,400)
        self.login(self.manager)
        self.assertEqual(self.save(self.first,'delete_check',checkId=cid).status_code,200)
        self.assertFalse(TaskChecklistItem.objects.filter(pk=cid).exists())

    def test_dependency_is_project_scoped_and_acyclic(self):
        self.login(self.worker)
        self.assertEqual(self.save(self.second,'set_dependency',blockedBy=str(self.first.pk)).status_code,403)
        self.login(self.manager)
        self.assertEqual(self.save(self.second,'set_dependency',blockedBy=str(self.first.pk)).status_code,200)
        self.second.refresh_from_db()
        self.assertEqual(self.second.blocked_by_id, self.first.pk)
        self.assertEqual(self.save(self.first,'set_dependency',blockedBy=str(self.second.pk)).status_code,400)
        self.assertEqual(self.save(self.second,'set_dependency',blockedBy=str(self.foreign.pk)).status_code,400)
        self.assertEqual(self.save(self.second,'set_dependency',blockedBy='').status_code,200)

    def test_duplicate_is_internal_and_does_not_copy_dates(self):
        self.login(self.worker)
        self.assertEqual(self.save(self.first,'duplicate').status_code,403)
        self.login(self.manager)
        r=self.save(self.first,'duplicate')
        self.assertEqual(r.status_code,201)
        copy=Task.objects.get(pk=r.json()['id'])
        self.assertEqual(copy.title,'Copy of Storyboard')
        self.assertFalse(copy.client_visible)
        self.assertIsNone(copy.due_at)
        self.assertEqual(copy.project_id,self.project.pk)
        self.login(self.portal)
        self.assertEqual(self.client.get(self.url(copy)).status_code,403)

    def test_comment_notifications_never_leak_internal_body_to_clients(self):
        self.login(self.worker)
        self.assertEqual(self.save(self.first,'add_comment',body='Super secret internal briefing',isInternal=True).status_code,201)
        self.assertFalse(Notification.objects.filter(recipient=self.portal,body__icontains='Super secret').exists())
        self.assertEqual(self.save(self.first,'add_comment',body='Customer review is ready').status_code,201)
        self.assertTrue(Notification.objects.filter(recipient=self.portal,body__icontains='Customer review is ready').exists())
