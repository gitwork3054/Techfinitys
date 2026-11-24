"""Project workspace API: task lists, issues, team, project feed, documents,
widget layouts and bulk updates. Every database operation is tenant scoped.
"""
import csv
import json
from datetime import datetime, time
from pathlib import Path
from uuid import UUID
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_http_methods
from .models import (
    Project, Task, Member, ClientAssignment, ProjectTaskList, ProjectTeam,
    ProjectIssue, ProjectDiscussion, ProjectDocument, DashboardLayout, Notification,
)
from .views import _context, _client_ids_for, _log

STAFF = ('admin', 'manager', 'employee')
MANAGERS = ('admin', 'manager')
WIDGETS = {'stats', 'today', 'overdue', 'task_chart', 'team', 'issues', 'progress',
           'activity', 'approvals', 'timesheets', 'projects', 'shortcuts', 'calendar', 'updates'}
DEFAULT_GLOBAL = ['stats', 'today', 'overdue', 'projects', 'issues', 'approvals', 'activity']
DEFAULT_PROJECT = ['stats', 'task_chart', 'overdue', 'team', 'issues', 'progress', 'activity']
FILE_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.webp', '.doc', '.docx', '.xls',
                   '.xlsx', '.ppt', '.pptx', '.csv', '.txt', '.zip'}


def _name(member):
    return member.user.get_full_name() or member.user.username if member else 'System'


def _short(text, limit, field='Text', required=True):
    text = str(text or '').strip()
    if required and not text:
        raise ValueError(f'{field} is required')
    if len(text) > limit:
        raise ValueError(f'{field} cannot exceed {limit} characters')
    return text


def _choice(text, choices, field):
    if text not in choices:
        raise ValueError(f'Invalid {field}')
    return text


def _project(member, project_id):
    # Return "not found" for both nonexistent and unauthorized projects.
    try:
        return Project.objects.select_related('client').get(pk=project_id, client_id__in=_client_ids_for(member))
    except (ValueError, TypeError, ValidationError, Project.DoesNotExist):
        raise ValueError('Project not found in your workspace')


def _task(member, task_id):
    try:
        task = Task.objects.select_related('project', 'client', 'blocked_by').get(pk=task_id, client_id__in=_client_ids_for(member))
    except (ValueError, TypeError, ValidationError, Task.DoesNotExist):
        raise ValueError('Task not found in your workspace')
    if member.role == 'client' and not task.client_visible:
        raise PermissionError('This task is internal')
    return task


def _staff(member):
    if member.role not in STAFF:
        raise PermissionError('This operation is for the internal delivery team')


def _staff_for_project(project, member_id):
    if not member_id:
        return None
    member = Member.objects.filter(pk=member_id, is_active=True, role__in=STAFF).first()
    if not member:
        raise ValueError('Selected staff member was not found')
    if member.role == 'employee' and not ClientAssignment.objects.filter(
        client_id=project.client_id, employee=member, active=True
    ).exists():
        raise PermissionError('Assign this employee to the client first')
    return member


def _can_edit_task(member, task):
    _staff(member)
    if member.role == 'employee' and task.assigned_to_id not in (None, member.pk) and not task.assignees.filter(pk=member.pk).exists():
        raise PermissionError('Task is assigned to another employee')


def _when(text):
    if not text:
        return None
    value = parse_datetime(str(text))
    if value is None:
        raise ValueError('Date must include a valid time')
    return timezone.make_aware(value, timezone.get_current_timezone()) if timezone.is_naive(value) else value


def _notify_project(project, title, body='', exclude=None, client_visible=True):
    team = Member.objects.filter(project_memberships__project=project, is_active=True)
    if client_visible:
        team = Member.objects.filter(
            Q(project_memberships__project=project) | Q(role='client', client_account_id=project.client_id),
            is_active=True,
        )
    team = team.distinct()
    if exclude:
        team = team.exclude(pk=exclude.pk)
    Notification.objects.bulk_create([
        Notification(recipient=p, client=project.client, title=title[:220], body=body[:800]) for p in team
    ])


def _recalculate_project(project_id):
    if not project_id:
        return
    from django.db.models import Count
    qs = Task.objects.filter(project_id=project_id)
    total = qs.count()
    if total:
        complete = qs.filter(status='completed').count()
        Project.objects.filter(pk=project_id).update(progress=round(complete * 100 / total))


def _issue_json(i):
    return {
        'id': str(i.pk), 'projectId': str(i.project_id), 'projectName': i.project.title,
        'clientId': str(i.client_id), 'title': i.title, 'description': i.description,
        'taskId': str(i.task_id) if i.task_id else '', 'status': i.status, 'priority': i.priority,
        'assignedTo': i.assigned_to_id, 'assignedName': _name(i.assigned_to) if i.assigned_to else '',
        'reportedBy': _name(i.reported_by) if i.reported_by else '',
        'dueAt': i.due_at.isoformat() if i.due_at else '', 'clientVisible': i.client_visible,
        'createdAt': i.created_at.isoformat(), 'updatedAt': i.updated_at.isoformat(),
    }


def _doc_json(d):
    return {
        'id': str(d.pk), 'projectId': str(d.project_id), 'title': d.title,
        'size': d.size_bytes, 'clientVisible': d.client_visible,
        'uploadedBy': _name(d.uploaded_by) if d.uploaded_by else 'System',
        'createdAt': d.created_at.isoformat(),
        'downloadUrl': f'/api/projects-plus/document/{d.pk}/',
    }


def _get(member):
    client_ids = _client_ids_for(member)
    projects = Project.objects.filter(client_id__in=client_ids)
    lists = ProjectTaskList.objects.filter(project__client_id__in=client_ids).select_related('project')[:1500]
    issues = ProjectIssue.objects.filter(client_id__in=client_ids).select_related(
        'project', 'reported_by__user', 'assigned_to__user', 'task'
    )
    discussions = ProjectDiscussion.objects.filter(project__client_id__in=client_ids).select_related(
        'project', 'author__user'
    )
    documents = ProjectDocument.objects.filter(project__client_id__in=client_ids).select_related('project', 'uploaded_by__user')
    if member.role == 'client':
        issues = issues.filter(client_visible=True).exclude(task__client_visible=False)
        discussions = discussions.filter(visibility='client')
        documents = documents.filter(client_visible=True)
    memberships = ProjectTeam.objects.filter(project__client_id__in=client_ids).select_related('member__user')[:1500]
    layouts = DashboardLayout.objects.filter(owner=member)
    return {
        'taskLists': [
            {'id': str(r.pk), 'projectId': str(r.project_id), 'title': r.title, 'position': r.position}
            for r in lists
        ],
        'projectIssues': [_issue_json(r) for r in issues[:900]],
        'projectFeed': [
            {'id': str(r.pk), 'projectId': str(r.project_id), 'body': r.body,
             'author': _name(r.author) if r.author else 'System',
             'authorId': r.author_id, 'visibility': r.visibility,
             'parentId': str(r.parent_id) if r.parent_id else '', 'createdAt': r.created_at.isoformat(),
             'photoUrl': f'/api/projects-plus/feed-photo/{r.pk}/' if r.photo else ''}
            for r in discussions[:900]
        ],
        'projectDocs': [_doc_json(r) for r in documents[:800]],
        'projectTeams': [
            {'id': r.id, 'projectId': str(r.project_id), 'memberId': r.member_id,
             'name': _name(r.member), 'role': r.role}
            for r in memberships
        ],
        'dashboardLayouts': [{'scope': r.scope, 'widgets': r.widgets} for r in layouts],
        'defaultWidgets': {'global': DEFAULT_GLOBAL, 'project': DEFAULT_PROJECT},
        'projectGroups': sorted(set(filter(None, projects.values_list('group_name', flat=True)))),
    }


@require_http_methods(['GET', 'POST'])
def projects_plus_api(request):
    try:
        member = _context(request)
        if request.method == 'GET':
            return JsonResponse(_get(member))
        payload = json.loads(request.body or b'{}')
        if not isinstance(payload, dict):
            raise ValueError('JSON object required')
        action = payload.get('action')
        with transaction.atomic():
            if action == 'quick_create_task':
                # Quick entry is intentionally restricted to the same roles that
                # can access the full task creation form.
                if member.role not in MANAGERS:
                    raise PermissionError('Only managers can create tasks')
                project = _project(member, payload.get('projectId'))
                title = _short(payload.get('title'), 220, 'Task name')
                list_id = payload.get('taskListId') or None
                task_list = None
                if list_id:
                    task_list = ProjectTaskList.objects.filter(pk=list_id, project=project).first()
                    if not task_list:
                        raise ValueError('Task list must belong to the selected project')
                task = Task.objects.create(
                    client=project.client, project=project, task_list=task_list,
                    title=title, status='todo', priority='normal',
                    created_by=member, client_visible=False,
                )
                _recalculate_project(project.pk)
                _log(member, 'Created task', task, project.client, title)
                # Managers' quick-add rows create unassigned tasks. Notify only
                # active employees assigned to this client, not unrelated staff.
                recipients = Member.objects.filter(
                    role='employee', is_active=True, user__is_active=True,
                    client_assignments__client=project.client,
                    client_assignments__active=True,
                ).exclude(pk=member.pk).distinct()
                Notification.objects.bulk_create([
                    Notification(
                        recipient=employee, client=project.client,
                        title=f'New project task: {title}'[:220],
                        body=f'{project.title} · Task available for assignment.',
                        link=f'#projects/{project.pk}/tasks',
                    ) for employee in recipients
                ])
                return JsonResponse({'ok': True, 'id': str(task.pk)}, status=201)

            if action == 'set_task_date':
                if member.role not in MANAGERS:
                    raise PermissionError('Only managers can reschedule tasks')
                task = _task(member, payload.get('taskId'))
                field = _choice(payload.get('field'), {'startAt', 'dueAt'}, 'date field')
                raw = payload.get('date', '')
                if not isinstance(raw, str) or len(raw) > 10:
                    raise ValueError('Choose a valid calendar date')
                day = parse_date(raw) if raw else None
                if raw and day is None:
                    raise ValueError('Choose a valid calendar date')
                attr = 'start_at' if field == 'startAt' else 'due_at'
                existing = getattr(task, attr)
                local_time = timezone.localtime(existing).time().replace(tzinfo=None) if existing else time(hour=9)
                new_value = timezone.make_aware(
                    datetime.combine(day, local_time), timezone.get_current_timezone()
                ) if day else None
                start = new_value if attr == 'start_at' else task.start_at
                due = new_value if attr == 'due_at' else task.due_at
                if start and due and start > due:
                    raise ValueError('Due date cannot be before start date')
                setattr(task, attr, new_value)
                task.save(update_fields=[attr, 'updated_at'])
                _log(member, 'Updated task dates', task, task.client,
                     f'{task.title} - {field}: {day.isoformat() if day else "cleared"}')
                return JsonResponse({'ok': True, 'date': day.isoformat() if day else ''})

            if action == 'save_project_meta':
                _staff(member)
                p = _project(member, payload.get('projectId'))
                if 'groupName' in payload:
                    p.group_name = _short(payload['groupName'], 100, 'Project group', False)
                if 'tags' in payload:
                    tags = payload.get('tags')
                    if isinstance(tags, str):
                        tags = [x.strip() for x in tags.split(',') if x.strip()]
                    if not isinstance(tags, list) or len(tags) > 15 or any(not isinstance(x, str) or len(x) > 35 for x in tags):
                        raise ValueError('Provide up to 15 short project tags')
                    p.tags = tags
                p.save(update_fields=['group_name', 'tags', 'updated_at'])
                _log(member, 'Updated project details', p, p.client)
                return JsonResponse({'ok': True})

            if action in ('save_task_list', 'delete_task_list'):
                _staff(member)
                project = _project(member, payload.get('projectId'))
                list_id = payload.get('id')
                item = ProjectTaskList.objects.filter(pk=list_id, project=project).first() if list_id else None
                if action == 'delete_task_list':
                    if not item:
                        raise ValueError('Task list not found')
                    if item.tasks.exists():
                        raise ValueError('Move tasks to another list before deleting it')
                    item.delete()
                elif list_id and not item:
                    raise ValueError('Task list not found')
                else:
                    title = _short(payload.get('title'), 120, 'Task list name')
                    if item is None:
                        item = ProjectTaskList(project=project, created_by=member)
                    item.title = title
                    if 'position' in payload:
                        item.position = min(10000, max(0, int(payload['position'])))
                    item.save()
                _log(member, 'Changed project task lists', project, project.client)
                return JsonResponse({'ok': True})

            if action == 'set_task_extra':
                task = _task(member, payload.get('taskId'))
                _can_edit_task(member, task)
                if 'taskListId' in payload:
                    list_id = payload.get('taskListId')
                    if list_id and not task.project_id:
                        raise ValueError('Choose a project before a task list')
                    item = ProjectTaskList.objects.filter(pk=list_id, project_id=task.project_id).first() if list_id else None
                    if list_id and not item:
                        raise ValueError('Task list must belong to the selected project')
                    task.task_list = item
                if 'billingType' in payload:
                    task.billing_type = _choice(payload['billingType'], {'billable', 'nonbillable'}, 'billing type')
                if 'percentComplete' in payload:
                    value = int(payload['percentComplete'])
                    if not 0 <= value <= 100:
                        raise ValueError('Completion percentage must be 0–100')
                    if task.status == 'completed' and value != 100:
                        raise ValueError('Completed tasks must be 100% complete')
                    task.percent_complete = value
                task.save()
                if 'assigneeIds' in payload:
                    ids = payload['assigneeIds']
                    if not isinstance(ids, list) or len(ids) > 12:
                        raise ValueError('Up to 12 task collaborators are allowed')
                    assignees = []
                    for member_id in set(ids):
                        assignees.append(_staff_for_project(task.project or Project(client=task.client), member_id))
                    task.assignees.set(assignees)
                _log(member, 'Updated task details', task, task.client)
                return JsonResponse({'ok': True})

            if action == 'bulk_task_status':
                _staff(member)
                ids = payload.get('taskIds') or []
                if not isinstance(ids, list) or not 1 <= len(ids) <= 50 or len(ids) != len(set(ids)):
                    raise ValueError('Select 1–50 distinct tasks')
                target = _choice(payload.get('status'), {s[0] for s in Task.STATUS}, 'task status')
                tasks = list(Task.objects.select_for_update().select_related('blocked_by').filter(
                    pk__in=ids, client_id__in=_client_ids_for(member)
                ))
                if len(tasks) != len(ids):
                    raise PermissionError('One or more tasks are outside your workspace')
                touched = set()
                for task in tasks:
                    _can_edit_task(member, task)
                    if target == 'completed' and task.blocked_by_id and task.blocked_by.status != 'completed':
                        raise ValueError(f'Complete the dependency of {task.title} first')
                    old_status = task.status
                    task.status = target
                    task.completed_at = timezone.now() if target == 'completed' else None
                    task.percent_complete = 100 if target == 'completed' else min(task.percent_complete, 99)
                    task.save(update_fields=['status', 'completed_at', 'percent_complete', 'updated_at'])
                    touched.add(task.project_id)
                    _log(member, 'Bulk changed task status', task, task.client, target)
                    from .views import _run_task_workflows
                    _run_task_workflows(task, old_status, member)
                for pk in touched:
                    _recalculate_project(pk)
                return JsonResponse({'ok': True, 'updated': len(tasks)})

            if action == 'save_project_member':
                if member.role not in MANAGERS:
                    raise PermissionError('Only managers can manage project teams')
                project = _project(member, payload.get('projectId'))
                person = _staff_for_project(project, payload.get('memberId'))
                role = _choice(payload.get('role', 'contributor'), {'lead', 'contributor', 'observer'}, 'team role')
                ProjectTeam.objects.update_or_create(project=project, member=person, defaults={'role': role})
                _log(member, 'Assigned project team member', project, project.client, _name(person))
                return JsonResponse({'ok': True})

            if action == 'remove_project_member':
                if member.role not in MANAGERS:
                    raise PermissionError('Only managers can manage project teams')
                project = _project(member, payload.get('projectId'))
                deleted, _ = ProjectTeam.objects.filter(project=project, member_id=payload.get('memberId')).delete()
                if not deleted:
                    raise ValueError('Project team member not found')
                _log(member, 'Removed project team member', project, project.client)
                return JsonResponse({'ok': True})

            if action == 'save_issue':
                project = _project(member, payload.get('projectId'))
                task = _task(member, payload.get('taskId')) if payload.get('taskId') else None
                if task and task.project_id != project.id:
                    raise ValueError('Issue task must belong to this project')
                title = _short(payload.get('title'), 220, 'Issue title')
                priority = _choice(payload.get('priority', 'normal'), {s[0] for s in ProjectIssue.PRIORITY}, 'priority')
                visible = True if member.role == 'client' else bool(payload.get('clientVisible', True))
                assignee = _staff_for_project(project, payload.get('assignedTo')) if member.role in STAFF else None
                issue = ProjectIssue.objects.create(
                    project=project, client=project.client, task=task, title=title,
                    description=_short(payload.get('description'), 4000, 'Description', False),
                    priority=priority, reported_by=member, assigned_to=assignee,
                    due_at=_when(payload.get('dueAt')), client_visible=visible,
                )
                _log(member, 'Created issue', issue, project.client, title)
                _notify_project(project, f'New issue: {title}', priority, exclude=member, client_visible=visible)
                return JsonResponse({'ok': True, 'id': str(issue.pk)})

            if action == 'issue_status':
                _staff(member)
                try:
                    issue = ProjectIssue.objects.select_for_update().select_related('project__client').get(
                        pk=payload.get('id'), client_id__in=_client_ids_for(member))
                except (ValueError, ValidationError, ProjectIssue.DoesNotExist):
                    raise ValueError('Issue not found in your workspace')
                status = _choice(payload.get('status'), {s[0] for s in ProjectIssue.STATUS}, 'issue status')
                issue.status = status
                issue.resolved_at = timezone.now() if status in ('resolved', 'closed') else None
                issue.save(update_fields=['status', 'resolved_at', 'updated_at'])
                _log(member, 'Updated issue', issue, issue.client, status)
                _notify_project(issue.project, f'Issue {status.replace("_", " ")}: {issue.title}',
                                exclude=member, client_visible=issue.client_visible)
                return JsonResponse({'ok': True})

            if action == 'post_project_feed':
                project = _project(member, payload.get('projectId'))
                visibility = 'client' if member.role == 'client' else _choice(
                    payload.get('visibility', 'client'), {'client', 'team'}, 'visibility'
                )
                parent = None
                if payload.get('parentId'):
                    parent = ProjectDiscussion.objects.filter(pk=payload['parentId'], project=project).first()
                    if not parent or (member.role == 'client' and parent.visibility != 'client'):
                        raise PermissionError('Parent post is not visible in this workspace')
                body = _short(payload.get('body'), 4000, 'Message')
                post = ProjectDiscussion.objects.create(project=project, author=member, body=body,
                                                        visibility=visibility, parent=parent)
                _log(member, 'Posted project update', post, project.client, body[:120])
                _notify_project(project, f'New project discussion: {project.title}', body[:180],
                                exclude=member, client_visible=visibility == 'client')
                return JsonResponse({'ok': True})

            if action == 'save_dashboard_layout':
                scope = _short(payload.get('scope', 'global'), 60, 'Dashboard scope')
                if scope != 'global':
                    if not scope.startswith('project:'):
                        raise ValueError('Invalid dashboard scope')
                    _project(member, scope[8:])
                widgets = payload.get('widgets')
                if not isinstance(widgets, list) or not 1 <= len(widgets) <= 14 or len(set(widgets)) != len(widgets):
                    raise ValueError('Choose 1–14 different widgets')
                if any(key not in WIDGETS for key in widgets):
                    raise ValueError('Dashboard includes an unsupported widget')
                DashboardLayout.objects.update_or_create(owner=member, scope=scope, defaults={'widgets': widgets})
                return JsonResponse({'ok': True})

            raise ValueError('Unknown project action')
    except PermissionError as exc:
        return JsonResponse({'error': str(exc)}, status=403)
    except (ValueError, TypeError, ValidationError, IntegrityError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)


@require_http_methods(['POST'])
def project_feed_photo_upload(request):
    """Post an update with an optional employee photo, scoped to its project."""
    try:
        from PIL import Image, UnidentifiedImageError
        member = _context(request)
        _staff(member)
        project = _project(member, request.POST.get('projectId'))
        visibility = _choice(request.POST.get('visibility', 'team'), {'client', 'team'}, 'visibility')
        body = _short(request.POST.get('body'), 4000, 'Message', required=False)
        photo = request.FILES.get('photo')
        if not photo:
            raise ValueError('Select a photo to upload')
        if not 0 < photo.size <= 5_000_000:
            raise ValueError('Photo must be smaller than 5 MB')
        ext = Path(photo.name).suffix.lower()
        if ext not in {'.jpg', '.jpeg', '.png', '.webp'}:
            raise ValueError('Choose a JPG, PNG or WebP photo')
        try:
            image = Image.open(photo)
            image.verify()
            if image.format not in ('JPEG', 'PNG', 'WEBP'):
                raise ValueError('Unsupported photo format')
            photo.seek(0)
            image = Image.open(photo)
            if image.width * image.height > 24_000_000:
                raise ValueError('Photo dimensions are too large')
            image.load()
            photo.seek(0)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise ValueError('Photo could not be verified')
        parent = None
        if request.POST.get('parentId'):
            parent = ProjectDiscussion.objects.filter(
                pk=request.POST['parentId'], project=project
            ).first()
            if not parent:
                raise PermissionError('Parent update is not available')
            if visibility == 'client' and parent.visibility == 'team':
                raise PermissionError('Internal replies cannot be made client-visible')
        post = ProjectDiscussion.objects.create(
            project=project, author=member, body=body,
            visibility=visibility, parent=parent, photo=photo,
        )
        _log(member, 'Posted project update with photo', post, project.client, (body or 'Photo attached')[:120])
        _notify_project(project, f'New project photo update: {project.title}',
                        (body or 'A photo was attached')[:180],
                        exclude=member, client_visible=visibility == 'client')
        return JsonResponse({'ok': True, 'id': str(post.pk)}, status=201)
    except PermissionError as exc:
        return JsonResponse({'error': str(exc)}, status=403)
    except (ValueError, TypeError, ValidationError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)


@require_http_methods(['GET'])
def project_feed_photo(request, post_id):
    """Serve images through Django's membership and visibility checks."""
    try:
        member = _context(request)
    except PermissionError:
        return HttpResponse('Sign in required', status=401)
    post = ProjectDiscussion.objects.filter(
        pk=post_id, project__client_id__in=_client_ids_for(member)
    ).first()
    if not post or not post.photo or (member.role == 'client' and post.visibility != 'client'):
        return HttpResponse('Photo not found', status=404)
    try:
        stream = post.photo.open('rb')
    except (OSError, FileNotFoundError):
        return HttpResponse('Photo storage unavailable', status=404)
    suffix = Path(post.photo.name).suffix.lower()
    media_type = {'.png': 'image/png', '.webp': 'image/webp',
                  '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}.get(suffix, 'application/octet-stream')
    response = FileResponse(stream, content_type=media_type)
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@require_http_methods(['POST'])
def document_upload(request):
    try:
        member = _context(request)
        project = _project(member, request.POST.get('projectId'))
        attachment = request.FILES.get('file')
        if not attachment or not attachment.name:
            raise ValueError('Choose a file to upload')
        if not 0 < attachment.size <= 8_000_000:
            raise ValueError('File size must be between 1 byte and 8 MB')
        extension = Path(attachment.name).suffix.lower()
        if extension not in FILE_EXTENSIONS:
            raise ValueError('Unsupported file extension')
        title = _short(request.POST.get('title') or Path(attachment.name).name, 220, 'Document name')
        client_visible = True if member.role == 'client' else request.POST.get('clientVisible', 'true').lower() == 'true'
        doc = ProjectDocument.objects.create(project=project, uploaded_by=member, title=title,
            attachment=attachment, size_bytes=attachment.size, client_visible=client_visible)
        _log(member, 'Uploaded project document', doc, project.client, title)
        return JsonResponse({'ok': True, 'id': str(doc.id)})
    except PermissionError as exc:
        return JsonResponse({'error': str(exc)}, status=403)
    except (ValueError, TypeError, ValidationError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)


@require_http_methods(['GET'])
def document_download(request, document_id):
    try:
        member = _context(request)
    except PermissionError as exc:
        return HttpResponse(str(exc), status=401)
    doc = ProjectDocument.objects.filter(pk=document_id, project__client_id__in=_client_ids_for(member)).first()
    if not doc or (member.role == 'client' and not doc.client_visible):
        return HttpResponse('Document not found', status=404)
    try:
        stream = doc.attachment.open('rb')
    except (OSError, FileNotFoundError):
        return HttpResponse('Document storage unavailable', status=404)
    response = FileResponse(stream, as_attachment=True, filename=doc.title)
    response['Cache-Control'] = 'private, no-store'
    return response


@require_http_methods(['GET'])
def export_project_csv(request, kind):
    try:
        member = _context(request)
    except PermissionError as exc:
        return JsonResponse({'error': str(exc)}, status=401)
    if kind not in {'tasks', 'projects', 'issues'}:
        return JsonResponse({'error': 'Unknown export'}, status=404)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="techfinitys_{kind}.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)

    def safe(value):
        value = str(value if value is not None else '')
        return "'" + value if value.startswith(('=', '+', '-', '@', '\t', '\r')) else value

    if kind == 'tasks':
        qs = Task.objects.filter(client_id__in=_client_ids_for(member))
        if member.role == 'client':
            qs = qs.filter(client_visible=True)
        if request.GET.get('project'):
            qs = qs.filter(project_id=request.GET['project'])
        if request.GET.get('status'):
            qs = qs.filter(status=request.GET['status'])
        qs = qs.select_related('project', 'client', 'assigned_to__user').order_by('due_at')
        writer.writerow(['Task', 'Project', 'Client', 'Owner', 'Status', 'Priority', 'Completion', 'Due', 'Billable'])
        for t in qs.iterator(chunk_size=500):
            writer.writerow([safe(t.title), safe(t.project.title if t.project else ''),safe(t.client.name),
                safe(_name(t.assigned_to) if t.assigned_to else ''),t.status,t.priority,
                t.percent_complete,t.due_at or '',t.billing_type])
    elif kind == 'projects':
        writer.writerow(['Project', 'Client', 'Group', 'Status', 'Progress', 'Start', 'End'])
        for p in Project.objects.filter(client_id__in=_client_ids_for(member)).select_related('client').iterator(chunk_size=500):
            writer.writerow([safe(p.title),safe(p.client.name),safe(p.group_name),p.status,p.progress,
                             p.start_date or '',p.due_date or ''])
    else:
        qs = ProjectIssue.objects.filter(client_id__in=_client_ids_for(member))
        if member.role == 'client':
            qs = qs.filter(client_visible=True).exclude(task__client_visible=False)
        writer.writerow(['Issue', 'Project', 'Priority', 'Status', 'Reported at'])
        for x in qs.select_related('project').iterator(chunk_size=500):
            writer.writerow([safe(x.title),safe(x.project.title),x.priority,x.status,x.created_at])
    return response
