"""Admin configuration of the video app."""

from django.contrib import admin

from .models import Video


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    """Upload videos and follow their conversion status."""

    list_display = ("title", "category", "status", "created_at")
    list_filter = ("status", "category")
    search_fields = ("title", "description")
    readonly_fields = ("status", "thumbnail", "created_at")
