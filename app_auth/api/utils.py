"""Helper functions of the authentication views."""

from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .tokens import activation_token_generator


def get_tokens_for_user(user):
    """Create a token pair for the user, the same way the login does.

    Args:
        user: The user the tokens belong to.

    Returns:
        Dictionary with the keys ``refresh`` and ``access``.
    """
    refresh = TokenObtainPairSerializer.get_token(user)

    if settings.SIMPLE_JWT.get("UPDATE_LAST_LOGIN"):
        update_last_login(None, user)

    return {"refresh": str(refresh), "access": str(refresh.access_token)}


def _set_cookie(response, name, value, path, lifetime):
    """Store a token in an ``HttpOnly`` cookie of the response."""
    response.set_cookie(
        key=name,
        value=value,
        max_age=lifetime,
        path=path,
        secure=settings.AUTH_COOKIE["SECURE"],
        httponly=True,
        samesite=settings.AUTH_COOKIE["SAMESITE"],
    )


def set_auth_cookies(response, tokens):
    """Store the access token and, if present, the refresh token in cookies.

    Args:
        response: The response that carries the cookies.
        tokens: Dictionary with the key ``access`` and optionally ``refresh``.
            ``refresh`` is missing after a token refresh without rotation.
    """
    cookie = settings.AUTH_COOKIE
    jwt = settings.SIMPLE_JWT

    _set_cookie(
        response,
        cookie["ACCESS_NAME"],
        tokens["access"],
        cookie["ACCESS_PATH"],
        jwt["ACCESS_TOKEN_LIFETIME"],
    )

    if "refresh" in tokens:
        _set_cookie(
            response,
            cookie["REFRESH_NAME"],
            tokens["refresh"],
            cookie["REFRESH_PATH"],
            jwt["REFRESH_TOKEN_LIFETIME"],
        )


def delete_auth_cookies(response):
    """Delete both auth cookies.

    Path and SameSite must match the values used when setting the cookies,
    otherwise the browser keeps them.
    """
    cookie = settings.AUTH_COOKIE

    for name, path in (
        (cookie["ACCESS_NAME"], cookie["ACCESS_PATH"]),
        (cookie["REFRESH_NAME"], cookie["REFRESH_PATH"]),
    ):
        response.delete_cookie(key=name, path=path, samesite=cookie["SAMESITE"])


def build_activation_url(user):
    """Return the activation link for the user.

    ``FRONTEND_BASE_URL`` plus ``AUTH_REGISTRATION["ACTIVATION_PATH"]``, with
    ``{uid}`` and ``{token}`` filled in. ``uid`` is the user id, encoded so
    that it can be used in a URL.
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = activation_token_generator.make_token(user)
    path = settings.AUTH_REGISTRATION["ACTIVATION_PATH"].format(uid=uid, token=token)

    return f"{settings.FRONTEND_BASE_URL}/{path.lstrip('/')}"


def send_activation_email(user):
    """Send the activation link to the email address of the user.

    Uses the default mailer from ``MAILERS`` and ``DEFAULT_FROM_EMAIL``.

    Raises:
        Exception: The mail could not be sent, e.g. SMTP server not reachable.
    """
    activation_url = build_activation_url(user)

    send_mail(
        subject="Activate your account",
        message=(
            f"Hello {user.username},\n\n"
            "please open the following link to activate your account:\n\n"
            f"{activation_url}\n\n"
            "If you did not register, you can ignore this email."
        ),
        from_email=None,
        recipient_list=[user.email],
    )
