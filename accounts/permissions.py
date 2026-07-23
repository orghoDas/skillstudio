from rest_framework.permissions import BasePermission, SAFE_METHODS
from .utils import is_platform_admin


class BaseRolePermission(BasePermission):
    """
    Shared base permission to avoid role leaks.
    """
    allowed_roles = []

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Platform admins are allowed across role-specific permission checks.
        if is_platform_admin(request.user):
            return True

        return request.user.role in self.allowed_roles


class IsStudent(BaseRolePermission):
    allowed_roles = ["student"]


class IsInstructor(BaseRolePermission):
    allowed_roles = ["instructor"]


class IsAdmin(BaseRolePermission):
    allowed_roles = ["admin"]
