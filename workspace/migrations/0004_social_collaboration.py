# Generated for Techfinitys CRM: staff chat, photo profiles and recent projects.
import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('workspace', '0003_project_workspaces')]
    operations = [
        migrations.AddField(model_name='member', name='profile_photo', field=models.ImageField(blank=True, null=True, upload_to='avatars/%Y/%m/')),
        migrations.AddField(model_name='member', name='google_sub', field=models.CharField(blank=True, max_length=255, null=True, unique=True)),
        migrations.CreateModel(name='ChatConversation', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('kind', models.CharField(max_length=12, choices=[('direct','Direct message'),('group','Group')], default='direct')),
            ('title', models.CharField(blank=True,max_length=100)),
            ('direct_key', models.CharField(blank=True,null=True,max_length=80,unique=True)),
            ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ('updated_at', models.DateTimeField(default=django.utils.timezone.now,db_index=True)),
            ('created_by', models.ForeignKey(to='workspace.member',related_name='created_chats',null=True,on_delete=django.db.models.deletion.SET_NULL)),
        ], options={'ordering':['-updated_at']}),
        migrations.CreateModel(name='ChatParticipant', fields=[
            ('id', models.BigAutoField(primary_key=True,serialize=False)),
            ('joined_at', models.DateTimeField(default=django.utils.timezone.now)),
            ('last_read_at', models.DateTimeField(blank=True,null=True)),
            ('conversation', models.ForeignKey(to='workspace.chatconversation',related_name='participants',on_delete=django.db.models.deletion.CASCADE)),
            ('member', models.ForeignKey(to='workspace.member',related_name='chat_memberships',on_delete=django.db.models.deletion.CASCADE)),
        ]),
        migrations.CreateModel(name='ChatMessage', fields=[
            ('id', models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,serialize=False)),
            ('body', models.TextField(max_length=4000)),
            ('created_at', models.DateTimeField(default=django.utils.timezone.now,db_index=True)),
            ('conversation', models.ForeignKey(to='workspace.chatconversation',related_name='messages',on_delete=django.db.models.deletion.CASCADE)),
            ('sender', models.ForeignKey(to='workspace.member',related_name='chat_messages',on_delete=django.db.models.deletion.PROTECT)),
        ], options={'ordering':['created_at','id']}),
        migrations.CreateModel(name='RecentProjectVisit', fields=[
            ('id', models.BigAutoField(primary_key=True,serialize=False)),
            ('visited_at', models.DateTimeField(auto_now=True)),
            ('member', models.ForeignKey(to='workspace.member',related_name='recent_projects',on_delete=django.db.models.deletion.CASCADE)),
            ('project', models.ForeignKey(to='workspace.project',related_name='recent_visitors',on_delete=django.db.models.deletion.CASCADE)),
        ], options={'ordering':['-visited_at']}),
        migrations.AddConstraint(model_name='chatparticipant',constraint=models.UniqueConstraint(fields=('conversation','member'),name='tf_unique_chat_member')),
        migrations.AddIndex(model_name='chatparticipant',index=models.Index(fields=['member','conversation'],name='tf_chat_participant_idx')),
        migrations.AddIndex(model_name='chatmessage',index=models.Index(fields=['conversation','created_at'],name='tf_chat_messages_idx')),
        migrations.AddConstraint(model_name='recentprojectvisit',constraint=models.UniqueConstraint(fields=('member','project'),name='tf_unique_recent_project')),
        migrations.AddIndex(model_name='recentprojectvisit',index=models.Index(fields=['member','-visited_at'],name='tf_recent_project_idx')),
    ]
