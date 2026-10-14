"""App configuration of ``app_auth``."""

from django.apps import AppConfig


class AppAuthConfig(AppConfig):
    """Custom user model and the authentication API (``app_auth.api``)."""

    name = "app_auth"
