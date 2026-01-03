from django.urls import path
from .views import (
    StudentDashboardView,
    StudentActivityFeedView,
    StudentProfileView,
    StudentNoteListCreateView,
    StudentNoteDetailView,
    StudentBookmarkListCreateView,
    StudentBookmarkDetailView,
)

urlpatterns = [
    path('dashboard/', StudentDashboardView.as_view(), name='student-dashboard'),
    path('activity-feed/', StudentActivityFeedView.as_view(), name='student-activity-feed'),
    path('profile/', StudentProfileView.as_view(), name='student-profile'),
    path('notes/', StudentNoteListCreateView.as_view(), name='student-notes-list'),
    path('notes/<uuid:id>/', StudentNoteDetailView.as_view(), name='student-note-detail'),
    path('bookmarks/', StudentBookmarkListCreateView.as_view(), name='student-bookmarks-list'),
    path('bookmarks/<uuid:id>/', StudentBookmarkDetailView.as_view(), name='student-bookmark-detail'),
]
