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
from .services import (
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
        require_active_enrollment(request.user, quiz.lesson.module.course)
        return Response(QuizDetailSerializer(quiz).data)


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
