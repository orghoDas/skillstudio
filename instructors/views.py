from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q

from accounts.permissions import IsInstructor
from accounts.utils import public_instructor_name
from courses.models import Course
from enrollments.models import Enrollment
from django.shortcuts import get_object_or_404
from .models import InstructorProfile
from .serializers import (
    InstructorProfileSerializer,
    InstructorDashboardSerializer,
)
from .services import (
    get_course_overview,
    get_student_engagement,
    get_revenue_summary,
    get_or_create_instructor_profile,
    update_instructor_profile,
)


class InstructorDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request):
        instructor = request.user

        courses = get_course_overview(instructor)
        students = get_student_engagement(instructor)
        earnings, payouts = get_revenue_summary(instructor)

        # Get total counts for stats
        total_courses = Course.objects.filter(instructor=instructor).count()
        total_students = Enrollment.objects.filter(course__instructor=instructor).values('user').distinct().count()
        active_enrollments = Enrollment.objects.filter(course__instructor=instructor, status='active').count()
        
        # Safely get total revenue
        total_earned = earnings.get("total_earned") or 0
        total_revenue = float(total_earned) if total_earned else 0.0

        return Response({
            "total_courses": total_courses,
            "total_students": total_students,
            "active_enrollments": active_enrollments,
            "total_revenue": total_revenue,
            "courses": [
                {
                    "id": c.id,
                    "title": c.title,
                    "enrollments": c.total_enrollments,
                }
                for c in courses
            ],
            "students": [
                {
                    "student_id": e.user.id,
                    "student_email": e.user.email,
                    "course": e.course.title,
                    "completed_lessons": e.completed_lessons,
                    "last_activity": e.last_activity,
                }
                for e in students
            ],
            "revenue": {
                "total_earned": earnings.get("total_earned") or 0,
                "platform_fee": earnings.get("platform_fee") or 0,
                "available": earnings.get("available") or 0,
                "pending_payouts": earnings.get("pending_payouts") or 0,
                "paid_out": earnings.get("paid_out") or 0,
            },
            "payouts": [
                {
                    "id": p.id,
                    "amount": p.amount,
                    "status": p.status,
                    "created_at": p.created_at,
                }
                for p in payouts
            ]
        })


class InstructorProfileView(APIView):
    """Get or update instructor profile."""
    permission_classes = [IsAuthenticated, IsInstructor]
    
    def get(self, request):
        profile = get_or_create_instructor_profile(request.user)
        serializer = InstructorProfileSerializer(profile)
        return Response(serializer.data)
    
    def put(self, request):
        profile = update_instructor_profile(request.user, **request.data)
        serializer = InstructorProfileSerializer(profile)
        return Response(serializer.data)

    patch = put


class InstructorStudentsView(APIView):
    """List all students enrolled in instructor's courses."""
    permission_classes = [IsAuthenticated, IsInstructor]
    
    def get(self, request):
        instructor = request.user
        
        # Get all enrollments for instructor's courses
        enrollments = Enrollment.objects.filter(
            course__instructor=instructor
        ).select_related('user', 'course').prefetch_related('lesson_progress').order_by('-enrolled_at')
        
        # Group students by course
        students_data = []
        seen_students = set()
        
        for enrollment in enrollments:
            student_key = (enrollment.user.id, enrollment.course.id)
            if student_key not in seen_students:
                seen_students.add(student_key)
                
                # Calculate progress percentage
                from courses.models import Lesson
                total_lessons = Lesson.objects.filter(
                    module__course=enrollment.course,
                    is_free=False
                ).count()
                
                if total_lessons == 0:
                    progress_percentage = 0
                else:
                    completed_lessons = enrollment.lesson_progress.filter(is_completed=True).count()
                    progress_percentage = round((completed_lessons / total_lessons) * 100, 2)
                
                students_data.append({
                    "id": enrollment.user.id,
                    "email": enrollment.user.email,
                    "course": {
                        "id": enrollment.course.id,
                        "title": enrollment.course.title,
                    },
                    "enrolled_at": enrollment.enrolled_at,
                    "progress": progress_percentage,
                    "status": enrollment.status,
                    "last_accessed": enrollment.updated_at if hasattr(enrollment, 'updated_at') else enrollment.enrolled_at,
                })
        
        return Response({
            "count": len(students_data),
            "students": students_data
        })


class FeaturedInstructorsView(APIView):
    """Public: instructors with published courses, most students first (API-01).

    Returns display data only (name, headline, counts) — never email addresses.
    """
    permission_classes = [AllowAny]
    LIMIT = 8

    def get(self, request):
        from django.contrib.auth import get_user_model
        from enrollments.constants import ACCESS_STATUSES

        User = get_user_model()
        published = Q(courses__status='published')
        instructors = (
            User.objects.filter(role=User.Role.INSTRUCTOR, is_active=True)
            .annotate(
                courses_count=Count('courses', filter=published, distinct=True),
                students_count=Count(
                    'courses__enrollments__user',
                    filter=published & Q(courses__enrollments__status__in=ACCESS_STATUSES),
                    distinct=True,
                ),
            )
            .filter(courses_count__gt=0)
            .select_related('profile', 'instructor_profile')
            .order_by('-students_count', '-courses_count', 'id')[: self.LIMIT]
        )
        return Response([_featured_instructor_data(user) for user in instructors])


def _featured_instructor_data(user):
    instructor_profile = getattr(user, 'instructor_profile', None)
    return {
        'id': user.id,
        'name': public_instructor_name(user),
        'headline': (instructor_profile.headline if instructor_profile else '') or '',
        'courses_count': user.courses_count,
        'students_count': user.students_count,
    }
