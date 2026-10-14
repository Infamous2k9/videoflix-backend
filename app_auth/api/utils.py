"""Helper functions of the authentication views."""

import django_rq
from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.core.mail import send_mail
from django.db import transaction
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


ACTIVATION_EMAIL_QUEUE = "high"


def build_activation_url(user, token):
    """Return the frontend link that activates the user's account.

    ``FRONTEND_BASE_URL`` plus ``AUTH_REGISTRATION["ACTIVATION_PATH"]``, with
    ``{uid}`` and ``{token}`` filled in.
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    path = settings.AUTH_REGISTRATION["ACTIVATION_PATH"].format(uid=uid, token=token)
    return f"{settings.FRONTEND_BASE_URL}/{path.lstrip('/')}"


def send_activation_email(email, activation_url):
    """Send the activation link. Runs as a background job in the RQ worker."""
    send_mail(
        subject="Activate your Videoflix account",
        message=(
            "Welcome to Videoflix!\n\n"
            "Please open the following link to activate your account:\n\n"
            f"{activation_url}\n\n"
            "If you did not register, you can ignore this email."
        ),
        from_email=None,
        recipient_list=[email],
    )


def queue_activation_email(user, token):
    """Queue the activation email as soon as the user is saved."""
    activation_url = build_activation_url(user, token)
    queue = django_rq.get_queue(ACTIVATION_EMAIL_QUEUE)
    transaction.on_commit(
        lambda: queue.enqueue(send_activation_email, user.email, activation_url)
    )
