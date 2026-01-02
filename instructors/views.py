from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from courses.models import Course
from accounts.permissions import IsInstructor
from enrollments.models import Enrollment, LessonProgress
from instructors.services import get_course_lesson_analytics, get_course_overview_analytics, get_instructor_course_metrics, get_instructor_enrollment_trends, get_instructor_revenue_summary, get_lesson_dropoff_analytics
from payments.models import Payment, Payout
from payments.services import get_unpaid_payments_for_instructor
from django.db.models import Sum


class InstructorDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request):
        instructor = request.user

        # 1️⃣ Courses
        courses = Course.objects.filter(instructor=instructor)

        # 2️⃣ Enrollment metrics
        enrollments = Enrollment.objects.filter(course__in=courses)

        total_students = enrollments.values("user").distinct().count()
        total_enrollments = enrollments.count()

        # 3️⃣ Lesson activity
        lesson_activity = LessonProgress.objects.filter(
            enrollment__course__in=courses
        ).count()

        # 4️⃣ Revenue metrics
        total_earned = Payment.objects.filter(
            instructor=instructor,
            status="completed"
        ).aggregate(
            total=Sum("instructor_earnings")
        )["total"] or 0

        unpaid_payments = get_unpaid_payments_for_instructor(instructor)

        pending_payout = unpaid_payments.aggregate(
            total=Sum("instructor_earnings")
        )["total"] or 0

        # 5️⃣ Recent payouts
        payouts = Payout.objects.filter(
            instructor=instructor
        ).order_by("-created_at")[:5]

        return Response({
            "courses_count": courses.count(),
            "total_students": total_students,
            "total_enrollments": total_enrollments,
            "lesson_activity_count": lesson_activity,

            "revenue": {
                "total_earned": total_earned,
                "pending_payout": pending_payout,
            },

            "recent_payouts": [
                {
                    "id": payout.id,
                    "amount": payout.amount,
                    "status": payout.status,
                    "created_at": payout.created_at,
                }
                for payout in payouts
            ]
        })

    

class InstructorEnrollmentTrendsView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        data = get_instructor_enrollment_trends(request.user, days=days)
        return Response(data)
    

class InstructorCourseAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request, course_id):
        course = get_object_or_404(
            Course,
            id=course_id,
            instructor=request.user
        )

        overview = get_course_overview_analytics(course)
        lessons = get_course_lesson_analytics(course)

        return Response({
            "course_id": course.id,
            "course_title": course.title,
            "overview": overview,
            "lessons": lessons
        })
    

class InstructorCourseDropoffView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request, course_id):
        course = get_object_or_404(
            Course,
            id=course_id,
            instructor=request.user
        )

        dropoffs = get_lesson_dropoff_analytics(course)

        return Response({
            "course_id": course.id,
            "course_title": course.title,
            "dropoff_analysis": dropoffs
        })


class InstructorRevenueView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request):
        instructor = request.user

        unpaid = get_unpaid_payments_for_instructor(instructor)

        total_earned = Payment.objects.filter(
            instructor=instructor,
            status="completed"
        ).aggregate(total=Sum("instructor_earnings"))["total"] or 0

        pending_payout = unpaid.aggregate(
            total=Sum("instructor_earnings")
        )["total"] or 0

        return Response({
            "total_earned": total_earned,
            "pending_payout": pending_payout,
            "completed_payments": unpaid.count()
        })


