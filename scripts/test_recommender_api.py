import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','skillstudio.settings')
django.setup()

from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
User = get_user_model()

client = APIClient()
user = User.objects.get(id=1)
client.force_authenticate(user=user)
resp = client.get('/api/ai-recommender/my/')
print('status', resp.status_code)
print(resp.data)
