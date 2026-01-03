from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Max
from django.core.exceptions import ValidationError as DjangoValidationError, PermissionDenied as DjangoPermissionDenied

from accounts.mixins import StudentOnlyMixin
from accounts.permissions import IsStudent
from enrollments.models import Enrollment, LessonProgress
from courses.models import Lesson
from enrollments.services import get_resume_lesson
from .models import StudentProfile, StudentNote, StudentBookmark
from .serializers import (
    StudentProfileSerializer,
    StudentNoteSerializer,
    StudentNoteListSerializer,
    StudentBookmarkSerializer,
    StudentDashboardSerializer,
    StudentActivityFeedSerializer,
)
from .services import (
    get_student_activity_feed,
    get_student_dashboard_data,
    get_weekly_learning_progress,
    get_learning_streak,
    get_student_achievements,
    get_or_create_student_profile,
    update_student_profile,
    create_student_note,
    update_student_note,
    delete_student_note,
    create_bookmark,
    delete_bookmark,
    get_student_notes,
    get_student_bookmarks,
)


class StudentDashboardView(APIView, StudentOnlyMixin):
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        streak = get_learning_streak(request.user)
        weekly = get_weekly_learning_progress(request.user)
        achievements = get_student_achievements(request.user, streak)
        dashboard = get_student_dashboard_data(request.user)
        activity_feed = get_student_activity_feed(request.user, limit=5)
        
        return Response({
            "streak": streak,
            "weekly_progress": weekly,
            "achievements": achievements,
            "courses": dashboard,
            "activity_feed": activity_feed,
        })

    
class StudentActivityFeedView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        feed = get_student_activity_feed(request.user)
        serializer = StudentActivityFeedSerializer(feed, many=True)
        return Response(serializer.data)


class StudentProfileView(APIView):
    """Get or update student profile."""
    permission_classes = [IsAuthenticated, IsStudent]
    
    def get(self, request):
        profile = get_or_create_student_profile(request.user)
        serializer = StudentProfileSerializer(profile)
        return Response(serializer.data)
    
    def put(self, request):
        try:
            profile = update_student_profile(request.user, **request.data)
            serializer = StudentProfileSerializer(profile)
            return Response(serializer.data)
        except DjangoValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def patch(self, request):
        try:
            profile = update_student_profile(request.user, **request.data)
            serializer = StudentProfileSerializer(profile)
            return Response(serializer.data)
        except DjangoValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class StudentNoteListCreateView(ListCreateAPIView):
    """List and create student notes."""
    permission_classes = [IsAuthenticated, IsStudent]
    serializer_class = StudentNoteListSerializer
    
    def get_queryset(self):
        lesson_id = self.request.query_params.get('lesson')
        course_id = self.request.query_params.get('course')
        return get_student_notes(
            self.request.user,
            lesson_id=lesson_id,
            course_id=course_id
        )
    
    def post(self, request):
        try:
            note = create_student_note(
                user=request.user,
                lesson_id=request.data.get('lesson'),
                content=request.data.get('content'),
                timestamp=request.data.get('timestamp', 0),
                tags=request.data.get('tags', [])
            )
            serializer = StudentNoteSerializer(note)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except DjangoValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class StudentNoteDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a student note."""
    permission_classes = [IsAuthenticated, IsStudent]
    serializer_class = StudentNoteSerializer
    lookup_field = 'id'
    
    def get_queryset(self):
        return StudentNote.objects.filter(user=self.request.user)
    
    def put(self, request, id):
        try:
            note = update_student_note(id, request.user, **request.data)
            serializer = StudentNoteSerializer(note)
            return Response(serializer.data)
        except (DjangoValidationError, DjangoPermissionDenied) as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def patch(self, request, id):
        try:
            note = update_student_note(id, request.user, **request.data)
            serializer = StudentNoteSerializer(note)
            return Response(serializer.data)
        except (DjangoValidationError, DjangoPermissionDenied) as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def delete(self, request, id):
        try:
            delete_student_note(id, request.user)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except (DjangoValidationError, DjangoPermissionDenied) as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class StudentBookmarkListCreateView(ListCreateAPIView):
    """List and create student bookmarks."""
    permission_classes = [IsAuthenticated, IsStudent]
    serializer_class = StudentBookmarkSerializer
    
    def get_queryset(self):
        return get_student_bookmarks(self.request.user)
    
    def post(self, request):
        try:
            bookmark = create_bookmark(
                user=request.user,
                course_id=request.data.get('course'),
                lesson_id=request.data.get('lesson'),
                note=request.data.get('note', '')
            )
            serializer = StudentBookmarkSerializer(bookmark)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except DjangoValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class StudentBookmarkDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve or delete a student bookmark."""
    permission_classes = [IsAuthenticated, IsStudent]
    serializer_class = StudentBookmarkSerializer
    lookup_field = 'id'
    
    def get_queryset(self):
        return StudentBookmark.objects.filter(user=self.request.user)
    
    def delete(self, request, id):
        try:
            delete_bookmark(id, request.user)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except (DjangoValidationError, DjangoPermissionDenied) as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )