"""Authentication class that reads the JWT from a cookie."""

from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate with the access token from the ``HttpOnly`` cookie.

    Replaces the ``Authorization`` header of the default ``JWTAuthentication``.
    Registered in ``REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]``.
    """

    def authenticate(self, request):
        """Return the user and the token of the access cookie.

        Returns:
            ``(user, token)`` for a valid cookie, ``None`` without a cookie.
            ``None`` means anonymous; the permission classes decide whether
            that is allowed.

        Raises:
            InvalidToken: The cookie is invalid or expired. Results in a 401.
        """
        raw_token = request.COOKIES.get(settings.AUTH_COOKIE["ACCESS_NAME"])

        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)

        return self.get_user(validated_token), validated_token
