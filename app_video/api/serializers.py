"""Serializers of the video API."""

from rest_framework import serializers

from ..models import Video


class VideoSerializer(serializers.ModelSerializer):
    """Metadata of a video for the dashboard."""

    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = [
            "id",
            "created_at",
            "title",
            "description",
            "thumbnail_url",
            "category",
        ]

    def get_thumbnail_url(self, obj):
        """Return the absolute URL of the thumbnail, or ``None`` if there is none."""
        if not obj.thumbnail:
            return None
        return self.context["request"].build_absolute_uri(obj.thumbnail.url)
