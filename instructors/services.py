from django.db.models import Count, Sum, Max, Q,F, Avg, ExpressionWrapper
from django.forms import DurationField
from courses.models import Course, Lesson
from enrollments.models import Enrollment
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import TruncDate

from payments.models import Payment, Payout


def get_instructor_course_metrics(instructor):
    courses = (
        Course.objects
        .filter(instructor=instructor)
        .annotate(
            total_students=Count(
                'enrollments',
                filter=Q(enrollments__status='active')
            ),
            completed_students=Count(
                'enrollments',
                filter=Q(enrollments__is_completed=True)
            ),
            last_enrollment_at=Max('enrollments__enrolled_at'),
            total_revenue=Sum(
                'enrollments__amount_paid',
                filter=Q(enrollments__status='active')
            )
        )
        .order_by('-created_at')
    )

    dashboard = []

    for course in courses:
        completion_rate = (
            round(
                (course.completed_students / course.total_students) * 100,
                2
            )
            if course.total_students > 0 else 0
        )

        dashboard.append({
            "course_id": course.id,
            "course_title": course.title,
            "total_students": course.total_students,
            "completed_students": course.completed_students,
            "completion_rate": completion_rate,
            "total_revenue": course.total_revenue or 0,
            "last_enrollment_at": course.last_enrollment_at,
        })

    return dashboard


def get_instructor_enrollment_trends(instructor, days=30):
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)

    qs = (
        Enrollment.objects
        .filter(
            course__instructor=instructor,
            enrolled_at__date__gte=start_date,
            enrolled_at__date__lte=end_date
        )
        .annotate(date=TruncDate('enrolled_at'))
        .values('date')
        .annotate(
            enrollments=Count('id'),
            completions=Count(
                'id',
                filter=Q(is_completed=True)
            )
        )
        .order_by('date')
    )

    return list(qs)


def get_course_overview_analytics(course):
    enrollments = Enrollment.objects.filter(course=course)

    total = enrollments.count()
    active = enrollments.filter(status='active').count()
    completed = enrollments.filter(is_completed=True)

    completion_rate = (
        round((completed.count() / total) * 100, 2)
        if total > 0 else 0
    )

    avg_completion_time = completed.annotate(
        duration=ExpressionWrapper(
            F('completed_at') - F('enrolled_at'),
            output_field=DurationField()
        )
    ).aggregate(avg=Avg('duration'))['avg']

    avg_completion_days = (
        round(avg_completion_time.total_seconds() / 86400, 2)
        if avg_completion_time else None
    )

    return {
        "total_enrollments": total,
        "active_enrollments": active,
        "completed_enrollments": completed.count(),
        "completion_rate": completion_rate,
        "avg_completion_time_days": avg_completion_days,
    }


def get_course_lesson_analytics(course):
    lessons = (
        Lesson.objects
        .filter(module__course=course, is_free=False)
        .annotate(
            started_count=Count('lesson_progress'),
            completed_count=Count(
                'lesson_progress',
                filter=F('lesson_progress__is_completed')
            ),
            avg_watch_ratio=Avg(
                F('lesson_progress__watch_time') / F('duration_seconds')
            )
        )
        .values(
            'id',
            'title',
            'started_count',
            'completed_count',
            'avg_watch_ratio'
        )
        .order_by('module__position', 'position')
    )

    return list(lessons)

def get_lesson_dropoff_analytics(course):
    lessons = (
        Lesson.objects
        .filter(module__course=course, is_free=False)
        .annotate(
            started_count=Count('lesson_progress'),
            completed_count=Count(
                'lesson_progress',
                filter=F('lesson_progress__is_completed')
            ),
            avg_watch_time=Avg('lesson_progress__watch_time')
        )
        .values(
            'id',
            'title',
            'duration_seconds',
            'started_count',
            'completed_count',
            'avg_watch_time'
        )
        .order_by('module__position', 'position')
    )

    results = []

    for lesson in lessons:
        started = lesson['started_count']
        completed = lesson['completed_count']
        duration = lesson['duration_seconds'] or 1
        avg_watch = lesson['avg_watch_time'] or 0

        dropoff_rate = (
            round(((started - completed) / started) * 100, 2)
            if started > 0 else 0
        )

        avg_watch_ratio = round(avg_watch / duration, 2)

        results.append({
            "lesson_id": lesson['id'],
            "lesson_title": lesson['title'],
            "started": started,
            "completed": completed,
            "dropoff_rate": dropoff_rate,
            "avg_watch_ratio": avg_watch_ratio,
            "is_bottleneck": dropoff_rate >= 40 or avg_watch_ratio < 0.5
        })

    return results


def get_instructor_revenue_summary(instructor):
    gross = Payment.objects.filter(
        instructor=instructor,
        status="completed"
    ).aggregate(total=Sum("amount"))["total"] or 0

    net = Payment.objects.filter(
        instructor=instructor,
        status="completed"
    ).aggregate(total=Sum("instructor_earnings"))["total"] or 0

    paid_out = Payout.objects.filter(
        instructor=instructor,
        status="completed"
    ).aggregate(total=Sum("amount"))["total"] or 0

    return {
        "gross_revenue": gross,
        "net_earnings": net,
        "paid_out": paid_out,
        "pending_payout": net - paid_out
    }
