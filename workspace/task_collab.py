"""Scoped task-detail conversation, checklist, dependency and duplication endpoints.

No data is changed without authenticated membership/role and tenant verification.
Task detail reads are per task, so the initial dashboard stays small.
"""
import json
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Task, Member, Notification, ActivityLog, TaskComment, TaskChecklistItem
from .views import _context, _log
from .projects_plus import _task, _can_edit_task, _recalculate_project, MANAGERS


def _serialize_comment(row):
    return {
        'id': str(row.pk), 'body': row.body, 'isInternal': row.is_internal,
        'author': row.author.user.get_full_name() or row.author.user.username if row.author else 'Former member',
        'authorId': row.author_id, 'createdAt': row.created_at.isoformat(),
    }


def _serialize_check(row):
    return {'id': str(row.pk), 'title': row.title, 'done': row.done, 'position': row.position}


def _text(value, limit, field):
    if not isinstance(value, str):
        raise ValueError(f'{field} must be text')
    cleaned = value.strip()
    if not cleaned or len(cleaned) > limit:
        raise ValueError(f'{field} must be 1–{limit} characters')
    return cleaned


def _check_access(member, task):
    # An employee may discuss tasks for a client they are assigned to, as in
    # the existing project feed. They must be assigned to modify checklist state.
    _can_edit_task(member, task)
    if member.role == 'employee' and task.assigned_to_id != member.pk and not task.assignees.filter(pk=member.pk).exists():
        raise PermissionError('Only assigned employees can edit this checklist')


def _notify_comment(task, member, body, internal):
    # Keep private commentary out of client notifications.
    ids = set(task.assignees.values_list('id', flat=True))
    if task.assigned_to_id:
        ids.add(task.assigned_to_id)
    if task.project:
        ids.update(i for i in (task.project.owner_id, task.project.manager_id) if i)
    if not internal and task.client_visible:
        ids.update(Member.objects.filter(role='client', client_account=task.client, is_active=True).values_list('id', flat=True))
    ids.discard(member.pk)
    recipients = Member.objects.filter(pk__in=ids, is_active=True)
    Notification.objects.bulk_create([
        Notification(recipient=r, client=task.client, title=f'Task comment: {task.title}'[:220], body=body[:260])
        for r in recipients
    ])


@require_http_methods(['GET', 'POST'])
def task_detail_api(request, task_id):
    try:
        member = _context(request)
        task = _task(member, task_id)
        if request.method == 'GET':
            comments = TaskComment.objects.filter(task=task).select_related('author__user')
            if member.role == 'client':
                comments = comments.filter(is_internal=False)
            checklist = TaskChecklistItem.objects.filter(task=task)
            activity = (ActivityLog.objects.none() if member.role == 'client' else
                ActivityLog.objects.filter(entity_type='Task', entity_id=str(task.pk)).select_related('actor__user').order_by('-created_at')[:35])
            return JsonResponse({
                'id': str(task.pk), 'comments': [_serialize_comment(c) for c in comments.order_by('created_at')[:250]],
                'checklist': [_serialize_check(c) for c in checklist[:100]],
                'dependency': str(task.blocked_by_id) if task.blocked_by_id else '',
                'activity': [{'id': r.pk, 'action': r.action, 'detail': r.detail,
                              'author': r.actor.user.get_full_name() or r.actor.user.username if r.actor else 'System',
                              'createdAt': r.created_at.isoformat()} for r in activity],
            })
        payload = json.loads(request.body or b'{}')
        if not isinstance(payload, dict):
            raise ValueError('JSON object required')
        action = payload.get('action')
        with transaction.atomic():
            if action == 'add_comment':
                body = _text(payload.get('body'), 4000, 'Comment')
                internal = bool(payload.get('isInternal', False))
                if member.role == 'client' and internal:
                    raise PermissionError('Clients cannot create internal comments')
                row = TaskComment.objects.create(task=task, client=task.client, author=member, body=body, is_internal=internal)
                _log(member, 'Commented on task', task, task.client, f'{task.title} · {"Internal" if internal else "Shared"} comment')
                _notify_comment(task, member, body, internal)
                return JsonResponse({'ok': True, 'id': str(row.pk)}, status=201)
            if action == 'add_check':
                _check_access(member, task)
                title = _text(payload.get('title'), 240, 'Checklist item')
                if TaskChecklistItem.objects.filter(task=task).count() >= 100:
                    raise ValueError('Checklist limit reached (100)')
                item = TaskChecklistItem.objects.create(task=task, title=title, created_by=member,
                    position=TaskChecklistItem.objects.filter(task=task).count())
                _log(member, 'Added task checklist item', task, task.client, title)
                return JsonResponse({'ok': True, 'id': str(item.pk)}, status=201)
            if action in ('toggle_check', 'delete_check'):
                _check_access(member, task)
                try:
                    item = TaskChecklistItem.objects.select_for_update().get(pk=payload.get('checkId'), task=task)
                except (ValueError, TypeError, ValidationError, TaskChecklistItem.DoesNotExist):
                    raise ValueError('Checklist item was not found')
                if action == 'toggle_check':
                    item.done = not item.done
                    item.save(update_fields=['done', 'updated_at'])
                    _log(member, 'Updated task checklist', task, task.client, f'{item.title}: {"Done" if item.done else "Open"}')
                else:
                    if member.role not in MANAGERS:
                        raise PermissionError('Only managers can delete checklist items')
                    title = item.title
                    item.delete()
                    _log(member, 'Deleted task checklist item', task, task.client, title)
                return JsonResponse({'ok': True})
            if action == 'set_dependency':
                if member.role not in MANAGERS:
                    raise PermissionError('Only managers can plan dependencies')
                blocked_by_id = payload.get('blockedBy') or None
                blocker = None
                if blocked_by_id:
                    blocker = _task(member, blocked_by_id)
                    if blocker.client_id != task.client_id or blocker.project_id != task.project_id or not task.project_id:
                        raise ValueError('Dependencies must be in the same project')
                    cursor = blocker
                    for _ in range(100):
                        if cursor.pk == task.pk:
                            raise ValueError('Circular task dependency')
                        if not cursor.blocked_by_id:
                            break
                        cursor = Task.objects.filter(pk=cursor.blocked_by_id, client=task.client).first()
                        if cursor is None:
                            break
                    else:
                        raise ValueError('Dependency chain is too deep')
                task.blocked_by = blocker
                task.save(update_fields=['blocked_by','updated_at'])
                _log(member, 'Updated task dependency', task, task.client, blocker.title if blocker else 'Dependency removed')
                return JsonResponse({'ok': True})
            if action == 'duplicate':
                if member.role not in MANAGERS:
                    raise PermissionError('Only managers can duplicate tasks')
                clone = Task.objects.create(
                    client=task.client, project=task.project, task_list=task.task_list,
                    title=('Copy of ' + task.title)[:220], description=task.description,
                    priority=task.priority, status='todo', created_by=member,
                    assigned_to=task.assigned_to, estimated_hours=task.estimated_hours,
                    billing_type=task.billing_type, tags=list(task.tags or []),
                    client_visible=False,
                )
                clone.assignees.set(task.assignees.all())
                _recalculate_project(task.project_id)
                _log(member, 'Duplicated task', clone, task.client, f'Duplicated from {task.title}')
                return JsonResponse({'ok': True, 'id': str(clone.pk)}, status=201)
            raise ValueError('Unsupported task detail action')
    except PermissionError as e:
        return JsonResponse({'error': str(e)}, status=403)
    except (ValueError, TypeError, ValidationError) as e:
        return JsonResponse({'error': str(e)}, status=400)
