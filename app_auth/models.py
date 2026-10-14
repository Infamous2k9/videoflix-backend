"""
Custom user model and manager.

Behaves like Django's default user: login with username and password.
Using a custom model from the start allows adding fields later without
rebuilding the database.

How to extend the model:
1. Add fields to the User class, e.g.
       avatar = models.ImageField(upload_to="avatars/", blank=True)
2. Create and apply the migration:
       python manage.py makemigrations app_auth
       python manage.py migrate
3. Show the new fields in the admin: app_auth/admin.py, extend `fieldsets`
   in the UserAdmin class.
4. Expose the new fields in the API: app_auth/api/serializers.py (`fields`).

Note: switching to a different user model after the first migration is
costly, which is why this model exists from the start.
"""

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager


class UserManager(DjangoUserManager):
    """Manager for the custom user model.

    Inherits everything from Django's ``UserManager``:
    ``create_user(username, email=None, password=None, **extra_fields)`` and
    ``create_superuser(username, email=None, password=None, **extra_fields)``.
    Both hash the password and normalize the email address.

    Override methods here to change how users are created, e.g. to set
    default values for new fields.
    """


class User(AbstractUser):
    """User that logs in with username.

    All fields come from ``AbstractUser``: ``username``, ``email``,
    ``first_name``, ``last_name``, ``password``, ``is_active``, ``is_staff``,
    ``is_superuser``, ``last_login``, ``date_joined``, ``groups`` and
    ``user_permissions``.
    """

    objects = UserManager()
