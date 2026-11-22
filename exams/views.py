from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema

from .models import QuestionBank, Exam, ExamAttempt
from enrollments.constants import ACCESS_STATUSES
from .serializers import (
    QuestionBankSerializer, QuestionBankListSerializer,
    ExamSerializer, ExamListSerializer, ExamDetailSerializer,
    ExamAttemptSerializer, ExamAttemptListSerializer,
    ExamResultSerializer, ExamAnswersSerializer
)
from .services import (
    ExamUnavailable, attempt_started_within_window, current_exam_questions, ensure_question_bank_matches_course,
    get_exam_analytics, record_exam_answers, start_exam_attempt, submit_exam_attempt, validated_exam_total,
)
from .grading import MAX_EXAM_MARKS, total_question_marks
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
        status__in=ACCESS_STATUSES
    ).exists()


def ensure_student_can_access_exam(user, exam):
    if is_admin_user(user) or owns_exam_course(user, exam):
        return

    if exam.status != 'published':
        raise PermissionDenied("Exam is not available.")

    if not has_active_course_enrollment(user, exam.course):
        raise PermissionDenied("Active course enrollment required.")


def get_manageable_exam_or_404(user, exam_id, *, lock=False):
    exams = Exam.objects.select_related('course')
    if lock:
        exams = exams.select_for_update(of=('self',))
    exam = get_object_or_404(exams, id=exam_id)
    if not owns_exam_course(user, exam):
        raise PermissionDenied("You do not have permission to manage this exam.")
    return exam


def exam_result_context(user, exam):
    manages_exam = owns_exam_course(user, exam)
    show_results = manages_exam or exam.show_results_immediately
    show_review = manages_exam or (show_results and exam.show_correct_answers)
    if show_review:
        try:
            ensure_question_bank_matches_course(exam)
        except ExamUnavailable:
            show_review = False
    return {'manages_exam': manages_exam, 'show_results': show_results, 'show_question_review': show_review}


def lock_selected_questions(serializer, course):
    questions = serializer.validated_data.get('questions', [])
    ids = {question.pk for question in questions}
    if not ids:
        return
    locked = list(QuestionBank.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
    if len(locked) != len(ids) or any(question.course_id != course.pk for question in locked):
        raise ValidationError({'questions': 'Select questions from this exam’s course.'})


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
        queryset = QuestionBank.objects.select_related('course', 'created_by__profile')
        if is_admin_user(self.request.user):
            return queryset
        return queryset.filter(course__instructor=self.request.user)

    def _lock_related_exams(self, question):
        exams = list(Exam.objects.filter(questions=question).order_by('pk').select_for_update(of=('self',)))
        if any(exam.attempts.exists() for exam in exams):
            raise ValidationError("This question has been used in an exam attempt. Create a new question for future exams.")
        return exams

    @staticmethod
    def _refresh_marks(exams):
        for exam in exams:
            questions = current_exam_questions(exam)
            total = total_question_marks(questions)
            if exam.status == 'published':
                try:
                    validated_exam_total(questions, exam.passing_marks)
                except ExamUnavailable as exc:
                    raise ValidationError(f"{exam.title}: {exc.message}") from exc
            if total > MAX_EXAM_MARKS:
                raise ValidationError("The exam's question total may not exceed 9999.99.")
            exam.total_marks = total
            exam.save(update_fields=['total_marks', 'updated_at'])

    @transaction.atomic
    def perform_update(self, serializer):
        question = serializer.instance
        exams = self._lock_related_exams(question)
        locked = get_object_or_404(QuestionBank.objects.select_for_update(), pk=question.pk)
        if locked.course_id != question.course_id:
            raise ValidationError("The question was moved. Reload before editing it.")
        course = serializer.validated_data.get('course', question.course)
        if not owns_course(self.request.user, course):
            raise PermissionDenied("You do not have permission to manage questions in that course.")
        if course.pk != question.course_id and question.exams.exists():
            raise ValidationError("A question assigned to an exam cannot be moved to a different course.")
        serializer.save()
        self._refresh_marks(exams)

    @transaction.atomic
    def perform_destroy(self, instance):
        exams = self._lock_related_exams(instance)
        instance.delete()
        self._refresh_marks(exams)


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
        user = self.request.user
        queryset = Exam.objects.select_related('course', 'created_by')
        if not is_admin_user(user):
            if user.role == 'instructor':
                queryset = queryset.filter(course__instructor=user)
            else:
                enrolled_courses = Enrollment.objects.filter(user=user, status__in=ACCESS_STATUSES)
                queryset = queryset.filter(course_id__in=enrolled_courses.values('course_id'), status='published')

        availability = self.request.query_params.get('availability')
        now = timezone.now()
        if availability == 'upcoming':
            queryset = queryset.filter(status='published', start_datetime__gt=now)
        elif availability == 'active':
            queryset = queryset.filter(status='published').filter(
                Q(start_datetime__isnull=True) | Q(start_datetime__lte=now),
                Q(end_datetime__isnull=True) | Q(end_datetime__gte=now),
            )
        elif availability == 'completed':
            attempts = ExamAttempt.objects.filter(exam_id=OuterRef('pk'), status='completed')
            if not is_admin_user(user) and user.role != 'instructor':
                attempts = attempts.filter(user=user)
            queryset = queryset.filter(Exists(attempts))
        return queryset.order_by('-created_at', '-pk')

    @transaction.atomic
    def perform_create(self, serializer):
        if self.request.user.role != 'instructor' and not is_admin_user(self.request.user):
            raise PermissionDenied("Only instructors can create exams.")

        course = serializer.validated_data.get('course')
        if not course or not owns_course(self.request.user, course):
            raise PermissionDenied("You do not have permission to create exams for this course.")

        lock_selected_questions(serializer, course)
        serializer.save(created_by=self.request.user)


class ExamDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete an exam."""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Exam.objects.select_related('course', 'created_by__profile').prefetch_related('questions')
        user = self.request.user
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            queryset = queryset.select_for_update(of=('self',))

        if is_admin_user(user):
            return queryset

        if user.role == 'instructor':
            return queryset.filter(course__instructor=user)

        if self.request.method not in ('GET', 'HEAD', 'OPTIONS'):
            return queryset.none()

        enrolled_courses = Enrollment.objects.filter(
            user=user,
            status__in=ACCESS_STATUSES
        ).values_list('course_id', flat=True)

        return queryset.filter(course_id__in=enrolled_courses, status='published')
    
    def get_serializer_class(self):
        if self.request.method not in ('GET', 'HEAD', 'OPTIONS'):
            return ExamSerializer
        if getattr(self.request.user, 'role', None) == 'instructor' or is_admin_user(self.request.user):
            return ExamSerializer
        return ExamDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        exam = self.get_object()
        serializer_class = self.get_serializer_class()
        context = self.get_serializer_context()
        if serializer_class is ExamDetailSerializer:
            attempts = ExamAttempt.objects.filter(exam=exam, user=request.user)
            attempt_id = request.query_params.get('attempt')
            if attempt_id is not None:
                try:
                    attempt_id = int(attempt_id)
                except ValueError as exc:
                    raise ValidationError({'attempt': 'Invalid attempt ID.'}) from exc
                attempt = get_object_or_404(attempts, pk=attempt_id)
            else:
                attempt = attempts.filter(status='in_progress').first()
            if attempt and attempt.status == 'in_progress':
                try:
                    ensure_question_bank_matches_course(exam)
                except ExamUnavailable:
                    attempt = None
            context['attempt'] = _finalize_if_due(attempt)
        return Response(serializer_class(exam, context=context).data)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        course = serializer.validated_data.get('course', serializer.instance.course)
        if not owns_course(self.request.user, course):
            raise PermissionDenied("You do not have permission to manage exams in that course.")
        lock_selected_questions(serializer, course)
        serializer.save()

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if instance.attempts.exists():
            raise ValidationError("Archive this exam to preserve its attempts and results.")
        instance.delete()


def _finalize_if_due(attempt):
    if attempt and attempt.status == 'in_progress':
        if not attempt_started_within_window(attempt):
            return None
        if attempt.is_expired() or attempt.snapshot is None:
            try:
                return record_exam_answers(attempt)
            except ExamUnavailable:
                # Legacy attempts created outside the window cannot reveal questions.
                return None
    return attempt


# ===========================
# 🎯 Exam Taking Views (Students)
# ===========================

class CourseExamListView(generics.ListAPIView):
    """Published exams accessible to an enrolled learner or course manager."""
    permission_classes = [IsAuthenticated]
    serializer_class = ExamListSerializer
    queryset = Exam.objects.none()

    def get_queryset(self):
        course = get_object_or_404(Course, pk=self.kwargs['course_id'])
        if not owns_course(self.request.user, course) and not has_active_course_enrollment(self.request.user, course):
            raise PermissionDenied("Active course enrollment required.")
        return Exam.objects.filter(course=course, status='published').select_related('course').order_by('-created_at', '-pk')


@extend_schema(request=None, responses={201: ExamAttemptSerializer})
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

    except ExamUnavailable as exc:
        # EXM-01: say why (not open yet / closed / no attempts left).
        return Response({'error': exc.message, 'code': exc.code}, status=status.HTTP_409_CONFLICT)
    except ValueError:
        return Response({
            'error': 'Exam attempt could not be started.'
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(request=ExamAnswersSerializer, responses=OpenApiTypes.OBJECT)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_exam(request, exam_id):
    """Submit exam answers."""
    attempt, answers = _get_attempt_and_answers(request, exam_id)
    try:
        submitted_attempt = submit_exam_attempt(attempt, answers)
    except ExamUnavailable as exc:
        return Response({'error': exc.message, 'code': exc.code}, status=status.HTTP_409_CONFLICT)

    context = exam_result_context(request.user, submitted_attempt.exam)
    response_data = {
        'score': submitted_attempt.score if context['show_results'] else None,
        'percentage': submitted_attempt.percentage if context['show_results'] else None,
        'passed': submitted_attempt.passed if context['show_results'] else None,
        'total_marks': submitted_attempt.grading_total_marks,
        'message': 'Exam submitted successfully'
    }
    if context['show_results'] and hasattr(submitted_attempt, 'result'):
        response_data['result'] = ExamResultSerializer(submitted_attempt.result, context=context).data
    return Response(response_data)


def _get_attempt_and_answers(request, exam_id):
    serializer = ExamAnswersSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    attempt = get_object_or_404(
        ExamAttempt.objects.select_related('exam__course'),
        id=serializer.validated_data['attempt_id'],
        exam_id=exam_id,
        user=request.user
    )
    ensure_student_can_access_exam(request.user, attempt.exam)
    return attempt, serializer.validated_data['answers']


@extend_schema(request=ExamAnswersSerializer, responses=OpenApiTypes.OBJECT)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_exam_answers(request, exam_id):
    """Save changes to an in-progress exam or finish an overdue attempt."""
    attempt, answers = _get_attempt_and_answers(request, exam_id)
    try:
        attempt = record_exam_answers(attempt, answers)
    except ExamUnavailable as exc:
        return Response({'error': exc.message, 'code': exc.code}, status=status.HTTP_409_CONFLICT)
    return Response({'status': attempt.status, 'time_remaining': attempt.time_remaining_seconds()})


class ExamAttemptsListView(generics.ListAPIView):
    """Paginate attempt records before finalizing overdue attempts on this page."""
    queryset = ExamAttempt.objects.none()

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        attempts = [_finalize_if_due(attempt) or attempt for attempt in page]
        return self.get_paginated_response(self.get_serializer(attempts, many=True).data)


class ExamHistoryView(ExamAttemptsListView):
    permission_classes = [IsAuthenticated]
    serializer_class = ExamAttemptListSerializer

    def get_queryset(self):
        exam = get_object_or_404(Exam.objects.select_related('course'), pk=self.kwargs['exam_id'])
        ensure_student_can_access_exam(self.request.user, exam)
        self.result_context = exam_result_context(self.request.user, exam)
        attempts = ExamAttempt.objects.filter(exam=exam, user=self.request.user)
        if self.request.query_params.get('status') == 'completed':
            attempts = attempts.filter(status='completed')
        return attempts.select_related(
            'exam', 'result', 'user__profile',
        ).order_by('-started_at', '-pk')

    def get_serializer_context(self):
        return {**super().get_serializer_context(), **getattr(self, 'result_context', {})}


@extend_schema(responses=ExamResultSerializer)
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

    context = exam_result_context(request.user, attempt.exam)
    if attempt.user_id == request.user.id and not context['manages_exam']:
        ensure_student_can_access_exam(request.user, attempt.exam)
        if not context['show_results']:
            raise PermissionDenied("Result is not available yet.")
    attempt = _finalize_if_due(attempt) or attempt
    if not hasattr(attempt, 'result'):
        return Response({
            'error': 'Result not available yet'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = ExamResultSerializer(attempt.result, context=context)
    return Response(serializer.data)


# ===========================
# 👨‍🏫 Instructor Views
# ===========================

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsInstructor])
def exam_analytics(request, exam_id):
    """Get analytics for an exam."""
    exam = get_manageable_exam_or_404(request.user, exam_id)
    try:
        ensure_question_bank_matches_course(exam)
    except ExamUnavailable as exc:
        return Response({'error': exc.message, 'code': exc.code}, status=status.HTTP_409_CONFLICT)
    for attempt in exam.attempts.filter(status='in_progress').select_related('exam'):
        _finalize_if_due(attempt)
    analytics_data = get_exam_analytics(exam)
    return Response(analytics_data)


class InstructorExamAttemptsView(ExamAttemptsListView):
    permission_classes = [IsAuthenticated, IsInstructor]
    serializer_class = ExamAttemptSerializer

    def get_queryset(self):
        exam = get_manageable_exam_or_404(self.request.user, self.kwargs['exam_id'])
        return ExamAttempt.objects.filter(exam=exam).select_related('user__profile', 'exam').order_by('-started_at', '-pk')


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsInstructor])
@transaction.atomic
def publish_exam(request, exam_id):
    """Publish an exam."""
    exam = get_manageable_exam_or_404(request.user, exam_id, lock=True)
    try:
        ensure_question_bank_matches_course(exam)
        exam.total_marks = validated_exam_total(current_exam_questions(exam), exam.passing_marks)
    except ExamUnavailable as exc:
        return Response({'error': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
    exam.status = 'published'
    exam.save(update_fields=['status', 'total_marks', 'updated_at'])
    
    serializer = ExamSerializer(exam)
    return Response({
        'exam': serializer.data,
        'message': 'Exam published successfully'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsInstructor])
@transaction.atomic
def archive_exam(request, exam_id):
    """Archive an exam."""
    exam = get_manageable_exam_or_404(request.user, exam_id, lock=True)
    exam.status = 'archived'
    exam.save(update_fields=['status', 'updated_at'])
    
    serializer = ExamSerializer(exam)
    return Response({
        'exam': serializer.data,
        'message': 'Exam archived successfully'
    })
