import json
import uuid
from datetime import datetime
from django.contrib.auth import authenticate, login, logout
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import JsonResponse, HttpResponse, FileResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .models import (
    Record, Member, ClientAccount, ClientAssignment, Project, Task, Update, Note,
    CalendarEvent, Notification, ActivityLog
)
from .policy import ROLES, ALL_KINDS, allowed, visible_legacy


def _member_for_user(user):
    if not user.is_authenticated:
        return None
    try:
        return user.workspace_member
    except Member.DoesNotExist:
        return None


def _client_ids_for(member):
    if not member:
        return []
    if member.role in ('admin','manager'):
        return list(ClientAccount.objects.values_list('id', flat=True))
    if member.role == 'client':
        return [member.client_account_id] if member.client_account_id else []
    return list(ClientAssignment.objects.filter(employee=member, active=True).values_list('client_id', flat=True))


def _client_codes_for(member):
    ids = _client_ids_for(member)
    return list(ClientAccount.objects.filter(id__in=ids).values_list('code', flat=True))


def _can_manage_people(member):
    return bool(member and member.role in ('manager','admin'))


def _can_access_client(member, client):
    return bool(member and (member.role in ('admin','manager') or client.id in _client_ids_for(member)))


def _can_access_member(actor, target):
    if not actor:
        return False
    if actor.role == 'admin':
        return True
    if actor.role == 'manager':
        return target.role in ('employee','client') or target.manager_id == actor.id or target.id == actor.id
    return actor.id == target.id


def _assigned_staff_member(client, member_id):
    """Validate personnel on a project belong to the client's delivery team."""
    if not member_id:
        return None
    person = Member.objects.filter(pk=member_id, role__in=('admin', 'manager', 'employee'), is_active=True).first()
    if not person:
        raise ValueError('Staff member not found')
    if person.role == 'employee' and not ClientAssignment.objects.filter(client=client, employee=person, active=True).exists():
        raise PermissionError('Staff member is not assigned to this client')
    return person


def _log(actor, action, entity=None, client=None, detail=''):
    ActivityLog.objects.create(
        actor=actor,
        client=client,
        action=action,
        entity_type=entity.__class__.__name__ if entity else '',
        entity_id=str(getattr(entity, 'pk', '')) if entity else '',
        detail=detail,
    )


def _notify_client_team(client, title, body='', exclude=None):
    qs = Member.objects.filter(is_active=True).filter(
        Q(client_account=client) | Q(client_assignments__client=client, client_assignments__active=True)
    ).distinct()
    if exclude:
        qs = qs.exclude(pk=exclude.pk)
    Notification.objects.bulk_create([
        Notification(recipient=m, client=client, title=title, body=body) for m in qs
    ])


@ensure_csrf_cookie
def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('/login/')
    member = _member_for_user(request.user)
    if not member:
        return render(request, 'workspace/dashboard.html', {'provisioning_error': True})
    return render(request, 'workspace/dashboard.html', {'member': member})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('/')
    error = ''
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username',''), password=request.POST.get('password',''))
        if user:
            login(request, user)
            membership = _member_for_user(user)
            if membership and membership.role in ('employee', 'manager'):
                _log(membership, 'Signed in', detail='Password sign-in')
            return redirect('/')
        error = 'Invalid username or password.'
    return render(request, 'workspace/login.html', {
        'error': error,
        'google_enabled': bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET),
        'google_error': request.GET.get('google_error', ''),
    })


def logout_view(request):
    # Revoke browser push tokens for the session being signed out, so one
    # employee's notifications cannot leak to the next user of this browser.
    if request.user.is_authenticated and request.session.session_key:
        from .models import PushSubscription
        PushSubscription.objects.filter(
            member__user=request.user,
            session_key=request.session.session_key,
        ).delete()
    membership = _member_for_user(request.user)
    if membership and membership.role in ('employee', 'manager'):
        _log(membership, 'Signed out', detail='Session signed out')
    logout(request)
    return redirect('/login/')


def _context(request):
    if not request.user.is_authenticated:
        raise PermissionError('Sign in to continue')
    member = _member_for_user(request.user)
    if not member or not member.is_active:
        raise PermissionError('Account has not been provisioned or is inactive')
    return member


def _member_json(m):
    return {
        'id': m.id,
        'username': m.user.username,
        'name': m.user.get_full_name() or m.user.username,
        'email': m.user.email,
        'role': m.role,
        'roleLabel': m.get_role_display(),
        'department': m.department,
        'jobTitle': m.job_title,
        'phone': m.phone,
        'managerId': m.manager_id,
        'managerName': (m.manager.user.get_full_name() or m.manager.user.username) if m.manager else '',
        'clientId': str(m.client_account_id) if m.client_account_id else '',
        'clientName': m.client_account.name if m.client_account else '',
        'permissions': m.permissions or [],
        'active': m.is_active,
        'profilePhotoUrl': f'/api/collaboration/avatar/{m.pk}/' if m.profile_photo else '',
    }


def _client_json(c):
    return {
        'id': str(c.id), 'code': c.code, 'name': c.name, 'email': c.email, 'phone': c.phone,
        'company': c.company, 'package': c.package, 'status': c.status,
        'statusLabel': c.get_status_display(),
        'assignedEmployees': [a.employee_id for a in c.assignments.filter(active=True)],
        'assignedNames': [a.employee.user.get_full_name() or a.employee.user.username for a in c.assignments.filter(active=True).select_related('employee__user')],
    }


def _project_json(p):
    return {
        'id': str(p.id), 'clientId': str(p.client_id), 'clientName': p.client.name,
        'title': p.title, 'description': p.description, 'status': p.status,
        'code': f'TF-{str(p.id)[:6].upper()}', 'groupName': p.group_name, 'tags': p.tags or [],
        'createdAt': p.created_at.isoformat(), 'updatedAt': p.updated_at.isoformat(),
        'statusLabel': p.get_status_display(), 'progress': p.progress,
        'managerId': p.manager_id, 'managerName': (p.manager.user.get_full_name() or p.manager.user.username) if p.manager else '',
        'ownerId': p.owner_id, 'ownerName': (p.owner.user.get_full_name() or p.owner.user.username) if p.owner else '',
        'startDate': p.start_date.isoformat() if p.start_date else '',
        'dueDate': p.due_date.isoformat() if p.due_date else '',
    }


def _task_json(t):
    return {
        'id': str(t.id), 'clientId': str(t.client_id), 'clientName': t.client.name,
        'code': f'T-{str(t.id)[:7].upper()}', 'taskListId': str(t.task_list_id) if t.task_list_id else '',
        'assigneeIds': list(t.assignees.values_list('id', flat=True)),
        'assigneeNames': [m.user.get_full_name() or m.user.username for m in t.assignees.all()],
        'percentComplete': t.percent_complete, 'billingType': t.billing_type,
        'createdAt': t.created_at.isoformat(), 'updatedAt': t.updated_at.isoformat(),
        'completedAt': t.completed_at.isoformat() if t.completed_at else '',
        'projectId': str(t.project_id) if t.project_id else '', 'projectName': t.project.title if t.project else '',
        'parentId': str(t.parent_id) if t.parent_id else '',
        'title': t.title, 'description': t.description, 'status': t.status,
        'statusLabel': t.get_status_display(), 'priority': t.priority, 'priorityLabel': t.get_priority_display(),
        'assignedTo': t.assigned_to_id, 'assignedName': (t.assigned_to.user.get_full_name() or t.assigned_to.user.username) if t.assigned_to else '',
        'createdBy': t.created_by_id, 'createdByName': (t.created_by.user.get_full_name() or t.created_by.user.username) if t.created_by else '',
        'startAt': t.start_at.isoformat() if t.start_at else '', 'dueAt': t.due_at.isoformat() if t.due_at else '',
        'estimatedHours': float(t.estimated_hours), 'recurrence': t.recurrence, 'clientVisible': t.client_visible,
        'blockedBy': str(t.blocked_by_id) if t.blocked_by_id else '', 'tags': t.tags or [],
    }


def _update_json(u):
    return {
        'id': str(u.id), 'clientId': str(u.client_id), 'clientName': u.client.name,
        'taskId': str(u.task_id) if u.task_id else '', 'taskName': u.task.title if u.task else '',
        'title': u.title, 'body': u.body, 'visibility': u.visibility, 'progress': u.progress,
        'authorId': u.author_id, 'authorName': (u.author.user.get_full_name() or u.author.user.username) if u.author else 'System',
        'createdAt': u.created_at.isoformat(),
    }


def _note_json(n):
    return {
        'id': str(n.id), 'clientId': str(n.client_id), 'clientName': n.client.name,
        'projectId': str(n.project_id) if n.project_id else '', 'taskId': str(n.task_id) if n.task_id else '',
        'body': n.body, 'visibility': n.visibility, 'pinned': n.pinned,
        'authorId': n.author_id, 'authorName': (n.author.user.get_full_name() or n.author.user.username) if n.author else 'System',
        'createdAt': n.created_at.isoformat(),
    }


def _event_json(e):
    return {
        'id': str(e.id), 'clientId': str(e.client_id) if e.client_id else '', 'clientName': e.client.name if e.client else 'Organisation',
        'title': e.title, 'eventType': e.event_type, 'eventTypeLabel': e.get_event_type_display(),
        'description': e.description, 'startAt': e.start_at.isoformat(), 'endAt': e.end_at.isoformat() if e.end_at else '',
        'ownerId': e.owner_id, 'ownerName': (e.owner.user.get_full_name() or e.owner.user.username) if e.owner else '',
        'attendeeIds': list(e.attendees.values_list('id', flat=True)),
        'attendeeNames': [m.user.get_full_name() or m.user.username for m in e.attendees.select_related('user')],
    }



def _run_task_workflows(task, old_status, actor):
    """Execute bounded manager-configured rules for task status changes."""
    if old_status == task.status:
        return
    for record in Record.objects.filter(space='live', kind='workflows'):
        rule = record.data or {}
        if rule.get('status') != 'Active' or rule.get('trigger') != 'task_status':
            continue
        if rule.get('client') not in ('org', task.client.code):
            continue
        if rule.get('toStatus') not in ('any', task.status) or rule.get('fromStatus') not in ('any', old_status):
            continue
        for action in rule.get('actions', [])[:4]:
            if not isinstance(action, dict):
                continue
            if action.get('type') == 'notify_assignee' and task.assigned_to_id:
                Notification.objects.create(recipient=task.assigned_to, client=task.client,
                    title=('Workflow: ' + str(rule.get('title', 'Task updated')))[:220],
                    body=f'{task.title} moved to {task.get_status_display()}.')
            elif action.get('type') == 'set_priority' and action.get('priority') in dict(Task.PRIORITY):
                Task.objects.filter(pk=task.pk).update(priority=action['priority'])
                task.priority = action['priority']
            elif action.get('type') == 'create_followup':
                title = str(action.get('title') or '').strip()[:180]
                if title:
                    Task.objects.create(client=task.client, project=task.project, parent=task,
                        title=title, status='todo', priority='normal', assigned_to=task.assigned_to,
                        created_by=actor, description=f'Automatically created from task: {task.title}',
                        client_visible=task.client_visible)
        _log(actor, 'Executed workflow', task, task.client, str(rule.get('title', 'Workflow'))[:180])


@require_http_methods(['GET','POST'])
def workspace_api(request):
    try:
        member = _context(request)
    except PermissionError as exc:
        return JsonResponse({'error': str(exc)}, status=401)

    # Lightweight recipient-scoped polling for in-app notification popups.
    # Avoid loading the entire CRM workspace every time the timer fires.
    if request.method == 'GET' and request.GET.get('notifications_only') == '1':
        recent = Notification.objects.filter(recipient=member).order_by('-created_at')[:40]
        response = JsonResponse({'notifications': [
            {'id': n.id, 'title': n.title, 'body': n.body,
             'link': n.link, 'read': bool(n.read_at),
             'createdAt': n.created_at.isoformat()}
            for n in recent
        ]})
        response['Cache-Control'] = 'private, no-store'
        return response

    client_ids = _client_ids_for(member)
    client_codes = _client_codes_for(member)

    if request.method == 'GET':
        clients = ClientAccount.objects.filter(id__in=client_ids).prefetch_related('assignments__employee__user')
        if member.role in ('admin','manager'):
            members = Member.objects.select_related('user','manager__user','client_account').all()
        elif member.role == 'employee':
            members = Member.objects.select_related('user','manager__user','client_account').filter(
                Q(pk=member.pk) | Q(client_assignments__client_id__in=client_ids)
            ).distinct()
        else:
            members = Member.objects.select_related('user','manager__user','client_account').filter(Q(pk=member.pk) | Q(client_assignments__client_id__in=client_ids)).distinct()

        projects = Project.objects.filter(client_id__in=client_ids).select_related('client','manager__user','owner__user')
        tasks = Task.objects.filter(client_id__in=client_ids).select_related('client','project','task_list','assigned_to__user','created_by__user').prefetch_related('assignees__user')
        if member.role == 'client':
            tasks = tasks.filter(client_visible=True)
        updates = Update.objects.filter(client_id__in=client_ids).select_related('client','task','author__user')
        notes = Note.objects.filter(client_id__in=client_ids).select_related('client','author__user')
        if member.role == 'client':
            updates = updates.filter(visibility='client').exclude(task__client_visible=False)
            notes = notes.filter(visibility='client').exclude(task__client_visible=False)
        elif member.role == 'employee':
            notes = notes.filter(Q(visibility__in=['client','team']) | Q(visibility='private', author=member))
        if member.role in ('admin','manager'):
            events = CalendarEvent.objects.all()
        elif member.role == 'client':
            events = CalendarEvent.objects.filter(client_id__in=client_ids)
        else:
            events = CalendarEvent.objects.filter(Q(client_id__in=client_ids) | Q(client__isnull=True, attendees=member))
        events = events.select_related('client','owner__user').prefetch_related('attendees')
        notifications = Notification.objects.filter(recipient=member)[:100]
        # Audit details may mention internal task or note titles. Clients see only
        # their own actions, never the internal team's operational audit trail.
        activity_scope = Q(actor=member) if member.role == 'client' else Q(client_id__in=client_ids) | Q(actor=member)
        activities = ActivityLog.objects.filter(activity_scope).select_related('actor__user','client')[:150]

        legacy = []
        for r in Record.objects.filter(space='live').order_by('-updated_at'):
            if r.kind in ('clients','employees','tasks'):
                continue
            if allowed(member.role, r.kind, 'read', member.permissions) and visible_legacy(member.role, client_codes, r.data):
                d = dict(r.data)
                d.setdefault('id', r.id.split(':')[-1]); d.setdefault('kind', r.kind); d.setdefault('client', r.client)
                d['hasAttachment'] = bool(r.attachment)
                legacy.append(d)

        return JsonResponse({
            'context': {
                'id': member.id, 'user': request.user.username, 'name': request.user.get_full_name() or request.user.username,
                'role': member.role, 'roleLabel': member.get_role_display(), 'permissions': member.permissions or [],
                'preferences': (Record.objects.filter(id=f'pref:{member.pk}',space='personal',kind='preferences').values_list('data',flat=True).first() or {}),
                'profilePhotoUrl': f'/api/collaboration/avatar/{member.pk}/' if member.profile_photo else '',
                'clientIds': [str(x) for x in client_ids], 'clientCodes': client_codes,
            },
            'clients': [_client_json(x) for x in clients],
            'members': [({**_member_json(x), 'email': '', 'phone': ''} if member.role == 'client' and x.pk != member.pk else _member_json(x)) for x in members],
            'assignments': [
                {'id': a.id, 'clientId': str(a.client_id), 'employeeId': a.employee_id, 'roleTitle': a.role_title, 'isPrimary': a.is_primary, 'active': a.active}
                for a in ClientAssignment.objects.filter(client_id__in=client_ids, active=True)
            ],
            'projects': [_project_json(x) for x in projects],
            'tasks': [_task_json(x) for x in tasks],
            'updates': [_update_json(x) for x in updates],
            'notes': [_note_json(x) for x in notes],
            'events': [_event_json(x) for x in events],
            'notifications': [
                {'id': n.id, 'title': n.title, 'body': n.body, 'clientId': str(n.client_id) if n.client_id else '', 'link': n.link, 'read': bool(n.read_at), 'createdAt': n.created_at.isoformat()}
                for n in notifications
            ],
            'activities': [
                {'id': a.id, 'action': a.action, 'detail': a.detail, 'entityType': a.entity_type, 'entityId': a.entity_id, 'clientName': a.client.name if a.client else '', 'actorName': (a.actor.user.get_full_name() or a.actor.user.username) if a.actor else 'System', 'createdAt': a.created_at.isoformat()}
                for a in activities
            ],
            'records': legacy,
        })

    try:
        data = json.loads(request.body or b'{}')
    except Exception:
        return JsonResponse({'error':'JSON required'}, status=415)
    action = data.get('action','')

    try:
        with transaction.atomic():
            if action == 'save_preferences':
                allowed_keys = {
                    'fontSize': ('small','normal','large','extra'),
                    'mode': ('light','dark','auto'),
                    'accent': ('blue','orange','teal','red','green','purple'),
                    'panel': ('aurora','solid','glass','minimal'),
                    'landingPage': ('overview','projects','tasks','updates'),
                    'reduceMotion': (True,False),
                    'highContrast': (True,False),
                    'compactMode': (True,False),
                    'feedNotifications': (True,False),
                    'soundNotifications': (True,False),
                    'emailNotifications': (True,False),
                    'activityReminders': (True,False),
                }
                requested = data.get('preferences')
                if not isinstance(requested,dict) or not requested or len(requested)>len(allowed_keys):
                    raise ValueError('Invalid personal preferences')
                if any(key not in allowed_keys or value not in allowed_keys[key]
                       or (isinstance(value,bool) != isinstance(allowed_keys[key][0],bool))
                       for key,value in requested.items()):
                    raise ValueError('Unsupported preferences value')
                ident = f'pref:{member.pk}'
                row, _ = Record.objects.select_for_update().get_or_create(
                    id=ident, defaults={'space':'personal','kind':'preferences','client':str(member.pk),'data':{}}
                )
                row.data = {**(row.data or {}), **requested}
                row.save(update_fields=['data','updated_at'])
                return JsonResponse({'ok':True,'preferences':row.data})

            # --- People & hierarchy -------------------------------------------------
            if action == 'create_client':
                if not _can_manage_people(member):
                    raise PermissionError('Only Office Managers and Super Admins can create clients')
                name = (data.get('name') or '').strip()
                code = (data.get('code') or '').strip().lower().replace(' ','-') or f'client-{uuid.uuid4().hex[:8]}'
                if not name:
                    raise ValueError('Client name is required')
                client = ClientAccount.objects.create(
                    name=name, code=code, email=data.get('email',''), phone=data.get('phone',''), company=data.get('company',''),
                    package=data.get('package',''), status=data.get('status','onboarding'), created_by=request.user,
                )
                _log(member,'Created client',client,client,f'{name} ({code})')

                # Optional employee assignment at client creation time. Managers/admins
                # can still add more employees later from Client assignments.
                employee_id = data.get('employeeId')
                if employee_id:
                    employee = Member.objects.filter(pk=employee_id, role='employee').select_related('user').first()
                    if not employee:
                        raise ValueError('Selected employee was not found')
                    assignment, _ = ClientAssignment.objects.update_or_create(
                        client=client,
                        employee=employee,
                        defaults={
                            'assigned_by': member,
                            'role_title': 'Account team',
                            'is_primary': True,
                            'active': True,
                        },
                    )
                    _log(member,'Assigned employee to client',assignment,client,f'{employee} → {client.name}')
                    Notification.objects.create(
                        recipient=employee,
                        client=client,
                        title=f'Client assigned: {client.name}',
                        body='You can now access this client workspace and its related work.',
                    )

                # optional portal user
                portal_username = (data.get('portalUsername') or '').strip()
                if portal_username:
                    if len(data.get('portalPassword') or '') < 4:
                        raise ValueError('Set a client portal password with at least 4 characters')
                    if User.objects.filter(username=portal_username).exists():
                        raise ValueError('Portal username already exists')
                    u = User.objects.create_user(username=portal_username, email=data.get('email',''), password=data['portalPassword'])
                    u.first_name = data.get('contactFirstName','Client'); u.last_name = data.get('contactLastName', name); u.save()
                    cm = Member.objects.create(user=u, role='client', client_account=client, client=client.code, job_title='Client portal')
                    _log(member,'Provisioned client portal',cm,client,portal_username)
                return JsonResponse({'ok':True,'client':_client_json(client)})

            if action == 'create_member':
                if not _can_manage_people(member):
                    raise PermissionError('Only Office Managers and Super Admins can create employees')
                role = data.get('role','employee')
                if member.role == 'manager' and role not in ('employee','client'):
                    raise PermissionError('Office Managers can create Employees and Client users only')
                if role not in ROLES:
                    raise ValueError('Invalid role')
                username = (data.get('username') or '').strip()
                if not username or User.objects.filter(username=username).exists():
                    raise ValueError('A unique username is required')
                if len(data.get('password') or '') < 4:
                    raise ValueError('New users require a password of at least 4 characters')
                if role == 'client' and not data.get('clientId'):
                    raise ValueError('Client users must belong to a client')
                if role == 'client' and not ClientAccount.objects.filter(pk=data['clientId']).exists():
                    raise ValueError('The selected client does not exist')
                u = User.objects.create_user(username=username, email=data.get('email',''), password=data['password'])
                u.first_name = data.get('firstName',''); u.last_name = data.get('lastName',''); u.save()
                client = ClientAccount.objects.filter(pk=data.get('clientId')).first() if data.get('clientId') else None
                manager_obj = Member.objects.filter(pk=data.get('managerId')).first() if data.get('managerId') else (member if role=='employee' and member.role=='manager' else None)
                m = Member.objects.create(
                    user=u, role=role, client_account=client if role=='client' else None, client=client.code if client and role=='client' else '',
                    manager=manager_obj, department=data.get('department',''), job_title=data.get('jobTitle',''), phone=data.get('phone',''),
                    permissions=data.get('permissions') or [],
                )
                _log(member,'Created team member',m,client,f'{m} reports to {manager_obj or "—"}')
                return JsonResponse({'ok':True,'member':_member_json(m)})

            if action == 'update_member':
                if not _can_manage_people(member):
                    raise PermissionError('Permission denied')
                target = Member.objects.select_related('user').get(pk=data.get('memberId'))
                if not _can_access_member(member,target):
                    raise PermissionError('Cannot manage this user')
                if target.role == 'admin' and member.role != 'admin':
                    raise PermissionError('Only Super Admin can manage administrators')
                if target.pk == member.pk and 'active' in data and not data['active']:
                    raise PermissionError('Cannot deactivate your own account')
                if 'role' in data:
                    new_role = data['role']
                    if new_role not in ('employee', 'manager', 'admin'):
                        raise ValueError('Invalid staff role')
                    if member.role != 'admin' and new_role != target.role:
                        raise PermissionError('Only Super Admin can change roles')
                    if target.pk == member.pk and new_role != 'admin':
                        raise PermissionError('Cannot remove your own Super Admin role')
                    target.role = new_role
                if 'active' in data:
                    target.is_active = bool(data['active'])
                    target.user.is_active = bool(data['active'])
                if 'department' in data: target.department = str(data['department']).strip()[:100]
                if 'jobTitle' in data: target.job_title = str(data['jobTitle']).strip()[:120]
                if 'phone' in data: target.phone = str(data['phone']).strip()[:40]
                if 'managerId' in data:
                    manager_id = data.get('managerId')
                    manager_obj = Member.objects.filter(pk=manager_id, role__in=('manager','admin')).first() if manager_id else None
                    if manager_id and not manager_obj:
                        raise ValueError('Reporting manager not found')
                    if manager_obj and manager_obj.pk == target.pk:
                        raise ValueError('Employees cannot report to themselves')
                    target.manager = manager_obj
                if 'permissions' in data: target.permissions = data.get('permissions') or []
                user = target.user
                for key, attr, max_len in [('firstName','first_name',150),('lastName','last_name',150),('email','email',254)]:
                    if key in data: setattr(user, attr, str(data[key]).strip()[:max_len])
                if 'username' in data:
                    username = str(data['username']).strip()
                    if not username or len(username)>150 or User.objects.exclude(pk=user.pk).filter(username=username).exists():
                        raise ValueError('Username must be unique and not empty')
                    user.username = username
                if data.get('password'):
                    if member.role != 'admin':
                        raise PermissionError('Only Super Admin can reset employee passwords')
                    if len(str(data['password'])) < 4:
                        raise ValueError('Password must have at least 4 characters')
                    user.set_password(str(data['password']))
                user.save()
                target.save()
                _log(member,'Updated team member',target,target.client_account,'Profile, hierarchy or access updated')
                return JsonResponse({'ok':True,'member':_member_json(target)})

            if action == 'delete_member':
                if member.role != 'admin':
                    raise PermissionError('Only Super Admin can delete employee accounts')
                target = Member.objects.select_related('user').get(pk=data.get('memberId'))
                if target.pk == member.pk or target.role == 'admin':
                    raise PermissionError('Super Admin accounts cannot be deleted here')
                if target.role not in ('employee','manager'):
                    raise PermissionError('Only employee and manager accounts can be removed here')
                # Soft-delete preserves attendance, leave, task, project, and audit
                # history. Disabling Django User also revokes further login access.
                target.is_active = False
                target.user.is_active = False
                target.user.save(update_fields=['is_active'])
                target.save(update_fields=['is_active'])
                ClientAssignment.objects.filter(employee=target,active=True).update(active=False)
                _log(member,'Archived employee account',target,detail=f'{target.user.username} access disabled')
                return JsonResponse({'ok':True,'archived':True})

            if action == 'assign_client':
                if not _can_manage_people(member):
                    raise PermissionError('Only Office Managers and Super Admins can assign clients')
                client = ClientAccount.objects.get(pk=data.get('clientId'))
                employee = Member.objects.get(pk=data.get('employeeId'))
                if employee.role not in ('employee','manager'):
                    raise ValueError('Only employees/managers can be assigned to client teams')
                assignment, _ = ClientAssignment.objects.update_or_create(
                    client=client, employee=employee,
                    defaults={'assigned_by':member,'role_title':data.get('roleTitle','Account team'),'is_primary':bool(data.get('isPrimary')),'active':True}
                )
                _log(member,'Assigned employee to client',assignment,client,f'{employee} → {client.name}')
                Notification.objects.create(recipient=employee,client=client,title=f'Assigned to {client.name}',body='You can now access this client workspace.')
                return JsonResponse({'ok':True})

            if action == 'unassign_client':
                if not _can_manage_people(member):
                    raise PermissionError('Permission denied')
                a = ClientAssignment.objects.get(pk=data.get('assignmentId'))
                a.active = False; a.save(update_fields=['active'])
                _log(member,'Removed client assignment',a,a.client,f'{a.employee} removed')
                return JsonResponse({'ok':True})

            # --- Projects -----------------------------------------------------------
            if action == 'save_project':
                client = ClientAccount.objects.get(pk=data.get('clientId'))
                if not _can_access_client(member,client) or member.role == 'client':
                    raise PermissionError('Project creation is restricted to the internal team')
                project_id = data.get('id')
                p = Project.objects.filter(pk=project_id, client=client).first() if project_id else Project(client=client, created_by=member)
                if project_id and not p: raise PermissionError('Project does not belong to this workspace')
                p.client=client; p.title=(data.get('title') or '').strip(); p.description=data.get('description',''); p.status=data.get('status','planned')
                if p.status not in dict(Project.STATUS): raise ValueError('Invalid project status')
                p.progress=max(0,min(100,int(data.get('progress') or 0)))
                if 'groupName' in data:
                    p.group_name = str(data.get('groupName') or '').strip()[:100]
                if 'tags' in data:
                    tags=data['tags']
                    if isinstance(tags,str): tags=[v.strip() for v in tags.split(',') if v.strip()]
                    if not isinstance(tags,list) or len(tags)>15 or any(not isinstance(v,str) or len(v)>35 for v in tags):
                        raise ValueError('Project tags must contain up to 15 short labels')
                    p.tags=tags
                p.manager=_assigned_staff_member(client,data.get('managerId'))
                p.owner=_assigned_staff_member(client,data.get('ownerId'))
                p.start_date=parse_date(data.get('startDate') or '') if data.get('startDate') else None
                p.due_date=parse_date(data.get('dueDate') or '') if data.get('dueDate') else None
                if not p.title: raise ValueError('Project title is required')
                p.save(); _log(member,'Saved project',p,client,p.title)
                _notify_client_team(client,f'Project updated: {p.title}',f'{p.get_status_display()} · {p.progress}% complete',exclude=member)
                return JsonResponse({'ok':True})

            # --- Employee self-service task creation (restricted to assigned clients) ---
            if action == 'self_create_task':
                if member.role != 'employee':
                    raise PermissionError('Employee task creation only')
                project = Project.objects.select_related('client').filter(pk=data.get('projectId')).first()
                if not project or not ClientAssignment.objects.filter(
                    employee=member, client=project.client, active=True
                ).exists():
                    raise PermissionError('You are not assigned to this project client')
                title = str(data.get('title') or '').strip()
                if not 1 <= len(title) <= 220:
                    raise ValueError('Task name must contain 1 to 220 characters')
                description = str(data.get('description') or '').strip()
                if len(description) > 4000:
                    raise ValueError('Description is too long')
                priority = data.get('priority', 'normal')
                if priority not in dict(Task.PRIORITY):
                    raise ValueError('Invalid priority')
                due_at = parse_datetime(data['dueAt']) if data.get('dueAt') else None
                if data.get('dueAt') and not due_at:
                    raise ValueError('Invalid due date')
                t = Task.objects.create(
                    client=project.client, project=project, created_by=member,
                    assigned_to=member, title=title, description=description,
                    priority=priority, status='todo', due_at=due_at,
                    client_visible=False,
                )
                _log(member, 'Created own project task', t, project.client, title)
                # Self-service tasks appear in the creator's inbox as well,
                # confirming the task was saved and assigned to their account.
                Notification.objects.create(
                    recipient=member, client=project.client,
                    title=f'Task added: {t.title}'[:220],
                    body=f'Assigned to you in {project.title}.',
                    link=f'#projects/{project.pk}/tasks',
                )
                return JsonResponse({'ok': True, 'id': str(t.pk)}, status=201)

            # --- Tasks --------------------------------------------------------------
            if action == 'save_task':
                client = ClientAccount.objects.get(pk=data.get('clientId'))
                if not _can_access_client(member,client) or member.role == 'client':
                    raise PermissionError('Clients cannot create internal tasks')
                task_id = data.get('id')
                t = Task.objects.filter(pk=task_id, client=client).first() if task_id else Task(client=client, created_by=member)
                if task_id and not t: raise PermissionError('Task does not belong to this workspace')
                if task_id and member.role == 'employee' and t.assigned_to_id not in (None, member.id) and not t.assignees.filter(pk=member.pk).exists():
                    raise PermissionError('Cannot edit a task assigned to a different employee')
                if data.get('status','todo') not in dict(Task.STATUS) or data.get('priority','normal') not in dict(Task.PRIORITY):
                    raise ValueError('Invalid task status or priority')
                previous_status = t.status if task_id else None
                previous_project_id = t.project_id
                t.client=client; t.title=(data.get('title') or '').strip(); t.description=data.get('description',''); t.status=data.get('status','todo'); t.priority=data.get('priority','normal')
                t.project=Project.objects.filter(pk=data.get('projectId'),client=client).first() if data.get('projectId') else None
                if data.get('projectId') and not t.project:
                    raise PermissionError('Project does not belong to this client')
                t.parent=Task.objects.filter(pk=data.get('parentId'),client=client).first() if data.get('parentId') else None
                if t.parent and t.project_id != t.parent.project_id:
                    raise ValueError('Parent task must belong to the same project')
                if t.parent_id == t.pk: raise ValueError('A task cannot be its own parent')
                blocker_id = data.get('blockedBy')
                if blocker_id:
                    blocker = Task.objects.filter(pk=blocker_id,client=client).first()
                    if not blocker: raise ValueError('Dependency must belong to the same client')
                    cursor = blocker
                    for _ in range(50):
                        if t.pk and cursor.pk == t.pk:
                            raise ValueError('Circular task dependency')
                        if not cursor.blocked_by_id:
                            break
                        cursor = Task.objects.filter(pk=cursor.blocked_by_id, client=client).first()
                        if not cursor:
                            break
                    else:
                        raise ValueError('Dependency chain is too deep')
                    t.blocked_by = blocker
                else:
                    t.blocked_by = None
                tags = data.get('tags',[])
                if isinstance(tags,str): tags = [x.strip() for x in tags.split(',') if x.strip()]
                if not isinstance(tags,list) or len(tags)>12 or any(not isinstance(x,str) or len(x)>40 for x in tags):
                    raise ValueError('Tags must be a list of up to 12 short labels')
                t.tags=tags
                assignee=Member.objects.filter(pk=data.get('assignedTo')).first() if data.get('assignedTo') else None
                if assignee and assignee.role not in ('employee','manager','admin'):
                    raise ValueError('Tasks can only be assigned to employees')
                if assignee and assignee.role=='employee' and not ClientAssignment.objects.filter(client=client,employee=assignee,active=True).exists():
                    raise ValueError('Assign this employee to the client before assigning a task')
                t.assigned_to=assignee; t.recurrence=data.get('recurrence',''); t.client_visible=bool(data.get('clientVisible',True))
                if 'taskListId' in data:
                    from .models import ProjectTaskList
                    task_list_id=data.get('taskListId')
                    task_list=ProjectTaskList.objects.filter(pk=task_list_id, project=t.project).first() if task_list_id and t.project else None
                    if task_list_id and not task_list: raise ValueError('Task list belongs to another project')
                    t.task_list=task_list
                elif t.task_list_id and t.task_list.project_id != t.project_id:
                    t.task_list=None
                if 'billingType' in data:
                    billing=data['billingType']
                    if billing not in ('billable','nonbillable'): raise ValueError('Invalid billing type')
                    t.billing_type=billing
                if 'percentComplete' in data:
                    pct=int(data['percentComplete'])
                    if not 0<=pct<=100: raise ValueError('Completion percentage must be 0–100')
                    t.percent_complete=pct
                t.estimated_hours=data.get('estimatedHours') or 0
                t.start_at=parse_datetime(data.get('startAt')) if data.get('startAt') else None
                t.due_at=parse_datetime(data.get('dueAt')) if data.get('dueAt') else None
                if t.status=='completed' and t.blocked_by_id and t.blocked_by.status!='completed':
                    raise ValueError('Complete the dependency before completing this task')
                if t.status=='completed' and not t.completed_at: t.completed_at=timezone.now()
                if t.status=='completed': t.percent_complete=100
                elif t.percent_complete==100: t.percent_complete=99
                if t.status!='completed': t.completed_at=None
                if not t.title: raise ValueError('Task title is required')
                t.save()
                if 'assigneeIds' in data:
                    from .projects_plus import _staff_for_project
                    ids=data.get('assigneeIds')
                    if not isinstance(ids,list) or len(ids)>12: raise ValueError('Up to 12 task collaborators are supported')
                    t.assignees.set([_staff_for_project(t.project or Project(client=client),pk) for pk in set(ids)])
                from .projects_plus import _recalculate_project
                _recalculate_project(t.project_id)
                if previous_project_id != t.project_id: _recalculate_project(previous_project_id)
                _log(member,'Saved task',t,client,f'{t.title} → {assignee or "Unassigned"}')
                if previous_status is not None: _run_task_workflows(t, previous_status, member)
                if assignee and assignee != member:
                    Notification.objects.create(
                        recipient=assignee, client=client,
                        title=f'Task assigned: {t.title}'[:220],
                        body=f'{client.name} · {t.get_priority_display()} priority',
                        link=f'#projects/{t.project_id}/tasks' if t.project_id else '#tasks',
                    )
                return JsonResponse({'ok':True})

            if action == 'task_status':
                t = Task.objects.select_related('client').get(pk=data.get('id'))
                old_status = t.status
                if not _can_access_client(member,t.client) or member.role=='client': raise PermissionError('Permission denied')
                if member.role=='employee' and t.assigned_to_id not in (None,member.id) and not t.assignees.filter(pk=member.pk).exists(): raise PermissionError('This task is assigned to another employee')
                next_status=data.get('status',t.status)
                if next_status not in dict(Task.STATUS): raise ValueError('Invalid task status')
                if next_status=='completed' and t.blocked_by_id and t.blocked_by.status!='completed':
                    raise ValueError('Complete the dependency first')
                t.status=next_status; t.completed_at=timezone.now() if t.status=='completed' else None
                t.percent_complete=100 if next_status=='completed' else min(t.percent_complete,99)
                t.save(update_fields=['status','completed_at','percent_complete','updated_at'])
                from .projects_plus import _recalculate_project
                _recalculate_project(t.project_id)
                _log(member,'Changed task status',t,t.client,f'{t.title}: {old_status.replace("_"," ")} → {next_status.replace("_"," ")}')
                _run_task_workflows(t, old_status, member)
                return JsonResponse({'ok':True})

            # --- Updates / notes ----------------------------------------------------
            if action == 'add_update':
                client=ClientAccount.objects.get(pk=data.get('clientId'))
                if not _can_access_client(member,client): raise PermissionError('Client access denied')
                if member.role=='client':
                    visibility='client'
                else:
                    visibility=data.get('visibility','client')
                task=Task.objects.filter(pk=data.get('taskId'),client=client).first() if data.get('taskId') else None
                if task and not task.client_visible and (member.role=='client' or visibility=='client'):
                    raise PermissionError('Internal tasks cannot be linked to client-visible updates')
                u=Update.objects.create(client=client,task=task,author=member,title=(data.get('title') or 'Progress update').strip(),body=(data.get('body') or '').strip(),visibility=visibility,progress=max(0,min(100,int(data.get('progress') or 0))))
                _log(member,'Posted update',u,client,u.title)
                if visibility=='client' and member.role!='client': _notify_client_team(client,f'New update: {u.title}',u.body[:180],exclude=member)
                return JsonResponse({'ok':True})

            if action == 'add_note':
                client=ClientAccount.objects.get(pk=data.get('clientId'))
                if not _can_access_client(member,client): raise PermissionError('Client access denied')
                vis='client' if member.role=='client' else data.get('visibility','team')
                if vis not in dict(Note.VISIBILITY): raise ValueError('Invalid note visibility')
                note_task=Task.objects.filter(pk=data.get('taskId'),client=client).first() if data.get('taskId') else None
                if vis=='client' and note_task and not note_task.client_visible:
                    raise PermissionError('Internal tasks cannot be linked to public notes')
                n=Note.objects.create(client=client,author=member,body=(data.get('body') or '').strip(),visibility=vis,pinned=bool(data.get('pinned')),
                    task=note_task,
                    project=Project.objects.filter(pk=data.get('projectId'),client=client).first() if data.get('projectId') else None)
                _log(member,'Added note',n,client,vis)
                return JsonResponse({'ok':True})

            # --- Calendar -----------------------------------------------------------
            if action == 'save_event':
                client=ClientAccount.objects.filter(pk=data.get('clientId')).first() if data.get('clientId') else None
                if client and not _can_access_client(member,client): raise PermissionError('Client access denied')
                if member.role=='client': raise PermissionError('Clients cannot schedule internal calendar events')
                start=parse_datetime(data.get('startAt') or '')
                if not start: raise ValueError('Start date/time is required')
                event_id=data.get('id')
                e=CalendarEvent.objects.filter(pk=event_id).first() if event_id else CalendarEvent(created_by=member)
                if event_id and not e: raise ValueError('Event not found')
                if event_id and (e.client_id != (client.id if client else None) or (member.role == 'employee' and e.owner_id != member.id)):
                    raise PermissionError('Cannot edit this event')
                if not client and member.role not in ('manager','admin'):
                    raise PermissionError('Only managers can create organisation-wide events')
                e.client=client; e.title=(data.get('title') or '').strip(); e.event_type=data.get('eventType','meeting'); e.description=data.get('description',''); e.start_at=start
                e.end_at=parse_datetime(data.get('endAt')) if data.get('endAt') else None; e.owner=Member.objects.filter(pk=data.get('ownerId')).first() or member
                if not e.title: raise ValueError('Event title is required')
                attendees=Member.objects.filter(pk__in=data.get('attendeeIds') or [],is_active=True)
                if member.role=='employee' and any(a.role=='employee' and not ClientAssignment.objects.filter(client=client,employee=a,active=True).exists() for a in attendees):
                    raise PermissionError('Attendee is not assigned to this client')
                e.save(); e.attendees.set(attendees)
                _log(member,'Saved calendar event',e,client,e.title)
                for a in e.attendees.exclude(pk=member.pk): Notification.objects.create(recipient=a,client=client,title=f'Calendar: {e.title}',body=e.start_at.strftime('%d %b %Y %I:%M %p'))
                return JsonResponse({'ok':True})

            if action == 'read_notification':
                n=Notification.objects.get(pk=data.get('id'),recipient=member); n.read_at=timezone.now(); n.save(update_fields=['read_at']); return JsonResponse({'ok':True})

            # --- Existing generic modules ------------------------------------------
            kind=data.get('kind')
            if kind not in ALL_KINDS or kind in ('clients','employees','tasks','projects','updates','notes','calendar','assignments'):
                raise ValueError('Unknown action')
            if kind == 'workflows':
                if member.role not in ('admin', 'manager'):
                    raise PermissionError('Only managers may configure automation rules')
                if data.get('action') == 'delete_workflow':
                    record = Record.objects.filter(id=f"live:{data.get('id')}", kind='workflows', space='live').first()
                    if not record: raise ValueError('Workflow not found')
                    record.delete()
                    _log(member, 'Deleted workflow', detail='Workflow removed')
                    return JsonResponse({'ok':True})
                if data.get('trigger') != 'task_status' or data.get('status') not in ('Draft','Active'):
                    raise ValueError('Invalid workflow trigger or status')
                for field in ('fromStatus','toStatus'):
                    if data.get(field) not in ('any', *dict(Task.STATUS)):
                        raise ValueError('Invalid task status condition')
                actions = data.get('actions')
                if not isinstance(actions, list) or not 1 <= len(actions) <= 4:
                    raise ValueError('Choose 1 to 4 workflow actions')
                for entry in actions:
                    if not isinstance(entry,dict) or entry.get('type') not in ('notify_assignee','set_priority','create_followup'):
                        raise ValueError('Invalid workflow action')
                    if entry['type'] == 'set_priority' and entry.get('priority') not in dict(Task.PRIORITY):
                        raise ValueError('Invalid priority')
                    if entry['type'] == 'create_followup' and not str(entry.get('title') or '').strip()[:180]:
                        raise ValueError('Follow-up task title is required')
                if data.get('client') not in ('org', *ClientAccount.objects.values_list('code',flat=True)):
                    raise ValueError('Choose an existing client')
            if not allowed(member.role,kind,'write',member.permissions): raise PermissionError('Permission denied')
            rid=data.get('id') or str(uuid.uuid4()); obj=Record.objects.filter(id=f'live:{rid}',space='live').first(); old=dict(obj.data) if obj else {}
            client_code=old.get('client') or data.get('client') or (client_codes[0] if len(client_codes)==1 else 'org')
            if member.role not in ('admin','manager') and client_code not in client_codes and not (member.role=='employee' and client_code=='org'): raise PermissionError('Client access denied')
            if obj and member.role not in ('admin','manager') and not visible_legacy(member.role,client_codes,obj.data):
                raise PermissionError('Record does not belong to your workspace')
            next_row={**old,**{k:v for k,v in data.items() if k not in ('action','kind','id')},'id':rid,'kind':kind,'client':client_code,'updatedAt':timezone.now().isoformat()}
            if not next_row.get('title'): next_row['title']=kind.title()
            if not next_row.get('status'): next_row['status']='Draft'
            record,_ = Record.objects.update_or_create(id=f'live:{rid}',defaults={'space':'live','kind':kind,'client':client_code,'data':next_row})
            if data.get('fileData'):
                if kind != 'files' or member.role == 'client':
                    raise PermissionError('File upload denied')
                import base64
                from django.core.files.base import ContentFile
                try:
                    raw = base64.b64decode(data['fileData'])
                except Exception:
                    raise ValueError('Invalid upload')
                if len(raw) > 5_000_000:
                    raise ValueError('Maximum file size is 5 MB')
                record.attachment.save(data.get('fileName') or 'upload.bin', ContentFile(raw), save=True)
                next_row['detail'] = f'Uploaded file · {len(raw)} bytes'
                record.data = next_row
                record.save(update_fields=['data'])
            _log(member,f'Updated {kind}',None,ClientAccount.objects.filter(code=client_code).first(),next_row['title'])
            return JsonResponse({'ok':True,'record':next_row})

    except PermissionError as exc:
        return JsonResponse({'error':str(exc)},status=403)
    except (ValueError, TypeError, ValidationError, ClientAccount.DoesNotExist, Member.DoesNotExist, Task.DoesNotExist, ClientAssignment.DoesNotExist) as exc:
        return JsonResponse({'error':str(exc)},status=400)


def file_download(request, record_id):
    try:
        member=_context(request)
    except PermissionError as e:
        return HttpResponse(str(e),status=403)
    obj=Record.objects.filter(id=f'live:{record_id}',space='live',kind='files').first()
    if not obj or not visible_legacy(member.role,_client_codes_for(member),obj.data): return HttpResponse('File not found',status=404)
    if obj.attachment: return FileResponse(obj.attachment.open('rb'),as_attachment=True,filename=obj.attachment.name.split('/')[-1])
    body=obj.data.get('body') or obj.data.get('detail',''); res=HttpResponse(body,content_type='text/plain'); res['Content-Disposition']=f'attachment; filename="{obj.data.get("title","reference")}.txt"'; return res


def razorpay_stub(request):
    return JsonResponse({'error':'Live payment gateway is not configured in this local build.'},status=503)
