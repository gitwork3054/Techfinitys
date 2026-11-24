#!/usr/bin/env bash
set -euo pipefail
python manage.py migrate --noinput
python manage.py ensure_admin
python manage.py ensure_employees
python manage.py ensure_demo_records
exec gunicorn techfinitys_crm.wsgi:application --bind "0.0.0.0:${PORT:-10000}" --workers "${WEB_CONCURRENCY:-2}" --timeout 75 --access-logfile -