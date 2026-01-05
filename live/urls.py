"""
Live Streaming URL Configuration
"""

from django.urls import path
from live import views

app_name = 'live'

urlpatterns = [
    # Live Session Management
    path('sessions/', views.LiveSessionListView.as_view(), name='session-list'),
    path('sessions/create/', views.CreateLiveSessionView.as_view(), name='session-create'),
    path('sessions/<int:pk>/', views.LiveSessionDetailView.as_view(), name='session-detail'),
    path('sessions/<int:session_id>/start/', views.start_session, name='session-start'),
    path('sessions/<int:session_id>/end/', views.end_session, name='session-end'),
    
    # Session Participation
    path('sessions/<int:session_id>/join/', views.join_session, name='session-join'),
    path('sessions/<int:session_id>/leave/', views.leave_session, name='session-leave'),
    path('sessions/<int:session_id>/participants/', views.session_participants, name='session-participants'),
    
    # Streaming Control
    path('sessions/<int:session_id>/streaming/start/', views.start_streaming, name='streaming-start'),
    path('sessions/<int:session_id>/streaming/stop/', views.stop_streaming, name='streaming-stop'),
    path('sessions/<int:session_id>/streaming/status/', views.streaming_status, name='streaming-status'),
    
    # Chat
    path('sessions/<int:session_id>/chat/', views.session_chat_messages, name='session-chat'),
    path('sessions/<int:session_id>/chat/send/', views.send_chat_message, name='chat-send'),
    
    # Q&A
    path('sessions/<int:session_id>/questions/', views.session_questions, name='session-questions'),
    path('sessions/<int:session_id>/questions/ask/', views.ask_question, name='question-ask'),
    path('questions/<int:question_id>/answer/', views.answer_question, name='question-answer'),
    path('questions/<int:question_id>/upvote/', views.upvote_question, name='question-upvote'),
    
    # Polls
    path('sessions/<int:session_id>/polls/', views.session_polls, name='session-polls'),
    path('sessions/<int:session_id>/polls/create/', views.create_poll, name='poll-create'),
    path('polls/<int:poll_id>/start/', views.start_poll, name='poll-start'),
    path('polls/<int:poll_id>/close/', views.close_poll, name='poll-close'),
    path('polls/<int:poll_id>/vote/', views.vote_poll, name='poll-vote'),
    path('polls/<int:poll_id>/results/', views.poll_results, name='poll-results'),
    
    # Recordings
    path('sessions/<int:session_id>/recordings/', views.session_recordings, name='session-recordings'),
    path('sessions/<int:session_id>/recordings/create/', views.create_recording, name='recording-create'),
    path('recordings/<int:recording_id>/', views.recording_detail, name='recording-detail'),
    path('recordings/<int:recording_id>/track/', views.track_recording_view, name='recording-track'),
    
    # Attendance
    path('sessions/<int:session_id>/attendance/', views.session_attendance, name='session-attendance'),
    
    # Analytics
    path('sessions/<int:session_id>/analytics/', views.session_analytics, name='session-analytics'),
    
    # User-specific
    path('upcoming/', views.upcoming_sessions, name='upcoming-sessions'),
    path('history/', views.user_session_history, name='user-history'),
]
