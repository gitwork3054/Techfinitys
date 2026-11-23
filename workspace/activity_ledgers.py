"""Paginated Super Admin employee ledgers.

These read-only records are available ONLY through the authenticated, admin-only
activity endpoint. Private chat content, passwords, tokens and medical data are
never copied into the attendance ledger.
"""
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import Attendance, LeaveRequest, TimeEntry

STAFF_ROLES = ('employee', 'manager')
PAGE_SIZE = 50


def _person(member):
    if not member:
        return '—'
    return member.user.get_full_name() or member.user.username


def _iso(value):
    return value.isoformat() if value else None


def employee_ledger(request, overview):
    params = request.GET
    kind = params.get('ledger', '').strip().lower()
    if kind not in ('attendance', 'leaves', 'timesheets'):
        return JsonResponse({'error': 'Invalid employee register'}, status=400)

    raw_page = params.get('page', '1').strip()
    if not raw_page.isascii() or not raw_page.isdecimal() or not (1 <= int(raw_page) <= 10000):
        return JsonResponse({'error': 'Invalid register page'}, status=400)
    page = int(raw_page)

    status = (params.get('status') or 'all').strip().lower()
    allowed_status = {
        'attendance': ('all', 'working', 'on_break', 'clocked_out'),
        'leaves': ('all', 'pending', 'approved', 'rejected', 'cancelled'),
        'timesheets': ('all', 'draft', 'submitted', 'approved', 'rejected'),
    }
    if status not in allowed_status[kind]:
        return JsonResponse({'error': 'Invalid record status'}, status=400)

    raw_employee = params.get('employeeId', '').strip()
    if raw_employee and (len(raw_employee) > 20 or not raw_employee.isascii() or not raw_employee.isdecimal()):
        return JsonResponse({'error': 'Invalid employee filter'}, status=400)

    period = {}
    for key in ('from', 'to'):
        raw = (params.get(key) or '').strip()
        if raw:
            parsed = parse_date(raw)
            if not parsed or parsed.isoformat() != raw:
                return JsonResponse({'error': f'Invalid {key} date'}, status=400)
            period[key] = parsed
    if period.get('from') and period.get('to') and period['from'] > period['to']:
        return JsonResponse({'error': 'From date must not be after To date'}, status=400)

    term = (params.get('q') or '').strip()[:100]
    if kind == 'attendance':
        records = (Attendance.objects.filter(employee__role__in=STAFF_ROLES)
                   .select_related('employee__user')
                   .order_by('-date', '-clock_in', '-pk'))
    elif kind == 'leaves':
        records = (LeaveRequest.objects.filter(employee__role__in=STAFF_ROLES)
                   .select_related('employee__user', 'reviewed_by__user')
                   .order_by('-created_at', '-pk'))
    else:
        records = (TimeEntry.objects.filter(employee__role__in=STAFF_ROLES)
                   .select_related('employee__user', 'client', 'project', 'task', 'reviewed_by__user')
                   .order_by('-date', '-created_at', '-pk'))

    if status != 'all':
        if kind == 'attendance':
            if status == 'clocked_out':
                records = records.filter(clock_out__isnull=False)
            elif status == 'on_break':
                records = records.filter(clock_out__isnull=True, break_started_at__isnull=False)
            else:
                records = records.filter(clock_out__isnull=True, break_started_at__isnull=True)
        else:
            records = records.filter(status=status)

    if raw_employee:
        records = records.filter(employee_id=int(raw_employee))

    if kind == 'leaves':
        # Include leave periods overlapping the requested date range.
        if period.get('from'):
            records = records.filter(end_date__gte=period['from'])
        if period.get('to'):
            records = records.filter(start_date__lte=period['to'])
    else:
        if period.get('from'):
            records = records.filter(date__gte=period['from'])
        if period.get('to'):
            records = records.filter(date__lte=period['to'])

    if term:
        name_search = (Q(employee__user__username__icontains=term)
                       | Q(employee__user__first_name__icontains=term)
                       | Q(employee__user__last_name__icontains=term))
        if kind == 'attendance':
            records = records.filter(name_search | Q(mode__icontains=term) | Q(note__icontains=term))
        elif kind == 'leaves':
            records = records.filter(name_search | Q(leave_type__icontains=term) | Q(status__icontains=term))
        else:
            records = records.filter(name_search | Q(status__icontains=term)
                                     | Q(client__name__icontains=term)
                                     | Q(project__title__icontains=term)
                                     | Q(task__title__icontains=term)
                                     | Q(description__icontains=term))

    start = (page - 1) * PAGE_SIZE
    found = list(records[start:start + PAGE_SIZE + 1])
    has_more = len(found) > PAGE_SIZE
    items = found[:PAGE_SIZE]
    rows = []

    if kind == 'attendance':
        now = timezone.now()
        for a in items:
            running_break = max(0, int((now - a.break_started_at).total_seconds())) if a.break_started_at else 0
            rows.append({
                'id': a.pk, 'employeeId': a.employee_id, 'employee': _person(a.employee),
                'date': a.date.isoformat(), 'clockIn': _iso(a.clock_in), 'clockOut': _iso(a.clock_out),
                'breakStartedAt': _iso(a.break_started_at),
                'breakMinutes': round((a.break_seconds + running_break) / 60, 1),
                'workedMinutes': round(a.worked_seconds / 60, 1),
                'mode': a.get_mode_display(), 'note': a.note,
                'status': 'On break' if a.break_started_at else ('Clocked out' if a.clock_out else 'Working'),
            })
    elif kind == 'leaves':
        for l in items:
            rows.append({
                'id': str(l.pk), 'employeeId': l.employee_id, 'employee': _person(l.employee),
                'type': l.get_leave_type_display(),
                'startDate': l.start_date.isoformat(), 'endDate': l.end_date.isoformat(),
                'days': (l.end_date - l.start_date).days + 1,
                'status': l.status, 'reason': l.reason[:1200],
                'submittedAt': _iso(l.created_at), 'reviewedAt': _iso(l.reviewed_at),
                'reviewedBy': _person(l.reviewed_by) if l.reviewed_by else '',
                'reviewNote': l.review_note[:1200],
            })
    else:
        for t in items:
            rows.append({
                'id': str(t.pk), 'employeeId': t.employee_id, 'employee': _person(t.employee),
                'date': t.date.isoformat(), 'minutes': t.minutes, 'status': t.status,
                'billable': t.billable,
                'client': t.client.name, 'project': t.project.title if t.project else '',
                'task': t.task.title if t.task else '', 'description': t.description,
                'submittedAt': _iso(t.created_at), 'reviewedAt': _iso(t.reviewed_at),
                'reviewedBy': _person(t.reviewed_by) if t.reviewed_by else '',
            })

    response = JsonResponse({
        'summary': overview, 'ledger': kind, 'rows': rows,
        'page': page, 'hasMore': has_more,
    })
    response['Cache-Control'] = 'private, no-store'
    return response
