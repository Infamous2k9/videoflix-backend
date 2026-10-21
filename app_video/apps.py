"""App configuration of the video app."""

from django.apps import AppConfig


class AppVideoConfig(AppConfig):
    """Configuration that registers the signals of the video app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "app_video"

    def ready(self):
        """Import the signals so their receivers are connected."""
        from . import signals  # noqa: F401
