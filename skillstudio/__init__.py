from .celery import app as celery_app

# Expose Celery app as a module-level variable for `celery -A skillstudio`.
__all__ = ('celery_app',)
