from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

from enrollments.services import require_active_enrollment

from .models import Quiz, Assignment, QuizAttempt, Submission
from .serializers import (
    QuizDetailSerializer,
    QuizAttemptSerializer,
    AssignmentSerializer,
    SubmissionSerializer
)
from .services import (
    start_quiz_attempt,
    submit_quiz_attempt,
    submit_assignment
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

        attempt = start_quiz_attempt(request.user, quiz)
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
        attempt = submit_quiz_attempt(attempt, answers)

        return Response(QuizAttemptSerializer(attempt).data)


# ======================================================
# ASSIGNMENT APIs
# ======================================================

class AssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, lesson_id):
        assignment = get_object_or_404(Assignment, lesson_id=lesson_id)
        require_active_enrollment(request.user, assignment.lesson.module.course)

        return Response(AssignmentSerializer(assignment).data)


class SubmitAssignmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        assignment = get_object_or_404(Assignment, id=assignment_id)
        require_active_enrollment(request.user, assignment.lesson.module.course)

        submission = submit_assignment(
            request.user,
            assignment,
            file_url=request.data.get("file_url"),
            text=request.data.get("text")
        )

        return Response(SubmissionSerializer(submission).data)


class SubmitAssignmentByLessonView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, lesson_id):
        from courses.models import Lesson
        
        lesson = get_object_or_404(Lesson, id=lesson_id)
        require_active_enrollment(request.user, lesson.module.course)
        
        # Get or create assignment for this lesson
        assignment, created = Assignment.objects.get_or_create(
            lesson=lesson,
            defaults={
                'title': f"Assignment - {lesson.title}",
                'instructions': lesson.content_text or ''
            }
        )
        
        # Handle file upload if present
        file_url = None
        uploaded_file = request.FILES.get('file')
        if uploaded_file:
            # Save file and get URL
            from django.core.files.storage import default_storage
            file_path = f'assignments/{request.user.id}/{lesson_id}/{uploaded_file.name}'
            saved_path = default_storage.save(file_path, uploaded_file)
            file_url = default_storage.url(saved_path)
        
        # Get text submission
        text = request.data.get('text', '') or request.data.get('comments', '')
        
        submission = submit_assignment(
            request.user,
            assignment,
            file_url=file_url,
            text=text
        )

        return Response({
            'message': 'Assignment submitted successfully',
            'submission': SubmissionSerializer(submission).data
        })
