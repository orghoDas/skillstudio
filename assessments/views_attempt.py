from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from certificates.services import issue_certificate_if_eligible

from .models import Quiz, QuizAttempt
from .services_timer import auto_submit_attempt
from .services_scoring import calculate_quiz_score


class StartQuizAttemptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quiz_id):
        quiz = get_object_or_404(Quiz, id=quiz_id)

        attempt, created = QuizAttempt.objects.get_or_create(
            quiz=quiz,
            user=request.user,
            completed_at__isnull=True,
            defaults={}
        )

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
            raise ValidationError("Attempt already completed.")

        if attempt.quiz.has_time_limit() and attempt.is_expired():
            auto_submit_attempt(attempt)
            raise ValidationError("Time expired. Auto-submitted.")

        question_id = str(request.data["question_id"])
        option_id = request.data["option_id"]

        attempt.answers[question_id] = option_id
        attempt.save(update_fields=["answers"])

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

        certificate = issue_certificate_if_eligible(attempt)

        return Response({
            "score": attempt.score,
            "auto_submitted": attempt.is_auto_submitted,
            "certificate_issued": bool(certificate),
            "certificate_code": (
                str(certificate.certificate_code)
                if certificate else None
            )
        })

