"""Regression tests for tenant isolation and approval transitions.

Run with: python manage.py test workspace -v 2
These exercise the actual Django views and database (not UI mocks).
"""
import json
from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from .models import (
    Member, ClientAccount, ClientAssignment, Project, Task, Update, Note,
    ActivityLog, Attendance, LeaveRequest, TimeEntry, ApprovalRequest,
    SupportTicket, TicketMessage, ProjectMilestone, Lead, SavedView, Record
)


class OperationsAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def user(name, role, client=None):
            account = User.objects.create_user(username=name, password='demo-regression-strong-123')
            return Member.objects.create(user=account, role=role, client_account=client)
        cls.a = ClientAccount.objects.create(name='Test Client Alpha', code='test-alpha')
        cls.b = ClientAccount.objects.create(name='Test Client Beta', code='test-beta')
        cls.manager = user('test_manager', 'manager')
        cls.worker = user('test_worker', 'employee')
        cls.other = user('test_other', 'employee')
        cls.client_a = user('test_client_a', 'client', cls.a)
        cls.client_b = user('test_client_b', 'client', cls.b)
        ClientAssignment.objects.create(client=cls.a, employee=cls.worker, assigned_by=cls.manager)
        ClientAssignment.objects.create(client=cls.b, employee=cls.other, assigned_by=cls.manager)
        cls.p_a = Project.objects.create(client=cls.a, title='Alpha campaign', status='active')
        cls.p_b = Project.objects.create(client=cls.b, title='Beta campaign', status='active')
        cls.t_a = Task.objects.create(client=cls.a, project=cls.p_a, title='Public task', assigned_to=cls.worker)
        cls.t_a_private = Task.objects.create(client=cls.a, project=cls.p_a, title='Internal budget', client_visible=False)
        cls.t_b = Task.objects.create(client=cls.b, project=cls.p_b, title='Beta task', assigned_to=cls.other)

    def as_user(self, member):
        self.client.force_login(member.user)

    def send(self, action, **kwargs):
        return self.client.post('/api/operations/', json.dumps({'action': action, **kwargs}), content_type='application/json')

    def save(self, action, **kwargs):
        return self.client.post('/api/workspace/', json.dumps({'action': action, **kwargs}), content_type='application/json')

    def test_employee_isolated_from_other_clients_in_both_feeds(self):
        self.as_user(self.worker)
        raw = self.client.get('/api/workspace/')
        self.assertEqual(raw.status_code, 200)
        payload = raw.json()
        self.assertEqual({c['id'] for c in payload['clients']}, {str(self.a.id)})
        self.assertNotIn(str(self.t_b.id), {t['id'] for t in payload['tasks']})
        self.assertEqual(self.client.get('/api/operations/').status_code, 200)

    def test_client_filters_private_tasks_updates_notes_and_audit(self):
        Update.objects.create(client=self.a, author=self.worker, task=self.t_a_private,
                              title='Leaky linked update', body='Internal secret', visibility='client')
        Note.objects.create(client=self.a, author=self.worker, task=self.t_a_private,
                            body='Private linked note', visibility='client')
        ActivityLog.objects.create(actor=self.manager, client=self.a, action='Saved task', detail='Internal budget')
        self.as_user(self.client_a)
        response = self.client.get('/api/workspace/').json()
        self.assertNotIn(str(self.t_a_private.id), {t['id'] for t in response['tasks']})
        self.assertNotIn('Leaky linked update', {u['title'] for u in response['updates']})
        self.assertFalse(any(n['body'] == 'Private linked note' for n in response['notes']))
        self.assertFalse(any('Internal budget' in a['detail'] for a in response['activities']))
        staff = next(m for m in response['members'] if m['id'] == self.worker.id)
        self.assertEqual(staff['email'], '')

    def test_employee_cannot_modify_unassigned_project_or_task_by_id(self):
        self.as_user(self.worker)
        cross = self.save('task_status', id=str(self.t_b.id), status='completed')
        self.assertEqual(cross.status_code, 403)
        foreign = self.save('save_project', clientId=str(self.a.id), id=str(self.p_b.id), title='Hijacked')
        self.assertEqual(foreign.status_code, 403)
        self.p_b.refresh_from_db()
        self.assertEqual(self.p_b.title, 'Beta campaign')

    def test_client_cannot_create_internal_tasks_or_view_org_records(self):
        Record.objects.create(id='live:internal-record', space='live', kind='files', client='org',
                              data={'id':'internal-record','client':'org','title':'Internal price list'})
        self.as_user(self.client_a)
        r = self.save('save_task', clientId=str(self.a.id), title='Client injected task')
        self.assertEqual(r.status_code, 403)
        self.assertFalse(any(rec.get('title') == 'Internal price list' for rec in self.client.get('/api/workspace/').json()['records']))
        self.assertEqual(self.client.get('/api/file/internal-record/').status_code, 404)

    def test_attendance_clock_break_and_no_duplicate_day(self):
        self.as_user(self.worker)
        self.assertEqual(self.send('clock_in',mode='remote').status_code, 200)
        self.assertEqual(self.send('start_break').status_code, 200)
        self.assertEqual(self.send('end_break').status_code, 200)
        self.assertEqual(self.send('clock_out').status_code, 200)
        a = Attendance.objects.get(employee=self.worker)
        self.assertIsNotNone(a.clock_out)
        self.assertGreaterEqual(a.worked_seconds, 0)
        self.assertEqual(self.send('clock_in',mode='office').status_code, 400)
        self.as_user(self.client_a)
        self.assertEqual(self.send('clock_in').status_code, 403)

    def test_leave_submission_and_manager_review(self):
        self.as_user(self.worker)
        tomorrow = timezone.localdate() + timedelta(days=1)
        self.assertEqual(self.send('request_leave',startDate=str(tomorrow),endDate=str(tomorrow),type='annual').status_code, 200)
        leave = LeaveRequest.objects.get(employee=self.worker)
        self.as_user(self.manager)
        self.assertEqual(self.send('review_leave',id=str(leave.pk),status='approved').status_code, 200)
        leave.refresh_from_db()
        self.assertEqual(leave.status, 'approved')
        self.assertEqual(leave.reviewed_by, self.manager)

    def test_timesheets_submit_approve_and_client_scope(self):
        self.as_user(self.worker)
        resp=self.send('add_time',clientId=str(self.b.id),date=str(timezone.localdate()),minutes=40)
        self.assertEqual(resp.status_code, 403)
        resp=self.send('add_time',clientId=str(self.a.id),date=str(timezone.localdate()),minutes=90,
                       taskId=str(self.t_a.pk),billable=True,description='Design review')
        self.assertEqual(resp.status_code, 200)
        entry = TimeEntry.objects.get(employee=self.worker)
        self.assertEqual(self.send('time_status',id=str(entry.pk),status='submitted').status_code, 200)
        self.as_user(self.manager)
        self.assertEqual(self.send('time_status',id=str(entry.pk),status='approved').status_code, 200)
        entry.refresh_from_db()
        self.assertEqual(entry.status, 'approved')
        self.as_user(self.client_a)
        self.assertEqual(self.client.get('/api/export/timesheets/').status_code, 403)
        self.assertEqual(self.client.get('/api/operations/').json()['timeEntries'], [])

    def test_client_signoff_and_private_approval_isolation(self):
        public = ApprovalRequest.objects.create(client=self.a, requested_by=self.worker, title='Review homepage', audience='client')
        internal = ApprovalRequest.objects.create(client=self.a, requested_by=self.manager, title='Internal allocation',
                                                  audience='internal', reviewer=self.worker)
        self.as_user(self.client_a)
        body = self.client.get('/api/operations/').json()
        self.assertEqual({r['id'] for r in body['approvalRequests']}, {str(public.id)})
        self.assertEqual(self.send('decide_approval',id=str(internal.id),status='approved').status_code, 403)
        self.assertEqual(self.send('decide_approval',id=str(public.id),status='approved').status_code, 200)
        public.refresh_from_db()
        self.assertEqual(public.status, 'approved')
        self.as_user(self.client_b)
        self.assertEqual(self.send('decide_approval',id=str(public.id),status='rejected',note='No').status_code, 403)

    def test_ticket_thread_hides_internal_staff_reply(self):
        ticket = SupportTicket.objects.create(client=self.a, title='Site issue', description='Broken thumbnail',created_by=self.client_a)
        TicketMessage.objects.create(ticket=ticket, author=self.worker, body='Need to check the supplier', internal=True)
        TicketMessage.objects.create(ticket=ticket, author=self.worker, body='We are investigating', internal=False)
        self.as_user(self.client_a)
        tickets = self.client.get('/api/operations/').json()['supportTickets']
        self.assertEqual(len(tickets), 1)
        self.assertEqual([m['body'] for m in tickets[0]['messages']], ['We are investigating'])
        self.assertEqual(self.send('ticket_message',id=str(ticket.pk),body='Thanks',internal=True).status_code, 200)
        self.assertFalse(TicketMessage.objects.get(body='Thanks').internal)
        self.as_user(self.client_b)
        self.assertEqual(self.send('ticket_message',id=str(ticket.pk),body='Foreign reply').status_code, 403)

    def test_milestones_and_saved_views_are_scoped(self):
        milestone = ProjectMilestone.objects.create(project=self.b,title='Hidden milestone')
        self.as_user(self.worker)
        self.assertEqual(self.send('milestone_status',id=str(milestone.pk),status='completed').status_code, 403)
        self.assertEqual(self.send('save_view',name='My urgent work',filters={'priority':'urgent'}).status_code, 200)
        self.assertEqual(SavedView.objects.filter(owner=self.worker).count(),1)
        self.as_user(self.other)
        self.assertEqual(self.client.get('/api/operations/').json()['savedViews'],[])

    def test_leads_manager_only_and_conversion(self):
        self.as_user(self.worker)
        self.assertEqual(self.send('save_lead',name='Prospect').status_code, 403)
        self.as_user(self.manager)
        self.assertEqual(self.send('save_lead',name='Tara',company='New account',value='25000').status_code, 200)
        lead = Lead.objects.get(name='Tara')
        self.assertEqual(self.send('convert_lead',id=str(lead.id)).status_code, 200)
        lead.refresh_from_db()
        self.assertIsNotNone(lead.converted_client_id)
        self.assertEqual(lead.stage,'won')

    def test_client_ticket_export_contains_only_its_clients(self):
        SupportTicket.objects.create(client=self.a, title='Alpha issue',description='One')
        SupportTicket.objects.create(client=self.b, title='Beta issue',description='Two')
        self.as_user(self.client_a)
        resp = self.client.get('/api/export/tickets/')
        self.assertEqual(resp.status_code, 200)
        content=resp.content.decode('utf-8-sig')
        self.assertIn('Alpha issue',content)
        self.assertNotIn('Beta issue',content)

    def test_task_dependency_prevents_premature_completion(self):
        self.as_user(self.worker)
        independent = self.t_a
        dependent = Task.objects.create(client=self.a,project=self.p_a,title='Publish',blocked_by=independent,assigned_to=self.worker)
        self.assertEqual(self.save('task_status',id=str(dependent.pk),status='completed').status_code, 400)
        self.assertEqual(self.save('task_status',id=str(independent.pk),status='completed').status_code, 200)
        self.assertEqual(self.save('task_status',id=str(dependent.pk),status='completed').status_code, 200)


class ProjectStudioTests(TestCase):
    """Project workspace integration and cross-tenant permission regressions."""
    @classmethod
    def setUpTestData(cls):
        def create(name, role, client=None):
            user=User.objects.create_user(username=name, password='long-project-test-password-2345')
            return Member.objects.create(user=user, role=role, client_account=client)
        cls.alpha=ClientAccount.objects.create(name='Alpha', code='studio-alpha')
        cls.beta=ClientAccount.objects.create(name='Beta', code='studio-beta')
        cls.manager=create('studio_manager','manager')
        cls.employee=create('studio_employee','employee')
        cls.b_employee=create('studio_other','employee')
        cls.client_a=create('studio_client_a','client',cls.alpha)
        cls.client_b=create('studio_client_b','client',cls.beta)
        ClientAssignment.objects.create(client=cls.alpha, employee=cls.employee)
        ClientAssignment.objects.create(client=cls.beta, employee=cls.b_employee)
        cls.project_a=Project.objects.create(client=cls.alpha,title='Alpha project',status='active')
        cls.project_b=Project.objects.create(client=cls.beta,title='Beta project',status='active')
        cls.task_a=Task.objects.create(client=cls.alpha,project=cls.project_a,title='Visible task',assigned_to=cls.employee)
        cls.task_private=Task.objects.create(client=cls.alpha,project=cls.project_a,title='Internal brief',client_visible=False)
        cls.task_b=Task.objects.create(client=cls.beta,project=cls.project_b,title='Unrelated',assigned_to=cls.b_employee)

    def signed(self, member):
        self.client.force_login(member.user)

    def plus(self, action, **payload):
        return self.client.post('/api/projects-plus/',json.dumps({'action':action, **payload}),content_type='application/json')

    def test_task_list_grouping_and_cross_project_guards(self):
        self.signed(self.employee)
        result=self.plus('save_task_list',projectId=str(self.project_a.pk),title='Content planning')
        self.assertEqual(result.status_code,200)
        from .models import ProjectTaskList
        task_list=ProjectTaskList.objects.get(project=self.project_a)
        self.assertEqual(self.plus('set_task_extra',taskId=str(self.task_a.pk),taskListId=str(task_list.pk)).status_code,200)
        self.task_a.refresh_from_db()
        self.assertEqual(self.task_a.task_list,task_list)
        self.assertEqual(self.plus('save_task_list',projectId=str(self.project_b.pk),title='Intrusion').status_code,400)
        self.assertEqual(self.plus('set_task_extra',taskId=str(self.task_b.pk),taskListId=str(task_list.pk)).status_code,400)
        self.assertEqual(self.plus('delete_task_list',projectId=str(self.project_a.pk),id=str(task_list.pk)).status_code,400)

    def test_issue_visibility_and_status_separation(self):
        from .models import ProjectIssue
        ProjectIssue.objects.create(project=self.project_a,client=self.alpha,title='Internal issue',client_visible=False)
        ProjectIssue.objects.create(project=self.project_b,client=self.beta,title='Other client issue')
        self.signed(self.client_a)
        result=self.plus('save_issue',projectId=str(self.project_a.pk),title='Public bug',priority='critical',clientVisible=False)
        self.assertEqual(result.status_code,200)
        created=ProjectIssue.objects.get(title='Public bug')
        self.assertTrue(created.client_visible)
        self.assertEqual(self.plus('issue_status',id=str(created.id),status='resolved').status_code,403)
        items=self.client.get('/api/projects-plus/').json()['projectIssues']
        self.assertEqual({i['title'] for i in items},{'Public bug'})
        self.signed(self.client_b)
        self.assertEqual(self.plus('save_issue',projectId=str(self.project_a.pk),title='Hijack').status_code,400)
        self.assertNotIn('Public bug',{i['title'] for i in self.client.get('/api/projects-plus/').json()['projectIssues']})

    def test_discussion_feed_privacy_and_parent_link(self):
        from .models import ProjectDiscussion
        internal=ProjectDiscussion.objects.create(project=self.project_a,author=self.employee,body='Internal budget',visibility='team')
        self.signed(self.client_a)
        self.assertEqual(self.plus('post_project_feed',projectId=str(self.project_a.id),body='Client question',visibility='team').status_code,200)
        feed=self.client.get('/api/projects-plus/').json()['projectFeed']
        self.assertEqual(len(feed),1)
        self.assertEqual(feed[0]['visibility'],'client')
        self.assertEqual(self.plus('post_project_feed',projectId=str(self.project_a.id),body='Leaky reply',parentId=str(internal.id)).status_code,403)
        self.signed(self.employee)
        self.assertEqual(self.plus('post_project_feed',projectId=str(self.project_b.id),body='Foreign project').status_code,400)

    def test_bulk_status_is_atomic_and_dependency_safe(self):
        self.signed(self.employee)
        result=self.plus('bulk_task_status',taskIds=[str(self.task_a.id),str(self.task_b.id)],status='completed')
        self.assertEqual(result.status_code,403)
        self.task_a.refresh_from_db();self.assertEqual(self.task_a.status,'todo')
        result=self.plus('bulk_task_status',taskIds=[str(self.task_a.id)],status='completed')
        self.assertEqual(result.status_code,200)
        self.task_a.refresh_from_db();self.project_a.refresh_from_db()
        self.assertEqual(self.task_a.percent_complete,100)
        self.assertEqual(self.task_a.status,'completed')
        self.assertEqual(self.project_a.progress,50)

    def test_dashboard_preferences_scoped_to_member_and_project(self):
        self.signed(self.client_a)
        self.assertEqual(self.plus('save_dashboard_layout',scope='project:'+str(self.project_b.id),widgets=['stats']).status_code,400)
        self.assertEqual(self.plus('save_dashboard_layout',scope='global',widgets=['stats','today','issues']).status_code,200)
        self.assertEqual(self.client.get('/api/projects-plus/').json()['dashboardLayouts'][0]['widgets'],['stats','today','issues'])
        self.signed(self.client_b)
        self.assertEqual(self.client.get('/api/projects-plus/').json()['dashboardLayouts'],[])

    def test_project_documents_are_download_protected(self):
        from tempfile import TemporaryDirectory
        from django.test import override_settings
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import ProjectDocument
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            self.signed(self.employee)
            response=self.client.post('/api/projects-plus/upload/',{
                'projectId':str(self.project_a.id),'title':'Internal plan','clientVisible':'false',
                'file':SimpleUploadedFile('plan.txt',b'internal text',content_type='text/plain'),
            })
            self.assertEqual(response.status_code,200)
            doc=ProjectDocument.objects.get(project=self.project_a)
            self.assertEqual(self.client.get('/api/projects-plus/document/'+str(doc.id)+'/').status_code,200)
            self.signed(self.client_a)
            self.assertEqual(self.client.get('/api/projects-plus/document/'+str(doc.id)+'/').status_code,404)
            self.signed(self.client_b)
            self.assertEqual(self.client.get('/api/projects-plus/document/'+str(doc.id)+'/').status_code,404)

    def test_project_team_members_must_belong_to_client(self):
        self.signed(self.manager)
        self.assertEqual(self.plus('save_project_member',projectId=str(self.project_a.id),memberId=self.b_employee.id).status_code,403)
        self.assertEqual(self.plus('save_project_member',projectId=str(self.project_a.id),memberId=self.employee.id).status_code,200)
        self.signed(self.client_a)
        self.assertEqual(self.plus('remove_project_member',projectId=str(self.project_a.id),memberId=self.employee.id).status_code,403)
