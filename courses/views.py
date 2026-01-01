from django.utils import timezone
from django.forms import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from django.db.models import F

from accounts.permissions import IsAdmin
from courses.permissions import CanEditCourse
from courses.services import validate_course_for_submission
from enrollments.services import get_next_lesson
from enrollments.utils import require_active_enrollment

from .models import Course, Lesson, User
from .serializers import CourseCurriculumSerializer, LessonDataSerializer
from enrollments.models import Enrollment, LessonProgress

class LessonDetailView(APIView):

    def get(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        course = lesson.module.course
        user = request.user

        Lesson.objects.filter(id=lesson.id).update(view_count=F('view_count') + 1)

        # Free lesson → public
        if lesson.is_free:
            return Response(LessonDataSerializer(lesson).data)

        # Protected lesson
        if not user.is_authenticated:
            raise PermissionDenied("Login required.")

        enrollment = require_active_enrollment(user, course)

        # 🔒 Lock check (progression)
        previous_lessons = Lesson.objects.filter(
            module__course=course,
            module__position__lt=lesson.module.position
        ) | Lesson.objects.filter(
            module=lesson.module,
            position__lt=lesson.position
        )

        # Check if all previous lessons are completed
        total_previous = previous_lessons.count()
        if total_previous > 0:
            completed_previous = LessonProgress.objects.filter(
                enrollment=enrollment,
                lesson__in=previous_lessons,
                is_completed=True
            ).count()
            is_unlocked = completed_previous == total_previous
        else:
            is_unlocked = True  # First lesson is always unlocked

        if not lesson.is_free and not is_unlocked:
            raise PermissionDenied("Lesson is locked.")

        return Response(LessonDataSerializer(lesson).data)    

class CourseCurriculumView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, course_id):
        user = request.user
        course = get_object_or_404(Course, id=course_id)

        enrollment = None

        # 🔐 ACCESS ENFORCEMENT (Step 8)
        if not course.is_free:
            if not user.is_authenticated:
                raise PermissionDenied("Login required.")

            enrollment = Enrollment.objects.filter(
                user=user,
                course=course,
                status='active'
            ).first()

            if not enrollment and course.instructor != user and not user.is_staff:
                raise PermissionDenied("Active enrollment required.")

        # 1️⃣ All lessons (ordered)
        lessons = Lesson.objects.filter(
            module__course=course
        ).order_by('module__position', 'position')

        lesson_ids = list(lessons.values_list('id', flat=True))

        # 2️⃣ Completed lessons
        completed_ids = set()

        if enrollment:
            completed_ids = set(
                LessonProgress.objects.filter(
                    enrollment=enrollment,
                    is_completed=True
                ).values_list('lesson_id', flat=True)
            )

        # 3️⃣ Locked lesson computation (ONCE)
        locked_ids = set()
        unlock_next = True

        for lesson in lessons:
            if lesson.is_free:
                continue

            if unlock_next:
                unlock_next = lesson.id in completed_ids
            else:
                locked_ids.add(lesson.id)

        # 4️⃣ Serializer context
        serializer = CourseCurriculumSerializer(
            course,
            context={
                'completed_ids': completed_ids,
                'locked_ids': locked_ids,
            }
        )

        return Response(serializer.data)
    

class SubmitCourseForReviewView(APIView):
    permission_classes = [IsAuthenticated, CanEditCourse]

    def post(self, request, course_id):
        user = request.user

        course = Course.objects.filter(
            id=course_id,
            instructor=user
        ).first()

        if not course:
            raise PermissionDenied("You do not own this course.")

        if course.status != 'draft':
            raise ValidationError("Only draft courses can be submitted.")

        validate_course_for_submission(course)

        course.status = 'under_review'
        course.submitted_for_review_at = timezone.now()
        course.save(update_fields=['status', 'submitted_for_review_at'])

        return Response({
            "message": "Course submitted for review.",
            "status": course.status
        })
    

class PublishCourseView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)

        if course.status != 'under_review':
            raise ValidationError("Course is not under review.")

        course.status = 'published'
        course.reviewed_at = timezone.now()
        course.reviewed_by = request.user
        course.rejection_reason = ""

        course.save(update_fields=[
            'status',
            'reviewed_at',
            'reviewed_by',
            'rejection_reason'
        ])

        return Response({
            "message": "Course published successfully."
        })
    

class RejectCourseView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)
        reason = request.data.get('reason', '').strip()

        if course.status != 'under_review':
            raise ValidationError("Course is not under review.")

        if not reason:
            raise ValidationError("Rejection reason is required.")

        course.status = 'draft'
        course.rejection_reason = reason
        course.reviewed_at = timezone.now()
        course.reviewed_by = request.user

        course.save(update_fields=[
            'status',
            'rejection_reason',
            'reviewed_at',
            'reviewed_by'
        ])

        return Response({
            "message": "Course rejected and returned to draft."
        })


class ResumeLearningView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        user = request.user
        enrollment = require_active_enrollment(user, course_id)
        lesson = get_next_lesson(enrollment)

        if not lesson:
            return Response({
                'completed': True,
                'message': "You have completed all lessons in this course."
            })
        
        return Response({
            'lesson_id': lesson.id,
            'lesson_title': lesson.title,
            'module_title': lesson.module.title,
        })