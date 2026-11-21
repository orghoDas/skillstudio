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


def profile_display_name(user):
    """Return a profile name that does not contain the account email."""
    profile = getattr(user, 'profile', None)
    if profile is not None:
        full_name = (profile.full_name or '').strip()
        parts = ' '.join(part.strip() for part in (profile.first_name, profile.last_name) if part).strip()
        account_email = (user.email or '').strip().casefold()
        for name in (full_name, parts):
            if name and (not account_email or account_email not in name.casefold()):
                return name
    return ''


def public_instructor_name(user):
    return profile_display_name(user) or 'Instructor'


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

