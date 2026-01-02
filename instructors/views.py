from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsInstructor
from instructors.services import get_course_overview, get_student_engagement, get_revenue_summary, get_lesson_dropoff
from courses.models import Course
from django.shortcuts import get_object_or_404



class InstructorDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request):
        instructor = request.user

        courses = get_course_overview(instructor)
        students = get_student_engagement(instructor)
        earnings, payouts = get_revenue_summary(instructor)

        return Response({
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
                "total_earned": earnings["total_earned"],
                "platform_fee": earnings["platform_fee"],
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


class InstructorCourseDetailView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request, course_id):
        course = get_object_or_404(
            Course,
            id=course_id,
            instructor=request.user
        )

        dropoff = get_lesson_dropoff(course)

        return Response({
            "course": course.title,
            "dropoff": list(dropoff)
        })