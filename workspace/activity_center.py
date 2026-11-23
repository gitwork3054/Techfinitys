"""Super Admin audit inbox.

The immutable ActivityLog remains the source of truth. This API only reads it and
routes approvals through the existing, permission-checked operations endpoints.
Never expose this company-wide feed to clients, employees or office managers.
"""
import json
from datetime import datetime, time

from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from .models import ActivityLog, Attendance, LeaveRequest, TimeEntry, ApprovalRequest, Member, Notification
from .views import _context

STAFF_ROLES = ('employee', 'manager')
SECTIONS = {
    'attendance': ('clock', 'break', 'attendance', 'shift', 'resumed work'),
    'leave': ('leave',),
    'tasks': ('task', 'project', 'milestone', 'issue', 'update', 'note', 'document', 'deliverable'),
    'time': ('time', 'timesheet', 'hours'),
    'approvals': ('approval',),
    'clients': ('client', 'ticket', 'support'),
    'billing': ('invoice', 'payment', 'billing'),
    'people': ('employee', 'member', 'assignment', 'lead', 'profile', 'team', 'password'),
    'access': ('signed in', 'signed out', 'login', 'logout', 'sign-in', 'sign-out'),
    'chat': ('chat', 'conversation', 'message'),
}


def category_of(action):
    key = (action or '').lower()
    for category, words in SECTIONS.items():
        if any(word in key for word in words):
            return category
    return 'other'


def _category_query(name):
    combined = Q()
    for term in SECTIONS.get(name, ()):
        combined |= Q(action__icontains=term)
    if name == 'other':
        known = Q()
        for category in SECTIONS:
            known |= _category_query(category)
        return ~known
    return combined


def _employee_name(member):
    return member.user.get_full_name() or member.user.username


def _view(request, member):
    data = request.GET
    summary = data.get('summary') == '1'
    events = ActivityLog.objects.filter(actor__role__in=STAFF_ROLES).select_related('actor__user', 'client')
    unread = Notification.objects.filter(recipient=member, link='#admin_activity', read_at__isnull=True).count()
    local_today = timezone.localdate()
    day_start = timezone.make_aware(datetime.combine(local_today, time.min), timezone.get_current_timezone())
    overview = {
        'unread': unread,
        'pendingLeaves': LeaveRequest.objects.filter(status='pending', employee__role__in=STAFF_ROLES).count(),
        'pendingTimesheets': TimeEntry.objects.filter(status='submitted', employee__role__in=STAFF_ROLES).count(),
        'pendingApprovals': ApprovalRequest.objects.filter(status='pending', audience='internal').count(),
        'onShift': Attendance.objects.filter(clock_out__isnull=True, employee__is_active=True, employee__role__in=STAFF_ROLES).count(),
        'onBreak': Attendance.objects.filter(clock_out__isnull=True, break_started_at__isnull=False, employee__role__in=STAFF_ROLES).count(),
        'clockedInToday': Attendance.objects.filter(date=local_today, employee__role__in=STAFF_ROLES).count(),
        'todayActions': events.filter(created_at__gte=day_start).count(),
    }
    if summary:
        return JsonResponse({'summary': overview})
    if data.get('ledger'):
        from .activity_ledgers import employee_ledger
        return employee_ledger(request, overview)

    # Always scope event searches server-side; pagination prevents huge audit payloads.
    term = (data.get('q') or '').strip()[:100]
    if term:
        events = events.filter(Q(action__icontains=term) | Q(detail__icontains=term)
                               | Q(actor__user__username__icontains=term)
                               | Q(actor__user__first_name__icontains=term)
                               | Q(actor__user__last_name__icontains=term)
                               | Q(client__name__icontains=term))
    employee_id = data.get('employeeId', '').strip()
    if employee_id:
        if len(employee_id) > 20 or not employee_id.isascii() or not employee_id.isdecimal():
            return JsonResponse({'error': 'Invalid employee filter'}, status=400)
        events = events.filter(actor_id=int(employee_id))
    category = (data.get('category') or 'all').lower()
    if category != 'all':
        if category not in (*SECTIONS.keys(), 'other'):
            return JsonResponse({'error': 'Invalid activity category'}, status=400)
        events = events.filter(_category_query(category))
    for key, op in [('from', 'gte'), ('to', 'lte')]:
        raw = (data.get(key) or '').strip()
        if raw:
            parsed = parse_date(raw)
            if not parsed or parsed.isoformat() != raw:
                return JsonResponse({'error': f'Invalid {key} date'}, status=400)
            events = events.filter(**{f'created_at__date__{op}': parsed})
    before = (data.get('before') or '').strip()
    if before:
        if len(before) > 20 or not before.isascii() or not before.isdecimal():
            return JsonResponse({'error': 'Invalid pagination cursor'}, status=400)
        events = events.filter(pk__lt=int(before))
    results = list(events.order_by('-id')[:51])
    more = len(results) > 50
    rows = results[:50]
    staff = Member.objects.filter(role__in=STAFF_ROLES).select_related('user').order_by('user__first_name', 'user__username')[:400]
    leaves = LeaveRequest.objects.filter(status='pending', employee__role__in=STAFF_ROLES).select_related('employee__user').order_by('created_at')[:60]
    times = TimeEntry.objects.filter(status='submitted', employee__role__in=STAFF_ROLES).select_related('employee__user', 'client', 'project').order_by('created_at')[:60]
    approvals = ApprovalRequest.objects.filter(status='pending', audience='internal').select_related('requested_by__user', 'client').order_by('created_at')[:60]
    return JsonResponse({
        'summary': overview,
        'events': [{
            'id':a.pk, 'action':a.action, 'category':category_of(a.action),
            'employeeId':a.actor_id, 'employee':_employee_name(a.actor),
            'role':a.actor.role, 'client':a.client.name if a.client else '',
            'detail':a.detail[:1600], 'entityType':a.entity_type,
            'entityId':a.entity_id, 'at':a.created_at.isoformat(),
        } for a in rows],
        'nextBefore': rows[-1].pk if more and rows else None,
        'employees':[{'id':p.pk, 'name':_employee_name(p)} for p in staff],
        'leaves':[{'id':str(l.pk), 'employeeId':l.employee_id, 'employee':_employee_name(l.employee),
                   'type':l.get_leave_type_display(), 'startDate':l.start_date.isoformat(),
                   'endDate':l.end_date.isoformat(), 'reason':l.reason[:1200],
                   'submittedAt':l.created_at.isoformat()} for l in leaves],
        'timesheets':[{'id':str(t.pk), 'employeeId':t.employee_id, 'employee':_employee_name(t.employee),
                       'client':t.client.name, 'project':t.project.title if t.project else '',
                       'minutes':t.minutes, 'date':t.date.isoformat(), 'description':t.description[:300]} for t in times],
        'approvals':[{'id':str(a.pk), 'requestedBy':_employee_name(a.requested_by) if a.requested_by else 'System',
                      'title':a.title, 'client':a.client.name, 'description':a.description[:400]} for a in approvals],
    })


@require_http_methods(['GET', 'POST'])
def admin_activity_api(request):
    try:
        member = _context(request)
    except PermissionError as exc:
        return JsonResponse({'error': str(exc)}, status=401)
    if member.role != 'admin':
        return JsonResponse({'error': 'Super Admin access required'}, status=403)
    if request.method == 'GET':
        result = _view(request, member)
        result['Cache-Control'] = 'private, no-store'
        return result
    try:
        payload = json.loads(request.body or b'{}')
        if not isinstance(payload, dict) or payload.get('action') != 'mark_seen':
            return JsonResponse({'error':'Unsupported activity action'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'error':'Invalid JSON'}, status=400)
    updated = Notification.objects.filter(recipient=member, link='#admin_activity', read_at__isnull=True).update(read_at=timezone.now())
    return JsonResponse({'ok':True, 'updated':updated})
