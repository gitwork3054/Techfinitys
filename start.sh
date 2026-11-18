#!/usr/bin/env bash
set -euo pipefail
python manage.py migrate --noinput
python manage.py ensure_admin
exec gunicorn techfinitys_crm.wsgi:application --bind "0.0.0.0:${PORT:-10000}" --workers "${WEB_CONCURRENCY:-2}" --timeout 75 --access-logfile -
