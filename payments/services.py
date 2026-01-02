from decimal import Decimal
from django.db import transaction

from payments.models import Payment, Payout

PLATFORM_FEE_RATE = Decimal("0.20") 

def finalize_course_payment(payment: Payment):
    course = payment.course
    instructor = course.instructor

    platform_fee = payment.amount * PLATFORM_FEE_RATE
    instructor_earnings = payment.amount - platform_fee

    payment.instructor = instructor
    payment.platform_fee = platform_fee
    payment.instructor_earnings = instructor_earnings
    payment.status = "completed"

    payment.save(update_fields=[
        "instructor",
        "platform_fee",
        "instructor_earnings",
        "status"
    ])



def refund_payment(payment: Payment):
    payment.status = "refunded"
    payment.platform_fee = Decimal("0.00")
    payment.instructor_earnings = Decimal("0.00")

    payment.save(update_fields=[
        "status",
        "platform_fee",
        "instructor_earnings"
    ])



@transaction.atomic
def create_payout_for_instructor(instructor):
    payments = get_unpaid_payments_for_instructor(instructor)

    if not payments.exists():
        return None

    total_amount = sum(p.instructor_earnings for p in payments)

    payout = Payout.objects.create(
        instructor=instructor,
        amount=total_amount,
        status="pending"
    )

    payments.update(payout=payout)

    return payout


def get_unpaid_payments_for_instructor(instructor):
    return Payment.objects.filter(
        instructor=instructor,
        status="completed",
        payout__isnull=True
    )

