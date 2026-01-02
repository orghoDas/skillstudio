from accounts.models import User
from courses.models import Course
from enrollments.models import Enrollment
from payments.models import Payment, Payout, Refund
from social.models import Review
from django.utils import timezone
from django.db.models import Sum


# user and instructor management
def get_all_users():
    return User.objects.all().order_by("-created_at")


def approve_instructor(user_id):
    user = User.objects.get(id=user_id)
    user.role = "instructor"
    user.save(update_fields=["role"])
    return user


def suspend_user(user_id):
    user = User.objects.get(id=user_id)
    user.is_active = False
    user.save(update_fields=["is_active"])
    return user


# course moderation
def get_pending_courses():
    return Course.objects.filter(status="pending")


def approve_course(course_id):
    course = Course.objects.get(id=course_id)
    course.status = "published"
    course.save(update_fields=["status"])
    return course


def reject_course(course_id, reason=None):
    course = Course.objects.get(id=course_id)
    course.status = "rejected"
    course.rejection_reason = reason
    course.save(update_fields=["status", "rejection_reason"])
    return course


# review and content moderation
def get_flagged_reviews():
    return Review.objects.filter(is_flagged=True)


def remove_review(review_id):
    Review.objects.filter(id=review_id).delete()


# platform analytics
def platform_stats():
    return {
        "total_courses": Course.objects.count(),
        "total_enrollments": Enrollment.objects.count(),
        "total_revenue": Payment.objects.filter(
            status="completed"
        ).aggregate(total=Sum("amount"))["total"],
    }


# payments, refunds and payouts
def get_all_payments():
    return Payment.objects.select_related("user", "course")


def refund_payment(payment_id, reason=None):
    payment = Payment.objects.get(id=payment_id)
    payment.status = "refunded"
    payment.save(update_fields=["status"])

    Refund.objects.create(
        payment=payment,
        amount=payment.amount,
        reason=reason,
        processed_at=timezone.now()
    )


def get_pending_payouts():
    return Payout.objects.filter(status="pending")

