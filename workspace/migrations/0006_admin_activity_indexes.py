from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('workspace', '0005_invoice_billing')]
    operations = [
        migrations.AddIndex(model_name='notification', index=models.Index(fields=['recipient', 'read_at'], name='tf_notif_unread_idx')),
        migrations.AddIndex(model_name='activitylog', index=models.Index(fields=['-created_at'], name='tf_activity_latest_idx')),
        migrations.AddIndex(model_name='activitylog', index=models.Index(fields=['actor', '-created_at'], name='tf_activity_actor_idx')),
    ]
