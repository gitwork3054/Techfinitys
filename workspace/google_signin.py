"""Google OpenID Connect sign-in for pre-provisioned Techfinitys accounts.

No self-registration, no Gmail inbox scopes and no long-lived Google tokens.
"""
import hmac
import logging
import secrets
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .models import Member

logger = logging.getLogger(__name__)
GOOGLE_AUTH_ENDPOINT = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token'


def _enabled():
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def _callback_uri(request):
    return settings.GOOGLE_OAUTH_REDIRECT_URI or request.build_absolute_uri(reverse('google_callback'))


def _error(code):
    # Fixed error codes prevent leaking identity details or OAuth parameters.
    return redirect(reverse('login') + '?' + urlencode({'google_error':code}))


@never_cache
@require_GET
def google_start(request):
    if request.user.is_authenticated:
        return redirect('/')
    if not _enabled():
        return _error('unconfigured')
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    request.session['tf_google_state'] = state
    request.session['tf_google_nonce'] = nonce
    next_url = request.GET.get('next', '/')
    request.session['tf_google_next'] = next_url if url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ) else '/'
    params = {
        'client_id':settings.GOOGLE_OAUTH_CLIENT_ID,
        'redirect_uri':_callback_uri(request),
        'response_type':'code',
        'scope':'openid email profile',
        'state':state,
        'nonce':nonce,
        'prompt':'select_account',
    }
    return redirect(GOOGLE_AUTH_ENDPOINT + '?' + urlencode(params))


@never_cache
@require_GET
def google_callback(request):
    expected = request.session.pop('tf_google_state', None)
    nonce = request.session.pop('tf_google_nonce', None)
    next_url = request.session.pop('tf_google_next', '/')
    state = request.GET.get('state', '')
    if not _enabled() or not expected or not nonce or not hmac.compare_digest(state, expected):
        return HttpResponseBadRequest('Google sign-in session expired or invalid. Return to the sign-in page.')
    if request.GET.get('error'):
        return _error('cancelled')
    code = request.GET.get('code', '')
    if not code or len(code) > 4096:
        return _error('invalid')
    try:
        token_response = requests.post(GOOGLE_TOKEN_ENDPOINT, data={
            'code':code,
            'client_id':settings.GOOGLE_OAUTH_CLIENT_ID,
            'client_secret':settings.GOOGLE_OAUTH_CLIENT_SECRET,
            'redirect_uri':_callback_uri(request),
            'grant_type':'authorization_code',
        }, timeout=12)
        token_response.raise_for_status()
        identity_token = token_response.json().get('id_token', '')
        if not identity_token:
            raise ValueError('Missing ID token')
        # Verify signature against Google's published public keys, plus aud,
        # issuer, expiry and then the request nonce to prevent replay.
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
        claims = id_token.verify_oauth2_token(identity_token, google_requests.Request(), settings.GOOGLE_OAUTH_CLIENT_ID)
        if claims.get('iss') not in ('accounts.google.com', 'https://accounts.google.com'):
            raise ValueError('Invalid token issuer')
        if not hmac.compare_digest(str(claims.get('nonce') or ''), nonce):
            raise ValueError('Invalid nonce')
        if claims.get('email_verified') is not True:
            raise ValueError('Email is unverified')
        email = str(claims.get('email') or '').lower().strip()
        sub = str(claims.get('sub') or '')
        if not email or not sub or len(sub) > 255:
            raise ValueError('Incomplete Google identity')
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        # Log only the type, never tokens/codes/emails or sensitive payloads.
        logger.warning('Google OIDC verification failed (%s)',type(exc).__name__)
        return _error('invalid')
    except Exception as exc:
        logger.warning('Google OIDC verification unavailable (%s)',type(exc).__name__)
        return _error('invalid')
    try:
        with transaction.atomic():
            matches = list(User.objects.select_for_update().filter(email__iexact=email)[:2])
            if len(matches) != 1:
                return _error('uninvited')
            user = matches[0]
            membership = Member.objects.select_for_update().filter(user=user).first()
            if not user.is_active or not membership or not membership.is_active:
                return _error('uninvited')
            # The provider's immutable subject prevents rebinding an existing
            # account to a different Google identity after the first login.
            if membership.google_sub and membership.google_sub != sub:
                return _error('mismatch')
            if not membership.google_sub:
                if Member.objects.filter(google_sub=sub).exclude(pk=membership.pk).exists():
                    return _error('mismatch')
                membership.google_sub = sub
                membership.save(update_fields=['google_sub'])
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect(next_url if url_has_allowed_host_and_scheme(next_url,
            allowed_hosts={request.get_host()}, require_https=request.is_secure()) else '/')
    except IntegrityError:
        return _error('mismatch')
