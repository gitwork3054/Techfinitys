"""Idempotent demonstration data for the Techfinitys CRM.

Runs on startup so the Render Free ephemeral SQLite database is repopulated
after an instance recreation. Never resets existing client/project/task edits,
creates login accounts, or touches records outside the demo namespace.
"""
from datetime import timedelta
from uuid import uuid5, NAMESPACE_URL

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from workspace.models import ClientAccount, ClientAssignment, Member, Project, Task


DEMO_CLIENTS = [
    ("demo-aurelia-living", "DEMO | Aurelia Living", "Home decor", "Social Media Growth"),
    ("demo-northstar-cafe", "DEMO | Northstar Cafe", "Cafe & hospitality", "Monthly Content"),
    ("demo-velora-wellness", "DEMO | Velora Wellness", "Health & wellness", "Brand + Digital"),
    ("demo-urban-nest", "DEMO | Urban Nest", "Real estate", "Website + Leads"),
    ("demo-saffron-studio", "DEMO | Saffron Studio", "Fashion", "Creative Retainer"),
]

# Each client has two projects; each project has three independent tasks.
PROJECT_DEFINITIONS = [
    ("Instagram Content Calendar", "Monthly creative planning, reels, posts and publishing."),
    ("Digital Growth Campaign", "Campaign delivery, audience experiments and reporting."),
]

TASK_DEFINITIONS = [
    ("Plan creative brief", "todo", "normal", 3),
    ("Produce campaign creatives", "in_progress", "high", 7),
    ("Review and deliver assets", "review", "normal", 12),
]


class Command(BaseCommand):
    help = "Ensure persistent-looking demo client/project/task fixtures without duplicates."

    def handle(self, *args, **options):
        names = ("priya", "yatri", "janvi", "maya", "mahi")
        employees = {}
        for username in names:
            member = Member.objects.filter(
                user__username__iexact=username, role="employee", is_active=True,
                user__is_active=True,
            ).first()
            if member:
                employees[username] = member
        if not employees:
            self.stdout.write(self.style.WARNING(
                "Demo records skipped: none of the named employee accounts exist."
            ))
            return

        today = timezone.localdate()
        now = timezone.now()
        counts = {"clients": 0, "projects": 0, "tasks": 0, "assignments": 0}
        with transaction.atomic():
            for index, (code, name, company, package) in enumerate(DEMO_CLIENTS):
                client, made = ClientAccount.objects.get_or_create(
                    code=code,
                    defaults={
                        "name": name, "company": company, "package": package,
                        "status": "active",
                    },
                )
                counts["clients"] += int(made)
                employee = employees.get(names[index])
                if employee:
                    assignment, new_assignment = ClientAssignment.objects.get_or_create(
                        client=client, employee=employee,
                        defaults={
                            "role_title": "Demo project owner", "is_primary": True,
                            "active": True,
                        },
                    )
                    counts["assignments"] += int(new_assignment)

                for project_index, (title, description) in enumerate(PROJECT_DEFINITIONS):
                    stable_project_id = uuid5(NAMESPACE_URL, f"techfinitys-demo-project:{code}:{project_index}")
                    project, new_project = Project.objects.get_or_create(
                        pk=stable_project_id,
                        defaults={
                            "client": client, "title": "DEMO | " + title,
                            "description": description + " (Sample data)",
                            "status": "active" if project_index == 0 else "planned",
                            "owner": employee, "progress": 25 if project_index == 0 else 0,
                            "start_date": today, "due_date": today + timedelta(days=30),
                            "group_name": "Demo projects", "tags": ["demo", "sample"],
                        },
                    )
                    counts["projects"] += int(new_project)

                    for task_index, (task_title, status, priority, offset) in enumerate(TASK_DEFINITIONS):
                        stable_task_id = uuid5(NAMESPACE_URL, f"techfinitys-demo-task:{code}:{project_index}:{task_index}")
                        task, new_task = Task.objects.get_or_create(
                            pk=stable_task_id,
                            defaults={
                                "client": client, "project": project,
                                "title": "DEMO | " + task_title,
                                "description": (
                                    "Sample task for exploring Techfinitys CRM. "
                                    "Edit the status, assignment, or deadline as needed."
                                ),
                                "status": status if project_index == 0 else "todo",
                                "priority": priority,
                                "assigned_to": employee,
                                "start_at": now,
                                "due_at": now + timedelta(days=offset + project_index * 5),
                                "estimated_hours": 3 + task_index,
                                "client_visible": False,
                                "percent_complete": 50 if status == "in_progress" and project_index == 0 else 0,
                                "tags": ["demo"],
                            },
                        )
                        counts["tasks"] += int(new_task)

        self.stdout.write(self.style.SUCCESS(
            "Demo records ready: "
            + ", ".join(f"{count} new {kind}" for kind, count in counts.items())
            + ". Existing records were preserved."
        ))
