"""Serializers of the authentication API."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .tokens import activation_token_generator

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Public data of a user, used in responses.

    Add new user fields to ``fields`` to include them in every auth response.
    """

    class Meta:
        model = User
        fields = ("id", "username", "email")
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    """Validate the registration data and create the user."""

    class Meta:
        model = User
        fields = ("id", "username", "email", "password")
        extra_kwargs = {
            "email": {"required": True},
            "password": {"write_only": True},
        }

    def validate_email(self, value):
        """Reject an email that is already used, regardless of upper/lower case."""
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email already exists.")

        return value

    def validate(self, attrs):
        """Check the password with the validators from ``AUTH_PASSWORD_VALIDATORS``.

        An unsaved user is passed, so the validators can also reject passwords
        that are too similar to the username or email.
        """
        user = User(username=attrs["username"], email=attrs["email"])

        try:
            validate_password(attrs["password"], user=user)
        except DjangoValidationError as e:
            # Show the errors under "password" instead of "non_field_errors".
            raise serializers.ValidationError({"password": e.messages})

        return attrs

    def create(self, validated_data):
        """Create the user. ``create_user`` hashes the password.

        ``validated_data`` also contains the arguments of ``serializer.save()``,
        e.g. ``is_active=False`` from the registration with email activation.
        """
        return User.objects.create_user(**validated_data)


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
        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uidb64"]))
            user = User.objects.get(pk=user_id)
        except (
            ValueError,
            TypeError,
            OverflowError,
            User.DoesNotExist,
            DjangoValidationError,
        ):
            self.fail("invalid_link")

        if not activation_token_generator.check_token(user, attrs["token"]):
            self.fail("invalid_link")

        attrs["user"] = user

        return attrs


class LoginSerializer(TokenObtainPairSerializer):
    """Validate the login credentials and add the user data to the result."""

    def validate(self, attrs):
        """Return the token pair extended by a ``user`` entry.

        The parent checks username and password and raises a 401 error
        if they are wrong. It also updates ``last_login``.
        """
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data

        return data
