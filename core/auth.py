"""Server-side gating for HTML page routes based on the JWT auth cookies.

Page views render shells; the data is fetched client-side. This gate keeps
anonymous users from loading authenticated pages at all (no content flash),
replacing the old client-side `if (!localStorage.token) redirect` checks.
"""

from functools import wraps
from urllib.parse import quote

from django.conf import settings
from django.shortcuts import redirect
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.exceptions import TokenError


def _is_authenticated(request):
    # A valid (unexpired) access cookie is enough.
    access = request.COOKIES.get(settings.JWT_AUTH_COOKIE)
    if access:
        try:
            AccessToken(access)
            return True
        except TokenError:
            pass
    # Otherwise a valid refresh cookie is fine — the client will refresh the
    # access token on its first API call, so don't bounce them to login.
    refresh = request.COOKIES.get(settings.JWT_AUTH_REFRESH_COOKIE)
    if refresh:
        try:
            RefreshToken(refresh)
            return True
        except TokenError:
            pass
    return False


def cookie_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not _is_authenticated(request):
            return redirect(f"/auth/login/?next={quote(request.get_full_path())}")
        return view_func(request, *args, **kwargs)

    return wrapper
