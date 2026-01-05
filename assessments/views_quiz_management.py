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
        
        # Get or create quiz
        quiz, created = Quiz.objects.get_or_create(
            lesson=lesson,
            defaults={
                'title': f"{lesson.title} Quiz",
                'passing_percentage': 50
            }
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
        
        # Update quiz settings
        quiz.title = request.data.get('title', quiz.title)
        quiz.passing_percentage = request.data.get('passing_percentage', quiz.passing_percentage)
        time_limit_minutes = request.data.get('time_limit_minutes')
        quiz.time_limit_minutes = None if time_limit_minutes in (None, '', 0) else time_limit_minutes
        
        # Delete existing questions
        quiz.questions.all().delete()
        
        # Create new questions
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
