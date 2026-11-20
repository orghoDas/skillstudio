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


def email_domain(email):
    """Lower-cased domain part of an email address ('' if there is none)."""
    _, _, domain = (email or "").strip().rpartition("@")
    return domain.lower()


def signup_role_for_email(email):
    """Role a new self-registered account gets (Decision D-02 / SEC-07).

    Exact domain match, case-insensitive: ``x@instructor.com`` is an
    instructor, but ``x@evil.instructor.com`` is not. Raises ``ValueError``
    for domains that may not self-register (admin).
    """
    from django.conf import settings

    domain = email_domain(email)
    if domain in settings.SIGNUP_FORBIDDEN_EMAIL_DOMAINS:
        raise ValueError(
            "Admin accounts can't be created by signing up. Ask an existing admin to create one."
        )
    return settings.SIGNUP_ROLE_BY_EMAIL_DOMAIN.get(domain, settings.SIGNUP_DEFAULT_ROLE)


def normalize_role_flags(user):
    if getattr(user, 'is_superuser', False):
        user.role = user.Role.ADMIN
        user.is_staff = True
    elif getattr(user, 'role', None) == user.Role.ADMIN:
        user.is_staff = True
    return user
