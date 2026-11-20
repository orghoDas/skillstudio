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

from django.apps import apps as django_apps
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from courses.models import Category, Course
from enrollments.models import Enrollment
from payments import serializers as payment_serializers
from payments import services
from payments.models import Coupon, CouponRedemption, Payment, Payout
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


class PayoutPathTests(PaymentsFixtureMixin, APITestCase):
    """The payout paths used to crash (removed `event` relation, User.first_name)."""

    def test_create_payout_and_list_it(self):
        services.purchase_course(self.student, self.course.id)
        payout = services.create_payout(self.instructor, amount=Decimal("50.00"))
        self.assertEqual(payout.payments.count(), 1)

        self.client.force_authenticate(self.instructor)
        response = self.client.get("/api/payments/payouts/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["instructor_name"], self.instructor.email)

    def test_balance_endpoint(self):
        services.purchase_course(self.student, self.course.id)
        self.client.force_authenticate(self.instructor)
        response = self.client.get("/api/payments/payouts/balance/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data["available"]), Decimal("90.00"))


class RetireEventCouponsMigrationTests(PaymentsFixtureMixin, TestCase):
    def test_legacy_events_coupons_are_deactivated(self):
        legacy = self.make_coupon("EVENT20")
        Coupon.objects.filter(pk=legacy.pk).update(applies_to="events")  # bypasses choices, like old rows
        migration = importlib.import_module("payments.migrations.0002_payments_wallet_architecture")
        migration.retire_event_coupons(django_apps, None)
        legacy.refresh_from_db()
        self.assertEqual((legacy.applies_to, legacy.is_active), ("specific", False))
