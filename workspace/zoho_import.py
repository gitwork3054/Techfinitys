"""Read-only Zoho Projects V3 import, with OAuth consent and duplicate-safe selection."""
import json
import os
import re
import secrets
import time
from datetime import date
from urllib.parse import urlencode

import requests
from django.db import transaction, IntegrityError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST

from .models import ClientAccount, Member, Project, ZohoProjectLink
from .views import _context, _log

REGIONS = {
    'in': ('https://accounts.zoho.in', 'https://projects.zoho.in'),
    'com': ('https://accounts.zoho.com', 'https://projects.zoho.com'),
    'eu': ('https://accounts.zoho.eu', 'https://projects.zoho.eu'),
    'com.au': ('https://accounts.zoho.com.au', 'https://projects.zoho.com.au'),
}
SCOPES = 'ZohoProjects.portals.READ,ZohoProjects.projects.READ'
MAX_PROJECTS = 500


class ZohoImportError(Exception):
    pass


def _admin(request):
    member = _context(request)
    if member.role not in ('admin', 'manager'):
        raise PermissionError('Only Admin and Managers can import Zoho projects')
    return member


def _redirect_uri(request):
    # Fixed hostname, no untrusted Host header reflected into OAuth redirect.
    return os.getenv('ZOHO_PROJECTS_REDIRECT_URI', 'https://techfinitys-crm-8wp1.onrender.com/api/zoho/callback/')


def _config(region):
    if region not in REGIONS:
        raise ZohoImportError('Select a supported Zoho data centre')
    client_id = os.environ.get('ZOHO_PROJECTS_CLIENT_ID', '').strip()
    client_secret = os.environ.get('ZOHO_PROJECTS_CLIENT_SECRET', '').strip()
    if not client_id or not client_secret:
        raise ZohoImportError('Zoho integration needs OAuth client ID and secret configured on Render')
    return client_id, client_secret


def _token_request(region, params):
    accounts = REGIONS[region][0]
    try:
        response = requests.post(accounts + '/oauth/v2/token', data=params, timeout=12)
        result = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ZohoImportError('Zoho authorization service is unavailable') from exc
    if not response.ok or not result.get('access_token'):
        raise ZohoImportError('Zoho authorization failed. Reconnect your account.')
    return result


def _access_token(request):
    connection = request.session.get('zoho_projects_connection') or {}
    if not connection or connection.get('owner') != request.user.pk:
        raise ZohoImportError('Connect Zoho Projects first')
    region = connection.get('region')
    if region not in REGIONS:
        raise ZohoImportError('Invalid Zoho region')
    if connection.get('expires_at', 0) > time.time() + 90:
        return region, connection['access_token']
    refresh = connection.get('refresh_token')
    if not refresh:
        raise ZohoImportError('Zoho session expired. Reconnect.')
    client_id, client_secret = _config(region)
    data = _token_request(region, {
        'client_id': client_id, 'client_secret': client_secret,
        'grant_type': 'refresh_token', 'refresh_token': refresh,
    })
    connection.update(access_token=data['access_token'], expires_at=time.time() + int(data.get('expires_in', 3600)))
    request.session['zoho_projects_connection'] = connection
    request.session.modified = True
    return region, connection['access_token']


def _api_get(request, endpoint, params=None):
    region, token = _access_token(request)
    try:
        response = requests.get(REGIONS[region][1] + endpoint, params=params,
                                headers={'Authorization': 'Bearer ' + token}, timeout=16)
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ZohoImportError('Unable to retrieve projects from Zoho') from exc
    if not response.ok:
        raise ZohoImportError('Zoho could not load the requested projects. Check your portal permissions.')
    return data


def _portal_id(text):
    value = str(text or '')
    if not re.fullmatch(r'[0-9]{1,32}', value):
        raise ZohoImportError('Invalid Zoho portal')
    return value


def _date(value):
    if not value:
        return None
    if isinstance(value, dict):
        value = value.get('date') or value.get('value')
    return parse_date(str(value)[:10])


def _name(value):
    return str(value or '').strip()[:180]


def _project_row(obj):
    status = obj.get('status') or ''
    if isinstance(status, dict):
        status = status.get('name') or status.get('type') or ''
    status = str(status).lower().strip()
    completed = any(term in status for term in ('closed', 'completed', 'finished')) or str(obj.get('is_completed', '')).lower() == 'true'
    hold = any(term in status for term in ('hold', 'paused'))
    state = 'completed' if completed else 'on_hold' if hold else 'active'
    description = obj.get('description') or ''
    if isinstance(description, dict):
        description = description.get('text') or ''
    name = _name(obj.get('name') or obj.get('project_name') or obj.get('title'))
    pid = str(obj.get('id') or '')
    if not re.fullmatch(r'[0-9]{1,64}', pid) or not name:
        return None
    try:
        progress = max(0, min(100, int(float(obj.get('percent_complete') or 0))))
    except (ValueError, TypeError):
        progress = 0
    return {
        'id': pid, 'name': name, 'description': str(description)[:10000],
        'status': state, 'progress': progress,
        'start_date': _date(obj.get('start_date')),
        'due_date': _date(obj.get('end_date') or obj.get('due_date')),
    }


def _json_error(exc):
    if isinstance(exc, PermissionError):
        return JsonResponse({'error': str(exc)}, status=403)
    if isinstance(exc, ZohoImportError):
        return JsonResponse({'error': str(exc)}, status=400)
    return JsonResponse({'error': 'Could not complete the Zoho import'}, status=400)


@require_GET
def status(request):
    try:
        member = _admin(request)
        conn = request.session.get('zoho_projects_connection') or {}
        connected = conn.get('owner') == request.user.pk and bool(conn.get('refresh_token') or conn.get('access_token'))
        return JsonResponse({
            'connected': connected,
            'configured': bool(os.getenv('ZOHO_PROJECTS_CLIENT_ID') and os.getenv('ZOHO_PROJECTS_CLIENT_SECRET')),
            'region': conn.get('region') if connected else None,
            'clients': list(ClientAccount.objects.values('id', 'name'))[:500],
        })
    except (PermissionError, ZohoImportError) as exc:
        return _json_error(exc)


@require_GET
def connect(request):
    try:
        _admin(request)
        region = request.GET.get('region', 'in')
        client_id, _ = _config(region)
        state = secrets.token_urlsafe(30)
        request.session['zoho_oauth_pending'] = {
            'state': state, 'region': region, 'owner': request.user.pk, 'created': time.time()
        }
        uri = REGIONS[region][0] + '/oauth/v2/auth?' + urlencode({
            'response_type': 'code', 'client_id': client_id,
            'redirect_uri': _redirect_uri(request), 'scope': SCOPES,
            'access_type': 'offline', 'prompt': 'consent', 'state': state,
        })
        return redirect(uri)
    except (PermissionError, ZohoImportError) as exc:
        return _json_error(exc)


@require_GET
def callback(request):
    try:
        _admin(request)
        pending = request.session.pop('zoho_oauth_pending', None) or {}
        if (not pending or pending.get('owner') != request.user.pk or
            time.time() - pending.get('created', 0) > 600 or
            not secrets.compare_digest(str(pending.get('state', '')), request.GET.get('state', ''))):
            raise ZohoImportError('Zoho connection expired. Please try again.')
        if request.GET.get('error') or not request.GET.get('code'):
            raise ZohoImportError('Zoho connection was cancelled.')
        region = pending['region']
        client_id, client_secret = _config(region)
        token = _token_request(region, {
            'code': request.GET['code'], 'grant_type': 'authorization_code',
            'client_id': client_id, 'client_secret': client_secret,
            'redirect_uri': _redirect_uri(request),
        })
        previous = request.session.get('zoho_projects_connection') or {}
        refresh = token.get('refresh_token') or previous.get('refresh_token')
        if not refresh:
            raise ZohoImportError('Zoho did not issue an offline token. Reconnect with consent.')
        request.session['zoho_projects_connection'] = {
            'owner': request.user.pk, 'region': region,
            'refresh_token': refresh, 'access_token': token['access_token'],
            'expires_at': time.time() + int(token.get('expires_in', 3600)),
        }
        request.session.pop('zoho_projects_preview', None)
        return redirect('/#projects')
    except (PermissionError, ZohoImportError) as exc:
        request.session['zoho_projects_error'] = str(exc)
        return redirect('/#projects')


@require_GET
def portals(request):
    try:
        _admin(request)
        data = _api_get(request, '/api/v3/portals')
        rows = data.get('portals', data) if isinstance(data, (dict, list)) else []
        if not isinstance(rows, list):
            rows = []
        return JsonResponse({'portals': [
            {'id': str(row.get('id')), 'name': str(row.get('name') or row.get('portal_name') or row.get('id'))}
            for row in rows if isinstance(row, dict) and re.fullmatch(r'[0-9]{1,32}', str(row.get('id', '')))
        ]})
    except (PermissionError, ZohoImportError) as exc:
        return _json_error(exc)


@require_GET
def preview(request):
    try:
        _admin(request)
        portal_id = _portal_id(request.GET.get('portal_id'))
        # Only a bounded number of pages is fetched to protect server time.
        raw = []
        for page in range(1, 6):
            data = _api_get(request, f'/api/v3/portal/{portal_id}/projects', {'page': page, 'per_page': 100})
            batch = data.get('projects', []) if isinstance(data, dict) else []
            if not isinstance(batch, list):
                break
            raw.extend(batch)
            if len(batch) < 100 or not (data.get('page_info') or {}).get('has_next_page', False):
                break
        rows = [row for x in raw if isinstance(x, dict) if (row := _project_row(x))]
        rows = rows[:MAX_PROJECTS]
        source_ids = [x['id'] for x in rows]
        existing = set(ZohoProjectLink.objects.filter(
            portal_id=portal_id, zoho_project_id__in=source_ids
        ).values_list('zoho_project_id', flat=True))
        request.session['zoho_projects_preview'] = {'portal_id': portal_id, 'ids': source_ids}
        return JsonResponse({'projects': [
            {**row, 'start_date': row['start_date'].isoformat() if row['start_date'] else '',
             'due_date': row['due_date'].isoformat() if row['due_date'] else '',
             'imported': row['id'] in existing}
            for row in rows
        ], 'limitReached': len(rows) == MAX_PROJECTS})
    except (PermissionError, ZohoImportError) as exc:
        return _json_error(exc)


@require_POST
def import_projects(request):
    try:
        member = _admin(request)
        payload = json.loads(request.body or '{}')
        if not isinstance(payload, dict):
            raise ZohoImportError('Invalid import request')
        client_id = str(payload.get('client_id') or '')
        client = ClientAccount.objects.filter(pk=client_id).first() if client_id else None
        if not client:
            raise ZohoImportError('Select a destination client first')
        portal_id = _portal_id(payload.get('portal_id'))
        preview_data = request.session.get('zoho_projects_preview') or {}
        if preview_data.get('portal_id') != portal_id:
            raise ZohoImportError('Preview the Zoho portal before importing')
        ids = payload.get('project_ids')
        if not isinstance(ids, list) or not ids or len(ids) > 100:
            raise ZohoImportError('Select between 1 and 100 projects per import')
        allowed = set(preview_data.get('ids', []))
        selected = list(dict.fromkeys(str(x) for x in ids))
        if not set(selected) <= allowed:
            raise ZohoImportError('Selected projects must come from your preview')
        created, skipped = [], 0
        # Fetch authoritative source metadata just before import.
        for zoho_id in selected:
            data = _api_get(request, f'/api/v3/portal/{portal_id}/projects/{zoho_id}')
            source = data.get('project', data) if isinstance(data, dict) else {}
            if isinstance(source, list):
                source = source[0] if source else {}
            item = _project_row(source) if isinstance(source, dict) else None
            if not item or item['id'] != zoho_id:
                raise ZohoImportError('Unable to verify a selected Zoho project')
            with transaction.atomic():
                if ZohoProjectLink.objects.filter(portal_id=portal_id, zoho_project_id=zoho_id).exists():
                    skipped += 1
                    continue
                project = Project.objects.create(
                    client=client, title=item['name'],
                    description=item['description'], status=item['status'],
                    progress=item['progress'],
                    start_date=item['start_date'], due_date=item['due_date'],
                    group_name='Imported from Zoho', created_by=member,
                )
                try:
                    ZohoProjectLink.objects.create(
                        portal_id=portal_id, zoho_project_id=zoho_id,
                        project=project, imported_by=member,
                    )
                except IntegrityError:
                    # Protect against concurrent imports of the same source.
                    project.delete()
                    skipped += 1
                    continue
                _log(member, 'Imported project from Zoho', project, client, item['name'])
                created.append({'id': str(project.pk), 'name': project.title})
        return JsonResponse({'ok': True, 'created': created, 'skipped': skipped})
    except (PermissionError, ZohoImportError, ValueError, TypeError) as exc:
        return _json_error(exc)


@require_POST
def disconnect(request):
    try:
        _admin(request)
        request.session.pop('zoho_projects_connection', None)
        request.session.pop('zoho_projects_preview', None)
        return JsonResponse({'ok': True})
    except (PermissionError, ZohoImportError) as exc:
        return _json_error(exc)
