from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import QuestionBank, Exam, ExamAttempt, ExamResult
from .serializers import (
    QuestionBankSerializer, QuestionBankListSerializer,
    ExamSerializer, ExamListSerializer, ExamDetailSerializer,
    ExamAttemptSerializer, ExamAttemptListSerializer,
    ExamResultSerializer, SubmitExamSerializer
)
from .services import (
    start_exam_attempt, submit_exam_attempt,
    get_exam_analytics, grade_manual_questions
)
from courses.models import Course
from accounts.permissions import IsInstructor, IsStudent


# ===========================
# 📝 Question Bank Views
# ===========================

class QuestionBankListView(generics.ListCreateAPIView):
    """List all questions or create new question."""
    permission_classes = [IsAuthenticated, IsInstructor]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return QuestionBankSerializer
        return QuestionBankListSerializer
    
    def get_queryset(self):
        course_id = self.request.query_params.get('course_id')
        if course_id:
            return QuestionBank.objects.filter(course_id=course_id)
        return QuestionBank.objects.all()
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class QuestionBankDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a question."""
    permission_classes = [IsAuthenticated, IsInstructor]
    serializer_class = QuestionBankSerializer
    queryset = QuestionBank.objects.all()


# ===========================
# 📋 Exam Management Views (Instructors)
# ===========================

class ExamListCreateView(generics.ListCreateAPIView):
    """List all exams or create new exam."""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ExamSerializer
        return ExamListSerializer
    
    def get_queryset(self):
        if self.request.user.role == 'instructor':
            # Instructors see all exams they created
            return Exam.objects.filter(created_by=self.request.user)
        else:
            # Students see published exams for their enrolled courses
            from enrollments.models import Enrollment
            enrolled_courses = Enrollment.objects.filter(
                user=self.request.user,
                status='active'
            ).values_list('course_id', flat=True)
            
            return Exam.objects.filter(
                course_id__in=enrolled_courses,
                status='published'
            )
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ExamDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete an exam."""
    permission_classes = [IsAuthenticated]
    queryset = Exam.objects.all()
    
    def get_serializer_class(self):
        if self.request.user.role == 'instructor':
            return ExamSerializer
        return ExamDetailSerializer


# ===========================
# 🎯 Exam Taking Views (Students)
# ===========================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_exam_for_course(request, course_id):
    """Get all exams for a course."""
    exams = Exam.objects.filter(
        course_id=course_id,
        status='published'
    )
    
    serializer = ExamListSerializer(exams, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_exam(request, exam_id):
    """Start a new exam attempt."""
    exam = get_object_or_404(Exam, id=exam_id)
    
    try:
        attempt = start_exam_attempt(exam, request.user)
        serializer = ExamAttemptSerializer(attempt)
        
        return Response({
            'attempt': serializer.data,
            'message': 'Exam attempt started successfully'
        }, status=status.HTTP_201_CREATED)
        
    except ValueError as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_exam(request, exam_id):
    """Submit exam answers."""
    serializer = SubmitExamSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    attempt_id = serializer.validated_data['attempt_id']
    answers = serializer.validated_data['answers']
    
    attempt = get_object_or_404(ExamAttempt, id=attempt_id, user=request.user)
    
    try:
        submitted_attempt = submit_exam_attempt(attempt, answers)
        
        response_data = {
            'score': submitted_attempt.score,
            'percentage': submitted_attempt.percentage,
            'passed': submitted_attempt.passed,
            'total_marks': submitted_attempt.exam.total_marks,
            'message': 'Exam submitted successfully'
        }
        
        # Include detailed results if exam settings allow
        if submitted_attempt.exam.show_results_immediately:
            if hasattr(submitted_attempt, 'result'):
                result_serializer = ExamResultSerializer(submitted_attempt.result)
                response_data['result'] = result_serializer.data
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def exam_attempts_history(request, exam_id):
    """Get user's attempt history for an exam."""
    attempts = ExamAttempt.objects.filter(
        exam_id=exam_id,
        user=request.user
    ).order_by('-started_at')
    
    serializer = ExamAttemptListSerializer(attempts, many=True)
    return Response({
        'attempts': serializer.data,
        'total_attempts': attempts.count()
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def exam_result_detail(request, attempt_id):
    """Get detailed result for an attempt."""
    attempt = get_object_or_404(ExamAttempt, id=attempt_id, user=request.user)
    
    if not hasattr(attempt, 'result'):
        return Response({
            'error': 'Result not available yet'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = ExamResultSerializer(attempt.result)
    return Response(serializer.data)


# ===========================
# 👨‍🏫 Instructor Views
# ===========================

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsInstructor])
def exam_analytics(request, exam_id):
    """Get analytics for an exam."""
    exam = get_object_or_404(Exam, id=exam_id)
    
    analytics_data = get_exam_analytics(exam)
    return Response(analytics_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsInstructor])
def exam_attempts_list(request, exam_id):
    """Get all attempts for an exam (instructor view)."""
    exam = get_object_or_404(Exam, id=exam_id)
    
    attempts = ExamAttempt.objects.filter(exam=exam).select_related('user')
    serializer = ExamAttemptSerializer(attempts, many=True)
    
    return Response({
        'attempts': serializer.data,
        'total_attempts': attempts.count()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsInstructor])
def grade_manual_exam(request, attempt_id):
    """Manually grade essay/short answer questions."""
    attempt = get_object_or_404(ExamAttempt, id=attempt_id)
    
    manual_grades = request.data.get('manual_grades', {})
    
    if not manual_grades:
        return Response({
            'error': 'No manual grades provided'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    graded_attempt = grade_manual_questions(attempt, manual_grades, request.user)
    serializer = ExamAttemptSerializer(graded_attempt)
    
    return Response({
        'attempt': serializer.data,
        'message': 'Exam graded successfully'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsInstructor])
def publish_exam(request, exam_id):
    """Publish an exam."""
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    
    if exam.get_question_count() == 0:
        return Response({
            'error': 'Cannot publish exam with no questions'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    exam.status = 'published'
    exam.save()
    
    serializer = ExamSerializer(exam)
    return Response({
        'exam': serializer.data,
        'message': 'Exam published successfully'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsInstructor])
def archive_exam(request, exam_id):
    """Archive an exam."""
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    
    exam.status = 'archived'
    exam.save()
    
    serializer = ExamSerializer(exam)
    return Response({
        'exam': serializer.data,
        'message': 'Exam archived successfully'
    })

