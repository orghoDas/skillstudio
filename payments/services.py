"""
Payment Services
Comprehensive business logic for payment processing, refunds, payouts, and coupons
"""

from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Q, Count
from django.core.exceptions import ValidationError
from typing import Optional, Dict, Any
import logging

from payments.models import (
    Payment, Payout, Refund, Coupon, CouponRedemption,
    PaymentGatewayConfig, PaymentWebhookLog, PaymentDispute
)
from accounts.models import User

logger = logging.getLogger(__name__)

# Constants
PLATFORM_FEE_RATE = Decimal("0.20")  # 20%
MIN_PAYOUT_AMOUNT = Decimal("10.00")


# ==========================================
# PAYMENT PROCESSING
# ==========================================

@transaction.atomic
def create_payment(
    user,
    amount,
    course=None,
    event=None,
    payment_method="stripe",
    coupon_code=None,
    billing_email=None,
    billing_address=None,
    ip_address=None,
    **kwargs
):
    """Create a new payment transaction"""
    if not course and not event:
        raise ValidationError("Payment must be for either a course or event")
    
    original_amount = amount
    discount_amount = Decimal('0.00')
    coupon = None
    
    # Apply coupon if provided
    if coupon_code:
        coupon = validate_and_apply_coupon(
            coupon_code=coupon_code,
            user=user,
            amount=amount,
            course=course,
            event=event
        )
        if coupon:
            discount_amount = calculate_coupon_discount(coupon, amount)
            amount = amount - discount_amount
    
    # Create payment
    payment = Payment.objects.create(
        user=user,
        course=course,
        event=event,
        amount=amount,
        original_amount=original_amount,
        discount_amount=discount_amount,
        payment_method=payment_method,
        coupon=coupon,
        billing_email=billing_email or user.email,
        billing_address=billing_address or {},
        ip_address=ip_address,
        status='pending',
        **kwargs
    )
    
    logger.info(f"Payment created: {payment.id} for {user.email} - Amount: {amount}")
    return payment


def calculate_coupon_discount(coupon, amount):
    """Calculate discount amount from coupon"""
    if coupon.discount_type == Coupon.PERCENT:
        discount = (amount * coupon.discount_value / 100).quantize(Decimal('0.01'))
        if coupon.max_discount_amount:
            discount = min(discount, coupon.max_discount_amount)
    else:  # FIXED
        discount = min(coupon.discount_value, amount)
    
    return discount


def validate_and_apply_coupon(
    coupon_code,
    user,
    amount,
    course=None,
    event=None
):
    """Validate coupon and check if it can be applied"""
    try:
        coupon = Coupon.objects.get(code=coupon_code)
    except Coupon.DoesNotExist:
        raise ValidationError(f"Invalid coupon code: {coupon_code}")
    
    if not coupon.is_valid:
        raise ValidationError("Coupon is expired or inactive")
    
    if not coupon.can_be_used_by(user):
        raise ValidationError("You have exceeded the usage limit for this coupon")
    
    if coupon.min_order_amount and amount < coupon.min_order_amount:
        raise ValidationError(
            f"Minimum order amount ${coupon.min_order_amount} required"
        )
    
    if coupon.applies_to == 'courses' and not course:
        raise ValidationError("This coupon is only valid for courses")
    
    if coupon.applies_to == 'events' and not event:
        raise ValidationError("This coupon is only valid for events")
    
    if coupon.applies_to == 'specific':
        if course and not coupon.specific_courses.filter(id=course.id).exists():
            raise ValidationError("This coupon is not valid for this course")
        if event and not coupon.specific_events.filter(id=event.id).exists():
            raise ValidationError("This coupon is not valid for this event")
    
    return coupon


@transaction.atomic
def process_payment_success(
    payment,
    provider_id,
    metadata=None
):
    """Mark payment as successful and calculate earnings"""
    if payment.status != 'pending':
        logger.warning(f"Attempting to complete non-pending payment {payment.id}")
        return payment
    
    # Determine instructor
    instructor = payment.course.instructor if payment.course else payment.event.instructor
    
    # Calculate fees
    platform_fee = (payment.amount * PLATFORM_FEE_RATE).quantize(Decimal("0.01"))
    instructor_earnings = payment.amount - platform_fee
    
    # Update payment
    payment.instructor = instructor
    payment.platform_fee = platform_fee
    payment.instructor_earnings = instructor_earnings
    payment.status = 'completed'
    payment.provider_id = provider_id
    payment.completed_at = timezone.now()
    
    if metadata:
        payment.metadata.update(metadata)
    
    payment.save(update_fields=[
        'instructor', 'platform_fee', 'instructor_earnings',
        'status', 'provider_id', 'completed_at', 'metadata', 'updated_at'
    ])
    
    # Record coupon redemption
    if payment.coupon:
        CouponRedemption.objects.create(
            coupon=payment.coupon,
            user=payment.user,
            payment=payment,
            discount_amount=payment.discount_amount
        )
        payment.coupon.current_usage += 1
        payment.coupon.save(update_fields=['current_usage'])
    
    logger.info(f"Payment completed: {payment.id}")
    return payment


@transaction.atomic
def process_payment_failure(payment, reason, metadata=None):
    """Mark payment as failed"""
    payment.status = 'failed'
    payment.failure_reason = reason
    
    if metadata:
        payment.metadata.update(metadata)
    
    payment.save(update_fields=['status', 'failure_reason', 'metadata', 'updated_at'])
    
    logger.warning(f"Payment failed: {payment.id} - Reason: {reason}")
    return payment


def get_payment_by_provider_id(provider, provider_id):
    """Get payment by provider ID"""
    try:
        return Payment.objects.get(provider=provider, provider_id=provider_id)
    except Payment.DoesNotExist:
        return None


# ==========================================
# REFUND MANAGEMENT
# ==========================================

@transaction.atomic
def request_refund(payment, amount, reason, user, refund_type='full'):
    """Create a refund request"""
    if not payment.can_be_refunded:
        raise ValidationError(f"Payment cannot be refunded. Status: {payment.status}")
    
    if amount > payment.amount:
        raise ValidationError("Refund amount cannot exceed payment amount")
    
    if refund_type == 'full' and amount != payment.amount:
        raise ValidationError("Full refund must equal payment amount")
    
    refund = Refund.objects.create(
        payment=payment,
        requested_by=user,
        amount=amount,
        reason=reason,
        refund_type=refund_type,
        status='requested'
    )
    
    logger.info(f"Refund requested: {refund.id} for payment {payment.id}")
    return refund


@transaction.atomic
def approve_refund(refund, admin_user, notes=None):
    """Approve a refund request"""
    if refund.status != 'requested':
        raise ValidationError(f"Cannot approve refund with status: {refund.status}")
    
    refund.status = 'approved'
    refund.processed_by = admin_user
    refund.admin_notes = notes or ''
    refund.save(update_fields=['status', 'processed_by', 'admin_notes', 'updated_at'])
    
    payment = refund.payment
    if refund.refund_type == 'full':
        payment.status = 'refunded'
    else:
        payment.status = 'partially_refunded'
    payment.save(update_fields=['status', 'updated_at'])
    
    logger.info(f"Refund approved: {refund.id}")
    return refund


@transaction.atomic
def reject_refund(refund, admin_user, reason):
    """Reject a refund request"""
    if refund.status != 'requested':
        raise ValidationError(f"Cannot reject refund with status: {refund.status}")
    
    refund.status = 'rejected'
    refund.processed_by = admin_user
    refund.rejection_reason = reason
    refund.processed_at = timezone.now()
    refund.save(update_fields=[
        'status', 'processed_by', 'rejection_reason',
        'processed_at', 'updated_at'
    ])
    
    logger.info(f"Refund rejected: {refund.id}")
    return refund


@transaction.atomic
def process_refund(refund, provider_refund_id, admin_user=None):
    """Mark refund as processed"""
    refund.status = 'processed'
    refund.provider_refund_id = provider_refund_id
    refund.processed_at = timezone.now()
    
    if admin_user:
        refund.processed_by = admin_user
    
    refund.save(update_fields=[
        'status', 'provider_refund_id', 'processed_at',
        'processed_by', 'updated_at'
    ])
    
    payment = refund.payment
    payment.platform_fee = Decimal('0.00')
    payment.instructor_earnings = Decimal('0.00')
    payment.save(update_fields=['platform_fee', 'instructor_earnings', 'updated_at'])
    
    logger.info(f"Refund processed: {refund.id}")
    return refund


def get_pending_refunds():
    """Get all pending refund requests"""
    return Refund.objects.filter(status='requested').select_related(
        'payment', 'payment__user', 'requested_by'
    ).order_by('-requested_at')


# ==========================================
# PAYOUT MANAGEMENT
# ==========================================

def get_unpaid_payments_for_instructor(instructor):
    """Get payments eligible for payout"""
    return Payment.objects.filter(
        instructor=instructor,
        status='completed',
        payouts__isnull=True,
    ).select_related('course', 'event')


def calculate_instructor_balance(instructor):
    """Calculate instructor's current balance"""
    total_earnings = Payment.objects.filter(
        instructor=instructor,
        status='completed'
    ).aggregate(
        total=Sum('instructor_earnings')
    )['total'] or Decimal('0.00')
    
    paid_out = Payout.objects.filter(
        instructor=instructor,
        status__in=['paid', 'processing']
    ).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    pending = Payout.objects.filter(
        instructor=instructor,
        status='pending'
    ).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    available = total_earnings - paid_out - pending
    
    return {
        'total_earnings': total_earnings,
        'paid_out': paid_out,
        'pending': pending,
        'available': available
    }


@transaction.atomic
def create_payout(instructor, amount=None, payout_method='stripe_connect', account_details=None):
    """Create payout from unpaid payments"""
    balance = calculate_instructor_balance(instructor)
    
    if not amount:
        amount = balance['available']
    
    if amount < MIN_PAYOUT_AMOUNT:
        raise ValidationError(f"Minimum payout amount is ${MIN_PAYOUT_AMOUNT}")
    
    if amount > balance['available']:
        raise ValidationError(f"Insufficient balance. Available: ${balance['available']}")
    
    payments = get_unpaid_payments_for_instructor(instructor)
    
    if not payments.exists():
        raise ValidationError("No eligible payments for payout")
    
    payout = Payout.objects.create(
        instructor=instructor,
        amount=amount,
        payout_method=payout_method,
        account_details=account_details or {},
        status='pending'
    )
    
    total = Decimal('0.00')
    for payment in payments:
        if total >= amount:
            break
        payout.payments.add(payment)
        total += payment.instructor_earnings
    
    logger.info(f"Payout created: {payout.id} for {instructor.email}")
    return payout


@transaction.atomic
def approve_payout(payout, admin_user=None, notes=None):
    """Approve and mark payout as processing"""
    if payout.status != 'pending':
        raise ValidationError(f"Cannot approve payout with status: {payout.status}")
    
    payout.status = 'processing'
    payout.admin_notes = notes or ''
    payout.save(update_fields=['status', 'admin_notes', 'updated_at'])
    
    logger.info(f"Payout approved: {payout.id}")
    return payout


@transaction.atomic
def complete_payout(payout, transaction_id, metadata=None):
    """Mark payout as completed"""
    payout.status = 'paid'
    payout.transaction_id = transaction_id
    payout.processed_at = timezone.now()
    
    if metadata:
        payout.provider_details.update(metadata)
    
    payout.save(update_fields=[
        'status', 'transaction_id', 'processed_at',
        'provider_details', 'updated_at'
    ])
    
    logger.info(f"Payout completed: {payout.id}")
    return payout


@transaction.atomic
def fail_payout(payout, reason):
    """Mark payout as failed"""
    payout.status = 'failed'
    payout.failure_reason = reason
    payout.save(update_fields=['status', 'failure_reason', 'updated_at'])
    
    logger.warning(f"Payout failed: {payout.id}")
    return payout


def get_pending_payouts():
    """Get all pending payouts"""
    return Payout.objects.filter(status='pending').select_related(
        'instructor'
    ).order_by('-created_at')


# ==========================================
# COUPON MANAGEMENT
# ==========================================

@transaction.atomic
def create_coupon(code, discount_type, discount_value, created_by, **kwargs):
    """Create a new coupon"""
    code = code.upper().strip()
    
    if Coupon.objects.filter(code=code).exists():
        raise ValidationError(f"Coupon code '{code}' already exists")
    
    coupon = Coupon.objects.create(
        code=code,
        discount_type=discount_type,
        discount_value=discount_value,
        created_by=created_by,
        **kwargs
    )
    
    logger.info(f"Coupon created: {coupon.code}")
    return coupon


def deactivate_coupon(coupon_id):
    """Deactivate a coupon"""
    coupon = Coupon.objects.get(id=coupon_id)
    coupon.is_active = False
    coupon.save(update_fields=['is_active', 'updated_at'])
    
    logger.info(f"Coupon deactivated: {coupon.code}")
    return coupon


def get_active_coupons():
    """Get all active coupons"""
    return Coupon.objects.filter(
        is_active=True
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    ).order_by('-created_at')


def get_coupon_usage_stats(coupon):
    """Get usage statistics for a coupon"""
    redemptions = CouponRedemption.objects.filter(coupon=coupon)
    
    total_discount = redemptions.aggregate(
        total=Sum('discount_amount')
    )['total'] or Decimal('0.00')
    
    unique_users = redemptions.values('user').distinct().count()
    
    return {
        'total_redemptions': redemptions.count(),
        'unique_users': unique_users,
        'total_discount_given': total_discount,
        'current_usage': coupon.current_usage,
        'usage_limit': coupon.usage_limit,
        'is_valid': coupon.is_valid
    }


# ==========================================
# PAYMENT ANALYTICS
# ==========================================

def get_payment_stats(start_date=None, end_date=None):
    """Get comprehensive payment statistics"""
    queryset = Payment.objects.all()
    
    if start_date:
        queryset = queryset.filter(created_at__gte=start_date)
    if end_date:
        queryset = queryset.filter(created_at__lte=end_date)
    
    stats = queryset.aggregate(
        total_revenue=Sum('amount', filter=Q(status='completed')),
        total_refunded=Sum('amount', filter=Q(status='refunded')),
        total_platform_fees=Sum('platform_fee', filter=Q(status='completed')),
        total_instructor_earnings=Sum('instructor_earnings', filter=Q(status='completed')),
        total_transactions=Count('id'),
        completed_transactions=Count('id', filter=Q(status='completed')),
        failed_transactions=Count('id', filter=Q(status='failed')),
    )
    
    if stats['total_transactions'] > 0:
        stats['success_rate'] = (
            stats['completed_transactions'] / stats['total_transactions'] * 100
        )
    else:
        stats['success_rate'] = 0
    
    stats['by_payment_method'] = list(
        queryset.filter(status='completed')
        .values('payment_method')
        .annotate(
            count=Count('id'),
            total=Sum('amount')
        )
    )
    
    return stats


def get_instructor_earnings(instructor, start_date=None, end_date=None):
    """Get instructor earnings statistics"""
    queryset = Payment.objects.filter(instructor=instructor, status='completed')
    
    if start_date:
        queryset = queryset.filter(created_at__gte=start_date)
    if end_date:
        queryset = queryset.filter(created_at__lte=end_date)
    
    stats = queryset.aggregate(
        total_earnings=Sum('instructor_earnings'),
        total_sales=Sum('amount'),
        total_transactions=Count('id')
    )
    
    balance = calculate_instructor_balance(instructor)
    
    return {
        **stats,
        **balance,
        'average_transaction': (
            stats['total_sales'] / stats['total_transactions']
            if stats['total_transactions'] > 0 else Decimal('0.00')
        )
    }


# ==========================================
# WEBHOOK PROCESSING
# ==========================================

@transaction.atomic
def log_webhook_event(gateway, event_type, event_id, payload, payment=None):
    """Log webhook event"""
    webhook_log = PaymentWebhookLog.objects.create(
        gateway=gateway,
        event_type=event_type,
        event_id=event_id,
        payload=payload,
        payment=payment
    )
    
    logger.info(f"Webhook logged: {gateway} - {event_type}")
    return webhook_log


@transaction.atomic
def mark_webhook_processed(webhook_log, error=None):
    """Mark webhook as processed"""
    webhook_log.processed = True
    webhook_log.processed_at = timezone.now()
    
    if error:
        webhook_log.processing_error = error
    
    webhook_log.save(update_fields=[
        'processed', 'processed_at', 'processing_error'
    ])


# ==========================================
# DISPUTE MANAGEMENT
# ==========================================

@transaction.atomic
def create_dispute(payment, dispute_id, amount, reason):
    """Create a payment dispute"""
    dispute = PaymentDispute.objects.create(
        payment=payment,
        dispute_id=dispute_id,
        amount=amount,
        currency=payment.currency,
        reason=reason,
        status='opened'
    )
    
    payment.status = 'disputed'
    payment.save(update_fields=['status', 'updated_at'])
    
    logger.warning(f"Dispute created: {dispute.dispute_id}")
    return dispute


@transaction.atomic
def resolve_dispute(dispute, status, notes=None):
    """Resolve a payment dispute"""
    dispute.status = status
    dispute.closed_at = timezone.now()
    dispute.admin_notes = notes or ''
    dispute.save(update_fields=['status', 'closed_at', 'admin_notes', 'updated_at'])
    
    logger.info(f"Dispute resolved: {dispute.dispute_id} - Status: {status}")
    return dispute
