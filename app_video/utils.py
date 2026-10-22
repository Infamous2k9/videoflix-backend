"""Helpers that convert videos with FFmpeg and manage the created files."""

import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.http import Http404

RESOLUTIONS = {"480p": 480, "720p": 720, "1080p": 1080}
HLS_SEGMENT_SECONDS = 10


def get_video_dir(video_id):
    """Return the folder that holds all HLS files of one video."""
    return Path(settings.MEDIA_ROOT) / "videos" / str(video_id)


def get_hls_dir(video_id, resolution):
    """Return the folder of the HLS files of one video and resolution."""
    return get_video_dir(video_id) / resolution


def build_hls_command(source, output_dir, height):
    """Return the FFmpeg command that creates the HLS stream of one resolution."""
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-vf",
        f"scale=-2:{height}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-hls_time",
        str(HLS_SEGMENT_SECONDS),
        "-hls_playlist_type",
        "vod",
        "-hls_segment_filename",
        str(output_dir / "%03d.ts"),
        str(output_dir / "index.m3u8"),
    ]


def create_hls_streams(video):
    """Create the HLS stream of every resolution in ``RESOLUTIONS``."""
    for resolution, height in RESOLUTIONS.items():
        output_dir = get_hls_dir(video.id, resolution)
        output_dir.mkdir(parents=True, exist_ok=True)
        command = build_hls_command(video.video_file.path, output_dir, height)
        subprocess.run(command, check=True, capture_output=True)


def create_thumbnail(video):
    """Save a frame after one second as thumbnail and return its media path."""
    relative_path = f"thumbnails/{video.id}.jpg"
    output = Path(settings.MEDIA_ROOT) / relative_path
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        video.video_file.path,
        "-ss",
        "00:00:01",
        "-frames:v",
        "1",
        "-vf",
        "scale=-2:360",
        str(output),
    ]
    subprocess.run(command, check=True, capture_output=True)
    return relative_path


def delete_video_files(video):
    """Delete the original, the thumbnail and all HLS files of a video."""
    video.video_file.delete(save=False)
    video.thumbnail.delete(save=False)
    shutil.rmtree(get_video_dir(video.id), ignore_errors=True)


def get_hls_file(video_id, resolution, filename):
    """Return the path of an HLS file.

    Raises:
        Http404: The resolution is unknown or the file does not exist.
    """
    if resolution not in RESOLUTIONS:
        raise Http404
    path = get_hls_dir(video_id, resolution) / filename
    if not path.is_file():
        raise Http404
    return path
