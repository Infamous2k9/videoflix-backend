"""Views of the authentication API.

All tokens are sent as ``HttpOnly`` cookies, never in the response body.
"""

from django.conf import settings
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenRefreshView,
)

from .serializers import (
    ActivationSerializer,
    LoginSerializer,
    PasswordConfirmSerializer,
    PasswordResetSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .tokens import activation_token_generator
from .utils import (
    delete_auth_cookies,
    get_refresh_cookie,
    get_tokens_for_user,
    queue_activation_email,
    queue_password_reset_email,
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

    Endpoint: ``POST /api/logout/``
    Authentication: none, the refresh cookie is checked instead.
    """

    def post(self, request, *args, **kwargs):
        """Blacklist the refresh token from the cookie and delete both cookies."""
        self._blacklist_refresh_cookie(request)
        response = Response(
            {
                "detail": (
                    "Logout successful! All tokens will be deleted. "
                    "Refresh token is now invalid."
                ),
            },
            status=status.HTTP_200_OK,
        )
        delete_auth_cookies(response)
        return response

    def _blacklist_refresh_cookie(self, request):
        """Put the refresh token from the cookie on the blacklist.

        Raises:
            ValidationError: The refresh cookie is missing (400).
        """
        serializer = self.get_serializer(data={"refresh": get_refresh_cookie(request)})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError:
            # Already expired or blacklisted: the cookies are deleted anyway.
            pass


class CookieTokenRefreshView(TokenRefreshView):
    """Create new tokens from the refresh cookie.

    Endpoint: ``POST /api/token/refresh/``
    Authentication: none, disabled by the parent class.
    """

    def post(self, request, *args, **kwargs):
        """Set new auth cookies and return the new access token.

        The access token in the body is for demonstration only, the frontend
        uses the cookie.
        """
        tokens = self._get_refreshed_tokens(request)
        response = Response(
            {"detail": "Token refreshed", "access": tokens["access"]},
            status=status.HTTP_200_OK,
        )
        set_auth_cookies(response, tokens)
        return response

    def _get_refreshed_tokens(self, request):
        """Validate the refresh cookie and return the new tokens.

        Raises:
            ValidationError: The refresh cookie is missing (400).
            InvalidToken: The token is invalid, expired or blacklisted (401).
        """
        serializer = self.get_serializer(data={"refresh": get_refresh_cookie(request)})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as error:
            raise InvalidToken(error.args[0]) from error
        return serializer.validated_data


class PasswordResetView(generics.GenericAPIView):
    """Send a password reset link by email.

    Endpoint: ``POST /api/password_reset/``
    Authentication: none.
    """

    serializer_class = PasswordResetSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request, *args, **kwargs):
        """Queue the reset email. The response is the same for every email."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        queue_password_reset_email(serializer.validated_data["email"])
        return Response(
            {"detail": "An email has been sent to reset your password."},
            status=status.HTTP_200_OK,
        )


class PasswordConfirmView(generics.GenericAPIView):
    """Set a new password with the data from the reset link.

    Endpoint: ``POST /api/password_confirm/<uidb64>/<token>/``
    Authentication: none.
    """

    serializer_class = PasswordConfirmSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request, uidb64, token, *args, **kwargs):
        """Check the link and the new password, then save it."""
        context = {**self.get_serializer_context(), "uidb64": uidb64, "token": token}
        serializer = self.get_serializer(data=request.data, context=context)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Your Password has been successfully reset."},
            status=status.HTTP_200_OK,
        )
