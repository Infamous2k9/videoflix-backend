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
from .tokens import activation_token_generator
from .utils import (
    delete_auth_cookies,
    get_tokens_for_user,
    queue_activation_email,
    send_activation_email,
    set_auth_cookies,
)


class RegisterView(generics.CreateAPIView):
    """Create an inactive user and send the activation link by email.

    Endpoint: ``POST /api/register/``
    Authentication: none, an expired access cookie must not block the request.
    """

    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def create(self, request, *args, **kwargs):
        """Validate the data, create the user and queue the activation email."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token = activation_token_generator.make_token(user)
        queue_activation_email(user, token)
        data = {"user": {"id": user.id, "email": user.email}, "token": token}
        return Response(data, status=status.HTTP_201_CREATED)


class ActivateView(generics.GenericAPIView):
    """Activate a user with the data from the activation link.

    Endpoint: ``GET /api/activate/<uidb64>/<token>/``
    Authentication: none, the user is not logged in yet.
    """

    serializer_class = ActivationSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get(self, request, uidb64, token, *args, **kwargs):
        """Check the link and set the user active. The link works only once."""
        serializer = self.get_serializer(data={"uidb64": uidb64, "token": token})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.is_active = True
        user.save(update_fields=["is_active"])
        return Response(
            {"message": "Account successfully activated."},
            status=status.HTTP_200_OK,
        )


class LoginView(generics.GenericAPIView):
    """Log in with email and password.

    Endpoint: ``POST /api/login/``
    Authentication: none, an expired access cookie must not block the login.
    """

    serializer_class = LoginSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request, *args, **kwargs):
        """Check the credentials and set the access and refresh cookie."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        response = Response(
            {"detail": "Login successful", "user": UserSerializer(user).data},
            status=status.HTTP_200_OK,
        )
        set_auth_cookies(response, get_tokens_for_user(user))
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
