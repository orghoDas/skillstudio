from decimal import Decimal
from django.utils import timezone
from django.db import transaction

from payments.models import Payment, Payout, Refund

PLATFORM_FEE_RATE = Decimal("0.20")  # 20%


@transaction.atomic
def finalize_course_payment(payment: Payment):
    """
    Marks payment as completed and calculates earnings.
    """
    course = payment.course
    instructor = course.instructor

    platform_fee = (payment.amount * PLATFORM_FEE_RATE).quantize(Decimal("0.01"))
    instructor_earnings = payment.amount - platform_fee

    payment.instructor = instructor
    payment.platform_fee = platform_fee
    payment.instructor_earnings = instructor_earnings
    payment.status = "completed"

    payment.save(update_fields=[
        "instructor",
        "platform_fee",
        "instructor_earnings",
        "status",
    ])

    return payment


@transaction.atomic
def refund_payment(payment: Payment, reason=""):
    """
    Fully refunds a completed payment.
    """
    if payment.status != "completed":
        raise ValueError("Only completed payments can be refunded.")

    Refund.objects.create(
        payment=payment,
        amount=payment.amount,
        reason=reason,
        status="processed",
        processed_at=timezone.now(),
    )

    payment.status = "refunded"
    payment.platform_fee = Decimal("0")
    payment.instructor_earnings = Decimal("0")

    payment.save(update_fields=[
        "status",
        "platform_fee",
        "instructor_earnings",
    ])

    return payment


def get_unpaid_payments_for_instructor(instructor):
    """
    Payments eligible for payout.
    """
    return Payment.objects.filter(
        instructor=instructor,
        status="completed",
        payouts__isnull=True,
    )


@transaction.atomic
def create_payout(instructor):
    """
    Creates payout from unpaid payments.
    """
    payments = get_unpaid_payments_for_instructor(instructor)

    if not payments.exists():
        return None

    total_amount = sum(
        (p.instructor_earnings for p in payments),
        Decimal("0.00"),
    )

    payout = Payout.objects.create(
        instructor=instructor,
        amount=total_amount,
        status="pending",
    )

    payout.payments.add(*payments)

    return payout