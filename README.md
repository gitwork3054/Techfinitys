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


---

## WorkChat, profile pictures, and Google sign-in (November 2026)

The workspace includes a Recent Projects sidebar (recently visited, then recent accessible projects),
profile photo editor (click the header avatar), employee-only WorkChat, and optional Google sign-in.

### Private team messaging

- **Chats > People** starts a direct conversation with an active employee.
- **Chats > + New > Start group** creates a group chat with selected colleagues (up to 20 members).
- Messages are stored in Django's database and access is checked on every request. Clients **cannot** read or join internal employee conversations.
- The chat list refreshes every 30 seconds when the tab is visible; an open conversation refreshes every 6 seconds. This is polling, not WebSockets, voice calling, or Gmail inbox integration.
- Recent project history is scoped to your assigned clients; the database prevents duplicate per-user visit records.

### Profile photos

Use the top-right avatar → **Edit profile**, choose a JPG/PNG/WebP smaller than 2 MB, and save.
The server validates the photo, converts it to a 384px WebP thumbnail, and serves it through
a permission-controlled endpoint. The local filesystem used for uploads on Render Free is
**ephemeral**; for live users, configure durable object storage (S3/R2/etc.) before relying on profile photos.

### Enable **Continue with Google** (Google OpenID Connect)

This implements sign-in with a Google/Gmail account; it does **not** read emails or connect a Gmail inbox.
The button remains explicitly disabled until OAuth credentials are configured.

1. Visit [Google Cloud console](https://console.cloud.google.com/apis/credentials), configure the OAuth consent screen, then create an **OAuth 2.0 Client ID** of type **Web application**.
2. Add the exact **Authorized redirect URI**:
   `https://techfinitys-crm-8wp1.onrender.com/auth/google/callback/`.
3. In **Render → techfinitys-crm-8wp1 → Environment**, set `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`. You may also set `GOOGLE_OAUTH_REDIRECT_URI` to the URI above for explicit matching. **Never commit OAuth credentials to GitHub.**
4. In Techfinitys CRM's Django administrator (`/admin/`), set each employee/client's own Google email on their existing Django user account. Email addresses must be unique. Google **does not** create new CRM accounts or assign roles; an active, pre-invited CRM member is required.
5. Restart/redeploy via Render so the variables are available, then use **Continue with Google** on the login page.

The server validates OAuth state, ID-token issuer/audience/expiry/nonce, verified email, and
Google's immutable subject. It requests only `openid email profile` scopes and stores **no Google access/refresh tokens**.

### Production data warning

Render Free currently runs this CRM using SQLite and local media storage. Database data,
chat messages, project visit history, and photos can disappear on redeploy or restart.
Deploy with a durable PostgreSQL database and object storage before real organizational use.

### Check security and regression tests

```bash
python manage.py migrate
python manage.py test workspace.test_collaboration -v 2
python manage.py test workspace -v 2
```

---

## Client invoicing / Billing Studio (November 2026)

`Billing` now contains **real relational invoices** (not legacy JSON records): a client/package selection form, quantities and additional charges, discount and tax percentage, client billing details, due dates, and payments. All money calculations use Python `Decimal` and are recomputed on the server. Invoice numbers are assigned *only when issued* in the sequence `TF-YYYY-00001`. Issued invoice amounts, billing-party details and seller letterhead values cannot be edited; corrections require voiding an unpaid issued invoice and creating a new one. A paid invoice cannot be voided from the CRM UI.

The generated A4 PDF is available to managers and to the **account owning client**, never an unrelated client. It contains company logo, branded header/footer, buyer/seller information, package lines, tax breakdown, totals, due date, payment history and a visual **authorized company stamp**. The stamp is a visual brand mark, *not* a cryptographic e-signature. The Super Admin may update letterhead/bank details and optionally upload a PNG/JPEG company stamp; issued invoices retain the seller text/stamp snapshot. Configure actual legal name, GSTIN, billing address and bank details before issuing real tax invoices. **GST rate and label are deliberately not auto-filled**: confirm the appropriate tax treatment with a qualified accountant. The system is not represented as e-invoicing or GST compliance software.

Billing endpoints:

| Route | Behavior |
|---|---|
| `GET /api/billing/` | Role-scoped invoice register; clients only see issued, paid or void invoices belonging to them |
| `POST /api/billing/` | Create/edit draft, issue, record payment, void, save letterhead or recurring schedule (manager/admin) |
| `GET /api/billing/pdf/<invoice_uuid>/` | Authenticated, no-cache branded PDF with authorization checks |
| `GET /api/billing/export/` | Manager/admin CSV export |
| `POST /api/billing/stamp/` | Super Admin PNG/JPEG company stamp upload |

**Recurring billing:** Managers can set monthly, quarterly or annual plans. Each due cycle generates an invoice as a **draft**; optionally tick **Auto-issue** to issue it automatically when the generator runs. The generation command is idempotent, never charges a card, and never sends external emails:

```bash
python manage.py generate_invoices
```

Run it from a **secure daily scheduler** in a persistent environment. A free Render web app does **not** automatically run scheduled commands. No paid Render cron service is provisioned by this update. Do not enable automated issuing or enter real finance data until PostgreSQL and durable media storage are configured: current free SQLite and stamp-upload storage are temporary and can be lost on restart/redeploy. Test with representative fake data first.

Run billing integration tests after installing dependencies:

```bash
python manage.py migrate
python manage.py test workspace.test_billing -v 2
python manage.py check
```

`reportlab` is required for invoice PDF generation and is included in `requirements.txt`.

## Super Admin Activity & Approval Center (November 2026)

The **Admin activity** section is visible only to a provisioned **Super Admin** (`role=admin`). The notification bell opens the same command center, and the main dashboard shows a team-activity summary. Available tools:

- **Approval queue:** pending employee leave requests, submitted timesheets and internal sign-offs. The Approve / Decline buttons call the existing, permission-checked `/api/operations/` actions. Employees receive the original decision notification, with reviewer and decision time saved by the operations model.
- **Employee activity feed:** actor, client, action, description and original timestamp across attendance, breaks, time logs, tasks, task status, project/issue updates, internal approvals, support, client actions, billing and staff changes. Includes employee search, date range, type filters and cursor-based pagination.
- **In-app alerts:** each new employee/manager `ActivityLog` is delivered to active Super Admins as an in-app notification tagged `#admin_activity`. Notifications are per recipient and can be marked read without changing the underlying audit. Direct chat messages appear in audit metadata **without message content** and do not trigger per-message bell notifications.
- **Live overview:** active shifts, pending reviews, today’s activity, unread alerts. The browser refreshes when the admin activity page is open and visible (polling, not WebSockets).

The server enforces admin-only read and mark-read access for `/api/admin-activity/`; changing a client-side role or route never unlocks that endpoint. The audit is **application-level**: it records actions that are logged by the CRM, not the contents of external websites, email, or employees’ devices. Data produced before logging was introduced cannot be backfilled automatically.

Regression tests: `python manage.py test workspace.test_admin_activity workspace.test_billing -v 1`. Browser/JavaScript smoke: `node qa/node_activity_smoke.js`.

**Production readiness:** The Render Free demo currently uses ephemeral SQLite. Employee events, approvals, and notifications can disappear across restarts or deploys. Use a durable PostgreSQL database, backups, a configured log-retention policy, and proper role offboarding before collecting actual employee records. In-app polling is active; email/push notifications are not configured. Follow applicable workplace privacy and employee-notice requirements when enabling centralized monitoring.

## Employee navigation & All Tasks home panel (November 2026)

Employee accounts have a focused navigation: **Home, My Tasks, Projects, Attendance, Time Tracking, Leave, Calendar, Updates and Documents.** WorkChat and the profile-photo editor remain available from the chat dock and avatar. Employees do not see CRM-wide sales, billing, team administration, reports, audit, widget editing, bulk task assignment or other management controls. Office Managers and Super Admins retain their existing management tools; clients keep their client portal.

The **All Tasks** register is always visible at the top of the home dashboard, independently of saved dashboard widgets. Super Admins/managers see tasks from their authorized workspaces, while employees see tasks **assigned to them** (primary owner or collaborator). Employees can click any listed task to inspect details and, for assigned tasks, update its status, without seeing assignment or billing fields. The home list includes open and completed work, search, status filters, due dates and a progressive **Show more** control, as well as a link to the full task workspace. Project tabs are simplified for employees.

The backend remains the authority for client isolation and task updates: hiding a menu item does not replace API access checks. JavaScript regression check: `node qa/node_employee_roles_smoke.js` (no packages required); it covers focused navigation, assigned-task filtering, click-through task details, client-side route restrictions, and retained Super Admin controls.

The application continues using temporary SQLite and local uploads on Render Free. Do not enter real employee or client data until persistent PostgreSQL and durable media storage are configured.

### Inline task entry and date editing (project Task List)

Office Managers and Super Admins can open **Projects > a project > Tasks > List** and type directly into the **Add task…** row underneath each task group. **Enter** (or **Add ↵**) saves an internal draft task in that project/task list; **Escape** clears the draft. The server generates the task ID, keeps client visibility off until a manager deliberately publishes it, and records an audit entry. Employees cannot create tasks through this interface, preserving the restricted employee workspace.

Click a task's **Start date** or **Due date** cell to open the browser's native date picker. Picking a date saves only that field, with server validation ensuring the due date cannot precede the start date. Clearing a date is supported. Users can still use the detailed task editor for descriptions, ownership, priority, and other settings.

## 2026-11-23 — Projects workspace UI/UX modernization

A redesigned, Techfinitys-branded light project-management interface now presents a compact navigation, tabbed project workspaces, dense editable task lists, and new Gantt / workload views. Task detail opens as a side drawer with real API-backed comments, checklist items, activity and dependency management, plus safe task duplication. Existing billing, employee operations, chat, client portal and Super Admin activity modules are preserved.

**What remains:** This is not full Zoho Projects feature parity. Consult [`ZOHO_PARITY.md`](ZOHO_PARITY.md) for supported and future capabilities. The live Render Free preview is still **not suitable for production data** until its database and file storage are persistent.
