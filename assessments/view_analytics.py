from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

from courses.models import Course
from courses.policies import can_manage_course
from .models import Quiz
from .analytics import (
    get_course_assessment_overview,
    get_quiz_question_analytics
)


class InstructorAssessmentOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)

        if not can_manage_course(request.user, course):
            raise PermissionDenied("Only the course instructor or an admin can view these analytics.")

        data = get_course_assessment_overview(course)
        return Response(data)


class QuizQuestionAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id):
        quiz = get_object_or_404(Quiz, id=quiz_id)
        course = quiz.lesson.module.course

        if not can_manage_course(request.user, course):
            raise PermissionDenied("Only the course instructor or an admin can view these analytics.")

        data = get_quiz_question_analytics(quiz)
        return Response(data)
