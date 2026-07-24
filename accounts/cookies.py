"""Helpers for delivering JWTs to browsers as httpOnly cookies."""

from django.conf import settings


def _cookie_kwargs():
    return {
        "httponly": True,
        # Secure in production; off in dev so http://localhost works.
        "secure": not settings.DEBUG,
        "samesite": settings.JWT_AUTH_COOKIE_SAMESITE,
        "path": "/",
    }


def set_jwt_cookies(response, access=None, refresh=None):
    """Attach access/refresh JWT cookies to a response (each optional)."""
    kwargs = _cookie_kwargs()
    if access is not None:
        response.set_cookie(
            settings.JWT_AUTH_COOKIE,
            access,
            max_age=int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
            **kwargs,
        )
    if refresh is not None:
        response.set_cookie(
            settings.JWT_AUTH_REFRESH_COOKIE,
            refresh,
            max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
            **kwargs,
        )
    return response


def clear_jwt_cookies(response):
    response.delete_cookie(settings.JWT_AUTH_COOKIE, path="/")
    response.delete_cookie(settings.JWT_AUTH_REFRESH_COOKIE, path="/")
    return response
