"""Helpers for delivering JWTs to browsers as httpOnly cookies."""

from django.conf import settings


LEGACY_REFRESH_COOKIE = "refresh_token"


def get_refresh_cookie(request):
    return request.COOKIES.get(settings.JWT_AUTH_REFRESH_COOKIE) or request.COOKIES.get(LEGACY_REFRESH_COOKIE)


def _cookie_kwargs():
    return {
        "httponly": True,
        # Secure in production; off in dev so http://localhost works.
        "secure": not settings.DEBUG,
        "samesite": settings.JWT_AUTH_COOKIE_SAMESITE,
    }


def set_jwt_cookies(response, access=None, refresh=None):
    """Attach access/refresh JWT cookies to a response (each optional)."""
    kwargs = _cookie_kwargs()
    if access is not None:
        response.set_cookie(
            settings.JWT_AUTH_COOKIE,
            access,
            max_age=int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
            path="/",
            **kwargs,
        )
    if refresh is not None:
        response.set_cookie(
            settings.JWT_AUTH_REFRESH_COOKIE,
            refresh,
            max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
            path=settings.JWT_AUTH_REFRESH_COOKIE_PATH,
            **kwargs,
        )
    return response


def clear_legacy_refresh_cookie(response):
    response.delete_cookie(LEGACY_REFRESH_COOKIE, path="/", samesite=settings.JWT_AUTH_COOKIE_SAMESITE)


def clear_jwt_cookies(response):
    samesite = settings.JWT_AUTH_COOKIE_SAMESITE
    response.delete_cookie(settings.JWT_AUTH_COOKIE, path="/", samesite=samesite)
    response.delete_cookie(settings.JWT_AUTH_REFRESH_COOKIE, path=settings.JWT_AUTH_REFRESH_COOKIE_PATH, samesite=samesite)
    clear_legacy_refresh_cookie(response)
    return response
