from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from django.db.models import F

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
        if lesson.position > enrollment.current_position:
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