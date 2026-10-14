"""Views of the authentication API.

All tokens are sent as ``HttpOnly`` cookies, never in the response body.
"""

from django.conf import settings
from django.db import transaction
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from .serializers import (
    ActivationSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .utils import (
    delete_auth_cookies,
    get_tokens_for_user,
    send_activation_email,
    set_auth_cookies,
)


class RegisterView(generics.CreateAPIView):
    """Create a user. What happens next depends on ``AUTH_REGISTRATION``.

    - ``EMAIL_ACTIVATION`` off: the user is active and logged in right away.
    - ``EMAIL_ACTIVATION`` on: the user is inactive and gets an activation
      link by email. No cookies are set. ``ActivateView`` logs them in.

    Endpoint: ``POST /auth/register/``
    Authentication: none, an expired access cookie must not block the request.
    """

    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def create(self, request, *args, **kwargs):
        """Validate the data and create the user.

        The setting is read on every request, so tests can change it with
        ``override_settings``.

        Request body:
            ``username``, ``email``, ``password``

        Responses:
            201: ``detail`` and ``user``. Without email activation, access and
                refresh cookie are set.
            400: Field errors, e.g. email already exists or password too weak.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if settings.AUTH_REGISTRATION["EMAIL_ACTIVATION"]:
            return self._register_with_activation(serializer)

        return self._register_and_login(serializer)

    def _register_and_login(self, serializer):
        """Create an active user and set both auth cookies."""
        user = serializer.save()

        response = Response(
            {
                "detail": "Registration successful!",
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )

        set_auth_cookies(response, get_tokens_for_user(user))

        return response

    def _register_with_activation(self, serializer):
        """Create an inactive user and send the activation link.

        If the mail can't be sent, the user is not saved. Otherwise username
        and email would be taken by an account that can never be activated.
        The error then results in a 500 response.
        """
        with transaction.atomic():
            user = serializer.save(is_active=False)
            send_activation_email(user)

        return Response(
            {
                "detail": "Registration successful! Please check your email to activate your account.",
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class ActivateView(generics.GenericAPIView):
    """Activate a user with the data from the activation link and log them in.

    Endpoint: ``POST /auth/activate/<uidb64>/<token>/``
    Authentication: none, the user is not logged in yet.

    POST instead of GET, because the request changes data (see
    ``AUTH_COOKIE["SAMESITE"]`` in the settings). The frontend page of
    ``AUTH_REGISTRATION["ACTIVATION_PATH"]`` reads ``uid`` and ``token`` from
    its URL and sends them here.
    """

    serializer_class = ActivationSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request, uidb64, token, *args, **kwargs):
        """Check the link, set the user active and set both auth cookies.

        The link works only once, so it can't be used to log in a second time.

        URL parameters:
            ``uidb64``: encoded user id, ``token``: activation token.

        Request body:
            none.

        Responses:
            200: ``detail`` and ``user``. Access and refresh cookie are set.
            400: Link invalid, expired or already used.
        """
        serializer = self.get_serializer(data={"uidb64": uidb64, "token": token})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        user.is_active = True
        user.save(update_fields=["is_active"])

        response = Response(
            {
                "detail": "Account activated!",
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )

        set_auth_cookies(response, get_tokens_for_user(user))

        return response


class LoginView(TokenObtainPairView):
    """Log in with username and password.

    Endpoint: ``POST /auth/login/``
    Authentication: none, disabled by the parent class.
    """

    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        """Check the credentials and set both auth cookies.

        The tokens are removed from the response body.

        Request body:
            ``username``, ``password``

        Responses:
            200: ``detail`` and ``user``. Access and refresh cookie are set.
            401: Wrong credentials or inactive user.
        """
        response = super().post(request, *args, **kwargs)
        tokens = response.data

        set_auth_cookies(response, tokens)

        response.data = {
            "detail": "Login successful!",
            "user": tokens["user"],
        }

        return response


class LogoutView(TokenBlacklistView):
    """Log out and invalidate the refresh token.

    Endpoint: ``POST /auth/logout/``
    Authentication: none, disabled by the parent class.
    """

    def post(self, request, *args, **kwargs):
        """Blacklist the refresh token from the cookie and delete both cookies.

        Request body:
            none, the refresh token is read from the cookie.

        Responses:
            200: ``detail``. Both cookies are deleted. Also returned when there
                are no cookies or the token is already invalid.
        """
        self._blacklist_refresh_cookie(request)

        response = Response(
            {
                "detail": (
                    "Logout successful! All tokens have been deleted "
                    "and the refresh token is now invalid."
                ),
            },
            status=status.HTTP_200_OK,
        )
        delete_auth_cookies(response)

        return response

    def _blacklist_refresh_cookie(self, request):
        """Blacklist the token of the refresh cookie, if present and valid."""
        refresh_token = request.COOKIES.get(settings.AUTH_COOKIE["REFRESH_NAME"])

        if not refresh_token:
            return

        serializer = self.get_serializer(data={"refresh": refresh_token})

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError:
            # Token already expired or blacklisted: the cookies are deleted anyway.
            pass


class CookieTokenRefreshView(TokenRefreshView):
    """Create new tokens from the refresh cookie.

    Endpoint: ``POST /auth/token/refresh/``
    Authentication: none, disabled by the parent class.
    """

    def post(self, request, *args, **kwargs):
        """Read the refresh token from the cookie and set new auth cookies.

        With ``ROTATE_REFRESH_TOKENS`` a new refresh token is set as well and
        the old one is blacklisted (``BLACKLIST_AFTER_ROTATION``).

        Request body:
            none, the refresh token is read from the cookie.

        Responses:
            200: ``detail``. New access cookie, with rotation also a new refresh cookie.
            401: Refresh cookie missing, expired or blacklisted.
        """
        refresh_token = request.COOKIES.get(settings.AUTH_COOKIE["REFRESH_NAME"])

        if not refresh_token:
            raise InvalidToken("No refresh token cookie.")

        serializer = self.get_serializer(data={"refresh": refresh_token})

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            # Same handling as the parent class: turns into a 401 response.
            raise InvalidToken(e.args[0]) from e

        response = Response(
            {
                "detail": "Tokens refreshed!",
            },
            status=status.HTTP_200_OK,
        )

        set_auth_cookies(response, serializer.validated_data)

        return response
