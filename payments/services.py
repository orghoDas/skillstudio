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
    PaymentWebhookLog, PaymentDispute
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

class PaymentsError(Exception):
    """A money action was refused for a reason the user should see.

    ``message`` is safe to show to users; ``code`` is a stable machine-readable
    reason. Views return them as ``{"detail": message, "code": code}``.
    """

    def __init__(self, message, code):
        super().__init__(message)
        self.message = message
        self.code = code


class PurchaseError(PaymentsError):
    """A purchase was refused for a reason the user should see."""


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

    # A fully refunded purchase no longer counts as paid (status "refunded").
    previously_paid = enrollment is not None and Payment.objects.filter(
        user=user, course=course,
        purpose=Payment.PURPOSE_COURSE_PURCHASE,
        status__in=("completed", "partially_refunded"),
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
# REFUNDS (course purchases -> student wallet)
# ==========================================
#
# Decision D-01 / PAY-08: a course purchase was paid from the wallet, so a
# refund puts the money back into the student's wallet and takes the
# instructor's pro-rata share back out of the instructor's wallet. The platform
# fee part is simply not re-credited to anyone (it was never in a wallet).

class RefundError(PaymentsError):
    """A refund request/decision was refused for a reason the user should see."""


REFUNDABLE_PAYMENT_STATUSES = ("completed", "partially_refunded")
OPEN_REFUND_STATUSES = ("requested",)


def _refunded_total(payment):
    return payment.refunds.filter(status="processed").aggregate(t=Sum("amount"))["t"] or Decimal("0.00")


def refundable_amount(payment) -> Decimal:
    """How much of ``payment`` can still be refunded."""
    if payment.status not in REFUNDABLE_PAYMENT_STATUSES:
        return Decimal("0.00")
    return max(Decimal("0.00"), payment.amount - _refunded_total(payment))


@transaction.atomic
def request_refund(user, payment_id, reason, amount=None):
    """Student asks for (part of) a course purchase back.

    ``amount`` defaults to everything still refundable. Only one open request
    per payment at a time; cumulative refunds can never exceed the payment.
    """
    try:
        payment = Payment.objects.select_for_update().get(pk=payment_id, user=user)
    except Payment.DoesNotExist:
        raise RefundError("Payment not found.", "not_found")

    if payment.purpose != Payment.PURPOSE_COURSE_PURCHASE:
        raise RefundError("Only course purchases can be refunded.", "not_refundable")
    if payment.status not in REFUNDABLE_PAYMENT_STATUSES:
        raise RefundError(f"This payment cannot be refunded (status: {payment.status}).", "not_refundable")
    if payment.refunds.filter(status__in=OPEN_REFUND_STATUSES).exists():
        raise RefundError("There is already an open refund request for this payment.", "refund_already_requested")

    remaining = refundable_amount(payment)
    amount = remaining if amount is None else to_money(amount)
    if amount <= 0:
        raise RefundError("Refund amount must be greater than zero.", "invalid_amount")
    if amount > remaining:
        raise RefundError(f"Refund amount cannot exceed the refundable ${remaining}.", "invalid_amount")

    refund = Refund.objects.create(
        payment=payment,
        requested_by=user,
        amount=amount,
        reason=reason,
        refund_type="full" if amount == payment.amount else "partial",
        status="requested",
    )
    logger.info("Refund requested: refund=%s payment=%s amount=%s", refund.pk, payment.pk, amount)
    return refund


def _instructor_share(payment, refund_amount, remaining_after):
    """Instructor's pro-rata share of a refund, exact to the cent overall."""
    already = payment.refunds.filter(status="processed").aggregate(t=Sum("instructor_debit"))["t"] or Decimal("0.00")
    if remaining_after == 0:
        # Final refund: take back exactly what is left so rounding never drifts.
        return max(Decimal("0.00"), payment.instructor_earnings - already)
    if payment.amount <= 0:
        return Decimal("0.00")
    share = to_money(refund_amount * payment.instructor_earnings / payment.amount)
    return min(share, max(Decimal("0.00"), payment.instructor_earnings - already))


@transaction.atomic
def approve_refund(refund_id, admin_user, notes="", absorb_shortfall=False):
    """Admin approves a refund: money moves immediately (wallet to wallet).

    If the instructor's wallet can't cover their share (e.g. it was already
    paid out), approval is refused unless ``absorb_shortfall`` is set, in which
    case the instructor is debited what they have and the platform absorbs the
    rest (recorded on the refund).
    """
    from enrollments.models import Enrollment

    try:
        refund = Refund.objects.select_for_update().select_related("payment").get(pk=refund_id)
    except Refund.DoesNotExist:
        raise RefundError("Refund not found.", "not_found")
    if refund.status != "requested":
        raise RefundError(f"Cannot approve a refund with status '{refund.status}'.", "invalid_state")

    payment = Payment.objects.select_for_update().select_related("user", "instructor", "course").get(pk=refund.payment_id)
    remaining = refundable_amount(payment)
    if refund.amount > remaining:
        raise RefundError(f"Refund exceeds the refundable ${remaining}.", "invalid_amount")
    remaining_after = remaining - refund.amount

    share = _instructor_share(payment, refund.amount, remaining_after)
    student_wallet, instructor_wallet = _lock_wallets(payment.user, payment.instructor)
    instructor_debit = share
    absorbed = Decimal("0.00")
    if instructor_wallet.balance < share:
        if not absorb_shortfall:
            raise RefundError(
                f"The instructor's wallet (${instructor_wallet.balance}) can't cover their "
                f"${share} share. Approve with absorb_shortfall to let the platform cover it.",
                "instructor_balance_insufficient",
            )
        instructor_debit = instructor_wallet.balance
        absorbed = share - instructor_debit

    title = payment.course.title if payment.course else f"payment #{payment.pk}"
    student_wallet.add_money(refund.amount, description=f"Refund #{refund.pk}: {title}")
    if instructor_debit > 0:
        instructor_wallet.deduct_money(instructor_debit, description=f"Refund #{refund.pk} reversal: {title}")

    now = timezone.now()
    refund.status = "processed"
    refund.processed_by = admin_user
    refund.processed_at = now
    refund.admin_notes = notes or ""
    refund.instructor_debit = instructor_debit
    refund.platform_absorbed = absorbed
    refund.save(update_fields=[
        "status", "processed_by", "processed_at", "admin_notes",
        "instructor_debit", "platform_absorbed", "updated_at",
    ])

    payment.status = "refunded" if remaining_after == 0 else "partially_refunded"
    payment.save(update_fields=["status", "updated_at"])

    if remaining_after == 0 and payment.course_id:
        # Full refund revokes access. (Certificate revocation: see CRT-01.)
        Enrollment.objects.filter(
            user=payment.user, course_id=payment.course_id, status__in=("active", "completed")
        ).update(status="canceled")

    logger.info(
        "Refund processed: refund=%s payment=%s amount=%s instructor_debit=%s absorbed=%s",
        refund.pk, payment.pk, refund.amount, instructor_debit, absorbed,
    )
    return refund


@transaction.atomic
def reject_refund(refund_id, admin_user, reason):
    """Admin rejects a refund request. No money moves."""
    try:
        refund = Refund.objects.select_for_update().get(pk=refund_id)
    except Refund.DoesNotExist:
        raise RefundError("Refund not found.", "not_found")
    if refund.status != "requested":
        raise RefundError(f"Cannot reject a refund with status '{refund.status}'.", "invalid_state")

    refund.status = "rejected"
    refund.processed_by = admin_user
    refund.rejection_reason = reason or "No reason provided"
    refund.processed_at = timezone.now()
    refund.save(update_fields=["status", "processed_by", "rejection_reason", "processed_at", "updated_at"])
    logger.info("Refund rejected: %s", refund.pk)
    return refund


def get_pending_refunds():
    """Get all pending refund requests"""
    return Refund.objects.filter(status='requested').select_related(
        'payment', 'payment__user', 'requested_by'
    ).order_by('-requested_at')


# ==========================================
# PAYOUTS (instructor wallet -> outside world)
# ==========================================
#
# PAY-07 / PAY-06: the instructor's wallet is the single source of truth for
# withdrawable money. Requesting a payout immediately debits (reserves) the
# amount from the wallet, so the same money can't be requested twice or spent
# elsewhere. Rejected/failed/cancelled payouts credit it back.
# Payment.instructor_earnings is an immutable reporting snapshot only.

class PayoutError(PaymentsError):
    """A payout action was refused for a reason the user should see."""


OPEN_PAYOUT_STATUSES = ("pending", "processing")


def calculate_instructor_balance(instructor):
    """Instructor money summary, all derived from the wallet ledger + payouts."""
    from students.models import Wallet

    wallet, _ = Wallet.objects.get_or_create(user=instructor)
    payouts = Payout.objects.filter(instructor=instructor)
    gross = Payment.objects.filter(
        instructor=instructor,
        purpose=Payment.PURPOSE_COURSE_PURCHASE,
        status__in=("completed", "partially_refunded", "refunded"),
    ).aggregate(t=Sum("instructor_earnings"))["t"] or Decimal("0.00")
    reversed_by_refunds = Refund.objects.filter(
        payment__instructor=instructor, status="processed"
    ).aggregate(t=Sum("instructor_debit"))["t"] or Decimal("0.00")

    return {
        "total_earnings": gross - reversed_by_refunds,
        "paid_out": payouts.filter(status="paid").aggregate(t=Sum("amount"))["t"] or Decimal("0.00"),
        "pending": payouts.filter(status__in=OPEN_PAYOUT_STATUSES, wallet_debited=True)
                          .aggregate(t=Sum("amount"))["t"] or Decimal("0.00"),
        "available": wallet.balance,
    }


def _reserve_payout_funds(payout):
    """Debit the payout amount from the instructor's wallet (caller holds locks)."""
    (wallet,) = _lock_wallets(payout.instructor)
    if wallet.balance < payout.amount:
        raise PayoutError(
            f"Insufficient wallet balance. Available: ${wallet.balance}", "insufficient_balance"
        )
    wallet.deduct_money(payout.amount, description=f"Payout #{payout.pk} (reserved)")
    payout.wallet_debited = True


def _release_payout_funds(payout):
    """Credit a reserved payout amount back to the instructor's wallet."""
    if payout.wallet_debited:
        (wallet,) = _lock_wallets(payout.instructor)
        wallet.add_money(payout.amount, description=f"Payout #{payout.pk} returned")
        payout.wallet_debited = False


def _locked_payout(payout_id):
    try:
        return Payout.objects.select_for_update().select_related("instructor").get(pk=payout_id)
    except Payout.DoesNotExist:
        raise PayoutError("Payout not found.", "not_found")


@transaction.atomic
def create_payout(instructor, amount=None, payout_method="stripe_connect", account_details=None):
    """Instructor requests a payout; the amount is reserved from their wallet now."""
    (wallet,) = _lock_wallets(instructor)
    amount = wallet.balance if amount is None else to_money(amount)
    if amount < MIN_PAYOUT_AMOUNT:
        raise PayoutError(f"Minimum payout amount is ${MIN_PAYOUT_AMOUNT}.", "below_minimum")
    if amount > wallet.balance:
        raise PayoutError(f"Insufficient wallet balance. Available: ${wallet.balance}", "insufficient_balance")

    payout = Payout.objects.create(
        instructor=instructor,
        amount=amount,
        payout_method=payout_method,
        account_details=account_details or {},
        status="pending",
    )
    _reserve_payout_funds(payout)
    payout.save(update_fields=["wallet_debited", "updated_at"])
    logger.info("Payout requested: payout=%s instructor=%s amount=%s", payout.pk, instructor.pk, amount)
    return payout


request_payout = create_payout  # clearer name for new callers


@transaction.atomic
def approve_payout(payout_id, admin_user=None, notes=None):
    """Admin approves a pending payout (pending -> processing)."""
    payout = _locked_payout(payout_id)
    if payout.status != "pending":
        raise PayoutError(f"Cannot approve a payout with status '{payout.status}'.", "invalid_state")
    if not payout.wallet_debited:  # legacy request made before the wallet ledger
        _reserve_payout_funds(payout)
    payout.status = "processing"
    payout.admin_notes = notes or payout.admin_notes
    payout.save(update_fields=["status", "admin_notes", "wallet_debited", "updated_at"])
    logger.info("Payout approved: %s", payout.pk)
    return payout


@transaction.atomic
def complete_payout(payout_id, transaction_id, admin_user=None, metadata=None):
    """Admin records that the money was sent (processing -> paid)."""
    if not transaction_id:
        raise PayoutError("A transaction id is required.", "invalid_request")
    payout = _locked_payout(payout_id)
    if payout.status != "processing":
        raise PayoutError(f"Only approved (processing) payouts can be completed, not '{payout.status}'.", "invalid_state")
    if not payout.wallet_debited:
        _reserve_payout_funds(payout)
    payout.status = "paid"
    payout.transaction_id = transaction_id
    payout.processed_at = timezone.now()
    if metadata:
        payout.provider_details.update(metadata)
    payout.save(update_fields=[
        "status", "transaction_id", "processed_at", "provider_details", "wallet_debited", "updated_at",
    ])
    logger.info("Payout completed: %s", payout.pk)
    return payout


def _close_payout(payout_id, new_status, reason, allowed_from):
    payout = _locked_payout(payout_id)
    if payout.status not in allowed_from:
        raise PayoutError(f"Cannot change a payout with status '{payout.status}'.", "invalid_state")
    _release_payout_funds(payout)
    payout.status = new_status
    payout.failure_reason = reason or ""
    payout.processed_at = timezone.now()
    payout.save(update_fields=["status", "failure_reason", "processed_at", "wallet_debited", "updated_at"])
    logger.info("Payout %s: %s", new_status, payout.pk)
    return payout


@transaction.atomic
def reject_payout(payout_id, admin_user=None, reason=""):
    """Admin rejects a payout; the reserved amount returns to the wallet."""
    return _close_payout(payout_id, "cancelled", reason or "Rejected by admin", OPEN_PAYOUT_STATUSES)


@transaction.atomic
def fail_payout(payout_id, reason):
    """The transfer failed; the reserved amount returns to the wallet."""
    return _close_payout(payout_id, "failed", reason, OPEN_PAYOUT_STATUSES)


@transaction.atomic
def cancel_payout(payout_id, instructor):
    """Instructor withdraws their own still-pending request."""
    payout = _locked_payout(payout_id)
    if payout.instructor_id != instructor.pk:
        raise PayoutError("Payout not found.", "not_found")
    return _close_payout(payout_id, "cancelled", "Cancelled by instructor", ("pending",))


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
    """Instructor earnings: all-time wallet-ledger balance + sales in a date range.

    ``total_earnings``/``paid_out``/``pending``/``available`` are all-time
    (see calculate_instructor_balance); ``period_*`` cover start/end dates.
    """
    queryset = Payment.objects.filter(
        instructor=instructor,
        purpose=Payment.PURPOSE_COURSE_PURCHASE,
        status__in=('completed', 'partially_refunded'),
    )

    if start_date:
        queryset = queryset.filter(created_at__gte=start_date)
    if end_date:
        queryset = queryset.filter(created_at__lte=end_date)

    stats = queryset.aggregate(
        period_earnings=Sum('instructor_earnings'),
        period_sales=Sum('amount'),
        period_transactions=Count('id')
    )

    return {
        **calculate_instructor_balance(instructor),
        **stats,
        'average_transaction': (
            stats['period_sales'] / stats['period_transactions']
            if stats['period_transactions'] else Decimal('0.00')
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
