from django.db import models
from django.db.models import Count, Avg, Max, Sum
from courses.models import Course
from enrollments.models import Enrollment, LessonProgress
from payments.models import Payment, Payout
from events.models import Event


def get_course_overview(instructor):
    return (
        Course.objects
        .filter(instructor=instructor)
        .annotate(
            total_enrollments=Count("enrollments"),
            avg_rating=Avg("reviews__rating"),
        )
    )


def get_student_engagement(instructor):
    return (
        Enrollment.objects
        .filter(course__instructor=instructor)
        .annotate(
            completed_lessons=Count(
                "lesson_progress",
                filter=models.Q(lesson_progress__is_completed=True)
            ),
            last_activity=Max("lesson_progress__updated_at")
        )
        .select_related("course", "user")
    )


def get_lesson_dropoff(course):
    return (
        LessonProgress.objects
        .filter(lesson__module__course=course)
        .values("lesson__id", "lesson__title")
        .annotate(students=Count("user"))
        .order_by("students")
    )


def get_revenue_summary(instructor):
    earnings = (
        Payment.objects
        .filter(instructor=instructor, status="completed")
        .aggregate(
            total_earned=Sum("instructor_earnings"),
            platform_fee=Sum("platform_fee"),
        )
    )

    payouts = (
        Payout.objects
        .filter(instructor=instructor)
        .order_by("-created_at")
    )

    return earnings, payouts


def get_instructor_events(instructor):
    return Event.objects.filter(host=instructor)