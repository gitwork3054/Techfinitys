"""Relational, staff-only conversations and per-user project history.

Imported from models.py to keep CRM schema organized and prevent client chat leaks.
"""
import uuid
from django.db import models
from django.utils import timezone


class ChatConversation(models.Model):
    KINDS = [('direct', 'Direct message'), ('group', 'Group')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=12, choices=KINDS, default='direct')
    title = models.CharField(max_length=100, blank=True)
    # Direct pairs have exactly one thread, irrespective of who starts first.
    direct_key = models.CharField(max_length=80, blank=True, null=True, unique=True)
    created_by = models.ForeignKey('workspace.Member', on_delete=models.SET_NULL, null=True, related_name='created_chats')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-updated_at']


class ChatParticipant(models.Model):
    conversation = models.ForeignKey(ChatConversation, on_delete=models.CASCADE, related_name='participants')
    member = models.ForeignKey('workspace.Member', on_delete=models.CASCADE, related_name='chat_memberships')
    joined_at = models.DateTimeField(default=timezone.now)
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['conversation', 'member'], name='tf_unique_chat_member')]
        indexes = [models.Index(fields=['member', 'conversation'], name='tf_chat_participant_idx')]


class ChatMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(ChatConversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey('workspace.Member', on_delete=models.PROTECT, related_name='chat_messages')
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['created_at', 'id']
        indexes = [models.Index(fields=['conversation', 'created_at'], name='tf_chat_messages_idx')]


class RecentProjectVisit(models.Model):
    member = models.ForeignKey('workspace.Member', on_delete=models.CASCADE, related_name='recent_projects')
    project = models.ForeignKey('workspace.Project', on_delete=models.CASCADE, related_name='recent_visitors')
    visited_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['member','project'], name='tf_unique_recent_project')]
        indexes = [models.Index(fields=['member', '-visited_at'], name='tf_recent_project_idx')]
        ordering = ['-visited_at']
