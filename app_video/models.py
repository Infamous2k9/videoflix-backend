"""Models of the video app."""

from django.db import models


class Video(models.Model):
    """A video that is converted to HLS streams in several resolutions."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    title = models.CharField(max_length=100)
    description = models.TextField()
    category = models.CharField(max_length=50)
    video_file = models.FileField(upload_to="videos/originals/")
    thumbnail = models.FileField(upload_to="thumbnails/", blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Video"
        verbose_name_plural = "Videos"

    def __str__(self):
        return self.title
