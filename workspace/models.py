import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ClientAccount(models.Model):
    STATUS_CHOICES = [('onboarding','Onboarding'),('active','Active'),('paused','Paused'),('closed','Closed')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=160)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    company = models.CharField(max_length=180, blank=True)
    package = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='onboarding')
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_clients')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Member(models.Model):
    ROLE_CHOICES = [
        ('client','Client'),
        ('employee','Employee'),
        ('manager','Office Manager'),
        ('admin','Super Admin'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='workspace_member')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    client_account = models.ForeignKey(ClientAccount, null=True, blank=True, on_delete=models.SET_NULL, related_name='portal_members')
    # legacy string retained for backwards compatibility with the first Django build
    client = models.CharField(max_length=120, blank=True, default='')
    manager = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='direct_reports')
    department = models.CharField(max_length=100, blank=True)
    job_title = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    profile_photo = models.ImageField(upload_to="avatars/%Y/%m/", blank=True, null=True)
    google_sub = models.CharField(max_length=255, unique=True, null=True, blank=True)
    permissions = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} · {self.get_role_display()}'


class ClientAssignment(models.Model):
    client = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name='assignments')
    employee = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='client_assignments')
    assigned_by = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='assignments_created')
    role_title = models.CharField(max_length=120, blank=True, default='Account team')
    is_primary = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['client','employee'], name='unique_client_employee_assignment')]
        ordering = ['client__name','employee__user__first_name']

    def __str__(self):
        return f'{self.employee} → {self.client}'


class Project(models.Model):
    STATUS = [('planned','Planned'),('active','Active'),('on_hold','On hold'),('completed','Completed')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name='projects')
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='planned')
    manager = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='managed_projects')
    owner = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='owned_projects')
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    progress = models.PositiveSmallIntegerField(default=0)
    group_name = models.CharField(max_length=100, blank=True)
    tags = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='projects_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']


class Task(models.Model):
    STATUS = [('todo','To do'),('in_progress','In progress'),('review','In review'),('blocked','Blocked'),('completed','Completed')]
    PRIORITY = [('low','Low'),('normal','Normal'),('high','High'),('urgent','Urgent')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name='tasks')
    project = models.ForeignKey(Project, null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='subtasks')
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='todo')
    priority = models.CharField(max_length=20, choices=PRIORITY, default='normal')
    assigned_to = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks_assigned')
    created_by = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks_created')
    start_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    estimated_hours = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    recurrence = models.CharField(max_length=80, blank=True)
    client_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    percent_complete = models.PositiveSmallIntegerField(default=0)
    billing_type = models.CharField(max_length=15, choices=[('billable','Billable'),('nonbillable','Non-billable')], default='billable')
    task_list = models.ForeignKey('ProjectTaskList', null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks')
    assignees = models.ManyToManyField(Member, blank=True, related_name='coassigned_tasks')

    blocked_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='dependent_tasks')
    tags = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['status','due_at','-updated_at']
        indexes = [models.Index(fields=['client', 'status', 'due_at'], name='tf_task_status_due_idx')]


class Update(models.Model):
    VISIBILITY = [('client','Client + team'),('team','Internal team only')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name='updates')
    task = models.ForeignKey(Task, null=True, blank=True, on_delete=models.SET_NULL, related_name='updates')
    author = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='updates_authored')
    title = models.CharField(max_length=220)
    body = models.TextField()
    visibility = models.CharField(max_length=20, choices=VISIBILITY, default='client')
    progress = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


class Note(models.Model):
    VISIBILITY = [('client','Client + team'),('team','Internal team only'),('private','Private')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name='notes')
    project = models.ForeignKey(Project, null=True, blank=True, on_delete=models.SET_NULL, related_name='notes')
    task = models.ForeignKey(Task, null=True, blank=True, on_delete=models.SET_NULL, related_name='notes')
    author = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='notes_authored')
    body = models.TextField()
    visibility = models.CharField(max_length=20, choices=VISIBILITY, default='team')
    pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-pinned','-created_at']


class CalendarEvent(models.Model):
    TYPE = [('meeting','Meeting'),('deadline','Deadline'),('shoot','Shoot'),('review','Review'),('reminder','Reminder'),('other','Other')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(ClientAccount, null=True, blank=True, on_delete=models.CASCADE, related_name='events')
    title = models.CharField(max_length=220)
    event_type = models.CharField(max_length=20, choices=TYPE, default='meeting')
    description = models.TextField(blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(null=True, blank=True)
    owner = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='events_owned')
    attendees = models.ManyToManyField(Member, blank=True, related_name='events_attending')
    created_by = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='events_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_at']


class Notification(models.Model):
    recipient = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='crm_notifications')
    client = models.ForeignKey(ClientAccount, null=True, blank=True, on_delete=models.CASCADE, related_name='crm_notifications')
    title = models.CharField(max_length=220)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=400, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']


class ActivityLog(models.Model):
    actor = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='activities')
    client = models.ForeignKey(ClientAccount, null=True, blank=True, on_delete=models.SET_NULL, related_name='activities')
    action = models.CharField(max_length=120)
    entity_type = models.CharField(max_length=80, blank=True)
    entity_id = models.CharField(max_length=80, blank=True)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Record(models.Model):
    id = models.CharField(max_length=160, primary_key=True)
    space = models.CharField(max_length=180, db_index=True)
    kind = models.CharField(max_length=40, db_index=True)
    client = models.CharField(max_length=120, db_index=True)
    data = models.JSONField(default=dict)
    attachment = models.FileField(upload_to='uploads/%Y/%m/', blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['space','kind','client'])]

    def __str__(self):
        return f'{self.kind}: {self.data.get("title", self.id)}'


# Structured operations. Unlike legacy JSON records, these rows support relational
# permissions, time accounting, manager review, and efficient filtered queries.
class Attendance(models.Model):
    MODE = [('office', 'Office'), ('remote', 'Remote'), ('field', 'Field work')]
    employee = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='attendance_days')
    date = models.DateField(db_index=True)
    clock_in = models.DateTimeField()
    clock_out = models.DateTimeField(null=True, blank=True)
    break_started_at = models.DateTimeField(null=True, blank=True)
    break_seconds = models.PositiveIntegerField(default=0)
    mode = models.CharField(max_length=12, choices=MODE, default='office')
    note = models.CharField(max_length=400, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-clock_in']
        constraints = [models.UniqueConstraint(fields=['employee', 'date'], name='tf_attendance_employee_date')]
        indexes = [models.Index(fields=['date', 'employee'], name='tf_attendance_day_emp_idx')]

    @property
    def worked_seconds(self):
        end = self.clock_out or timezone.now()
        breaks = self.break_seconds
        if self.break_started_at:
            breaks += max(0, int((end - self.break_started_at).total_seconds()))
        return max(0, int((end - self.clock_in).total_seconds()) - breaks)


class LeaveRequest(models.Model):
    TYPE = [('annual', 'Annual'), ('sick', 'Sick'), ('casual', 'Casual'), ('unpaid', 'Unpaid'), ('other', 'Other')]
    STATUS = [('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=12, choices=TYPE, default='annual')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default='pending', db_index=True)
    reviewed_by = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True, related_name='leaves_reviewed')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['employee', 'status', 'start_date'], name='tf_leave_emp_status_idx')]


class TimeEntry(models.Model):
    STATUS = [('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'), ('rejected', 'Rejected')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='time_entries')
    client = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name='time_entries')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='time_entries')
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='time_entries')
    date = models.DateField(db_index=True)
    minutes = models.PositiveIntegerField()
    description = models.CharField(max_length=500, blank=True)
    billable = models.BooleanField(default=True)
    status = models.CharField(max_length=12, choices=STATUS, default='draft', db_index=True)
    reviewed_by = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True, related_name='time_entries_reviewed')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [models.Index(fields=['employee', 'date'], name='tf_time_employee_day_idx'), models.Index(fields=['client', 'status'], name='tf_time_client_state_idx')]


class ApprovalRequest(models.Model):
    STATUS = [('pending', 'Pending'), ('approved', 'Approved'), ('changes', 'Changes requested'), ('rejected', 'Rejected')]
    AUDIENCE = [('client', 'Client approval'), ('internal', 'Internal approval')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name='approval_requests')
    project = models.ForeignKey(Project, null=True, blank=True, on_delete=models.SET_NULL, related_name='approval_requests')
    task = models.ForeignKey(Task, null=True, blank=True, on_delete=models.SET_NULL, related_name='approval_requests')
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    audience = models.CharField(max_length=12, choices=AUDIENCE, default='client')
    status = models.CharField(max_length=12, choices=STATUS, default='pending', db_index=True)
    requested_by = models.ForeignKey(Member, null=True, on_delete=models.SET_NULL, related_name='approvals_requested')
    reviewer = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='approvals_assigned')
    due_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    decided_by = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='approvals_decided')
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['client', 'audience', 'status'], name='tf_approval_scope_idx')]


class SupportTicket(models.Model):
    PRIORITY = [('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')]
    STATUS = [('open', 'Open'), ('in_progress', 'In progress'), ('waiting_client', 'Waiting on client'), ('resolved', 'Resolved'), ('closed', 'Closed')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name='support_tickets')
    project = models.ForeignKey(Project, null=True, blank=True, on_delete=models.SET_NULL, related_name='support_tickets')
    title = models.CharField(max_length=220)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS, default='open', db_index=True)
    priority = models.CharField(max_length=12, choices=PRIORITY, default='normal')
    created_by = models.ForeignKey(Member, null=True, on_delete=models.SET_NULL, related_name='tickets_created')
    assigned_to = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='tickets_assigned')
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [models.Index(fields=['client', 'status', 'updated_at'], name='tf_ticket_client_state_idx')]


class TicketMessage(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(Member, null=True, on_delete=models.SET_NULL, related_name='ticket_messages')
    body = models.TextField()
    internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class ProjectMilestone(models.Model):
    STATUS = [('planned', 'Planned'), ('active', 'In progress'), ('completed', 'Completed')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default='planned')
    owner = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='milestones_owned')
    client_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['due_date', 'created_at']


class SavedView(models.Model):
    owner = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='saved_views')
    name = models.CharField(max_length=80)
    module = models.CharField(max_length=30, default='tasks')
    filters = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        constraints = [models.UniqueConstraint(fields=['owner', 'module', 'name'], name='tf_unique_personal_view')]


class Lead(models.Model):
    STAGES = [('new', 'New'), ('contacted', 'Contacted'), ('qualified', 'Qualified'), ('proposal', 'Proposal'), ('negotiation', 'Negotiation'), ('won', 'Won'), ('lost', 'Lost')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    company = models.CharField(max_length=180, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    source = models.CharField(max_length=100, blank=True)
    stage = models.CharField(max_length=15, choices=STAGES, default='new', db_index=True)
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    owner = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='sales_leads')
    converted_client = models.ForeignKey(ClientAccount, null=True, blank=True, on_delete=models.SET_NULL, related_name='source_leads')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [models.Index(fields=['stage', 'owner'], name='tf_lead_stage_owner_idx')]


# Project operations: each object is backed by a relational client-scoped model.
# These power task lists, threaded project feeds, issues, documents and widgets.
class ProjectTaskList(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='task_lists')
    title = models.CharField(max_length=120)
    position = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'created_at']
        constraints = [models.UniqueConstraint(fields=['project', 'title'], name='tf_unique_project_task_list')]


class ProjectTeam(models.Model):
    ROLE = [('lead', 'Project lead'), ('contributor', 'Contributor'), ('observer', 'Observer')]
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='team_memberships')
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='project_memberships')
    role = models.CharField(max_length=16, choices=ROLE, default='contributor')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['project', 'member'], name='tf_unique_project_team')]


class ProjectIssue(models.Model):
    STATUS = [('open', 'Open'), ('in_progress', 'In progress'), ('resolved', 'Resolved'), ('closed', 'Closed')]
    PRIORITY = [('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('critical', 'Critical')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='issues')
    client = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name='project_issues')
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='project_issues')
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='open', db_index=True)
    priority = models.CharField(max_length=12, choices=PRIORITY, default='normal')
    reported_by = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True, related_name='issues_reported')
    assigned_to = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True, related_name='issues_assigned')
    due_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    client_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [models.Index(fields=['project', 'status'], name='tf_issue_project_status_idx')]


class ProjectDiscussion(models.Model):
    VISIBILITY = [('client', 'Client and team'), ('team', 'Internal team')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='discussions')
    author = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True, related_name='project_posts')
    body = models.TextField()
    visibility = models.CharField(max_length=12, choices=VISIBILITY, default='client')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [models.Index(fields=['project', 'created_at'], name='tf_feed_project_time_idx')]


class ProjectDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='documents')
    uploaded_by = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True, related_name='project_uploads')
    title = models.CharField(max_length=220)
    attachment = models.FileField(upload_to='project_documents/%Y/%m/')
    size_bytes = models.PositiveIntegerField(default=0)
    client_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class DashboardLayout(models.Model):
    owner = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='dashboard_layouts')
    # 'global' or 'project:<project UUID>'
    scope = models.CharField(max_length=60, default='global')
    widgets = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner', 'scope'], name='tf_unique_dashboard_layout')]

# The collaboration models live in their own module but are registered through
# this standard Django models entrypoint for migrations and admin discovery.
from .collaboration_models import ChatConversation, ChatParticipant, ChatMessage, RecentProjectVisit

# Billing models live in their own module to keep the workspace model file manageable.
from .billing_models import BillingProfile, InvoiceSequence, BillingSchedule, Invoice, InvoiceLine, InvoicePayment  # noqa: E402,F401
