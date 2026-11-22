"""Resolve page access from the browser's JWT access cookie."""

from functools import wraps
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken

from accounts.utils import is_platform_admin


def page_user(request):
    if not hasattr(request, '_page_user'):
        request._page_user = None
        access = request.COOKIES.get(settings.JWT_AUTH_COOKIE)
        if access:
            auth = JWTAuthentication()
            try:
                request._page_user = auth.get_user(auth.get_validated_token(access))
            except (AuthenticationFailed, InvalidToken):
                pass
    return request._page_user


def page_auth_context(request):
    user = page_user(request)
    if user is None:
        return {'page_role': None}
    return {
        'page_role': 'admin' if is_platform_admin(user) else user.role,
        'page_username': user.email.split('@', 1)[0],
    }


def cookie_login_required(view_func=None, *, role=None):
    def decorate(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            user = page_user(request)
            if user is None:
                query = urlencode({'next': request.get_full_path()})
                return redirect(f'/auth/login/?{query}')
            if role and user.role != role and not is_platform_admin(user):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper

    return decorate(view_func) if view_func else decorate
