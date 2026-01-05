from itertools import chain
from datetime import timedelta
from decimal import Decimal
from django.db import models, transaction
from django.db.models import Value, CharField, Count, Q, Max, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth import get_user_model

from certificates.models import Certificate
from courses.models import Lesson, Course
from enrollments.models import Enrollment, LessonProgress
from enrollments.services import get_resume_lesson
from .models import StudentProfile, StudentNote, StudentBookmark, Wallet, WalletTransaction
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
        total=Sum('watch_time')
    )['total'] or 0

    return {
        "active_days": active_days,
        "total_watch_time": total_watch_time
    }


@transaction.atomic
def get_or_create_student_profile(user):
    """
    Get or create student profile for a user.
    
    Args:
        user: User instance
    
    Returns:
        StudentProfile instance
    """
    profile, created = StudentProfile.objects.get_or_create(
        user=user,
        defaults={}
    )
    
    if created:
        # Initialize statistics
        profile.update_statistics()
    
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
    if not Enrollment.objects.filter(user=user, course=course, status='active').exists():
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
        except Course.DoesNotExist:
            raise ValidationError("Course not found.")
    
    if lesson_id:
        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
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
    return StudentBookmark.objects.filter(user=user).select_related(
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


def add_funds_to_wallet(user, amount, description='Funds added to wallet'):
    """
    Add funds to student wallet.
    
    Args:
        user: User instance
        amount: Decimal amount to add
        description: Transaction description
    
    Returns:
        dict with success status, new balance, and transaction
    
    Raises:
        ValidationError: If amount is invalid
    """
    if amount <= 0:
        raise ValidationError("Amount must be positive")
    
    wallet = get_or_create_wallet(user)
    
    with transaction.atomic():
        new_balance = wallet.add_money(amount)
        
        transaction_record = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='credit',
            amount=amount,
            description=description,
            balance_after=new_balance
        )
    
    return {
        'success': True,
        'balance': new_balance,
        'transaction': transaction_record
    }


def deduct_funds_from_wallet(user, amount, description='Purchase'):
    """
    Deduct funds from student wallet.
    
    Args:
        user: User instance
        amount: Decimal amount to deduct
        description: Transaction description
    
    Returns:
        dict with success status, new balance, and transaction
    
    Raises:
        ValidationError: If amount is invalid or insufficient balance
    """
    if amount <= 0:
        raise ValidationError("Amount must be positive")
    
    wallet = get_or_create_wallet(user)
    
    if wallet.balance < Decimal(str(amount)):
        raise ValidationError(
            f"Insufficient balance. Current balance: ${wallet.balance}, Required: ${amount}"
        )
    
    with transaction.atomic():
        new_balance = wallet.deduct_money(amount)
        
        transaction_record = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='debit',
            amount=amount,
            description=description,
            balance_after=new_balance
        )
    
    return {
        'success': True,
        'balance': new_balance,
        'transaction': transaction_record
    }


def get_wallet_balance(user):
    """
    Get current wallet balance.
    
    Args:
        user: User instance
    
    Returns:
        Decimal balance
    """
    wallet = get_or_create_wallet(user)
    return wallet.balance


def get_wallet_transactions(user, limit=None):
    """
    Get wallet transaction history.
    
    Args:
        user: User instance
        limit: Optional limit on number of transactions
    
    Returns:
        QuerySet of WalletTransaction instances
    """
    wallet = get_or_create_wallet(user)
    transactions = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')
    
    if limit:
        transactions = transactions[:limit]
    
    return transactions
