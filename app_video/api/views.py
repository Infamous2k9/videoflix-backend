"""Views of the video API."""

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ..models import Video
from ..utils import get_hls_file
from .serializers import VideoSerializer


class VideoListView(generics.ListAPIView):
    """List all converted videos, newest first.

    Endpoint: ``GET /api/video/``
    """

    queryset = Video.objects.filter(status=Video.Status.READY)
    serializer_class = VideoSerializer
    permission_classes = [IsAuthenticated]


class HlsFileView(APIView):
    """Base view that streams one HLS file of a converted video."""

    permission_classes = [IsAuthenticated]
    content_type = None

    def stream_file(self, movie_id, resolution, filename):
        """Return the file as response, or 404 if video or file are missing."""
        get_object_or_404(Video, pk=movie_id, status=Video.Status.READY)
        path = get_hls_file(movie_id, resolution, filename)
        return FileResponse(path.open("rb"), content_type=self.content_type)


class ManifestView(HlsFileView):
    """Return the HLS playlist of a video in one resolution.

    Endpoint: ``GET /api/video/<movie_id>/<resolution>/index.m3u8``
    """

    content_type = "application/vnd.apple.mpegurl"

    def get(self, request, movie_id, resolution):
        """Stream the ``index.m3u8`` file."""
        return self.stream_file(movie_id, resolution, "index.m3u8")


class SegmentView(HlsFileView):
    """Return one HLS segment of a video in one resolution.

    Endpoint: ``GET /api/video/<movie_id>/<resolution>/<segment>/``
    """

    content_type = "video/MP2T"

    def get(self, request, movie_id, resolution, segment):
        """Stream the requested ``.ts`` file."""
        return self.stream_file(movie_id, resolution, segment)
