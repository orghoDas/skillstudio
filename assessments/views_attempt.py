from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
# from certificates.services import issue_certificate_if_eligible
from enrollments.services import require_active_enrollment

from .models import Quiz, QuizAttempt
from .services import save_quiz_answer, start_quiz_attempt
from .services_timer import auto_submit_attempt
from .services_scoring import calculate_quiz_score


class StartQuizAttemptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quiz_id):
        quiz = get_object_or_404(Quiz, id=quiz_id)
        require_active_enrollment(request.user, quiz.lesson.module.course)

        try:
            attempt = start_quiz_attempt(request.user, quiz)
        except ValidationError as exc:
            return Response({"error": exc.messages[0]}, status=status.HTTP_409_CONFLICT)

        return Response({
            "attempt_id": attempt.id,
            "started_at": attempt.started_at,
            "time_remaining_seconds": attempt.time_remaining_seconds()
        })


class SubmitQuizAnswerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(
            QuizAttempt,
            id=attempt_id,
            user=request.user
        )

        if attempt.completed_at:
            return Response(
                {"error": "Attempt already completed."},
                status=status.HTTP_409_CONFLICT,
            )

        if attempt.quiz.has_time_limit() and attempt.is_expired():
            auto_submit_attempt(attempt)
            return Response(
                {"error": "Time expired. Auto-submitted."},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            question_id = request.data["question_id"]
            option_id = request.data["option_id"]
        except KeyError as exc:
            return Response(
                {"error": f"Missing required field: {exc.args[0]}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            attempt = save_quiz_answer(attempt, question_id, option_id)
        except ValidationError as exc:
            return Response(
                {"error": exc.messages[0]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "status": "answer_saved",
            "time_remaining_seconds": attempt.time_remaining_seconds()
        })


class SubmitQuizAttemptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(
            QuizAttempt,
            id=attempt_id,
            user=request.user
        )

        if attempt.completed_at:
            return Response({
                "score": attempt.score,
                "auto_submitted": attempt.is_auto_submitted
            })

        if attempt.quiz.has_time_limit() and attempt.is_expired():
            auto_submit_attempt(attempt)
        else:
            calculate_quiz_score(attempt)

        # certificate = issue_certificate_if_eligible(attempt)

        return Response({
            "score": attempt.score,
            "auto_submitted": attempt.is_auto_submitted,
            # "certificate_issued": bool(certificate),
            # "certificate_code": (
            #     str(certificate.certificate_code)
            #     if certificate else None
            # )
        })
