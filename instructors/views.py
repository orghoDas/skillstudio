from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.db.models import Avg, Count, FloatField, Q
from django.db.models.functions import Cast, Coalesce, NullIf

from accounts.permissions import IsInstructor
from accounts.utils import public_instructor_name
from core.pagination import SummaryPageNumberPagination
from enrollments.models import Enrollment
from enrollments.constants import ACCESS_STATUSES
from enrollments.services import lesson_progress_percentage, with_enrollment_progress
from .serializers import (
    FeaturedInstructorSerializer,
    InstructorProfileSerializer,
    InstructorDashboardSerializer,
    InstructorRosterEntrySerializer,
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
    serializer_class = InstructorDashboardSerializer

    def get(self, request):
        instructor = request.user

        courses = list(get_course_overview(instructor))
        students = get_student_engagement(instructor)
        earnings, payouts = get_revenue_summary(instructor)

        enrollment_counts = Enrollment.objects.filter(course__instructor=instructor).aggregate(
            total_students=Count('user', filter=Q(status__in=ACCESS_STATUSES), distinct=True),
            active_enrollments=Count('pk', filter=Q(status='active')),
        )

        return Response({
            "total_courses": len(courses),
            **enrollment_counts,
            "total_revenue": float(earnings["total_earned"]),
            "courses": [
                {
                    "id": c.id,
                    "title": c.title,
                    "status": c.status,
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
            "revenue": earnings,
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
    serializer_class = InstructorProfileSerializer
    
    def get(self, request):
        profile = get_or_create_instructor_profile(request.user)
        serializer = InstructorProfileSerializer(profile)
        return Response(serializer.data)
    
    def put(self, request):
        changes = InstructorProfileSerializer(data=request.data, partial=True)
        changes.is_valid(raise_exception=True)
        profile = update_instructor_profile(request.user, **changes.validated_data)
        serializer = InstructorProfileSerializer(profile)
        return Response(serializer.data)

    patch = put


class InstructorRosterPagination(SummaryPageNumberPagination):
    summary_properties = {'active_count': {'type': 'integer'}, 'average_progress': {'type': 'number'}}


class InstructorStudentsView(ListAPIView):
    """List all students enrolled in instructor's courses."""
    permission_classes = [IsAuthenticated, IsInstructor]
    serializer_class = InstructorRosterEntrySerializer
    pagination_class = InstructorRosterPagination
    
    def get_queryset(self):
        queryset = Enrollment.objects.filter(course__instructor=self.request.user).select_related('user', 'course')
        return with_enrollment_progress(queryset.order_by('-enrolled_at', '-pk'))

    def list(self, request, *args, **kwargs):
        enrollments = self.get_queryset()
        page = self.paginate_queryset(enrollments)
        students = [
            {
                'id': row.user_id,
                'email': row.user.email,
                'course': {'id': row.course_id, 'title': row.course.title},
                'enrolled_at': row.enrolled_at,
                'progress': lesson_progress_percentage(row.required_completed_count, row.required_count),
                'status': row.status,
                'last_accessed': row.enrolled_at,
            }
            for row in page
        ]
        response = self.get_paginated_response(students)
        ratio = Cast('required_completed_count', FloatField()) * 100 / NullIf(Cast('required_count', FloatField()), 0.0)
        summary = enrollments.aggregate(
            active_count=Count('pk', filter=Q(status='active')),
            average_progress=Avg(Coalesce(ratio, 0.0), default=0.0),
        )
        summary['average_progress'] = round(summary['average_progress'], 2)
        response.data['summary'] = summary
        return response


class FeaturedInstructorsView(ListAPIView):
    """Public: instructors with published courses, most students first (API-01).

    Returns display data only (name, headline, counts) — never email addresses.
    """
    permission_classes = [AllowAny]
    serializer_class = FeaturedInstructorSerializer
    LIMIT = 8

    def get_queryset(self):
        from django.contrib.auth import get_user_model

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
        return [_featured_instructor_data(user) for user in instructors]


def _featured_instructor_data(user):
    instructor_profile = getattr(user, 'instructor_profile', None)
    return {
        'id': user.id,
        'name': public_instructor_name(user),
        'headline': (instructor_profile.headline if instructor_profile else '') or '',
        'courses_count': user.courses_count,
        'students_count': user.students_count,
    }
