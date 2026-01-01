from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from django.db.models import F

from .models import Course, Lesson, User
from .serializers import CourseCurriculumSerializer, LessonDataSerializer
from enrollments.models import Enrollment, LessonProgress

class LessonDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        user = request.user
        course = lesson.module.course

        # 1️⃣ Free lesson → always allowed
        if lesson.is_free:
            return Response(LessonDataSerializer(lesson).data)

        # 2️⃣ Not logged in → blocked
        if not user.is_authenticated:
            raise PermissionDenied("Login required to access this lesson.")

        # 3️⃣ Admin / Instructor → allowed
        if user.is_staff or course.instructor == user:
            return Response(LessonDataSerializer(lesson).data)

        # 4️⃣ Must be enrolled
        enrollment = Enrollment.objects.filter(
            user=user,
            course=course,
            status='active'
        ).first()

        if not enrollment:
            raise PermissionDenied("You must be enrolled in this course.")

        # 5️⃣ Locking logic (core security)
        completed_ids = set(
            LessonProgress.objects.filter(
                enrollment=enrollment,
                is_completed=True
            ).values_list('lesson_id', flat=True)
        )

        ordered_lessons = list(
            Lesson.objects.filter(
                module__course=course
            ).order_by('module__position', 'position')
        )

        unlocked_ids = set()
        for l in ordered_lessons:
            unlocked_ids.add(l.id)
            if l.id not in completed_ids:
                break

        if lesson.id not in unlocked_ids:
            raise PermissionDenied("Complete previous lessons to unlock this one.")

        # 6️⃣ Allowed
        return Response(LessonDataSerializer(lesson).data)
    

class CourseLessonListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        user = request.user

        enrollment = get_object_or_404(
            Enrollment,
            user=user,
            course_id=course_id,
            status='active'
        )

        lessons = Lesson.objects.filter(
            module__course=Course).order_by('module__position', 'position')

        completed_ids = set(
            LessonProgress.objects.filter(
                enrollment=enrollment,
                is_completed=True
            ).values_list('lesson_id', flat=True)
        )

        lesson_data = []
        previous_completed = True  

        for lesson in lessons:
            is_completed = lesson.id in completed_ids

            is_locked = (
                not lesson.is_free
                and not is_completed
                and not previous_completed
            )

            lesson_data.append({
                'id': lesson.id,
                'title': lesson.title,
                'position': lesson.position,
                'is_free': lesson.is_free,
                'is_completed': is_completed,
                'is_locked': is_locked,
            })

            previous_completed = is_completed or lesson.is_free

        return Response(lesson_data)
    

class CourseCurriculumView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        user = request.user
        course = get_object_or_404(Course, id=course_id)

        enrollment = get_object_or_404(
            Enrollment,
            user=user,
            course=course,
            status='active'
        )

        # 1️⃣ All lessons (ordered)
        lessons = Lesson.objects.filter(
            module__course=course
        ).order_by('module__position', 'position')

        lesson_ids = list(lessons.values_list('id', flat=True))

        # 2️⃣ Completed lessons
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

        # 4️⃣ Serializer context (IMPORTANT)
        serializer = CourseCurriculumSerializer(
            course,
            context={
                'completed_ids': completed_ids,
                'locked_ids': locked_ids,
            }
        )

        return Response(serializer.data)