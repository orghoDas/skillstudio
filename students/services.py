from itertools import chain
from django.db.models import Value, CharField, Count, Q, Max
from accounts import models
from certificates.models import Certificate
from courses.models import Lesson
from enrollments.models import Enrollment, LessonProgress
from enrollments.services import get_resume_lesson
from .constants import (
    ACHIEVEMENTS,
    LESSON_STARTED,
    LESSON_COMPLETED,
    COURSE_COMPLETED,
    CERTIFICATE_ISSUED,
)

from datetime import timedelta
from django.utils import timezone
from django.db.models.functions import TruncDate

def get_student_activity_feed(user, limit=20):
    activities = []

    # 1️⃣ Lesson started / completed
    lesson_progress = (
        LessonProgress.objects
        .filter(user=user)
        .select_related('lesson', 'lesson__module__course')
        .order_by('-updated_at')[:limit]
    )

    for lp in lesson_progress:
        if lp.is_completed:
            activities.append({
                "type": LESSON_COMPLETED,
                "course_id": lp.lesson.module.course.id,
                "course_title": lp.lesson.module.course.title,
                "lesson_id": lp.lesson.id,
                "lesson_title": lp.lesson.title,
                "timestamp": lp.completed_at,
            })
        else:
            activities.append({
                "type": LESSON_STARTED,
                "course_id": lp.lesson.module.course.id,
                "course_title": lp.lesson.module.course.title,
                "lesson_id": lp.lesson.id,
                "lesson_title": lp.lesson.title,
                "timestamp": lp.started_at,
            })

    # 2️⃣ Course completed
    completed_courses = (
        Enrollment.objects
        .filter(user=user, is_completed=True)
        .select_related('course')
        .order_by('-completed_at')
    )

    for enrollment in completed_courses:
        activities.append({
            "type": COURSE_COMPLETED,
            "course_id": enrollment.course.id,
            "course_title": enrollment.course.title,
            "timestamp": enrollment.completed_at,
        })

    # 3️⃣ Certificate issued
    certificates = (
        Certificate.objects
        .filter(user=user)
        .select_related('course')
        .order_by('-issued_at')
    )

    for cert in certificates:
        activities.append({
            "type": CERTIFICATE_ISSUED,
            "course_id": cert.course.id,
            "course_title": cert.course.title,
            "timestamp": cert.issued_at,
        })

    # 4️⃣ Sort & trim
    activities.sort(key=lambda x: x["timestamp"], reverse=True)

    return activities[:limit]


def get_student_dashboard_data(user):
    enrollments = (
        Enrollment.objects
        .filter(user=user)
        .select_related('course')
        .annotate(
            completed_lessons=Count(
                'lesson_progress',
                filter=Q(lesson_progress__is_completed=True)
            ),
            last_activity=Max('lesson_progress__updated_at')
        )
        .order_by('-enrolled_at')
    )

    # Pre-calc total lessons per course
    lesson_counts = (
        Lesson.objects
        .filter(is_free=False)
        .values('module__course')
        .annotate(total=Count('id'))
    )

    lesson_count_map = {
        row['module__course']: row['total']
        for row in lesson_counts
    }

    dashboard = []

    for enrollment in enrollments:
        total_lessons = lesson_count_map.get(enrollment.course_id, 0)

        progress_percentage = (
            round((enrollment.completed_lessons / total_lessons) * 100, 2)
            if total_lessons > 0 else 0
        )

        resume_lesson = get_resume_lesson(enrollment)

        resume_context = None
        if resume_lesson:
            resume_context = {
                "lesson_id": resume_lesson.id,
                "lesson_title": resume_lesson.title,
                "module_title": resume_lesson.module.title,
            }

        if enrollment.is_completed:
            primary_action = "view_certificate"
            action_target = enrollment.course_id

        elif enrollment.completed_lessons == 0:
            primary_action = "start_course"
            action_target = enrollment.course_id

        else:
            primary_action = "resume_lesson"
            action_target = resume_lesson.id if resume_lesson else None

        dashboard.append({
            "course_id": enrollment.course.id,
            "course_title": enrollment.course.title,
            "status": enrollment.status,
            "progress_percentage": progress_percentage,
            "completed_lessons": enrollment.completed_lessons,
            "total_lessons": total_lessons,
            "has_certificate": enrollment.is_completed,
            "resume_lesson_id": resume_lesson.id if resume_lesson else None,
            "last_activity": enrollment.last_activity,
            "resume_context": resume_context,

            # ✅ STEP 7 additions
            "primary_action": primary_action,
            "action_target": action_target,
        })

    return dashboard

def get_learning_streak(user):
    """
    Returns:
    {
        current_streak: int,
        longest_streak: int
    }
    """
    today = timezone.now().date()

    active_days = (
        LessonProgress.objects
        .filter(user=user)
        .annotate(day=TruncDate('updated_at'))
        .values_list('day', flat=True)
        .distinct()
        .order_by('-day')
    )

    if not active_days:
        return {"current_streak": 0, "longest_streak": 0}

    # 🔥 Current streak
    current_streak = 0
    expected_day = today

    for day in active_days:
        if day == expected_day:
            current_streak += 1
            expected_day -= timedelta(days=1)
        else:
            break

    # 🏆 Longest streak
    longest_streak = 1
    temp_streak = 1

    sorted_days = sorted(active_days)

    for i in range(1, len(sorted_days)):
        if sorted_days[i] == sorted_days[i - 1] + timedelta(days=1):
            temp_streak += 1
            longest_streak = max(longest_streak, temp_streak)
        else:
            temp_streak = 1

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak
    }

def get_student_achievements(user, streak_data):
    achievements = []

    completed_lessons = LessonProgress.objects.filter(
        user=user,
        is_completed=True
    ).exists()

    completed_courses = Enrollment.objects.filter(
        user=user,
        is_completed=True
    ).exists()

    if completed_lessons:
        achievements.append("first_lesson")

    if completed_courses:
        achievements.append("first_course")

    if streak_data["current_streak"] >= 3:
        achievements.append("streak_3")

    if streak_data["current_streak"] >= 7:
        achievements.append("streak_7")

    return [
        {
            "key": key,
            "title": ACHIEVEMENTS[key]["title"],
            "description": ACHIEVEMENTS[key]["description"],
        }
        for key in achievements
    ]


def get_weekly_learning_progress(user):
    """
    Returns:
    {
        active_days: int,
        total_watch_time: int
    }
    """
    start_of_week = timezone.now().date() - timedelta(days=timezone.now().weekday())

    weekly_progress = LessonProgress.objects.filter(
        user=user,
        updated_at__date__gte=start_of_week
    )

    active_days = (
        weekly_progress
        .annotate(day=TruncDate('updated_at'))
        .values('day')
        .distinct()
        .count()
    )

    total_watch_time = weekly_progress.aggregate(
        total=models.Sum('watch_time')
    )['total'] or 0

    return {
        "active_days": active_days,
        "total_watch_time": total_watch_time
    }
