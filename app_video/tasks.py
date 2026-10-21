"""Background jobs of the video app, executed by the RQ worker."""

import subprocess

from .models import Video
from .utils import create_hls_streams, create_thumbnail


def update_video(video_id, **fields):
    """Update fields without calling ``save()``, so no signal is sent."""
    Video.objects.filter(pk=video_id).update(**fields)


def convert_video(video_id):
    """Create the HLS streams and the thumbnail of a video."""
    video = Video.objects.get(pk=video_id)
    update_video(video_id, status=Video.Status.PROCESSING)
    try:
        create_hls_streams(video)
        thumbnail = create_thumbnail(video)
    except subprocess.CalledProcessError:
        update_video(video_id, status=Video.Status.FAILED)
        raise
    update_video(video_id, status=Video.Status.READY, thumbnail=thumbnail)
