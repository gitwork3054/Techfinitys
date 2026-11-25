"""Unique provenance mapping for one-way Zoho Projects imports."""
from django.db import models


class ZohoProjectLink(models.Model):
    portal_id = models.CharField(max_length=32)
    zoho_project_id = models.CharField(max_length=64)
    project = models.ForeignKey('workspace.Project', on_delete=models.CASCADE, related_name='zoho_links')
    imported_by = models.ForeignKey('workspace.Member', null=True, on_delete=models.SET_NULL)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['portal_id', 'zoho_project_id'], name='tf_unique_zoho_project')
        ]
