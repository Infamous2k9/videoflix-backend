"""URLs of the video API, included under ``api/`` in ``core/urls.py``."""

from django.urls import path, re_path

from .views import ManifestView, SegmentView, VideoListView

urlpatterns = [
    path("video/", VideoListView.as_view(), name="video-list"),
    path(
        "video/<int:movie_id>/<str:resolution>/index.m3u8",
        ManifestView.as_view(),
        name="video-manifest",
    ),
    re_path(
        r"^video/(?P<movie_id>\d+)/(?P<resolution>\w+)/(?P<segment>\d+\.ts)/?$",
        SegmentView.as_view(),
        name="video-segment",
    ),
]
