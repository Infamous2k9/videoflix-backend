"""Signals that start the video conversion and clean up the files."""

import django_rq
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Video
from .tasks import convert_video
from .utils import delete_video_files

CONVERSION_QUEUE = "low"


@receiver(post_save, sender=Video)
def queue_conversion(sender, instance, created, **kwargs):
    """Queue the conversion of a new video once it is saved."""
    if not created:
        return
    queue = django_rq.get_queue(CONVERSION_QUEUE)
    transaction.on_commit(lambda: queue.enqueue(convert_video, instance.id))


@receiver(post_delete, sender=Video)
def remove_video_files(sender, instance, **kwargs):
    """Delete all files of a video when it is deleted."""
    delete_video_files(instance)
