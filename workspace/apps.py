from django.apps import AppConfig


class WorkspaceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'workspace'

    def ready(self):
        # Register once per app instance; dispatch_uid guards duplicate imports.
        from . import activity_events  # noqa: F401
        from . import push_notifications  # noqa: F401
