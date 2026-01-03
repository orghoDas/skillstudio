"""
Analytics Services
Comprehensive analytics and reporting services for the platform
"""

from django.db.models import Count, Avg, Sum, Q, F, Max, Min
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from courses.models import Course, Lesson
from enrollments.models import Enrollment, LessonProgress
from accounts.models import User
from payments.models import Payment
from events.models import Event
from social.models import Review
from analytics.models import (
    CourseAnalyticsSnapshot,
    UserInteraction,
    InstructorAnalytics,
    LessonAnalytics,
    EventAnalytics,
    SearchQuery,
    DailyPlatformMetrics,
)


# ==========================================
# COURSE ANALYTICS
# ==========================================

def get_course_analytics(course_id, instructor=None):
    """
    Get comprehensive analytics for a specific course
    """
    try:
        course = Course.objects.get(id=course_id)
        
        # Verify instructor ownership if provided
        if instructor and course.instructor != instructor:
            raise PermissionError("Instructor does not own this course")
        
        enrollments = Enrollment.objects.filter(course=course)
        total_enrollments = enrollments.count()
        completed_enrollments = enrollments.filter(is_completed=True).count()
        
        completion_rate = round((completed_enrollments / total_enrollments * 100), 2) if total_enrollments > 0 else 0
        
        # Lesson analytics
        total_lessons = Lesson.objects.filter(module__course=course).count()
        
        progress_queryset = (
            LessonProgress.objects.filter(lesson__module__course=course, is_completed=True)
            .values('enrollment')
            .annotate(completed_lessons=Count('id'))
        )
        
        progress_percentages = [
            (item['completed_lessons'] / total_lessons) * 100 for item in progress_queryset
        ] if total_lessons > 0 else []
        
        avg_progress = round(sum(progress_percentages) / len(progress_percentages), 2) if progress_percentages else 0
        
        # Drop-off analysis
        drop_off = (LessonProgress.objects
                    .filter(lesson__module__course=course)
                    .values('lesson_id', 'lesson__title')
                    .annotate(total_views=Count('enrollment', distinct=True))
                    .order_by('total_views').first()
                    )
        
        # Watch time
        total_watch_time = LessonProgress.objects.filter(
            lesson__module__course=course
        ).aggregate(total_time=Sum('watch_time'))['total_time'] or 0
        
        avg_watch_time = LessonProgress.objects.filter(
            lesson__module__course=course
        ).aggregate(avg_time=Avg('watch_time'))['avg_time'] or 0
        
        # Revenue analytics
        total_revenue = Payment.objects.filter(
            course=course,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Rating analytics
        reviews = Review.objects.filter(course=course)
        avg_rating = reviews.aggregate(avg=Avg('rating'))['avg']
        total_reviews = reviews.count()
        
        # Enrollment trend (last 30 days)
        cutoff_date = timezone.now() - timedelta(days=30)
        enrollment_trend = enrollments.filter(
            enrolled_at__gte=cutoff_date
        ).annotate(
            date=TruncDate('enrolled_at')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        return {
            'course_id': course.id,
            'course_title': course.title,
            'total_enrollments': total_enrollments,
            'completed_enrollments': completed_enrollments,
            'active_enrollments': enrollments.filter(status='active').count(),
            'completion_rate': completion_rate,
            'average_progress': avg_progress,
            'total_lessons': total_lessons,
            'highest_drop_off_lesson': drop_off,
            'total_watch_time_seconds': int(total_watch_time),
            'average_watch_time_seconds': round(avg_watch_time, 2),
            'total_revenue': float(total_revenue),
            'average_rating': round(avg_rating, 2) if avg_rating else None,
            'total_reviews': total_reviews,
            'enrollment_trend': list(enrollment_trend),
        }
    except Course.DoesNotExist:
        return None


def get_lesson_analytics(lesson_id):
    """Get analytics for a specific lesson"""
    try:
        lesson = Lesson.objects.get(id=lesson_id)
        
        progress_records = LessonProgress.objects.filter(lesson=lesson)
        total_views = progress_records.count()
        total_completions = progress_records.filter(is_completed=True).count()
        
        completion_rate = (total_completions / total_views * 100) if total_views > 0 else 0
        
        avg_watch_time = progress_records.aggregate(avg=Avg('watch_time'))['avg'] or 0
        
        # Update or create lesson analytics
        analytics, created = LessonAnalytics.objects.update_or_create(
            lesson=lesson,
            defaults={
                'total_views': total_views,
                'total_completions': total_completions,
                'average_watch_time': int(avg_watch_time),
                'drop_off_rate': round(100 - completion_rate, 2),
            }
        )
        
        return {
            'lesson_id': lesson.id,
            'lesson_title': lesson.title,
            'total_views': total_views,
            'total_completions': total_completions,
            'completion_rate': round(completion_rate, 2),
            'average_watch_time': round(avg_watch_time, 2),
            'drop_off_rate': analytics.drop_off_rate,
        }
    except Lesson.DoesNotExist:
        return None


def get_course_comparison(instructor):
    """Compare all courses for an instructor"""
    courses = Course.objects.filter(instructor=instructor)
    
    data = []
    for course in courses:
        analytics = get_course_analytics(course.id, instructor=instructor)
        if analytics:
            data.append(analytics)
    
    return data


def get_lesson_dropoff_analysis(course_id, instructor=None):
    """Analyze lesson-level drop-off rates for a course"""
    try:
        course = Course.objects.get(id=course_id)
        
        if instructor and course.instructor != instructor:
            raise PermissionError("Instructor does not own this course")
        
        lessons = Lesson.objects.filter(module__course=course).annotate(
            started_count=Count('lessonprogress', distinct=True),
            completed_count=Count('lessonprogress', filter=Q(lessonprogress__is_completed=True), distinct=True)
        )
        
        data = []
        for lesson in lessons:
            started = lesson.started_count or 0
            completed = lesson.completed_count or 0
            drop_off = started - completed
            drop_off_rate = round((drop_off * 100.0 / started), 2) if started > 0 else 0
            
            data.append({
                'lesson_id': lesson.id,
                'lesson_title': lesson.title,
                'module_title': lesson.module.title,
                'started_enrollments': started,
                'completed_enrollments': completed,
                'drop_off_count': drop_off,
                'drop_off_rate_percentage': drop_off_rate,
            })
        
        return data
    except Course.DoesNotExist:
        return None


# ==========================================
# INSTRUCTOR ANALYTICS
# ==========================================

def get_instructor_analytics(instructor):
    """Get comprehensive analytics for an instructor"""
    courses = Course.objects.filter(instructor=instructor)
    
    total_students = Enrollment.objects.filter(
        course__in=courses
    ).values('user').distinct().count()
    
    total_revenue = Payment.objects.filter(
        instructor=instructor,
        status='completed'
    ).aggregate(total=Sum('instructor_earnings'))['total'] or Decimal('0')
    
    total_completions = Enrollment.objects.filter(
        course__in=courses,
        is_completed=True
    ).count()
    
    avg_rating = Review.objects.filter(
        course__in=courses
    ).aggregate(avg=Avg('rating'))['avg']
    
    total_reviews = Review.objects.filter(course__in=courses).count()
    
    # Update or create instructor analytics
    analytics, created = InstructorAnalytics.objects.update_or_create(
        instructor=instructor,
        defaults={
            'total_courses': courses.count(),
            'total_students': total_students,
            'total_revenue': total_revenue,
            'average_rating': round(avg_rating, 2) if avg_rating else None,
            'total_reviews': total_reviews,
            'total_completions': total_completions,
        }
    )
    
    # Course breakdown
    course_breakdown = []
    for course in courses:
        course_data = get_course_analytics(course.id, instructor=instructor)
        if course_data:
            course_breakdown.append({
                'course_id': course.id,
                'title': course.title,
                'enrollments': course_data['total_enrollments'],
                'revenue': course_data['total_revenue'],
                'rating': course_data['average_rating'],
            })
    
    return {
        'instructor_id': instructor.id,
        'instructor_email': instructor.email,
        'total_courses': courses.count(),
        'total_students': total_students,
        'total_revenue': float(total_revenue),
        'average_rating': round(avg_rating, 2) if avg_rating else None,
        'total_reviews': total_reviews,
        'total_completions': total_completions,
        'course_breakdown': course_breakdown,
    }


def get_instructor_earnings_breakdown(instructor, start_date=None, end_date=None):
    """Get detailed earnings breakdown for instructor"""
    payments = Payment.objects.filter(
        instructor=instructor,
        status='completed'
    )
    
    if start_date:
        payments = payments.filter(created_at__gte=start_date)
    if end_date:
        payments = payments.filter(created_at__lte=end_date)
    
    # Aggregate by course
    by_course = payments.values(
        'course__id', 'course__title'
    ).annotate(
        total=Sum('instructor_earnings'),
        count=Count('id')
    ).order_by('-total')
    
    # Aggregate by month
    by_month = payments.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        total=Sum('instructor_earnings'),
        count=Count('id')
    ).order_by('month')
    
    total_earnings = payments.aggregate(total=Sum('instructor_earnings'))['total'] or Decimal('0')
    total_transactions = payments.count()
    
    return {
        'total_earnings': float(total_earnings),
        'total_transactions': total_transactions,
        'by_course': list(by_course),
        'by_month': list(by_month),
    }


# ==========================================
# STUDENT ANALYTICS
# ==========================================

def get_student_analytics(student):
    """Get analytics for a student"""
    enrollments = Enrollment.objects.filter(user=student)
    
    total_enrollments = enrollments.count()
    completed = enrollments.filter(is_completed=True).count()
    in_progress = enrollments.filter(status='active', is_completed=False).count()
    
    # Learning time
    total_watch_time = LessonProgress.objects.filter(
        user=student
    ).aggregate(total=Sum('watch_time'))['total'] or 0
    
    # Certificates/completions
    certificates = completed  # Simplified, can link to actual certificate model
    
    # Recent activity
    recent_activity = LessonProgress.objects.filter(
        user=student
    ).select_related('lesson', 'lesson__module', 'lesson__module__course'
    ).order_by('-updated_at')[:10]
    
    return {
        'student_id': student.id,
        'total_enrollments': total_enrollments,
        'completed_courses': completed,
        'in_progress_courses': in_progress,
        'total_watch_time_hours': round(total_watch_time / 3600, 2),
        'certificates_earned': certificates,
        'recent_activity': [
            {
                'lesson': activity.lesson.title,
                'course': activity.lesson.module.course.title,
                'is_completed': activity.is_completed,
                'last_accessed': activity.updated_at,
            }
            for activity in recent_activity
        ],
    }


def get_student_progress_report(student, course_id):
    """Get detailed progress report for a student in a specific course"""
    try:
        enrollment = Enrollment.objects.get(user=student, course_id=course_id)
        course = enrollment.course
        
        lessons = Lesson.objects.filter(module__course=course)
        total_lessons = lessons.count()
        
        progress_records = LessonProgress.objects.filter(
            enrollment=enrollment
        ).select_related('lesson')
        
        completed_lessons = progress_records.filter(is_completed=True).count()
        
        progress_percentage = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
        
        total_watch_time = progress_records.aggregate(total=Sum('watch_time'))['total'] or 0
        
        # Lesson-by-lesson breakdown
        lesson_breakdown = []
        for lesson in lessons:
            progress = progress_records.filter(lesson=lesson).first()
            lesson_breakdown.append({
                'lesson_id': lesson.id,
                'title': lesson.title,
                'is_completed': progress.is_completed if progress else False,
                'watch_time': progress.watch_time if progress else 0,
                'last_accessed': progress.updated_at if progress else None,
            })
        
        return {
            'course_id': course.id,
            'course_title': course.title,
            'enrollment_date': enrollment.enrolled_at,
            'is_completed': enrollment.is_completed,
            'progress_percentage': round(progress_percentage, 2),
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'total_watch_time_minutes': round(total_watch_time / 60, 2),
            'lesson_breakdown': lesson_breakdown,
        }
    except Enrollment.DoesNotExist:
        return None


# ==========================================
# EVENT ANALYTICS
# ==========================================

def get_event_analytics(event_id):
    """Get analytics for a specific event"""
    try:
        event = Event.objects.get(id=event_id)
        
        # Check if EventRegistration model exists
        try:
            from events.models import EventRegistration
            registrations = EventRegistration.objects.filter(event=event)
            total_registrations = registrations.count()
            confirmed = registrations.filter(status='confirmed').count()
            attended = registrations.filter(attended=True).count() if hasattr(EventRegistration, 'attended') else 0
            attendance_rate = (attended / confirmed * 100) if confirmed > 0 else 0
        except (ImportError, AttributeError):
            total_registrations = 0
            confirmed = 0
            attended = 0
            attendance_rate = 0
        
        # Revenue
        total_revenue = Payment.objects.filter(
            event=event,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Update or create event analytics
        analytics, created = EventAnalytics.objects.update_or_create(
            event=event,
            defaults={
                'total_registrations': total_registrations,
                'total_attendees': attended,
                'attendance_rate': round(attendance_rate, 2),
                'total_revenue': total_revenue,
            }
        )
        
        return {
            'event_id': event.id,
            'event_title': event.title,
            'scheduled_for': event.scheduled_for,
            'status': event.status,
            'total_registrations': total_registrations,
            'confirmed_registrations': confirmed,
            'total_attendees': attended,
            'attendance_rate': round(attendance_rate, 2),
            'total_revenue': float(total_revenue),
            'seats_available': event.seats_available() if hasattr(event, 'seats_available') else None,
        }
    except Event.DoesNotExist:
        return None


# ==========================================
# PLATFORM-WIDE ANALYTICS
# ==========================================

def get_platform_overview(days=30):
    """Get platform-wide overview analytics"""
    cutoff_date = timezone.now() - timedelta(days=days)
    
    total_users = User.objects.count()
    new_users = User.objects.filter(created_at__gte=cutoff_date).count()
    
    total_courses = Course.objects.filter(status='published').count()
    total_enrollments = Enrollment.objects.count()
    new_enrollments = Enrollment.objects.filter(enrolled_at__gte=cutoff_date).count()
    
    total_revenue = Payment.objects.filter(
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    revenue_period = Payment.objects.filter(
        status='completed',
        created_at__gte=cutoff_date
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    return {
        'period_days': days,
        'total_users': total_users,
        'new_users': new_users,
        'total_courses': total_courses,
        'total_enrollments': total_enrollments,
        'new_enrollments': new_enrollments,
        'total_revenue': float(total_revenue),
        'revenue_this_period': float(revenue_period),
    }


def get_trending_courses(limit=10, days=7):
    """Get trending courses based on recent enrollments"""
    cutoff_date = timezone.now() - timedelta(days=days)
    
    trending = Course.objects.filter(
        status='published'
    ).annotate(
        recent_enrollments=Count(
            'enrollments',
            filter=Q(enrollments__enrolled_at__gte=cutoff_date)
        )
    ).order_by('-recent_enrollments')[:limit]
    
    return [
        {
            'course_id': course.id,
            'title': course.title,
            'instructor': course.instructor.email,
            'recent_enrollments': course.recent_enrollments,
            'total_enrollments': course.enrollments.count(),
        }
        for course in trending
    ]


def get_search_analytics(days=30):
    """Get search analytics and popular queries"""
    cutoff_date = timezone.now() - timedelta(days=days)
    
    queries = SearchQuery.objects.filter(created_at__gte=cutoff_date)
    
    # Most popular searches
    popular_queries = queries.values('query').annotate(
        count=Count('id')
    ).order_by('-count')[:20]
    
    # Searches with no results
    zero_results = queries.filter(results_count=0).count()
    
    # Total searches
    total_searches = queries.count()
    
    return {
        'total_searches': total_searches,
        'zero_result_searches': zero_results,
        'popular_queries': list(popular_queries),
        'zero_result_rate': round((zero_results / total_searches * 100), 2) if total_searches > 0 else 0,
    }


def track_user_interaction(user, action, **kwargs):
    """Track a user interaction"""
    return UserInteraction.objects.create(
        user=user,
        action=action,
        course=kwargs.get('course'),
        event=kwargs.get('event'),
        metadata=kwargs.get('metadata', {}),
        session_id=kwargs.get('session_id', ''),
        ip_address=kwargs.get('ip_address'),
        user_agent=kwargs.get('user_agent', ''),
    )


def create_daily_snapshot(date=None):
    """Create daily analytics snapshot for all courses"""
    if date is None:
        date = timezone.now().date()
    
    courses = Course.objects.filter(status='published')
    
    for course in courses:
        enrollments = Enrollment.objects.filter(course=course)
        
        CourseAnalyticsSnapshot.objects.update_or_create(
            course=course,
            snapshot_date=date,
            defaults={
                'total_enrollments': enrollments.count(),
                'total_completions': enrollments.filter(is_completed=True).count(),
                'total_watch_minutes': int(
                    (LessonProgress.objects.filter(
                        lesson__module__course=course
                    ).aggregate(total=Sum('watch_time'))['total'] or 0) / 60
                ),
                'unique_viewers': enrollments.values('user').distinct().count(),
                'average_rating': Review.objects.filter(course=course).aggregate(avg=Avg('rating'))['avg'],
                'total_revenue': Payment.objects.filter(
                    course=course,
                    status='completed'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
            }
        )


def create_daily_platform_metrics(date=None):
    """Create daily platform metrics snapshot"""
    if date is None:
        date = timezone.now().date()
    
    DailyPlatformMetrics.objects.update_or_create(
        date=date,
        defaults={
            'total_users': User.objects.count(),
            'new_users': User.objects.filter(created_at__date=date).count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'total_enrollments': Enrollment.objects.count(),
            'new_enrollments': Enrollment.objects.filter(enrolled_at__date=date).count(),
            'total_completions': Enrollment.objects.filter(is_completed=True).count(),
            'total_revenue': Payment.objects.filter(
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
            'total_courses': Course.objects.filter(status='published').count(),
            'total_events': Event.objects.count(),
        }
    )
