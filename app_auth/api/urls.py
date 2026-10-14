"""URLs of the authentication API, included under ``auth/`` in ``core/urls.py``.

The refresh cookie is only sent to paths below ``AUTH_COOKIE["REFRESH_PATH"]``
(``/auth/``). Refresh and logout must stay below that path.
"""

from django.urls import path

from .views import (
    ActivateView,
    CookieTokenRefreshView,
    LoginView,
    LogoutView,
    RegisterView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("token/refresh/", CookieTokenRefreshView.as_view(), name="refresh"),
    path("activate/<str:uidb64>/<str:token>/", ActivateView.as_view(), name="activate"),
]
