import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skillstudio.settings')

app = Celery('skillstudio')

# Read broker URL from environment; default to redis on localhost
app.conf.broker_url = os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
app.conf.result_backend = os.getenv('CELERY_RESULT_BACKEND', app.conf.broker_url)

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from installed apps
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
