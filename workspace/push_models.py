"""Per-browser Web Push subscriptions, separated by authenticated CRM member."""
from django.db import models


class PushSubscription(models.Model):
    member = models.ForeignKey('workspace.Member', on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.URLField(max_length=2048, unique=True)
    keys = models.JSONField(default=dict)
    session_key = models.CharField(max_length=60, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['member', 'updated_at'], name='tf_push_member_idx')]
