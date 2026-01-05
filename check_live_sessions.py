import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skillstudio.settings')
django.setup()

from live.models import LiveSession
from django.utils import timezone

sessions = LiveSession.objects.all()
now = timezone.now()

print(f"Current time: {now}")
print(f"\nTotal sessions: {sessions.count()}\n")

for session in sessions:
    print(f"Session: {session.title}")
    print(f"  Status: {session.status}")
    print(f"  Scheduled Start: {session.scheduled_start}")
    print(f"  Scheduled End: {session.scheduled_end}")
    print(f"  Is Live (method): {session.is_live()}")
    print(f"  Is Upcoming (method): {session.is_upcoming()}")
    print(f"  Is Past (method): {session.is_past()}")
    
    # Check if should be live
    if session.scheduled_start <= now <= session.scheduled_end:
        print(f"  >>> SHOULD BE LIVE NOW!")
    elif now < session.scheduled_start:
        print(f"  >>> Starts in: {session.scheduled_start - now}")
    else:
        print(f"  >>> Ended {now - session.scheduled_end} ago")
    
    print()
