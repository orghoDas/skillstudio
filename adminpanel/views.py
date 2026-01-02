from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdmin
from adminpanel.services import approve_course, platform_stats, suspend_user
from adminpanel.services import get_all_users
from adminpanel.services import get_pending_courses
from adminpanel.services import get_all_payments


class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        return Response({
            "stats": platform_stats(),
            "users": [
                {
                    "id": u.id,
                    "email": u.email,
                    "role": u.role,
                    "active": u.is_active,
                }
                for u in get_all_users()
            ],
            "pending_courses": [
                {
                    "id": c.id,
                    "title": c.title,
                    "instructor": c.instructor.email,
                }
                for c in get_pending_courses()
            ],
            "payments": [
                {
                    "id": p.id,
                    "user": p.user.email,
                    "amount": p.amount,
                    "status": p.status,
                }
                for p in get_all_payments()
            ],
        })


class ApproveCourseView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, course_id):
        approve_course(course_id)
        return Response({"status": "approved"})


class SuspendUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, user_id):
        suspend_user(user_id)
        return Response({"status": "suspended"})
