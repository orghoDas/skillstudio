"""
WebSocket routing for live streaming.
"""

from django.urls import re_path
from live import consumers

websocket_urlpatterns = [
    re_path(r'ws/live/sessions/(?P<session_id>\d+)/$', consumers.LiveStreamConsumer.as_asgi()),
]
