"""Shared authorization helpers for social learning circles."""

from django.db.models import Q

from .models import CircleMembership, LearningCircle


def is_admin_user(user):
    return bool(
        user
        and user.is_authenticated
        and (
            getattr(user, "role", None) == "admin"
            or getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
        )
    )


def active_membership(user, circle):
    if not user or not user.is_authenticated:
        return None
    return CircleMembership.objects.filter(
        circle=circle,
        user=user,
        status="active",
    ).first()


def is_active_circle_member(user, circle):
    return active_membership(user, circle) is not None


def can_view_circle(user, circle):
    if not user or not user.is_authenticated:
        return False
    if is_admin_user(user):
        return True
    if circle.status == "archived":
        return False
    if not circle.is_private:
        return True
    return is_active_circle_member(user, circle)


def can_manage_circle(user, circle):
    if is_admin_user(user):
        return True
    membership = active_membership(user, circle)
    return bool(membership and membership.role == "admin")


def can_moderate_circle(user, circle):
    if can_manage_circle(user, circle):
        return True
    membership = active_membership(user, circle)
    return bool(membership and membership.role == "moderator")


def can_use_circle(user, circle):
    return is_admin_user(user) or is_active_circle_member(user, circle)


def visible_circle_filter(user):
    if not user or not user.is_authenticated:
        return Q(pk__isnull=True)
    if is_admin_user(user):
        return ~Q(status="archived")
    return (
        Q(is_private=False)
        | Q(members__user=user, members__status="active")
    ) & ~Q(status="archived")


def visible_circles_for(user):
    return LearningCircle.objects.filter(visible_circle_filter(user)).distinct()
