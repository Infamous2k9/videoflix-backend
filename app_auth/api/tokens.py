"""Token for the activation link that is sent by email after registration."""

from django.contrib.auth.tokens import PasswordResetTokenGenerator


class ActivationTokenGenerator(PasswordResetTokenGenerator):
    """Create and check activation tokens.

    Works like the token of Django's password reset, with two differences:

    - Own ``key_salt``: a password reset token is not accepted as an
      activation token, and the other way round.
    - ``is_active`` is part of the token: as soon as the user is active,
      the link stops working. Every link can therefore be used only once.

    The link expires after ``PASSWORD_RESET_TIMEOUT`` seconds.
    """

    key_salt = "app_auth.api.tokens.ActivationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        return f"{super()._make_hash_value(user, timestamp)}{user.is_active}"


activation_token_generator = ActivationTokenGenerator()
