"""Additive task-detail collaboration models.

A task's client ownership is deliberately duplicated on comments for efficient
scoping/auditing, and is verified against the task on every write.
"""
import uuid
from django.db import models


class TaskComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey('workspace.Task', on_delete=models.CASCADE, related_name='comments')
    client = models.ForeignKey('workspace.ClientAccount', on_delete=models.CASCADE, related_name='task_comments')
    author = models.ForeignKey('workspace.Member', on_delete=models.SET_NULL, null=True, related_name='task_comments')
    body = models.TextField()
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [models.Index(fields=['task', 'created_at'], name='tf_tcomment_task_time')]


class TaskChecklistItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey('workspace.Task', on_delete=models.CASCADE, related_name='checklist')
    title = models.CharField(max_length=240)
    done = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(default=0)
    created_by = models.ForeignKey('workspace.Member', null=True, on_delete=models.SET_NULL, related_name='checklist_created')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'pk']
        indexes = [models.Index(fields=['task', 'position'], name='tf_checklist_task_pos')]
