from accounts.models import User
from courses.models import Course
from enrollments.models import Enrollment
from payments.models import Payment, Payout, Refund
from social.models import Review, Thread, Post
from events.models import Event, EventRegistration
from adminpanel.models import AdminAction, ContentModerationQueue, PlatformSettings, SystemAlert
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q, F
from django.db.models.functions import TruncDate, TruncMonth
from datetime import timedelta


# ==========================================
# USER MANAGEMENT
# ==========================================

def get_all_users(filters=None):
    """Get all users with optional filters"""
    queryset = User.objects.all().select_related('profile').order_by("-created_at")
    
    if filters:
        if filters.get('role'):
            queryset = queryset.filter(role=filters['role'])
        if filters.get('is_active') is not None:
            queryset = queryset.filter(is_active=filters['is_active'])
        if filters.get('search'):
            search_term = filters['search']
            queryset = queryset.filter(
                Q(email__icontains=search_term) |
                Q(profile__full_name__icontains=search_term)
            )
    
    return queryset


def get_user_stats():
    """Get user statistics"""
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    
    return {
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': total_users - active_users,
        'students': User.objects.filter(role='student').count(),
        'instructors': User.objects.filter(role='instructor').count(),
        'admins': User.objects.filter(role='admin').count(),
        'new_users_30_days': User.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count(),
    }


def approve_instructor(user_id, admin_user=None):
    """Approve a user as instructor"""
    user = User.objects.get(id=user_id)
    user.role = "instructor"
    user.save(update_fields=["role"])
    
    # Log admin action
    if admin_user:
        AdminAction.objects.create(
            admin_user=admin_user,
            action_type='instructor_approve',
            target_model='User',
            target_id=user_id,
            description=f"Approved {user.email} as instructor"
        )
    
    return user


def suspend_user(user_id, admin_user=None, reason=None):
    """Suspend a user account"""
    user = User.objects.get(id=user_id)
    user.is_active = False
    user.save(update_fields=["is_active"])
    
    # Log admin action
    if admin_user:
        AdminAction.objects.create(
            admin_user=admin_user,
            action_type='user_suspend',
            target_model='User',
            target_id=user_id,
            description=reason or f"Suspended user {user.email}",
            metadata={'reason': reason}
        )
    
    return user


def activate_user(user_id, admin_user=None):
    """Activate a suspended user account"""
    user = User.objects.get(id=user_id)
    user.is_active = True
    user.save(update_fields=["is_active"])
    
    # Log admin action
    if admin_user:
        AdminAction.objects.create(
            admin_user=admin_user,
            action_type='user_activate',
            target_model='User',
            target_id=user_id,
            description=f"Activated user {user.email}"
        )
    
    return user


def delete_user(user_id, admin_user=None):
    """Delete a user account (soft delete by deactivating)"""
    user = User.objects.get(id=user_id)
    
    # Log before deletion
    if admin_user:
        AdminAction.objects.create(
            admin_user=admin_user,
            action_type='user_delete',
            target_model='User',
            target_id=user_id,
            description=f"Deleted user {user.email}",
            metadata={'email': user.email, 'role': user.role}
        )
    
    # Perform soft delete
    user.is_active = False
    user.email = f"deleted_{user.id}_{user.email}"
    user.save()
    
    return True


# ==========================================
# COURSE MODERATION
# ==========================================

def get_pending_courses():
    """Get courses pending approval"""
    return Course.objects.filter(
        status__in=['under_review', 'draft']
    ).select_related('instructor', 'category').order_by('-created_at')


def get_course_stats():
    """Get course statistics"""
    return {
        'total_courses': Course.objects.count(),
        'published': Course.objects.filter(status='published').count(),
        'pending': Course.objects.filter(status='under_review').count(),
        'draft': Course.objects.filter(status='draft').count(),
        'archived': Course.objects.filter(status='archived').count(),
    }


def approve_course(course_id, admin_user=None):
    """Approve a course for publication"""
    course = Course.objects.get(id=course_id)
    course.status = "published"
    course.published_at = timezone.now()
    if admin_user:
        course.reviewed_by = admin_user
        course.reviewed_at = timezone.now()
    course.save()
    
    # Log admin action
    if admin_user:
        AdminAction.objects.create(
            admin_user=admin_user,
            action_type='course_approve',
            target_model='Course',
            target_id=course_id,
            description=f"Approved course: {course.title}"
        )
    
    return course


def reject_course(course_id, reason=None, admin_user=None):
    """Reject a course"""
    course = Course.objects.get(id=course_id)
    course.status = "draft"
    if hasattr(course, 'rejection_reason'):
        course.rejection_reason = reason
    if admin_user:
        course.reviewed_by = admin_user
        course.reviewed_at = timezone.now()
    course.save()
    
    # Log admin action
    if admin_user:
        AdminAction.objects.create(
            admin_user=admin_user,
            action_type='course_reject',
            target_model='Course',
            target_id=course_id,
            description=f"Rejected course: {course.title}",
            metadata={'reason': reason}
        )
    
    return course


def delete_course(course_id, admin_user=None):
    """Delete a course (archive it)"""
    course = Course.objects.get(id=course_id)
    course.status = 'archived'
    course.archived_at = timezone.now()
    course.save()
    
    # Log admin action
    if admin_user:
        AdminAction.objects.create(
            admin_user=admin_user,
            action_type='course_delete',
            target_model='Course',
            target_id=course_id,
            description=f"Deleted/Archived course: {course.title}"
        )
    
    return course


# ==========================================
# CONTENT MODERATION
# ==========================================

def get_flagged_content():
    """Get all flagged content for review"""
    return ContentModerationQueue.objects.filter(
        status__in=['pending', 'flagged']
    ).select_related('reported_by', 'reviewed_by').order_by('-created_at')


def get_flagged_reviews():
    """Get flagged reviews"""
    return Review.objects.filter(is_flagged=True).select_related('user', 'course')


def remove_review(review_id, admin_user=None):
    """Remove a flagged review"""
    review = Review.objects.get(id=review_id)
    
    # Log admin action before deletion
    if admin_user:
        AdminAction.objects.create(
            admin_user=admin_user,
            action_type='review_remove',
            target_model='Review',
            target_id=review_id,
            description=f"Removed review by {review.user.email} for {review.course.title}"
        )
    
    review.delete()
    return True


def approve_review(review_id, admin_user=None):
    """Approve a flagged review"""
    review = Review.objects.get(id=review_id)
    review.is_flagged = False
    review.is_approved = True
    review.save()
    
    # Log admin action
    if admin_user:
        AdminAction.objects.create(
            admin_user=admin_user,
            action_type='review_approve',
            target_model='Review',
            target_id=review_id,
            description=f"Approved review by {review.user.email}"
        )
    
    return review


def moderate_content(content_id, action, admin_user=None, notes=None):
    """Moderate content in moderation queue"""
    moderation = ContentModerationQueue.objects.get(id=content_id)
    moderation.status = action  # 'approved' or 'rejected'
    moderation.reviewed_by = admin_user
    moderation.reviewed_at = timezone.now()
    if notes:
        moderation.admin_notes = notes
    moderation.save()
    
    return moderation


# ==========================================
# PAYMENT & REVENUE MANAGEMENT
# ==========================================

def get_all_payments(filters=None):
    """Get all payments with filters"""
    queryset = Payment.objects.select_related("user", "course", "instructor", "event")
    
    if filters:
        if filters.get('status'):
            queryset = queryset.filter(status=filters['status'])
        if filters.get('start_date'):
            queryset = queryset.filter(created_at__gte=filters['start_date'])
        if filters.get('end_date'):
            queryset = queryset.filter(created_at__lte=filters['end_date'])
    
    return queryset.order_by('-created_at')


def get_revenue_stats(start_date=None, end_date=None):
    """Get revenue statistics"""
    queryset = Payment.objects.filter(status="completed")
    
    if start_date:
        queryset = queryset.filter(created_at__gte=start_date)
    if end_date:
        queryset = queryset.filter(created_at__lte=end_date)
    
    stats = queryset.aggregate(
        total_revenue=Sum('amount'),
        platform_revenue=Sum('platform_fee'),
        instructor_revenue=Sum('instructor_earnings'),
        total_transactions=Count('id'),
        avg_transaction=Avg('amount')
    )
    
    return {
        'total_revenue': stats['total_revenue'] or 0,
        'platform_revenue': stats['platform_revenue'] or 0,
        'instructor_revenue': stats['instructor_revenue'] or 0,
        'total_transactions': stats['total_transactions'] or 0,
        'avg_transaction': stats['avg_transaction'] or 0,
        'pending_payments': Payment.objects.filter(status='pending').count(),
        'failed_payments': Payment.objects.filter(status='failed').count(),
    }


def refund_payment(payment_id, reason=None, admin_user=None):
    """Process a refund for a payment"""
    payment = Payment.objects.get(id=payment_id)
    payment.status = "refunded"
    payment.save(update_fields=["status"])

    refund = Refund.objects.create(
        payment=payment,
        amount=payment.amount,
        reason=reason,
        processed_at=timezone.now()
    )
    
    # Log admin action
    if admin_user:
        AdminAction.objects.create(
            admin_user=admin_user,
            action_type='payment_refund',
            target_model='Payment',
            target_id=payment_id,
            description=f"Refunded payment of {payment.amount} {payment.currency}",
            metadata={'reason': reason}
        )
    
    return refund


def get_pending_payouts():
    """Get pending instructor payouts"""
    return Payout.objects.filter(status="pending").select_related('instructor')


def approve_payout(payout_id, admin_user=None):
    """Approve and process a payout"""
    payout = Payout.objects.get(id=payout_id)
    payout.status = "paid"
    payout.processed_at = timezone.now()
    payout.save()
    
    # Log admin action
    if admin_user:
        AdminAction.objects.create(
            admin_user=admin_user,
            action_type='payout_approve',
            target_model='Payout',
            target_id=payout_id,
            description=f"Approved payout of {payout.amount} to {payout.instructor.email}"
        )
    
    return payout


# ==========================================
# PLATFORM ANALYTICS & STATS
# ==========================================

def platform_stats():
    """Get comprehensive platform statistics"""
    return {
        'total_courses': Course.objects.count(),
        'published_courses': Course.objects.filter(status='published').count(),
        'total_users': User.objects.count(),
        'total_students': User.objects.filter(role='student').count(),
        'total_instructors': User.objects.filter(role='instructor').count(),
        'total_enrollments': Enrollment.objects.count(),
        'active_enrollments': Enrollment.objects.filter(status='active').count(),
        'completed_enrollments': Enrollment.objects.filter(is_completed=True).count(),
        'total_revenue': Payment.objects.filter(
            status="completed"
        ).aggregate(total=Sum("amount"))["total"] or 0,
        'pending_reviews': ContentModerationQueue.objects.filter(status='pending').count(),
        'flagged_content': ContentModerationQueue.objects.filter(status='flagged').count(),
        'total_events': Event.objects.count(),
        'upcoming_events': Event.objects.filter(
            scheduled_for__gte=timezone.now(),
            status='published'
        ).count(),
    }


def get_growth_metrics(days=30):
    """Get platform growth metrics over time"""
    cutoff_date = timezone.now() - timedelta(days=days)
    
    # User growth
    users_by_day = User.objects.filter(
        created_at__gte=cutoff_date
    ).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Enrollment growth
    enrollments_by_day = Enrollment.objects.filter(
        enrolled_at__gte=cutoff_date
    ).annotate(
        date=TruncDate('enrolled_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Revenue growth
    revenue_by_day = Payment.objects.filter(
        created_at__gte=cutoff_date,
        status='completed'
    ).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        revenue=Sum('amount')
    ).order_by('date')
    
    return {
        'users': list(users_by_day),
        'enrollments': list(enrollments_by_day),
        'revenue': list(revenue_by_day),
    }


def get_top_performing_courses(limit=10):
    """Get top performing courses by enrollments and revenue"""
    return Course.objects.filter(
        status='published'
    ).annotate(
        enrollment_count=Count('enrollments'),
        total_revenue=Sum('payments__amount', filter=Q(payments__status='completed'))
    ).order_by('-enrollment_count')[:limit]


def get_top_instructors(limit=10):
    """Get top instructors by revenue and student count"""
    return User.objects.filter(
        role='instructor'
    ).annotate(
        total_students=Count('courses__enrollments', distinct=True),
        total_revenue=Sum('instructor_payments__amount', filter=Q(instructor_payments__status='completed'))
    ).order_by('-total_revenue')[:limit]


# ==========================================
# SYSTEM SETTINGS & ALERTS
# ==========================================

def get_platform_settings():
    """Get all platform settings"""
    return PlatformSettings.objects.all()


def update_platform_setting(key, value, admin_user=None):
    """Update or create a platform setting"""
    setting, created = PlatformSettings.objects.update_or_create(
        key=key,
        defaults={
            'value': value,
            'updated_by': admin_user,
        }
    )
    return setting


def get_active_system_alerts():
    """Get currently active system alerts"""
    now = timezone.now()
    return SystemAlert.objects.filter(
        is_active=True,
        start_time__lte=now
    ).filter(
        Q(end_time__isnull=True) | Q(end_time__gte=now)
    )


def create_system_alert(title, message, alert_type='info', admin_user=None, **kwargs):
    """Create a new system alert"""
    alert = SystemAlert.objects.create(
        title=title,
        message=message,
        alert_type=alert_type,
        created_by=admin_user,
        **kwargs
    )
    return alert


# ==========================================
# EVENT MANAGEMENT
# ==========================================

def get_event_stats():
    """Get event statistics"""
    return {
        'total_events': Event.objects.count(),
        'published': Event.objects.filter(status='published').count(),
        'draft': Event.objects.filter(status='draft').count(),
        'completed': Event.objects.filter(status='completed').count(),
        'cancelled': Event.objects.filter(status='cancelled').count(),
        'upcoming': Event.objects.filter(
            scheduled_for__gte=timezone.now(),
            status='published'
        ).count(),
        'total_registrations': EventRegistration.objects.filter(
            status='confirmed'
        ).count() if hasattr(EventRegistration, 'objects') else 0,
    }


def cancel_event(event_id, reason=None, admin_user=None):
    """Cancel an event"""
    event = Event.objects.get(id=event_id)
    event.status = 'cancelled'
    event.save()
    
    # Log admin action
    if admin_user:
        AdminAction.objects.create(
            admin_user=admin_user,
            action_type='event_cancel',
            target_model='Event',
            target_id=event_id,
            description=f"Cancelled event: {event.title}",
            metadata={'reason': reason}
        )
    
    return event


# ==========================================
# ADMIN ACTIVITY LOG
# ==========================================

def get_admin_activity_log(admin_user=None, limit=100):
    """Get admin activity log"""
    queryset = AdminAction.objects.select_related('admin_user')
    
    if admin_user:
        queryset = queryset.filter(admin_user=admin_user)
    
    return queryset[:limit]


def get_recent_admin_actions(days=7):
    """Get recent admin actions"""
    cutoff_date = timezone.now() - timedelta(days=days)
    return AdminAction.objects.filter(
        created_at__gte=cutoff_date
    ).select_related('admin_user').order_by('-created_at')


