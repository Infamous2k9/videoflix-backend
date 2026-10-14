"""Admin configuration for the custom user model."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin for the custom user model.

    Inherits the layout of Django's ``UserAdmin``: list, search, filters,
    the "add user" form and the password change form.

    To show custom fields, extend the inherited ``fieldsets`` (edit page)
    and, if needed, ``add_fieldsets`` (add page), e.g.:

        fieldsets = BaseUserAdmin.fieldsets + (
            ("Profile", {"fields": ("avatar",)}),
        )
        add_fieldsets = BaseUserAdmin.add_fieldsets + (
            ("Profile", {"fields": ("avatar",)}),
        )

    New columns in the user list go into ``list_display``, e.g.:

        list_display = BaseUserAdmin.list_display + ("avatar",)
    """
