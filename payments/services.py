"""
Payment Services

Payments architecture (AUDIT_REPORT.md Decision D-01):

    Stripe (test mode) --top-up--> student Wallet --pays for--> Course

* Money only enters the platform through a wallet top-up (the Stripe flow is
  not built yet; until then there is no way to add funds).
* Courses are only bought from the wallet, through ``purchase_course``. The
  price always comes from the course record; clients never send an amount.
* Every money movement is recorded as a ``Payment`` with a ``purpose`` and as
  ``WalletTransaction`` ledger rows.
"""

from collections import namedtuple
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Q, Count, F
from django.core.exceptions import ValidationError
import logging

from payments.models import (
    Payment, Payout, Refund, Coupon, CouponRedemption,
    PaymentGatewayConfig, PaymentWebhookLog, PaymentDispute
)
from accounts.models import User

logger = logging.getLogger(__name__)

# Constants
CENT = Decimal("0.01")
MIN_PAYOUT_AMOUNT = Decimal("10.00")


def to_money(value) -> Decimal:
    """Normalise any numeric value to a 2-decimal Decimal (half-up)."""
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def platform_fee_rate() -> Decimal:
    """The single platform fee rate used by every purchase (settings)."""
    return Decimal(str(settings.PLATFORM_FEE_RATE))


def split_platform_fee(amount):
    """Return (platform_fee, instructor_earnings) for a paid amount."""
    amount = to_money(amount)
    fee = to_money(amount * platform_fee_rate())
    return fee, amount - fee


# Kept for backwards compatibility with code that imported the old constant.
PLATFORM_FEE_RATE = platform_fee_rate()


# ==========================================
# PRICING & COUPONS
# ==========================================

PriceQuote = namedtuple("PriceQuote", "original_amount discount_amount final_amount coupon")


def calculate_coupon_discount(coupon, amount):
    """Discount a coupon gives on ``amount``; never more than ``amount``."""
    amount = to_money(amount)
    if coupon.discount_type == Coupon.PERCENT:
        discount = to_money(amount * coupon.discount_value / 100)
        if coupon.max_discount_amount:
            discount = min(discount, to_money(coupon.max_discount_amount))
    else:  # FIXED
        discount = to_money(coupon.discount_value)
    return max(Decimal("0.00"), min(discount, amount))


def validate_coupon_for_course(coupon_code, user, course, amount):
    """Return the Coupon if it may be applied to ``course`` at ``amount``.

    Raises ``ValidationError`` with a user-facing message otherwise.
    """
    code = (coupon_code or "").strip().upper()
    try:
        coupon = Coupon.objects.get(code=code)
    except Coupon.DoesNotExist:
        raise ValidationError("Invalid coupon code.")

    if not coupon.is_valid:
        raise ValidationError("This coupon is expired or inactive.")
    if not coupon.can_be_used_by(user):
        raise ValidationError("You have reached the usage limit for this coupon.")
    if coupon.min_order_amount and amount < coupon.min_order_amount:
        raise ValidationError(f"A minimum order of ${coupon.min_order_amount} is required for this coupon.")
    if coupon.applies_to == "specific" and not coupon.specific_courses.filter(id=course.id).exists():
        raise ValidationError("This coupon is not valid for this course.")
    if coupon.applies_to not in ("all", "courses", "specific"):
        raise ValidationError("This coupon is not valid for courses.")
    return coupon


def quote_course_price(user, course, coupon_code=None) -> PriceQuote:
    """Server-side price for ``user`` buying ``course`` (optionally with a coupon)."""
    original = Decimal("0.00") if course.is_free else to_money(course.price)
    if not coupon_code:
        return PriceQuote(original, Decimal("0.00"), original, None)
    if original <= 0:
        raise ValidationError("This course is free; no coupon is needed.")
    coupon = validate_coupon_for_course(coupon_code, user, course, original)
    discount = calculate_coupon_discount(coupon, original)
    return PriceQuote(original, discount, original - discount, coupon)


def record_coupon_redemption(coupon, user, discount_amount, payment=None):
    """Record a redemption and bump usage atomically (no lost updates)."""
    CouponRedemption.objects.create(
        coupon=coupon, user=user, payment=payment, discount_amount=discount_amount
    )
    Coupon.objects.filter(pk=coupon.pk).update(current_usage=F("current_usage") + 1)


# ==========================================
# COURSE PURCHASE (wallet)
# ==========================================

class PurchaseError(Exception):
    """A purchase was refused for a reason the user should see."""

    def __init__(self, message, code):
        super().__init__(message)
        self.message = message
        self.code = code


PurchaseResult = namedtuple("PurchaseResult", "enrollment outcome payment charged_amount")

OUTCOME_CREATED = "created"
OUTCOME_REACTIVATED = "reactivated"
OUTCOME_ALREADY_ENROLLED = "already_enrolled"


def _lock_wallets(*users):
    """Get-or-create and row-lock the users' wallets in a stable (pk) order.

    Locking the buyer's wallet serialises all purchases by the same user, which
    makes double-clicks and retries safe. A stable order avoids deadlocks when
    two users buy each other's courses at the same moment.
    """
    from students.models import Wallet

    wallet_ids = {}
    for user in users:
        wallet, _ = Wallet.objects.get_or_create(user=user)
        wallet_ids[user.pk] = wallet.pk
    locked = {
        w.pk: w
        for w in Wallet.objects.select_for_update().filter(pk__in=wallet_ids.values()).order_by("pk")
    }
    return [locked[wallet_ids[user.pk]] for user in users]


@transaction.atomic
def purchase_course(user, course_id, coupon_code=None) -> PurchaseResult:
    """Enroll ``user`` in a course, charging their wallet if the course is paid.

    Idempotent per (user, course): if the user already owns the course
    (active or completed enrollment) nothing is charged and the existing
    enrollment is returned. A canceled enrollment that was paid for before is
    reactivated for free.
    """
    from courses.models import Course
    from enrollments.constants import ACCESS_STATUSES
    from enrollments.models import Enrollment

    try:
        course = Course.objects.select_related("instructor").get(id=course_id, status="published")
    except Course.DoesNotExist:
        raise PurchaseError("Course not found or not published.", "course_unavailable")

    if course.instructor_id == user.id:
        raise PurchaseError("You can't enroll in your own course.", "own_course")

    buyer_wallet, instructor_wallet = _lock_wallets(user, course.instructor)

    enrollment = Enrollment.objects.select_for_update().filter(user=user, course=course).first()
    if enrollment and enrollment.status in ACCESS_STATUSES:
        return PurchaseResult(enrollment, OUTCOME_ALREADY_ENROLLED, None, Decimal("0.00"))

    try:
        quote = quote_course_price(user, course, coupon_code)
    except ValidationError as exc:
        raise PurchaseError(exc.messages[0], "invalid_coupon")

    previously_paid = enrollment is not None and Payment.objects.filter(
        user=user, course=course,
        purpose=Payment.PURPOSE_COURSE_PURCHASE, status="completed",
    ).exists()

    payment = None
    charged = Decimal("0.00")
    if quote.final_amount > 0 and not previously_paid:
        if buyer_wallet.balance < quote.final_amount:
            raise PurchaseError("Insufficient balance", "insufficient_balance")

        buyer_wallet.deduct_money(quote.final_amount, description=f"Course purchase: {course.title}")
        fee, earnings = split_platform_fee(quote.final_amount)
        if earnings > 0:
            instructor_wallet.add_money(earnings, description=f"Course sale: {course.title}")

        payment = Payment.objects.create(
            purpose=Payment.PURPOSE_COURSE_PURCHASE,
            user=user,
            instructor=course.instructor,
            course=course,
            amount=quote.final_amount,
            original_amount=quote.original_amount,
            discount_amount=quote.discount_amount,
            platform_fee=fee,
            instructor_earnings=earnings,
            currency="USD",
            payment_method="wallet",
            provider="wallet",
            coupon=quote.coupon,
            status="completed",
            completed_at=timezone.now(),
            billing_email=user.email,
        )
        charged = quote.final_amount

    if quote.coupon and not previously_paid:
        record_coupon_redemption(quote.coupon, user, quote.discount_amount, payment)

    if enrollment is None:
        enrollment = Enrollment.objects.create(user=user, course=course, status="active")
        outcome = OUTCOME_CREATED
    else:  # canceled -> reactivate
        enrollment.status = "active"
        enrollment.is_completed = False
        enrollment.completed_at = None
        enrollment.save(update_fields=["status", "is_completed", "completed_at"])
        outcome = OUTCOME_REACTIVATED

    logger.info(
        "Course purchase: user=%s course=%s outcome=%s charged=%s payment=%s",
        user.pk, course.pk, outcome, charged, getattr(payment, "pk", None),
    )
    return PurchaseResult(enrollment, outcome, payment, charged)


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
    ).select_related('course')


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
    """Get comprehensive payment statistics.

    Revenue figures cover course purchases only: a wallet top-up moves the
    student's own money into their wallet and is not platform revenue.
    """
    queryset = Payment.objects.filter(purpose=Payment.PURPOSE_COURSE_PURCHASE)

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
