from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('workspace', '0008_push_subscriptions')]

    operations = [
        migrations.AddField(
            model_name='projectdiscussion',
            name='photo',
            field=models.ImageField(blank=True, null=True, upload_to='project_feed/%Y/%m/'),
        ),
    ]
