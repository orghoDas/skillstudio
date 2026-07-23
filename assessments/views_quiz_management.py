from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction

from courses.models import Lesson
from .models import Quiz, QuizQuestion, QuestionOption
from .serializers import ManageQuizDetailSerializer


class ManageQuizView(APIView):
    """Create or update quiz for a lesson (instructor only)"""
    permission_classes = [IsAuthenticated]

    def get(self, request, lesson_id):
        """Get quiz for a lesson"""
        lesson = get_object_or_404(Lesson, id=lesson_id)
        
        # Check if user is the instructor
        if lesson.module.course.instructor != request.user:
            return Response(
                {'error': 'You do not have permission to access this quiz'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        quiz = Quiz.objects.filter(lesson=lesson).first()
        if not quiz:
            return Response(
                {'error': 'Quiz not found for this lesson.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(ManageQuizDetailSerializer(quiz).data)

    @transaction.atomic
    def post(self, request, lesson_id):
        """Create or update quiz questions"""
        lesson = get_object_or_404(Lesson, id=lesson_id)
        
        # Check if user is the instructor
        if lesson.module.course.instructor != request.user:
            return Response(
                {'error': 'You do not have permission to manage this quiz'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get or create quiz
        quiz, created = Quiz.objects.get_or_create(
            lesson=lesson,
            defaults={
                'title': request.data.get('title', f"{lesson.title} Quiz"),
                'passing_percentage': request.data.get('passing_percentage', 50),
                'time_limit_minutes': request.data.get('time_limit_minutes')
            }
        )

        replacing_questions = 'questions' in request.data
        if not created and replacing_questions and quiz.attempts.exists():
            return Response(
                {
                    'error': (
                        'Quiz questions cannot be replaced after attempts exist. '
                        'Create a new quiz version instead.'
                    )
                },
                status=status.HTTP_409_CONFLICT
            )

        # Update quiz settings
        quiz.title = request.data.get('title', quiz.title)
        quiz.passing_percentage = request.data.get('passing_percentage', quiz.passing_percentage)
        if 'time_limit_minutes' in request.data:
            time_limit_minutes = request.data.get('time_limit_minutes')
            quiz.time_limit_minutes = None if time_limit_minutes in (None, '', 0) else time_limit_minutes

        if replacing_questions:
            # Replace questions only while there is no attempt history to preserve.
            quiz.questions.all().delete()

            questions_data = request.data.get('questions', [])
            total_marks = 0

            for q_data in questions_data:
                question = QuizQuestion.objects.create(
                    quiz=quiz,
                    question_text=q_data.get('text', ''),
                    question_type=q_data.get('type', 'mcq'),
                    marks=q_data.get('marks', 1)
                )
                total_marks += question.marks

                # Create options
                for opt_data in q_data.get('options', []):
                    QuestionOption.objects.create(
                        question=question,
                        option_text=opt_data.get('text', ''),
                        is_correct=opt_data.get('is_correct', False)
                    )

            # Update total marks
            quiz.total_marks = total_marks

        quiz.save()

        return Response({
            'message': 'Quiz saved successfully',
            'quiz': ManageQuizDetailSerializer(quiz).data
        }, status=status.HTTP_200_OK)
