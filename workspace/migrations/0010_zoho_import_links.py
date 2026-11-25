from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('workspace', '0009_project_discussion_photo')]

    operations = [
        migrations.CreateModel(
            name='ZohoProjectLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('portal_id', models.CharField(max_length=32)),
                ('zoho_project_id', models.CharField(max_length=64)),
                ('imported_at', models.DateTimeField(auto_now_add=True)),
                ('imported_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='workspace.member')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='zoho_links', to='workspace.project')),
            ],
            options={'constraints': [models.UniqueConstraint(fields=('portal_id', 'zoho_project_id'), name='tf_unique_zoho_project')]},
        ),
    ]
