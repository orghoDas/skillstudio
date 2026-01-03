from functools import wraps
from rest_framework.exceptions import PermissionDenied


def role_required(*roles):
    """
    Function-based view protection.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required")

            if request.user.role == "admin":
                return view_func(request, *args, **kwargs)

            if request.user.role not in roles:
                raise PermissionDenied("Insufficient role permissions")

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
