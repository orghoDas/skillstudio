from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from datetime import datetime, timedelta

from accounts.mixins import AdminOnlyMixin
from accounts.permissions import IsAdmin
from accounts.models import User
from courses.models import Course
from payments.models import Payment, Payout
from events.models import Event
from social.models import Review
from adminpanel.models import AdminAction, ContentModerationQueue, PlatformSettings, SystemAlert
from adminpanel.services import (
    # User management
    get_all_users, get_user_stats, approve_instructor, suspend_user, 
    activate_user, delete_user,
    # Course management
    get_pending_courses, get_course_stats, approve_course, reject_course, delete_course,
    # Content moderation
    get_flagged_content, get_flagged_reviews, remove_review, approve_review, moderate_content,
    # Payment management
    get_all_payments, get_revenue_stats, refund_payment, get_pending_payouts, approve_payout,
    # Platform stats
    platform_stats, get_growth_metrics, get_top_performing_courses, get_top_instructors,
    # Settings
    get_platform_settings, update_platform_setting, get_active_system_alerts, create_system_alert,
    # Events
    get_event_stats, cancel_event,
    # Activity log
    get_admin_activity_log, get_recent_admin_actions,
)


# ==========================================
# DASHBOARD & OVERVIEW
# ==========================================

class AdminDashboardView(APIView, AdminOnlyMixin):
    """Comprehensive admin dashboard with all key metrics"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        # Get date range from query params (default: last 30 days)
        days = int(request.query_params.get('days', 30))
        
        return Response({
            "platform_stats": platform_stats(),
            "user_stats": get_user_stats(),
            "course_stats": get_course_stats(),
            "revenue_stats": get_revenue_stats(),
            "event_stats": get_event_stats(),
            "growth_metrics": get_growth_metrics(days=days),
            "pending_items": {
                "courses": get_pending_courses().count(),
                "payouts": get_pending_payouts().count(),
                "flagged_content": get_flagged_content().count(),
            },
            "top_courses": [
                {
                    "id": c.id,
                    "title": c.title,
                    "instructor": c.instructor.email,
                    "enrollments": c.enrollment_count,
                    "revenue": float(c.total_revenue or 0),
                }
                for c in get_top_performing_courses(limit=5)
            ],
            "top_instructors": [
                {
                    "id": i.id,
                    "email": i.email,
                    "name": i.profile.full_name if hasattr(i, 'profile') and i.profile.full_name else i.email,
                    "total_students": i.total_students,
                    "total_revenue": float(i.total_revenue or 0),
                }
                for i in get_top_instructors(limit=5)
            ],
            "recent_actions": [
                {
                    "id": a.id,
                    "admin": a.admin_user.email if a.admin_user else "System",
                    "action": a.get_action_type_display(),
                    "description": a.description,
                    "timestamp": a.created_at,
                }
                for a in get_recent_admin_actions(days=7)[:10]
            ],
        })


class PlatformStatsView(APIView):
    """Detailed platform statistics"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        
        return Response({
            "overview": platform_stats(),
            "users": get_user_stats(),
            "courses": get_course_stats(),
            "events": get_event_stats(),
            "revenue": get_revenue_stats(),
            "growth": get_growth_metrics(days=days),
        })


# ==========================================
# USER MANAGEMENT
# ==========================================

class UserManagementListView(APIView):
    """List all users with filtering options"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        filters = {
            'role': request.query_params.get('role'),
            'is_active': request.query_params.get('is_active'),
            'search': request.query_params.get('search'),
        }
        # Remove None values
        filters = {k: v for k, v in filters.items() if v is not None}
        
        users = get_all_users(filters=filters)
        
        return Response({
            "count": users.count(),
            "users": [
                {
                    "id": u.id,
                    "email": u.email,
                    "role": u.role,
                    "is_active": u.is_active,
                    "full_name": u.profile.full_name if hasattr(u, 'profile') and u.profile else None,
                    "created_at": u.created_at,
                }
                for u in users[:100]  # Limit to 100 for performance
            ],
            "stats": get_user_stats(),
        })


class UserDetailView(APIView):
    """Get detailed information about a specific user"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        
        # Get user's enrollments, courses, payments
        enrollments = user.enrollments.select_related('course').all()[:10]
        
        data = {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "profile": {
                "full_name": user.profile.full_name if hasattr(user, 'profile') and user.profile else None,
                "bio": user.profile.bio if hasattr(user, 'profile') and user.profile else None,
            },
            "enrollments_count": user.enrollments.count(),
            "recent_enrollments": [
                {
                    "course_id": e.course.id,
                    "course_title": e.course.title,
                    "enrolled_at": e.enrolled_at,
                    "is_completed": e.is_completed,
                }
                for e in enrollments
            ],
        }
        
        # Add instructor-specific data
        if user.role == 'instructor':
            courses = user.courses.all()[:10]
            data["instructor_data"] = {
                "courses_count": user.courses.count(),
                "recent_courses": [
                    {
                        "id": c.id,
                        "title": c.title,
                        "status": c.status,
                        "enrollments": c.enrollments.count(),
                    }
                    for c in courses
                ],
                "total_revenue": float(
                    user.instructor_payments.filter(status='completed').aggregate(
                        total=__import__('django.db.models', fromlist=['Sum']).Sum('instructor_earnings')
                    )['total'] or 0
                ),
            }
        
        return Response(data)


class ApproveInstructorView(APIView):
    """Approve a user as instructor"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, user_id):
        user = approve_instructor(user_id, admin_user=request.user)
        return Response({
            "status": "approved",
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
        })


class SuspendUserView(APIView):
    """Suspend a user account"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, user_id):
        reason = request.data.get('reason')
        user = suspend_user(user_id, admin_user=request.user, reason=reason)
        return Response({
            "status": "suspended",
            "user_id": user.id,
            "reason": reason,
        })


class ActivateUserView(APIView):
    """Activate a suspended user"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, user_id):
        user = activate_user(user_id, admin_user=request.user)
        return Response({
            "status": "activated",
            "user_id": user.id,
        })


class DeleteUserView(APIView):
    """Delete a user account"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, user_id):
        delete_user(user_id, admin_user=request.user)
        return Response({
            "status": "deleted",
            "user_id": user_id,
        }, status=status.HTTP_204_NO_CONTENT)


# ==========================================
# COURSE MODERATION
# ==========================================

class PendingCoursesView(APIView):
    """List all courses pending approval"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        courses = get_pending_courses()
        
        return Response({
            "count": courses.count(),
            "courses": [
                {
                    "id": c.id,
                    "title": c.title,
                    "instructor": {
                        "id": c.instructor.id,
                        "email": c.instructor.email,
                    },
                    "category": c.category.name if c.category else None,
                    "status": c.status,
                    "created_at": c.created_at,
                    "submitted_for_review_at": c.submitted_for_review_at,
                }
                for c in courses
            ],
        })


class ApproveCourseView(APIView):
    """Approve a course for publication"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, course_id):
        course = approve_course(course_id, admin_user=request.user)
        return Response({
            "status": "approved",
            "course_id": course.id,
            "title": course.title,
            "published_at": course.published_at,
        })


class RejectCourseView(APIView):
    """Reject a course"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, course_id):
        reason = request.data.get('reason', '')
        course = reject_course(course_id, reason=reason, admin_user=request.user)
        return Response({
            "status": "rejected",
            "course_id": course.id,
            "reason": reason,
        })


class DeleteCourseView(APIView):
    """Delete/archive a course"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, course_id):
        course = delete_course(course_id, admin_user=request.user)
        return Response({
            "status": "deleted",
            "course_id": course.id,
        }, status=status.HTTP_204_NO_CONTENT)


# ==========================================
# CONTENT MODERATION
# ==========================================

class ContentModerationQueueView(APIView):
    """List content in moderation queue"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        content = get_flagged_content()
        
        return Response({
            "count": content.count(),
            "items": [
                {
                    "id": item.id,
                    "content_type": item.get_content_type_display(),
                    "content_id": item.content_id,
                    "reported_by": item.reported_by.email if item.reported_by else None,
                    "reason": item.reason,
                    "status": item.get_status_display(),
                    "created_at": item.created_at,
                }
                for item in content[:50]
            ],
        })


class ModerateContentView(APIView):
    """Approve or reject content"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, content_id):
        action = request.data.get('action')  # 'approved' or 'rejected'
        notes = request.data.get('notes', '')
        
        if action not in ['approved', 'rejected']:
            return Response(
                {"error": "Invalid action. Use 'approved' or 'rejected'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        moderation = moderate_content(
            content_id,
            action=action,
            admin_user=request.user,
            notes=notes
        )
        
        return Response({
            "status": moderation.status,
            "content_id": content_id,
        })


class FlaggedReviewsView(APIView):
    """List flagged reviews"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        reviews = get_flagged_reviews()
        
        return Response({
            "count": reviews.count(),
            "reviews": [
                {
                    "id": r.id,
                    "user": r.user.email,
                    "course": r.course.title,
                    "rating": r.rating,
                    "comment": r.comment,
                    "created_at": r.created_at,
                }
                for r in reviews[:50]
            ],
        })


class RemoveReviewView(APIView):
    """Remove a flagged review"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, review_id):
        remove_review(review_id, admin_user=request.user)
        return Response({
            "status": "removed",
            "review_id": review_id,
        }, status=status.HTTP_204_NO_CONTENT)


class ApproveReviewView(APIView):
    """Approve a flagged review"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, review_id):
        review = approve_review(review_id, admin_user=request.user)
        return Response({
            "status": "approved",
            "review_id": review.id,
        })


# ==========================================
# PAYMENT & REVENUE MANAGEMENT
# ==========================================

class PaymentListView(APIView):
    """List all payments with filtering"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        filters = {}
        if request.query_params.get('status'):
            filters['status'] = request.query_params.get('status')
        if request.query_params.get('start_date'):
            filters['start_date'] = datetime.fromisoformat(request.query_params.get('start_date'))
        if request.query_params.get('end_date'):
            filters['end_date'] = datetime.fromisoformat(request.query_params.get('end_date'))
        
        payments = get_all_payments(filters=filters)
        
        return Response({
            "count": payments.count(),
            "payments": [
                {
                    "id": p.id,
                    "user": p.user.email,
                    "amount": float(p.amount),
                    "currency": p.currency,
                    "status": p.status,
                    "course": p.course.title if p.course else None,
                    "event": p.event.title if p.event else None,
                    "created_at": p.created_at,
                }
                for p in payments[:100]
            ],
        })


class RevenueStatsView(APIView):
    """Get revenue statistics"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            start_date = datetime.fromisoformat(start_date)
        if end_date:
            end_date = datetime.fromisoformat(end_date)
        
        return Response(get_revenue_stats(start_date=start_date, end_date=end_date))


class RefundPaymentView(APIView):
    """Process a payment refund"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, payment_id):
        reason = request.data.get('reason', '')
        refund = refund_payment(payment_id, reason=reason, admin_user=request.user)
        
        return Response({
            "status": "refunded",
            "payment_id": payment_id,
            "refund_id": refund.id,
            "amount": float(refund.amount),
        })


class PayoutListView(APIView):
    """List pending payouts"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        payouts = get_pending_payouts()
        
        return Response({
            "count": payouts.count(),
            "payouts": [
                {
                    "id": p.id,
                    "instructor": p.instructor.email,
                    "amount": float(p.amount),
                    "currency": p.currency,
                    "status": p.status,
                    "created_at": p.created_at,
                }
                for p in payouts
            ],
        })


class ApprovePayoutView(APIView):
    """Approve a payout"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, payout_id):
        payout = approve_payout(payout_id, admin_user=request.user)
        return Response({
            "status": "approved",
            "payout_id": payout.id,
            "processed_at": payout.processed_at,
        })


# ==========================================
# PLATFORM SETTINGS
# ==========================================

class PlatformSettingsView(APIView):
    """Get and update platform settings"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        settings = get_platform_settings()
        
        return Response({
            "settings": [
                {
                    "key": s.key,
                    "value": s.value,
                    "description": s.description,
                    "data_type": s.data_type,
                    "is_public": s.is_public,
                }
                for s in settings
            ],
        })

    def post(self, request):
        key = request.data.get('key')
        value = request.data.get('value')
        
        if not key or value is None:
            return Response(
                {"error": "Both 'key' and 'value' are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        setting = update_platform_setting(key, value, admin_user=request.user)
        
        return Response({
            "key": setting.key,
            "value": setting.value,
            "updated_at": setting.updated_at,
        })


# ==========================================
# SYSTEM ALERTS
# ==========================================

class SystemAlertListView(APIView):
    """List and create system alerts"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        alerts = SystemAlert.objects.all().order_by('-created_at')[:50]
        
        return Response({
            "alerts": [
                {
                    "id": a.id,
                    "title": a.title,
                    "message": a.message,
                    "alert_type": a.alert_type,
                    "is_active": a.is_active,
                    "start_time": a.start_time,
                    "end_time": a.end_time,
                }
                for a in alerts
            ],
        })

    def post(self, request):
        title = request.data.get('title')
        message = request.data.get('message')
        alert_type = request.data.get('alert_type', 'info')
        
        if not title or not message:
            return Response(
                {"error": "Both 'title' and 'message' are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        alert = create_system_alert(
            title=title,
            message=message,
            alert_type=alert_type,
            admin_user=request.user,
            target_roles=request.data.get('target_roles', []),
            end_time=request.data.get('end_time'),
        )
        
        return Response({
            "id": alert.id,
            "title": alert.title,
            "created_at": alert.created_at,
        }, status=status.HTTP_201_CREATED)


class SystemAlertDetailView(APIView):
    """Update or delete a system alert"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, alert_id):
        alert = get_object_or_404(SystemAlert, id=alert_id)
        
        if 'is_active' in request.data:
            alert.is_active = request.data['is_active']
        if 'end_time' in request.data:
            alert.end_time = request.data['end_time']
        
        alert.save()
        
        return Response({
            "id": alert.id,
            "is_active": alert.is_active,
        })

    def delete(self, request, alert_id):
        alert = get_object_or_404(SystemAlert, id=alert_id)
        alert.delete()
        
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# ACTIVITY LOG
# ==========================================

class AdminActivityLogView(APIView):
    """View admin activity log"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        limit = int(request.query_params.get('limit', 100))
        admin_user_id = request.query_params.get('admin_user_id')
        
        if admin_user_id:
            admin_user = get_object_or_404(User, id=admin_user_id)
            actions = get_admin_activity_log(admin_user=admin_user, limit=limit)
        else:
            actions = get_admin_activity_log(limit=limit)
        
        return Response({
            "count": actions.count(),
            "actions": [
                {
                    "id": a.id,
                    "admin": a.admin_user.email if a.admin_user else "System",
                    "action_type": a.get_action_type_display(),
                    "target_model": a.target_model,
                    "target_id": a.target_id,
                    "description": a.description,
                    "metadata": a.metadata,
                    "created_at": a.created_at,
                }
                for a in actions
            ],
        })

