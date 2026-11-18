# Additive project workspace features; keeps existing project and task IDs intact.
import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('workspace', '0002_operations')]

    operations = [
        migrations.AddField(
            model_name='project', name='group_name',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='project', name='tags',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.CreateModel(
            name='ProjectTaskList', fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ('title', models.CharField(max_length=120)),
                ('position', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='workspace.member')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_lists', to='workspace.project')),
            ],
            options={'ordering': ['position', 'created_at']},
        ),
        migrations.AddConstraint(
            model_name='projecttasklist',
            constraint=models.UniqueConstraint(fields=('project', 'title'), name='tf_unique_project_task_list'),
        ),
        migrations.AddField(
            model_name='task', name='task_list',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tasks', to='workspace.projecttasklist'),
        ),
        migrations.AddField(
            model_name='task', name='assignees',
            field=models.ManyToManyField(blank=True, related_name='coassigned_tasks', to='workspace.member'),
        ),
        migrations.AddField(
            model_name='task', name='percent_complete',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='task', name='billing_type',
            field=models.CharField(choices=[('billable', 'Billable'), ('nonbillable', 'Non-billable')], default='billable', max_length=15),
        ),
        migrations.CreateModel(
            name='ProjectTeam', fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('role', models.CharField(choices=[('lead', 'Project lead'), ('contributor', 'Contributor'), ('observer', 'Observer')], default='contributor', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_memberships', to='workspace.member')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='team_memberships', to='workspace.project')),
            ],
        ),
        migrations.AddConstraint(
            model_name='projectteam',
            constraint=models.UniqueConstraint(fields=('project', 'member'), name='tf_unique_project_team'),
        ),
        migrations.CreateModel(
            name='ProjectIssue', fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ('title', models.CharField(max_length=220)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('open', 'Open'), ('in_progress', 'In progress'), ('resolved', 'Resolved'), ('closed', 'Closed')], db_index=True, default='open', max_length=20)),
                ('priority', models.CharField(choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('critical', 'Critical')], default='normal', max_length=12)),
                ('due_at', models.DateTimeField(blank=True, null=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('client_visible', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='issues_assigned', to='workspace.member')),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_issues', to='workspace.clientaccount')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='issues', to='workspace.project')),
                ('reported_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='issues_reported', to='workspace.member')),
                ('task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='project_issues', to='workspace.task')),
            ],
            options={'ordering': ['-updated_at']},
        ),
        migrations.AddIndex(
            model_name='projectissue', index=models.Index(fields=['project', 'status'], name='tf_issue_project_status_idx'),
        ),
        migrations.CreateModel(
            name='ProjectDiscussion', fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ('body', models.TextField()),
                ('visibility', models.CharField(choices=[('client', 'Client and team'), ('team', 'Internal team')], default='client', max_length=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('author', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='project_posts', to='workspace.member')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='replies', to='workspace.projectdiscussion')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='discussions', to='workspace.project')),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.AddIndex(
            model_name='projectdiscussion', index=models.Index(fields=['project', 'created_at'], name='tf_feed_project_time_idx'),
        ),
        migrations.CreateModel(
            name='ProjectDocument', fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ('title', models.CharField(max_length=220)),
                ('attachment', models.FileField(upload_to='project_documents/%Y/%m/')),
                ('size_bytes', models.PositiveIntegerField(default=0)),
                ('client_visible', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='workspace.project')),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='project_uploads', to='workspace.member')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='DashboardLayout', fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('scope', models.CharField(default='global', max_length=60)),
                ('widgets', models.JSONField(default=list)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dashboard_layouts', to='workspace.member')),
            ],
        ),
        migrations.AddConstraint(
            model_name='dashboardlayout',
            constraint=models.UniqueConstraint(fields=('owner', 'scope'), name='tf_unique_dashboard_layout'),
        ),
    ]
