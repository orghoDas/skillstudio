import hmac

from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import SAFE_METHODS
from rest_framework_simplejwt.authentication import JWTAuthentication, default_user_authentication_rule
from rest_framework_simplejwt.exceptions import AuthenticationFailed as JWTAuthenticationFailed

from .models import APIKey


def can_authenticate_on_website(user):
    return default_user_authentication_rule(user) and not user.admin_console_only


class _EnforcedCsrfCheck(CsrfViewMiddleware):
    """CsrfViewMiddleware subclass whose rejection returns the reason string."""

    def _reject(self, request, reason):
        return reason


def enforce_cookie_csrf(request):
    if request.method in (*SAFE_METHODS, "TRACE"):
        return
    check = _EnforcedCsrfCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate via JWT from the Authorization header OR an httpOnly cookie.

    Browsers receive the token as an httpOnly cookie (unreadable by JS, so XSS
    cannot steal it). Because cookies are sent automatically, cookie-based
    requests are CSRF-enforced on unsafe methods. Header-based requests
    (API clients) are not CSRF-checked — a bearer header is not auto-attached
    cross-site, so it is not CSRF-exploitable.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if user.admin_console_only:
            raise JWTAuthenticationFailed("This account uses the admin console.")
        return user

    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
            if raw_token is None:
                return None
            validated = self.get_validated_token(raw_token)
            return self.get_user(validated), validated

        raw_token = request.COOKIES.get(settings.JWT_AUTH_COOKIE)
        if not raw_token:
            return None

        validated = self.get_validated_token(raw_token)
        enforce_cookie_csrf(request)
        return self.get_user(validated), validated


class APIKeyAuthentication(BaseAuthentication):
    """
    Authenticate requests with `Authorization: Api-Key <secret>` or `X-API-Key`.
    """

    keyword = "Api-Key"

    def authenticate(self, request):
        secret = self._get_secret(request)
        if not secret:
            return None

        key_hash = APIKey.hash_secret(secret)
        prefix = secret[:16]
        api_key = (
            APIKey.objects
            .select_related("user")
            .filter(prefix=prefix, is_active=True, revoked_at__isnull=True)
            .first()
        )

        if not api_key or not hmac.compare_digest(api_key.key_hash, key_hash):
            raise AuthenticationFailed("Invalid API key.")

        if not api_key.user.is_active:
            raise AuthenticationFailed("API key user is inactive.")
        if api_key.user.admin_console_only:
            raise AuthenticationFailed("This account uses the admin console.")

        scope = APIKey.Scope.READ if request.method in SAFE_METHODS else APIKey.Scope.WRITE
        scopes = api_key.scopes
        # Empty lists preserve the access of existing unscoped keys.
        if not isinstance(scopes, list) or (scopes and scope not in scopes):
            raise exceptions.PermissionDenied(f"This API key requires the {scope} scope.")

        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=["last_used_at"])
        return api_key.user, api_key

    def _get_secret(self, request):
        auth_header = request.headers.get("Authorization", "")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == self.keyword.lower():
                return parts[1]

        return request.headers.get("X-API-Key")
