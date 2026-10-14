"""Serializers of the authentication API."""

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from .tokens import activation_token_generator

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
