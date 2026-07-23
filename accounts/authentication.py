import hmac

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import APIKey


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
