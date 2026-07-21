"""
Authorization helpers for live sessions.

Keep these checks small and explicit so HTTP views, services, and WebSocket
consumers make the same access decisions.
"""

from django.db.models import Q

from enrollments.models import Enrollment
from live.models import LiveSession, SessionParticipant


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


def is_session_owner(user, session):
    return bool(user and user.is_authenticated and session.instructor_id == user.id)


def has_active_enrollment(user, course):
    if not user or not user.is_authenticated:
        return False
    return Enrollment.objects.filter(
        user=user,
        course=course,
        status="active",
    ).exists()


def is_joined_participant(user, session):
    if not user or not user.is_authenticated:
        return False
    return SessionParticipant.objects.filter(
        session=session,
        user=user,
        status="joined",
    ).exists()


def visible_live_session_filter(user):
    if not user or not user.is_authenticated:
        return Q(pk__isnull=True)

    if is_admin_user(user):
        return Q()

    return (
        Q(instructor=user)
        | Q(is_public=True, course__status="published")
        | Q(requires_enrollment=False, course__status="published")
        | Q(course__enrollments__user=user, course__enrollments__status="active")
    )


def visible_live_sessions_for(user):
    return LiveSession.objects.filter(visible_live_session_filter(user)).distinct()


def can_view_live_session(user, session):
    if not user or not user.is_authenticated:
        return False
    if is_admin_user(user) or is_session_owner(user, session):
        return True
    if session.course.status != "published":
        return False
    if session.is_public or not session.requires_enrollment:
        return True
    return has_active_enrollment(user, session.course)


def can_manage_live_session(user, session):
    return is_admin_user(user) or is_session_owner(user, session)


def can_join_live_session(user, session, meeting_password=None):
    if not can_view_live_session(user, session):
        return False

    if session.status != "live":
        return False

    if can_manage_live_session(user, session):
        return True

    if session.password_protected and session.meeting_password:
        if meeting_password != session.meeting_password:
            return False

    if session.requires_enrollment and not has_active_enrollment(user, session.course):
        return False

    participant = SessionParticipant.objects.filter(session=session, user=user).first()
    if participant and participant.status == "banned":
        return False

    return True


def can_use_live_interactions(user, session):
    if can_manage_live_session(user, session):
        return True
    return is_joined_participant(user, session)


def can_connect_live_socket(user, session):
    if not user or not user.is_authenticated:
        return False
    if session.status != "live":
        return False
    return can_manage_live_session(user, session) or is_joined_participant(user, session)


def can_view_recording(user, recording):
    session = recording.session
    if can_manage_live_session(user, session):
        return True
    if recording.is_public and session.course.status == "published":
        return True
    if recording.requires_enrollment:
        return has_active_enrollment(user, session.course)
    return can_view_live_session(user, session)
