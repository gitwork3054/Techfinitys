"""Idempotent daily deadline reminders for work, approvals and escalations.

Schedule externally (e.g. at 09:00 Asia/Kolkata in cron, Render Cron or Celery).
This command sends only in-app notifications, not email or SMS.
"""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from workspace.models import (
    Task, ProjectMilestone, ApprovalRequest, SupportTicket, Notification, Member
)


class Command(BaseCommand):
    help = 'Queue in-app reminders for due tasks, milestones, approvals and stale urgent tickets'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Count candidate notifications without writing')

    def handle(self, *args, **options):
        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)
        now = timezone.now()
        dry_run = options['dry_run']
        queued = set()
        counts = {'tasks':0, 'milestones':0, 'approvals':0, 'tickets':0}

        def deliver(recipient, title, client, bucket):
            if recipient is None or not recipient.is_active:
                return
            key = (recipient.pk, title)
            if key in queued:
                return
            queued.add(key)
            if Notification.objects.filter(recipient=recipient, title=title, created_at__date=today).exists():
                return
            if not dry_run:
                Notification.objects.create(recipient=recipient, client=client, title=title, body='Review this item in your Techfinitys workspace.')
            counts[bucket] += 1

        # Only incomplete work and assigned recipients receive due reminders.
        for t in Task.objects.filter(assigned_to__isnull=False, due_at__date__lte=tomorrow).exclude(
                status='completed').select_related('assigned_to', 'client').iterator(chunk_size=300):
            state = 'Overdue' if t.due_at.date() < today else 'Due soon'
            deliver(t.assigned_to, f'{state} task: {t.title}'[:220], t.client, 'tasks')

        for m in ProjectMilestone.objects.filter(owner__isnull=False, due_date__lte=tomorrow).exclude(
                status='completed').select_related('owner', 'project__client').iterator(chunk_size=300):
            state = 'Overdue' if m.due_date < today else 'Upcoming'
            deliver(m.owner, f'{state} milestone: {m.title}'[:220], m.project.client, 'milestones')

        for a in ApprovalRequest.objects.filter(status='pending', due_at__date__lte=tomorrow).select_related(
                'reviewer', 'client').iterator(chunk_size=300):
            state = 'Overdue' if a.due_at.date() < today else 'Due soon'
            title = f'{state} approval: {a.title}'[:220]
            if a.audience == 'client':
                for portal in Member.objects.filter(role='client', client_account=a.client, is_active=True):
                    deliver(portal, title, a.client, 'approvals')
            else:
                deliver(a.reviewer, title, a.client, 'approvals')

        managers = list(Member.objects.filter(role__in=['admin', 'manager'], is_active=True))
        for ticket in SupportTicket.objects.filter(priority='urgent', status__in=['open','in_progress'],
                updated_at__lte=now-timedelta(hours=24)).select_related('client').iterator(chunk_size=300):
            for manager in managers:
                deliver(manager, f'Stale urgent ticket: {ticket.title}'[:220], ticket.client, 'tickets')

        self.stdout.write(self.style.SUCCESS(
            ('Dry run: ' if dry_run else 'Sent: ') + ', '.join(f'{key}={value}' for key, value in counts.items())))
