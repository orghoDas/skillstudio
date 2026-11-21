from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db.models import F
from django.utils import timezone

from .models import LearningActivity


def learning_timezone(request):
    name = request.query_params.get('timezone', '')
    if 0 < len(name) <= 64:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return timezone.get_default_timezone()


def record_learning_activity(user_id, occurred_at, *, local_zone=None, watch_seconds=0):
    day = timezone.localdate(occurred_at, timezone=local_zone)
    activity, created = LearningActivity.objects.get_or_create(
        user_id=user_id, date=day, defaults={'watch_seconds': watch_seconds},
    )
    if watch_seconds and not created:
        LearningActivity.objects.filter(pk=activity.pk).update(watch_seconds=F('watch_seconds') + watch_seconds)
