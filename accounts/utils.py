"""
Utility functions for the accounts app
"""


def is_platform_admin(user):
    return (
        getattr(user, 'is_authenticated', False)
        and (
            getattr(user, 'is_superuser', False)
            or getattr(user, 'role', None) == 'admin'
        )
    )


def normalize_role_flags(user):
    if getattr(user, 'is_superuser', False):
        user.role = user.Role.ADMIN
        user.is_staff = True
    elif getattr(user, 'role', None) == user.Role.ADMIN:
        user.is_staff = True
    return user
