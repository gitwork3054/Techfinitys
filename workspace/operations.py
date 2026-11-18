"""Typed, permission-scoped operations API shared by staff and client portal.

All endpoints use Django sessions and CSRF. A client's permitted workspaces are
resolved on the server; submitted IDs never grant access by themselves.
"""
import csv
import json
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_http_methods
from .models import (
    Attendance, LeaveRequest, TimeEntry, ApprovalRequest, SupportTicket,
    TicketMessage, ProjectMilestone, SavedView, Lead, Member, ClientAccount,
    Project, Task, Notification, ClientAssignment
)
from .views import _context, _client_ids_for, _can_access_client, _log, _notify_client_team


MANAGERS = ('admin', 'manager')
STAFF = ('admin', 'manager', 'employee')


def _person(m):
    return m.user.get_full_name() or m.user.username if m else 'System'


def _date(value, label='Date'):
    d = parse_date(str(value or ''))
    if d is None:
        raise ValueError(f'{label} must be a valid YYYY-MM-DD date')
    return d


def _datetime(value):
    if not value:
        return None
    d = parse_datetime(str(value))
    if not d:
        raise ValueError('Invalid date and time')
    if timezone.is_naive(d):
        d = timezone.make_aware(d, timezone.get_current_timezone())
    return d


def _choice(value, choices, label):
    if value not in choices:
        raise ValueError(f'Invalid {label}')
    return value


def _str(value, label, limit=220, required=True):
    result = str(value or '').strip()
    if required and not result:
        raise ValueError(f'{label} is required')
    if len(result) > limit:
        raise ValueError(f'{label} must be at most {limit} characters')
    return result


def _client(member, client_id):
    try:
        obj = ClientAccount.objects.get(pk=client_id)
    except (ClientAccount.DoesNotExist, ValueError, TypeError):
        raise ValueError('Client not found')
    if not _can_access_client(member, obj):
        raise PermissionError('Client access denied')
    return obj


def _project(client, project_id):
    if not project_id:
        return None
    p = Project.objects.filter(pk=project_id, client=client).first()
    if p is None:
        raise ValueError('Project is not part of this client')
    return p


def _task(client, task_id):
    if not task_id:
        return None
    t = Task.objects.filter(pk=task_id, client=client).first()
    if t is None:
        raise ValueError('Task is not part of this client')
    return t


def _eligible_assignee(client, member_id):
    if not member_id:
        return None
    m = Member.objects.filter(pk=member_id, is_active=True, role__in=STAFF).first()
    if not m:
        raise ValueError('User not found')
    if m.role == 'employee' and not ClientAssignment.objects.filter(client=client, employee=m, active=True).exists():
        raise ValueError('The employee must be assigned to this client')
    return m


def _notify(recipient, title, body='', client=None):
    if recipient and recipient.is_active:
        Notification.objects.create(recipient=recipient, client=client, title=title[:220], body=body[:2000])


def _notify_managers(title, body='', client=None):
    for manager in Member.objects.filter(role__in=MANAGERS, is_active=True):
        _notify(manager, title, body, client)


def _iso(value):
    return value.isoformat() if value else ''


def _staff_only(member):
    if member.role not in STAFF:
        raise PermissionError('This is an employee-only operation')


def _attendance_json(a):
    return {'id':a.id,'employeeId':a.employee_id,'employeeName':_person(a.employee),
            'date':_iso(a.date),'clockIn':_iso(a.clock_in),'clockOut':_iso(a.clock_out),
            'breakStartedAt':_iso(a.break_started_at),'breakSeconds':a.break_seconds,
            'workedMinutes':round(a.worked_seconds / 60), 'mode':a.mode,'note':a.note,
            'status':'on_break' if a.break_started_at else ('clocked_out' if a.clock_out else 'working')}


def _leave_json(r):
    return {'id':str(r.pk),'employeeId':r.employee_id,'employeeName':_person(r.employee),
            'type':r.leave_type,'startDate':_iso(r.start_date),'endDate':_iso(r.end_date),
            'days':(r.end_date-r.start_date).days+1,'reason':r.reason,'status':r.status,
            'reviewer':_person(r.reviewed_by) if r.reviewed_by else '', 'reviewNote':r.review_note,
            'createdAt':_iso(r.created_at)}


def _time_json(t):
    return {'id':str(t.pk),'employeeId':t.employee_id,'employeeName':_person(t.employee),
            'clientId':str(t.client_id),'clientName':t.client.name,'projectId':str(t.project_id) if t.project_id else '',
            'projectName':t.project.title if t.project else '', 'taskId':str(t.task_id) if t.task_id else '',
            'taskName':t.task.title if t.task else '', 'date':_iso(t.date),'minutes':t.minutes,
            'hours':round(t.minutes / 60, 2),'description':t.description,'billable':t.billable,
            'status':t.status,'createdAt':_iso(t.created_at)}


def _approval_json(a):
    return {'id':str(a.pk),'clientId':str(a.client_id),'clientName':a.client.name,
            'projectId':str(a.project_id) if a.project_id else '', 'taskId':str(a.task_id) if a.task_id else '',
            'title':a.title,'description':a.description,'audience':a.audience,'status':a.status,
            'requestedBy':_person(a.requested_by) if a.requested_by else 'System',
            'reviewerId':a.reviewer_id, 'reviewerName':_person(a.reviewer) if a.reviewer else '',
            'decisionNote':a.decision_note,'decidedBy':_person(a.decided_by) if a.decided_by else '',
            'dueAt':_iso(a.due_at),'createdAt':_iso(a.created_at)}


def _ticket_json(t, member):
    msgs = t.messages.all()
    if member.role == 'client':
        msgs = [m for m in msgs if not m.internal]
    return {'id':str(t.pk),'clientId':str(t.client_id),'clientName':t.client.name,
            'title':t.title,'description':t.description,'priority':t.priority,'status':t.status,
            'createdBy':_person(t.created_by) if t.created_by else 'System',
            'assignedName':_person(t.assigned_to) if t.assigned_to else '',
            'assignedTo':t.assigned_to_id,'createdAt':_iso(t.created_at),'updatedAt':_iso(t.updated_at),
            'messages':[{'id':m.id,'author':_person(m.author) if m.author else 'System',
                         'body':m.body,'internal':m.internal,'createdAt':_iso(m.created_at)} for m in msgs]}


def _milestone_json(m):
    return {'id':str(m.pk),'projectId':str(m.project_id),'projectName':m.project.title,
            'clientId':str(m.project.client_id),'title':m.title,'description':m.description,
            'dueDate':_iso(m.due_date),'status':m.status,'ownerName':_person(m.owner) if m.owner else '',
            'clientVisible':m.client_visible}


def _lead_json(l):
    return {'id':str(l.pk),'name':l.name,'company':l.company,'email':l.email,'phone':l.phone,
            'source':l.source,'stage':l.stage,'value':str(l.estimated_value),'notes':l.notes,
            'ownerId':l.owner_id,'ownerName':_person(l.owner) if l.owner else '',
            'convertedClientId':str(l.converted_client_id) if l.converted_client_id else '',
            'updatedAt':_iso(l.updated_at)}


@require_http_methods(['GET','POST'])
def operations_api(request):
    try:
        member = _context(request)
    except PermissionError as exc:
        return JsonResponse({'error': str(exc)}, status=401)

    if request.method == 'GET':
        client_ids = _client_ids_for(member)
        staff = member.role in STAFF
        supervisor = member.role in MANAGERS
        approvals = ApprovalRequest.objects.filter(client_id__in=client_ids)
        tickets = SupportTicket.objects.filter(client_id__in=client_ids)
        milestones = ProjectMilestone.objects.filter(project__client_id__in=client_ids)
        if member.role == 'client':
            approvals = approvals.filter(audience='client')
            milestones = milestones.filter(client_visible=True)
        elif member.role == 'employee':
            approvals = approvals.filter(Q(audience='client')|Q(requested_by=member)|Q(reviewer=member))
        # The API enforces a bounded feed; filters and CSV exports support larger datasets.
        approvals = approvals.select_related('client','requested_by__user','reviewer__user','decided_by__user')[:400]
        tickets = tickets.select_related('client','created_by__user','assigned_to__user').prefetch_related('messages__author__user')[:300]
        milestones = milestones.select_related('project__client','owner__user')[:400]
        attendance = Attendance.objects.none()
        leaves = LeaveRequest.objects.none()
        time_entries = TimeEntry.objects.none()
        if staff:
            attendance = Attendance.objects.filter(date__gte=timezone.localdate()-timedelta(days=45))
            leaves = LeaveRequest.objects.all()
            time_entries = TimeEntry.objects.all()
            if not supervisor:
                attendance = attendance.filter(employee=member)
                leaves = leaves.filter(employee=member)
                time_entries = time_entries.filter(employee=member)
            attendance = attendance.select_related('employee__user')[:600]
            leaves = leaves.select_related('employee__user','reviewed_by__user')[:400]
            time_entries = time_entries.select_related('employee__user','client','project','task')[:500]
        if supervisor:
            leads = Lead.objects.select_related('owner__user')[:300]
        else:
            leads = Lead.objects.none()
        views = SavedView.objects.filter(owner=member)[:30]
        return JsonResponse({
            'attendance': [_attendance_json(a) for a in attendance],
            'leaves': [_leave_json(r) for r in leaves],
            'timeEntries': [_time_json(t) for t in time_entries],
            'approvalRequests': [_approval_json(a) for a in approvals],
            'supportTickets': [_ticket_json(t, member) for t in tickets],
            'milestones': [_milestone_json(m) for m in milestones],
            'salesLeads': [_lead_json(l) for l in leads],
            'savedViews': [{'id':v.pk,'name':v.name,'module':v.module,'filters':v.filters} for v in views],
            'serverToday':timezone.localdate().isoformat(),
        })

    try:
        data = json.loads(request.body or b'{}')
        if not isinstance(data, dict):
            raise ValueError('Expected a JSON object')
        action = data.get('action')
        with transaction.atomic():
            now = timezone.now()
            if action in ('clock_in','start_break','end_break','clock_out'):
                _staff_only(member)
                if action == 'clock_in':
                    if Attendance.objects.filter(employee=member, clock_out__isnull=True).exists():
                        raise ValueError('Clock out of the previous attendance session first')
                    mode = _choice(data.get('mode','office'), {'office','remote','field'}, 'work mode')
                    Attendance.objects.create(employee=member,date=timezone.localdate(),clock_in=now,
                                              mode=mode,note=_str(data.get('note'),'Note',400,False))
                    _log(member,'Clocked in', detail=mode)
                else:
                    a = Attendance.objects.select_for_update().filter(employee=member, clock_out__isnull=True).first()
                    if not a:
                        raise ValueError('You are not clocked in')
                    if action == 'start_break':
                        if a.break_started_at:
                            raise ValueError('A break is already running')
                        a.break_started_at = now
                        a.save(update_fields=['break_started_at'])
                    elif action == 'end_break':
                        if not a.break_started_at:
                            raise ValueError('No break is running')
                        a.break_seconds += max(0,int((now-a.break_started_at).total_seconds()))
                        a.break_started_at = None
                        a.save(update_fields=['break_seconds','break_started_at'])
                    else:
                        if a.break_started_at:
                            a.break_seconds += max(0,int((now-a.break_started_at).total_seconds()))
                            a.break_started_at = None
                        a.clock_out = now
                        a.save(update_fields=['clock_out','break_seconds','break_started_at'])
                        _log(member,'Clocked out',detail=f'{a.worked_seconds//60} minutes')
                return JsonResponse({'ok':True})

            if action == 'request_leave':
                _staff_only(member)
                start, end = _date(data.get('startDate'),'Start date'), _date(data.get('endDate'),'End date')
                if end < start or (end-start).days > 90:
                    raise ValueError('Leave must be 1–91 days with the end on or after the start')
                if LeaveRequest.objects.filter(employee=member, status__in=['pending','approved'],start_date__lte=end,end_date__gte=start).exists():
                    raise ValueError('You already have an overlapping leave request')
                r = LeaveRequest.objects.create(employee=member,leave_type=_choice(data.get('type','annual'),
                    {'annual','sick','casual','unpaid','other'},'leave type'),start_date=start,end_date=end,
                    reason=_str(data.get('reason'),'Reason',2000,False))
                _notify_managers(f'Leave approval: {_person(member)}',f'{start} to {end}')
                _log(member,'Requested leave',r,detail=f'{start} – {end}')
                return JsonResponse({'ok':True,'id':str(r.id)})

            if action == 'review_leave':
                if member.role not in MANAGERS:
                    raise PermissionError('Only managers can review leave')
                r = LeaveRequest.objects.select_for_update().get(pk=data.get('id'))
                if r.employee_id == member.id:
                    raise PermissionError('You cannot approve your own leave')
                if r.status != 'pending':
                    raise ValueError('Only pending requests can be reviewed')
                r.status = _choice(data.get('status'), {'approved','rejected'}, 'decision')
                r.review_note = _str(data.get('note'),'Review note',2000,False)
                r.reviewed_at=now; r.reviewed_by=member
                r.save()
                _notify(r.employee, f'Leave {r.status}', r.review_note)
                _log(member,'Reviewed leave',r,detail=r.status)
                return JsonResponse({'ok':True})

            if action == 'cancel_leave':
                _staff_only(member)
                r = LeaveRequest.objects.get(pk=data.get('id'),employee=member)
                if r.status != 'pending':
                    raise ValueError('Only pending leave can be cancelled')
                r.status='cancelled'; r.save(update_fields=['status'])
                _log(member,'Cancelled leave',r)
                return JsonResponse({'ok':True})

            if action == 'add_time':
                _staff_only(member)
                client = _client(member, data.get('clientId'))
                project, task = _project(client, data.get('projectId')), _task(client, data.get('taskId'))
                if project and task and task.project_id and task.project_id != project.id:
                    raise ValueError('Task belongs to a different project')
                day = _date(data.get('date'))
                if day > timezone.localdate() + timedelta(days=1):
                    raise ValueError('You cannot log time in the future')
                try:
                    minutes = int(data.get('minutes'))
                except (ValueError, TypeError):
                    raise ValueError('Duration must be minutes')
                if not 1 <= minutes <= 1440:
                    raise ValueError('Time entry must be between 1 minute and 24 hours')
                used = sum(TimeEntry.objects.filter(employee=member,date=day).values_list('minutes',flat=True))
                if used + minutes > 1440:
                    raise ValueError('Time logged for one day cannot exceed 24 hours')
                entry = TimeEntry.objects.create(employee=member,client=client,project=project,task=task,
                    date=day,minutes=minutes,description=_str(data.get('description'),'Description',500,False),
                    billable=bool(data.get('billable',True)))
                _log(member,'Logged time',entry,client,f'{minutes} minutes')
                return JsonResponse({'ok':True,'id':str(entry.id)})

            if action == 'time_status':
                _staff_only(member)
                entry = TimeEntry.objects.select_for_update().get(pk=data.get('id'))
                decision = data.get('status')
                if member.role in MANAGERS and entry.employee_id != member.id and decision in ('approved','rejected'):
                    if entry.status != 'submitted':
                        raise ValueError('Only submitted time can be reviewed')
                    entry.status = decision; entry.reviewed_by=member; entry.reviewed_at=now
                    _notify(entry.employee, f'Time entry {decision}', entry.description, entry.client)
                elif entry.employee_id == member.id and decision == 'submitted' and entry.status in ('draft','rejected'):
                    entry.status = 'submitted'; entry.reviewed_by=None; entry.reviewed_at=None
                    _notify_managers(f'Timesheet submitted by {_person(member)}',entry.description,entry.client)
                else:
                    raise PermissionError('Time entry transition is not allowed')
                entry.save()
                _log(member,'Changed timesheet status',entry,entry.client,entry.status)
                return JsonResponse({'ok':True})

            if action == 'create_approval':
                _staff_only(member)
                client = _client(member, data.get('clientId'))
                audience = _choice(data.get('audience','client'), {'client','internal'}, 'approval audience')
                reviewer = _eligible_assignee(client,data.get('reviewerId')) if audience == 'internal' else None
                if audience == 'internal' and not reviewer:
                    raise ValueError('Select an internal reviewer')
                task = _task(client,data.get('taskId'))
                if task and audience == 'client' and not task.client_visible:
                    raise ValueError('An internal-only task cannot be linked to a client approval')
                a = ApprovalRequest.objects.create(client=client, project=_project(client,data.get('projectId')),
                    task=task, title=_str(data.get('title'),'Title'), description=_str(data.get('description'),'Description',4000,False),
                    audience=audience, requested_by=member, reviewer=reviewer, due_at=_datetime(data.get('dueAt')))
                if audience == 'client':
                    for portal in Member.objects.filter(role='client',client_account=client,is_active=True):
                        _notify(portal,f'Approval needed: {a.title}',a.description[:150],client)
                else:
                    _notify(reviewer,f'Internal approval: {a.title}',a.description[:150],client)
                _log(member,'Requested approval',a,client,a.title)
                return JsonResponse({'ok':True,'id':str(a.pk)})

            if action == 'decide_approval':
                a = ApprovalRequest.objects.select_for_update().select_related('client').get(pk=data.get('id'))
                _client(member,a.client_id)
                if a.status != 'pending':
                    raise ValueError('This approval has already been decided')
                if a.audience == 'client':
                    if member.role != 'client' or member.client_account_id != a.client_id:
                        raise PermissionError('Only the client can decide a client approval')
                elif member.role not in MANAGERS and member.id != a.reviewer_id:
                    raise PermissionError('Not the assigned reviewer')
                if a.requested_by_id == member.id:
                    raise PermissionError('You cannot approve your own request')
                a.status = _choice(data.get('status'), {'approved','rejected','changes'}, 'decision')
                a.decision_note = _str(data.get('note'),'Decision note',4000, a.status != 'approved')
                a.decided_by=member; a.decided_at=now; a.save()
                _notify(a.requested_by,f'Approval {a.get_status_display().lower()}: {a.title}',a.decision_note,a.client)
                _log(member,'Decided approval',a,a.client,f'{a.title} · {a.status}')
                return JsonResponse({'ok':True})

            if action == 'create_ticket':
                client = _client(member,data.get('clientId'))
                assignment = _eligible_assignee(client,data.get('assignedTo')) if member.role in MANAGERS else None
                ticket = SupportTicket.objects.create(client=client, title=_str(data.get('title'),'Subject'),
                    description=_str(data.get('description'),'Description',5000),
                    priority=_choice(data.get('priority','normal'),{'low','normal','high','urgent'},'priority'),
                    project=_project(client,data.get('projectId')),assigned_to=assignment,created_by=member)
                _notify_client_team(client,f'New support ticket: {ticket.title}',ticket.description[:150],exclude=member)
                if member.role == 'client':
                    _notify_managers(f'Client support: {ticket.title}',ticket.description[:120],client)
                _log(member,'Opened support ticket',ticket,client,ticket.title)
                return JsonResponse({'ok':True,'id':str(ticket.id)})

            if action in ('ticket_message','ticket_status'):
                ticket = SupportTicket.objects.select_for_update().select_related('client').get(pk=data.get('id'))
                _client(member,ticket.client_id)
                if action == 'ticket_message':
                    body = _str(data.get('body'),'Reply',4000)
                    internal = member.role in STAFF and bool(data.get('internal'))
                    TicketMessage.objects.create(ticket=ticket,author=member,body=body,internal=internal)
                    # A new customer message reopens a resolved ticket for follow-up.
                    if member.role == 'client' and ticket.status == 'resolved':
                        ticket.status='open'
                    ticket.save(update_fields=['status','updated_at'])
                    if member.role == 'client':
                        _notify_managers(f'Client replied: {ticket.title}',body[:150],ticket.client)
                    elif not internal:
                        for portal in Member.objects.filter(client_account=ticket.client,role='client',is_active=True):
                            _notify(portal,f'Support reply: {ticket.title}',body[:150],ticket.client)
                    _log(member,'Replied to ticket',ticket,ticket.client)
                else:
                    _staff_only(member)
                    ticket.status=_choice(data.get('status'),{'open','in_progress','waiting_client','resolved','closed'},'ticket status')
                    ticket.resolved_at=now if ticket.status=='resolved' else None
                    ticket.save(update_fields=['status','resolved_at','updated_at'])
                    if ticket.status in ('waiting_client','resolved'):
                        for portal in Member.objects.filter(client_account=ticket.client,role='client',is_active=True):
                            _notify(portal,f'Ticket {ticket.get_status_display().lower()}: {ticket.title}',client=ticket.client)
                    _log(member,'Updated ticket',ticket,ticket.client,ticket.status)
                return JsonResponse({'ok':True})

            if action == 'save_milestone':
                _staff_only(member)
                project = Project.objects.select_related('client').get(pk=data.get('projectId'))
                _client(member,project.client_id)
                m = ProjectMilestone.objects.create(project=project,title=_str(data.get('title'),'Milestone title'),
                    description=_str(data.get('description'),'Description',2000,False),
                    due_date=_date(data.get('dueDate')) if data.get('dueDate') else None,
                    owner=_eligible_assignee(project.client,data.get('ownerId')),client_visible=bool(data.get('clientVisible',True)))
                _log(member,'Created milestone',m,project.client,m.title)
                return JsonResponse({'ok':True})

            if action == 'milestone_status':
                _staff_only(member)
                m = ProjectMilestone.objects.select_related('project__client').get(pk=data.get('id'))
                _client(member,m.project.client_id)
                m.status=_choice(data.get('status'),{'planned','active','completed'},'status')
                m.save(update_fields=['status'])
                _log(member,'Updated milestone',m,m.project.client,m.status)
                return JsonResponse({'ok':True})

            if action == 'save_view':
                name = _str(data.get('name'),'View name',80)
                if (SavedView.objects.filter(owner=member).count() >= 20
                        and not SavedView.objects.filter(owner=member,module='tasks',name=name).exists()):
                    raise ValueError('Maximum 20 saved views per user')
                filters = data.get('filters',{})
                if not isinstance(filters,dict) or set(filters) - {'search','client','owner','status','priority','timespan','view'}:
                    raise ValueError('Unsupported view filters')
                if any(not isinstance(v,str) or len(v)>150 for v in filters.values()):
                    raise ValueError('Filter values must be short strings')
                SavedView.objects.update_or_create(owner=member,module='tasks',name=name,defaults={'filters':filters})
                return JsonResponse({'ok':True})

            if action == 'delete_view':
                count,_ = SavedView.objects.filter(pk=data.get('id'),owner=member).delete()
                if not count: raise ValueError('View not found')
                return JsonResponse({'ok':True})

            if action in ('save_lead','lead_stage','convert_lead'):
                if member.role not in MANAGERS:
                    raise PermissionError('Sales pipeline is manager-only')
                if action == 'save_lead':
                    owner = Member.objects.filter(pk=data.get('ownerId'),role__in=STAFF).first() if data.get('ownerId') else member
                    try:
                        value = Decimal(str(data.get('value') or 0))
                    except InvalidOperation:
                        raise ValueError('Invalid estimated value')
                    if value < 0 or value > 9999999999:
                        raise ValueError('Estimated value must be positive and within range')
                    l = Lead.objects.create(name=_str(data.get('name'),'Contact name',160),company=_str(data.get('company'),'Company',180,False),
                        email=_str(data.get('email'),'Email',254,False),phone=_str(data.get('phone'),'Phone',40,False),
                        source=_str(data.get('source'),'Source',100,False),notes=_str(data.get('notes'),'Notes',4000,False),
                        estimated_value=value,owner=owner)
                    _log(member,'Created sales lead',l,detail=l.name)
                else:
                    l = Lead.objects.select_for_update().get(pk=data.get('id'))
                    if action == 'lead_stage':
                        l.stage = _choice(data.get('stage'),{key for key,_ in Lead.STAGES},'pipeline stage')
                        l.save(update_fields=['stage','updated_at'])
                        _log(member,'Advanced lead',l,detail=f'{l.name} → {l.stage}')
                    else:
                        if l.converted_client_id:
                            raise ValueError('Lead has already been converted')
                        if l.stage == 'lost':
                            raise ValueError('Lost leads cannot be converted')
                        base = ''.join(c if c.isalnum() or c=='-' else '-' for c in (l.company or l.name).lower())[:28].strip('-') or 'client'
                        code = f'{base}-{uuid.uuid4().hex[:5]}'
                        client = ClientAccount.objects.create(code=code,name=l.company or l.name,
                            company=l.company,email=l.email,phone=l.phone,status='onboarding',created_by=member.user)
                        l.converted_client = client; l.stage='won'; l.save(update_fields=['converted_client','stage','updated_at'])
                        _log(member,'Converted lead to client',l,client,l.name)
                return JsonResponse({'ok':True})

            if action == 'change_password':
                old = str(data.get('oldPassword') or '')
                new = str(data.get('newPassword') or '')
                if not request.user.check_password(old):
                    raise PermissionError('Current password is incorrect')
                if len(new)<12 or new==old or new.isalpha() or new.isdigit():
                    raise ValueError('New password must have at least 12 characters and include a mix of characters')
                request.user.set_password(new); request.user.save(update_fields=['password'])
                update_session_auth_hash(request,request.user)
                _log(member,'Changed own password')
                return JsonResponse({'ok':True})

            raise ValueError('Unknown action')
    except PermissionError as exc:
        return JsonResponse({'error':str(exc)},status=403)
    except (ValueError, TypeError, ValidationError, IntegrityError, Attendance.DoesNotExist, LeaveRequest.DoesNotExist,
            TimeEntry.DoesNotExist, ApprovalRequest.DoesNotExist, SupportTicket.DoesNotExist,
            ProjectMilestone.DoesNotExist, Lead.DoesNotExist, Project.DoesNotExist) as exc:
        return JsonResponse({'error':str(exc)},status=400)


def _csv_cell(value):
    """Prevent spreadsheet formula injection in user-authored CSV cells."""
    text = str(value if value is not None else '')
    return "'" + text if text.startswith(('=','+','-','@','\t','\r')) else text


@require_http_methods(['GET'])
def export_csv(request, kind):
    try:
        m = _context(request)
    except PermissionError as exc:
        return JsonResponse({'error':str(exc)},status=401)
    if kind not in ('attendance','timesheets','leaves','tickets','leads'):
        return JsonResponse({'error':'Unknown export'},status=404)
    if kind in ('attendance','timesheets','leaves','leads') and m.role == 'client':
        return JsonResponse({'error':'Forbidden'},status=403)
    if kind == 'leads' and m.role not in MANAGERS:
        return JsonResponse({'error':'Forbidden'},status=403)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition']=f'attachment; filename="techfinitys_{kind}.csv"'
    response.write('\ufeff')
    writer=csv.writer(response)
    if kind == 'attendance':
        qs=Attendance.objects.select_related('employee__user').filter(date__gte=timezone.localdate()-timedelta(days=365))
        if m.role not in MANAGERS: qs=qs.filter(employee=m)
        writer.writerow(['Employee','Date','In','Out','Mode','Worked minutes'])
        for a in qs.iterator(chunk_size=500): writer.writerow([_csv_cell(_person(a.employee)),a.date,a.clock_in,a.clock_out or '',a.mode,a.worked_seconds//60])
    elif kind == 'timesheets':
        qs=TimeEntry.objects.select_related('employee__user','client')
        if m.role not in MANAGERS: qs=qs.filter(employee=m)
        writer.writerow(['Employee','Client','Date','Hours','Status','Billable','Description'])
        for t in qs.iterator(chunk_size=500): writer.writerow([_csv_cell(_person(t.employee)),_csv_cell(t.client.name),t.date,round(t.minutes/60,2),t.status,t.billable,_csv_cell(t.description)])
    elif kind == 'leaves':
        qs=LeaveRequest.objects.select_related('employee__user')
        if m.role not in MANAGERS: qs=qs.filter(employee=m)
        writer.writerow(['Employee','From','To','Type','Status','Reason'])
        for r in qs.iterator(chunk_size=500): writer.writerow([_csv_cell(_person(r.employee)),r.start_date,r.end_date,r.leave_type,r.status,_csv_cell(r.reason)])
    elif kind == 'leads':
        writer.writerow(['Contact','Company','Email','Phone','Stage','Estimated value','Source'])
        for l in Lead.objects.all().iterator(chunk_size=500): writer.writerow([_csv_cell(l.name),_csv_cell(l.company),_csv_cell(l.email),_csv_cell(l.phone),l.stage,l.estimated_value,_csv_cell(l.source)])
    else:
        qs=SupportTicket.objects.select_related('client').filter(client_id__in=_client_ids_for(m))
        writer.writerow(['Client','Subject','Priority','Status','Created'])
        for t in qs.iterator(chunk_size=500): writer.writerow([_csv_cell(t.client.name),_csv_cell(t.title),t.priority,t.status,t.created_at])
    return response
