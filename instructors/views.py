from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError, PermissionDenied as DjangoPermissionDenied
from django.db.models import Count, Q

from accounts.mixins import InstructorOnlyMixin
from accounts.permissions import IsInstructor
from courses.models import Course
from enrollments.models import Enrollment
from django.shortcuts import get_object_or_404
from .models import InstructorProfile, InstructorPayout
from .serializers import (
    InstructorProfileSerializer,
    InstructorPayoutSerializer,
    InstructorPayoutListSerializer,
    InstructorDashboardSerializer,
)
from .services import (
    get_course_overview,
    get_student_engagement,
    get_revenue_summary,
    get_lesson_dropoff,
    get_or_create_instructor_profile,
    update_instructor_profile,
    request_payout,
)


class InstructorDashboardView(APIView, InstructorOnlyMixin):
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request):
        instructor = request.user

        try:
            courses = get_course_overview(instructor)
            students = get_student_engagement(instructor)
            earnings, payouts = get_revenue_summary(instructor)
        except Exception as e:
            # Log the error and return default values
            import traceback
            print(f"Error in instructor dashboard: {str(e)}")
            traceback.print_exc()
            
            # Return minimal data
            return Response({
                "total_courses": Course.objects.filter(instructor=instructor).count(),
                "total_students": Enrollment.objects.filter(course__instructor=instructor).values('user').distinct().count(),
                "active_enrollments": Enrollment.objects.filter(course__instructor=instructor, status='active').count(),
                "total_revenue": 0,
                "courses": [],
                "students": [],
                "revenue": {"total_earned": 0, "platform_fee": 0},
                "payouts": []
            })

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
                    "avg_rating": c.avg_rating,
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
        try:
            profile = update_instructor_profile(request.user, **request.data)
            serializer = InstructorProfileSerializer(profile)
            return Response(serializer.data)
        except DjangoValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def patch(self, request):
        try:
            profile = update_instructor_profile(request.user, **request.data)
            serializer = InstructorProfileSerializer(profile)
            return Response(serializer.data)
        except DjangoValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class InstructorPayoutListView(ListAPIView):
    """List all payouts for instructor."""
    permission_classes = [IsAuthenticated, IsInstructor]
    serializer_class = InstructorPayoutListSerializer
    
    def get_queryset(self):
        return InstructorPayout.objects.filter(
            instructor=self.request.user
        ).order_by('-created_at')


class InstructorPayoutRequestView(APIView):
    """Request a new payout."""
    permission_classes = [IsAuthenticated, IsInstructor]
    
    def post(self, request):
        try:
            payout = request_payout(
                instructor=request.user,
                amount=request.data.get('amount'),
                payment_method=request.data.get('payment_method', 'bank_transfer'),
                payment_details=request.data.get('payment_details')
            )
            serializer = InstructorPayoutSerializer(payout)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except DjangoValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


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
