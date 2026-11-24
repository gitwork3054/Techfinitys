"""Browser push notification subscriptions."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('workspace', '0007_zoho_task_details')]

    operations = [
        migrations.CreateModel(
            name='PushSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.URLField(max_length=2048, unique=True)),
                ('keys', models.JSONField(default=dict)),
                ('session_key', models.CharField(blank=True, db_index=True, max_length=60)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                     related_name='push_subscriptions', to='workspace.member')),
            ],
            options={'indexes':[models.Index(fields=['member', 'updated_at'], name='tf_push_member_idx')]},
        ),
    ]
