from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Max

from enrollments.models import Enrollment, LessonProgress
from courses.models import Lesson

from accounts.permissions import IsStudent
from enrollments.services import get_resume_lesson
from .services import get_student_activity_feed, get_student_dashboard_data, get_weekly_learning_progress, get_learning_streak, get_student_achievements

# Create your views here.
class StudentDashboardView(APIView):
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
        return Response(feed)