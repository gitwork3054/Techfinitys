# Techfinitys CRM — Zoho Projects reference and implementation status

**Reference:** Zoho Projects' public feature documentation and the screenshots supplied by the Techfinitys team. Techfinitys is an independent CRM; it does not copy Zoho's source code, branding, or assets. A similar navigation and workflow pattern is provided under Techfinitys branding.

## Available in this release

| Capability | Implementation and scope |
|---|---|
| Clean project-management shell | Light blue/white desktop layout, compact sticky global navigation, responsive sidebar, denser tables, tabbed project workspaces, light/dark mode |
| Projects, clients, teams and roles | Existing linked Django models and tenant-scoped APIs retained |
| Project dashboard & widgets | Configurable metrics, charts, activity and due work, existing real data |
| Classic task table and Kanban | Grouping, inline new task, editable dates, owners, saved filters, bulk status and paginated list |
| **Gantt task timeline** | New, interactive, date-based read-only chart for visible tasks; click bars to view task. Limited to 180 visible rows and 90-day viewport with month navigation for browser performance |
| **Workload report** | New view from assigned tasks and estimates; compares estimated hours to a **40-hour planning benchmark**, not a validated HR capacity or actual utilization figure |
| **Task details side panel** | New task Overview, Comments, Checklist and Activity tabs; updates persist to database |
| **Task comments** | New per-task threaded history timeline, internal/client visibility, notifications to relevant users; user-supplied text is escaped in the UI |
| **Checklists** | New add, toggle, remove with role permissions and progress calculation |
| **Task dependencies** | New predecessor selector with project scoping and circular-chain rejection, using the existing blocked-by relationship |
| **Duplicate task** | New manager-only copy workflow; duplicated task is internal by default with no inherited date |
| Attendance, leave, approvals and timesheets | Existing modules retained; Super Admin activity center and notifications retained |
| Issues, project files, discussions and teams | Existing modules retained and accessible from project tabs |
| Billing | Existing PDF invoice, partial payments, recurring plans retained |

## Not yet full Zoho Projects parity

These require separate, tested product releases and some may need paid infrastructure or third-party credentials:

- Full multi-dependency drag-and-drop Gantt with project-wide baselines, variance management, and critical-path computation
- Custom task layouts/fields, organization-wide template library and task import/migration assistants
- Blueprint workflow designer, conditional transitions, webhook delivery engine, SLA rule editor and safe scheduled workers
- Capacity planning with leave calendars, rates, holidays, holidays by region, finance-based budget forecasts and earned-value analysis
- Rich file annotation, version history, meeting integration, email-to-task ingestion and external third-party apps
- Fully persistent web/mobile real-time presence with websocket chat, push notifications and an offline mobile client
- Full exports/printed reports and detailed organization permission matrix beyond existing roles and tenant scoping

## Reliability and operational constraints

- `task-detail` API checks authenticated role and client scope on every request; clients cannot read internal comments or internal task activity.
- New comments and checklists are stored in Django models and require the additive `0007_zoho_task_details` migration.
- Task detail records are **lazy loaded** per task instead of included in every dashboard response.
- The Render Free preview currently uses **ephemeral SQLite and local uploads**. This is not suitable for real company tasks or long-term audit/invoice data; configure persistent PostgreSQL, object storage, backups and a proper secret-management policy before onboarding production users.
- Google sign-in requires configured Google OAuth credentials; scheduled reminders/recurring invoice generation require external scheduling.

## Relevant product references

- [Zoho Projects features](https://www.zoho.com/projects/features.html)
- [Task list / Gantt / Kanban task operations](https://help.zoho.com/portal/en/kb/projects/tasks/tasks/tasks-introduction/articles/tasks-15-12-2023)
- [Task details, descriptions and comments](https://help.zoho.com/portal/en/kb/projects/tasks/tasks/tasks-introduction/articles/task-details-page)
- [Task dependencies, Gantt and baselines](https://help.zoho.com/portal/en/kb/projects/tasks/tasks/task-operations/articles/projects-baseline)
