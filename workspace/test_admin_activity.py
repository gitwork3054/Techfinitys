"""Access, notifications, review and filtering tests for Super Admin activity."""
import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import (
    Member, ClientAccount, ClientAssignment, Project, Task, ActivityLog,
    Attendance, LeaveRequest, TimeEntry, ApprovalRequest, Notification,
)
from .views import _log


@override_settings(SECURE_SSL_REDIRECT=False)
class AdminActivityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client_a = ClientAccount.objects.create(code='activity-alpha', name='Agency Alpha')
        cls.client_b = ClientAccount.objects.create(code='activity-beta', name='Agency Beta')
        def member(username, role, client=None):
            user=User.objects.create_user(username=username, password='a-long-safe-password-456')
            return Member.objects.create(user=user, role=role, client_account=client)
        cls.admin=member('activity-admin','admin')
        cls.admin2=member('activity-admin2','admin')
        cls.manager=member('activity-manager','manager')
        cls.worker=member('activity-worker','employee')
        cls.other=member('activity-other','employee')
        cls.portal=member('activity-client','client',cls.client_a)
        ClientAssignment.objects.create(client=cls.client_a, employee=cls.worker)
        ClientAssignment.objects.create(client=cls.client_b, employee=cls.other)
        cls.project=Project.objects.create(client=cls.client_a, title='Alpha project', status='active')
        cls.task=Task.objects.create(client=cls.client_a, project=cls.project, title='Social creative', assigned_to=cls.worker)

    def as_user(self,member):
        self.client.force_login(member.user)

    def act(self,url,action,**payload):
        return self.client.post(url,json.dumps({'action':action,**payload}),content_type='application/json')

    def test_only_super_admin_can_see_feed_and_mark_read(self):
        path='/api/admin-activity/'
        self.assertEqual(self.client.get(path).status_code,401)
        for actor in [self.worker,self.manager,self.portal]:
            self.as_user(actor)
            self.assertEqual(self.client.get(path).status_code,403)
            self.assertEqual(self.client.get(path+'?summary=1').status_code,403)
            self.assertEqual(self.act(path,'mark_seen').status_code,403)
        self.as_user(self.admin)
        self.assertEqual(self.client.get(path).status_code,200)
        self.assertEqual(self.client.get(path+'?summary=1').status_code,200)

    def test_notifications_are_private_to_each_super_admin(self):
        _log(self.worker,'Changed task status',self.task,self.client_a,'Social creative: To do -> In progress')
        self.assertEqual(Notification.objects.filter(recipient=self.admin,link='#admin_activity',read_at__isnull=True).count(),1)
        self.assertEqual(Notification.objects.filter(recipient=self.admin2,link='#admin_activity',read_at__isnull=True).count(),1)
        self.as_user(self.admin)
        d=self.client.get('/api/admin-activity/').json()
        self.assertEqual(d['summary']['unread'],1)
        self.assertEqual(d['events'][0]['category'],'tasks')
        self.assertEqual(d['events'][0]['employee'],'activity-worker')
        self.assertEqual(self.act('/api/admin-activity/','mark_seen').status_code,200)
        self.assertEqual(Notification.objects.filter(recipient=self.admin,link='#admin_activity',read_at__isnull=True).count(),0)
        self.assertEqual(Notification.objects.filter(recipient=self.admin2,link='#admin_activity',read_at__isnull=True).count(),1)
        self.assertEqual(ActivityLog.objects.count(),1)  # reading does not erase audit

    def test_staff_attendance_actions_are_recorded(self):
        self.as_user(self.worker)
        for action in ('clock_in','start_break','end_break','clock_out'):
            payload={'mode':'office'} if action=='clock_in' else {}
            result=self.act('/api/operations/', action, **payload)
            self.assertEqual(result.status_code,200,result.content)
        self.as_user(self.admin)
        d=self.client.get('/api/admin-activity/?category=attendance').json()
        self.assertEqual({e['action'] for e in d['events']}, {'Clocked in','Started break','Resumed work','Clocked out'})
        self.assertEqual(d['summary']['onShift'],0)
        self.assertEqual(len(d['events']),4)

    def test_leave_approval_updates_status_and_restricts_self_review(self):
        self.as_user(self.worker)
        today=timezone.localdate()+timedelta(days=7)
        result=self.act('/api/operations/','request_leave',type='annual',startDate=today.isoformat(),endDate=(today+timedelta(days=1)).isoformat(),reason='Family event')
        self.assertEqual(result.status_code,200,result.content)
        leave_id=result.json()['id']
        self.as_user(self.admin)
        d=self.client.get('/api/admin-activity/').json()
        self.assertEqual(d['summary']['pendingLeaves'],1)
        self.assertEqual(d['leaves'][0]['id'],leave_id)
        decision=self.act('/api/operations/','review_leave',id=leave_id,status='approved')
        self.assertEqual(decision.status_code,200,decision.content)
        self.assertEqual(LeaveRequest.objects.get(pk=leave_id).status,'approved')
        self.assertEqual(self.act('/api/operations/','review_leave',id=leave_id,status='rejected').status_code,400)
        self.assertEqual(self.client.get('/api/admin-activity/').json()['summary']['pendingLeaves'],0)
        self.assertTrue(Notification.objects.filter(recipient=self.worker,title__icontains='Leave approved').exists())
        self.as_user(self.worker)
        self.assertEqual(self.act('/api/operations/','review_leave',id=leave_id,status='rejected').status_code,403)

    def test_timesheet_review_and_task_changes_show_in_feed(self):
        self.as_user(self.worker)
        entry=self.act('/api/operations/','add_time',clientId=str(self.client_a.pk), projectId=str(self.project.pk),taskId=str(self.task.pk),date=timezone.localdate().isoformat(),minutes=90,description='Design delivery')
        self.assertEqual(entry.status_code,200,entry.content)
        entry_id=entry.json()['id']
        self.assertEqual(self.act('/api/operations/','time_status',id=entry_id,status='submitted').status_code,200)
        task=self.act('/api/workspace/','task_status',id=str(self.task.pk),status='in_progress')
        self.assertEqual(task.status_code,200,task.content)
        self.as_user(self.admin)
        data=self.client.get('/api/admin-activity/').json()
        self.assertEqual(data['summary']['pendingTimesheets'],1)
        self.assertEqual(data['timesheets'][0]['id'],entry_id)
        self.assertTrue(any('Social creative:' in e['detail'] for e in data['events']))
        self.assertEqual(self.act('/api/operations/','time_status',id=entry_id,status='approved').status_code,200)
        self.assertEqual(self.client.get('/api/admin-activity/').json()['summary']['pendingTimesheets'],0)

    def test_internal_approval_queue_and_actions(self):
        self.as_user(self.worker)
        res=self.act('/api/operations/','create_approval',clientId=str(self.client_a.pk),title='Approve draft artwork',audience='internal',reviewerId=self.manager.pk,description='Artwork review')
        self.assertEqual(res.status_code,200,res.content)
        approval_id=res.json()['id']
        self.as_user(self.admin)
        data=self.client.get('/api/admin-activity/').json()
        self.assertEqual(data['summary']['pendingApprovals'],1)
        self.assertEqual(data['approvals'][0]['id'],approval_id)
        res=self.act('/api/operations/','decide_approval',id=approval_id,status='rejected',note='Needs title update')
        self.assertEqual(res.status_code,200,res.content)
        self.assertEqual(ApprovalRequest.objects.get(pk=approval_id).status,'rejected')

    def test_filters_search_pagination_and_client_isolation(self):
        for i in range(54):
            _log(self.worker,'Updated task details',self.task,self.client_a,f'Alpha iteration {i}')
        _log(self.other,'Clocked in',detail='remote')
        self.as_user(self.admin)
        base=self.client.get('/api/admin-activity/').json()
        self.assertEqual(len(base['events']),50)
        self.assertIsNotNone(base['nextBefore'])
        page2=self.client.get('/api/admin-activity/',{'before':base['nextBefore']}).json()
        self.assertEqual(len(page2['events']),5)
        filtered=self.client.get('/api/admin-activity/',{'employeeId':self.worker.id,'category':'tasks','q':'iteration 42'}).json()
        self.assertEqual(len(filtered['events']),1)
        self.assertEqual(filtered['events'][0]['detail'],'Alpha iteration 42')
        self.assertEqual(self.client.get('/api/admin-activity/?before=bad').status_code,400)
        self.assertEqual(self.client.get('/api/admin-activity/?category=bad').status_code,400)
        self.as_user(self.portal)
        self.assertEqual(self.client.get('/api/admin-activity/?q=Alpha').status_code,403)

    def test_employee_chat_metadata_is_visible_but_message_body_is_not(self):
        self.as_user(self.worker)
        started=self.act('/api/collaboration/','start_chat',kind='direct',memberIds=[self.manager.pk])
        self.assertEqual(started.status_code,200,started.content)
        thread=started.json()['conversation']['id']
        confidential='private-chat-secret-do-not-expose'
        message=self.act('/api/collaboration/','send_chat',conversationId=thread,body=confidential)
        self.assertEqual(message.status_code,200,message.content)
        self.as_user(self.admin)
        data=self.client.get('/api/admin-activity/?category=chat').json()
        self.assertTrue(any(e['action']=='Sent internal chat message' for e in data['events']))
        self.assertNotIn(confidential,json.dumps(data))

    def test_admin_activity_does_not_include_admin_actions(self):
        _log(self.admin,'Changed own password')
        _log(self.worker,'Logged time',detail='120 minutes')
        self.as_user(self.admin)
        events=self.client.get('/api/admin-activity/').json()['events']
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['category'],'time')
