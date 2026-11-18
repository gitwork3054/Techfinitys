"""Techfinitys OS Django settings.

Local SQLite works with no environment setup. Production reads settings from
environment variables, uses PostgreSQL, HTTPS cookies and static file serving.
"""
import os
from pathlib import Path
from urllib.parse import urlparse, unquote
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get('DJANGO_DEBUG', 'true').lower() in ('1','true','yes')
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY before running in production')
    SECRET_KEY = 'django-insecure-local-development-only-change-before-deployment'

ALLOWED_HOSTS = [host.strip() for host in os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if host.strip()]
CSRF_TRUSTED_ORIGINS = [host.strip() for host in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if host.strip()]

# Render supplies the actual service hostname. Keep Host and CSRF checks strict
# without needing to guess the onrender.com subdomain ahead of deployment.
render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '').strip()
render_origin = os.environ.get('RENDER_EXTERNAL_URL', '').strip()
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)
if render_origin and render_origin not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(render_origin)

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'workspace'
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'techfinitys_crm.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]}
}]
WSGI_APPLICATION = 'techfinitys_crm.wsgi.application'

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}
database_url = os.environ.get('DATABASE_URL', '')
if database_url:
    parsed = urlparse(database_url)
    if parsed.scheme not in ('postgres', 'postgresql'):
        raise ImproperlyConfigured('DATABASE_URL must be a PostgreSQL URL')
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': unquote(parsed.path.lstrip('/')),
        'USER': unquote(parsed.username or ''),
        'PASSWORD': unquote(parsed.password or ''),
        'HOST': parsed.hostname or 'localhost',
        'PORT': parsed.port or '5432',
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {'sslmode': os.environ.get('DB_SSLMODE', 'prefer')},
    }}

# Set an actual, supported email transport and provider in production before
# relying on email notifications. In-app notifications work out of the box.
AUTH_PASSWORD_VALIDATORS = [
    {'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':10}},
    {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE='en-us'
TIME_ZONE='Asia/Kolkata'
USE_I18N=True
USE_TZ=True
STATIC_URL='/static/'
STATIC_ROOT=BASE_DIR/'staticfiles'
MEDIA_URL='/media/'
MEDIA_ROOT=BASE_DIR/'media'
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
LOGIN_URL='/login/'
LOGIN_REDIRECT_URL='/'
FILE_UPLOAD_MAX_MEMORY_SIZE=2_000_000
DATA_UPLOAD_MAX_MEMORY_SIZE=8_000_000

# Browser security for live deployments. Set proper HTTPS termination at proxy.
SESSION_COOKIE_HTTPONLY=True
CSRF_COOKIE_HTTPONLY=False  # Used by the first-party JavaScript CSRF header.
SESSION_COOKIE_SAMESITE='Lax'
CSRF_COOKIE_SAMESITE='Lax'
SESSION_COOKIE_SECURE=not DEBUG
CSRF_COOKIE_SECURE=not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF=True
SECURE_REFERRER_POLICY='same-origin'
X_FRAME_OPTIONS='DENY'
SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')
SECURE_SSL_REDIRECT=not DEBUG and os.environ.get('DJANGO_HTTPS_REDIRECT','true').lower()=='true'
SECURE_HSTS_SECONDS=31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS=not DEBUG
SECURE_HSTS_PRELOAD=False

# WhiteNoise supports production static assets when installed. Django's normal
# development static serving is unchanged when it is absent.
try:
    import whitenoise  # noqa: F401
except ImportError:
    if not DEBUG:
        raise ImproperlyConfigured('Install requirements.txt (WhiteNoise) before deploying')
else:
    MIDDLEWARE.insert(1,'whitenoise.middleware.WhiteNoiseMiddleware')
    STORAGES = {'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
                'staticfiles':{'BACKEND':'whitenoise.storage.CompressedManifestStaticFilesStorage'}}

# Google OAuth client credentials must live in Render Environment, never Git.
GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID', '').strip()
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET', '').strip()
GOOGLE_OAUTH_REDIRECT_URI = os.environ.get('GOOGLE_OAUTH_REDIRECT_URI', '').strip()
