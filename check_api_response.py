import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skillstudio.settings')
django.setup()

from live.models import LiveSession
from live.serializers import LiveSessionSerializer

sessions = LiveSession.objects.all()

for session in sessions:
    serializer = LiveSessionSerializer(session)
    data = serializer.data
    
    print(f"\nSession: {data['title']}")
    print(f"Status in DB: {session.status}")
    print(f"Status in API: {data['status']}")
    print(f"is_live in API: {data['is_live']}")
    print(f"is_upcoming in API: {data['is_upcoming']}")
    print(f"is_past in API: {data['is_past']}")
    print(f"scheduled_start: {data['scheduled_start']}")
    print(f"scheduled_end: {data['scheduled_end']}")
