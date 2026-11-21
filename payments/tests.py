"""
Payments tests.

Architecture under test (AUDIT_REPORT.md Decision D-01):
    Stripe (test mode) -> wallet top-up -> wallet pays for courses.
Courses are bought only through payments.services.purchase_course (exposed as
POST /api/enrollments/enroll/). There is no card "create payment" route and no
way for a student to credit their own wallet.
"""

import importlib
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.apps import apps as django_apps
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from certificates.models import Certificate
from courses.models import Category, Course, Lesson, Module
from enrollments.models import Enrollment
from enrollments.services import evaluate_and_complete_enrollment, mark_lesson_completed
from payments import serializers as payment_serializers
from payments import services
from payments.models import Coupon, CouponRedemption, Payment, Payout, Refund
from students.models import Wallet, WalletTransaction


def make_user(email, role="student"):
    return User.objects.create_user(email=email, password="testpass123", role=role)


class PaymentsFixtureMixin:
    """Shared users, courses and wallets."""

    def setUp(self):
        super().setUp()
        self.student = make_user("student@test.com")
        self.instructor = make_user("instructor@test.com", role="instructor")
        self.admin = User.objects.create_superuser(email="admin@test.com", password="testpass123")
        self.category = Category.objects.create(name="Tech", slug="tech")
        self.course = Course.objects.create(
            title="Paid Course", instructor=self.instructor, category=self.category,
            status="published", price=Decimal("100.00"), is_free=False,
        )
        self.free_course = Course.objects.create(
            title="Free Course", instructor=self.instructor, category=self.category,
            status="published", price=Decimal("0.00"), is_free=True,
        )
        self.draft_course = Course.objects.create(
            title="Draft Course", instructor=self.instructor, category=self.category,
            status="draft", price=Decimal("50.00"),
        )
        self.wallet = Wallet.objects.create(user=self.student, balance=Decimal("150.00"))

    def balance(self, user):
        return Wallet.objects.get(user=user).balance

    def make_coupon(self, code="SAVE10", **kwargs):
        defaults = dict(discount_type=Coupon.PERCENT, discount_value=Decimal("10"), created_by=self.admin)
        defaults.update(kwargs)
        return Coupon.objects.create(code=code, **defaults)


# ==========================================
# SMOKE: every payments serializer builds
# ==========================================

class SerializerSmokeTests(TestCase):
    def test_every_payments_serializer_builds_its_fields(self):
        """Guards against stale field names (e.g. the removed `specific_events`)."""
        from rest_framework import serializers as drf

        for name in dir(payment_serializers):
            cls = getattr(payment_serializers, name)
            if isinstance(cls, type) and issubclass(cls, drf.BaseSerializer) and cls.__module__ == payment_serializers.__name__:
                with self.subTest(serializer=name):
                    cls().fields  # raises ImproperlyConfigured on a bad field


# ==========================================
# PRICING & COUPONS
# ==========================================

class PricingTests(PaymentsFixtureMixin, TestCase):
    def test_quote_uses_server_price(self):
        quote = services.quote_course_price(self.student, self.course)
        self.assertEqual(quote, (Decimal("100.00"), Decimal("0.00"), Decimal("100.00"), None))

    def test_free_course_quotes_zero(self):
        self.assertEqual(services.quote_course_price(self.student, self.free_course).final_amount, Decimal("0.00"))

    def test_percent_coupon_respects_max_discount(self):
        self.make_coupon("HALF", discount_value=Decimal("50"), max_discount_amount=Decimal("20.00"))
        quote = services.quote_course_price(self.student, self.course, "half")  # case-insensitive
        self.assertEqual(quote.discount_amount, Decimal("20.00"))
        self.assertEqual(quote.final_amount, Decimal("80.00"))

    def test_fixed_coupon_never_exceeds_price(self):
        self.make_coupon("BIG", discount_type=Coupon.FIXED, discount_value=Decimal("500.00"))
        quote = services.quote_course_price(self.student, self.course, "BIG")
        self.assertEqual(quote.discount_amount, Decimal("100.00"))
        self.assertEqual(quote.final_amount, Decimal("0.00"))

    def test_invalid_expired_and_wrong_course_coupons_are_rejected(self):
        from django.core.exceptions import ValidationError

        self.make_coupon("OLD", expires_at=timezone.now() - timedelta(days=1))
        specific = self.make_coupon("ONLYFREE", applies_to="specific")
        specific.specific_courses.set([self.free_course])
        self.make_coupon("MIN", min_order_amount=Decimal("500.00"))
        for code in ("NOPE", "OLD", "ONLYFREE", "MIN"):
            with self.subTest(code=code), self.assertRaises(ValidationError):
                services.quote_course_price(self.student, self.course, code)

    def test_coupon_on_free_course_is_rejected(self):
        from django.core.exceptions import ValidationError

        self.make_coupon()
        with self.assertRaises(ValidationError):
            services.quote_course_price(self.student, self.free_course, "SAVE10")


# ==========================================
# PURCHASE SERVICE
# ==========================================

class PurchaseCourseTests(PaymentsFixtureMixin, TestCase):
    def test_paid_purchase_moves_money_and_records_payment(self):
        result = services.purchase_course(self.student, self.course.id)

        self.assertEqual(result.outcome, services.OUTCOME_CREATED)
        self.assertEqual(result.charged_amount, Decimal("100.00"))
        self.assertEqual(self.balance(self.student), Decimal("50.00"))
        self.assertEqual(self.balance(self.instructor), Decimal("90.00"))  # 10% platform fee

        payment = result.payment
        self.assertEqual(payment.purpose, Payment.PURPOSE_COURSE_PURCHASE)
        self.assertEqual(payment.payment_method, "wallet")
        self.assertEqual(payment.status, "completed")
        self.assertEqual((payment.amount, payment.platform_fee, payment.instructor_earnings),
                         (Decimal("100.00"), Decimal("10.00"), Decimal("90.00")))
        self.assertTrue(Enrollment.objects.filter(user=self.student, course=self.course, status="active").exists())

    def test_repurchase_of_owned_course_charges_nothing(self):
        services.purchase_course(self.student, self.course.id)
        second = services.purchase_course(self.student, self.course.id)

        self.assertEqual(second.outcome, services.OUTCOME_ALREADY_ENROLLED)
        self.assertIsNone(second.payment)
        self.assertEqual(self.balance(self.student), Decimal("50.00"))
        self.assertEqual(Payment.objects.filter(user=self.student).count(), 1)
        self.assertEqual(WalletTransaction.objects.filter(wallet__user=self.student, transaction_type="debit").count(), 1)

    def test_completed_course_is_never_charged_again(self):
        Enrollment.objects.create(user=self.student, course=self.course, status="completed", is_completed=True)
        result = services.purchase_course(self.student, self.course.id)
        self.assertEqual(result.outcome, services.OUTCOME_ALREADY_ENROLLED)
        self.assertEqual(self.balance(self.student), Decimal("150.00"))

    def test_canceled_paid_enrollment_reactivates_for_free(self):
        services.purchase_course(self.student, self.course.id)
        Enrollment.objects.filter(user=self.student, course=self.course).update(status="canceled")

        result = services.purchase_course(self.student, self.course.id)

        self.assertEqual(result.outcome, services.OUTCOME_REACTIVATED)
        self.assertEqual(result.charged_amount, Decimal("0.00"))
        self.assertEqual(self.balance(self.student), Decimal("50.00"))
        self.assertEqual(result.enrollment.status, "active")

    def test_canceled_never_paid_enrollment_is_charged_on_reactivation(self):
        Enrollment.objects.create(user=self.student, course=self.course, status="canceled")
        result = services.purchase_course(self.student, self.course.id)
        self.assertEqual(result.outcome, services.OUTCOME_REACTIVATED)
        self.assertEqual(result.charged_amount, Decimal("100.00"))

    def test_free_course_creates_enrollment_without_payment(self):
        result = services.purchase_course(self.student, self.free_course.id)
        self.assertEqual(result.outcome, services.OUTCOME_CREATED)
        self.assertIsNone(result.payment)
        self.assertEqual(self.balance(self.student), Decimal("150.00"))

    def test_insufficient_balance_changes_nothing(self):
        self.wallet.balance = Decimal("10.00")
        self.wallet.save()
        with self.assertRaises(services.PurchaseError) as ctx:
            services.purchase_course(self.student, self.course.id)
        self.assertEqual(ctx.exception.code, "insufficient_balance")
        self.assertEqual(self.balance(self.student), Decimal("10.00"))
        self.assertFalse(Enrollment.objects.filter(user=self.student, course=self.course).exists())
        self.assertFalse(Payment.objects.exists())

    def test_instructor_cannot_buy_own_course(self):
        Wallet.objects.create(user=self.instructor, balance=Decimal("500.00"))
        with self.assertRaises(services.PurchaseError) as ctx:
            services.purchase_course(self.instructor, self.course.id)
        self.assertEqual(ctx.exception.code, "own_course")

    def test_unpublished_course_cannot_be_bought(self):
        with self.assertRaises(services.PurchaseError) as ctx:
            services.purchase_course(self.student, self.draft_course.id)
        self.assertEqual(ctx.exception.code, "course_unavailable")

    def test_coupon_discount_is_charged_and_redeemed_once(self):
        coupon = self.make_coupon("SAVE10", discount_value=Decimal("10"))
        result = services.purchase_course(self.student, self.course.id, coupon_code="save10")

        self.assertEqual(result.charged_amount, Decimal("90.00"))
        self.assertEqual(result.payment.discount_amount, Decimal("10.00"))
        self.assertEqual(result.payment.coupon, coupon)
        self.assertEqual(self.balance(self.instructor), Decimal("81.00"))  # 90 - 10% fee
        coupon.refresh_from_db()
        self.assertEqual(coupon.current_usage, 1)
        self.assertEqual(CouponRedemption.objects.filter(coupon=coupon, user=self.student).count(), 1)

        # Re-enrolling must not redeem the coupon again.
        services.purchase_course(self.student, self.course.id, coupon_code="SAVE10")
        coupon.refresh_from_db()
        self.assertEqual(coupon.current_usage, 1)

    def test_full_discount_coupon_enrolls_without_payment_row(self):
        coupon = self.make_coupon("FREE100", discount_value=Decimal("100"))
        result = services.purchase_course(self.student, self.course.id, coupon_code="FREE100")
        self.assertEqual(result.charged_amount, Decimal("0.00"))
        self.assertIsNone(result.payment)
        self.assertEqual(self.balance(self.student), Decimal("150.00"))
        self.assertEqual(CouponRedemption.objects.filter(coupon=coupon).count(), 1)

    def test_invalid_coupon_blocks_purchase(self):
        with self.assertRaises(services.PurchaseError) as ctx:
            services.purchase_course(self.student, self.course.id, coupon_code="NOPE")
        self.assertEqual(ctx.exception.code, "invalid_coupon")
        self.assertEqual(self.balance(self.student), Decimal("150.00"))

    @override_settings(PLATFORM_FEE_RATE=Decimal("0.25"))
    def test_platform_fee_comes_from_settings(self):
        result = services.purchase_course(self.student, self.course.id)
        self.assertEqual(result.payment.platform_fee, Decimal("25.00"))
        self.assertEqual(self.balance(self.instructor), Decimal("75.00"))


# ==========================================
# API
# ==========================================

class EnrollAPITests(PaymentsFixtureMixin, APITestCase):
    url = "/api/enrollments/enroll/"

    def test_enroll_twice_charges_once(self):
        self.client.force_authenticate(self.student)
        first = self.client.post(self.url, {"course_id": self.course.id}, format="json")
        second = self.client.post(self.url, {"course_id": self.course.id}, format="json")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first.data["outcome"], "created")
        self.assertEqual(first.data["charged_amount"], "100.00")
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.data["outcome"], "already_enrolled")
        self.assertFalse(second.data["was_reactivated"])
        self.assertEqual(self.balance(self.student), Decimal("50.00"))

    def test_client_cannot_set_the_price(self):
        self.client.force_authenticate(self.student)
        response = self.client.post(self.url, {"course_id": self.course.id, "amount": "0.01", "price": "0.01"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Payment.objects.get(user=self.student).amount, Decimal("100.00"))

    def test_insufficient_balance_returns_code(self):
        self.wallet.balance = Decimal("1.00")
        self.wallet.save()
        self.client.force_authenticate(self.student)
        response = self.client.post(self.url, {"course_id": self.course.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"detail": "Insufficient balance", "code": "insufficient_balance"})


class RemovedAndLockedEndpointTests(PaymentsFixtureMixin, APITestCase):
    def test_card_payment_create_route_is_gone(self):
        self.client.force_authenticate(self.student)
        response = self.client.post("/api/payments/create/", {"course_id": self.course.id, "amount": "0.01"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Payment.objects.exists())

    def test_students_cannot_credit_their_own_wallet(self):
        self.client.force_authenticate(self.student)
        response = self.client.post("/api/students/wallet/", {"amount": "1000"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.balance(self.student), Decimal("150.00"))

    def test_forged_stripe_webhook_is_rejected(self):
        pending = Payment.objects.create(
            purpose=Payment.PURPOSE_WALLET_TOPUP, user=self.student, amount=Decimal("500.00"),
            original_amount=Decimal("500.00"), provider="stripe", provider_id="pi_forged", status="pending",
        )
        response = self.client.post(
            "/api/payments/webhooks/stripe/",
            {"id": "evt_1", "type": "payment_intent.succeeded", "data": {"object": {"id": "pi_forged"}}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        pending.refresh_from_db()
        self.assertEqual(pending.status, "pending")
        self.assertEqual(self.balance(self.student), Decimal("150.00"))

    def test_paypal_webhook_route_is_gone(self):
        response = self.client.post("/api/payments/webhooks/paypal/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CouponAPITests(PaymentsFixtureMixin, APITestCase):
    def test_coupon_domain_validation_preserves_field_messages(self):
        self.client.force_authenticate(self.admin)
        error = ValidationError({"discount_value": ["Discount is too large."]})
        with patch("payments.views.services.create_coupon", side_effect=error):
            response = self.client.post("/api/payments/coupons/create/", {
                "code": "LIMIT", "discount_type": "fixed", "discount_value": "5.00",
            }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {
            "detail": "Invalid input.",
            "code": "validation_error",
            "fields": {"discount_value": ["Discount is too large."]},
        })

    def test_unexpected_coupon_failure_logs_the_exception_and_rolls_back(self):
        self.client.force_authenticate(self.admin)

        def fail_after_write(**kwargs):
            self.make_coupon(kwargs["code"])
            raise TypeError("Internal coupon failure")

        with (
            patch("payments.views.services.create_coupon", side_effect=fail_after_write),
            self.assertLogs("core.api_exceptions", level="ERROR") as logs,
        ):
            response = self.client.post("/api/payments/coupons/create/", {
                "code": "ROLLBACK", "discount_type": "fixed", "discount_value": "5.00",
            }, format="json")
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {
            "detail": "An unexpected server error occurred.",
            "code": "internal_error",
        })
        self.assertIn("TypeError: Internal coupon failure", logs.output[0])
        self.assertFalse(Coupon.objects.filter(code="ROLLBACK").exists())

    def test_students_only_see_public_active_coupons(self):
        self.make_coupon("PUBLIC10", is_public=True)
        self.make_coupon("SECRET50")
        self.make_coupon("OLDPUBLIC", is_public=True, is_active=False)
        self.client.force_authenticate(self.student)
        response = self.client.get("/api/payments/coupons/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([c["code"] for c in response.data], ["PUBLIC10"])
        self.assertNotIn("usage_stats", response.data[0])

    def test_admin_sees_all_coupons(self):
        self.make_coupon("PUBLIC10", is_public=True)
        self.make_coupon("SECRET50")
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/payments/coupons/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({c["code"] for c in response.data}, {"PUBLIC10", "SECRET50"})

    def test_validate_quotes_server_price_and_ignores_client_amount(self):
        self.make_coupon("SAVE10")
        self.client.force_authenticate(self.student)
        response = self.client.post(
            "/api/payments/coupons/validate/",
            {"code": "SAVE10", "course_id": self.course.id, "amount": "1.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            (response.data["original_amount"], response.data["discount_amount"], response.data["final_amount"]),
            ("100.00", "10.00", "90.00"),
        )

    def test_validate_rejects_bad_code(self):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            "/api/payments/coupons/validate/", {"code": "NOPE", "course_id": self.course.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["valid"])

    def test_admin_creates_course_specific_coupon(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post("/api/payments/coupons/create/", {
            "code": "only-this", "discount_type": "fixed", "discount_value": "5.00",
            "applies_to": "specific", "specific_course_ids": [self.course.id], "is_public": True,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        coupon = Coupon.objects.get(code="ONLY-THIS")
        self.assertEqual(list(coupon.specific_courses.all()), [self.course])
        self.assertTrue(coupon.is_public)

    def test_students_cannot_create_coupons(self):
        self.client.force_authenticate(self.student)
        response = self.client.post("/api/payments/coupons/create/", {
            "code": "HACK", "discount_type": "percent", "discount_value": "100",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PaymentHistoryAndStatsTests(PaymentsFixtureMixin, APITestCase):
    def test_history_lists_own_payments_with_purpose_and_filters(self):
        services.purchase_course(self.student, self.course.id)
        Payment.objects.create(
            purpose=Payment.PURPOSE_WALLET_TOPUP, user=self.student, amount=Decimal("20.00"),
            original_amount=Decimal("20.00"), status="pending",
        )
        other = make_user("other@test.com")
        Payment.objects.create(user=other, amount=Decimal("5.00"), original_amount=Decimal("5.00"))

        self.client.force_authenticate(self.student)
        response = self.client.get("/api/payments/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({p["purpose"] for p in response.data}, {"course_purchase", "wallet_topup"})
        completed = self.client.get("/api/payments/?status=completed")
        self.assertEqual([p["course_slug"] for p in completed.data], [self.course.slug])

    def test_revenue_stats_exclude_wallet_topups(self):
        services.purchase_course(self.student, self.course.id)
        Payment.objects.create(
            purpose=Payment.PURPOSE_WALLET_TOPUP, user=self.student, amount=Decimal("500.00"),
            original_amount=Decimal("500.00"), status="completed",
        )
        stats = services.get_payment_stats()
        self.assertEqual(stats["total_revenue"], Decimal("100.00"))
        self.assertEqual(stats["total_platform_fees"], Decimal("10.00"))


class PayoutTests(PaymentsFixtureMixin, APITestCase):
    """PAY-06 / PAY-07: payouts come out of the instructor wallet and are reserved at request."""

    def setUp(self):
        super().setUp()
        services.purchase_course(self.student, self.course.id)  # instructor wallet: 90.00

    def test_request_reserves_funds_from_wallet(self):
        payout = services.create_payout(self.instructor, amount=Decimal("50.00"))
        self.assertTrue(payout.wallet_debited)
        self.assertEqual(payout.status, "pending")
        self.assertEqual(self.balance(self.instructor), Decimal("40.00"))
        self.assertEqual(
            services.calculate_instructor_balance(self.instructor),
            {"total_earnings": Decimal("90.00"), "paid_out": Decimal("0.00"),
             "pending": Decimal("50.00"), "available": Decimal("40.00")},
        )

    def test_earnings_cannot_be_withdrawn_twice(self):
        """The old double-dip: wallet credit + Payment earnings both withdrawable."""
        services.create_payout(self.instructor, amount=Decimal("90.00"))
        with self.assertRaises(services.PayoutError) as ctx:
            services.create_payout(self.instructor, amount=Decimal("10.00"))
        self.assertEqual(ctx.exception.code, "insufficient_balance")

    def test_pending_requests_cannot_exceed_balance(self):
        services.create_payout(self.instructor, amount=Decimal("60.00"))
        with self.assertRaises(services.PayoutError):
            services.create_payout(self.instructor, amount=Decimal("60.00"))
        self.assertEqual(Payout.objects.filter(instructor=self.instructor).count(), 1)

    def test_minimum_and_default_amount(self):
        with self.assertRaises(services.PayoutError) as ctx:
            services.create_payout(self.instructor, amount=Decimal("5.00"))
        self.assertEqual(ctx.exception.code, "below_minimum")
        payout = services.create_payout(self.instructor)  # defaults to the whole balance
        self.assertEqual(payout.amount, Decimal("90.00"))
        self.assertEqual(self.balance(self.instructor), Decimal("0.00"))

    def test_full_lifecycle_approve_complete(self):
        payout = services.create_payout(self.instructor, amount=Decimal("50.00"))
        with self.assertRaises(services.PayoutError):
            services.complete_payout(payout.id, "TXN-1", self.admin)  # must be approved first
        services.approve_payout(payout.id, self.admin)
        with self.assertRaises(services.PayoutError):
            services.complete_payout(payout.id, "", self.admin)  # transaction id required
        paid = services.complete_payout(payout.id, "TXN-1", self.admin)
        self.assertEqual((paid.status, paid.transaction_id), ("paid", "TXN-1"))
        self.assertEqual(self.balance(self.instructor), Decimal("40.00"))
        self.assertEqual(services.calculate_instructor_balance(self.instructor)["paid_out"], Decimal("50.00"))

    def test_reject_returns_reserved_funds(self):
        payout = services.create_payout(self.instructor, amount=Decimal("50.00"))
        services.approve_payout(payout.id, self.admin)
        rejected = services.reject_payout(payout.id, self.admin, "Bank details invalid")
        self.assertEqual((rejected.status, rejected.wallet_debited), ("cancelled", False))
        self.assertEqual(self.balance(self.instructor), Decimal("90.00"))
        with self.assertRaises(services.PayoutError):
            services.reject_payout(payout.id, self.admin)  # can't release twice

    def test_instructor_can_cancel_only_own_pending_payout(self):
        payout = services.create_payout(self.instructor, amount=Decimal("50.00"))
        other = make_user("other-instructor@test.com", role="instructor")
        with self.assertRaises(services.PayoutError) as ctx:
            services.cancel_payout(payout.id, other)
        self.assertEqual(ctx.exception.code, "not_found")
        services.cancel_payout(payout.id, self.instructor)
        self.assertEqual(self.balance(self.instructor), Decimal("90.00"))

        approved = services.create_payout(self.instructor, amount=Decimal("20.00"))
        services.approve_payout(approved.id, self.admin)
        with self.assertRaises(services.PayoutError):
            services.cancel_payout(approved.id, self.instructor)

    def test_legacy_undebited_payout_reserves_on_approval(self):
        legacy = Payout.objects.create(instructor=self.instructor, amount=Decimal("30.00"), status="pending")
        services.approve_payout(legacy.id, self.admin)
        legacy.refresh_from_db()
        self.assertTrue(legacy.wallet_debited)
        self.assertEqual(self.balance(self.instructor), Decimal("60.00"))

        too_big = Payout.objects.create(instructor=self.instructor, amount=Decimal("500.00"), status="pending")
        with self.assertRaises(services.PayoutError) as ctx:
            services.approve_payout(too_big.id, self.admin)
        self.assertEqual(ctx.exception.code, "insufficient_balance")

    def test_payout_api_permissions_and_errors(self):
        self.client.force_authenticate(self.instructor)
        created = self.client.post("/api/payments/payouts/request/", {"amount": "50.00"}, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        payout_id = created.data["id"]
        too_much = self.client.post("/api/payments/payouts/request/", {"amount": "500.00"}, format="json")
        self.assertEqual(too_much.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(too_much.data["code"], "insufficient_balance")
        listing = self.client.get("/api/payments/payouts/")
        self.assertEqual([p["id"] for p in listing.data], [payout_id])
        self.assertEqual(listing.data[0]["instructor_name"], self.instructor.email)
        self.assertEqual(
            self.client.post(f"/api/payments/payouts/{payout_id}/approve/").status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.client.force_authenticate(self.student)
        self.assertEqual(
            self.client.post("/api/payments/payouts/request/", {"amount": "10.00"}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(f"/api/payments/payouts/{payout_id}/approve/").status_code, 200)
        done = self.client.post(f"/api/payments/payouts/{payout_id}/complete/", {"transaction_id": "TX9"}, format="json")
        self.assertEqual((done.status_code, done.data["status"]), (200, "paid"))
        missing = self.client.post("/api/payments/payouts/999999/reject/")
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)

    def test_instructor_can_read_own_wallet(self):
        self.client.force_authenticate(self.instructor)
        response = self.client.get("/api/students/wallet/", {"user": self.student.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data["balance"]), Decimal("90.00"))
        transactions = self.client.get("/api/students/wallet/transactions/", {"user": self.student.pk})
        self.assertEqual(transactions.status_code, status.HTTP_200_OK)
        self.assertEqual(transactions.data["count"], 1)
        self.assertEqual(transactions.data["results"][0]["transaction_type"], "credit")
        self.assertEqual(Decimal(transactions.data["results"][0]["amount"]), Decimal("90.00"))

    @override_settings(PAYOUT_DETAILS_ENCRYPTION_KEY=Fernet.generate_key().decode())
    def test_payout_destinations_are_encrypted_and_responses_are_masked(self):
        details = {"iban": "TEST-DESTINATION-1234", "account_holder": "Private Name"}
        self.client.force_authenticate(self.instructor)
        created = self.client.post(
            "/api/payments/payouts/request/",
            {"amount": "10.00", "payout_method": "bank_transfer", "account_details": details},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertEqual(created.data["account_details"], {"provided": True})
        payout = Payout.objects.get(pk=created.data["id"])
        self.assertTrue(payout.account_details_encrypted)
        self.assertNotIn(details["iban"], payout.account_details_encrypted)
        self.assertEqual(payout.get_account_details(), details)

        self.client.force_authenticate(self.admin)
        listed = self.client.get("/api/payments/payouts/")
        approved = self.client.post(f"/api/payments/payouts/{payout.pk}/approve/")
        self.assertEqual(listed.data[0]["account_details"], {"provided": True})
        self.assertEqual(approved.data["account_details"], {"provided": True})

        self.client.force_login(self.admin)
        admin_page = self.client.get(reverse("admin:payments_payout_change", args=[payout.pk]), secure=True)
        self.assertContains(admin_page, "Payout destination on file")
        self.assertNotContains(admin_page, details["iban"])
        self.assertNotContains(admin_page, details["account_holder"])
        self.assertNotContains(admin_page, payout.account_details_encrypted)

    @override_settings(PAYOUT_DETAILS_ENCRYPTION_KEY="")
    def test_payout_details_without_key_do_not_reserve_funds(self):
        self.client.force_authenticate(self.instructor)
        response = self.client.post(
            "/api/payments/payouts/request/",
            {"amount": "10.00", "account_details": {"iban": "TEST-DESTINATION-1234"}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["code"], "payout_details_unavailable")
        self.assertEqual(self.balance(self.instructor), Decimal("90.00"))
        self.assertFalse(Payout.objects.filter(instructor=self.instructor).exists())

    def test_old_instructor_payout_routes_are_gone(self):
        self.client.force_authenticate(self.instructor)
        self.assertEqual(self.client.get("/api/instructors/payouts/").status_code, status.HTTP_404_NOT_FOUND)


class RefundTests(PaymentsFixtureMixin, APITestCase):
    """PAY-08: refunds of course purchases go back to the student's wallet."""

    def setUp(self):
        super().setUp()
        self.payment = services.purchase_course(self.student, self.course.id).payment  # student 50, instructor 90

    def test_full_refund_moves_money_back_and_revokes_access(self):
        enrollment = Enrollment.objects.get(user=self.student, course=self.course)
        module = Module.objects.create(course=self.course, title="Module")
        lesson = Lesson.objects.create(module=module, title="Required lesson")
        mark_lesson_completed(enrollment, lesson)
        self.assertTrue(evaluate_and_complete_enrollment(enrollment.pk))
        certificate = Certificate.objects.get(enrollment=enrollment)
        verification_code = certificate.verification_code

        refund = services.request_refund(self.student, self.payment.id, "Not for me")
        self.assertEqual((refund.amount, refund.refund_type), (Decimal("100.00"), "full"))
        services.approve_refund(refund.id, self.admin)

        refund.refresh_from_db(); self.payment.refresh_from_db()
        self.assertEqual((refund.status, refund.instructor_debit), ("processed", Decimal("90.00")))
        self.assertEqual(self.payment.status, "refunded")
        self.assertEqual(self.balance(self.student), Decimal("150.00"))
        self.assertEqual(self.balance(self.instructor), Decimal("0.00"))
        self.assertEqual(Enrollment.objects.get(user=self.student, course=self.course).status, "canceled")
        self.assertEqual(services.calculate_instructor_balance(self.instructor)["total_earnings"], Decimal("0.00"))
        certificate.refresh_from_db()
        self.assertIsNotNone(certificate.revoked_at)
        self.assertEqual(self.client.get(f"/api/certificates/verify/{verification_code}/").status_code, 410)

        result = services.purchase_course(self.student, self.course.pk)
        self.assertEqual(result.enrollment.status, "completed")
        certificate.refresh_from_db()
        self.assertIsNone(certificate.revoked_at)
        self.assertNotEqual(certificate.verification_code, verification_code)

    def test_rebuying_after_full_refund_charges_again(self):
        refund = services.request_refund(self.student, self.payment.id, "Changed my mind")
        services.approve_refund(refund.id, self.admin)
        result = services.purchase_course(self.student, self.course.id)
        self.assertEqual((result.outcome, result.charged_amount), (services.OUTCOME_REACTIVATED, Decimal("100.00")))

    def test_partial_refunds_never_exceed_payment_and_split_exactly(self):
        cheap = Course.objects.create(
            title="Odd Price", instructor=self.instructor, category=self.category,
            status="published", price=Decimal("99.99"),
        )
        Wallet.objects.filter(user=self.student).update(balance=Decimal("200.00"))
        payment = services.purchase_course(self.student, cheap.id).payment
        self.assertEqual(payment.instructor_earnings, Decimal("89.99"))

        first = services.request_refund(self.student, payment.id, "partial", amount=Decimal("33.33"))
        services.approve_refund(first.id, self.admin)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "partially_refunded")
        self.assertEqual(services.refundable_amount(payment), Decimal("66.66"))
        self.assertEqual(Enrollment.objects.get(user=self.student, course=cheap).status, "active")

        with self.assertRaises(services.RefundError) as ctx:
            services.request_refund(self.student, payment.id, "too much", amount=Decimal("66.67"))
        self.assertEqual(ctx.exception.code, "invalid_amount")

        rest = services.request_refund(self.student, payment.id, "the rest")  # defaults to remaining
        self.assertEqual(rest.amount, Decimal("66.66"))
        services.approve_refund(rest.id, self.admin)
        payment.refresh_from_db()
        total_debit = sum(r.instructor_debit for r in payment.refunds.all())
        self.assertEqual(total_debit, payment.instructor_earnings)  # cent-exact, no rounding drift
        self.assertEqual(payment.status, "refunded")

    def test_only_one_open_request_and_only_own_course_purchases(self):
        services.request_refund(self.student, self.payment.id, "first")
        with self.assertRaises(services.RefundError) as ctx:
            services.request_refund(self.student, self.payment.id, "second")
        self.assertEqual(ctx.exception.code, "refund_already_requested")

        other = make_user("someone@test.com")
        with self.assertRaises(services.RefundError) as ctx:
            services.request_refund(other, self.payment.id, "not mine")
        self.assertEqual(ctx.exception.code, "not_found")

        topup = Payment.objects.create(
            purpose=Payment.PURPOSE_WALLET_TOPUP, user=self.student, amount=Decimal("20.00"),
            original_amount=Decimal("20.00"), status="completed",
        )
        with self.assertRaises(services.RefundError) as ctx:
            services.request_refund(self.student, topup.id, "top-up")
        self.assertEqual(ctx.exception.code, "not_refundable")

    def test_instructor_shortfall_needs_explicit_absorb(self):
        services.create_payout(self.instructor, amount=Decimal("80.00"))  # instructor wallet: 10.00
        refund = services.request_refund(self.student, self.payment.id, "refund please")
        with self.assertRaises(services.RefundError) as ctx:
            services.approve_refund(refund.id, self.admin)
        self.assertEqual(ctx.exception.code, "instructor_balance_insufficient")
        self.assertEqual(self.balance(self.student), Decimal("50.00"))  # nothing moved

        services.approve_refund(refund.id, self.admin, absorb_shortfall=True)
        refund.refresh_from_db()
        self.assertEqual((refund.instructor_debit, refund.platform_absorbed), (Decimal("10.00"), Decimal("80.00")))
        self.assertEqual(self.balance(self.student), Decimal("150.00"))
        self.assertEqual(self.balance(self.instructor), Decimal("0.00"))

    def test_reject_moves_no_money(self):
        refund = services.request_refund(self.student, self.payment.id, "meh")
        services.reject_refund(refund.id, self.admin, "Course mostly consumed")
        refund.refresh_from_db(); self.payment.refresh_from_db()
        self.assertEqual((refund.status, self.payment.status), ("rejected", "completed"))
        self.assertEqual(self.balance(self.student), Decimal("50.00"))
        with self.assertRaises(services.RefundError):
            services.approve_refund(refund.id, self.admin)

    def test_refund_api(self):
        self.client.force_authenticate(self.student)
        created = self.client.post(
            "/api/payments/refunds/request/", {"payment_id": self.payment.id, "reason": "Bad fit"}, format="json"
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        refund_id = created.data["id"]
        dup = self.client.post(
            "/api/payments/refunds/request/", {"payment_id": self.payment.id, "reason": "again"}, format="json"
        )
        self.assertEqual((dup.status_code, dup.data["code"]), (400, "refund_already_requested"))
        self.assertEqual(self.client.post(f"/api/payments/refunds/{refund_id}/approve/").status_code, 403)

        self.client.force_authenticate(self.admin)
        approved = self.client.post(f"/api/payments/refunds/{refund_id}/approve/", {"notes": "ok"}, format="json")
        self.assertEqual((approved.status_code, approved.data["status"]), (200, "processed"))
        self.assertEqual(self.balance(self.student), Decimal("150.00"))


class ReconcilePayoutLedgerCommandTests(PaymentsFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        services.purchase_course(self.student, self.course.id)  # instructor wallet: 90.00

    def run_command(self, *args):
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command("reconcile_payout_ledger", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_then_apply(self):
        legacy = Payout.objects.create(instructor=self.instructor, amount=Decimal("30.00"), status="paid")
        output = self.run_command()
        self.assertIn("would debit", output)
        self.assertEqual(self.balance(self.instructor), Decimal("90.00"))

        self.run_command("--apply")
        legacy.refresh_from_db()
        self.assertTrue(legacy.wallet_debited)
        self.assertEqual(self.balance(self.instructor), Decimal("60.00"))
        self.assertIn("Nothing to reconcile", self.run_command("--apply"))

    def test_insufficient_wallet_is_skipped(self):
        Payout.objects.create(instructor=self.instructor, amount=Decimal("500.00"), status="paid")
        output = self.run_command("--apply")
        self.assertIn("SKIPPED", output)
        self.assertEqual(self.balance(self.instructor), Decimal("90.00"))


@override_settings(PAYOUT_DETAILS_ENCRYPTION_KEY=Fernet.generate_key().decode())
class LegacyInstructorPayoutMigrationTests(TransactionTestCase):
    """instructors/0003 copies InstructorPayout rows into payments.Payout."""

    migrate_from = [
        ("instructors", "0002_remove_review_stats"),
        ("payments", "0003_payouts_and_refunds_on_wallet_ledger"),
    ]
    migrate_to = [("instructors", "0003_move_payouts_to_wallet_ledger")]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_rows_are_copied_as_undebited_payouts(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        OldUser = old_apps.get_model("accounts", "User")
        OldInstructorPayout = old_apps.get_model("instructors", "InstructorPayout")
        user = OldUser.objects.create(email="legacy@test.com", password="x", role="instructor")
        OldInstructorPayout.objects.create(
            instructor=user, amount=Decimal("25.00"), status="completed", payment_method="bank_transfer",
            payment_details={"iban": "TEST"}, transaction_id="T-1", notes="sent manually",
        )
        OldInstructorPayout.objects.create(instructor=user, amount=Decimal("12.00"), status="pending")

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        new_apps = executor.loader.project_state(self.migrate_to).apps
        NewPayout = new_apps.get_model("payments", "Payout")
        rows = {p.status: p for p in NewPayout.objects.filter(instructor_id=user.id)}
        self.assertEqual(set(rows), {"paid", "pending"})
        self.assertEqual((rows["paid"].amount, rows["paid"].transaction_id), (Decimal("25.00"), "T-1"))
        self.assertEqual(rows["paid"].account_details, {"iban": "TEST"})
        self.assertFalse(any(p.wallet_debited for p in rows.values()))

        encrypt_migration = [("payments", "0005_encrypt_payout_destination")]
        executor = MigrationExecutor(connection)
        with override_settings(PAYOUT_DETAILS_ENCRYPTION_KEY=""):
            with self.assertRaises(ImproperlyConfigured):
                executor.migrate(encrypt_migration)
        self.assertEqual(NewPayout.objects.get(pk=rows["paid"].pk).account_details, {"iban": "TEST"})

        executor = MigrationExecutor(connection)
        executor.migrate(encrypt_migration)
        paid = Payout.objects.get(pk=rows["paid"].pk)
        self.assertNotIn("TEST", paid.account_details_encrypted)
        self.assertEqual(paid.get_account_details(), {"iban": "TEST"})
        self.assertEqual(Payout.objects.get(pk=rows["pending"].pk).account_details_encrypted, "")
        with connection.cursor() as cursor:
            columns = {column.name for column in connection.introspection.get_table_description(
                cursor, Payout._meta.db_table,
            )}
        self.assertNotIn("account_details", columns)


class RetireEventCouponsMigrationTests(PaymentsFixtureMixin, TestCase):
    def test_legacy_events_coupons_are_deactivated(self):
        legacy = self.make_coupon("EVENT20")
        Coupon.objects.filter(pk=legacy.pk).update(applies_to="events")  # bypasses choices, like old rows
        migration = importlib.import_module("payments.migrations.0002_payments_wallet_architecture")
        migration.retire_event_coupons(django_apps, None)
        legacy.refresh_from_db()
        self.assertEqual((legacy.applies_to, legacy.is_active), ("specific", False))
