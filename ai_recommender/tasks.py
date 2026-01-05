from celery import shared_task
from django.contrib.auth import get_user_model

from ai_recommender.services import generate_recommendations_for_user

User = get_user_model()


@shared_task(bind=True, ignore_result=True)
def generate_recommendations_task(self, top_n=10):
    """Generate recommendations for all users in a simple loop.

    This is intentionally minimal: for larger deployments, split users into
    batches and run in parallel worker tasks.
    """
    count = 0
    for user in User.objects.all():
        try:
            recs = generate_recommendations_for_user(user, top_n=top_n)
            count += len(recs)
        except Exception:
            # swallow exceptions per-user to keep task running
            continue
    return count
