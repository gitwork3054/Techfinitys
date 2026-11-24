"""Opt-in Web Push: desktop notifications even when the CRM tab is closed.

Subscriptions are per logged-in user and stored in the CRM database. Only
known browser push provider domains are accepted to prevent endpoint SSRF.
"""
import json
import logging
import os
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Member, Notification, PushSubscription

logger = logging.getLogger(__name__)

PUSH_DOMAINS = (
    'fcm.googleapis.com', 'updates.push.services.mozilla.com',
    'push.services.mozilla.com', 'web.push.apple.com',
    'notify.windows.com',
)


def _safe_endpoint(value):
    if not isinstance(value, str) or len(value) > 2048:
        return False
    parts = urlsplit(value)
    host = (parts.hostname or '').lower()
    if parts.scheme != 'https' or parts.username or parts.password or parts.port not in (None, 443):
        return False
    return bool(host and any(host == domain or host.endswith('.' + domain) for domain in PUSH_DOMAINS))


def _member(request):
    return Member.objects.filter(user=request.user, is_active=True, user__is_active=True).first()


@require_GET
def service_worker(request):
    # Root path gives this worker scope over all CRM pages.
    path = Path(settings.BASE_DIR) / 'workspace/static/workspace/push_sw.js'
    response = HttpResponse(path.read_text(encoding='utf-8'), content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@login_required
def push_config(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    key = os.environ.get('WEB_PUSH_VAPID_PUBLIC_KEY', '')
    return JsonResponse({'available': bool(key and os.environ.get('WEB_PUSH_VAPID_PRIVATE_KEY')), 'publicKey': key if key else ''})


@login_required
@require_GET
def push_status(request):
    """Safe diagnostics for the currently signed-in CRM account only."""
    member = _member(request)
    if not member:
        return JsonResponse({'error': 'Account unavailable'}, status=403)
    enabled = bool(os.environ.get('WEB_PUSH_VAPID_PUBLIC_KEY') and os.environ.get('WEB_PUSH_VAPID_PRIVATE_KEY'))
    return JsonResponse({
        'serverEnabled': enabled,
        'subscriptions': PushSubscription.objects.filter(member=member).count(),
    })


@login_required
@require_POST
def push_test(request):
    """One opt-in delivery test per account per minute, scoped to its own inbox."""
    member = _member(request)
    if not member:
        return JsonResponse({'error': 'Account unavailable'}, status=403)
    if not PushSubscription.objects.filter(member=member).exists():
        return JsonResponse({'error': 'Enable desktop notifications in this Chrome profile first.'}, status=400)
    if not cache.add(f'tf-push-test:{member.pk}', True, timeout=60):
        return JsonResponse({'error': 'A test was already sent recently. Try again after one minute.'}, status=429)
    Notification.objects.create(
        recipient=member,
        title='Techfinitys desktop notification test',
        body='Your Chrome profile is registered for CRM desktop alerts.',
        link='#settings',
    )
    return JsonResponse({'ok': True, 'message': 'Test notification queued for your registered browsers.'})


@login_required
@require_POST
def push_subscription(request):
    member = _member(request)
    if not member:
        return JsonResponse({'error': 'Account unavailable'}, status=403)
    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid request'}, status=400)
    endpoint = data.get('endpoint', '')
    if not _safe_endpoint(endpoint):
        return JsonResponse({'error': 'Invalid browser push endpoint'}, status=400)
    if data.get('action') == 'unsubscribe':
        PushSubscription.objects.filter(member=member, endpoint=endpoint).delete()
        return JsonResponse({'ok': True})
    if data.get('action') != 'subscribe':
        return JsonResponse({'error': 'Unknown action'}, status=400)
    keys = data.get('keys')
    if not isinstance(keys, dict) or any(not isinstance(keys.get(k), str) or
                                      not (12 <= len(keys.get(k)) <= 200)
                                      for k in ('p256dh', 'auth')):
        return JsonResponse({'error': 'Invalid browser keys'}, status=400)
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key or ''
    # A subscription endpoint identifies a browser, never allow another user to
    # silently keep the same endpoint when accounts switch.
    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={'member': member, 'keys': {'p256dh': keys['p256dh'], 'auth': keys['auth']},
                  'session_key': session_key},
    )
    return JsonResponse({'ok': True})


def send_notification_push(notification_id):
    """Called only after commit; failure cannot break chat or task writes."""
    private = os.environ.get('WEB_PUSH_VAPID_PRIVATE_KEY', '')
    if not private:
        return
    try:
        from pywebpush import webpush, WebPushException
        n = Notification.objects.filter(pk=notification_id).first()
        if not n:
            return
        payload = json.dumps({
            'id': n.pk, 'title': n.title, 'body': n.body[:150],
            'link': n.link or '#overview',
        })
        for sub in PushSubscription.objects.filter(member=n.recipient).iterator():
            try:
                webpush(
                    subscription_info={'endpoint': sub.endpoint, 'keys': sub.keys},
                    data=payload, vapid_private_key=private,
                    vapid_claims={'sub': os.environ.get('WEB_PUSH_VAPID_SUBJECT', 'https://techfinitys-crm-8wp1.onrender.com')},
                    timeout=4,
                )
            except WebPushException as exc:
                status = getattr(getattr(exc, 'response', None), 'status_code', None)
                if status in (404, 410):
                    sub.delete()
                else:
                    logger.warning('Web Push provider rejected delivery: %s', status)
            except Exception:
                logger.exception('Web Push delivery failure')
    except Exception:
        logger.exception('Web Push could not prepare notification')


@receiver(post_save, sender=Notification, dispatch_uid='tf_web_push_notification')
def notification_created(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(lambda notification_id=instance.pk: send_notification_push(notification_id))
