from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from enrollments.services import require_active_enrollment

from .models import Quiz, QuizAttempt
from .serializers import (
    QuizDetailSerializer,
    QuizAttemptSerializer,
)
from courses.policies import can_manage_course
from .services import (
    get_quiz_attempt_status,
    start_quiz_attempt,
    submit_quiz_attempt,
)


# ======================================================
# QUIZ APIs
# ======================================================

class QuizDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, lesson_id):
        quiz = get_object_or_404(Quiz, lesson_id=lesson_id)
        course = quiz.lesson.module.course
        require_active_enrollment(request.user, course)
        if not quiz.is_published and not can_manage_course(request.user, course):
            # Students can't start an unpublished quiz, so don't show it (ASM-01).
            return Response({"error": "Quiz not found."}, status=status.HTTP_404_NOT_FOUND)

        data = QuizDetailSerializer(quiz).data
        # The student's retake status (ASM-01): attempts used/remaining, passed, last result.
        data["attempt_status"] = get_quiz_attempt_status(request.user, quiz)
        return Response(data)


class StartQuizView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quiz_id):
        quiz = get_object_or_404(Quiz, id=quiz_id)
        require_active_enrollment(request.user, quiz.lesson.module.course)

        try:
            attempt = start_quiz_attempt(request.user, quiz)
        except ValidationError as exc:
            return Response({"error": exc.messages[0]}, status=status.HTTP_409_CONFLICT)

        return Response(QuizAttemptSerializer(attempt).data)


class SubmitQuizView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(
            QuizAttempt,
            id=attempt_id,
            user=request.user
        )

        answers = request.data.get("answers", {})
        try:
            attempt = submit_quiz_attempt(attempt, answers)
        except ValidationError as exc:
            return Response(
                {"error": exc.messages[0]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(QuizAttemptSerializer(attempt).data)
