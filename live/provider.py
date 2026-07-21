"""
Provider integration for real-time live classrooms.

LiveKit room access is issued from the backend after SkillStudio's own
authorization and enrollment checks pass. This keeps LiveKit as the media
transport while Django remains the source of truth for who may enter a room.
"""

from datetime import timedelta

import jwt
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from live import policies


class LiveKitConfigurationError(ImproperlyConfigured):
    """Raised when a LiveKit room token is requested without provider config."""


def is_livekit_configured():
    return bool(
        settings.LIVEKIT_ENABLED
        and settings.LIVEKIT_URL
        and settings.LIVEKIT_API_KEY
        and settings.LIVEKIT_API_SECRET
    )


def livekit_room_name(session):
    return f"skillstudio-live-session-{session.id}"


def participant_identity(user):
    return f"user-{user.id}"


def participant_name(user):
    profile = getattr(user, "profile", None)
    if profile:
        full_name = (
            getattr(profile, "full_name", None)
            or f"{getattr(profile, 'first_name', '') or ''} {getattr(profile, 'last_name', '') or ''}".strip()
        )
        if full_name:
            return full_name

    return getattr(user, "username", None) or getattr(user, "email", "") or participant_identity(user)


def generate_livekit_join_payload(user, session):
    if not is_livekit_configured():
        raise LiveKitConfigurationError("LiveKit is not configured")

    room_name = livekit_room_name(session)
    identity = participant_identity(user)
    name = participant_name(user)
    now = timezone.now()
    expires_at = now + timedelta(seconds=settings.LIVEKIT_TOKEN_TTL_SECONDS)
    can_manage = policies.can_manage_live_session(user, session)

    video_grant = {
        "roomJoin": True,
        "room": room_name,
        "canSubscribe": True,
        "canPublish": can_manage,
        "canPublishData": True,
        "roomAdmin": can_manage,
    }

    token = jwt.encode(
        {
            "iss": settings.LIVEKIT_API_KEY,
            "sub": identity,
            "name": name,
            "nbf": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "video": video_grant,
        },
        settings.LIVEKIT_API_SECRET,
        algorithm="HS256",
    )

    return {
        "provider": "livekit",
        "configured": True,
        "url": settings.LIVEKIT_URL,
        "room_name": room_name,
        "token": token,
        "identity": identity,
        "name": name,
        "expires_at": expires_at.isoformat(),
        "permissions": {
            "can_publish": can_manage,
            "can_subscribe": True,
            "can_publish_data": True,
            "room_admin": can_manage,
        },
    }
