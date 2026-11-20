"""Login and token-refresh endpoints (SEC-06).

Two explicit modes, so neither can be used to reach the other:

* **Cookie mode (default, browsers).** Login/refresh are CSRF-checked, the
  access/refresh JWTs are set as httpOnly cookies, and the response body
  contains **no tokens**. Injected JS therefore can't obtain a token by
  calling these endpoints (the cookie is sent automatically, the body is
  useless to it), and a cross-site form can't log a victim into another
  account (login CSRF).

* **Token mode (header-based API clients).** Login with
  ``{"token_in_body": true}`` or refresh by sending ``{"refresh": "..."}`` in
  the body. Tokens are returned in the body and **no cookies are set**, so no
  ambient credential is created and CSRF doesn't apply. Login still needs the
  password; refresh needs a refresh token the client already holds.
"""

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .authentication import _EnforcedCsrfCheck
from .cookies import set_jwt_cookies


def _truthy(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _csrf_failure(request):
    """Run Django's CSRF check on this request; return the reason or None."""
    check = _EnforcedCsrfCheck(lambda req: None)
    check.process_request(request)
    return check.process_view(request, None, (), {})


def _csrf_rejected(reason):
    return Response({"detail": f"CSRF Failed: {reason}"}, status=status.HTTP_403_FORBIDDEN)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except AuthenticationFailed:
            # Customize the error message for wrong password. Raise with a plain
            # string so DRF's exception handler returns a proper JSON detail.
            raise AuthenticationFailed("Incorrect email or password.")


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        token_mode = _truthy(request.data.get("token_in_body", False))
        if not token_mode:
            reason = _csrf_failure(request)
            if reason:
                return _csrf_rejected(reason)

        response = super().post(request, *args, **kwargs)
        if response.status_code != status.HTTP_200_OK or token_mode:
            return response  # token mode: tokens in body, no cookies

        set_jwt_cookies(response, response.data.get("access"), response.data.get("refresh"))
        response.data = {"detail": "Logged in."}
        return response


class CookieTokenRefreshView(TokenRefreshView):
    """Refresh from the cookie (browser, CSRF-checked, tokens only in cookies)
    or from a refresh token in the body (API client, tokens in the body)."""

    def post(self, request, *args, **kwargs):
        body_refresh = request.data.get("refresh")
        token_mode = bool(body_refresh)
        refresh = body_refresh or request.COOKIES.get(settings.JWT_AUTH_REFRESH_COOKIE)
        if not refresh:
            return Response(
                {"detail": "No refresh token provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not token_mode:
            reason = _csrf_failure(request)
            if reason:
                return _csrf_rejected(reason)

        serializer = self.get_serializer(data={"refresh": refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0])

        tokens = serializer.validated_data
        if token_mode:
            return Response(tokens, status=status.HTTP_200_OK)

        response = Response({"detail": "Token refreshed."}, status=status.HTTP_200_OK)
        set_jwt_cookies(response, tokens.get("access"), tokens.get("refresh"))
        return response
