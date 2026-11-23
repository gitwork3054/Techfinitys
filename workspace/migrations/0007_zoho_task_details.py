"""Task comments and checklists used by Project Studio task details."""
import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('workspace', '0006_admin_activity_indexes')]

    operations = [
        migrations.CreateModel(
            name='TaskComment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('body', models.TextField()),
                ('is_internal', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('author', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_comments', to='workspace.member')),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_comments', to='workspace.clientaccount')),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='workspace.task')),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.CreateModel(
            name='TaskChecklistItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=240)),
                ('done', models.BooleanField(default=False)),
                ('position', models.PositiveSmallIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='checklist_created', to='workspace.member')),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='checklist', to='workspace.task')),
            ],
            options={'ordering': ['position', 'pk']},
        ),
        migrations.AddIndex(model_name='taskcomment', index=models.Index(fields=['task', 'created_at'], name='tf_tcomment_task_time')),
        migrations.AddIndex(model_name='taskchecklistitem', index=models.Index(fields=['task', 'position'], name='tf_checklist_task_pos')),
    ]
