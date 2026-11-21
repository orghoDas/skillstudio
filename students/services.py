from itertools import chain
from datetime import timedelta
from django.db import transaction
from django.db.models import Value, CharField, Count, Exists, Max, OuterRef, Q, Sum
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth import get_user_model

from certificates.models import Certificate
from courses.models import Lesson, Course
from courses.policies import can_view_course_catalog, visible_catalog_courses
from enrollments.models import Enrollment, LessonProgress
from enrollments.constants import ACCESS_STATUSES
from enrollments.services import get_lesson_completion_stats, get_required_lessons, get_resume_lesson
from .models import LearningActivity, StudentProfile, StudentNote, StudentBookmark, Wallet, WalletTransaction
from .constants import (
    ACHIEVEMENTS,
    LESSON_STARTED,
    LESSON_COMPLETED,
    COURSE_COMPLETED,
    CERTIFICATE_ISSUED,
)

User = get_user_model()

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
                "timestamp": lp.completed_at or lp.updated_at,
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
        .filter(user=user, is_completed=True, completed_at__isnull=False)
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
            has_certificate=Exists(Certificate.objects.filter(
                course_id=OuterRef('course_id'), user=user, revoked_at__isnull=True,
            ).exclude(enrollment__status='canceled')),
            last_activity=Max('lesson_progress__updated_at'),
        )
        .order_by('-enrolled_at')
    )
    dashboard = []
    for enrollment in enrollments:
        required_lessons = list(get_required_lessons(enrollment.course).select_related('module'))
        stats = get_lesson_completion_stats(enrollment, required_lessons=required_lessons)
        completed_ids = set(stats['completed_lesson_ids'])
        resume_lesson = get_resume_lesson(
            enrollment, lessons=required_lessons, completed_ids=completed_ids,
        )

        resume_context = None
        if resume_lesson and enrollment.status in ACCESS_STATUSES and not enrollment.is_completed:
            resume_context = {
                "lesson_id": resume_lesson.id,
                "lesson_title": resume_lesson.title,
                "module_title": resume_lesson.module.title,
            }

        action_target = enrollment.course_id
        if enrollment.has_certificate:
            primary_action = "view_certificate"
        elif enrollment.is_completed or enrollment.status not in ACCESS_STATUSES or not resume_lesson:
            primary_action = "view_course"
        elif not stats['completed_lessons']:
            primary_action = "start_course"
        else:
            primary_action = "resume_lesson"
            action_target = resume_lesson.id

        dashboard.append({
            "course_id": enrollment.course_id,
            "course_title": enrollment.course.title,
            "status": enrollment.status,
            "is_completed": enrollment.is_completed,
            "progress_percentage": stats['progress_percentage'],
            "completed_lessons": stats['completed_lessons'],
            "total_lessons": stats['total_lessons'],
            "has_certificate": enrollment.has_certificate,
            "resume_lesson_id": resume_context["lesson_id"] if resume_context else None,
            "last_activity": enrollment.last_activity,
            "resume_context": resume_context,
            "primary_action": primary_action,
            "action_target": action_target,
        })

    return dashboard


def get_learning_streak(user, *, local_zone=None):
    today = timezone.localdate(timezone=local_zone)
    active_days = (
        LearningActivity.objects.filter(user=user, date__lte=today)
        .order_by('date')
        .values_list('date', flat=True)
    )
    one_day = timedelta(days=1)
    previous = None
    streak = longest = 0
    for day in active_days.iterator():
        streak = streak + 1 if previous and day - previous == one_day else 1
        longest = max(longest, streak)
        previous = day

    return {
        "current_streak": streak if previous and today - previous <= one_day else 0,
        "longest_streak": longest,
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


def get_weekly_learning_progress(user, *, local_zone=None):
    today = timezone.localdate(timezone=local_zone)
    start_of_week = today - timedelta(days=today.weekday())
    return LearningActivity.objects.filter(user=user, date__range=(start_of_week, today)).aggregate(
        active_days=Count('pk'),
        total_watch_time=Sum('watch_seconds', default=0),
    )


def get_or_create_student_profile(user):
    profile, _ = StudentProfile.objects.get_or_create(user=user)
    return profile


@transaction.atomic
def update_student_profile(user, **kwargs):
    """
    Update student profile.
    
    Args:
        user: User instance
        **kwargs: Fields to update
    
    Returns:
        Updated StudentProfile instance
    
    Raises:
        ValidationError: If user doesn't have a profile
    """
    try:
        profile = StudentProfile.objects.get(user=user)
    except StudentProfile.DoesNotExist:
        raise ValidationError("Student profile not found.")
    
    # Only allow updating certain fields
    allowed_fields = [
        'preferred_learning_style',
        'learning_goals',
        'interests',
        'weekly_study_hours',
        'preferred_study_time',
    ]
    
    for field, value in kwargs.items():
        if field in allowed_fields:
            setattr(profile, field, value)
    
    profile.save()
    return profile


@transaction.atomic
def create_student_note(user, lesson_id, content, timestamp=0, tags=None):
    """
    Create a note for a lesson.
    
    Args:
        user: User instance
        lesson_id: Lesson ID
        content: Note content
        timestamp: Video timestamp in seconds
        tags: List of tags
    
    Returns:
        StudentNote instance
    
    Raises:
        ValidationError: If lesson not found or user not enrolled
    """
    try:
        lesson = Lesson.objects.get(id=lesson_id)
    except Lesson.DoesNotExist:
        raise ValidationError("Lesson not found.")
    
    # Verify user is enrolled in the course
    course = lesson.module.course
    if not Enrollment.objects.filter(user=user, course=course, status__in=ACCESS_STATUSES).exists():
        raise ValidationError("You must be enrolled in this course to take notes.")
    
    note = StudentNote.objects.create(
        user=user,
        lesson=lesson,
        content=content,
        timestamp=timestamp,
        tags=tags or []
    )
    
    return note


@transaction.atomic
def update_student_note(note_id, user, **kwargs):
    """
    Update a student note.
    
    Args:
        note_id: Note UUID
        user: User instance
        **kwargs: Fields to update
    
    Returns:
        Updated StudentNote instance
    
    Raises:
        ValidationError: If note not found
        PermissionDenied: If user doesn't own the note
    """
    try:
        note = StudentNote.objects.get(id=note_id)
    except StudentNote.DoesNotExist:
        raise ValidationError("Note not found.")
    
    if note.user != user:
        raise PermissionDenied("You can only update your own notes.")
    
    allowed_fields = ['content', 'timestamp', 'is_pinned', 'tags']
    
    for field, value in kwargs.items():
        if field in allowed_fields:
            setattr(note, field, value)
    
    note.save()
    return note


@transaction.atomic
def delete_student_note(note_id, user):
    """
    Delete a student note.
    
    Args:
        note_id: Note UUID
        user: User instance
    
    Raises:
        ValidationError: If note not found
        PermissionDenied: If user doesn't own the note
    """
    try:
        note = StudentNote.objects.get(id=note_id)
    except StudentNote.DoesNotExist:
        raise ValidationError("Note not found.")
    
    if note.user != user:
        raise PermissionDenied("You can only delete your own notes.")
    
    note.delete()


@transaction.atomic
def create_bookmark(user, course_id=None, lesson_id=None, note=""):
    """
    Create a bookmark for a course or lesson.
    
    Args:
        user: User instance
        course_id: Course ID (optional)
        lesson_id: Lesson ID (optional)
        note: Bookmark note
    
    Returns:
        StudentBookmark instance
    
    Raises:
        ValidationError: If neither course nor lesson provided, or both provided
    """
    if not course_id and not lesson_id:
        raise ValidationError("Either course_id or lesson_id must be provided.")
    
    if course_id and lesson_id:
        raise ValidationError("Cannot bookmark both course and lesson simultaneously.")
    
    course = None
    lesson = None
    
    if course_id:
        try:
            course = Course.objects.get(id=course_id)
        except (Course.DoesNotExist, TypeError, ValueError, OverflowError) as exc:
            raise ValidationError("Course not found.") from exc
        if not can_view_course_catalog(user, course):
            raise ValidationError("Course not found.")
    
    if lesson_id:
        try:
            lesson = Lesson.objects.select_related('module__course').get(id=lesson_id)
        except (Lesson.DoesNotExist, TypeError, ValueError, OverflowError) as exc:
            raise ValidationError("Lesson not found.") from exc
        if not can_view_course_catalog(user, lesson.module.course):
            raise ValidationError("Lesson not found.")
    
    # Create or update bookmark
    bookmark, created = StudentBookmark.objects.update_or_create(
        user=user,
        course=course,
        lesson=lesson,
        defaults={'note': note}
    )
    
    return bookmark


@transaction.atomic
def delete_bookmark(bookmark_id, user):
    """
    Delete a bookmark.
    
    Args:
        bookmark_id: Bookmark UUID
        user: User instance
    
    Raises:
        ValidationError: If bookmark not found
        PermissionDenied: If user doesn't own the bookmark
    """
    try:
        bookmark = StudentBookmark.objects.get(id=bookmark_id)
    except StudentBookmark.DoesNotExist:
        raise ValidationError("Bookmark not found.")
    
    if bookmark.user != user:
        raise PermissionDenied("You can only delete your own bookmarks.")
    
    bookmark.delete()


def get_student_notes(user, lesson_id=None, course_id=None):
    """
    Get student notes, optionally filtered by lesson or course.
    
    Args:
        user: User instance
        lesson_id: Lesson ID (optional)
        course_id: Course ID (optional)
    
    Returns:
        QuerySet of StudentNote instances
    """
    notes = StudentNote.objects.filter(user=user).select_related(
        'lesson', 'lesson__module__course'
    )
    
    if lesson_id:
        notes = notes.filter(lesson_id=lesson_id)
    
    if course_id:
        notes = notes.filter(lesson__module__course_id=course_id)
    
    return notes.order_by('-is_pinned', '-created_at')


def get_student_bookmarks(user):
    """
    Get all student bookmarks.
    
    Args:
        user: User instance
    
    Returns:
        QuerySet of StudentBookmark instances
    """
    visible_courses = visible_catalog_courses(user)
    return StudentBookmark.objects.filter(user=user).filter(
        Q(course__in=visible_courses, lesson__isnull=True)
        | Q(lesson__module__course__in=visible_courses, course__isnull=True)
    ).select_related(
        'course', 'lesson', 'lesson__module__course'
    ).order_by('-created_at')


def get_or_create_wallet(user):
    """
    Get or create wallet for user.
    
    Args:
        user: User instance
    
    Returns:
        Wallet instance
    """
    wallet, created = Wallet.objects.get_or_create(user=user)
    return wallet
