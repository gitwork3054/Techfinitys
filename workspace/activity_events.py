"""Fan out staff audit events to Super Admin in-app notifications.

Never copy private chat message bodies to notifications. Notifications share the
ActivityLog transaction, so rolled-back writes cannot create phantom alerts.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ActivityLog, Member, Notification


@receiver(post_save, sender=ActivityLog, dispatch_uid='tf_admin_audit_alert')
def inform_super_admin(sender, instance, created, **kwargs):
    if not created or not instance.actor_id:
        return
    if instance.actor.role not in ('employee', 'manager'):
        return
    # Track messaging metadata in the audit feed without flooding an admin's
    # bell for each private chat message. Full content is never logged.
    if instance.action == 'Sent internal chat message':
        return
    admins = Member.objects.filter(role='admin', is_active=True, user__is_active=True).exclude(pk=instance.actor_id)
    name = instance.actor.user.get_full_name() or instance.actor.user.username
    # A concise headline prevents notification bodies from inadvertently
    # reproducing confidential task discussions or direct messages.
    Notification.objects.bulk_create([
        Notification(recipient_id=pk, client=instance.client,
                     title=f'{name}: {instance.action}'[:220],
                     body=instance.detail[:500], link='#admin_activity')
        for pk in admins.values_list('pk', flat=True)
    ])
