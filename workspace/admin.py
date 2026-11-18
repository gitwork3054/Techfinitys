from django.contrib import admin
from .models import (
    Member, Record, ClientAccount, ClientAssignment, Project, Task, Update,
    Note, CalendarEvent, Notification, ActivityLog
)

@admin.register(ClientAccount)
class ClientAccountAdmin(admin.ModelAdmin):
    list_display=('name','code','status','package','email','updated_at')
    list_filter=('status',)
    search_fields=('name','code','email','company')

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display=('user','role','department','job_title','manager','client_account','is_active')
    list_filter=('role','department','is_active')
    search_fields=('user__username','user__first_name','user__last_name','user__email','job_title')

@admin.register(ClientAssignment)
class ClientAssignmentAdmin(admin.ModelAdmin):
    list_display=('client','employee','role_title','is_primary','active','assigned_by')
    list_filter=('active','is_primary')

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display=('title','client','status','owner','manager','progress','due_date')
    list_filter=('status','client')
    search_fields=('title','description')

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display=('title','client','status','priority','assigned_to','due_at','client_visible')
    list_filter=('status','priority','client','client_visible')
    search_fields=('title','description')

@admin.register(Update)
class UpdateAdmin(admin.ModelAdmin):
    list_display=('title','client','author','visibility','progress','created_at')
    list_filter=('visibility','client')

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display=('client','author','visibility','pinned','created_at')
    list_filter=('visibility','pinned','client')

@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display=('title','client','event_type','owner','start_at','end_at')
    list_filter=('event_type','client')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display=('recipient','client','title','created_at','read_at')

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display=('created_at','actor','client','action','entity_type','entity_id')
    list_filter=('action','entity_type')

@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):
    list_display=('id','space','kind','client','updated_at')
    list_filter=('space','kind','client')
    search_fields=('id','data')

# Typed operational modules are also available to trusted Django staff.
from .models import (
    Attendance, LeaveRequest, TimeEntry, ApprovalRequest, SupportTicket,
    TicketMessage, ProjectMilestone, SavedView, Lead
)

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display=('employee','date','clock_in','clock_out','mode','break_seconds')
    list_filter=('date','mode')
    search_fields=('employee__user__username','employee__user__first_name')

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display=('employee','leave_type','start_date','end_date','status','reviewed_by')
    list_filter=('status','leave_type')

@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display=('employee','client','date','minutes','billable','status')
    list_filter=('status','client','billable')

@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display=('title','client','audience','status','requested_by','reviewer','created_at')
    list_filter=('audience','status','client')
    search_fields=('title','description')

class TicketMessageInline(admin.TabularInline):
    model=TicketMessage
    extra=0

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display=('title','client','status','priority','created_by','assigned_to','updated_at')
    list_filter=('status','priority','client')
    inlines=[TicketMessageInline]

@admin.register(ProjectMilestone)
class ProjectMilestoneAdmin(admin.ModelAdmin):
    list_display=('title','project','status','due_date','client_visible')
    list_filter=('status','client_visible')

@admin.register(SavedView)
class SavedViewAdmin(admin.ModelAdmin):
    list_display=('owner','name','module','created_at')

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display=('name','company','stage','estimated_value','owner','converted_client')
    list_filter=('stage',)
    search_fields=('name','company','email')


from .models import (ProjectTaskList, ProjectTeam, ProjectIssue, ProjectDiscussion,
                     ProjectDocument, DashboardLayout)

@admin.register(ProjectTaskList)
class ProjectTaskListAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'position', 'created_at')
    search_fields = ('title', 'project__title')

@admin.register(ProjectTeam)
class ProjectTeamAdmin(admin.ModelAdmin):
    list_display = ('project', 'member', 'role', 'created_at')
    list_filter = ('role',)

@admin.register(ProjectIssue)
class ProjectIssueAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'status', 'priority', 'assigned_to', 'updated_at')
    list_filter = ('status', 'priority', 'client_visible')
    search_fields = ('title', 'description', 'project__title')

@admin.register(ProjectDiscussion)
class ProjectDiscussionAdmin(admin.ModelAdmin):
    list_display = ('project', 'author', 'visibility', 'created_at')
    list_filter = ('visibility',)

@admin.register(ProjectDocument)
class ProjectDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'uploaded_by', 'client_visible', 'created_at')
    list_filter = ('client_visible',)

@admin.register(DashboardLayout)
class DashboardLayoutAdmin(admin.ModelAdmin):
    list_display = ('owner', 'scope', 'updated_at')
