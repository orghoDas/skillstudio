from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError, PermissionDenied as DjangoPermissionDenied

from accounts.mixins import InstructorOnlyMixin
from accounts.permissions import IsInstructor
from courses.models import Course
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