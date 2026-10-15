"""Helper functions of the authentication views."""

import django_rq
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


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


EMAIL_QUEUE = "high"


EMAIL_QUEUE = "high"


def build_frontend_url(path_template, user, token):
    """Return a frontend link with the encoded user id and the token.

    Args:
        path_template: Path with ``{uid}`` and ``{token}`` placeholders.
        user: The user the link belongs to.
        token: Activation or password reset token.
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    path = path_template.format(uid=uid, token=token)
    return f"{settings.FRONTEND_BASE_URL}/{path.lstrip('/')}"


def get_user_from_uidb64(uidb64):
    """Return the user of an encoded id, or ``None`` if the id is invalid."""
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        return User.objects.get(pk=user_id)
    except (
        ValueError,
        TypeError,
        OverflowError,
        User.DoesNotExist,
        DjangoValidationError,
    ):
        return None


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
    activation_url = build_frontend_url(
        settings.AUTH_REGISTRATION["ACTIVATION_PATH"], user, token
    )
    queue = django_rq.get_queue(EMAIL_QUEUE)
    transaction.on_commit(
        lambda: queue.enqueue(send_activation_email, user.email, activation_url)
    )


def get_refresh_cookie(request):
    """Return the refresh token from the cookie.

    Raises:
        ValidationError: The refresh cookie is missing (400).
    """
    refresh_token = request.COOKIES.get(settings.AUTH_COOKIE["REFRESH_NAME"])
    if not refresh_token:
        raise ValidationError({"detail": "Refresh token is missing."})
    return refresh_token


def send_password_reset_email(email, reset_url):
    """Send the password reset link. Runs as a background job in the RQ worker."""
    send_mail(
        subject="Reset your Videoflix password",
        message=(
            "We received a request to reset your password.\n\n"
            "Please open the following link to set a new password:\n\n"
            f"{reset_url}\n\n"
            "If you did not request this, you can ignore this email."
        ),
        from_email=None,
        recipient_list=[email],
    )


def queue_password_reset_email(email):
    """Queue a reset link if an active user with this email exists.

    Unknown emails are ignored silently, so the response does not reveal
    whether an account exists.
    """
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user is None:
        return
    token = default_token_generator.make_token(user)
    reset_url = build_frontend_url(settings.PASSWORD_RESET_PATH, user, token)
    django_rq.get_queue(EMAIL_QUEUE).enqueue(
        send_password_reset_email, user.email, reset_url
    )
