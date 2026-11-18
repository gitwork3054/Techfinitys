# Techfinitys OS — Client + Employee CRM

**A working Django CRM foundation with distinct client, employee, office-manager and admin workspaces.** Built on the supplied Techfinitys Zoho-style dashboard, keeping existing modules and data schemas while adding relational operations, a custom premium interface, workflows and isolation checks.

Inspired by common Zoho CRM / Projects / People workflow concepts; **not affiliated with Zoho** and does not copy Zoho code or assets.

## Included features

| Area | What this release implements |
|---|---|
| Workspaces | Client portal, employee desk, manager command center, super-admin view; role-based navigation and server-side tenant access |
| CRM / people | Multiple client accounts, employees, reporting managers, role permissions, account-team assignment, client portal users |
| Projects | Projects, status/progress, owners, dates, structured milestones and roadmap |
| Tasks | List and Kanban (existing), due dates, priorities, assignment, subtask hierarchy, dependencies, tags, saved personal filters/views, quick create |
| Attendance | One clock-in session per employee/day, work mode, clock-out, start/end break, worked-time calculation, manager team overview, CSV export |
| Leave | Annual/sick/casual/unpaid requests, overlapping-leave checks, manager approval/rejection, history, notifications |
| Timesheets | Time logs by client/project/task, billable flag, draft/submitted/approved/rejected lifecycle, 24h/day check, manager review, CSV export |
| Sign-offs | Client-facing deliverable approvals and internal review requests with decision notes, reviewer permissions and notifications |
| Support | Customer support tickets, priorities/statuses, threaded responses, private internal messages, status notifications and CSV export |
| Sales | Lead capture pipeline, stage updates, value tracking, client conversion, manager visibility, CSV export |
| Agency modules | Original calendar, client updates, notes, content, campaigns, deliverables, file records, shoots, packages, billing records, reports and legacy workflows |
| Productivity | Global keyboard search (`Ctrl/Cmd+K`), quick-create menu, notification inbox, personal filters, CSV reports, activity history, light/dark UI |
| Reminders | `send_reminders` command for approaching/overdue tasks, milestones, pending approvals and stale urgent tickets; requires external scheduling |
| Admin | Django Admin for structured entities, configurable super-admin/bootstrap command |

### Roles and privacy

**Super Admin:** Organisation-wide clients, people, CRM and configuration. **Office Manager:** Team and client operations, attendance/leave/timesheet oversight and leads. **Employee:** Only assigned client accounts, their work/timesheets/leave, linked tasks and team activity. **Client:** Only their own account, visible project/task updates, milestones, approvals, tickets and shared files.

The server checks the role, client assignment, visibility level, and referenced IDs. An employee cannot retrieve or modify an unassigned account by changing a record ID. Client-facing API responses exclude private tasks and internal ticket messages. Audit details are hidden from client users. The application includes regression tests for these rules.

## Requirements

- Python 3.11+ (3.13 supported by the declared dependencies)
- SQLite for local demos; **PostgreSQL for real/production deployments**
- Install packages from `requirements.txt` (internet/package mirror required for first install)

## Start locally (Windows / VS Code)

From the directory containing `manage.py`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo  # development demo ONLY; creates known sample passwords
python manage.py runserver
```

Visit **http://127.0.0.1:8000/**. For Windows Command Prompt, you can double-click `run_windows.bat` after the demo has been seeded; it installs dependencies, migrates and starts the server without resetting your sample accounts.

For macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

### Demo logins (local testing only)

| Role | Username | Password |
|---|---|---|
| Super Admin | `admin` | `admin12345` |
| Office Manager | `manager` | `manager12345` |
| Employee | `aarav` | `employee12345` |
| Employee | `riya` | `employee12345` |
| Employee | `dev` | `employee12345` |
| Employee | `neha` | `employee12345` |
| Client portal | `client_aurelia` | `client12345` |

**Never run `seed_demo` on a deployed or real database.** The command refuses to run with `DJANGO_DEBUG=false`. It creates **known passwords and sample client records**, and rerunning it in development resets those demo user passwords.

### Use real accounts instead of demo data

```bash
python manage.py migrate
python manage.py bootstrap_admin --username your_admin --password 'use-a-strong-unique-password'
python manage.py runserver
```

Create clients/people under their respective modules, assign delivery employees to clients, then create projects and tasks. Django administrative interface is available at `/admin/` to Super Admin users.

## How to operate the workflows

1. A manager creates a client and assigns account-team employees. Only those employees can see that client.
2. The team creates projects, phases/milestones, tasks (including dependency and tags), and schedules work; an assigned employee posts progress updates.
3. An employee clocks in/out, logs a break, requests time off and submits billable time. Managers review submitted leave and timesheets.
4. The employee requests a client approval for a deliverable. The correct client portal user approves, rejects or requests changes; the requesting team member is notified.
5. Clients open and reply to support tickets. Staff can add either shared replies or private internal notes; clients cannot see private replies.
6. Managers record leads, advance opportunity stages and convert won deals to client accounts. Everyone can search, set personal task views, and export the permitted reports.

## Important URLs / commands

| Endpoint | Purpose |
|---|---|
| `/` | Role-aware web application |
| `/login/` / `/logout/` | Django session authentication |
| `/api/workspace/` | Original scoped CRM data + actions |
| `/api/operations/` | Attendance, leave, timesheets, approvals, support, milestones, leads, views and password changes |
| `/api/export/attendance/` | Staff attendance CSV |
| `/api/export/timesheets/` | Staff time log CSV |
| `/api/export/leaves/` | Staff leave CSV |
| `/api/export/tickets/` | Scoped support CSV |
| `/api/export/leads/` | Manager lead CSV |
| `/admin/` | Django Admin |

Run daily reminders at approximately 09:00 Asia/Kolkata with your host's cron/task scheduler:

```bash
python manage.py send_reminders --dry-run  # report eligible notifications
python manage.py send_reminders            # add idempotent in-app notifications
```

Reminders are not automatically scheduled by Django; configure cron/Render Cron/Celery and database access separately. They do **not** send email, WhatsApp or SMS yet.

## Automated and visual tests

```bash
python manage.py test workspace -v 2
python manage.py check
python manage.py makemigrations --check --dry-run
```

`workspace/tests.py` includes regression cases for tenant isolation, client privacy, task dependencies, attendance, break tracking, leave, time approvals, client sign-offs, ticket privacy, saved filters, lead permissions/conversion and CSV scoping. **Run these tests in a Python environment with Django installed before putting real users on the system.**

The interface was also reviewed in a headless Chromium browser with mock data for manager, client and mobile layouts. Browser preview checks do not replace Django/database integration tests.

## Deployment (Render, GoDaddy VPS or other Python host)

1. Provision a persistent **PostgreSQL** database; configure `DATABASE_URL`.
2. Set `DJANGO_DEBUG=false`, a new random `DJANGO_SECRET_KEY`, domain(s) in `DJANGO_ALLOWED_HOSTS`, and origin(s) in `DJANGO_CSRF_TRUSTED_ORIGINS` (e.g. `https://crm.your-domain.com`). An example is in `.env.example`.
3. Install requirements, run `python manage.py migrate` and `python manage.py collectstatic --noinput`.
4. Start `gunicorn techfinitys_crm.wsgi:application --bind 0.0.0.0:$PORT --workers 3`, behind a HTTPS reverse proxy. Tune Gunicorn workers for your host's RAM/CPU; three is illustrative.
5. Create an actual administrator using `bootstrap_admin` (do not run demo seed). Add external scheduler for reminders, daily backups/restore verification, error monitoring and the public domain/DNS configuration.
6. For Render, `render.yaml` is a **deployment starting template**, not an automatic deployment. Set host/origin environment values and check database pricing before provisioning. For GoDaddy shared hosting, check support for long-running Python/Gunicorn and PostgreSQL; a VPS may be required.

### Before inviting real customers

This release is a **substantial functional CRM application/foundation**, but it has **not** received a production security audit, live database integration-test run in this generation environment, high-load benchmarking or operational sign-off. In particular:

- Uploaded files use local filesystem storage, which is **not durable** on ephemeral platforms like Render; integrate private S3-compatible object storage and secure signed file delivery before accepting real uploads.
- Billing, payments and the original “workflows” agency screens are legacy record modules, not connected accounting/payment processors or a general no-code automation engine. The Razorpay endpoint deliberately returns “not configured”.
- Email, WhatsApp, SMS, push notifications, external calendar sync, Google/Microsoft SSO, MFA, payroll, biometric/GPS attendance, mobile native apps, and advanced analytics warehouses are **not yet connected**. Integrate supported services explicitly as separate milestones.
- Add login throttling/lockouts, 2FA/SSO, attachment scanning, explicit retention policies, detailed audit and administrator-review procedures, stronger cross-object validation, and compliance/privacy review for live customer data.
- GET feeds are bounded but still load multiple modules together. For very large organisations, build paginated/server-filtered endpoints, caching, async workers, query monitoring, load tests and archiving before scaling.
- Maintain regular schema migrations, Postgres backups and tested restoration. API routes use Django's session authentication and CSRF protection; use HTTPS only in production.

## File map

```text
techfinitys_crm/settings.py             Environment-controlled configuration
workspace/models.py                     Client/project/task + new relational operations entities
workspace/migrations/0002_operations.py  Data-preserving schema extension
workspace/views.py                      Existing CRM APIs and access scope
workspace/operations.py                 New typed operational APIs and CSV reports
workspace/policy.py                     Role policy / legacy visibility
workspace/static/workspace/app.js        Original project functions
workspace/static/workspace/enterprise.js New workflow screens and navigation
workspace/static/workspace/app.css       Original UI foundation
workspace/static/workspace/enterprise.css Premium UI system and responsive design
workspace/templates/workspace/          Auth and app shells
workspace/management/commands/          Bootstrap, demo seed, daily reminders
workspace/tests.py                      Security and workflow regression tests
render.yaml                              Optional Render deployment template
```

All data stays in your own Django database. This is a custom Techfinitys application, not a Zoho subscription or an official Zoho integration.

### Deploying the free demo with Render

`render.yaml` configures a free web service and a free managed PostgreSQL database in Singapore.
The service collects static assets at build time; on boot, `start.sh` migrates the database,
creates the **first** super administrator from `CRM_ADMIN_USERNAME` / `CRM_ADMIN_PASSWORD`,
and starts Gunicorn. The provisioning command does **not** reset a user's password on later deploys.
Render generates the secret key and initial admin password automatically when using the Blueprint.
Read the generated `CRM_ADMIN_PASSWORD` in your Render service's Environment settings, sign
in as `admin`, and immediately change the password in Account settings.

**Important:** Render free database plans have service limits, no production SLA, and may expire.
This is suitable for evaluation only. Do not put important customer data or payroll records on
a free evaluation database. The application currently saves uploaded files to the container's
local filesystem; **those uploads are not durable on Render** without external object storage.
Use a paid persistent PostgreSQL plan, object storage, monitored backups and a production
security review before inviting real clients.

## Project Studio: task lists, advanced filters and per-project delivery

The integrated **Project Studio** workspace builds on the existing project and task
models; it is not a static Zoho copy or an integration with Zoho.

* **Projects register:** sortable project ID/name/owner/status/progress/task/issue/date columns,
  search, status/group filters, numbered pages, team progress and CSV export.
* **Individual project:** dashboard, task lists, project users, reports, documents,
  phases (milestones), time logs, issues, threaded feed, timesheets and approvals.
* **Tasks:** sortable table or Kanban board, project/task-list/status/owner grouping,
  multi-person collaborators, completion percentages, priorities, due-date alerts,
  bulk status updates and dependency checks.
* **Advanced filtering:** 22 conditions, Any/All logic, time spans, owner, project,
  tags, billing, dates, recurrence, completion percentage and saved personal views.
* **Project issues:** track blockers with assignees, severity, status transitions,
  client visibility, notifications and CSV exports.
* **Project feed:** thread replies with visibility scopes (team-only vs client-visible).
* **Files:** project-specific document upload, access-checked download and client
  visibility, currently using the local ephemeral filesystem.
* **Dashboards:** selectable/reorderable widgets saved per person for the global
  dashboard or each project, charts computed from actual scoped tasks, and rule-based
  task-priority suggestions (not an external AI service).

New schema migration: `workspace/migrations/0003_project_workspaces.py`.
New backend endpoints: `/api/projects-plus/`, `/api/projects-plus/upload/`,
`/api/projects-plus/document/<uuid>/`, `/api/project-export/projects/`,
`/api/project-export/tasks/`, `/api/project-export/issues/`.

### Hosting note: deployed Render demonstration

The current `render.yaml` deliberately provisions **only a free web service**:
there is no free PostgreSQL provisioned for this CRM because the workspace's
one free database is owned by an independent payment-gateway project. The CRM
therefore uses **temporary local SQLite** on Render. Data and document uploads
can disappear at any moment on restart, redeploy or container replacement.
Never upload real customer/client/employee records to this preview. Move to a
separate **persistent PostgreSQL** database, secured object storage, backup and
migration-tested runtime before production use. The earlier README's generic
example discussing free managed PostgreSQL is superseded by this note.

### Verification

Browser QA was performed with Chromium using representative **mock API data**
and covers the project register, per-project dashboard, task grid, full advanced
filter drawer, issue list, "All tasks", and mobile horizontal overflow.
Python syntax and JavaScript parse checks pass. The Django test suite in
`workspace/tests.py` now has project-tenant, document, issue and bulk-status
regressions; run it on a machine with Django installed before handling real data.
