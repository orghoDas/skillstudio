from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
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
    get_exam_analytics
)
from courses.models import Course
from accounts.permissions import IsInstructor
from accounts.utils import is_platform_admin
from enrollments.models import Enrollment


def is_admin_user(user):
    return is_platform_admin(user)


def owns_course(user, course):
    return is_admin_user(user) or course.instructor_id == user.id


def owns_exam_course(user, exam):
    return owns_course(user, exam.course)


def has_active_course_enrollment(user, course):
    return Enrollment.objects.filter(
        user=user,
        course=course,
        status='active'
    ).exists()


def ensure_student_can_access_exam(user, exam):
    if is_admin_user(user) or owns_exam_course(user, exam):
        return

    if exam.status != 'published':
        raise PermissionDenied("Exam is not available.")

    if not has_active_course_enrollment(user, exam.course):
        raise PermissionDenied("Active course enrollment required.")


def get_manageable_exam_or_404(user, exam_id):
    exam = get_object_or_404(Exam.objects.select_related('course'), id=exam_id)
    if not owns_exam_course(user, exam):
        raise PermissionDenied("You do not have permission to manage this exam.")
    return exam


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
        queryset = QuestionBank.objects.select_related('course', 'created_by')

        if not is_admin_user(self.request.user):
            queryset = queryset.filter(course__instructor=self.request.user)

        if course_id:
            queryset = queryset.filter(course_id=course_id)

        return queryset
    
    def perform_create(self, serializer):
        course = serializer.validated_data.get('course')
        if not course or not owns_course(self.request.user, course):
            raise PermissionDenied("You do not have permission to create questions for this course.")
        serializer.save(created_by=self.request.user)


class QuestionBankDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a question."""
    permission_classes = [IsAuthenticated, IsInstructor]
    serializer_class = QuestionBankSerializer

    def get_queryset(self):
        queryset = QuestionBank.objects.select_related('course', 'created_by')
        if is_admin_user(self.request.user):
            return queryset
        return queryset.filter(course__instructor=self.request.user)


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
        if is_admin_user(self.request.user):
            return Exam.objects.select_related('course', 'created_by').all()

        if self.request.user.role == 'instructor':
            # Instructors see exams for courses they own.
            return Exam.objects.select_related('course', 'created_by').filter(
                course__instructor=self.request.user
            )
        else:
            # Students see published exams for their enrolled courses
            enrolled_courses = Enrollment.objects.filter(
                user=self.request.user,
                status='active'
            ).values_list('course_id', flat=True)
            
            return Exam.objects.select_related('course', 'created_by').filter(
                course_id__in=enrolled_courses,
                status='published'
            )
    
    def perform_create(self, serializer):
        if self.request.user.role != 'instructor' and not is_admin_user(self.request.user):
            raise PermissionDenied("Only instructors can create exams.")

        course = serializer.validated_data.get('course')
        if not course or not owns_course(self.request.user, course):
            raise PermissionDenied("You do not have permission to create exams for this course.")

        serializer.save(created_by=self.request.user)


class ExamDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete an exam."""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Exam.objects.select_related('course', 'created_by').prefetch_related('questions')
        user = self.request.user

        if is_admin_user(user):
            return queryset

        if user.role == 'instructor':
            return queryset.filter(course__instructor=user)

        if self.request.method not in ('GET', 'HEAD', 'OPTIONS'):
            return queryset.none()

        enrolled_courses = Enrollment.objects.filter(
            user=user,
            status='active'
        ).values_list('course_id', flat=True)

        return queryset.filter(course_id__in=enrolled_courses, status='published')
    
    def get_serializer_class(self):
        if self.request.user.role == 'instructor' or is_admin_user(self.request.user):
            return ExamSerializer
        return ExamDetailSerializer


# ===========================
# 🎯 Exam Taking Views (Students)
# ===========================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_exam_for_course(request, course_id):
    """Get all exams for a course."""
    course = get_object_or_404(Course, id=course_id)
    if not owns_course(request.user, course) and not has_active_course_enrollment(request.user, course):
        raise PermissionDenied("Active course enrollment required.")

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
    exam = get_object_or_404(Exam.objects.select_related('course'), id=exam_id)
    ensure_student_can_access_exam(request.user, exam)
    
    try:
        attempt = start_exam_attempt(exam, request.user)
        serializer = ExamAttemptSerializer(attempt)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    except ValueError:
        return Response({
            'error': 'Exam attempt could not be started.'
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_exam(request, exam_id):
    """Submit exam answers."""
    serializer = SubmitExamSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    attempt_id = serializer.validated_data['attempt_id']
    answers = serializer.validated_data['answers']
    
    attempt = get_object_or_404(
        ExamAttempt.objects.select_related('exam__course'),
        id=attempt_id,
        exam_id=exam_id,
        user=request.user
    )
    ensure_student_can_access_exam(request.user, attempt.exam)
    
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
        
    except ValueError:
        return Response({
            'error': 'Exam submission could not be processed.'
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def exam_attempts_history(request, exam_id):
    """Get user's attempt history for an exam."""
    exam = get_object_or_404(Exam.objects.select_related('course'), id=exam_id)
    ensure_student_can_access_exam(request.user, exam)

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
    attempt = get_object_or_404(
        ExamAttempt.objects.select_related('exam__course'),
        id=attempt_id
    )

    if attempt.user_id != request.user.id and not owns_exam_course(request.user, attempt.exam):
        raise PermissionDenied("You do not have permission to view this result.")

    if attempt.user_id == request.user.id:
        ensure_student_can_access_exam(request.user, attempt.exam)
        if not attempt.exam.show_results_immediately:
            raise PermissionDenied("Result is not available yet.")
    
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
    exam = get_manageable_exam_or_404(request.user, exam_id)
    
    analytics_data = get_exam_analytics(exam)
    return Response(analytics_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsInstructor])
def exam_attempts_list(request, exam_id):
    """Get all attempts for an exam (instructor view)."""
    exam = get_manageable_exam_or_404(request.user, exam_id)
    
    attempts = ExamAttempt.objects.filter(exam=exam).select_related('user')
    serializer = ExamAttemptSerializer(attempts, many=True)
    
    return Response({
        'attempts': serializer.data,
        'total_attempts': attempts.count()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsInstructor])
def publish_exam(request, exam_id):
    """Publish an exam."""
    exam = get_manageable_exam_or_404(request.user, exam_id)
    
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
    exam = get_manageable_exam_or_404(request.user, exam_id)
    
    exam.status = 'archived'
    exam.save()
    
    serializer = ExamSerializer(exam)
    return Response({
        'exam': serializer.data,
        'message': 'Exam archived successfully'
    })
