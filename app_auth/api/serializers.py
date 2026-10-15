"""Serializers of the authentication API."""

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .tokens import activation_token_generator
from .utils import get_user_from_uidb64

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Public data of a user, used in the login response."""

    class Meta:
        model = User
        fields = ("id", "username")
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    """Validate the registration data and create an inactive user."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    confirmed_password = serializers.CharField(write_only=True)

    default_error_messages = {
        "invalid_input": "Please check your input and try again.",
    }

    def validate_email(self, value):
        """Reject an email that is already in use, ignoring upper/lower case."""
        if User.objects.filter(email__iexact=value).exists():
            self.fail("invalid_input")
        return value

    def validate(self, attrs):
        """Check that both passwords match and pass the password validators."""
        if attrs["password"] != attrs["confirmed_password"]:
            raise serializers.ValidationError(
                {"confirmed_password": "Passwords do not match."}
            )
        user = User(username=attrs["email"], email=attrs["email"])
        try:
            validate_password(attrs["password"], user=user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages})
        return attrs

    def create(self, validated_data):
        """Create an inactive user. The email is used as username as well."""
        email = validated_data["email"]
        return User.objects.create_user(
            username=email,
            email=email,
            password=validated_data["password"],
            is_active=False,
        )


class ActivationSerializer(serializers.Serializer):
    """Check ``uidb64`` and ``token`` from the activation link.

    After a successful check, ``validated_data["user"]`` holds the user.
    """

    uidb64 = serializers.CharField()
    token = serializers.CharField()

    default_error_messages = {
        "invalid_link": "Activation link is invalid or expired.",
    }

    def validate(self, attrs):
        """Load the user of ``uidb64`` and check the token.

        All errors return the same message, so the response does not reveal
        whether a user exists.
        """
        user = get_user_from_uidb64(attrs["uidb64"])
        if user is None or not activation_token_generator.check_token(
            user, attrs["token"]
        ):
            self.fail("invalid_link")
        attrs["user"] = user
        return attrs


class LoginSerializer(serializers.Serializer):
    """Check email and password and return the matching active user."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    default_error_messages = {
        "invalid_credentials": "Please check your input and try again.",
    }

    def validate(self, attrs):
        """Authenticate with the email as username.

        Wrong credentials and inactive accounts get the same message, so the
        response does not reveal whether an account exists.
        """
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["email"],
            password=attrs["password"],
        )
        if user is None:
            self.fail("invalid_credentials")
        attrs["user"] = user
        return attrs


class PasswordResetSerializer(serializers.Serializer):
    """Validate the email for a password reset request."""

    email = serializers.EmailField()


class PasswordConfirmSerializer(serializers.Serializer):
    """Check the reset link and the new password, then save it.

    ``uidb64`` and ``token`` from the URL are passed in the serializer context.
    """

    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    default_error_messages = {
        "invalid_link": "Password reset link is invalid or expired.",
    }

    def validate(self, attrs):
        """Check the link, that both passwords match and the password validators."""
        user = self._get_user_from_link()
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        try:
            validate_password(attrs["new_password"], user=user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"new_password": error.messages})
        attrs["user"] = user
        return attrs

    def create(self, validated_data):
        """Hash and save the new password. The old one is replaced."""
        user = validated_data["user"]
        user.set_password(validated_data["new_password"])
        user.save(update_fields=["password"])
        return user

    def _get_user_from_link(self):
        """Return the user of the link or fail with a generic message."""
        user = get_user_from_uidb64(self.context["uidb64"])
        if user is None or not default_token_generator.check_token(
            user, self.context["token"]
        ):
            self.fail("invalid_link")
        return user
